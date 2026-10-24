"""Verify the published ESWA article metadata in all repository citation surfaces."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TITLE = "An Intelligent Framework for Scan-Level Reliability, Accuracy Diagnostics, and Gross-Error Detection in Wi-Fi Fingerprinting-Based Indoor Positioning Systems"
AUTHORS_BIB = (
    "Ahmed Mansour and Wu Chen and Huan Luo and Mahmoud Adham and "
    "Jingxian Wang and Mahmoud Abdallah and Duojie Weng"
)
JOURNAL = "Expert Systems with Applications"
DOI = "10.1016/j.eswa.2026.134855"
ARTICLE_NUMBER = "134855"
PUBLISHER = "https://www.sciencedirect.com/science/article/pii/S0957417426037589"


def test_companion_bibtex_has_published_bibliography():
    bib = (ROOT / "CITATION.bib").read_text(encoding="utf-8")
    assert bib.count("@article{MANSOUR2026134855,") == 1
    assert f"author = {{{AUTHORS_BIB}}}" in bib
    assert f"title = {{{TITLE}}}" in bib
    assert f"journal = {{{JOURNAL}}}" in bib
    assert "year = {2026}" in bib
    assert f"pages = {{{ARTICLE_NUMBER}}}" in bib
    assert f"doi = {{{DOI}}}" in bib
    assert f"url = {{{PUBLISHER}}}" in bib
    assert "Manuscript under revision" not in bib
    assert "volume =" not in bib.lower()


def test_readme_displays_published_article_and_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert TITLE in readme
    assert JOURNAL in readme
    assert DOI in readme
    assert ARTICLE_NUMBER in readme
    assert PUBLISHER in readme
    assert "researchgate.net/publication/416717447" in readme
    assert "Mansour, A., Chen, W., Luo, H., Adham, M., Wang, J., Abdallah, M., and Weng, D." in readme
    assert "CITATION.bib" in readme and "CITATION.cff" in readme
    assert "not yet published" not in readme.lower()
    assert "manuscript under revision" not in readme.lower()


def test_github_citation_descriptor_prefers_published_article():
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "cff-version: 1.2.0" in cff
    assert "type: software" in cff
    assert "preferred-citation:" in cff
    assert "  type: article" in cff
    assert cff.count("family-names:") == 8  # one software author plus seven article authors
    assert TITLE in cff
    assert JOURNAL in cff
    assert f'doi: "{DOI}"' in cff
    assert PUBLISHER in cff
    assert "CITATION.bib" in cff
    assert "date-released:" not in cff.lower()
