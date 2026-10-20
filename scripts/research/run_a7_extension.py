from __future__ import annotations
from research_paths import REPO, WORKSPACE, output_dir


import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = WORKSPACE
OUT = output_dir("A7")
TABLES = OUT / 'tables'
FIGS = OUT / 'figures'
PROGRAMS = OUT / 'programs'
for p in (TABLES, FIGS, PROGRAMS):
    p.mkdir(parents=True, exist_ok=True)

os.chdir(ROOT)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

ge = load_module('ge21', ROOT / 'src' / '21_build_gross_error_discrimination.py')
cw = load_module('cw23', ROOT / 'src' / '23_build_confidently_wrong_fixes.py')

pred, features, combined = ge.load_inputs()
long_df = ge.build_long_table(pred, features, combined)
long_df = cw.add_nominal_rss_match_confidence(long_df)

adaptive_thresholds = ge.compute_condition_thresholds(long_df)
adaptive_thresholds['threshold_scheme'] = cw.ADAPTIVE_SLUG
fixed_thresholds = cw.make_fixed_thresholds(long_df, ge, cw.FIXED_THRESHOLD_M)

adaptive_labeled = cw.attach_strategy_labels(long_df, adaptive_thresholds, cw.ADAPTIVE_SLUG, ge)
fixed_labeled = cw.attach_strategy_labels(long_df, fixed_thresholds, cw.FIXED_SLUG, ge)
labeled = pd.concat([adaptive_labeled, fixed_labeled], ignore_index=True)

# Add four-state labels and normalized error severity.
labeled['confidence_state'] = np.where(labeled['nominally_confident'].eq(1), 'Nominally confident', 'Other scans')
labeled['outcome_state'] = np.select(
    [
        labeled['nominally_confident'].eq(1) & labeled['gross_error'].eq(0),
        labeled['nominally_confident'].eq(1) & labeled['gross_error'].eq(1),
        labeled['nominally_confident'].eq(0) & labeled['gross_error'].eq(0),
        labeled['nominally_confident'].eq(0) & labeled['gross_error'].eq(1),
    ],
    ['Confidently correct', 'Confidently wrong', 'Other correct', 'Other wrong'],
    default='Unclassified',
)
labeled['error_to_threshold_ratio'] = labeled['error_m'] / labeled['adaptive_threshold_m']
labeled['error_excess_m'] = labeled['error_m'] - labeled['adaptive_threshold_m']

# Save a compact per-fix table for reproducibility.
compact_cols = [
    'strategy','unit_label','estimator_display','row_id','error_m','adaptive_threshold_m',
    'gross_error','nominally_confident','confidently_wrong','confidently_correct',
    'outcome_state','rss_match_confidence','rss_match_confidence_percentile',
    'SQS','sigma_fps','I_k','D_cand','rss_gradient_proxy','nearest_rp_distance',
    'local_rp_density','ap_count','rss_std','rss_range'
]
labeled[compact_cols].to_csv(TABLES / 'A7_confidently_wrong_fix_level.csv.gz', index=False, compression='gzip')

# ------------------------------------------------------------------
# 1. Four-state composition by condition and strategy.
# ------------------------------------------------------------------
state_order = ['Confidently correct','Confidently wrong','Other correct','Other wrong']
condition_rows = []
for (strategy, unit, est), g in labeled.groupby(['strategy','unit_label','estimator_display'], observed=False):
    n = len(g)
    row = {
        'strategy': strategy,
        'strategy_label': cw.STRATEGY_LABELS[strategy],
        'unit_label': unit,
        'unit_short': ge.UNIT_SHORT.get(unit, unit),
        'estimator_display': est,
        'estimator_short': ge.ESTIMATOR_SHORT.get(est, est),
        'n_fixes': n,
    }
    for state in state_order:
        count = int((g['outcome_state'] == state).sum())
        slug = state.lower().replace(' ', '_')
        row[f'n_{slug}'] = count
        row[f'pct_{slug}'] = 100.0 * count / n if n else np.nan
    row['has_confidently_wrong'] = int(row['n_confidently_wrong'] > 0)
    condition_rows.append(row)
state_by_condition = pd.DataFrame(condition_rows)
state_by_condition.to_csv(TABLES / 'A7_four_state_by_condition.csv', index=False)

