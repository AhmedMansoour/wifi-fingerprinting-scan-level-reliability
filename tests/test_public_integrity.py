"""Small deterministic tests for the public native reliability entry point."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from reproduce_public_integrity import _read_unit, input_files, run


def test_unknown_unit_is_not_silently_replaced_with_synthetic_data(tmp_path):
    with pytest.raises(ValueError, match="Unpublished"):
        run(tmp_path, ["U08"], write=False)


def test_duplicate_unit_selection_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="distinct"):
        run(tmp_path, ["U09", "U09"], write=False)


def test_missing_measured_input_is_not_generated(tmp_path):
    class Spec:
        dataset = "UJIndoorLoc"
        group = "Building0"
    with pytest.raises(FileNotFoundError, match="Missing public empirical file"):
        _read_unit(tmp_path, "U01", Spec())


def test_hk_input_requires_ordered_radio_map_and_queries(tmp_path):
    names = input_files(tmp_path, "U09")
    assert [f.name for f in names] == ["hk_u09_train.csv.gz", "hk_u09_test_ordered.csv.gz"]
