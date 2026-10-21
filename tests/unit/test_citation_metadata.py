"""Companion manuscript citation is precise and does not imply publication."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TITLE = "An Intelligent Framework for Scan-Level Reliability, Accuracy Diagnostics, and Gross-Error Detection in Wi-Fi Fingerprinting-Based Indoor Positioning Systems"
AUTHORS = (
    "Mansour, Ahmed and Chen, Wu and Luo, Huan and Adham, Mahmoud and "
    "Wang, Jingxian and Abdallah, Mahmoud and Weng, Duojie"
)
JOURNAL = "Expert Systems with Applications"
MANUSCRIPT = "ESWA-D-26-23796R2"


def test_companion_bibtex_has_verified_bibliography_without_invented_doi():
    bib = (ROOT / "CITATION.bib").read_text(encoding="utf-8")
    assert bib.count("@article{mansour2026wifiintegrity") == 1
    assert "@unpublished" not in bib
    assert f"author = {{{AUTHORS}}}" in bib
    assert f"title = {{{TITLE}}}" in bib
    assert f"journal = {{{JOURNAL}}}" in bib
    assert MANUSCRIPT in bib
    assert "Manuscript under revision" in bib
    assert "doi =" not in bib.lower()
    assert "volume =" not in bib.lower()
    assert "pages =" not in bib.lower()


def test_readme_displays_full_title_and_all_seven_authors():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert TITLE in readme
    assert JOURNAL in readme and MANUSCRIPT in readme
    assert "Mansour, A., Chen, W., Luo, H., Adham, M., Wang, J., Abdallah, M., and Weng, D." in readme
    assert "CITATION.bib" in readme and "CITATION.cff" in readme
    assert "formatted as `@article`" in readme
    assert "not yet published" in readme.lower()


def test_github_citation_descriptor_identifies_software_without_fake_publication():
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "cff-version: 1.2.0" in cff
    assert "type: software" in cff
    assert "given-names: Ahmed" in cff
    assert "family-names: Mansour" in cff
    assert "CITATION.bib" in cff
    assert "doi:" not in cff.lower()
    assert "date-released:" not in cff.lower()
