import copy
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml
from wifi_integrity.reliability.calibration import fit_profile, apply_profile, adverse_percentile, COMPOSITES, ALIASES


def example():
    specs = yaml.safe_load((Path(__file__).resolve().parents[2]/'config/indicators.yaml').read_text())['indicators']
    data = {ALIASES.get(s['id'],s['id']): np.arange(12, dtype=float)+i for i,s in enumerate(specs) if ALIASES.get(s['id'],s['id']) not in COMPOSITES}
    return pd.DataFrame(dict(scan_id=[f'c{i}' for i in range(12)], **data)), specs


def test_ties_and_missing():
    assert adverse_percentile(2, [1,2,2,3], 'high') == .75
    assert adverse_percentile(2, [1,2,2,3], 'low') == .75
    assert np.isnan(adverse_percentile(np.nan, [1,2,3], 'high'))


def test_profile_is_frozen_and_condition_specific():
    frame, specs = example()
    profile = fit_profile(frame, specs, floor_id='f', estimator='WKNN_k3', reference_id='r1', role='calibration', evaluation_scan_ids=['q'])
    before = copy.deepcopy(profile)
    query = frame.iloc[:1].copy();query['min_rss_distance'] = 9999
    out = apply_profile(query, profile, floor_id='f', estimator='WKNN_k3')
    assert out.min_rss_distance_warning.iloc[0]
    assert profile == before
    with pytest.raises(ValueError): apply_profile(query, profile, floor_id='other', estimator='WKNN_k3')


def test_retrospective_role_and_overlap():
    frame, specs = example()
    p = fit_profile(frame, specs, floor_id='f', estimator='e', reference_id='r', role='retrospective')
    with pytest.raises(ValueError): apply_profile(frame, p, floor_id='f', estimator='e')
    with pytest.raises(ValueError): fit_profile(frame, specs, floor_id='f', estimator='e', reference_id='r', role='calibration', evaluation_scan_ids=['c0'])
