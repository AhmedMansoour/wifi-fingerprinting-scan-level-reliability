"""Prepare ignored inputs for the original numerical analysis drivers."""
import argparse, shutil
from pathlib import Path
import pandas as pd
import yaml
from sanitize_hk_data import transform
ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--combined', type=Path, help='Authorized combined table or the wholly synthetic public fixture')
    args = parser.parse_args()
    import sys
    sys.path.insert(0, str(ROOT/'scripts/research'))
    from research_paths import WORKSPACE
    for folder in ['data/processed', 'data/interim/datasets_combined_all', 'src', 'reference/A2', 'results/tables']:
        (WORKSPACE/folder).mkdir(parents=True, exist_ok=True)
    for source, name in [('estimator_predictions_approved.csv.gz', 'all_estimator_predictions_10like_units_plus_catboost.csv.gz'),
                         ('reliability_features_approved.csv.gz', 'scan_level_reliability_indicator_features.csv.gz')]:
        approved = ROOT/'reference/approved/legacy_canonical'/source
        if approved.is_file():
            shutil.copy2(approved, WORKSPACE/'data/processed'/name)
    for p in (ROOT/'scripts/research/legacy').glob('*.py'): shutil.copy2(p, WORKSPACE/'src'/p.name)
    aliases = {'d_cand': 'D_cand', 'i_k': 'I_k', 'sqs': 'SQS', 'c_sigma': 'C_sigma', 'fii': 'FII'}
    specs = yaml.safe_load((ROOT/'config/indicators.yaml').read_text())['indicators']
    rows = [dict(indicator_id=aliases.get(s['id'], s['id']), label=s['label'], family=s['group'],
                 expected_sign=1 if s['adverse_direction']=='high' else -1) for s in specs]
    pd.DataFrame(rows).to_csv(WORKSPACE/'reference/A2/A2_core_indicator_dictionary_18.csv', index=False)
    association = ROOT/'reference/approved/legacy_canonical/indicator_error_association_summary_legacy.csv'
    if association.is_file():
        shutil.copy2(association, WORKSPACE/'reference/A2/A2_indicator_error_association_summary_18.csv')
    if args.combined:
        raw = pd.read_csv(args.combined, dtype={'row_id': str}, low_memory=False)
        selected = []
        for unit in yaml.safe_load((ROOT/'config/datasets.yaml').read_text())['units']:
            block = raw[(raw.dataset==unit['dataset']) & (raw.group==unit['group'])]
            if sum(block.split=='train') != unit['expected_train'] or sum(block.split=='test') != unit['expected_test']:
                raise ValueError('Input counts do not match registry for '+unit['id'])
            public, _ = transform(block, unit_id=unit['id'])
            selected.append(public)
        pd.concat(selected).to_csv(WORKSPACE/'data/interim/datasets_combined_all/combined_all_datasets.csv', index=False)
    print('Prepared '+str(WORKSPACE)+'. Outputs remain local and ignored by Git.')

if __name__ == '__main__': main()
