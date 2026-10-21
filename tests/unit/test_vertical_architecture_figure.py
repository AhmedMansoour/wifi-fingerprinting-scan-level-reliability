"""Check the reviewed portrait architecture SVG used in the repository README."""
import hashlib
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
SVG = ROOT / "docs/assets/figures/fig_fingerprint_retrieval_vertical.svg"
EXPECTED_SHA = "63c8b0b5776bdbb7ffd756cb030c3822affed0e14967c814e5edcbba7d78a9be"


def test_figure_is_portrait_svg_linked_from_readme():
    document = ElementTree.fromstring(SVG.read_bytes())
    assert document.tag.endswith("svg")
    assert float(document.attrib["width"]) < float(document.attrib["height"])
    assert document.attrib["viewBox"] == "0 0 900 1575"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("docs/assets/figures/fig_fingerprint_retrieval_vertical.svg") == 1
    assert "flowchart LR" not in readme.split("**Figure 1.", 1)[1].split("The first ten retrieved", 1)[0]


def test_figure_content_matches_reviewed_asset():
    binary = SVG.read_bytes()
    assert hashlib.sha256(binary).hexdigest() == EXPECTED_SHA
    assert b"RSS-template retrieval" in binary
    assert b"15 scan-level diagnostic quantities" in binary
    assert b"nearest-RP distance" in binary
    assert b"<script" not in binary and (b"<" + b"image") not in binary
