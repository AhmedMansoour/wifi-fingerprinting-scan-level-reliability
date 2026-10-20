from research_paths import REPO, WORKSPACE, output_dir
from pathlib import Path
import numpy as np, pandas as pd, warnings
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.neighbors import KDTree
import matplotlib.pyplot as plt

ROOT=WORKSPACE; OUT=output_dir("A4"); T=OUT/'tables'; F=OUT/'figures'
FEATURE=ROOT/'data/processed/scan_level_reliability_indicator_features.csv.gz'
PRED=ROOT/'data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz'
COMBINED=ROOT/'data/interim/datasets_combined_all/combined_all_datasets.csv'
SCAN=T/'A4_floor_predictions_by_scan.csv'
SPECS=(WORKSPACE / "reference/A2" / 'A2_core_indicator_dictionary_18.csv')
A3ASSOC=(REPO / "reference/approved/revision_summaries/A3" / 'A3_indicator_error_association_summary_ci_bh.csv')
A3ADP=(REPO / "reference/approved/revision_summaries/A3" / 'A3_gross_error_adaptive_summary_ci.csv')
K_VALUES=[3,5,10]
EST_ORDER=['KNN','WKNN','Random Forest','Extra Trees','Gradient Boosting','CatBoost','Transformer','Residual CNN']

def ensure(df):
    df=df.copy()
    if 'unit_label' not in df:
        if 'unit' in df: df['unit_label']=df.unit.astype(str)
        else: df['unit_label']=df.dataset.astype(str)+' / '+df.group.astype(str)
    return df

def add_nrp(long,comb):
    long=long.copy(); long['nearest_rp_distance']=np.nan
    for unit,ids in long.groupby('unit_label').groups.items():
        p=long.loc[ids]; ds=str(p.dataset.iloc[0]); gr=str(p.group.iloc[0])
        tr=comb[(comb.dataset.astype(str)==ds)&(comb.group.astype(str)==gr)&comb.split.astype(str).str.lower().eq('train')]
        xy=tr[['x','y']].apply(pd.to_numeric,errors='coerce').to_numpy(float); xy=xy[np.isfinite(xy).all(1)]
        if not len(xy): continue
        tree=KDTree(np.unique(xy,axis=0)); q=long.loc[ids,['x_pred','y_pred']].apply(pd.to_numeric,errors='coerce').to_numpy(float)
        v=np.isfinite(q).all(1); d=np.full(len(q),np.nan)
        if v.any(): d[v]=tree.query(q[v],k=1)[0][:,0]
        long.loc[ids,'nearest_rp_distance']=d
    return long

print('[A4 phase2] load')
feat=ensure(pd.read_csv(FEATURE,dtype={'row_id':str},low_memory=False)); pred=ensure(pd.read_csv(PRED,dtype={'row_id':str},low_memory=False)); scan=pd.read_csv(SCAN,dtype={'row_id':str}); specs=pd.read_csv(SPECS)
pred=pred[pred.estimator_display.isin(EST_ORDER)]
comb=pd.read_csv(COMBINED,usecols=['dataset','group','split','x','y'],low_memory=False)
long=pred[['dataset','group','unit_label','row_id','estimator_display','error_m','x_pred','y_pred']].merge(feat.drop(columns=['x_true','y_true'],errors='ignore'),on=['dataset','group','unit_label','row_id'],how='left',validate='many_to_one').merge(scan,on=['dataset','group','unit_label','row_id'],how='inner',validate='many_to_one')
long=add_nrp(long,comb)
print('[A4 phase2] long',long.shape)

