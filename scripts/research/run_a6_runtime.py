#!/usr/bin/env python3
from __future__ import annotations
from research_paths import REPO, WORKSPACE, output_dir


import os
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('NUMEXPR_NUM_THREADS', '1')

import argparse
import importlib.util
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import KDTree
from threadpoolctl import threadpool_limits, threadpool_info

ROOT = WORKSPACE
SRC = ROOT / 'src' / '20_make_indicator_tables_and_association_figure.py'
OUT = output_dir("A6")
TABLES = OUT / 'tables'
PROGRAMS = OUT / 'programs'
TABLES.mkdir(parents=True, exist_ok=True)
PROGRAMS.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location('indicator_builder', SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

COMBINED_PATH = ROOT / 'data/interim/datasets_combined_all/combined_all_datasets.csv'
PRED_PATH = ROOT / 'data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz'
FEAT_PATH = ROOT / 'data/processed/scan_level_reliability_indicator_features.csv.gz'

RNG = np.random.default_rng(20260725)
EPS = 1e-6


def add_unit_label(df: pd.DataFrame) -> pd.DataFrame:
    return mod.ensure_unit_label(df)


def robust_bounds(series: pd.Series):
    vals = pd.to_numeric(series, errors='coerce').to_numpy(float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return (np.nan, np.nan)
    lo, hi = np.percentile(vals, [5, 95])
    return (float(lo), float(hi))


def robust_one(value: float, bounds):
    lo, hi = bounds
    if not np.isfinite(value):
        return np.nan
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return 0.5
    return float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))


def vectorize_scan(rss: dict[str, float], ap_index: dict[str, int], p: int):
    x = np.full(p, mod.RSS_FLOOR, dtype=np.float32)
    present = np.zeros(p, dtype=bool)
    for ap, val in rss.items():
        j = ap_index.get(ap)
        if j is not None:
            x[j] = float(val)
            present[j] = True
    return x, present


def retrieve_top20(train_X: np.ndarray, train_norm: np.ndarray, q: np.ndarray, k: int = 20):
    k = min(k, len(train_X))
    qrow = np.asarray(q, dtype=np.float32).reshape(1, -1)
    qnorm = np.sum(qrow * qrow, axis=1, dtype=np.float32)[:, None]
    dist2 = qnorm + train_norm[None, :] - 2.0 * (qrow @ train_X.T)
    np.maximum(dist2, 0.0, out=dist2)
    idx2 = np.argpartition(dist2, kth=k - 1, axis=1)[:, :k]
    part = np.take_along_axis(dist2, idx2, axis=1)
    order = np.argsort(part, axis=1)
    idx = np.take_along_axis(idx2, order, axis=1)[0]
    vals = np.take_along_axis(part, order, axis=1)[0]
    d = np.sqrt(vals, dtype=np.float32) / np.sqrt(max(1, train_X.shape[1]))
    return d, idx


def pairwise_diameter(points: np.ndarray) -> float:
    if len(points) <= 1:
        return 0.0
    diff = points[:, None, :] - points[None, :, :]
    return float(np.sqrt(np.sum(diff * diff, axis=2)).max())


def jaccard_stats(test_presence: np.ndarray, cand_presence: np.ndarray):
    inter = np.logical_and(cand_presence, test_presence).sum(axis=1).astype(float)
    union = np.logical_or(cand_presence, test_presence).sum(axis=1).astype(float)
    jac = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    return float(jac.max()), float(jac.mean())


def cosine_sim(a: np.ndarray, b: np.ndarray):
    aa = a.astype(float) - mod.RSS_FLOOR
    bb = b.astype(float) - mod.RSS_FLOOR
    denom = np.linalg.norm(aa) * np.linalg.norm(bb)
    if denom <= 0 or not np.isfinite(denom):
        return np.nan
    return float(np.dot(aa, bb) / denom)


