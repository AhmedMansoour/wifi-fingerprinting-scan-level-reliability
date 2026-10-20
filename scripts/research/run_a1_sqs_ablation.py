from research_paths import REPO, WORKSPACE, output_dir
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, average_precision_score
import matplotlib.pyplot as plt

ROOT = WORKSPACE
OUT = output_dir("A1")
OUT.mkdir(parents=True, exist_ok=True)

FEATURE_PATH = ROOT/'data/processed/scan_level_reliability_indicator_features.csv.gz'
PRED_PATH = ROOT/'data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz'

ESTIMATOR_ORDER = [
    'KNN','WKNN','Random Forest','Extra Trees','Gradient Boosting',
    'CatBoost','Transformer','Residual CNN'
]


def robust01(x):
    arr = np.asarray(x, dtype=float)
    out = np.full(arr.shape, np.nan, dtype=float)
    mask = np.isfinite(arr)
    if mask.sum() == 0:
        return out
    vals = arr[mask]
    lo, hi = np.percentile(vals, [5, 95])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        out[mask] = 0.5
        return out
    out[mask] = np.clip((vals - lo)/(hi-lo), 0, 1)
    return out


def metric_auc(y, score):
    tmp = pd.DataFrame({'y': y, 's': score}).replace([np.inf,-np.inf], np.nan).dropna()
    if len(tmp) < 20:
        return None
    yy = tmp.y.astype(int).to_numpy()
    ss = tmp.s.to_numpy(float)
    npos = int(yy.sum()); nneg = len(yy)-npos
    if npos < 3 or nneg < 3:
        return None
    return {
        'n_valid_scans': len(yy),
        'n_gross_error': npos,
        'prevalence': npos/len(yy),
        'auroc': roc_auc_score(yy, ss),
        'auprc': average_precision_score(yy, ss),
    }

# Load
f = pd.read_csv(FEATURE_PATH, dtype={'row_id':str}, low_memory=False)
p = pd.read_csv(PRED_PATH, dtype={'row_id':str}, low_memory=False)
if 'unit_label' not in p.columns:
    p['unit_label'] = p['dataset'].astype(str)+' / '+p['group'].astype(str)
p = p[p['estimator_display'].isin(ESTIMATOR_ORDER)].copy()
p['error_m'] = pd.to_numeric(p['error_m'], errors='coerce')
p = p[np.isfinite(p['error_m'])].copy()

# Reconstruct supports separately within each radio-map unit.
frames=[]
for unit,g in f.groupby('unit_label', sort=False):
    g=g.copy()
    r_min=robust01(g['min_rss_distance'])
    r_spread=robust01(g['sigma_fps'])
    r_diam=robust01(g['D_cand'])
    s_signal=1-r_min
    s_spread=1-r_spread
    s_diam=1-r_diam
    s_geometry=(s_spread+s_diam)/2
    s_ap=robust01(g['ap_count'])
    s_overlap=robust01(g['ap_overlap'])
    s_density=robust01(g['local_rp_density'])
    g['S_signal']=s_signal
    g['S_spread']=s_spread
    g['S_diameter']=s_diam
    g['S_geometry']=s_geometry
    g['S_ap_count']=s_ap
    g['S_overlap']=s_overlap
    g['S_density']=s_density
    g['SQS_reconstructed']=np.nanmean(np.vstack([s_signal,s_geometry,s_ap,s_overlap,s_density]),axis=0)
    # conceptual leave-one-component-out, re-average remaining 4
    comps={'signal':s_signal,'geometry':s_geometry,'ap_count':s_ap,'overlap':s_overlap,'density':s_density}
    for omit in comps:
        rem=[v for k,v in comps.items() if k!=omit]
        g[f'SQS_without_{omit}']=np.nanmean(np.vstack(rem),axis=0)
    # raw-variable leave-one-out using original effective weights, renormalized.
    raw={'signal':(s_signal,1.0),'spread':(s_spread,0.5),'diameter':(s_diam,0.5),
         'ap_count':(s_ap,1.0),'overlap':(s_overlap,1.0),'density':(s_density,1.0)}
    for omit in raw:
        num=np.zeros(len(g)); den=np.zeros(len(g))
        for k,(v,w) in raw.items():
            if k==omit: continue
            valid=np.isfinite(v)
            num[valid]+=w*v[valid]
            den[valid]+=w
        out=np.full(len(g),np.nan)
        ok=den>0; out[ok]=num[ok]/den[ok]
        g[f'SQS_raw_without_{omit}']=out
    frames.append(g)
