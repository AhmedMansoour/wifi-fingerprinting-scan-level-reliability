"""Export a small, inspectable subset of ORIGINAL public empirical indicator outputs.

The exporter does not recompute indicators or infer warnings. To explain SQS it
reconstructs its five components using the existing, unmodified scaling function
on each ENTIRE evaluation unit, then selects representative held-out scans.

Usage:
    python scripts/export_interactive_examples.py
    python scripts/export_interactive_examples.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wifi_integrity.reliability.sqs import robust_unit_scale  # noqa: E402

UNITS = ('U01', 'U02', 'U03', 'U09')
QUANTILE_SAMPLES = np.array([0, .025, .055, .09, .13, .18, .23, .29, .35,
 .41, .47, .53, .59, .65, .71, .77, .82, .87, .91, .945, .972, 1])
INDICATORS = ('min_rss_distance', 'max_cosine_similarity', 'ap_count',
              'ap_overlap', 'sigma_fps', 'D_cand', 'local_rp_density',
              'nearest_match_isolation', 'ap_set_novelty', 'rss_gradient_proxy',
              'I_k', 'rss_std', 'rss_range', 'mean_ap_overlap', 'C_sigma', 'FII')


def _finite(value):
    if value is None or pd.isna(value):
        return None
    v = float(value)
    return round(v, 10) if np.isfinite(v) else None


def _unit_input(unit):
    base = ROOT / 'data/empirical'
    return base / (f'{unit}.csv.gz' if unit != 'U09' else 'hk_u09_test_ordered.csv.gz')


def _components(frame):
    # Reproduce the original five-component formula without a separate
    # percentile or weighting implementation. Scaling uses *all* held-out rows.
    signal = 1 - robust_unit_scale(frame['min_rss_distance'])
    geometry = 1 - pd.concat([
        robust_unit_scale(frame['sigma_fps']),
        robust_unit_scale(frame['D_cand'])], axis=1).mean(axis=1, skipna=True)
    components = pd.DataFrame({
        'signal_match': signal,
        'candidate_geometry': geometry,
        'ap_count': robust_unit_scale(frame['ap_count']),
        'ap_overlap': robust_unit_scale(frame['ap_overlap']),
        'local_density': robust_unit_scale(frame['local_rp_density']),
    })
    reconstructed = components.mean(axis=1, skipna=True)
    differences = (reconstructed - frame['SQS']).abs()
    if not np.isfinite(differences).all() or differences.max() > 1e-12:
        raise AssertionError('SQS components do not reproduce the source results')
    return components


def _make_unit(unit):
    root = ROOT / 'examples/empirical_integrity'
    features_path = root / f'{unit}_scan_reliability.csv.gz'
    candidates_path = root / f'{unit}_retrieved_candidates.csv.gz'
    input_path = _unit_input(unit)
    features = pd.read_csv(features_path, dtype={'row_id':'str'})
    candidates = pd.read_csv(candidates_path, dtype={'row_id':'str'})
    inputs = pd.read_csv(input_path, dtype={'row_id':'str'}, usecols=['row_id','split','rss_json'])
    inputs = inputs.loc[inputs['split'].eq('test'), ['row_id','rss_json']]
    if len(features) != len(inputs) or features['row_id'].duplicated().any():
        raise AssertionError(f'{unit}: missing or duplicate scan row')
    if len(candidates) != 10 * len(features):
        raise AssertionError(f'{unit}: missing candidates')
    if features['row_id'].isin(inputs.row_id).sum() != len(features):
        raise AssertionError(f'{unit}: query IDs do not align with input')
    components = _components(features)
    order = features.sort_values(['SQS','row_id']).index.to_numpy()
    choices = sorted(set(order[(QUANTILE_SAMPLES*(len(order)-1)).round().astype(int)].tolist()),
                     key=lambda i: (features.at[i,'SQS'],features.at[i,'row_id']))
    percentile_lookup = {int(pos): j/max(len(order)-1,1) for j,pos in enumerate(order)}
    candidates_by_scan = {str(k):group.sort_values('candidate_rank') for k,group in candidates.groupby('row_id')}
    rss_by_scan = dict(zip(inputs.row_id.astype(str), inputs.rss_json))
    out = []
    for rank,i in enumerate(choices):
        record = features.loc[i]
        row_id = str(record.row_id)
        # Only pseudonymous AP labels are supported here; never copy a raw BSSID.
        observed = json.loads(rss_by_scan[row_id])
        if not isinstance(observed,dict) or any(not k.startswith('AP') or not k[2:].isdigit() for k in observed):
            raise AssertionError(f'{unit}: non-anonymous AP label detected')
        strongest = sorted([(k,float(v)) for k,v in observed.items()], key=lambda x:x[1],reverse=True)[:10]
        cs = candidates_by_scan[row_id]
        if list(cs.candidate_rank.astype(int)) != list(range(1,11)):
            raise AssertionError(f'{unit}: candidate ranking mismatch')
        com = {key:_finite(components.at[i,key]) for key in components.columns}
        sqs = _finite(record.SQS)
        if abs(sum(v for v in com.values() if v is not None)/len([v for v in com.values() if v is not None])-sqs) > 1e-9:
            raise AssertionError('Rounded SQS mismatch')
        out.append({
            'row_id':row_id,
            'percentile_position': _finite(percentile_lookup[int(i)]),
            'sqs':sqs,
            'c_sigma':_finite(record.C_sigma),
            'fii':_finite(record.FII),
            'true_floor':str(record.floor),
            'reference':[_finite(record.x_true),_finite(record.y_true)],
            'diagnostic_centroid':[_finite(record.diagnostic_x),_finite(record.diagnostic_y)],
            'ap_observations':len(observed),
            'strongest_ap':[[ap,_finite(value)] for ap,value in strongest],
            'components':com,
            'indicators':{key:_finite(record[key]) for key in INDICATORS},
            'candidates':[
                {'rank':int(c.candidate_rank),'x':_finite(c.candidate_x),'y':_finite(c.candidate_y),
                 'floor':str(c.candidate_floor),'rss_distance':_finite(c.normalized_rss_distance)}
                for _,c in cs.iterrows()],
        })
    bins,edges = np.histogram(features.SQS.to_numpy(dtype=float),bins=np.linspace(0,1,21))
    return {
        'unit':unit,
        'name':{'U01':'UJIIndoorLoc · Building 0','U02':'UJIIndoorLoc · Building 1',
                'U03':'UJIIndoorLoc · Building 2','U09':'HK · relative coordinates'}[unit],
        'total_query_scans':len(features),
        'training_fingerprints':int(features.n_train_scans.iloc[0]),
        'mean_sqs':_finite(features.SQS.mean()),
        'median_sqs':_finite(features.SQS.median()),
        'sqs_histogram_20_bins':bins.tolist(),
        'input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),
        'source_sha256':hashlib.sha256(features_path.read_bytes()).hexdigest(),
        'candidate_sha256':hashlib.sha256(candidates_path.read_bytes()).hexdigest(),
        'selection':'22 deterministic equally ordered SQS-quantile samples from all test scans; not representative warning labels',
        'examples':out,
    }


def export():
    records={u:_make_unit(u) for u in UNITS}
    return {
        'schema_version':'1.0',
        'data_kind':'measured_empirical_fresh_native_computation',
        'no_retrained_models':True,
        'no_calibrated_warning_labels':True,
        'sqs_rule':'Equal average of five support components; normalized within the complete evaluation unit using the existing 5th–95th percentile function.',
        'candidate_plot':'Relative local metric coordinates, not an architectural floor plan',
        'source_paths':['examples/empirical_integrity/Uxx_scan_reliability.csv.gz','examples/empirical_integrity/Uxx_retrieved_candidates.csv.gz'],
        'units':records,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check',action='store_true',help='Fail if generated data differ from committed JSON')
    args=ap.parse_args()
    output=ROOT/'docs/assets/interactive/sample_scans.json'
    encoded=json.dumps(export(),ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n'
    if args.check:
        if not output.exists() or output.read_text('utf-8')!=encoded:
            raise SystemExit('Interactive measured-data export does not match committed examples')
        print('PASS: browser samples match published scientific output files')
    else:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(encoded,encoding='utf-8')
        print(f'Exported {len(encoded)} bytes of verified public measured-data examples')

if __name__=='__main__':
    main()
