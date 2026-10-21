"""Archived A1 SQS visualization verifies provenance and separates evidence scales."""
import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "docs/assets/interactive"
SOURCE = ROOT / "results/approved/revision_summaries/A1/A1_SQS_main_component_ablation_summary.csv"


def test_sqs_ablation_export_matches_approved_a1_csv():
    data = json.loads((ASSET / "sqs_ablation_summary.json").read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert data["no_scan_level_ablation_prediction"] is True
    assert data["no_browser_retraining"] is True
    assert data["source"] == SOURCE.relative_to(ROOT).as_posix()
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        original = list(csv.DictReader(stream))
    exported = data["variants"]
    assert len(original) == len(exported) == 11
    assert set(x["variant_id"] for x in original) == set(x["variant_id"] for x in exported)
    for entry, source in zip(exported, original):
        assert entry.keys() == source.keys()
        for k, v in source.items():
            if k in ("variant_id", "label", "variant_type"):
                assert entry[k] == v
            else:
                assert entry[k] == pytest.approx(float(v), rel=1e-12, abs=1e-12)
    types = [x["variant_type"] for x in exported]
    assert types.count("Full") == 1
    assert types.count("Component") == 5
    assert types.count("Conceptual ablation") == 5


def test_sqs_native_components_reconstruct_all_public_examples():
    public = json.loads((ASSET / "sample_scans.json").read_text(encoding="utf-8"))
    expected = {"signal_match", "candidate_geometry", "ap_count", "ap_overlap", "local_density"}
    assert public["no_calibrated_warning_labels"] is True
    assert len(public["units"]) == 4
    for unit in public["units"].values():
        assert len(unit["examples"]) == 22
        for scan in unit["examples"]:
            assert set(scan["components"]) == expected
            assert sum(scan["components"].values()) / 5 == pytest.approx(scan["sqs"], abs=1e-8)


def test_sqs_visualization_is_linked_and_distinguishes_retrospective_scope():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    homepage = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    nav = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    page = (ROOT / "docs/learn/sqs-ablation.md").read_text(encoding="utf-8")
    script = (ASSET / "sqs-lab.js").read_text(encoding="utf-8")
    embed = (ROOT / "docs/assets/javascripts/interactive-embed.js").read_text(encoding="utf-8")
    assert "learn/sqs-ablation" in readme and "learn/sqs-ablation" in homepage
    assert "learn/sqs-ablation.md" in nav
    assert "sqs-lab.html" in page and "interquartile ranges" in page.lower()
    assert "wifi-sqs-ablation" in script and "wifi-sqs-ablation" in embed
    assert "sample_scans.json" in script and "sqs_ablation_summary.json" in script
    assert "no_calibrated_warning_labels" in script