def prepare_unit(unit: str, combined: pd.DataFrame, pred: pd.DataFrame, feat: pd.DataFrame):
    pred_unit = pred[pred['unit_label'] == unit].copy()
    dataset = str(pred_unit['dataset'].iloc[0])
    group = str(pred_unit['group'].iloc[0])
    test_ids = set(pred_unit['row_id'].astype(str).unique())

    t0 = time.perf_counter_ns()
    unit_df = combined[(combined['dataset'].astype(str) == dataset) & (combined['group'].astype(str) == group)].copy()
    train_df = unit_df[unit_df['split'].astype(str).str.lower().eq('train')].copy()
    test_df = unit_df[unit_df['row_id'].astype(str).isin(test_ids)].copy()

    train_xy = mod.safe_xy(train_df)
    test_xy = mod.safe_xy(test_df)
    valid_train = np.isfinite(train_xy).all(axis=1)
    valid_test = np.isfinite(test_xy).all(axis=1)
    train_df = train_df.loc[valid_train].reset_index(drop=True)
    test_df = test_df.loc[valid_test].reset_index(drop=True)
    train_xy = train_xy[valid_train]
    test_xy = test_xy[valid_test]

    train_rss = [mod.parse_rss_json(s) for s in train_df['rss_json'].tolist()]
    test_rss = [mod.parse_rss_json(s) for s in test_df['rss_json'].tolist()]
    ap_list = mod.select_ap_list(train_rss, test_rss, mod.MAX_APS_PER_UNIT)
    ap_index = {ap: j for j, ap in enumerate(ap_list)}
    train_X, train_present = mod.make_dense_matrix(train_rss, ap_list)
    test_X, test_present = mod.make_dense_matrix(test_rss, ap_list)
    train_X, train_present, train_xy_templates, n_templates = mod.aggregate_training_templates(
        train_X, train_present, train_xy, train_df['floor'].to_numpy()
    )
    train_norm = np.sum(train_X * train_X, axis=1, dtype=np.float32)
    unique_xy = np.unique(train_xy_templates, axis=0)
    rp_tree = KDTree(unique_xy)
    density_radius = mod.adaptive_density_radius(unique_xy)

    f_unit = feat[feat['unit_label'] == unit]
    bounds = {
        name: robust_bounds(f_unit[name])
        for name in [
            'min_rss_distance', 'sigma_fps', 'D_cand', 'rss_gradient_proxy',
            'ap_set_novelty', 'ap_count', 'ap_overlap', 'local_rp_density',
            'nearest_match_isolation'
        ]
    }
    prep_ms = (time.perf_counter_ns() - t0) / 1e6

    # Precompute the reference top-20 candidates with the same batched routine used
    # in the analytical pipeline. These candidates are used only to time the
    # post-retrieval calculations and to avoid numerical tie-breaking differences
    # between batch and one-query matrix multiplication.
    dists_all, idx_all = mod.topk_euclidean_neighbors(
        train_X, test_X, k=min(20, len(train_X)), chunk_size=mod.DISTANCE_CHUNK_SIZE
    )

    pred_by_row = {
        str(row_id): g[['x_pred', 'y_pred']].apply(pd.to_numeric, errors='coerce').to_numpy(float)
        for row_id, g in pred_unit.groupby('row_id', observed=False)
    }

    radio_map_bytes = (
        train_X.nbytes + train_present.nbytes + train_xy_templates.nbytes + train_norm.nbytes
    )

    return {
        'unit': unit,
        'dataset': dataset,
        'group': group,
        'train_df': train_df,
        'test_df': test_df,
        'test_rss': test_rss,
        'test_X': test_X,
        'test_present': test_present,
        'test_xy': test_xy,
        'train_X': train_X,
        'train_present': train_present,
        'train_xy': train_xy_templates,
        'train_norm': train_norm,
        'ap_list': ap_list,
        'ap_index': ap_index,
        'rp_tree': rp_tree,
        'density_radius': density_radius,
        'bounds': bounds,
        'pred_by_row': pred_by_row,
        'dists_all': dists_all,
        'idx_all': idx_all,
        'prep_ms': prep_ms,
        'n_train_scans': len(train_df),
        'n_test_scans': len(test_df),
        'n_templates': n_templates,
        'n_ap_features': len(ap_list),
        'radio_map_mb': radio_map_bytes / (1024**2),
    }