summary_rows = []
for strategy, g in state_by_condition.groupby('strategy', observed=False):
    source = labeled[labeled['strategy'] == strategy]
    total = len(source)
    row = {
        'strategy': strategy,
        'strategy_label': cw.STRATEGY_LABELS[strategy],
        'n_conditions': len(g),
        'conditions_with_confidently_wrong': int(g['has_confidently_wrong'].sum()),
        'condition_coverage_pct': 100.0 * g['has_confidently_wrong'].mean(),
        'n_fixes': total,
    }
    for state in state_order:
        slug = state.lower().replace(' ', '_')
        row[f'scan_weighted_{slug}_pct'] = 100.0 * (source['outcome_state'] == state).mean()
        row[f'condition_median_{slug}_pct'] = float(g[f'pct_{slug}'].median())
        row[f'condition_q25_{slug}_pct'] = float(g[f'pct_{slug}'].quantile(0.25))
        row[f'condition_q75_{slug}_pct'] = float(g[f'pct_{slug}'].quantile(0.75))
    summary_rows.append(row)
state_summary = pd.DataFrame(summary_rows)
state_summary.to_csv(TABLES / 'A7_four_state_summary.csv', index=False)

# ------------------------------------------------------------------
# 2. Severity within each condition.
# ------------------------------------------------------------------
severity_rows = []
for (strategy, unit, est), g in labeled.groupby(['strategy','unit_label','estimator_display'], observed=False):
    row = {
        'strategy': strategy,
        'strategy_label': cw.STRATEGY_LABELS[strategy],
        'unit_label': unit,
        'unit_short': ge.UNIT_SHORT.get(unit, unit),
        'estimator_display': est,
        'estimator_short': ge.ESTIMATOR_SHORT.get(est, est),
        'threshold_m': float(g['adaptive_threshold_m'].iloc[0]),
    }
    for state in state_order:
        s = g.loc[g['outcome_state'] == state, 'error_m'].dropna()
        slug = state.lower().replace(' ', '_')
        row[f'n_{slug}'] = len(s)
        row[f'median_error_{slug}_m'] = float(s.median()) if len(s) else np.nan
        row[f'p75_error_{slug}_m'] = float(s.quantile(0.75)) if len(s) else np.nan
        row[f'p90_error_{slug}_m'] = float(s.quantile(0.90)) if len(s) else np.nan
    cw_g = g[g['outcome_state'] == 'Confidently wrong']
    row['median_cw_threshold_ratio'] = float(cw_g['error_to_threshold_ratio'].median()) if len(cw_g) else np.nan
    row['median_cw_excess_m'] = float(cw_g['error_excess_m'].median()) if len(cw_g) else np.nan
    severity_rows.append(row)
severity_by_condition = pd.DataFrame(severity_rows)
severity_by_condition.to_csv(TABLES / 'A7_error_severity_by_condition.csv', index=False)

severity_summary_rows = []
for strategy, g in severity_by_condition.groupby('strategy', observed=False):
    valid_cw = g[g['n_confidently_wrong'] > 0]
    row = {
        'strategy': strategy,
        'strategy_label': cw.STRATEGY_LABELS[strategy],
        'n_conditions_with_cw': len(valid_cw),
        'median_threshold_m': float(g['threshold_m'].median()),
        'median_condition_cw_error_m': float(valid_cw['median_error_confidently_wrong_m'].median()),
        'q25_condition_cw_error_m': float(valid_cw['median_error_confidently_wrong_m'].quantile(0.25)),
        'q75_condition_cw_error_m': float(valid_cw['median_error_confidently_wrong_m'].quantile(0.75)),
        'median_condition_cc_error_m': float(g['median_error_confidently_correct_m'].median()),
        'median_condition_other_wrong_error_m': float(g.loc[g['n_other_wrong'] > 0, 'median_error_other_wrong_m'].median()),
        'median_cw_to_cc_error_ratio': float((valid_cw['median_error_confidently_wrong_m'] / valid_cw['median_error_confidently_correct_m']).replace([np.inf,-np.inf],np.nan).median()),
        'median_cw_threshold_ratio': float(valid_cw['median_cw_threshold_ratio'].median()),
        'median_cw_excess_m': float(valid_cw['median_cw_excess_m'].median()),
    }
    severity_summary_rows.append(row)
severity_summary = pd.DataFrame(severity_summary_rows)
severity_summary.to_csv(TABLES / 'A7_error_severity_summary.csv', index=False)

