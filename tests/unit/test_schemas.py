from wifi_integrity.schemas import CANONICAL_PREDICTION_COLUMNS, HARMONIZED_SCAN_COLUMNS


def test_prediction_schema_contains_key_fields():
    assert {"unit_id", "scan_id", "estimator_id", "error_2d"}.issubset(
        CANONICAL_PREDICTION_COLUMNS
    )


def test_harmonized_schema_contains_lineage_fields():
    assert {"unit_id", "scan_id", "dataset", "group", "split", "rss_json"}.issubset(
        HARMONIZED_SCAN_COLUMNS
    )
