"""Convert publisher Wi-Fi RSS matrices into the eight-column local unit schema.

The caller must specify the matching source radio-map, query and coordinate files.
No historical ESWA split membership is reconstructed or assumed by this adapter.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ['dataset','group','split','row_id','floor','x','y','rss_json']


def load_csv(path: Path, *, has_header: bool = True) -> pd.DataFrame:
    return pd.read_csv(path, header=0 if has_header else None, low_memory=False)


def valid_rss(v) -> float | None:
    try:
        value=float(v)
    except (TypeError, ValueError):
        return None
    # Original non-detection sentinels +100, blank, NaN do not represent RSS.
    if np.isfinite(value) and -160 <= value <= 0:
        return value
    return None


def registry(uid: str, root: Path = ROOT) -> dict:
    units=yaml.safe_load((root/'config/datasets.yaml').read_text(encoding='utf8'))['units']
    by_id={u['id']:u for u in units}
    if uid not in by_id:
        raise ValueError(f'Unknown unit {uid}')
    return by_id[uid]


def _paired(rss_path: Path, coords_path: Path, *, rss_header: bool, coords_header: bool,
            x_index: int, y_index: int, floor_index: int) -> tuple[pd.DataFrame,pd.DataFrame]:
    rss=load_csv(rss_path,has_header=rss_header)
    coords=load_csv(coords_path,has_header=coords_header)
    if len(rss)!=len(coords):
        raise ValueError('RSS/coordinate file row counts differ; their source row order must match')
    if x_index<0 or y_index<0 or max(x_index,y_index)>=coords.shape[1]:
        raise ValueError('Invalid x/y column indices')
    if floor_index>=coords.shape[1]:
        raise ValueError('Invalid floor column index')
    out=pd.DataFrame({'x':pd.to_numeric(coords.iloc[:,x_index],errors='raise'),
                      'y':pd.to_numeric(coords.iloc[:,y_index],errors='raise'),
                      'floor':pd.to_numeric(coords.iloc[:,floor_index],errors='raise') if floor_index>=0 else -1})
    return rss,out


def _wide(path: Path, *, x_column: str, y_column: str, floor_column: str,
          ap_prefix: str, building_column: str | None, building_value: str | None):
    df=load_csv(path)
    if building_column:
        if building_column not in df.columns:
            raise ValueError('No selected building column')
        df=df.loc[df[building_column].astype(str)==str(building_value)].copy()
    if not all(c in df.columns for c in (x_column,y_column)):
        raise ValueError('Missing coordinate columns in wide source')
    coords=pd.DataFrame({'x':pd.to_numeric(df[x_column],errors='raise'),
                         'y':pd.to_numeric(df[y_column],errors='raise'),
                         'floor':pd.to_numeric(df[floor_column],errors='raise') if floor_column in df.columns else -1})
    aps=[col for col in df.columns if str(col).upper().startswith(ap_prefix.upper())]
    if not aps:
        raise ValueError('No RSS columns matching --ap-prefix')
    return df.loc[:,aps].reset_index(drop=True),coords.reset_index(drop=True)


def export(uid: str, mode: str, output_dir: Path, *, train: Path | None = None, test: Path | None = None,
           train_rss: Path | None = None, train_coords: Path | None = None,
           test_rss: Path | None = None, test_coords: Path | None = None,
           x_column: str = 'x', y_column: str = 'y', floor_column: str = 'floor',
           building_column: str | None = None, building_value: str | None = None,
           ap_prefix: str = 'AP', rss_header: bool = True, coords_header: bool = True,
           x_index: int = 0, y_index: int = 1, floor_index: int = -1, root: Path = ROOT):
    spec=registry(uid,root=root)
    if mode=='wide':
        if not train or not test:
            raise ValueError('--train and --test are required for wide mode')
        both=[_wide(p,x_column=x_column,y_column=y_column,floor_column=floor_column,
                    ap_prefix=ap_prefix,building_column=building_column,building_value=building_value)
              for p in (train,test)]
    elif mode=='paired':
        if not all((train_rss,train_coords,test_rss,test_coords)):
            raise ValueError('All four --train/--test-rss/coords inputs required')
        both=[_paired(r,c,rss_header=rss_header,coords_header=coords_header,
                      x_index=x_index,y_index=y_index,floor_index=floor_index)
              for r,c in ((train_rss,train_coords),(test_rss,test_coords))]
    else:
        raise ValueError('Unknown mode')
    if not len(both[0][0]) or not len(both[1][0]):
        raise ValueError('Both train and test must contain samples')
    if not both[0][0].columns.is_unique or not both[1][0].columns.is_unique:
        raise ValueError('Repeated AP columns')
    # Pair RSS column identities consistently across train and test, instead of
    # renumbering each file independently. Positional fallback for paired CSVs.
    if mode=='paired':
        if both[0][0].shape[1]!=both[1][0].shape[1]:
            raise ValueError('Train and test RSS column counts differ')
        source_keys=list(range(both[0][0].shape[1]))
    else:
        source_keys=sorted(set(both[0][0].columns)|set(both[1][0].columns))
    vocab={key:f'AP{i}' for i,key in enumerate(source_keys,1)}
    x0=float(both[0][1]['x'].min());y0=float(both[0][1]['y'].min())
    frames=[]
    for split,(rss,xy) in zip(('train','test'),both):
        if not len(rss)==len(xy):
            raise ValueError('RSS/coordinates misaligned')
        if not np.isfinite(xy[['x','y']].to_numpy(dtype=float)).all():
            raise ValueError('Nonfinite coordinates')
        if not (np.isfinite(xy['floor'].to_numpy(dtype=float)).all() and
                (xy['floor'].to_numpy(dtype=float)%1==0).all()):
            raise ValueError('Floor must be an integer category, not physical height')
        rows=[]
        for j in range(len(rss)):
            row=rss.iloc[j]
            keys=range(len(row)) if mode=='paired' else rss.columns
            obs={vocab[k]:v for k,k0 in zip(keys,range(len(row)))
                 if (v:=valid_rss(row.iloc[k0])) is not None}
            rows.append({'dataset':spec['dataset'],'group':spec['group'],
                         'split':split,'row_id':f'{uid}-{split}-{j:06d}',
                         'floor':int(xy.iloc[j]['floor']),
                         'x':round(float(xy.iloc[j]['x'])-x0,8),
                         'y':round(float(xy.iloc[j]['y'])-y0,8),
                         'rss_json':json.dumps(obs,sort_keys=True,separators=(',',':'))})
        frames.extend(rows)
    output_dir.mkdir(parents=True,exist_ok=True)
    path=output_dir/f'{uid}.csv.gz'
    pd.DataFrame(frames,columns=COLUMNS).to_csv(path,index=False,compression='gzip')
    return {'unit':uid,'path':str(path),'train':len(both[0][0]),'test':len(both[1][0]),
            'aps':len(vocab),'note':'source split retained; not presumed identical to historical ESWA split'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--unit',required=True)
    p.add_argument('--mode',required=True,choices=['paired','wide'])
    p.add_argument('--train',type=Path);p.add_argument('--test',type=Path)
    p.add_argument('--train-rss',type=Path);p.add_argument('--train-coords',type=Path)
    p.add_argument('--test-rss',type=Path);p.add_argument('--test-coords',type=Path)
    p.add_argument('--x-column',default='x');p.add_argument('--y-column',default='y')
    p.add_argument('--floor-column',default='floor');p.add_argument('--ap-prefix',default='AP')
    p.add_argument('--building-column');p.add_argument('--building-value')
    p.add_argument('--x-index',type=int,default=0);p.add_argument('--y-index',type=int,default=1)
    p.add_argument('--floor-index',type=int,default=-1)
    p.add_argument('--no-rss-header',action='store_true');p.add_argument('--no-coords-header',action='store_true')
    p.add_argument('--output-dir',type=Path,default=Path('LOCAL_MEASURED_UNITS'))
    args=p.parse_args()
    print(json.dumps(export(args.unit,args.mode,args.output_dir,train=args.train,test=args.test,
        train_rss=args.train_rss,train_coords=args.train_coords,test_rss=args.test_rss,
        test_coords=args.test_coords,x_column=args.x_column,y_column=args.y_column,
        floor_column=args.floor_column,building_column=args.building_column,
        building_value=args.building_value,ap_prefix=args.ap_prefix,
        rss_header=not args.no_rss_header,coords_header=not args.no_coords_header,
        x_index=args.x_index,y_index=args.y_index,floor_index=args.floor_index),indent=2))

if __name__=='__main__':
    main()
