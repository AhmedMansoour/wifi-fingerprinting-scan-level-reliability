"""Split-isolated illustrative adverse-percentile warning states.

Input CSV must have 'unit_id','scan_id' plus named indicator columns.
This does not rebuild the original retrospective reference-distribution experiment.
"""
from __future__ import annotations
import argparse,bisect,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]

def generate(calibration:Path,evaluation:Path,output:Path,cutoff:float=0.80):
    if calibration.resolve()==evaluation.resolve():raise ValueError('Identical calibration and evaluation files are forbidden')
    cal=pd.read_csv(calibration);test=pd.read_csv(evaluation)
    ids=['unit_id','scan_id']
    for d in (cal,test):
        if any(c not in d for c in ids):raise ValueError('Split input requires unit_id and scan_id')
        if d.duplicated(ids).any():raise ValueError('Duplicated scan identifiers')
    if set(zip(cal.unit_id,cal.scan_id))&set(zip(test.unit_id,test.scan_id)):
        raise ValueError('Calibration/evaluation leakage: overlapping scan identifiers')
    config=yaml.safe_load((ROOT/'config/indicators.yaml').read_text())
    defs=[x for x in config['indicators'] if x['id']!='nearest_rp_distance']
    dirs={x['id']:x['adverse_direction'] for x in defs}
    aliases={'sqs':'SQS','c_sigma':'C_sigma','fii':'FII','d_cand':'D_cand','i_k':'I_k'}
    out=[]; used=[]
    for (unit,),testpart in test.groupby(['unit_id']):
        calpart=cal[cal.unit_id==unit]
        if calpart.empty:raise ValueError(f'No calibration for {unit}')
        for code,side in dirs.items():
            col=aliases.get(code,code)
            if col not in cal or col not in test:continue
            ref=sorted(calpart[col].dropna().astype(float).tolist())
            if not ref:raise ValueError(f'Empty calibration {unit}/{code}')
            used.append((unit,code,len(ref)))
            for record in testpart.itertuples(index=False):
                value=float(getattr(record,col))
                if not np.isfinite(value):continue
                if side=='high':adverse=bisect.bisect_right(ref,value)/len(ref)
                elif side=='low':adverse=(len(ref)-bisect.bisect_left(ref,value))/len(ref)
                else:raise ValueError(f'Unexpected adverse direction {side}')
                out.append(dict(unit_id=unit,scan_id=record.scan_id,indicator_id=code,
                                adverse_percentile=adverse,warning=int(adverse>=cutoff)))
    output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(out).to_csv(output/'warning_states.csv',index=False)
    (output/'calibration_provenance.json').write_text(json.dumps({
       'calibration_sha256':hashlib.sha256(calibration.read_bytes()).hexdigest(),
       'evaluation_sha256':hashlib.sha256(evaluation.read_bytes()).hexdigest(),
       'overlap_count':0,'cutoff':cutoff,'reference_populations':used,
       'status':'prospective-style demonstrator; not the retrospective paper calibration'},indent=2)+'\n')
    return len(out)

if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--calibration',type=Path,required=True);q.add_argument('--evaluation',type=Path,required=True)
    q.add_argument('--output',type=Path,default=ROOT/'outputs'/'warnings');a=q.parse_args()
    print('warning records',generate(a.calibration,a.evaluation,a.output))
