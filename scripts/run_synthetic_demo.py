"""Run the shared retrieval-estimator interface on synthetic scans only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wifi_integrity.data.harmonize import dense_matrix, parse_rss_json, training_ap_vocabulary
from wifi_integrity.estimators.base import UnitData
from wifi_integrity.estimators.retrieval import RetrievalEstimator


def evaluate(frame: pd.DataFrame) -> dict:
    train = frame.loc[frame.split.eq('train')].copy()
    test = frame.loc[frame.split.eq('test')].copy()
    if len(train) < 5 or test.empty:
        raise ValueError('The demonstration needs at least five training scans and one query.')
    train_dicts = [parse_rss_json(s) for s in train.rss_json]
    test_dicts = [parse_rss_json(s) for s in test.rss_json]
    vocabulary = training_ap_vocabulary(train_dicts)
    if not vocabulary:
        raise ValueError('No observed training APs are available.')
    train_rss, train_observed = dense_matrix(train_dicts, vocabulary)
    test_rss, test_observed = dense_matrix(test_dicts, vocabulary)
    unit = UnitData(unit_id='DEMO', unit_label='Synthetic', dataset='synthetic', group='single_floor',
                    train_rss=train_rss, train_observed=train_observed,
                    test_rss=test_rss, test_observed=test_observed,
                    train_xy=train[['x', 'y']].to_numpy(float),
                    test_xy=test[['x', 'y']].to_numpy(float),
                    train_scan_id=train.row_id.to_numpy(), test_scan_id=test.row_id.to_numpy())
    summary = {'evidence': 'synthetic installation demonstration, not paper results',
               'training_scans': len(train), 'query_scans': len(test),
               'training_ap_count': len(vocabulary), 'estimators': {}}
    for eid, label, weight in [('knn', 'KNN', None), ('wknn', 'WKNN', 1.0)]:
        run = RetrievalEstimator(estimator_id=eid, estimator_label=label, k=5,
                                 metric='euclidean', weight_power=weight).fit_predict(unit)
        errors = run.predictions.error_2d.to_numpy()
        summary['estimators'][label] = {'rows': len(errors),
                                        'median_error_m': float(np.median(errors)),
                                        'p90_error_m': float(np.percentile(errors, 90))}
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'results/demo/synthetic_scans.csv')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/demo/demo_results.json')
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error('Generate the input first with: python scripts/reproduce_release.py --mode demo')
    summary = evaluate(pd.read_csv(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
