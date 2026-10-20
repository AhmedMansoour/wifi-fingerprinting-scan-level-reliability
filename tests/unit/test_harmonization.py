import numpy as np

from wifi_integrity.data.harmonize import (
    dense_matrix,
    diagnostic_ap_vocabulary,
    parse_rss_json,
    training_ap_vocabulary,
)


def test_parse_rss_json_drops_invalid_values():
    parsed = parse_rss_json('{"AP1": -60, "AP2": "-75", "bad": "x"}')
    assert parsed == {"AP1": -60.0, "AP2": -75.0}


def test_ap_vocabulary_is_deterministic():
    train = [{"B": -50, "A": -70}, {"A": -60}, {"C": -80}]
    test = [{"C": -70, "D": -90}]
    assert training_ap_vocabulary(train) == ["A", "B", "C"]
    assert diagnostic_ap_vocabulary(train, test, max_aps=3) == ["A", "C", "B"]


def test_dense_matrix_uses_explicit_missing_floor():
    values, observed = dense_matrix([{"AP1": -60}], ["AP1", "AP2"])
    np.testing.assert_allclose(values, [[-60, -110]])
    np.testing.assert_array_equal(observed, [[1, 0]])
