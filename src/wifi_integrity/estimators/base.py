"""Common estimator contracts for the reproducible benchmark."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class UnitData:
    unit_id: str
    unit_label: str
    dataset: str
    group: str
    train_rss: np.ndarray
    train_observed: np.ndarray
    test_rss: np.ndarray
    test_observed: np.ndarray
    train_xy: np.ndarray
    test_xy: np.ndarray
    train_scan_id: np.ndarray
    test_scan_id: np.ndarray
    ap_names: tuple[str, ...] | None = None

    @property
    def legacy_train_features(self) -> np.ndarray:
        """Legacy-compatible DictVectorizer view: unobserved APs are zero."""
        return np.where(self.train_observed.astype(bool), self.train_rss, 0.0)

    @property
    def legacy_test_features(self) -> np.ndarray:
        return np.where(self.test_observed.astype(bool), self.test_rss, 0.0)


@dataclass
class EstimatorRun:
    estimator_id: str
    estimator_label: str
    family: str
    mode: str
    unit_id: str
    predictions: pd.DataFrame
    metadata: dict[str, Any]


class BasePositionEstimator(ABC):
    estimator_id: str
    estimator_label: str
    family: str

    def __init__(self, *, seed: int = 42) -> None:
        self.seed = int(seed)

    @abstractmethod
    def fit(self, data: UnitData) -> "BasePositionEstimator":
        raise NotImplementedError

    @abstractmethod
    def predict(self, data: UnitData) -> np.ndarray:
        raise NotImplementedError

    def fit_predict(self, data: UnitData) -> EstimatorRun:
        self.fit(data)
        pred = np.asarray(self.predict(data), dtype=float)
        if pred.shape != data.test_xy.shape:
            raise ValueError(
                f"{self.estimator_id} returned {pred.shape}; expected {data.test_xy.shape}."
            )
        err = np.linalg.norm(pred - data.test_xy, axis=1)
        frame = pd.DataFrame(
            {
                "unit_id": data.unit_id,
                "unit_label": data.unit_label,
                "dataset": data.dataset,
                "group": data.group,
                "scan_id": data.test_scan_id.astype(str),
                "estimator_id": self.estimator_id,
                "estimator_label": self.estimator_label,
                "estimator_family": self.family,
                "x_true": data.test_xy[:, 0],
                "y_true": data.test_xy[:, 1],
                "x_pred": pred[:, 0],
                "y_pred": pred[:, 1],
                "error_2d": err,
                "result_mode": "native",
            }
        )
        return EstimatorRun(
            estimator_id=self.estimator_id,
            estimator_label=self.estimator_label,
            family=self.family,
            mode="native",
            unit_id=data.unit_id,
            predictions=frame,
            metadata={"seed": self.seed},
        )


def load_unit_data(root: Path, unit_id: str, registry: dict[str, dict[str, str]]) -> UnitData:
    path = root / "data" / "processed" / "units" / unit_id / "radio_map_matrices.npz"
    if not path.is_file():
        raise FileNotFoundError(path)
    z = np.load(path, allow_pickle=True)
    info = registry[unit_id]
    arrays = {name: z[name] for name in z.files}
    metadata_path = path.with_name("scan_metadata.csv.gz")
    if metadata_path.is_file():
        metadata = pd.read_csv(metadata_path, usecols=["scan_id", "split", "source_row"])
        source_order = metadata.set_index("scan_id")["source_row"].to_dict()
        train_order = np.argsort(
            [source_order.get(str(scan_id), index) for index, scan_id in enumerate(arrays["train_scan_id"])],
            kind="stable",
        )
        test_order = np.argsort(
            [source_order.get(str(scan_id), index) for index, scan_id in enumerate(arrays["test_scan_id"])],
            kind="stable",
        )
        for key in ["train_rss", "train_observed", "train_xy", "train_scan_id"]:
            arrays[key] = arrays[key][train_order]
        for key in ["test_rss", "test_observed", "test_xy", "test_scan_id"]:
            arrays[key] = arrays[key][test_order]
    return UnitData(
        unit_id=unit_id,
        unit_label=info["label"],
        dataset=info["dataset"],
        group=info["group"],
        train_rss=arrays["train_rss"],
        train_observed=arrays["train_observed"],
        test_rss=arrays["test_rss"],
        test_observed=arrays["test_observed"],
        train_xy=arrays["train_xy"],
        test_xy=arrays["test_xy"],
        train_scan_id=arrays["train_scan_id"],
        test_scan_id=arrays["test_scan_id"],
        ap_names=tuple(json.loads(path.with_name("ap_vocabulary_train.json").read_text())) if path.with_name("ap_vocabulary_train.json").is_file() else None,
    )