# ------------------------------------------------------------------
# 3. Unit and estimator heterogeneity.
# ------------------------------------------------------------------
def heterogeneity_table(group_col: str, short_col: str | None = None) -> pd.DataFrame:
    rows = []
    for (strategy, key), g in state_by_condition.groupby(['strategy', group_col], observed=False):
        row = {
            'strategy': strategy,
            'strategy_label': cw.STRATEGY_LABELS[strategy],
            group_col: key,
            'n_conditions': len(g),
            'conditions_with_cw': int(g['has_confidently_wrong'].sum()),
            'condition_coverage_pct': 100.0 * g['has_confidently_wrong'].mean(),
            'median_cw_all_pct': float(g['pct_confidently_wrong'].median()),
        }
        # CW among nominally confident = CW / (CC+CW)
        denom = g['n_confidently_correct'] + g['n_confidently_wrong']
        vals = 100.0 * g['n_confidently_wrong'] / denom.replace(0, np.nan)
        row['median_cw_among_confident_pct'] = float(vals.median())
        row['q25_cw_among_confident_pct'] = float(vals.quantile(0.25))
        row['q75_cw_among_confident_pct'] = float(vals.quantile(0.75))
        rows.append(row)
    out = pd.DataFrame(rows)
    if short_col:
        if group_col == 'estimator_display':
            out[short_col] = out[group_col].map(ge.ESTIMATOR_SHORT).fillna(out[group_col])
        elif group_col == 'unit_label':
            out[short_col] = out[group_col].map(ge.UNIT_SHORT).fillna(out[group_col])
    return out

by_estimator = heterogeneity_table('estimator_display', 'estimator_short')
by_unit = heterogeneity_table('unit_label', 'unit_short')
by_estimator.to_csv(TABLES / 'A7_prevalence_by_estimator.csv', index=False)
by_unit.to_csv(TABLES / 'A7_prevalence_by_unit.csv', index=False)

# Baseline-confidence monotonicity across quartiles.
quart = cw.compute_quartile_error_rates(labeled, ge)
monotonic_rows = []
for (strategy, unit, est), g in quart.groupby(['strategy','unit_label','estimator_display'], observed=False):
    qmap = dict(zip(g['rss_confidence_quartile'], g['gross_error_prevalence_pct']))
    if all(q in qmap for q in [1,2,3,4]):
        vals = [qmap[q] for q in [1,2,3,4]]
        monotonic_rows.append({
            'strategy': strategy,
            'unit_label': unit,
            'estimator_display': est,
            'q1_pct': vals[0], 'q2_pct': vals[1], 'q3_pct': vals[2], 'q4_pct': vals[3],
            'q4_lower_than_q1': int(vals[3] < vals[0]),
            'strictly_monotonic_decrease': int(vals[0] >= vals[1] >= vals[2] >= vals[3]),
            'q1_minus_q4_pp': vals[0] - vals[3],
        })
monotonic = pd.DataFrame(monotonic_rows)
monotonic.to_csv(TABLES / 'A7_confidence_quartile_monotonicity_by_condition.csv', index=False)
monotonic_summary = (monotonic.groupby('strategy', observed=False)
    .agg(n_conditions=('q4_lower_than_q1','size'),
         q4_lower_than_q1_pct=('q4_lower_than_q1','mean'),
         strictly_monotonic_pct=('strictly_monotonic_decrease','mean'),
         median_q1_minus_q4_pp=('q1_minus_q4_pp','median'))
    .reset_index())
monotonic_summary['q4_lower_than_q1_pct'] *= 100
monotonic_summary['strictly_monotonic_pct'] *= 100
monotonic_summary['strategy_label'] = monotonic_summary['strategy'].map(cw.STRATEGY_LABELS)
monotonic_summary.to_csv(TABLES / 'A7_confidence_quartile_monotonicity_summary.csv', index=False)