f2=pd.concat(frames,ignore_index=True)

# Exact reconstruction audit
absdiff=np.abs(f2['SQS_reconstructed']-f2['SQS'])
audit=pd.DataFrame({
    'n_scans':[len(f2)],
    'max_abs_difference':[absdiff.max()],
    'mean_abs_difference':[absdiff.mean()],
    'n_difference_gt_1e_12':[(absdiff>1e-12).sum()],
    'n_units':[f2.unit_label.nunique()],
})
audit.to_csv(OUT/'A1_SQS_reconstruction_audit.csv',index=False)

# Add percentile parameters per unit for transparency
pct_rows=[]
for unit,g in f.groupby('unit_label',sort=False):
    for var in ['min_rss_distance','sigma_fps','D_cand','ap_count','ap_overlap','local_rp_density']:
        vals=pd.to_numeric(g[var],errors='coerce').dropna().to_numpy(float)
        lo,hi=np.percentile(vals,[5,95])
        pct_rows.append({'unit_label':unit,'variable':var,'q05':lo,'q95':hi,'n_scans':len(vals)})
pd.DataFrame(pct_rows).to_csv(OUT/'A1_SQS_unit_percentile_parameters.csv',index=False)

# Variant metadata
variants = [
    ('SQS_reconstructed','Full SQS','Full'),
    ('S_signal','Signal support only','Component'),
    ('S_geometry','Candidate-geometry support only','Component'),
    ('S_ap_count','AP-count support only','Component'),
    ('S_overlap','AP-overlap support only','Component'),
    ('S_density','Local-density support only','Component'),
    ('S_spread','Candidate-spread support only','Raw component'),
    ('S_diameter','Candidate-diameter support only','Raw component'),
    ('SQS_without_signal','SQS without signal support','Conceptual ablation'),
    ('SQS_without_geometry','SQS without candidate geometry','Conceptual ablation'),
    ('SQS_without_ap_count','SQS without AP count','Conceptual ablation'),
    ('SQS_without_overlap','SQS without AP overlap','Conceptual ablation'),
    ('SQS_without_density','SQS without local density','Conceptual ablation'),
    ('SQS_raw_without_signal','SQS without min-RSS support','Raw ablation'),
    ('SQS_raw_without_spread','SQS without candidate spread','Raw ablation'),
    ('SQS_raw_without_diameter','SQS without candidate diameter','Raw ablation'),
    ('SQS_raw_without_ap_count','SQS without AP count (raw)','Raw ablation'),
    ('SQS_raw_without_overlap','SQS without AP overlap (raw)','Raw ablation'),
    ('SQS_raw_without_density','SQS without local density (raw)','Raw ablation'),
]
meta=pd.DataFrame(variants,columns=['variant_id','label','variant_type'])
meta.to_csv(OUT/'A1_SQS_variant_dictionary.csv',index=False)

# Merge into long table
keep=['dataset','group','unit_label','row_id']+[v[0] for v in variants]
long=p[['dataset','group','unit_label','row_id','estimator_display','error_m']].merge(
    f2[keep],on=['dataset','group','unit_label','row_id'],how='left',validate='many_to_one')

# Thresholds
thr=[]
for (unit,est),g in long.groupby(['unit_label','estimator_display'],sort=False):
    e=g.error_m.to_numpy(float)
    q25,q75=np.percentile(e,[25,75]); tau=q75+1.5*(q75-q25)
    thr.append({'unit_label':unit,'estimator_display':est,'adaptive_threshold_m':tau})
thr=pd.DataFrame(thr)
long=long.merge(thr,on=['unit_label','estimator_display'],how='left')
long['gross_adaptive']=(long.error_m>long.adaptive_threshold_m).astype(int)
long['gross_fixed_7m']=(long.error_m>7.0).astype(int)

