from __future__ import annotations
from research_paths import REPO, WORKSPACE, output_dir


import json
import math
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.neighbors import KDTree

ROOT = WORKSPACE
OUT = output_dir("A5")
TABLE_DIR = OUT / 'tables'
FIG_DIR = OUT / 'figures'
TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

PRED_PATH = ROOT / 'data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz'
FEAT_PATH = ROOT / 'data/processed/scan_level_reliability_indicator_features.csv.gz'
COMBINED_PATH = ROOT / 'data/interim/datasets_combined_all/combined_all_datasets.csv'
SRC20 = ROOT / 'src/20_make_indicator_tables_and_association_figure.py'
SRC21 = ROOT / 'src/21_build_gross_error_discrimination.py'

# Sensitivity grids
FIXED_THRESHOLDS = [5.0, 7.0, 10.0]
ADAPTIVE_QUANTILES = [0.70, 0.75, 0.80]
ADAPTIVE_MULTIPLIERS = [1.0, 1.5, 2.0]
CONFIDENCE_QUANTILES = [0.70, 0.75, 0.80]
CANDIDATE_SIZES = [5, 10, 15]
IK_HORIZONS = [5, 10, 15]
EPS_VALUES = [1e-8, 1e-6, 1e-4, 1e-2]
CSIGMA_CONSTANTS = [0.5, 1.0, 2.0]
BASE_EPS = 1e-6
BASE_Q = 0.75
BASE_LAMBDA = 1.5
BASE_FIXED = 7.0
BASE_CONF_Q = 0.75
BASE_M = 10
BASE_K = 10
BASE_CSIGMA = 1.0

MIN_SCANS = 20
MIN_POS = 3
MIN_NEG = 3

RISK_INDICATORS = [
    'SQS','sigma_fps','rss_gradient_proxy','I_k','D_cand',
    'nearest_rp_distance','local_rp_density','ap_count','rss_std','rss_range'
]
CONF_COMPONENTS = [
    ('FII', +1), ('C_sigma', +1), ('ap_overlap', +1),
    ('mean_ap_overlap', +1), ('max_cosine_similarity', +1),
    ('nearest_match_isolation', +1), ('min_rss_distance', -1),
    ('ap_set_novelty', -1),
]
CANDIDATE_SENSITIVE = [
    'SQS','C_sigma','FII','sigma_fps','D_cand','I_k',
    'rss_gradient_proxy','ap_overlap','mean_ap_overlap',
    'ap_set_novelty','local_rp_density'
]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

m20 = load_module(SRC20, 'm20')
ge = load_module(SRC21, 'ge')

INDICATOR_SPECS = ge.INDICATOR_SPECS
SPEC_BY_ID = {s['id']: s for s in INDICATOR_SPECS}


def finite(s):
    return pd.to_numeric(s, errors='coerce').replace([np.inf, -np.inf], np.nan)


def robust01(s: pd.Series) -> np.ndarray:
    x = finite(s).to_numpy(dtype=float)
    good = np.isfinite(x)
    out = np.full(len(x), np.nan, dtype=float)
    if good.sum() == 0:
        return out
    lo, hi = np.nanpercentile(x[good], [5, 95])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        out[good] = 0.5
    else:
        out[good] = np.clip((x[good] - lo) / (hi - lo), 0, 1)
    return out


def auc_metrics(y, score):
    d = pd.DataFrame({'y': y, 's': score}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) < MIN_SCANS:
        return None
    yy = d['y'].astype(int).to_numpy()
    ss = d['s'].astype(float).to_numpy()
    npos = int(yy.sum()); nneg = int(len(yy)-npos)
    if npos < MIN_POS or nneg < MIN_NEG:
        return None
    return {
        'n': int(len(yy)), 'n_pos': npos, 'prevalence': npos/len(yy),
        'auroc': float(roc_auc_score(yy, ss)),
        'auprc': float(average_precision_score(yy, ss)),
    }


def rank_concordance(summary: pd.DataFrame, baseline: pd.DataFrame, metric='median_auroc'):
    a = baseline[['indicator_id', metric]].merge(
        summary[['indicator_id', metric]], on='indicator_id', suffixes=('_base','_var')
    ).dropna()
    if len(a) < 3:
        return np.nan
    return float(spearmanr(a[f'{metric}_base'], a[f'{metric}_var']).statistic)


def top_overlap(summary: pd.DataFrame, baseline: pd.DataFrame, n=6, metric='median_auroc'):
    s1 = set(baseline.sort_values(metric, ascending=False).head(n)['indicator_id'])
    s2 = set(summary.sort_values(metric, ascending=False).head(n)['indicator_id'])
    return len(s1 & s2) / n


def add_unit_label(df):
    if 'unit_label' in df:
        return df
    df = df.copy()
    if 'unit' in df:
        df['unit_label'] = df['unit'].astype(str)
    else:
        df['unit_label'] = df['dataset'].astype(str) + ' / ' + df['group'].astype(str)
    return df


