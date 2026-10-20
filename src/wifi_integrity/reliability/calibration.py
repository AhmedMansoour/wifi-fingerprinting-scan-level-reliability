"""Frozen reference profiles for adverse percentiles and composite scaling.

Reference roles are explicit: retrospective profiles may describe an evaluated
cohort, but must not be presented as independent online calibration.
"""
from __future__ import annotations
import hashlib, json
import numpy as np
import pandas as pd
ALIASES = {'d_cand': 'D_cand', 'i_k': 'I_k', 'sqs': 'SQS', 'c_sigma': 'C_sigma', 'fii': 'FII'}
COMPOSITES = {'SQS', 'C_sigma', 'FII'}


def adverse_percentile(value, reference, direction):
    if direction not in {'high', 'low'}: raise ValueError('Direction must be high or low')
    values = np.sort(np.asarray(reference, float))
    if not len(values) or not np.isfinite(value): return float('nan')
    if not np.isfinite(values).all(): raise ValueError('Reference values must be finite')
    if direction == 'high': return float(np.searchsorted(values, value, side='right') / len(values))
    return float((len(values) - np.searchsorted(values, value, side='left')) / len(values))


def _scaled(value, distribution):
    lo, hi = distribution['q05'], distribution['q95']
    if not np.isfinite(value) or hi <= lo: return .5
    return float(np.clip((value - lo)/(hi - lo), 0, 1))


def composite_values(row, distributions):
    s = lambda name: _scaled(float(row[name]), distributions[name])
    signal = 1 - s('min_rss_distance')
    spread = s('sigma_fps')
    geometry = 1 - (spread + s('D_cand'))/2
    count, overlap, density = s('ap_count'), s('ap_overlap'), s('local_rp_density')
    return {'SQS': (signal+geometry+count+overlap+density)/5,
            'C_sigma': signal/(1+spread),
            'FII': (signal+count+overlap+s('nearest_match_isolation')+1-s('ap_set_novelty'))/5}


def fit_profile(reference, specs, *, floor_id, estimator, reference_id, role, evaluation_scan_ids=()):
    if role not in {'calibration', 'retrospective'}: raise ValueError('Explicit reference role required')
    if not all(str(v).strip() for v in [floor_id, estimator, reference_id]): raise ValueError('Profile identity is required')
    if 'scan_id' not in reference or reference.scan_id.isna().any() or reference.scan_id.duplicated().any():
        raise ValueError('Unique nonmissing reference scan IDs are required')
    heldout = {str(v) for v in evaluation_scan_ids}
    if heldout & set(reference.scan_id.astype(str)): raise ValueError('Reference and evaluation scan IDs overlap')
    if len(reference) < 8: raise ValueError('At least eight reference records are required')
    specs = [{**s, 'id': ALIASES.get(s['id'], s['id'])} for s in specs]
    if len(specs) != 18 or len({s['id'] for s in specs}) != 18: raise ValueError('All 18 indicator definitions are required')
    profile = {'schema_version': 1, 'floor_id': str(floor_id), 'estimator': str(estimator), 'diagnostic_m': 10,
        'reference_id': str(reference_id), 'reference_role': role, 'n_reference': len(reference),
        'cutoff': .8, 'scaling_quantiles': [.05, .95], 'heldout_id_check': bool(heldout),
        'indicators': {}}
    def fit_column(name, series, direction):
        values = pd.to_numeric(series, errors='coerce').to_numpy(float)
        values = np.sort(values[np.isfinite(values)])
        if len(values) < 8: raise ValueError(f'Insufficient finite calibration values: {name}')
        if direction not in {'high', 'low'}: raise ValueError('Invalid adverse direction')
        lo, hi = np.quantile(values, [.05, .95])
        profile['indicators'][name] = {'adverse_direction': direction, 'q05': float(lo), 'q95': float(hi), 'sorted_values': values.tolist()}
    for spec in specs:
        if spec['id'] not in COMPOSITES: fit_column(spec['id'], reference[spec['id']], spec['adverse_direction'])
    composites = pd.DataFrame([composite_values(row, profile['indicators']) for _, row in reference.iterrows()])
    for spec in specs:
        if spec['id'] in COMPOSITES: fit_column(spec['id'], composites[spec['id']], spec['adverse_direction'])
    profile['reference_values_sha256'] = hashlib.sha256(json.dumps(profile['indicators'], sort_keys=True, allow_nan=False).encode()).hexdigest()
    return profile


def apply_profile(frame, profile, *, floor_id, estimator, diagnostic_m=10, online=True):
    if str(floor_id) != profile['floor_id'] or estimator != profile['estimator'] or diagnostic_m != profile['diagnostic_m']:
        raise ValueError('Floor, estimator, or diagnostic M does not match the frozen profile')
    if online and profile['reference_role'] != 'calibration':
        raise ValueError('Retrospective profiles cannot be used as independently calibrated online profiles')
    out = frame.copy()
    for name in COMPOSITES: out[name] = [composite_values(row, profile['indicators'])[name] for _, row in frame.iterrows()]
    for name, distribution in profile['indicators'].items():
        out[name+'_adverse_percentile'] = [adverse_percentile(float(v), distribution['sorted_values'], distribution['adverse_direction']) for v in out[name]]
        # NaN does not warn; callers must also display missing diagnostics explicitly.
        out[name+'_warning'] = out[name+'_adverse_percentile'] >= profile['cutoff']
    return out


def android_rows(profile):
    return [{'floor_unique_id': profile['floor_id'], 'estimator': profile['estimator'], 'indicator_id': name,
             'adverse_direction': d['adverse_direction'], 'q05': d['q05'], 'q95': d['q95'],
             'sorted_values_json': json.dumps(d['sorted_values'], separators=(',', ':'))}
            for name, d in profile['indicators'].items()]