assoc_rows=[]; adapt_rows=[]; fixed_rows=[]
for vid,label,vtype in variants:
    for (unit,est),g in long.groupby(['unit_label','estimator_display'],sort=False):
        tmp=g[[vid,'error_m']].replace([np.inf,-np.inf],np.nan).dropna()
        if len(tmp)>=20 and tmp[vid].nunique()>=3 and tmp.error_m.nunique()>=3:
            rho=spearmanr(tmp[vid],tmp.error_m).statistic
            assoc_rows.append({'variant_id':vid,'label':label,'variant_type':vtype,
                               'unit_label':unit,'estimator_display':est,'n_valid_scans':len(tmp),
                               'rho':rho,'aligned_rho':-rho})
        m=metric_auc(g.gross_adaptive,-g[vid])
        if m:
            adapt_rows.append({'variant_id':vid,'label':label,'variant_type':vtype,
                               'unit_label':unit,'estimator_display':est,**m})
        m=metric_auc(g.gross_fixed_7m,-g[vid])
        if m:
            fixed_rows.append({'variant_id':vid,'label':label,'variant_type':vtype,
                               'unit_label':unit,'estimator_display':est,**m})

assoc=pd.DataFrame(assoc_rows); adapt=pd.DataFrame(adapt_rows); fixed=pd.DataFrame(fixed_rows)
assoc.to_csv(OUT/'A1_SQS_association_by_condition.csv',index=False)
adapt.to_csv(OUT/'A1_SQS_adaptive_discrimination_by_condition.csv',index=False)
fixed.to_csv(OUT/'A1_SQS_fixed7m_discrimination_by_condition.csv',index=False)


def summarize_assoc(df):
    return (df.groupby(['variant_id','label','variant_type'],as_index=False)
            .agg(n_conditions=('aligned_rho','count'),
                 median_aligned_rho=('aligned_rho','median'),
                 q25_aligned_rho=('aligned_rho',lambda x:np.percentile(x,25)),
                 q75_aligned_rho=('aligned_rho',lambda x:np.percentile(x,75)),
                 direction_consistency_pct=('aligned_rho',lambda x:100*np.mean(np.asarray(x)>0))))

def summarize_auc(df):
    return (df.groupby(['variant_id','label','variant_type'],as_index=False)
            .agg(n_conditions=('auroc','count'),
                 median_auroc=('auroc','median'),
                 q25_auroc=('auroc',lambda x:np.percentile(x,25)),
                 q75_auroc=('auroc',lambda x:np.percentile(x,75)),
                 median_auprc=('auprc','median'),
                 q25_auprc=('auprc',lambda x:np.percentile(x,25)),
                 q75_auprc=('auprc',lambda x:np.percentile(x,75))))

sa=summarize_assoc(assoc); sad=summarize_auc(adapt); sfx=summarize_auc(fixed)
full_a=float(sa.loc[sa.variant_id=='SQS_reconstructed','median_aligned_rho'].iloc[0])
full_ad_roc=float(sad.loc[sad.variant_id=='SQS_reconstructed','median_auroc'].iloc[0])
full_ad_pr=float(sad.loc[sad.variant_id=='SQS_reconstructed','median_auprc'].iloc[0])
full_fx_roc=float(sfx.loc[sfx.variant_id=='SQS_reconstructed','median_auroc'].iloc[0])
full_fx_pr=float(sfx.loc[sfx.variant_id=='SQS_reconstructed','median_auprc'].iloc[0])
sa['delta_vs_full_association']=sa.median_aligned_rho-full_a
sad['delta_vs_full_auroc']=sad.median_auroc-full_ad_roc
sad['delta_vs_full_auprc']=sad.median_auprc-full_ad_pr
sfx['delta_vs_full_auroc']=sfx.median_auroc-full_fx_roc
sfx['delta_vs_full_auprc']=sfx.median_auprc-full_fx_pr
sa.to_csv(OUT/'A1_SQS_association_summary.csv',index=False)
sad.to_csv(OUT/'A1_SQS_adaptive_discrimination_summary.csv',index=False)
sfx.to_csv(OUT/'A1_SQS_fixed7m_discrimination_summary.csv',index=False)

combined=sa.merge(sad,on=['variant_id','label','variant_type'],suffixes=('_assoc','_adaptive')).merge(
    sfx,on=['variant_id','label','variant_type'],suffixes=('','_fixed7m'))
combined.to_csv(OUT/'A1_SQS_complete_summary.csv',index=False)

# Main concise table: full, five components, five conceptual ablations
main_ids=['SQS_reconstructed','S_signal','S_geometry','S_ap_count','S_overlap','S_density',
          'SQS_without_signal','SQS_without_geometry','SQS_without_ap_count','SQS_without_overlap','SQS_without_density']
