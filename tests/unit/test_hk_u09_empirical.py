"""Evaluation protocol smoke tests on a tiny fabricated dataset."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_hk_u09 import evaluate, load_u09


def test_hk_u09_small_split_excludes_test_only_access_points(tmp_path):
    rows = []
    for i in range(7):
        rows.append(dict(dataset="fixture",group="fixture",split="train" if i < 5 else "test",
                         row_id=f"T{i}",floor=0,x=float(i),y=0.0,
                         rss_json=json.dumps({"AP1":float(-50-i),**({"TEST_AP":-30.} if i>=5 else {})})))
    p = tmp_path / "tiny.csv.gz"
    pd.DataFrame(rows).to_csv(p, compression="gzip", index=False)
    unit, test, meta = load_u09(p, check_hash=False)
    assert unit.ap_names == ("AP1",)
    assert meta["test_only_ap_count"] == 1
    assert len(test) == 2
    summary, pred = evaluate(p,estimators=("knn","wknn"),k=2,check_hash=False)
    assert summary["input"]["train_scans"] == 5
    assert set(summary["estimator_results"]) == {"knn","wknn"}
    assert np.isfinite(pred.error_2d.to_numpy()).all()
    assert len(pred) == 4


def test_hk_u09_hash_required(tmp_path):
    p = tmp_path / "arbitrary.csv.gz"
    pd.DataFrame({"something":[1]}).to_csv(p,compression="gzip",index=False)
    with pytest.raises(ValueError, match="digest"):
        load_u09(p)


def test_hk_u09_bad_split_ids(tmp_path):
    p = tmp_path / "bad.csv.gz"
    pd.DataFrame([
        dict(dataset="fixture",group="fixture",split=split,row_id="same",floor=0,x=0,y=0,rss_json='{"AP1":-60}')
        for split in ("train","train","test")
    ]).to_csv(p,compression="gzip",index=False)
    with pytest.raises(ValueError, match="Duplicate scan identifiers"):
        load_u09(p,check_hash=False)
