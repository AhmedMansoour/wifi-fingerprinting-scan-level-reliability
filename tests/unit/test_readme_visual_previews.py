"""Source-derived README preview SVGs: values, privacy boundaries, and clickable links."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "docs/assets/figures"
SCAN = FIGURES / "preview_scan_comparison.svg"
ABL = FIGURES / "preview_sqs_ablation.svg"
EVIDENCE = FIGURES / "preview_evidence_matrix.svg"


def test_readme_gallery_has_three_clickable_scientific_previews():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.index("### Android scan-level inspection interface") < readme.index("## Visual research explorer")
    assert readme.index("## Visual research explorer") < readme.index("## Motivation:")
    for filename, urlpart in (
        (SCAN.name, "learn/compare-scans/"),
        (ABL.name, "learn/sqs-ablation/"),
        (EVIDENCE.name, "results/evidence-matrix/"),
    ):
        assert readme.count("docs/assets/figures/" + filename.replace(".svg", ".gif")) == 1
        gif = FIGURES / filename.replace(".svg", ".gif")
        assert gif.read_bytes()[:6] == b"GIF89a"
        assert 0 < gif.stat().st_size < 2_000_000
        assert urlpart in readme


def test_previews_are_static_safe_vectors_with_published_numeric_values():
    for path in (SCAN, ABL, EVIDENCE):
        root = ET.parse(path).getroot()
        assert root.attrib["viewBox"] == "0 0 1100 540"
        assert len(path.read_bytes()) < 30000
        content = path.read_text(encoding="utf-8")
        assert chr(60) + "image" not in content
        assert "http://www.w3.org/2000/svg" in content
        for forbidden in ("BlockZ", "PolyU", "BSSID", "latitude", "longitude", "floorplan"):
            assert forbidden not in content
    measured = json.loads((ROOT / "docs/assets/interactive/sample_scans.json").read_text("utf-8"))
    rows = sorted(measured["units"]["U01"]["examples"], key=lambda row: row["sqs"])
    svg = SCAN.read_text("utf-8")
    for row in (rows[0], rows[-1]):
        assert row["row_id"] in svg
        assert f'{row["sqs"]:.3f}' in svg
        assert f'{row["indicators"]["sigma_fps"]:.1f} m' in svg
        for value in row["components"].values():
            assert f'{value:.3f}' in svg
    a1 = json.loads((ROOT / "docs/assets/interactive/sqs_ablation_summary.json").read_text("utf-8"))
    a1svg = ABL.read_text("utf-8")
    for item in a1["variants"]:
        if item["variant_type"] in ("Full", "Conceptual ablation"):
            assert f'{item["median_auroc"]:.3f}' in a1svg
    a3 = json.loads((ROOT / "docs/assets/interactive/evidence_summary.json").read_text("utf-8"))
    a3svg = EVIDENCE.read_text("utf-8")
    for item in sorted(a3["indicators"], key=lambda row: row["association"]["median"], reverse=True)[:8]:
        for key in ("association", "adaptive", "fixed7m"):
            assert f'{item[key]["median"]:.3f}' in a3svg
