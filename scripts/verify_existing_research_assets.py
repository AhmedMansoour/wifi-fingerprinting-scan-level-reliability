"""Validate original ESWA HK U09 research assets after origin-free relabeling.

The original eight-estimator predictions and reliability outputs are not recomputed;
this verifies that the approved saved results remain numerically coherent after
removal of site coordinate origins and original scan identifiers.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'metadata' / 'existing_research_asset_manifest.json'

def read_gzip(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))

def verify():
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    for row in manifest['files']:
        p=ROOT/row['path']
        assert p.is_file(), f'missing {p}'
        raw=p.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==row['sha256'], row['path']
        assert len(raw)==row['bytes'], row['path']
    radio=read_gzip(ROOT/'data/radio_maps/hk_u09_train.csv.gz')
    query=read_gzip(ROOT/'data/empirical/hk_u09_test_ordered.csv.gz')
    assert len(radio)==3319 and len(query)==831
    assert all(x['split']=='train' for x in radio)
    assert all(x['split']=='test' for x in query)
    for rows in (radio,query):
        for row in rows:
            ap=json.loads(row['rss_json'])
            assert all(re.fullmatch(r'AP[1-9][0-9]*',k) for k in ap)
            assert math.isfinite(float(row['x'])) and math.isfinite(float(row['y']))
    approved={
        'historical_estimator_predictions.csv.gz':6648,
        'historical_scan_reliability.csv.gz':831,
        'historical_reliability_decisions.csv.gz':6648,
    }
    total=0;max_error_gap=0.0;max_true_xy_discrepancy=0.0
    for name,n in approved.items():
        rows=read_gzip(ROOT/'results/empirical/hk_u09'/name)
        assert len(rows)==n,(name,len(rows))
        counts=Counter(r['row_id'] for r in rows)
        assert set(counts)=={f'U09-test-{i:06d}' for i in range(831)}
        assert set(counts.values())==({1} if n==831 else {8})
        for row in rows:
            assert row['dataset']=='HK_U09' and row['group']=='HK_LOCAL'
            i=int(row['row_id'].rsplit('-',1)[1]);test=query[i]
            xy_discrepancy=max(abs(float(row['x_true'])-float(test['x'])),abs(float(row['y_true'])-float(test['y'])))
            max_true_xy_discrepancy=max(max_true_xy_discrepancy,xy_discrepancy)
            assert xy_discrepancy<=0.031,'Original method-dependent rounding exceeded expected 0.03 m'
            if all(k in row for k in ('x_pred','y_pred','error_m')):
                error=math.hypot(float(row['x_true'])-float(row['x_pred']),float(row['y_true'])-float(row['y_pred']))
                delta=abs(error-float(row['error_m']))
                assert delta<0.00001,'Error is not invariant under coordinate translation'
                max_error_gap=max(max_error_gap,delta)
            assert not re.search(r'(?i)(?<![a-f0-9])(?:[a-f0-9]{2}[:-]){5}[a-f0-9]{2}(?![a-f0-9])',str(row))
        total+=n
    return {'status':'passed','train_radio_map_scans':3319,'test_scans':831,
            'historical_estimator_predictions':6648,'historical_indicator_rows':831,
            'historical_decision_rows':6648,'max_error_roundtrip_gap_m':max_error_gap,
            'max_historical_vs_input_reference_position_difference_m':max_true_xy_discrepancy,
            'approved_aggregates':len([x for x in manifest['files'] if x['path'].startswith('results/approved/')])}
if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