def load_long():
    pred = pd.read_csv(PRED_PATH, dtype={'row_id': str}, low_memory=False)
    pred = add_unit_label(pred)
    pred = pred[pred['estimator_display'].isin(ge.ESTIMATOR_ORDER)].copy()
    pred['error_m'] = finite(pred['error_m'])
    pred = pred[pred['error_m'].notna()].copy()

    feat = pd.read_csv(FEAT_PATH, dtype={'row_id': str}, low_memory=False)
    feat = add_unit_label(feat)

    usecols = ['dataset','group','split','x','y','row_id','floor','rss_json','rss_count']
    combined = pd.read_csv(COMBINED_PATH, usecols=usecols, dtype={'row_id':str}, low_memory=False)
    combined = add_unit_label(combined)
    pairs = pred[['dataset','group']].drop_duplicates()
    pairset = set(map(tuple, pairs.astype(str).to_numpy()))
    combined = combined[combined[['dataset','group']].astype(str).apply(tuple,axis=1).isin(pairset)].copy()

    long_df = ge.build_long_table(pred, feat, combined)
    return pred, feat, combined, long_df


def thresholds_adaptive(long_df, q, lam):
    rows=[]
    for (unit,est), g in long_df.groupby(['unit_label','estimator_display'], observed=False):
        err=finite(g['error_m']).dropna().to_numpy(float)
        if not len(err): continue
        lo=float(np.quantile(err,1-q)); hi=float(np.quantile(err,q)); spread=hi-lo
        tau=hi+lam*spread
        rows.append((unit,est,tau,float(np.mean(err>tau))))
    return pd.DataFrame(rows,columns=['unit_label','estimator_display','threshold_m','prevalence'])


def thresholds_fixed(long_df, t):
    rows=[]
    for (unit,est), g in long_df.groupby(['unit_label','estimator_display'], observed=False):
        err=finite(g['error_m']).dropna().to_numpy(float)
        if not len(err): continue
        rows.append((unit,est,t,float(np.mean(err>t))))
    return pd.DataFrame(rows,columns=['unit_label','estimator_display','threshold_m','prevalence'])


def evaluate_discrimination(long_df, thresholds, indicator_ids=None):
    df=long_df.merge(thresholds[['unit_label','estimator_display','threshold_m']],
                     on=['unit_label','estimator_display'],how='left',validate='many_to_one')
    df['gross_error']=(finite(df['error_m'])>finite(df['threshold_m'])).astype(int)
    specs=[s for s in INDICATOR_SPECS if s['id'] in df.columns]
    if indicator_ids is not None:
        specs=[s for s in specs if s['id'] in indicator_ids]
    rows=[]
    for spec in specs:
        iid=spec['id']; sign=spec['expected_sign']
        score=sign*finite(df[iid])
        for (unit,est), idx in df.groupby(['unit_label','estimator_display'], observed=False).groups.items():
            met=auc_metrics(df.loc[idx,'gross_error'],score.loc[idx])
            if met:
                rows.append({'indicator_id':iid,'label':spec['label'],'family':spec['family'],
                             'unit_label':unit,'estimator_display':est,**met})
    by=pd.DataFrame(rows)
    if by.empty:
        return by, by
    sm=(by.groupby(['indicator_id','label','family'],observed=False)
          .agg(n_conditions=('auroc','count'),median_auroc=('auroc','median'),
               median_auprc=('auprc','median'),median_prevalence=('prevalence','median'))
          .reset_index().sort_values(['median_auroc','median_auprc'],ascending=False))
    return by,sm


def evaluate_association(long_df, indicator_ids=None):
    specs=[s for s in INDICATOR_SPECS if s['id'] in long_df.columns]
    if indicator_ids is not None:
        specs=[s for s in specs if s['id'] in indicator_ids]
    rows=[]
    for spec in specs:
        iid=spec['id']; sign=spec['expected_sign']
        for (unit,est), g in long_df.groupby(['unit_label','estimator_display'],observed=False):
            d=pd.DataFrame({'x':finite(g[iid]),'e':finite(g['error_m'])}).dropna()
            if len(d)<8 or d['x'].nunique()<2 or d['e'].nunique()<2: continue
            rho=float(spearmanr(d['x'],d['e']).statistic)
            rows.append({'indicator_id':iid,'label':spec['label'],'family':spec['family'],
                         'unit_label':unit,'estimator_display':est,'aligned_rho':sign*rho})
    by=pd.DataFrame(rows)
    if by.empty: return by,by
    sm=(by.groupby(['indicator_id','label','family'],observed=False)
          .agg(n_conditions=('aligned_rho','count'),median_aligned_rho=('aligned_rho','median'),
               direction_consistency=('aligned_rho',lambda x:np.mean(np.asarray(x)>0)))
          .reset_index().sort_values('median_aligned_rho',ascending=False))
    return by,sm