# ------------------------------------------------------------------
# 4. Secondary-screening analysis at fixed alert budgets.
# ------------------------------------------------------------------
risk_specs = cw.get_risk_specs(ge, labeled)
alert_budgets = [0.10, 0.20, 0.25]
screen_rows = []
for spec in risk_specs:
    iid = spec['id']
    score_col = f'_risk_{iid}'
    labeled[score_col] = spec['expected_sign'] * pd.to_numeric(labeled[iid], errors='coerce')
    for (strategy, unit, est), g in labeled.groupby(['strategy','unit_label','estimator_display'], observed=False):
        sub = g[g['nominally_confident'].eq(1)].copy()
        sub = sub[np.isfinite(sub[score_col])].copy()
        n = len(sub)
        n_cw = int(sub['confidently_wrong'].sum())
        n_cc = int(sub['confidently_correct'].sum())
        if n < cw.MIN_CONFIDENT_SCANS_FOR_METRIC or n_cw < cw.MIN_CW_CASES or n_cc < cw.MIN_CC_CASES:
            continue
        # Percentile within nominally confident scans in this condition.
        sub['_risk_pct'] = sub[score_col].rank(pct=True, method='average')
        baseline_prev = n_cw / n
        for budget in alert_budgets:
            flagged = sub['_risk_pct'] >= (1.0 - budget)
            n_flag = int(flagged.sum())
            caught = int((sub.loc[flagged, 'confidently_wrong'] == 1).sum())
            precision = caught / n_flag if n_flag else np.nan
            capture = caught / n_cw if n_cw else np.nan
            alert_rate = n_flag / n if n else np.nan
            lift = precision / baseline_prev if baseline_prev > 0 else np.nan
            screen_rows.append({
                'strategy': strategy,
                'strategy_label': cw.STRATEGY_LABELS[strategy],
                'indicator_id': iid,
                'label': spec['label'],
                'family': spec['family'],
                'unit_label': unit,
                'unit_short': ge.UNIT_SHORT.get(unit, unit),
                'estimator_display': est,
                'estimator_short': ge.ESTIMATOR_SHORT.get(est, est),
                'alert_budget': budget,
                'n_confident': n,
                'n_confidently_wrong': n_cw,
                'n_flagged': n_flag,
                'n_cw_captured': caught,
                'actual_alert_rate': alert_rate,
                'capture_rate': capture,
                'precision': precision,
                'baseline_prevalence': baseline_prev,
                'precision_lift': lift,
            })
screen = pd.DataFrame(screen_rows)
screen.to_csv(TABLES / 'A7_secondary_screening_by_condition.csv', index=False)

screen_summary = (screen.groupby(['strategy','strategy_label','indicator_id','label','family','alert_budget'], observed=False)
    .agg(n_conditions=('capture_rate','count'),
         median_capture_rate=('capture_rate','median'),
         q25_capture_rate=('capture_rate', lambda x: x.quantile(0.25)),
         q75_capture_rate=('capture_rate', lambda x: x.quantile(0.75)),
         median_precision=('precision','median'),
         median_baseline_prevalence=('baseline_prevalence','median'),
         median_precision_lift=('precision_lift','median'),
         median_actual_alert_rate=('actual_alert_rate','median'))
    .reset_index())
screen_summary.to_csv(TABLES / 'A7_secondary_screening_summary.csv', index=False)

# Create a findings JSON with key manuscript values.
findings = {
    'four_state_summary': state_summary.to_dict(orient='records'),
    'severity_summary': severity_summary.to_dict(orient='records'),
    'monotonicity_summary': monotonic_summary.to_dict(orient='records'),
    'top_screening_20pct': {},
}
for strategy in [cw.ADAPTIVE_SLUG, cw.FIXED_SLUG]:
    s = screen_summary[(screen_summary['strategy'] == strategy) & (screen_summary['alert_budget'] == 0.20)]
    s = s.sort_values(['median_capture_rate','median_precision_lift'], ascending=False)
    findings['top_screening_20pct'][strategy] = s.head(10).to_dict(orient='records')

with open(TABLES / 'A7_findings.json', 'w', encoding='utf-8') as f:
    json.dump(findings, f, indent=2, default=float)

print('\nFOUR STATE SUMMARY')
print(state_summary.to_string(index=False))
print('\nSEVERITY SUMMARY')
print(severity_summary.to_string(index=False))
print('\nMONOTONICITY')
print(monotonic_summary.to_string(index=False))
print('\nBY ESTIMATOR')
print(by_estimator.sort_values(['strategy','median_cw_among_confident_pct'], ascending=[True,False]).to_string(index=False))
print('\nTOP SCREENING AT 20%')
for strategy in [cw.ADAPTIVE_SLUG, cw.FIXED_SLUG]:
    s = screen_summary[(screen_summary['strategy'] == strategy) & (screen_summary['alert_budget'] == 0.20)]
    print('\n', strategy)
    print(s.sort_values(['median_capture_rate','median_precision_lift'], ascending=False).head(10).to_string(index=False))

print(f'\nSaved to {OUT}')
