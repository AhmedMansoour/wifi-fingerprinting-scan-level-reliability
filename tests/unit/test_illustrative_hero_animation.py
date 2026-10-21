"""Protect the four-panel illustrative GIF in the repository README."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "docs/assets/figures/preview_illustrative_four_ai_cases.gif"
EXPECTED = "7d3f8c91e207d9f2b18a385858fa330788909735ca515359ead08b5d621748ba"


def test_illustrative_hero_gif_is_hashed_and_labeled():
    data = ASSET.read_bytes()
    assert data[:6] == b"GIF89a"
    assert len(data) == 1347110
    assert hashlib.sha256(data).hexdigest() == EXPECTED
    assert int.from_bytes(data[6:8], "little") == 1000
    assert int.from_bytes(data[8:10], "little") == 606

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("docs/assets/figures/preview_illustrative_four_ai_cases.gif") == 1
    assert readme.index("### Animated interface concept: four illustrative cases") < readme.index("### Android scan-level inspection interface")
    assert "AI-generated UI mock-ups" in readme
    assert "**fictional**" in readme
    assert "not measured research outputs" in readme
    assert "calibrated warning decisions" in readme

    safety = (ROOT / "scripts/check_public_release.py").read_text(encoding="utf-8")
    assert "'docs/assets/figures/preview_illustrative_four_ai_cases.gif': '7d3f8c91e207d9f2b18a385858fa330788909735ca515359ead08b5d621748ba'" in safety