def build_confidence_scan(feat):
    keys=['dataset','group','unit_label','row_id']
    scan=feat[keys+[c for c,_ in CONF_COMPONENTS if c in feat.columns]].copy()
    ranks=[]
    for c, direction in CONF_COMPONENTS:
        if c not in scan: continue
        rc='rank_'+c
        scan[rc]=np.nan
        for unit, idx in scan.groupby('unit_label',observed=False).groups.items():
            scan.loc[idx,rc]=(direction*finite(scan.loc[idx,c])).rank(pct=True,method='average')
        ranks.append(rc)
    scan['baseline_confidence']=scan[ranks].mean(axis=1,skipna=True)
    return scan[keys+['baseline_confidence']]


def evaluate_confidence_quantile(long_df, conf_scan, q, thresholds, risk_ids=RISK_INDICATORS):
    df=long_df.merge(conf_scan,on=['dataset','group','unit_label','row_id'],how='left',validate='many_to_one')
    df['nominally_confident']=0
    for unit, idx in df.groupby('unit_label',observed=False).groups.items():
        # repeated estimators: threshold based on unique scans
        unique=df.loc[idx,['row_id','baseline_confidence']].drop_duplicates('row_id')
        thr=float(np.nanquantile(unique['baseline_confidence'],q))
        df.loc[idx,'nominally_confident']=(finite(df.loc[idx,'baseline_confidence'])>=thr).astype(int)
    df=df.merge(thresholds[['unit_label','estimator_display','threshold_m']],
                on=['unit_label','estimator_display'],how='left',validate='many_to_one')
    df['gross_error']=(finite(df['error_m'])>finite(df['threshold_m'])).astype(int)
    df['confidently_wrong']=((df['nominally_confident']==1)&(df['gross_error']==1)).astype(int)
    cond=[]
    for (unit,est),g in df.groupby(['unit_label','estimator_display'],observed=False):
        n=len(g); nc=int(g['nominally_confident'].sum()); ng=int(g['gross_error'].sum()); nw=int(g['confidently_wrong'].sum())
        cond.append({'unit_label':unit,'estimator_display':est,'n':n,'n_confident':nc,'n_gross':ng,'n_cw':nw,
                     'cw_all_pct':100*nw/n if n else np.nan,
                     'cw_among_confident_pct':100*nw/nc if nc else np.nan,
                     'cw_among_gross_pct':100*nw/ng if ng else np.nan})
    cond=pd.DataFrame(cond)
    rows=[]
    for iid in risk_ids:
        if iid not in df or iid not in SPEC_BY_ID: continue
        sign=SPEC_BY_ID[iid]['expected_sign']
        for (unit,est),g in df.groupby(['unit_label','estimator_display'],observed=False):
            sub=g[g['nominally_confident']==1]
            met=auc_metrics(sub['gross_error'],sign*finite(sub[iid]))
            if met:
                rows.append({'indicator_id':iid,'label':SPEC_BY_ID[iid]['label'],
                             'unit_label':unit,'estimator_display':est,**met})
    by=pd.DataFrame(rows)
    if by.empty: sm=by
    else:
        sm=(by.groupby(['indicator_id','label'],observed=False)
              .agg(n_conditions=('auroc','count'),median_auroc=('auroc','median'),median_auprc=('auprc','median'))
              .reset_index().sort_values('median_auroc',ascending=False))
    return cond,by,sm