main=combined[combined.variant_id.isin(main_ids)].copy()
order={k:i for i,k in enumerate(main_ids)}
main['order']=main.variant_id.map(order); main=main.sort_values('order').drop(columns='order')
main.to_csv(OUT/'A1_SQS_main_component_ablation_summary.csv',index=False)

# Figure
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':8,'axes.linewidth':0.7,'xtick.direction':'in','ytick.direction':'in'})
labels=main.label.tolist(); y=np.arange(len(main))
fig,axs=plt.subplots(1,3,figsize=(11.2,5.4),sharey=True)
metrics=[('median_aligned_rho','Aligned Spearman association'),('median_auroc','Adaptive AUROC'),('median_auprc','Adaptive AUPRC')]
# resolve duplicate col names from merges: inspect dynamically
cols=list(main.columns)
assoc_col='median_aligned_rho'
# adaptive columns keep median_auroc and median_auprc; fixed ones get suffix _fixed7m
for ax,(col,xlab) in zip(axs,metrics):
    vals=main[col].to_numpy(float)
    bars=ax.barh(y,vals,edgecolor='black',linewidth=.35)
    for i,b in enumerate(bars):
        if main.iloc[i].variant_type=='Full': b.set_alpha(1.0)
        elif main.iloc[i].variant_type=='Component': b.set_alpha(.72)
        else: b.set_alpha(.45)
    ax.set_yticks(y)
    if ax is axs[0]:
        ax.set_yticklabels(labels)
    else:
        ax.tick_params(labelleft=False)
    ax.invert_yaxis(); ax.set_xlabel(xlab); ax.grid(axis='x',alpha=.25,linewidth=.4)
    ax.tick_params(top=True,right=True)
    for i,v in enumerate(vals): ax.text(v, i, f' {v:.3f}', va='center', fontsize=6.8)
axs[0].set_title('(a) Error association',loc='left')
axs[1].set_title('(b) Adaptive gross-error AUROC',loc='left')
axs[2].set_title('(c) Adaptive gross-error AUPRC',loc='left')
fig.tight_layout()
fig.savefig(OUT/'A1_SQS_component_ablation.pdf',bbox_inches='tight',pad_inches=.03)
fig.savefig(OUT/'A1_SQS_component_ablation.png',dpi=500,bbox_inches='tight',pad_inches=.03)
plt.close(fig)

# Human-readable findings
full=main[main.variant_id=='SQS_reconstructed'].iloc[0]
abl=main[main.variant_type=='Conceptual ablation'].copy()
comp=main[main.variant_type=='Component'].copy()
lines=[]
lines.append('A1 SQS COMPONENT AND ABLATION FINDINGS')
lines.append('')
lines.append(f"Exact reconstruction max absolute difference: {absdiff.max():.3e}")
lines.append(f"Full SQS: median aligned Spearman={full['median_aligned_rho']:.3f}; adaptive AUROC={full['median_auroc']:.3f}; adaptive AUPRC={full['median_auprc']:.3f}; fixed-7m AUROC={full['median_auroc_fixed7m']:.3f}; fixed-7m AUPRC={full['median_auprc_fixed7m']:.3f}.")
lines.append('')
lines.append('Component-only ranking by median aligned Spearman:')
for _,r in comp.sort_values('median_aligned_rho',ascending=False).iterrows():
    lines.append(f"- {r['label']}: rho={r['median_aligned_rho']:.3f}, adaptive AUROC={r['median_auroc']:.3f}, adaptive AUPRC={r['median_auprc']:.3f}")
lines.append('')
lines.append('Conceptual ablations (negative delta means performance below full SQS):')
for _,r in abl.sort_values('delta_vs_full_association').iterrows():
    lines.append(f"- {r['label']}: Δrho={r['delta_vs_full_association']:+.3f}, Δadaptive AUROC={r['delta_vs_full_auroc']:+.3f}, Δadaptive AUPRC={r['delta_vs_full_auprc']:+.3f}")
(OUT/'A1_SQS_findings.txt').write_text('\n'.join(lines),encoding='utf-8')

print(audit.to_string(index=False))
print('\nMAIN SUMMARY')
print(main[['label','variant_type','median_aligned_rho','median_auroc','median_auprc','median_auroc_fixed7m','median_auprc_fixed7m']].to_string(index=False))
print('\nOutputs:',OUT)
