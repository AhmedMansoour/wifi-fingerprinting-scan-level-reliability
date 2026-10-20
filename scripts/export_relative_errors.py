"""Convert authorized *local metric* predictions/GT into relative 2D error vectors.

Outputs no GT coordinates, predicted positions, floor geometry, BSSIDs, or radio maps.
The coordinates supplied by the author must already be in one consistent local
metric frame (metres) per evaluation unit. Do not feed longitude/latitude degrees.

Usage (with a private, locally held input; NEVER commit that input):
 python scripts/export_relative_errors.py --input /private/study_positions.csv \
   --output outputs/private_relative_errors.csv

Expected input columns: unit_id,scan_id,estimator,pred_x_m,pred_y_m,gt_x_m,gt_y_m
Output: unit_id,scan_id,estimator,dx_error_m,dy_error_m,error_2d_m

The two differences are invariant to any common coordinate translation, i.e.
(p - origin) - (GT - origin) == p - GT. This alone is not permission to share
HK-derived records; seek dataset-derivative authorization before publication.
"""
from __future__ import annotations
import argparse
import csv
import math
from pathlib import Path

REQUIRED={'unit_id','scan_id','estimator','pred_x_m','pred_y_m','gt_x_m','gt_y_m'}
OUTPUT=['unit_id','scan_id','estimator','dx_error_m','dy_error_m','error_2d_m']


def convert(input_csv:Path, output_csv:Path)->int:
    if input_csv.resolve()==output_csv.resolve():
        raise ValueError('Input and output must be different; never overwrite raw study coordinates')
    with input_csv.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError('Expected local-metric prediction and ground-truth coordinate columns')
        if any(x in {s.lower() for s in reader.fieldnames} for x in
               ('latitude','longitude','lat','lon','lng','easting','northing','epsg','crs')):
            raise ValueError('Georeferenced coordinate columns must not be supplied')
        rows=[]
        for r in reader:
            try:
                x,y,xgt,ygt=(float(r[k]) for k in ('pred_x_m','pred_y_m','gt_x_m','gt_y_m'))
                if not all(map(math.isfinite,(x,y,xgt,ygt))):raise ValueError('non-finite coordinates')
                dx,dy=x-xgt,y-ygt
                rows.append(dict(unit_id=r['unit_id'],scan_id=r['scan_id'],estimator=r['estimator'],
                                 dx_error_m=f'{dx:.12g}',dy_error_m=f'{dy:.12g}',
                                 error_2d_m=f'{math.hypot(dx,dy):.12g}'))
            except (TypeError,ValueError) as e:
                raise ValueError(f'Invalid metric coordinate on CSV line {reader.line_num}: {e}') from e
    output_csv.parent.mkdir(parents=True,exist_ok=True)
    with output_csv.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=OUTPUT)
        writer.writeheader();writer.writerows(rows)
    return len(rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True,help='Private local-metric position CSV')
    p.add_argument('--output',type=Path,default=Path('outputs/private_relative_errors.csv'))
    a=p.parse_args()
    print(f'Created {convert(a.input,a.output)} relative error records at {a.output} (not cleared for redistribution)')
