"""Provide verified composite components for the read-only indicator atlas.

Only the 88 already-published illustrative scan IDs are exported. Every support
component is reconstructed with the original per-unit robust scaling and checked
against frozen native C_sigma and FII; no model is trained, no warnings inferred.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import argparse
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from wifi_integrity.reliability.sqs import robust_unit_scale  # noqa: E402


def output_payload():
    samples=json.loads((ROOT/'docs/assets/interactive/sample_scans.json').read_text())
    out={}
    for uid, meta in samples['units'].items():
        frame=pd.read_csv(ROOT/f'examples/empirical_integrity/{uid}_scan_reliability.csv.gz',dtype={'row_id':'str'}).set_index('row_id',verify_integrity=True)
        s=1-robust_unit_scale(frame['min_rss_distance'])
        spread=robust_unit_scale(frame['sigma_fps'])
        ap=robust_unit_scale(frame['ap_count'])
        overlap=robust_unit_scale(frame['ap_overlap'])
        iso=robust_unit_scale(frame['nearest_match_isolation'])
        inverse_novelty=1-robust_unit_scale(frame['ap_set_novelty'])
        reconstructed_c=s/(1+spread)
        reconstructed_f=pd.concat([s,ap,overlap,iso,inverse_novelty],axis=1).mean(axis=1,skipna=True)
        c_ref=frame['C_sigma'].astype(float)
        f_ref=frame['FII'].astype(float)
        if not np.allclose(reconstructed_c,c_ref,atol=1e-10,rtol=0,equal_nan=True):
            raise AssertionError(f'{uid}: C_sigma does not match native result')
        if not np.allclose(reconstructed_f,f_ref,atol=1e-10,rtol=0,equal_nan=True):
            raise AssertionError(f'{uid}: FII does not match native result')
        rec={}
        for row in meta['examples']:
            rid=row['row_id']
            v={'signal':s.loc[rid],'spread_risk':spread.loc[rid],
               'ap_count':ap.loc[rid],'ap_overlap':overlap.loc[rid],
               'isolation':iso.loc[rid],'inverse_novelty':inverse_novelty.loc[rid]}
            rec[rid]={k:(float(round(x,10)) if pd.notna(x) else None) for k,x in v.items()}
        out[uid]=rec
    return {'schema_version':'1.0', 'source':'native robust_unit_scale with complete public unit',
            'no_fabricated_warning_labels':True, 'units':out}


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument('--check',action='store_true')
    opts=arg.parse_args()
    path=ROOT/'docs/assets/indicator-atlas/composites.json'
    encoded=json.dumps(output_payload(),sort_keys=True,separators=(',',':'))+'\n'
    if opts.check:
        if path.read_text()!=encoded:raise SystemExit('Composites export differs from original native public outputs')
        print('PASS: 88 composite sample records reconstruct the native output')
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(encoded)
        print('Exported',len(encoded),'bytes')

if __name__=='__main__':main()
