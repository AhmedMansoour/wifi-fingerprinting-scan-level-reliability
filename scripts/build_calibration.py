"""Build a new frozen profile; never silently refit a previous profile."""
import argparse, json
from pathlib import Path
import pandas as pd
import yaml
from wifi_integrity.reliability.calibration import fit_profile, android_rows
ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['input', 'output', 'floor-id', 'estimator', 'reference-id']: p.add_argument('--'+name, required=True)
    p.add_argument('--role', choices=['calibration', 'retrospective'], required=True)
    p.add_argument('--evaluation-ids', help='CSV with scan_id; required for calibration role')
    a = p.parse_args()
    if a.role == 'calibration' and not a.evaluation_ids: p.error('Calibration requires a held-out evaluation ID list')
    out = Path(a.output)
    if any((out/name).exists() for name in ['profile.json', 'calibration.csv']): p.error('Refusing to overwrite a frozen profile')
    heldout = pd.read_csv(a.evaluation_ids).scan_id.astype(str).tolist() if a.evaluation_ids else []
    if a.role == 'calibration' and not heldout: p.error('The held-out ID list must not be empty')
    profile = fit_profile(pd.read_csv(a.input), yaml.safe_load((ROOT/'config/indicators.yaml').read_text())['indicators'],
        floor_id=a.floor_id, estimator=a.estimator, reference_id=a.reference_id, role=a.role, evaluation_scan_ids=heldout)
    out.mkdir(parents=True, exist_ok=True)
    (out/'profile.json').write_text(json.dumps(profile, indent=2, allow_nan=False)+'\n')
    pd.DataFrame(android_rows(profile)).to_csv(out/'calibration.csv', index=False)
    print('Frozen profile written. Retain profile.json with calibration.csv to preserve provenance.')

if __name__ == '__main__': main()