def compute_one(ctx, i: int, M: int):
    rss = ctx['test_rss'][i]
    row_id = str(ctx['test_df']['row_id'].iloc[i])
    phase = {}
    total_start = time.perf_counter_ns()

    t = time.perf_counter_ns()
    q, q_present = vectorize_scan(rss, ctx['ap_index'], ctx['n_ap_features'])
    phase['scan_vectorization_ms'] = (time.perf_counter_ns() - t) / 1e6

    t = time.perf_counter_ns()
    _d_online, _idx_online = retrieve_top20(ctx['train_X'], ctx['train_norm'], q, k=20)
    phase['candidate_retrieval_ms'] = (time.perf_counter_ns() - t) / 1e6

    dists = ctx['dists_all'][i]
    idx = ctx['idx_all'][i]
    m = min(M, len(idx))
    cand_idx = idx[:m]
    cand_d = dists[:m]
    cand_xy = ctx['train_xy'][cand_idx]

    t = time.perf_counter_ns()
    rss_values = np.asarray(list(rss.values()), dtype=float)
    ap_count = int(q_present.sum())
    rss_std = float(np.nanstd(rss_values)) if len(rss_values) else np.nan
    rss_range = float(np.nanmax(rss_values) - np.nanmin(rss_values)) if len(rss_values) else np.nan
    phase['scan_statistics_ms'] = (time.perf_counter_ns() - t) / 1e6

    t = time.perf_counter_ns()
    min_rss = float(cand_d[0])
    second_rss = float(cand_d[1]) if len(cand_d) > 1 else min_rss
    gap = max(second_rss - min_rss, 0.0)
    isolation = gap / (second_rss + EPS)
    max_jac, mean_jac = jaccard_stats(q_present, ctx['train_present'][cand_idx])
    novelty = 1.0 - max_jac
    nearest_cos = cosine_sim(q, ctx['train_X'][cand_idx[0]])
    phase['compatibility_ms'] = (time.perf_counter_ns() - t) / 1e6

    t = time.perf_counter_ns()
    centroid = np.mean(cand_xy, axis=0)
    spread = float(np.sqrt(np.mean(np.sum((cand_xy - centroid) ** 2, axis=1))))
    diam = pairwise_diameter(cand_xy)
    cumulative = np.cumsum(cand_xy, axis=0) / np.arange(1, m + 1)[:, None]
    ik = float(np.max(np.linalg.norm(cumulative - cumulative[-1], axis=1)))
    kth_rss = float(cand_d[m - 1])
    contrast = max(kth_rss - min_rss, EPS)
    grad = spread / contrast
    phase['candidate_geometry_ms'] = (time.perf_counter_ns() - t) / 1e6

    t = time.perf_counter_ns()
    density = int(ctx['rp_tree'].query_radius(centroid.reshape(1, -1), r=ctx['density_radius'], count_only=True)[0])
    phase['local_support_ms'] = (time.perf_counter_ns() - t) / 1e6

    t = time.perf_counter_ns()
    b = ctx['bounds']
    risk_min = robust_one(min_rss, b['min_rss_distance'])
    risk_spread = robust_one(spread, b['sigma_fps'])
    risk_diam = robust_one(diam, b['D_cand'])
    risk_novelty = robust_one(novelty, b['ap_set_novelty'])
    sup_signal = 1.0 - risk_min
    sup_geometry = 1.0 - np.nanmean([risk_spread, risk_diam])
    sup_ap_count = robust_one(ap_count, b['ap_count'])
    sup_overlap = robust_one(max_jac, b['ap_overlap'])
    sup_density = robust_one(density, b['local_rp_density'])
    sup_isolation = robust_one(isolation, b['nearest_match_isolation'])
    sqs = float(np.nanmean([sup_signal, sup_geometry, sup_ap_count, sup_overlap, sup_density]))
    c_sigma = float(sup_signal / (1.0 + risk_spread))
    fii = float(np.nanmean([sup_signal, sup_ap_count, sup_overlap, sup_isolation, 1.0 - risk_novelty]))
    decision = bool(sqs < 0.5)
    phase['composite_and_decision_ms'] = (time.perf_counter_ns() - t) / 1e6

    t = time.perf_counter_ns()
    pred_xy = ctx['pred_by_row'].get(row_id)
    nrp_values = []
    if pred_xy is not None:
        for xy in pred_xy:
            if np.isfinite(xy).all():
                dd, _ = ctx['rp_tree'].query(xy.reshape(1, -1), k=1)
                nrp_values.append(float(dd[0, 0]))
    phase['nearest_rp_all_estimators_ms'] = (time.perf_counter_ns() - t) / 1e6
    phase['nearest_rp_per_estimator_ms'] = phase['nearest_rp_all_estimators_ms'] / max(1, len(nrp_values))

    phase['post_retrieval_indicators_ms'] = (
        phase['scan_statistics_ms'] + phase['compatibility_ms'] + phase['candidate_geometry_ms'] +
        phase['local_support_ms'] + phase['composite_and_decision_ms'] + phase['nearest_rp_per_estimator_ms']
    )
    phase['total_one_estimator_ms'] = (
        phase['scan_vectorization_ms'] + phase['candidate_retrieval_ms'] + phase['post_retrieval_indicators_ms']
    )
    phase['outer_total_ms'] = (time.perf_counter_ns() - total_start) / 1e6

    vals = {
        'row_id': row_id,
        'min_rss_distance': min_rss,
        'nearest_match_isolation': isolation,
        'max_cosine_similarity': nearest_cos,
        'sigma_fps': spread,
        'D_cand': diam,
        'I_k': ik,
        'rss_gradient_proxy': grad,
        'ap_overlap': max_jac,
        'mean_ap_overlap': mean_jac,
        'ap_set_novelty': novelty,
        'local_rp_density': density,
        'ap_count': ap_count,
        'rss_std': rss_std,
        'rss_range': rss_range,
        'SQS': sqs,
        'C_sigma': c_sigma,
        'FII': fii,
        'nearest_rp_mean': float(np.mean(nrp_values)) if nrp_values else np.nan,
        'decision_dummy': decision,
    }
    return phase, vals


