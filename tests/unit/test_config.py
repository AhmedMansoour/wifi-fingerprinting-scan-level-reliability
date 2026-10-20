from wifi_integrity.config import load_config_bundle


def test_scientific_configuration_is_locked():
    bundle = load_config_bundle("config")
    assert len(bundle["datasets"]["units"]) == 10
    assert len(bundle["estimators"]["estimators"]) == 8
    assert len(bundle["indicators"]["indicators"]) == 18
    estimator_ids = {item["id"] for item in bundle["estimators"]["estimators"]}
    assert "catboost" in estimator_ids
    assert "ridge" not in estimator_ids
    assert bundle["analysis"]["adaptive_gross_error"] == {
        "tail_quantile": 0.75,
        "multiplier": 1.5,
        "sensitivity_quantiles": [0.70, 0.75, 0.80],
        "sensitivity_multipliers": [1.0, 1.5, 2.0],
    }
