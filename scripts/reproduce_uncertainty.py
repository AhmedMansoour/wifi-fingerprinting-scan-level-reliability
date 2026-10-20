"""Recompute A3 intervals with 10,000 unit-cluster bootstrap replicates."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from wifi_integrity.reliability.uncertainty import cluster_boot_ci
ROOT = Path(__file__).resolve().parents[1]
BASE_SEED = 20260725

def main():
    association = pd.read_csv(ROOT/'results/tables/reliability_association_by_condition.csv')
    gross = pd.read_csv(ROOT/'results/tables/gross_error_discrimination_by_condition.csv')
    reference = ROOT/'reference/approved/revision_summaries/A3'
    tasks = [(association, pd.read_csv(reference/'A3_indicator_error_association_summary_ci_bh.csv'),
              'association', [('aligned_spearman_rho', 'aligned_rho')])]
    for strategy, name in [('adaptive_iqr', 'adaptive'), ('fixed_7m', 'fixed7m')]:
        tasks.append((gross[gross.strategy == strategy], pd.read_csv(reference/f'A3_gross_error_{name}_summary_ci.csv'),
                      strategy, [(v, v) for v in ['auroc', 'auprc', 'auprc_lift']]))
    rows = []
    for frame, expected, strategy, metrics in tasks:
        for record in expected.to_dict('records'):
            iid = record['indicator_id']
            for column, suffix in metrics:
                if strategy == 'association': seed = BASE_SEED + sum(map(ord, iid))
                else:
                    prefix = 'adp' if strategy == 'adaptive_iqr' else 'fix'
                    offset, letter = {'auroc': (400, 'a'), 'auprc': (500, 'p'), 'auprc_lift': (600, 'l')}[column]
                    seed = BASE_SEED + offset + sum(map(ord, prefix+iid+letter))
                point, lo, hi = cluster_boot_ci(frame[frame.indicator_id == iid], column, b=10000, seed=seed)
                difference = max(abs(lo-record['ci95_low_'+suffix]), abs(hi-record['ci95_high_'+suffix]))
                rows.append(dict(strategy=strategy, indicator_id=iid, metric=column, point=point,
                                 ci95_low=lo, ci95_high=hi, seed=seed, max_abs_difference=difference))
    result = pd.DataFrame(rows)
    result.to_csv(ROOT/'results/tables/uncertainty_regression.csv', index=False)
    maximum = float(result.max_abs_difference.max())
    passed = bool(np.isfinite(result.max_abs_difference).all() and maximum < 1e-9)
    report = dict(status='passed' if passed else 'failed', intervals=len(result), replicates=10000,
                  resampling_unit='dataset unit, retaining all associated estimator conditions',
                  base_seed=BASE_SEED, seed_schedule='Original A3 indicator/metric-dependent schedule',
                  max_abs_difference=maximum)
    (ROOT/'results/logs/uncertainty_regression.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    if not passed: raise SystemExit('Bootstrap interval regression failed')

if __name__ == '__main__': main()
