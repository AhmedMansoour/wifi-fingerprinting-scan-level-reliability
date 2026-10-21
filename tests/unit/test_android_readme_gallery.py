"""Published Android gallery source provenance and privacy guard regression."""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "docs/assets/android/android_inspector_ui_public.webp"
EXPECTED_SHA256 = "f275dcc1cbf66a1489b0989e63c57e0485c9c084f19442adc300b1ba5ff93e8f"


def test_android_gallery_links_to_hash_pinned_image():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("docs/assets/android/android_inspector_ui_public.webp") == 1
    assert "original site name is redacted" in readme
    assert "real floor-plan panel is excluded" in readme
    binary = ASSET.read_bytes()
    assert len(binary) == 54730
    assert binary[:4] == b"RIFF" and binary[8:12] == b"WEBP"
    assert hashlib.sha256(binary).hexdigest() == EXPECTED_SHA256


def test_image_is_allowlisted_only_by_verified_hash():
    privacy_gate = (ROOT / "scripts/check_public_release.py").read_text(encoding="utf-8")
    assert "UI_SCREENSHOT_SHA256" in privacy_gate
    assert EXPECTED_SHA256 in privacy_gate
    assert "if rel == UI_SCREENSHOT:" in privacy_gate
