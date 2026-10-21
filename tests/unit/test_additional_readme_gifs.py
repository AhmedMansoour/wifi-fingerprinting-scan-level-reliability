"""Validate public additional README GIFs and their measured UJI source boundaries."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "docs/assets/figures"
FILES = ("preview_additional_scan_cases.gif", "preview_xy_candidate_cases.gif")


def test_two_additional_readme_gifs_are_clickable_and_hash_pinned():
    readme = (ROOT / "README.md").read_text(encoding="utf8")
    checker = (ROOT / "scripts/check_public_release.py").read_text(encoding="utf8")
    for filename in FILES:
        path = FIGURES / filename
        assert path.is_file() and path.read_bytes()[:6] == b"GIF89a"
        assert 0 < path.stat().st_size < 2_000_000
        assert readme.count("docs/assets/figures/" + filename) == 1
        assert "docs/assets/figures/" + filename in checker
    assert "learn/interactive-explorer/" in readme
    assert readme.index("### Additional measured scan cases") < readme.index("## Motivation:")
    assert readme.index("### Relative x–y candidate geometry") < readme.index("## Motivation:")


def test_native_source_and_privacy_scope_of_animated_cases():
    data = json.loads((ROOT / "docs/assets/interactive/sample_scans.json").read_text("utf8"))
    assert data["no_calibrated_warning_labels"] is True
    assert len(data["units"]["U02"]["examples"]) == 22
    assert len(data["units"]["U03"]["examples"]) == 22
    scans = sorted(data["units"]["U02"]["examples"], key=lambda v:v["sqs"])
    chosen = (scans[0], scans[11], scans[-1])
    assert len({v["row_id"] for v in chosen}) == 3
    assert all(v["row_id"].startswith("U02-test-") for v in chosen)
    spatial = sorted(data["units"]["U03"]["examples"],
                     key=lambda v:v["indicators"]["sigma_fps"])
    assert spatial[0]["indicators"]["sigma_fps"] < spatial[-1]["indicators"]["sigma_fps"]
    generator = (ROOT / "scripts/generate_additional_readme_gifs.py").read_text("utf8")
    assert 'data["units"]["U02"]' in generator
    assert 'data["units"]["U03"]' in generator
    assert 'scan["diagnostic_centroid"]' in generator
    assert "rotate_relative" in generator
    assert "U09" not in generator