def candidate_features(combined, pred, baseline_feat):
    # Produce candidate-sensitive features for M=5,10,15 and I_k horizons.
    test_ids_by_pair={(str(d),str(g)):set(ids.astype(str)) for (d,g),ids in pred.groupby(['dataset','group'])['row_id']}
    output=[]
    ikh=[]
    base_keys=baseline_feat[['dataset','group','unit_label','row_id','ap_count','rss_std','rss_range']].copy()

    for (dataset,group), ids in test_ids_by_pair.items():
        unit=f'{dataset} / {group}'
        ud=combined[(combined['dataset'].astype(str)==dataset)&(combined['group'].astype(str)==group)].copy()
        train=ud[ud['split'].astype(str).str.lower().eq('train')].copy()
        test=ud[ud['row_id'].astype(str).isin(ids)].copy()
        train_xy=m20.safe_xy(train); test_xy=m20.safe_xy(test)
        vt=np.isfinite(train_xy).all(axis=1); vq=np.isfinite(test_xy).all(axis=1)
        train=train.loc[vt].reset_index(drop=True); train_xy=train_xy[vt]
        test=test.loc[vq].reset_index(drop=True); test_xy=test_xy[vq]
        train_rss=[m20.parse_rss_json(s) for s in train['rss_json'].tolist()]
        test_rss=[m20.parse_rss_json(s) for s in test['rss_json'].tolist()]
        aps=m20.select_ap_list(train_rss,test_rss,m20.MAX_APS_PER_UNIT)
        trX,trP=m20.make_dense_matrix(train_rss,aps); teX,teP=m20.make_dense_matrix(test_rss,aps)
        trX,trP,trXY,n_templates=m20.aggregate_training_templates(trX,trP,train_xy,train['floor'].to_numpy())
        maxm=min(max(CANDIDATE_SIZES),len(trX))
        dists,idx=m20.topk_euclidean_neighbors(trX,teX,k=maxm,chunk_size=m20.DISTANCE_CHUNK_SIZE)
        unique_xy=np.unique(trXY,axis=0); tree=KDTree(unique_xy); radius=m20.adaptive_density_radius(unique_xy)
        base=base_keys[(base_keys['dataset'].astype(str)==dataset)&(base_keys['group'].astype(str)==group)].set_index('row_id')
        perM={M:[] for M in CANDIDATE_SIZES if M<=maxm}
        perK={K:[] for K in IK_HORIZONS if K<=maxm}
        for i in range(len(test)):
            rid=str(test['row_id'].iloc[i]); cand_idx=idx[i]; cand_d=dists[i]; cand_xy=trXY[cand_idx]
            for M in perM:
                pts=cand_xy[:M]; centroid=np.mean(pts,axis=0)
                spread=float(np.sqrt(np.mean(np.sum((pts-centroid)**2,axis=1))))
                diam=m20.pairwise_diameter(pts)
                cc=np.cumsum(pts,axis=0)/np.arange(1,M+1)[:,None]
                ik=float(np.max(np.linalg.norm(cc-cc[-1],axis=1)))
                minrss=float(cand_d[0]); second=float(cand_d[1]) if len(cand_d)>1 else minrss
                isolation=max(second-minrss,0)/(second+BASE_EPS)
                contrast=max(float(cand_d[M-1])-minrss,BASE_EPS)
                grad=spread/contrast
                maxj,meanj=m20.mean_jaccard(teP[i],trP[cand_idx[:M]])
                novelty=1-maxj if np.isfinite(maxj) else np.nan
                density=int(tree.query_radius(centroid.reshape(1,-1),r=radius,count_only=True)[0])
                b=base.loc[rid] if rid in base.index else None
                perM[M].append({'dataset':dataset,'group':group,'unit_label':unit,'row_id':rid,'M':M,
                    'min_rss_distance':minrss,'nearest_match_isolation':isolation,
                    'sigma_fps':spread,'D_cand':diam,'I_k':ik,'rss_gradient_proxy':grad,
                    'ap_overlap':maxj,'mean_ap_overlap':meanj,'ap_set_novelty':novelty,
                    'local_rp_density':density,
                    'ap_count':float(b['ap_count']) if b is not None else np.nan,
                    'rss_std':float(b['rss_std']) if b is not None else np.nan,
                    'rss_range':float(b['rss_range']) if b is not None else np.nan})
            for K in perK:
                pts=cand_xy[:K]; cc=np.cumsum(pts,axis=0)/np.arange(1,K+1)[:,None]
                ik=float(np.max(np.linalg.norm(cc-cc[-1],axis=1)))
                perK[K].append({'dataset':dataset,'group':group,'unit_label':unit,'row_id':rid,'k_horizon':K,'I_k':ik})
        for M,rows in perM.items():
            f=pd.DataFrame(rows)
            # Preserve nearest-match cosine from baseline because it uses the same nearest candidate.
            for unit2, ids2 in f.groupby('unit_label').groups.items():
                risk_min=robust01(f.loc[ids2,'min_rss_distance']); risk_sp=robust01(f.loc[ids2,'sigma_fps'])
                risk_d=robust01(f.loc[ids2,'D_cand']); risk_n=robust01(f.loc[ids2,'ap_set_novelty'])
                sup_signal=1-risk_min; sup_geom=1-np.nanmean(np.vstack([risk_sp,risk_d]),axis=0)
                sup_ap=robust01(f.loc[ids2,'ap_count']); sup_ov=robust01(f.loc[ids2,'ap_overlap'])
                sup_den=robust01(f.loc[ids2,'local_rp_density']); sup_iso=robust01(f.loc[ids2,'nearest_match_isolation'])
                f.loc[ids2,'SQS']=np.nanmean(np.vstack([sup_signal,sup_geom,sup_ap,sup_ov,sup_den]),axis=0)
                f.loc[ids2,'C_sigma']=sup_signal/(1+invariant_array(risk_sp))
                f.loc[ids2,'FII']=np.nanmean(np.vstack([sup_signal,sup_ap,sup_ov,sup_iso,1-risk_n]),axis=0)
            output.append(f)
        for K,rows in perK.items(): ikh.append(pd.DataFrame(rows))
        print(f'[candidate] {unit}: test={len(test)}, templates={n_templates}, APs={len(aps)}')
    return pd.concat(output,ignore_index=True),pd.concat(ikh,ignore_index=True)


def invariant_array(x):
    return np.asarray(x,dtype=float)