def percentile_summary(s: pd.Series):
    a = pd.to_numeric(s, errors='coerce').dropna().to_numpy(float)
    if len(a) == 0:
        return {'mean': np.nan, 'median': np.nan, 'p95': np.nan, 'min': np.nan, 'max': np.nan}
    return {
        'mean': float(np.mean(a)), 'median': float(np.median(a)),
        'p95': float(np.percentile(a, 95)), 'min': float(np.min(a)), 'max': float(np.max(a))
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples-per-unit', type=int, default=200)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    if args.quick:
        args.samples_per_unit = 30
        args.repeats = 1

    usecols = ['dataset','group','floor','split','row_id','x','y','rss_json','rss_count']
    combined = pd.read_csv(COMBINED_PATH, usecols=usecols, dtype={'row_id':str}, low_memory=False)
    combined = add_unit_label(combined)
    pred = pd.read_csv(PRED_PATH, dtype={'row_id':str}, low_memory=False)
    pred = add_unit_label(pred)
    pred = pred[pred['estimator_display'].isin(mod.ESTIMATOR_ORDER)].copy()
    feat = pd.read_csv(FEAT_PATH, dtype={'row_id':str}, low_memory=False)
    feat = add_unit_label(feat)
    units = sorted(pred['unit_label'].unique(), key=mod.unit_sort_key)

    unit_records = []
    phase_records = []
    validation_records = []

    with threadpool_limits(limits=1):
        for ui, unit in enumerate(units, 1):
            print(f'[{ui}/{len(units)}] preparing {unit}', flush=True)
            ctx = prepare_unit(unit, combined, pred, feat)
            unit_records.append({k: ctx[k] for k in [
                'unit','dataset','group','prep_ms','n_train_scans','n_test_scans',
                'n_templates','n_ap_features','radio_map_mb'
            ]})

            n = ctx['n_test_scans']
            sample_n = min(args.samples_per_unit, n)
            indices = RNG.choice(n, size=sample_n, replace=False)

            # Warm-up.
            for i in indices[:min(20, sample_n)]:
                compute_one(ctx, int(i), 10)

            for M in [5, 10, 15]:
                for rep in range(args.repeats):
                    order = RNG.permutation(indices)
                    for i in order:
                        phase, vals = compute_one(ctx, int(i), M)
                        rec = {'unit_label': unit, 'M': M, 'repeat': rep, 'row_id': vals['row_id']}
                        rec.update(phase)
                        phase_records.append(rec)
                        if M == 10 and rep == 0 and len(validation_records) < 500:
                            vr = {'unit_label': unit, 'row_id': vals['row_id']}
                            vr.update(vals)
                            validation_records.append(vr)

    unit_df = pd.DataFrame(unit_records)
    phase_df = pd.DataFrame(phase_records)
    val_df = pd.DataFrame(validation_records)

    # Validate M=10 outputs against stored scan-level values.
    val_merge = val_df.merge(
        feat, on=['unit_label','row_id'], how='left', suffixes=('_bench','_stored')
    )
    value_cols = [
        'min_rss_distance','nearest_match_isolation','max_cosine_similarity','sigma_fps',
        'D_cand','I_k','rss_gradient_proxy','ap_overlap','mean_ap_overlap','ap_set_novelty',
        'local_rp_density','ap_count','rss_std','rss_range','SQS','C_sigma','FII'
    ]
    val_rows = []
    for c in value_cols:
        a = pd.to_numeric(val_merge[f'{c}_bench'], errors='coerce').to_numpy(float)
        b = pd.to_numeric(val_merge[f'{c}_stored'], errors='coerce').to_numpy(float)
        mask = np.isfinite(a) & np.isfinite(b)
        diff = np.abs(a[mask]-b[mask]) if mask.any() else np.array([])
        val_rows.append({
            'indicator': c, 'n_compared': int(mask.sum()),
            'median_abs_difference': float(np.median(diff)) if len(diff) else np.nan,
            'p95_abs_difference': float(np.percentile(diff,95)) if len(diff) else np.nan,
            'max_abs_difference': float(np.max(diff)) if len(diff) else np.nan,
            'pct_within_1e6': float(100*np.mean(diff <= 1e-6)) if len(diff) else np.nan,
        })
    validation_summary = pd.DataFrame(val_rows)

    # Per-unit runtime summary.
    unit_runtime_rows = []
    for (unit, M), g in phase_df.groupby(['unit_label','M'], observed=False):
        row = {'unit_label': unit, 'M': int(M), 'n_measurements': len(g)}
        for c in [
            'scan_vectorization_ms','candidate_retrieval_ms','scan_statistics_ms','compatibility_ms',
            'candidate_geometry_ms','local_support_ms','composite_and_decision_ms',
            'nearest_rp_per_estimator_ms','post_retrieval_indicators_ms','total_one_estimator_ms'
        ]:
            s = percentile_summary(g[c])
            row[f'{c}_median'] = s['median']
            row[f'{c}_p95'] = s['p95']
        unit_runtime_rows.append(row)
    unit_runtime = pd.DataFrame(unit_runtime_rows).merge(unit_df, left_on='unit_label', right_on='unit', how='left').drop(columns=['unit'])

    # Overall pooled summary by M and across-unit summary.
    overall_rows = []
    for M, g in phase_df.groupby('M', observed=False):
        rec = {'M': int(M), 'n_measurements': len(g)}
        for c in [
            'scan_vectorization_ms','candidate_retrieval_ms','scan_statistics_ms','compatibility_ms',
            'candidate_geometry_ms','local_support_ms','composite_and_decision_ms',
            'nearest_rp_per_estimator_ms','post_retrieval_indicators_ms','total_one_estimator_ms'
        ]:
            s = percentile_summary(g[c])
            rec[f'{c}_mean'] = s['mean']
            rec[f'{c}_median'] = s['median']
            rec[f'{c}_p95'] = s['p95']
        # median and range of unit medians
        ug = unit_runtime[unit_runtime['M'] == M]
        rec['median_of_unit_median_total_ms'] = float(ug['total_one_estimator_ms_median'].median())
        rec['min_unit_median_total_ms'] = float(ug['total_one_estimator_ms_median'].min())
        rec['max_unit_median_total_ms'] = float(ug['total_one_estimator_ms_median'].max())
        rec['median_of_unit_p95_total_ms'] = float(ug['total_one_estimator_ms_p95'].median())
        overall_rows.append(rec)
    overall = pd.DataFrame(overall_rows)

    # Phase share for primary M=10.
    primary = phase_df[phase_df['M'] == 10]
    phase_names = [
        'scan_vectorization_ms','candidate_retrieval_ms','scan_statistics_ms','compatibility_ms',
        'candidate_geometry_ms','local_support_ms','composite_and_decision_ms','nearest_rp_per_estimator_ms'
    ]
    phase_summary_rows = []
    total_median = float(primary['total_one_estimator_ms'].median())
    for c in phase_names:
        s = percentile_summary(primary[c])
        phase_summary_rows.append({
            'phase': c, 'median_ms': s['median'], 'p95_ms': s['p95'],
            'share_of_sum_of_phase_medians_pct': np.nan
        })
    phase_summary = pd.DataFrame(phase_summary_rows)
    denom = phase_summary['median_ms'].sum()
    phase_summary['share_of_sum_of_phase_medians_pct'] = 100.0 * phase_summary['median_ms'] / denom

    # Platform metadata.
    import numpy, sklearn, scipy, threadpoolctl
    metadata = {
        'timestamp_utc': pd.Timestamp.utcnow().isoformat(),
        'os': platform.platform(),
        'python': sys.version.replace('\n',' '),
        'numpy': numpy.__version__,
        'pandas': pd.__version__,
        'scikit_learn': sklearn.__version__,
        'scipy': scipy.__version__,
        'threadpoolctl': threadpoolctl.__version__,
        'threadpool_limit': 1,
        'samples_per_unit': args.samples_per_unit,
        'repeats': args.repeats,
        'units': len(units),
        'total_test_scans': int(unit_df['n_test_scans'].sum()),
        'threadpools': threadpool_info(),
    }

    phase_df.to_csv(TABLES/'A6_per_scan_runtime_measurements.csv.gz', index=False, compression='gzip')
    unit_df.to_csv(TABLES/'A6_offline_preparation_by_unit.csv', index=False)
    unit_runtime.to_csv(TABLES/'A6_runtime_by_unit_and_M.csv', index=False)
    overall.to_csv(TABLES/'A6_runtime_summary_by_M.csv', index=False)
    phase_summary.to_csv(TABLES/'A6_primary_phase_summary.csv', index=False)
    validation_summary.to_csv(TABLES/'A6_runtime_validation.csv', index=False)
    with open(TABLES/'A6_platform_metadata.json','w') as f:
        json.dump(metadata,f,indent=2,default=str)

    findings = {
        'primary_M': 10,
        'primary_pooled_median_ms': float(overall.loc[overall.M==10,'total_one_estimator_ms_median'].iloc[0]),
        'primary_pooled_p95_ms': float(overall.loc[overall.M==10,'total_one_estimator_ms_p95'].iloc[0]),
        'primary_median_unit_median_ms': float(overall.loc[overall.M==10,'median_of_unit_median_total_ms'].iloc[0]),
        'primary_max_unit_median_ms': float(overall.loc[overall.M==10,'max_unit_median_total_ms'].iloc[0]),
        'candidate_retrieval_median_ms': float(overall.loc[overall.M==10,'candidate_retrieval_ms_median'].iloc[0]),
        'post_retrieval_median_ms': float(overall.loc[overall.M==10,'post_retrieval_indicators_ms_median'].iloc[0]),
        'offline_prep_median_ms': float(unit_df.prep_ms.median()),
        'offline_prep_range_ms': [float(unit_df.prep_ms.min()), float(unit_df.prep_ms.max())],
        'radio_map_memory_median_mb': float(unit_df.radio_map_mb.median()),
        'radio_map_memory_max_mb': float(unit_df.radio_map_mb.max()),
        'validation_median_of_indicator_medians': float(validation_summary.median_abs_difference.median()),
    }
    with open(TABLES/'A6_findings.json','w') as f:
        json.dump(findings,f,indent=2)

    print('\nOVERALL\n', overall.to_string(index=False), flush=True)
    print('\nPHASES M=10\n', phase_summary.to_string(index=False), flush=True)
    print('\nOFFLINE\n', unit_df.to_string(index=False), flush=True)
    print('\nVALIDATION\n', validation_summary.to_string(index=False), flush=True)
    print('\nFINDINGS\n', json.dumps(findings,indent=2), flush=True)

if __name__ == '__main__':
    main()
