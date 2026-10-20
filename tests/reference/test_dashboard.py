import json
from pathlib import Path

from wifi_integrity.ui.build import build_dashboard


def test_dashboard_build_and_content():
    report = build_dashboard(Path("."), Path("site"))
    assert report["status"] == "completed"
    assert Path("site/index.html").is_file()
    assert Path("site/assets/styles.css").is_file()
    assert Path("site/assets/app.js").is_file()
    payload = json.loads(Path("site/data/dashboard.json").read_text(encoding="utf-8"))
    assert payload["counts"]["units"] == 10
    assert payload["counts"]["estimators"] == 8
    assert payload["counts"]["predictions"] == 109032
    assert payload["counts"]["indicators"] == 18
    assert payload["counts"]["cases"] == 24
    assert len(payload["indicators"]) == 18
    assert len(payload["cases"]) == 24
    assert len(payload["matrix"]["rows"]) == 10
    assert len(payload["matrix"]["columns"]) == 8
    assert "published reference replay" in payload["meta"]["result_mode"].replace("_", " ")


def test_dashboard_has_accessible_sections():
    html = Path("site/index.html").read_text(encoding="utf-8")
    for section in ["overview", "pipeline", "datasets", "estimators", "matrix", "indicators", "sqs", "cases", "tests", "artifacts", "roadmap"]:
        assert f'id="{section}"' in html
    assert 'aria-label="Dashboard sections"' in html