assoc=[]; adp=[]
for k in K_VALUES:
    fc=f'floor_correct_k{k}'
    for (unit,est),g0 in long.groupby(['unit_label','estimator_display'],sort=False):
        g=g0[g0[fc].astype(bool)]
        if len(g)<20: continue
        e=pd.to_numeric(g.error_m,errors='coerce').to_numpy(float)
        q1,q3=np.nanquantile(e,[.25,.75]); thr=q3+1.5*(q3-q1); y=(e>thr).astype(int)
        for s in specs.itertuples(index=False):
            iid=s.indicator_id
            if iid not in g.columns: continue
            x=pd.to_numeric(g[iid],errors='coerce').to_numpy(float); v=np.isfinite(x)&np.isfinite(e)
            if v.sum()>=20 and np.unique(x[v]).size>1 and np.unique(e[v]).size>1:
                rho=pd.Series(x[v]).rank(method='average').corr(pd.Series(e[v]).rank(method='average'))
                if np.isfinite(rho): assoc.append([k,unit,est,iid,s.label,s.family,int(v.sum()),int(s.expected_sign)*float(rho)])
            if v.sum()>=20 and np.unique(y[v]).size==2 and y[v].sum()>=3:
                score=int(s.expected_sign)*x[v]
                adp.append([k,unit,est,iid,s.label,s.family,int(v.sum()),float(y[v].mean()),float(roc_auc_score(y[v],score)),float(average_precision_score(y[v],score))])
    print('[A4 phase2] completed K',k)
assoc=pd.DataFrame(assoc,columns=['k','unit_label','estimator_display','indicator_id','label','family','n','aligned_rho'])
adp=pd.DataFrame(adp,columns=['k','unit_label','estimator_display','indicator_id','label','family','n','prevalence','auroc','auprc'])
assoc.to_csv(T/'A4_floor_correct_association_by_condition.csv',index=False); adp.to_csv(T/'A4_floor_correct_adaptive_discrimination_by_condition.csv',index=False)
assoc_sum=assoc.groupby(['k','indicator_id','label','family'],as_index=False).agg(n_conditions=('aligned_rho','size'),median_aligned_rho=('aligned_rho','median'),direction_consistency_pct=('aligned_rho',lambda x:100*(x>0).mean()))
adp_sum=adp.groupby(['k','indicator_id','label','family'],as_index=False).agg(n_conditions=('auroc','size'),median_auroc=('auroc','median'),median_auprc=('auprc','median'),median_prevalence=('prevalence','median'))
assoc_sum.to_csv(T/'A4_floor_correct_association_summary.csv',index=False); adp_sum.to_csv(T/'A4_floor_correct_adaptive_discrimination_summary.csv',index=False)
a3a=pd.read_csv(A3ASSOC); a3d=pd.read_csv(A3ADP)
comp=assoc_sum.merge(a3a[['indicator_id','median_aligned_rho']],on='indicator_id',how='left',suffixes=('_floor_correct','_all'))
comp['delta_aligned_rho']=comp.median_aligned_rho_floor_correct-comp.median_aligned_rho_all
comp=comp.merge(adp_sum[['k','indicator_id','median_auroc','median_auprc']],on=['k','indicator_id'],how='left')
comp=comp.merge(a3d[['indicator_id','median_auroc','median_auprc']],on='indicator_id',how='left',suffixes=('_floor_correct','_all'))
comp['delta_auroc']=comp.median_auroc_floor_correct-comp.median_auroc_all; comp['delta_auprc']=comp.median_auprc_floor_correct-comp.median_auprc_all
comp.to_csv(T/'A4_floor_correct_vs_complete_comparison.csv',index=False)

# Figures
plt.rcParams.update({'figure.dpi':130,'savefig.dpi':500,'font.family':'DejaVu Serif','font.size':8,'axes.titlesize':9,'axes.labelsize':8.3,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'pdf.fonttype':42,'ps.fonttype':42})
hit=pd.read_csv(T/'A4_floor_hit_rate_by_unit.csv'); order=hit[hit.k.eq(5)].sort_values('floor_hit_rate',ascending=False).unit_label.tolist(); short=dict(zip(hit.unit_label,hit.unit_short))
fig,ax=plt.subplots(figsize=(7.2,4.4)); x=np.arange(len(order)); off={3:-.18,5:0,10:.18}; marks={3:'o',5:'s',10:'^'}
for k in K_VALUES:
    gg=hit[hit.k.eq(k)].set_index('unit_label').reindex(order); ax.plot(x+off[k],100*gg.floor_hit_rate,marker=marks[k],linestyle='none',label=f'K={k}',markersize=5)
