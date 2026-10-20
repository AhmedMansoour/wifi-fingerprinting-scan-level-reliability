import numpy as np

from wifi_integrity.estimators.base import UnitData
from wifi_integrity.estimators.retrieval import RetrievalEstimator


def synthetic_unit():
    train_rss = np.array([[-50, -110], [-80, -60], [-55, -110]], dtype=np.float32)
    observed = (train_rss != -110).astype(np.uint8)
    test_rss = np.array([[-52, -110]], dtype=np.float32)
    test_observed = (test_rss != -110).astype(np.uint8)
    return UnitData(
        unit_id="UX",
        unit_label="Synthetic",
        dataset="synthetic",
        group="one",
        train_rss=train_rss,
        train_observed=observed,
        test_rss=test_rss,
        test_observed=test_observed,
        train_xy=np.array([[0, 0], [10, 0], [1, 0]], dtype=float),
        test_xy=np.array([[0.5, 0]], dtype=float),
        train_scan_id=np.array(["t0", "t1", "t2"], dtype=object),
        test_scan_id=np.array(["q0"], dtype=object),
    )


def test_retrieval_common_interface():
    estimator = RetrievalEstimator(
        estimator_id="knn", estimator_label="KNN", k=1, metric="euclidean"
    )
    run = estimator.fit_predict(synthetic_unit())
    assert len(run.predictions) == 1
    assert set(run.predictions["result_mode"]) == {"native"}
    assert run.predictions.loc[0, "estimator_id"] == "knn"
    assert np.isfinite(run.predictions.loc[0, "error_2d"])


def test_weighted_retrieval_prediction_shape():
    estimator = RetrievalEstimator(
        estimator_id="wknn",
        estimator_label="WKNN",
        k=2,
        metric="euclidean",
        weight_power=2,
    )
    run = estimator.fit_predict(synthetic_unit())
    assert run.predictions[["x_pred", "y_pred"]].shape == (1, 2)