def evaluate_candidate_variants(pred, combined, baseline_feat, base_long, adaptive_thresholds):
    cand, ikh=candidate_features(combined,pred,baseline_feat)
    cand.to_csv(TABLE_DIR/'A5_candidate_features_by_M.csv.gz',index=False,compression='gzip')
    ikh.to_csv(TABLE_DIR/'A5_Ik_by_horizon.csv.gz',index=False,compression='gzip')
    all_by=[]; all_sm=[]; assoc_by=[]; assoc_sm=[]
    keys=['dataset','group','unit_label','row_id']
    pred_small=pred[['dataset','group','unit_label','row_id','estimator_display','error_m']].copy()
    for M,g in cand.groupby('M'):
        long=pred_small.merge(g,on=keys,how='left',validate='many_to_one')
        # Add expected but invariant nearest-rp only if needed (not in candidate-sensitive set).
        by,sm=evaluate_discrimination(long,adaptive_thresholds,CANDIDATE_SENSITIVE)
        by['M']=M; sm['M']=M; all_by.append(by); all_sm.append(sm)
        ab,asm=evaluate_association(long,CANDIDATE_SENSITIVE)
        ab['M']=M; asm['M']=M; assoc_by.append(ab); assoc_sm.append(asm)
    # I_k horizons
    ik_by=[]; ik_sm=[]; ik_ab=[]; ik_as=[]
    for K,g in ikh.groupby('k_horizon'):
        long=pred_small.merge(g,on=keys,how='left',validate='many_to_one')
        by,sm=evaluate_discrimination(long,adaptive_thresholds,['I_k'])
        by['k_horizon']=K; sm['k_horizon']=K; ik_by.append(by); ik_sm.append(sm)
        ab,asm=evaluate_association(long,['I_k'])
        ab['k_horizon']=K; asm['k_horizon']=K; ik_ab.append(ab); ik_as.append(asm)
    return (pd.concat(all_by,ignore_index=True),pd.concat(all_sm,ignore_index=True),
            pd.concat(assoc_by,ignore_index=True),pd.concat(assoc_sm,ignore_index=True),
            pd.concat(ik_by,ignore_index=True),pd.concat(ik_sm,ignore_index=True),
            pd.concat(ik_ab,ignore_index=True),pd.concat(ik_as,ignore_index=True))


def additive_constant_sensitivity(feat,long_df,adaptive_thresholds):
    results=[]
    keys=['dataset','group','unit_label','row_id']
    # reconstruct second distance and raw contrast from baseline values
    scan=feat[keys+['min_rss_distance','nearest_match_isolation','sigma_fps','rss_gradient_proxy']].copy()
    iso=finite(scan['nearest_match_isolation']).to_numpy(float); d1=finite(scan['min_rss_distance']).to_numpy(float)
    second=np.where(np.isfinite(iso)&(iso<1), (d1+iso*BASE_EPS)/(1-iso), np.nan)
    spread=finite(scan['sigma_fps']).to_numpy(float); gp=finite(scan['rss_gradient_proxy']).to_numpy(float)
    contrast=np.where(np.isfinite(gp)&(gp>0), spread/gp, BASE_EPS)
    for eps in EPS_VALUES:
        v=scan[keys].copy()
        v['nearest_match_isolation']=(second-d1)/(second+eps)
        v['rss_gradient_proxy']=spread/np.maximum(contrast,eps)
        long=long_df.drop(columns=['nearest_match_isolation','rss_gradient_proxy']).merge(v,on=keys,how='left',validate='many_to_one')
        for iid in ['nearest_match_isolation','rss_gradient_proxy']:
            _,asm=evaluate_association(long,[iid]); _,dsm=evaluate_discrimination(long,adaptive_thresholds,[iid])
            ar=float(asm['median_aligned_rho'].iloc[0]) if len(asm) else np.nan
            au=float(dsm['median_auroc'].iloc[0]) if len(dsm) else np.nan
            results.append({'constant_type':'epsilon','value':eps,'indicator_id':iid,
                            'median_aligned_rho':ar,'median_auroc':au})
    # C_sigma structural denominator constant c + normalized spread.
    scan2=feat[keys+['min_rss_distance','sigma_fps']].copy()
    scan2['sup_signal']=np.nan; scan2['risk_spread']=np.nan
    for unit,idx in scan2.groupby('unit_label',observed=False).groups.items():
        scan2.loc[idx,'sup_signal']=1-robust01(scan2.loc[idx,'min_rss_distance'])
        scan2.loc[idx,'risk_spread']=robust01(scan2.loc[idx,'sigma_fps'])
    for c in CSIGMA_CONSTANTS:
        v=scan2[keys].copy(); v['C_sigma']=scan2['sup_signal']/(c+scan2['risk_spread'])
        long=long_df.drop(columns=['C_sigma']).merge(v,on=keys,how='left',validate='many_to_one')
        _,asm=evaluate_association(long,['C_sigma']); _,dsm=evaluate_discrimination(long,adaptive_thresholds,['C_sigma'])
        results.append({'constant_type':'C_sigma denominator','value':c,'indicator_id':'C_sigma',
                        'median_aligned_rho':float(asm['median_aligned_rho'].iloc[0]),
                        'median_auroc':float(dsm['median_auroc'].iloc[0])})
    return pd.DataFrame(results)


