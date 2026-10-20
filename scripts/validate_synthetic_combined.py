"""Validate a generated-only 10-unit test fixture; no empirical Wi-Fi records."""
import gzip
import hashlib
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'examples/synthetic_combined'
COLUMNS = ['dataset','group','split','row_id','floor','x','y','rss_json']
AP = re.compile(r'AP_\d{5}\Z')
MAC = re.compile(r'(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])')

def validate() -> dict:
    summary = json.loads((DATA/'validation_summary.json').read_text())
    src = DATA/'combined_all_datasets.csv.gz'
    with gzip.open(src,'rb') as f:
        sha = hashlib.sha256()
        while b:=f.read(1024*1024): sha.update(b)
    assert sha.hexdigest() == summary['combined_sha256'], 'Combined file hash mismatch'
    df = pd.read_csv(src,dtype={'row_id':'string'},low_memory=False)
    assert list(df) == COLUMNS
    assert len(df) == 68149
    assert df.split.value_counts().to_dict() == {'train':54520,'test':13629}
    assert df.row_id.is_unique and df.row_id.str.match(r'SYN_U\d{2}_(?:train|test)_\d{6}\Z').all()
    assert np.isfinite(df[['x','y']]).all().all()
    assert df.x.between(0,42).all() and df.y.between(0,29).all()
    assert df.floor.between(0,4).all()
    assert not any(MAC.search(s) for s in df.rss_json)
    for uid in [f'U{i:02d}' for i in range(1,11)]:
        records=df[df.row_id.str.startswith('SYN_'+uid+'_')]
        expected=next(x for x in summary['units'] if x['unit_id']==uid)
        assert len(records)==expected['train_scans']+expected['test_scans']
        assert (records.split=='train').sum()==expected['train_scans']
        assert (records.split=='test').sum()==expected['test_scans']
        p=DATA/'units'/f'{uid}.csv.gz'
        with gzip.open(p,'rb') as f:unit_bytes=f.read()
        assert hashlib.sha256(unit_bytes).hexdigest()==expected['sha256'],uid+' unit bytes hash mismatch'
        for raw in records.rss_json:
            d=json.loads(raw)
            assert d and all(AP.fullmatch(k) and isinstance(v,(int,float)) and -110<=v<=-20 for k,v in d.items())
    return {'result':'passed','fixture_kind':'wholly_generated_synthetic','rows':len(df),
            'training':int((df.split=='train').sum()),'test':int((df.split=='test').sum()),
            'units':10,'combined_csv_sha256':sha.hexdigest()}

if __name__=='__main__': print(json.dumps(validate(),indent=2))
