"""Validate modified UJIIndoorLoc U01-U03 RSS inputs (UCI CC BY 4.0)."""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SPECS = {'U01':(4628,1157), 'U02':(4402,1101), 'U03':(7808,1952)}
FIELDS = ['dataset','group','split','row_id','floor','x','y','rss_json']
AP = re.compile(r'AP[1-9][0-9]*\Z')
MAC = re.compile(r'(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])')

def validate(root=ROOT):
    root=Path(root)
    stats={}
    for uid,(train,test) in SPECS.items():
        file=root/'data/empirical'/f'{uid}.csv.gz'
        raw=file.read_bytes()
        assert raw[:2]==b'\x1f\x8b'
        assert MAC.search(raw.decode('latin1')) is None
        with gzip.open(file,'rt',encoding='utf8',newline='') as stream:
            reader=csv.DictReader(stream)
            assert reader.fieldnames==FIELDS
            rows=list(reader)
        counts={'train':0,'test':0}
        seen=set()
        for row in rows:
            assert row['dataset']=='UJIndoorLoc'
            assert row['split'] in counts
            counts[row['split']]+=1
            assert row['row_id'] not in seen
            seen.add(row['row_id'])
            assert row['x'] and row['y']
            keys=json.loads(row['rss_json'])
            assert all(AP.fullmatch(k) for k in keys)
            assert MAC.search(json.dumps(row)) is None
        assert counts=={'train':train,'test':test},(uid,counts)
        stats[uid]={'train':train,'test':test,'sha256':hashlib.sha256(raw).hexdigest()}
    return stats

if __name__=='__main__':
    print(json.dumps(validate(),indent=2))