def create_figures(rank_df, fixed_ind, conf_summary, cand_stability, ik_summary, const_summary):
    plt.rcParams.update({'font.family':'DejaVu Serif','font.size':9,'axes.linewidth':0.8,
                         'xtick.direction':'in','ytick.direction':'in','xtick.top':True,'ytick.right':True,
                         'pdf.fonttype':42,'ps.fonttype':42})
    # Figure 1: rank stability across parameter families.
    fig,ax=plt.subplots(figsize=(8.0,4.8))
    d=rank_df.copy().reset_index(drop=True)
    x=np.arange(len(d))
    ax.scatter(x,d['rank_concordance'],s=38)
    ax.axhline(0.9,linestyle='--',linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(d['label'],rotation=55,ha='right')
    ax.set_ylabel('Spearman concordance with baseline ranking')
    ax.set_ylim(0,1.04)
    ax.grid(axis='y',alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG_DIR/'fig_parameter_rank_stability_A5.png',dpi=500,bbox_inches='tight')
    fig.savefig(FIG_DIR/'fig_parameter_rank_stability_A5.pdf',bbox_inches='tight')
    plt.close(fig)

    # Figure 2: leading indicator AUROC across fixed thresholds.
    top= fixed_ind[fixed_ind['indicator_id'].isin(['SQS','nearest_rp_distance','sigma_fps','I_k','rss_gradient_proxy','D_cand'])]
    fig,ax=plt.subplots(figsize=(7.3,4.6))
    for iid,g in top.groupby('indicator_id'):
        label=SPEC_BY_ID[iid]['label'] if iid in SPEC_BY_ID else iid
        ax.plot(g['fixed_threshold_m'],g['median_auroc'],marker='o',label=label)
    ax.set_xlabel('Fixed gross-error threshold (m)')
    ax.set_ylabel('Median AUROC')
    ax.set_xticks(FIXED_THRESHOLDS)
    ax.grid(axis='y',alpha=0.25)
    ax.legend(ncol=2,frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR/'fig_fixed_threshold_sensitivity_A5.png',dpi=500,bbox_inches='tight')
    fig.savefig(FIG_DIR/'fig_fixed_threshold_sensitivity_A5.pdf',bbox_inches='tight')
    plt.close(fig)

    # Figure 3: confidence quantile sensitivity.
    fig,ax=plt.subplots(figsize=(6.8,4.3))
    for scheme,g in conf_summary.groupby('scheme'):
        ax.plot(g['confidence_quantile'],g['median_cw_among_confident_pct'],marker='o',label=scheme)
    ax.set_xlabel('Nominal-confidence quantile')
    ax.set_ylabel('Median confidently wrong among confident scans (%)')
    ax.set_xticks(CONFIDENCE_QUANTILES)
    ax.grid(axis='y',alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR/'fig_confidence_quantile_sensitivity_A5.png',dpi=500,bbox_inches='tight')
    fig.savefig(FIG_DIR/'fig_confidence_quantile_sensitivity_A5.pdf',bbox_inches='tight')
    plt.close(fig)


def main():
    pred,feat,combined,long_df=load_long()
    print('[data]',pred.shape,feat.shape,combined.shape,long_df.shape)

    # Baselines
    base_adapt=thresholds_adaptive(long_df,BASE_Q,BASE_LAMBDA)
    _,base_adapt_sm=evaluate_discrimination(long_df,base_adapt)
    base_fixed=thresholds_fixed(long_df,BASE_FIXED)
    _,base_fixed_sm=evaluate_discrimination(long_df,base_fixed)

    # Adaptive grid
    adaptive_grid=[]; adaptive_by=[]; adaptive_sm=[]
    for q in ADAPTIVE_QUANTILES:
        for lam in ADAPTIVE_MULTIPLIERS:
            th=thresholds_adaptive(long_df,q,lam)
            by,sm=evaluate_discrimination(long_df,th)
            rc=rank_concordance(sm,base_adapt_sm); to=top_overlap(sm,base_adapt_sm)
            sq=sm[sm['indicator_id']=='SQS']
            adaptive_grid.append({'tail_quantile':q,'multiplier':lam,'median_threshold_m':th['threshold_m'].median(),
                                  'median_prevalence_pct':100*th['prevalence'].median(),
                                  'rank_concordance':rc,'top6_overlap':to,
                                  'SQS_median_auroc':float(sq['median_auroc'].iloc[0]),
                                  'SQS_median_auprc':float(sq['median_auprc'].iloc[0])})
            by['tail_quantile']=q;by['multiplier']=lam;sm['tail_quantile']=q;sm['multiplier']=lam
            adaptive_by.append(by);adaptive_sm.append(sm)
    adaptive_grid=pd.DataFrame(adaptive_grid);adaptive_by=pd.concat(adaptive_by,ignore_index=True);adaptive_sm=pd.concat(adaptive_sm,ignore_index=True)

    # Fixed grid
    fixed_grid=[];fixed_by=[];fixed_sm=[]
    for t in FIXED_THRESHOLDS:
        th=thresholds_fixed(long_df,t);by,sm=evaluate_discrimination(long_df,th)
        rc=rank_concordance(sm,base_fixed_sm);to=top_overlap(sm,base_fixed_sm)
        sq=sm[sm['indicator_id']=='SQS']
        fixed_grid.append({'fixed_threshold_m':t,'median_prevalence_pct':100*th['prevalence'].median(),
                           'rank_concordance':rc,'top6_overlap':to,
                           'SQS_median_auroc':float(sq['median_auroc'].iloc[0]),
                           'SQS_median_auprc':float(sq['median_auprc'].iloc[0])})
        by['fixed_threshold_m']=t;sm['fixed_threshold_m']=t;fixed_by.append(by);fixed_sm.append(sm)
    fixed_grid=pd.DataFrame(fixed_grid);fixed_by=pd.concat(fixed_by,ignore_index=True);fixed_sm=pd.concat(fixed_sm,ignore_index=True)

    # Confidence quantile sensitivity under both primary adaptive and fixed 7 m schemes.
    conf_scan=build_confidence_scan(feat)
    conf_rows=[];conf_by=[];conf_sm=[]
    schemes=[('Adaptive',base_adapt),('Fixed 7 m',base_fixed)]
    baseline_conf_summaries={}
    for scheme,th in schemes:
        for q in CONFIDENCE_QUANTILES:
            cond,by,sm=evaluate_confidence_quantile(long_df,conf_scan,q,th)
            if q==BASE_CONF_Q: baseline_conf_summaries[scheme]=sm
            conf_rows.append({'scheme':scheme,'confidence_quantile':q,
                              'median_confident_pct':100*(1-q),
                              'median_cw_all_pct':cond['cw_all_pct'].median(),
                              'median_cw_among_confident_pct':cond['cw_among_confident_pct'].median(),
                              'median_cw_among_gross_pct':cond['cw_among_gross_pct'].median()})
            by['scheme']=scheme;by['confidence_quantile']=q;sm['scheme']=scheme;sm['confidence_quantile']=q
            conf_by.append(by);conf_sm.append(sm)
    conf_summary=pd.DataFrame(conf_rows);conf_by=pd.concat(conf_by,ignore_index=True);conf_sm=pd.concat(conf_sm,ignore_index=True)
    # add ranking concordance by scheme
    rcvals=[]
    for (scheme,q),g in conf_sm.groupby(['scheme','confidence_quantile']):
        rc=rank_concordance(g,baseline_conf_summaries[scheme]);to=top_overlap(g,baseline_conf_summaries[scheme])
        rcvals.append({'scheme':scheme,'confidence_quantile':q,'risk_rank_concordance':rc,'top6_overlap':to})
    conf_summary=conf_summary.merge(pd.DataFrame(rcvals),on=['scheme','confidence_quantile'])

    # Candidate M and I_k horizon sensitivity
    (cand_by,cand_sm,cand_assoc_by,cand_assoc_sm,ik_by,ik_sm,ik_assoc_by,ik_assoc_sm)=evaluate_candidate_variants(
        pred,combined,feat,long_df,base_adapt)
    base_cand=cand_sm[cand_sm['M']==BASE_M]
    base_cand_assoc=cand_assoc_sm[cand_assoc_sm['M']==BASE_M]
    cand_stability=[]
    for M,g in cand_sm.groupby('M'):
        ag=cand_assoc_sm[cand_assoc_sm['M']==M]
        cand_stability.append({'M':M,'auroc_rank_concordance':rank_concordance(g,base_cand),
                               'association_rank_concordance':rank_concordance(
                                   ag.rename(columns={'median_aligned_rho':'median_auroc'}),
                                   base_cand_assoc.rename(columns={'median_aligned_rho':'median_auroc'})),
                               'top6_overlap':top_overlap(g,base_cand)})
    cand_stability=pd.DataFrame(cand_stability)

    # Additive constants
    const_summary=additive_constant_sensitivity(feat,long_df,base_adapt)

    # Consolidated rank-stability entries for the main figure.
    rank_rows=[]
    for _,r in adaptive_grid.iterrows():
        if r['tail_quantile']==BASE_Q and r['multiplier']==BASE_LAMBDA: continue
        rank_rows.append({'family':'Adaptive rule','label':f"A{int(r['tail_quantile']*100)}-{r['multiplier']:g}",
                          'rank_concordance':r['rank_concordance']})
    for _,r in fixed_grid.iterrows():
        if r['fixed_threshold_m']==BASE_FIXED: continue
        rank_rows.append({'family':'Fixed threshold','label':f"F{r['fixed_threshold_m']:g}m",'rank_concordance':r['rank_concordance']})
    for _,r in conf_summary[conf_summary['scheme']=='Adaptive'].iterrows():
        if r['confidence_quantile']==BASE_CONF_Q: continue
        rank_rows.append({'family':'Confidence cutoff','label':f"C{int(r['confidence_quantile']*100)}",
                          'rank_concordance':r['risk_rank_concordance']})
    for _,r in cand_stability.iterrows():
        if r['M']==BASE_M: continue
        rank_rows.append({'family':'Candidate size','label':f"M{int(r['M'])}",
                          'rank_concordance':r['auroc_rank_concordance']})
    rank_df=pd.DataFrame(rank_rows)

    # Save tables.
    adaptive_grid.to_csv(TABLE_DIR/'A5_adaptive_rule_summary.csv',index=False)
    adaptive_by.to_csv(TABLE_DIR/'A5_adaptive_rule_by_condition.csv',index=False)
    adaptive_sm.to_csv(TABLE_DIR/'A5_adaptive_rule_indicator_summary.csv',index=False)
    fixed_grid.to_csv(TABLE_DIR/'A5_fixed_threshold_summary.csv',index=False)
    fixed_by.to_csv(TABLE_DIR/'A5_fixed_threshold_by_condition.csv',index=False)
    fixed_sm.to_csv(TABLE_DIR/'A5_fixed_threshold_indicator_summary.csv',index=False)
    conf_summary.to_csv(TABLE_DIR/'A5_confidence_quantile_summary.csv',index=False)
    conf_by.to_csv(TABLE_DIR/'A5_confidence_quantile_by_condition.csv',index=False)
    conf_sm.to_csv(TABLE_DIR/'A5_confidence_quantile_indicator_summary.csv',index=False)
    cand_by.to_csv(TABLE_DIR/'A5_candidate_M_by_condition.csv',index=False)
    cand_sm.to_csv(TABLE_DIR/'A5_candidate_M_indicator_summary.csv',index=False)
    cand_assoc_by.to_csv(TABLE_DIR/'A5_candidate_M_association_by_condition.csv',index=False)
    cand_assoc_sm.to_csv(TABLE_DIR/'A5_candidate_M_association_summary.csv',index=False)
    cand_stability.to_csv(TABLE_DIR/'A5_candidate_M_stability_summary.csv',index=False)
    ik_by.to_csv(TABLE_DIR/'A5_Ik_horizon_by_condition.csv',index=False)
    ik_sm.to_csv(TABLE_DIR/'A5_Ik_horizon_discrimination_summary.csv',index=False)
    ik_assoc_by.to_csv(TABLE_DIR/'A5_Ik_horizon_association_by_condition.csv',index=False)
    ik_assoc_sm.to_csv(TABLE_DIR/'A5_Ik_horizon_association_summary.csv',index=False)
    const_summary.to_csv(TABLE_DIR/'A5_additive_constant_summary.csv',index=False)
    rank_df.to_csv(TABLE_DIR/'A5_rank_stability_summary.csv',index=False)

    create_figures(rank_df,fixed_sm,conf_summary,cand_stability,ik_sm,const_summary)

    # Findings JSON/TXT
    findings={
      'adaptive_min_rank_concordance':float(adaptive_grid['rank_concordance'].min()),
      'adaptive_min_top6_overlap':float(adaptive_grid['top6_overlap'].min()),
      'adaptive_sqs_auroc_range':[float(adaptive_grid['SQS_median_auroc'].min()),float(adaptive_grid['SQS_median_auroc'].max())],
      'fixed_min_rank_concordance':float(fixed_grid['rank_concordance'].min()),
      'fixed_sqs_auroc_range':[float(fixed_grid['SQS_median_auroc'].min()),float(fixed_grid['SQS_median_auroc'].max())],
      'confidence_min_rank_concordance':float(conf_summary['risk_rank_concordance'].min()),
      'confidence_cw_range':[float(conf_summary['median_cw_among_confident_pct'].min()),float(conf_summary['median_cw_among_confident_pct'].max())],
      'candidate_min_auroc_rank_concordance':float(cand_stability['auroc_rank_concordance'].min()),
      'candidate_min_assoc_rank_concordance':float(cand_stability['association_rank_concordance'].min()),
    }
    (OUT/'A5_findings.json').write_text(json.dumps(findings,indent=2))
    print(json.dumps(findings,indent=2))
    print('\nAdaptive grid\n',adaptive_grid.to_string(index=False))
    print('\nFixed grid\n',fixed_grid.to_string(index=False))
    print('\nConfidence\n',conf_summary.to_string(index=False))
    print('\nCandidate stability\n',cand_stability.to_string(index=False))
    print('\nI_k\n',ik_sm.to_string(index=False))
    print('\nConstants\n',const_summary.to_string(index=False))

if __name__=='__main__':
    main()
