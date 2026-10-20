"""Validation and regression gates for the harmonized data release."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from wifi_integrity.data.registry import UnitSpec


class RegressionMismatch(AssertionError):
    """Raised when regenerated data diverge from the frozen approved state."""


def validate_unit_audit(audit_path: str | Path, units: list[UnitSpec]) -> dict[str, object]:
    audit = pd.read_csv(audit_path)
    expected_ids = {unit.id for unit in units}
    found_ids = set(audit["unit_id"].astype(str))
    if found_ids != expected_ids:
        raise RegressionMismatch(f"Unit IDs differ: expected {expected_ids}, found {found_ids}")

    mismatches: list[str] = []
    for unit in units:
        row = audit[audit["unit_id"] == unit.id].iloc[0]
        if int(row["n_train"]) != unit.expected_train:
            mismatches.append(f"{unit.id} train {row['n_train']} != {unit.expected_train}")
        if int(row["n_test"]) != unit.expected_test:
            mismatches.append(f"{unit.id} test {row['n_test']} != {unit.expected_test}")
        if int(row["duplicate_scan_ids"]) != 0:
            mismatches.append(f"{unit.id} duplicate scan IDs")
        if int(row["invalid_xy"]) != 0:
            mismatches.append(f"{unit.id} invalid coordinates")
    if mismatches:
        raise RegressionMismatch("; ".join(mismatches))

    total_train = int(audit["n_train"].sum())
    total_test = int(audit["n_test"].sum())
    if total_train != 54520 or total_test != 13629:
        raise RegressionMismatch(
            f"Approved totals changed: train={total_train}, test={total_test}"
        )
    return {
        "status": "passed",
        "units": len(audit),
        "train_rows": total_train,
        "test_rows": total_test,
        "total_rows": total_train + total_test,
    }


def write_validation_report(report: dict[str, object], path: str | Path) -> None:
    Path(path).write_text(json.dumps(report, indent=2), encoding="utf-8")
