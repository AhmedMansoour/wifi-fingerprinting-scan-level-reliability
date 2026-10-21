"""Scientific provenance checks for the read-only public visualization pages."""
import csv
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "assets" / "interactive"


def read_csv(path):
    with (ROOT / path).open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def test_evidence_matrix_matches_archived_sources():
    payload = json.loads((ASSETS / "evidence_summary.json").read_text("utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["unit_level_estimator_cells_included"] is False
    assert payload["units"] == 10 and payload["estimators_in_study"] == 8
    assert len(payload["estimators"]) == 8
    assert len(payload["indicators"]) == 18
    source_paths = payload["source_files"]
    assert len(source_paths) == 4
    estimators, association, adaptive, fixed = (read_csv(path) for path in source_paths)
    for item, native in zip(payload["estimators"], estimators):
        assert item["name"] == native["estimator_display"]
        assert item["units"] == int(native["units_covered"])
        for key, column in [("median", "median_of_unit_medians_m"), ("p90", "median_unit_p90_m"), ("rmse", "median_unit_rmse_m")]:
            assert item[key] == pytest.approx(float(native[column]), abs=1e-11)
    lookup = [{row["indicator_id"]: row for row in rows} for rows in (association, adaptive, fixed)]
    for item in payload["indicators"]:
        indicator_id = item["id"]
        for category, source, metric in zip(("association", "adaptive", "fixed7m"), lookup, ("aligned_rho", "auroc", "auroc")):
            row = source[indicator_id]
            metric_values = item[category]
            for name, prefix in (("median", "median"), ("low", "ci95_low"), ("high", "ci95_high")):
                assert metric_values[name] == pytest.approx(float(row[prefix + "_" + metric]), abs=1e-11)
            assert metric_values["n"] == int(row["n_conditions"])


def test_site_links_and_visualization_privacy_boundaries():
    readme = (ROOT / "README.md").read_text("utf-8")
    site_index = (ROOT / "docs" / "index.md").read_text("utf-8")
    docs_nav = (ROOT / "mkdocs.yml").read_text("utf-8")
    for name in ("learn/compare-scans", "results/evidence-matrix"):
        assert name in readme and name in site_index and name in docs_nav
    for name in ("comparison.html", "evidence.html"):
        assert (ASSETS / name).is_file()
    for name in ("comparison.js", "evidence.js"):
        body = (ASSETS / name).read_text("utf-8")
        assert "fetch(" in body
        assert "latitude" not in body and "longitude" not in body
        assert "floorplan" not in body.lower()
    # The new comparison uses already-approved native inputs; no coordinate reconstruction is added.
    assert "sample_scans.json" in (ASSETS / "comparison.js").read_text("utf-8")
    assert "unit_level_estimator_cells_included" in (ASSETS / "evidence.js").read_text("utf-8")
