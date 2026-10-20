"""Create a publicly distributable, ENTIRELY SYNTHETIC combined Wi-Fi input.

No source RSS, identifiers, locations, observations, or real floor-map shapes
are read. The 10 unit slots, per-unit train/test counts and the column schema
come from the manuscript implementation's dataset registry. Synthetic
coordinates, AP coordinates and measured signals are generated from a fixed
random seed; no site-origin or AP mappings exist.

NOT manuscript empirical data. Use for testing code and I/O only.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
import numpy as np

SCHEMA = ['dataset','group','split','row_id','floor','x','y','rss_json']
SEED = 20261021
# Registry-based unit labels and counts (not per-scan empirical data).
REGISTRY = [
 ('U01','UJIndoorLoc','Building0',4628,1157),
 ('U02','UJIndoorLoc','Building1',4402,1101),
 ('U03','UJIndoorLoc','Building2',7808,1952),
 ('U04','TUT_WLAN_RSS_1161525','TUT',1142,286),
 ('U05','TAU_ADDITIONAL_3819917','Database_Building01',8309,2076),
 ('U06','TAU_ADDITIONAL_3819917','Database_Building02',7433,1858),
 ('U07','TAMPERE_MULTIBUILDING_5174851','SAH1',7558,1889),
 ('U08','TAMPERE_MULTIBUILDING_5174851','TIE1',8547,2136),
 ('U09','BlockZ-10W-1719W','BlockZPolyU',3319,831),
 ('U10','DSI_3778646','single_area',1374,343),
]
# Chosen independently of REAL buildings. U09 intentionally has three
# fabricated categorical floors, NOT the real HK floor count or geometry.
SYNTH_FLOORS = [3,2,4,2,3,4,2,3,3,1]
MAC_LITERAL = re.compile(rb'(?<![\w:])(?:[A-Fa-f0-9]{2}[:-]){5}[A-Fa-f0-9]{2}(?![\w:])')


def unit_bytes(slot: int, uid: str, dataset: str, group: str, ntrain: int, ntest: int):
    rng = np.random.default_rng(SEED + (slot + 1)*104729)
    nfloors = SYNTH_FLOORS[slot]
    # Artificial AP placement inside simple abstract rectangles; no real geometry.
    # Each floor has local beacons; a few APs are cross-floor.
    ap_floor = np.repeat(np.arange(nfloors), 25)
    ap_x = rng.uniform(2.0, 40.0, size=len(ap_floor))
    ap_y = rng.uniform(2.0, 27.0, size=len(ap_floor))
    ap_ids = [f'AP_{i+1:05d}' for i in range(len(ap_floor))]
    stringbuf = io.StringIO(newline='')
    writer = csv.writer(stringbuf, lineterminator='\n')
    writer.writerow(SCHEMA)
    samples_per_floor = [0]*nfloors
    for split, n in [('train',ntrain),('test',ntest)]:
        for k in range(n):
            floor = int(rng.integers(0,nfloors))
            x = float(rng.uniform(0,42));y=float(rng.uniform(0,29))
            d = np.sqrt((ap_x-x)**2+(ap_y-y)**2+2.0**2)
            # Path-loss-style illustration, not a calibrated real-world channel.
            rss = -36 - 28*np.log10(d) - 24*np.abs(ap_floor-floor)
            rss = rss + rng.normal(0,3.0,size=len(rss))
            observed = np.flatnonzero(rss >= -88)
            if len(observed) < 5:
                observed = np.argsort(rss)[-5:]
            if len(observed) > 22:
                observed = observed[np.argpartition(rss[observed],-22)[-22:]]
            # Sort by synthetic AP index for deterministic JSON encoding.
            payload = {ap_ids[int(j)]:int(np.clip(np.rint(rss[j]),-101,-25)) for j in sorted(observed)}
            rowid = f'SYN_{uid}_{split}_{k:06d}'
            writer.writerow([dataset,group,split,rowid,floor,round(x,4),round(y,4),json.dumps(payload,separators=(',',':'))])
            samples_per_floor[floor] += 1
    raw = stringbuf.getvalue().encode('utf8')
    return raw, dict(unit_id=uid, train_scans=ntrain, test_scans=ntest,
                     simulated_floors=nfloors, theoretical_aps=len(ap_floor),
                     scan_counts_by_simulated_floor=samples_per_floor,
                     sha256=hashlib.sha256(raw).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    all_units=[]; report=[]
    for i,(uid,dataset,group,train,test) in enumerate(REGISTRY):
        raw,detail=unit_bytes(i,uid,dataset,group,train,test)
        all_units.append((uid,raw)); report.append(detail)
    head = (','.join(SCHEMA)+'\n').encode()
    combined = head + b''.join(raw[len(head):] for _,raw in all_units)
    assert combined.count(b'\n')==68150
    assert MAC_LITERAL.search(combined) is None
    assert b'836546.28' not in combined and b'818615.62' not in combined
    assert len(REGISTRY)==10
    assert sum(r['train_scans'] for r in report)==54520
    assert sum(r['test_scans'] for r in report)==13629
    meta = {
      'release_classification':'PUBLIC_SYNTHETIC_SOFTWARE_DEMO',
      'scientific_scope':'Synthetic end-to-end input for software tests only, not empirical ESWA findings',
      'generated_from_empirical_scan_data':False,
      'generated_from_real_AP_or_floor_coordinates':False,
      'dataset_and_group_columns':'Registry slot identifiers only; samples are NOT records from these real datasets',
      'seed':SEED,'train_scans':54520,'test_scans':13629,'scans':68149,
      'units':report,'schema':SCHEMA,'combined_sha256':hashlib.sha256(combined).hexdigest(),
      'license_note':'Generated algorithmically; the paper authors should approve the release notice before publishing.'
    }
    readme = '''# PUBLIC SYNTHETIC combined Wi-Fi data for software demonstrations

## Critical distinction
All 68,149 individual scans, relative 2D positions, RSS readings, AP placements,
and all map-like geometry are **fabricated from a random seed**. These are NOT
measurements from the ESWA study or from the named benchmark datasets. Dataset
and group names are registry slot labels used only for compatibility with the
repository; they DO NOT imply original dataset content is reproduced.

This file is suitable as a PUBLIC **synthetic software-test fixture**. It
CANNOT independently reproduce the paper's empirical accuracy, SQS calibration,
gross-error results, or per-environment conclusions. Do not label it as
"anonymized empirical data" or "processed study data". To reproduce reported
study reference statistics use the separately supplied approved scalar records,
subject to their own permissions.

## Files
- `processing_inputs/combined_all_datasets.csv` is the drop-in eight-column
  table for `scripts/prepare_research_workspace.py --combined ...`.
- `processing_inputs/units/U01.csv.gz` through `U10.csv.gz` are the unit slices.
- `processing_inputs/validation_summary.json` records sizes and SHA-256 hashes.
- `scripts/create_public_synthetic_combined.py` generates all 10 units afresh.

## Data schema
`dataset,group,split,row_id,floor,x,y,rss_json`

Coordinates are fabricated metre-scale local Cartesian positions with no
geodetic origin, genuine reference-point locations, or real floor geometry.
`floor` is a fabricated categorical level, not a true storey label. RSS
observations use fabricated AP keys in the `AP_00001` format, *not HK BSSIDs*.
No real scan rows, raw radio-map signatures, or reversible mappings were used.

## Reproduction
```bash
python scripts/create_public_synthetic_combined.py --output new_public_fixture.zip
unzip new_public_fixture.zip
python scripts/prepare_research_workspace.py \\
  --combined processing_inputs/combined_all_datasets.csv
```

The generator is deterministic given its code, seed, and numpy version. A SHA-256
of its committed output is recorded in the included validation summary. The
repository's analysis results are **not** expected to match the original paper
when this fixture is substituted for actual study data.

## Source and permissions
The published release excludes all actual HK indoor geometry, floor-plan
images, vector shapes, Wi-Fi identifiers, and empirically observed positions.
The separately stored 10-unit input ZIP contains real derived data and is
PRIVATE. Redistributing third-party empirical datasets requires dataset-specific
license verification even after IDs and coordinates are transformed.
'''
    # Include only text/CSV and gzip; do not include any actual radio-map geometry.
    with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as out:
        def add(name, data):
            # Fixed ZIP timestamps enable reproducible distribution across environments.
            info=zipfile.ZipInfo(name,date_time=(2026,10,21,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(0o644 << 16)
            out.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=7)
        add('README_PUBLIC_SYNTHETIC.md',readme.encode())
        add('processing_inputs/combined_all_datasets.csv',combined)
        add('processing_inputs/validation_summary.json', (json.dumps(meta,indent=2)+'\n').encode())
        for uid,raw in all_units:
            add(f'processing_inputs/units/{uid}.csv.gz',gzip.compress(raw,mtime=0,compresslevel=7))
        add('scripts/create_public_synthetic_combined.py',Path(__file__).read_bytes())
    with zipfile.ZipFile(a.output) as z:
        assert z.testzip() is None
        assert hashlib.sha256(z.read('processing_inputs/combined_all_datasets.csv')).hexdigest()==meta['combined_sha256']
    print(json.dumps({'archive':str(a.output),'compressed_bytes':a.output.stat().st_size,'combined_uncompressed_bytes':len(combined),
        'zip_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'combined_sha256':meta['combined_sha256'],
        'rows':68149,'train':54520,'test':13629,'units':10},indent=2))

if __name__=='__main__': main()