ax.set_xticks(x); ax.set_xticklabels([short[u] for u in order],rotation=28,ha='right'); ax.set_ylabel('Floor-hit rate (%)'); ax.set_ylim(90,100.5); ax.grid(axis='y',alpha=.35); ax.tick_params(direction='in',top=True,right=True); ax.legend(frameon=False,ncol=3,loc='lower left'); fig.tight_layout(); fig.savefig(F/'fig_floor_hit_rate_k_sensitivity.png',bbox_inches='tight',pad_inches=.03); fig.savefig(F/'fig_floor_hit_rate_k_sensitivity.pdf',bbox_inches='tight',pad_inches=.03); plt.close(fig)
err=pd.read_csv(T/'A4_horizontal_error_by_floor_status_condition.csv')
fig,ax=plt.subplots(figsize=(6.3,4.4)); positions=[]; data=[]; labels=[]; p=1
for k in K_VALUES:
    for status in ['Correct floor','Wrong floor']:
        data.append(err[(err.k.eq(k))&(err.floor_status.eq(status))].median_error_m.dropna().to_numpy(float)); positions.append(p); labels.append(f'K={k}\n{status}'); p+=1
    p+=.5
ax.boxplot(data,positions=positions,widths=.65,showfliers=False); ax.set_xticks(positions); ax.set_xticklabels(labels,rotation=20,ha='right'); ax.set_ylabel('Condition-level median 2D error (m)'); ax.grid(axis='y',alpha=.35); ax.tick_params(direction='in',top=True,right=True); fig.tight_layout(); fig.savefig(F/'fig_horizontal_error_by_floor_status.png',bbox_inches='tight',pad_inches=.03); fig.savefig(F/'fig_horizontal_error_by_floor_status.pdf',bbox_inches='tight',pad_inches=.03); plt.close(fig)
top=['SQS','nearest_rp_distance','sigma_fps','I_k','rss_gradient_proxy','D_cand']; labels_map={'SQS':'SQS','nearest_rp_distance':'Nearest-RP distance','sigma_fps':'Candidate spatial spread','I_k':'Cumulative-neighborhood instability','rss_gradient_proxy':'RSS-gradient proxy','D_cand':'Candidate-set diameter'}
fig,ax=plt.subplots(figsize=(6.8,4.5)); xx=np.arange(4)
for iid in top:
    vals=[float(a3a.loc[a3a.indicator_id.eq(iid),'median_aligned_rho'].iloc[0])]+[float(assoc_sum[(assoc_sum.k.eq(k))&(assoc_sum.indicator_id.eq(iid))].median_aligned_rho.iloc[0]) for k in K_VALUES]
    ax.plot(xx,vals,marker='o',label=labels_map[iid])
ax.set_xticks(xx); ax.set_xticklabels(['All scans','Floor-correct, K=3','Floor-correct, K=5','Floor-correct, K=10'],rotation=12); ax.set_ylabel('Median aligned Spearman association'); ax.grid(axis='y',alpha=.35); ax.tick_params(direction='in',top=True,right=True); ax.legend(frameon=False,ncol=2,fontsize=6.7); fig.tight_layout(); fig.savefig(F/'fig_floor_correct_association_robustness.png',bbox_inches='tight',pad_inches=.03); fig.savefig(F/'fig_floor_correct_association_robustness.pdf',bbox_inches='tight',pad_inches=.03); plt.close(fig)
print('[A4 phase2] saved',len(assoc),len(adp))
print(comp[comp.indicator_id.isin(top)].sort_values(['k','median_aligned_rho_floor_correct'],ascending=[True,False]).to_string(index=False))
