"""Published Android gallery source provenance and privacy guard regression."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "docs/assets/android/android_inspector_four_panel_privacy_safe.webp"
EXPECTED_SHA256 = "6f3df4622813c2a13e88f5ab608134835c8f2d3ab5e378d8df9be04a4e5735a6"


def test_android_gallery_links_to_hash_pinned_image():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("docs/assets/android/android_inspector_four_panel_privacy_safe.webp") == 1
    assert "original site name is redacted" in readme
    assert "confidential floor-plan content masked" in readme
    binary = ASSET.read_bytes()
    assert len(binary) == 132692
    assert binary[:4] == b"RIFF" and binary[8:12] == b"WEBP"
    assert hashlib.sha256(binary).hexdigest() == EXPECTED_SHA256


def test_image_is_allowlisted_only_by_verified_hash():
    privacy_gate = (ROOT / "scripts/check_public_release.py").read_text(encoding="utf-8")
    assert "UI_SCREENSHOT_SHA256" in privacy_gate
    assert EXPECTED_SHA256 in privacy_gate
    assert "if rel == UI_SCREENSHOT:" in privacy_gate
