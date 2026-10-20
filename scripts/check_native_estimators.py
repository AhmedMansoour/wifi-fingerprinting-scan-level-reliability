"""Small fit/inference smoke tests; these do not reproduce study accuracy."""
import os
os.environ.setdefault('TF_NUM_INTRAOP_THREADS', '1')
os.environ.setdefault('TF_NUM_INTEROP_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import argparse, json
from pathlib import Path
import numpy as np
from wifi_integrity.estimators.base import UnitData
from wifi_integrity.estimators.retrieval import RetrievalEstimator
from wifi_integrity.estimators.classical import make_random_forest, make_extra_trees, make_hgb
from wifi_integrity.estimators.catboost_model import CatBoostCoordinateEstimator
from wifi_integrity.estimators.deep import DeepCoordinateEstimator

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-all', action='store_true')
    args = parser.parse_args()
    rng = np.random.default_rng(42)
    x = rng.normal(-65, 10, (92, 20)).astype(np.float32)
    xy = (x[:, :2]+80)/3
    data = UnitData('synthetic', 'Synthetic', 'synthetic', 'demo', x[:80], np.ones_like(x[:80], bool),
                    x[80:], np.ones_like(x[80:], bool), xy[:80], xy[80:],
                    np.array([f't{i}' for i in range(80)]), np.array([f'q{i}' for i in range(12)]))
    estimators = [RetrievalEstimator(estimator_id='knn', estimator_label='KNN', k=3, metric='euclidean'),
        RetrievalEstimator(estimator_id='wknn', estimator_label='WKNN', k=3, metric='euclidean', weight_power=1),
        make_random_forest(), make_extra_trees(), make_hgb(), CatBoostCoordinateEstimator(iterations=20),
        DeepCoordinateEstimator('transformer_ap', epochs=2, batch_size=32),
        DeepCoordinateEstimator('residual_cnn', epochs=2, batch_size=32)]
    results = []
    for estimator in estimators:
        try:
            run = estimator.fit_predict(data)
            assert len(run.predictions) == 12
            assert np.isfinite(run.predictions[['x_pred', 'y_pred']].to_numpy()).all()
            results.append({'estimator': estimator.estimator_id, 'status': 'passed', 'prediction_rows': 12})
        except ImportError:
            if args.require_all: raise
            results.append({'estimator': estimator.estimator_id, 'status': 'skipped_missing_optional_dependency'})
    out = Path(__file__).resolve().parents[1] / 'results/logs/native_smoke.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))

if __name__ == '__main__': main()
