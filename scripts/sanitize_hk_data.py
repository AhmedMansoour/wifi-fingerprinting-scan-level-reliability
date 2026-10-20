"""Export a relative-coordinate, opaque-AP view; keep inverse mappings private."""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
PUBLIC_COLUMNS = ['dataset', 'group', 'split', 'row_id', 'floor', 'x', 'y', 'rss_json']


def transform(frame, unit_id='U09'):
    if not set(PUBLIC_COLUMNS).issubset(frame):
        raise ValueError('Missing required input columns')
    if len(frame[['dataset', 'group']].drop_duplicates()) != 1:
        raise ValueError('Transform one unit at a time')
    if frame.row_id.duplicated().any() or frame.row_id.isna().any():
        raise ValueError('Unique nonmissing row IDs are required')
    if not set(frame.split).issubset({'train', 'test'}) or not (frame.split == 'train').any():
        raise ValueError('Require training rows and train/test split labels')
    if not np.isfinite(frame[['x', 'y']].to_numpy(float)).all():
        raise ValueError('Coordinates must be finite')
    origin = frame.loc[frame.split == 'train', ['x', 'y']].min().to_numpy(float)
    dictionaries = [json.loads(v) for v in frame.rss_json]
    aps = {ap: f'AP_{i:05d}' for i, ap in enumerate(sorted({k for d in dictionaries for k in d}), 1)}
    floors = {str(k): i for i, k in enumerate(sorted(frame.floor.dropna().unique()))}
    ids = {old: f'{unit_id}-{split}-{i:06d}' for i, (old, split) in enumerate(zip(frame.row_id, frame.split))}
    result = frame[PUBLIC_COLUMNS].copy()
    result['row_id'] = frame.row_id.map(ids)
    result['floor'] = [floors.get(str(v), 0) for v in frame.floor]
    result[['x', 'y']] = frame[['x', 'y']].to_numpy(float) - origin
    result['rss_json'] = [json.dumps({aps[k]: v for k, v in d.items()}, separators=(',', ':'), allow_nan=False) for d in dictionaries]
    return result, {'origin': origin.tolist(), 'ap_mapping': aps, 'row_ids': ids, 'floors': floors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--private-mapping', type=Path, required=True)
    args = parser.parse_args()
    if args.private_mapping.resolve().is_relative_to(ROOT):
        parser.error('The private inverse mapping must be outside the repository')
    if args.output.exists() or args.private_mapping.exists():
        parser.error('Refusing to overwrite existing exports')
    frame = pd.read_csv(args.input, dtype={'row_id': str}, low_memory=False)
    frame = frame[(frame.dataset == 'BlockZ-10W-1719W') & (frame.group == 'BlockZPolyU')]
    public, mapping = transform(frame)
    args.private_mapping.parent.mkdir(parents=True, exist_ok=True)
    # Create private mapping with owner-only permissions from the first write.
    import os
    fd = os.open(args.private_mapping, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as out: json.dump(mapping, out)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    public.to_csv(args.output, index=False, compression='infer')
    print(f'Exported {len(public)} rows with relative metre coordinates and opaque AP tokens.')


if __name__ == '__main__': main()
