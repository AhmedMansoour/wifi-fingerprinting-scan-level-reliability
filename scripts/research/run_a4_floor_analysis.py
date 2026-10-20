from __future__ import annotations
from research_paths import REPO, WORKSPACE, output_dir


from pathlib import Path
import json, math, warnings
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.neighbors import KDTree
import matplotlib.pyplot as plt

ROOT = WORKSPACE
A2 = (WORKSPACE / "reference/A2")
A3 = (REPO / "reference/approved/revision_summaries/A3")
OUT = output_dir("A4")
TABLES = OUT/'tables'; FIGS=OUT/'figures'; SCRIPTS=OUT/'scripts'
for d in [OUT,TABLES,FIGS,SCRIPTS]: d.mkdir(parents=True,exist_ok=True)

COMBINED_PATH=ROOT/'data/interim/datasets_combined_all/combined_all_datasets.csv'
FEATURE_PATH=ROOT/'data/processed/scan_level_reliability_indicator_features.csv.gz'
PRED_PATH=ROOT/'data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz'
DICT_PATH=A2/'A2_core_indicator_dictionary_18.csv'
A3_ASSOC_PATH=A3/'A3_indicator_error_association_summary_ci_bh.csv'
A3_ADP_PATH=A3/'A3_gross_error_adaptive_summary_ci.csv'

RSS_FLOOR=-110.0
MAX_APS=180
CHUNK=256
K_VALUES=[3,5,10]
EST_ORDER=['KNN','WKNN','Random Forest','Extra Trees','Gradient Boosting','CatBoost','Transformer','Residual CNN']
EST_SHORT={'KNN':'KNN','WKNN':'WKNN','Random Forest':'RF','Extra Trees':'ET','Gradient Boosting':'HGB','CatBoost':'Cat','Transformer':'Trf','Residual CNN':'ResCNN'}
UNIT_SHORT={
    'BlockZ-10W-1719W / BlockZPolyU':'Block Z',
    'TAMPERE_MULTIBUILDING_5174851 / SAH1':'Tampere-SAH1',
    'TAMPERE_MULTIBUILDING_5174851 / TIE1':'Tampere-TIE1',
    'TAU_ADDITIONAL_3819917 / Database_Building01':'TAU-B1',
    'TAU_ADDITIONAL_3819917 / Database_Building02':'TAU-B2',
    'TUT_WLAN_RSS_1161525 / TUT':'TUT-WLAN',
    'UJIndoorLoc / Building0':'UJI-B0',
    'UJIndoorLoc / Building1':'UJI-B1',
    'UJIndoorLoc / Building2':'UJI-B2',
}
SEED=20260725
B=10000


def ensure_unit_label(df):
    df=df.copy()
    if 'unit_label' not in df.columns:
        if 'unit' in df.columns: df['unit_label']=df['unit'].astype(str)
        else: df['unit_label']=df['dataset'].astype(str)+' / '+df['group'].astype(str)
    return df


def parse_rss(s):
    if pd.isna(s): return {}
    try: d=json.loads(str(s)) if not isinstance(s,dict) else s
    except Exception: return {}
    out={}
    if isinstance(d,dict):
        for k,v in d.items():
            try:
                fv=float(v)
                if np.isfinite(fv): out[str(k)]=fv
            except Exception: pass
    return out


def floor_label(v):
    if pd.isna(v): return None
    s=str(v).strip()
    try:
        x=float(s)
        if np.isfinite(x):
            if abs(x-round(x))<1e-9: return str(int(round(x)))
            return f'{x:g}'
    except Exception: pass
    return s.lower()


def select_aps_train(train_rss,max_aps=MAX_APS):
    counts=defaultdict(int)
    for d in train_rss:
        for ap in d: counts[ap]+=1
    return sorted(counts,key=lambda a:(-counts[a],a))[:max_aps]


def make_dense(rss,aps):
    idx={a:j for j,a in enumerate(aps)}
    X=np.full((len(rss),len(aps)),RSS_FLOOR,dtype=np.float32)
    for i,d in enumerate(rss):
        for a,v in d.items():
            j=idx.get(a)
            if j is not None: X[i,j]=float(v)
    return X


def aggregate_templates(train_X,train_xy,train_floor):
    # Same RP and floor form one radio-map template.
    keys=np.array([(round(float(x),3),round(float(y),3),f) for (x,y),f in zip(train_xy,train_floor)],dtype=object)
    key_to_id={}; inv=[]; template_floors=[]
    for row in keys:
        key=tuple(row.tolist())
        if key not in key_to_id:
            key_to_id[key]=len(key_to_id); template_floors.append(key[2])
        inv.append(key_to_id[key])
    inv=np.asarray(inv,int); n=len(key_to_id)
    sums=np.zeros((n,train_X.shape[1]),np.float64); counts=np.zeros(n,np.float64)
    np.add.at(sums,inv,train_X.astype(np.float64)); np.add.at(counts,inv,1)
    return (sums/counts[:,None]).astype(np.float32),np.asarray(template_floors,object)


def topk(train,test,k=10,chunk=CHUNK):
    train=np.asarray(train,np.float32); test=np.asarray(test,np.float32)
    k=min(k,len(train)); tn=np.sum(train*train,axis=1,dtype=np.float32)
    ids=np.empty((len(test),k),np.int64); ds=np.empty((len(test),k),np.float32)
    for s in range(0,len(test),chunk):
        e=min(s+chunk,len(test)); b=test[s:e]; bn=np.sum(b*b,axis=1,dtype=np.float32)[:,None]
        d2=bn+tn[None,:]-2*(b@train.T); np.maximum(d2,0,out=d2)
        part=np.argpartition(d2,kth=k-1,axis=1)[:,:k]
        vals=np.take_along_axis(d2,part,axis=1); order=np.argsort(vals,axis=1)
        ids[s:e]=np.take_along_axis(part,order,axis=1)
        ds[s:e]=np.sqrt(np.take_along_axis(vals,order,axis=1))/np.sqrt(max(1,train.shape[1]))
    return ds,ids


def weighted_floor(neighbor_floors,neighbor_dist,k):
    floors=neighbor_floors[:k]; dist=np.asarray(neighbor_dist[:k],float)
    zero=dist<=1e-12
    if zero.any(): floors=floors[zero]; weights=np.ones(zero.sum())
    else: weights=1.0/(dist+1e-6)
    scores=defaultdict(float)
    for f,w in zip(floors,weights): scores[str(f)]+=float(w)
    mx=max(scores.values()); tied={f for f,s in scores.items() if abs(s-mx)<=1e-12}
    for f in floors:
        if str(f) in tied: return str(f)
    return str(floors[0])


def pct_ci_by_unit(df,value_col,seed=SEED):
    # Percentile CI for macro mean across units.
    unitvals=df.groupby('unit_label')[value_col].mean().dropna().to_numpy(float)
    if len(unitvals)==0: return (np.nan,np.nan,np.nan)
    rng=np.random.default_rng(seed); inds=rng.integers(0,len(unitvals),size=(B,len(unitvals)))
    boots=unitvals[inds].mean(axis=1)
    return float(unitvals.mean()),*map(float,np.quantile(boots,[.025,.975]))


def cluster_median_ci(df,value_col,seed=SEED):
    d=df[['unit_label',value_col]].dropna(); units=d.unit_label.unique().tolist()
    if not units: return (np.nan,np.nan,np.nan)
    point=float(np.median(d[value_col]))
    rng=np.random.default_rng(seed); boots=[]
    groups={u:d.loc[d.unit_label.eq(u),value_col].to_numpy(float) for u in units}
    for _ in range(B):
        sampled=rng.choice(units,len(units),replace=True)
        vals=np.concatenate([groups[u] for u in sampled])
        boots.append(np.median(vals))
    lo,hi=np.quantile(boots,[.025,.975]); return point,float(lo),float(hi)


def add_nearest_rp(long_df,combined):
    long_df=long_df.copy(); long_df['nearest_rp_distance']=np.nan
    for unit,idx in long_df.groupby('unit_label').groups.items():
        part=long_df.loc[idx]; ds=str(part.dataset.iloc[0]); group=str(part.group.iloc[0])
        tr=combined[(combined.dataset.astype(str)==ds)&(combined.group.astype(str)==group)&combined.split.astype(str).str.lower().eq('train')]
        xy=tr[['x','y']].apply(pd.to_numeric,errors='coerce').to_numpy(float); xy=xy[np.isfinite(xy).all(1)]
        if not len(xy): continue
        tree=KDTree(np.unique(xy,axis=0)); p=long_df.loc[idx,['x_pred','y_pred']].apply(pd.to_numeric,errors='coerce').to_numpy(float)
        v=np.isfinite(p).all(1); out=np.full(len(p),np.nan)
        if v.any(): out[v]=tree.query(p[v],k=1)[0][:,0]
        long_df.loc[idx,'nearest_rp_distance']=out
    return long_df


def main():
    print('[A4] Loading data')
    combined=pd.read_csv(COMBINED_PATH,usecols=['dataset','group','floor','split','row_id','x','y','rss_json'],dtype={'row_id':str},low_memory=False)
    combined=ensure_unit_label(combined)
    feat=ensure_unit_label(pd.read_csv(FEATURE_PATH,dtype={'row_id':str},low_memory=False))
    pred=ensure_unit_label(pd.read_csv(PRED_PATH,dtype={'row_id':str},low_memory=False))
    pred=pred[pred.estimator_display.isin(EST_ORDER)].copy()
    specs=pd.read_csv(DICT_PATH)
    # normalize expected field names
    if 'indicator_id' not in specs: specs=specs.rename(columns={'code_column':'indicator_id'})
    if 'label' not in specs:
        labcol='manuscript_label' if 'manuscript_label' in specs else 'indicator'
        specs=specs.rename(columns={labcol:'label'})
    print(specs.columns.tolist())

    scan_rows=[]; unit_meta=[]
    units=pred[['dataset','group','unit_label']].drop_duplicates().sort_values('unit_label')
    for _,u in units.iterrows():
        unit=str(u.unit_label); ds=str(u.dataset); group=str(u.group)
        sub=combined[(combined.dataset.astype(str)==ds)&(combined.group.astype(str)==group)].copy()
        train=sub[sub.split.astype(str).str.lower().eq('train')].copy()
        test_ids=set(feat.loc[feat.unit_label.eq(unit),'row_id'].astype(str))
        test=sub[sub.row_id.astype(str).isin(test_ids)].copy()
        train['floor_c']=train.floor.map(floor_label); test['floor_c']=test.floor.map(floor_label)
        train=train[train.floor_c.notna()].reset_index(drop=True); test=test[test.floor_c.notna()].reset_index(drop=True)
        if train.empty or test.empty or train.floor_c.nunique()<2:
            unit_meta.append({'unit_label':unit,'included':False,'reason':'floor labels unavailable or fewer than two floors','n_test':len(test),'n_floors':test.floor_c.nunique()})
            print('[A4] Excluded',unit)
            continue
        train_xy=train[['x','y']].apply(pd.to_numeric,errors='coerce').to_numpy(float)
        valid=np.isfinite(train_xy).all(1); train=train.loc[valid].reset_index(drop=True); train_xy=train_xy[valid]
        train_rss=[parse_rss(x) for x in train.rss_json]; test_rss=[parse_rss(x) for x in test.rss_json]
        aps=select_aps_train(train_rss)
        Xtr=make_dense(train_rss,aps); Xte=make_dense(test_rss,aps)
        T,floors=aggregate_templates(Xtr,train_xy,train.floor_c.to_numpy())
        dist,idx=topk(T,Xte,max(K_VALUES))
        unit_meta.append({'unit_label':unit,'included':True,'reason':'','n_train':len(train),'n_test':len(test),'n_floors':test.floor_c.nunique(),'n_templates':len(T),'n_ap_features':len(aps)})
        for i,row in test.iterrows():
            rec={'dataset':ds,'group':group,'unit_label':unit,'row_id':str(row.row_id),'true_floor':row.floor_c}
            nf=floors[idx[i]]
            for k in K_VALUES:
                pf=weighted_floor(nf,dist[i],k); rec[f'pred_floor_k{k}']=pf; rec[f'floor_correct_k{k}']=pf==row.floor_c
            scan_rows.append(rec)
        print(f'[A4] {unit}: train={len(train)}, test={len(test)}, floors={test.floor_c.nunique()}, templates={len(T)}')

    scan=pd.DataFrame(scan_rows); meta=pd.DataFrame(unit_meta)
    scan.to_csv(TABLES/'A4_floor_predictions_by_scan.csv',index=False)
    meta.to_csv(TABLES/'A4_floor_unit_eligibility.csv',index=False)

    # Floor-hit results.
    hit=[]
    for k in K_VALUES:
        c=f'floor_correct_k{k}'
        for unit,g in scan.groupby('unit_label'):
            hit.append({'k':k,'unit_label':unit,'unit_short':UNIT_SHORT.get(unit,unit.split(' / ')[-1]),'n_scans':len(g),'n_floor_correct':int(g[c].sum()),'floor_hit_rate':float(g[c].mean()),'wrong_floor_rate':float(1-g[c].mean())})
    hit=pd.DataFrame(hit); hit.to_csv(TABLES/'A4_floor_hit_rate_by_unit.csv',index=False)
    hit_summary=[]
    for k,g in hit.groupby('k'):
        micro=scan[f'floor_correct_k{k}'].mean(); macro,lo,hi=pct_ci_by_unit(scan.assign(value=scan[f'floor_correct_k{k}'].astype(float)),'value',seed=SEED+k)
        hit_summary.append({'k':k,'n_units':g.unit_label.nunique(),'n_scans':len(scan),'micro_floor_hit_rate':micro,'macro_mean_floor_hit_rate':macro,'ci95_low_macro':lo,'ci95_high_macro':hi,'median_unit_floor_hit_rate':g.floor_hit_rate.median(),'min_unit_floor_hit_rate':g.floor_hit_rate.min(),'max_unit_floor_hit_rate':g.floor_hit_rate.max()})
    hit_summary=pd.DataFrame(hit_summary); hit_summary.to_csv(TABLES/'A4_floor_hit_rate_summary.csv',index=False)

    # Build long estimator-indicator table.
    keep=['dataset','group','unit_label','row_id','estimator_display','error_m','x_pred','y_pred']
    long=pred[keep].merge(feat.drop(columns=[c for c in ['x_true','y_true'] if c in feat]),on=['dataset','group','unit_label','row_id'],how='left',validate='many_to_one')
    long=long.merge(scan,on=['dataset','group','unit_label','row_id'],how='inner',validate='many_to_one')
    long=add_nearest_rp(long,combined)

    # Conditional horizontal-error summaries.
    err_rows=[]
    for k in K_VALUES:
        fc=f'floor_correct_k{k}'
        for (unit,est),g in long.groupby(['unit_label','estimator_display']):
            errs=pd.to_numeric(g.error_m,errors='coerce')
            q1,q3=errs.quantile([.25,.75]); thr=float(q3+1.5*(q3-q1))
            for status,sg in g.groupby(fc):
                e=pd.to_numeric(sg.error_m,errors='coerce').dropna()
                if e.empty: continue
                err_rows.append({'k':k,'unit_label':unit,'estimator_display':est,'floor_status':'Correct floor' if status else 'Wrong floor','n':len(e),'median_error_m':e.median(),'p75_error_m':e.quantile(.75),'p95_error_m':e.quantile(.95),'fixed7_gross_pct':100*(e>7).mean(),'adaptive_gross_pct':100*(e>thr).mean(),'horizontally_within_7m_pct':100*(e<=7).mean()})
    err=pd.DataFrame(err_rows); err.to_csv(TABLES/'A4_horizontal_error_by_floor_status_condition.csv',index=False)
    err_est=[]
    for (k,est,status),g in err.groupby(['k','estimator_display','floor_status']):
        err_est.append({'k':k,'estimator_display':est,'floor_status':status,'n_conditions':len(g),'median_of_condition_medians_m':g.median_error_m.median(),'median_p95_error_m':g.p95_error_m.median(),'median_fixed7_gross_pct':g.fixed7_gross_pct.median(),'median_within7_pct':g.horizontally_within_7m_pct.median()})
    pd.DataFrame(err_est).to_csv(TABLES/'A4_horizontal_error_by_floor_status_estimator_summary.csv',index=False)

    # Wrong-floor discrimination by reliability indicator, unit-level (classifier common to estimators).
    specmap=specs.set_index('indicator_id')
    wf_rows=[]
    for k in K_VALUES:
        label=(~scan.set_index('row_id')[f'floor_correct_k{k}']).rename('wrong_floor')
        d=feat[feat.row_id.isin(scan.row_id)].copy().set_index('row_id').join(label,how='inner')
        for unit,g in d.groupby('unit_label'):
            y=g.wrong_floor.astype(int).to_numpy()
            if y.sum()<3 or (len(y)-y.sum())<3: continue
            for iid,s in specmap.iterrows():
                if iid not in g.columns or iid=='nearest_rp_distance': continue  # estimator-specific quantity
                x=pd.to_numeric(g[iid],errors='coerce').to_numpy(float); v=np.isfinite(x)
                if v.sum()<20 or len(np.unique(y[v]))<2 or np.unique(x[v]).size<2: continue
                score=int(s.expected_sign)*x[v]
                wf_rows.append({'k':k,'unit_label':unit,'indicator_id':iid,'label':s.label,'family':s.family,'n':int(v.sum()),'wrong_floor_prevalence':float(y[v].mean()),'auroc':roc_auc_score(y[v],score),'auprc':average_precision_score(y[v],score)})
    wf=pd.DataFrame(wf_rows); wf.to_csv(TABLES/'A4_wrong_floor_indicator_discrimination_by_unit.csv',index=False)
    wf_sum=[]
    for (k,iid),g in wf.groupby(['k','indicator_id']):
        r=g.iloc[0]; au,al,ah=cluster_median_ci(g,'auroc',seed=SEED+k+sum(map(ord,iid))); ap,pl,ph=cluster_median_ci(g,'auprc',seed=SEED+100+k+sum(map(ord,iid)))
        wf_sum.append({'k':k,'indicator_id':iid,'label':r.label,'family':r.family,'n_units':len(g),'median_auroc':au,'ci95_low_auroc':al,'ci95_high_auroc':ah,'median_auprc':ap,'ci95_low_auprc':pl,'ci95_high_auprc':ph,'median_prevalence':g.wrong_floor_prevalence.median()})
    wf_sum=pd.DataFrame(wf_sum).sort_values(['k','median_auroc'],ascending=[True,False]); wf_sum.to_csv(TABLES/'A4_wrong_floor_indicator_discrimination_summary.csv',index=False)

    # Floor-correct association and adaptive gross-error discrimination.
    assoc=[]; adp=[]
    for k in K_VALUES:
        fc=f'floor_correct_k{k}'
        for (unit,est),g0 in long.groupby(['unit_label','estimator_display']):
            g=g0[g0[fc]].copy()
            if len(g)<20: continue
            e=pd.to_numeric(g.error_m,errors='coerce').to_numpy(float)
            q1,q3=np.nanquantile(e,[.25,.75]); thr=q3+1.5*(q3-q1); y=(e>thr).astype(int)
            for iid,s in specmap.iterrows():
                if iid not in g.columns: continue
                x=pd.to_numeric(g[iid],errors='coerce').to_numpy(float); v=np.isfinite(x)&np.isfinite(e)
                if v.sum()>=20 and np.unique(x[v]).size>1 and np.unique(e[v]).size>1:
                    with warnings.catch_warnings(): warnings.simplefilter('ignore'); rho,_=spearmanr(x[v],e[v])
                    if np.isfinite(rho): assoc.append({'k':k,'unit_label':unit,'estimator_display':est,'indicator_id':iid,'label':s.label,'family':s.family,'n':int(v.sum()),'aligned_rho':int(s.expected_sign)*float(rho)})
                if v.sum()>=20 and np.unique(y[v]).size==2 and y[v].sum()>=3:
                    score=int(s.expected_sign)*x[v]
                    adp.append({'k':k,'unit_label':unit,'estimator_display':est,'indicator_id':iid,'label':s.label,'family':s.family,'n':int(v.sum()),'prevalence':float(y[v].mean()),'auroc':roc_auc_score(y[v],score),'auprc':average_precision_score(y[v],score)})
    assoc=pd.DataFrame(assoc); adp=pd.DataFrame(adp)
    assoc.to_csv(TABLES/'A4_floor_correct_association_by_condition.csv',index=False); adp.to_csv(TABLES/'A4_floor_correct_adaptive_discrimination_by_condition.csv',index=False)
    assoc_sum=assoc.groupby(['k','indicator_id','label','family'],as_index=False).agg(n_conditions=('aligned_rho','size'),median_aligned_rho=('aligned_rho','median'),direction_consistency_pct=('aligned_rho',lambda x:100*(x>0).mean()))
    adp_sum=adp.groupby(['k','indicator_id','label','family'],as_index=False).agg(n_conditions=('auroc','size'),median_auroc=('auroc','median'),median_auprc=('auprc','median'),median_prevalence=('prevalence','median'))
    assoc_sum.to_csv(TABLES/'A4_floor_correct_association_summary.csv',index=False); adp_sum.to_csv(TABLES/'A4_floor_correct_adaptive_discrimination_summary.csv',index=False)

    # Comparison with complete analysis.
    a3assoc=pd.read_csv(A3_ASSOC_PATH); a3adp=pd.read_csv(A3_ADP_PATH)
    comp=assoc_sum.merge(a3assoc[['indicator_id','median_aligned_rho']],on='indicator_id',how='left',suffixes=('_floor_correct','_all'))
    comp['delta_aligned_rho']=comp.median_aligned_rho_floor_correct-comp.median_aligned_rho_all
    comp=comp.merge(adp_sum[['k','indicator_id','median_auroc','median_auprc']],on=['k','indicator_id'],how='left')
    comp=comp.merge(a3adp[['indicator_id','median_auroc','median_auprc']],on='indicator_id',how='left',suffixes=('_floor_correct','_all'))
    comp['delta_auroc']=comp.median_auroc_floor_correct-comp.median_auroc_all; comp['delta_auprc']=comp.median_auprc_floor_correct-comp.median_auprc_all
    comp.to_csv(TABLES/'A4_floor_correct_vs_complete_comparison.csv',index=False)

    # Figures.
    plt.rcParams.update({'figure.dpi':130,'savefig.dpi':500,'font.family':'DejaVu Serif','font.size':8,'axes.titlesize':9,'axes.labelsize':8.3,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'pdf.fonttype':42,'ps.fonttype':42})
    order=hit[hit.k.eq(5)].sort_values('floor_hit_rate',ascending=False).unit_label.tolist()
    fig,ax=plt.subplots(figsize=(7.2,4.4))
    x=np.arange(len(order)); offsets={3:-.18,5:0,10:.18}; markers={3:'o',5:'s',10:'^'}
    for k in K_VALUES:
        gg=hit[hit.k.eq(k)].set_index('unit_label').reindex(order)
        ax.plot(x+offsets[k],100*gg.floor_hit_rate,marker=markers[k],linestyle='none',label=f'K={k}',markersize=5)
    ax.set_xticks(x); ax.set_xticklabels([UNIT_SHORT.get(u,u.split(' / ')[-1]) for u in order],rotation=28,ha='right'); ax.set_ylabel('Floor-hit rate (%)'); ax.set_ylim(0,102); ax.grid(axis='y',alpha=.35); ax.tick_params(direction='in',top=True,right=True); ax.legend(frameon=False,ncol=3,loc='lower left'); fig.tight_layout()
    fig.savefig(FIGS/'fig_floor_hit_rate_k_sensitivity.png',bbox_inches='tight',pad_inches=.03); fig.savefig(FIGS/'fig_floor_hit_rate_k_sensitivity.pdf',bbox_inches='tight',pad_inches=.03); plt.close(fig)

    # Error comparison figure (condition medians).
    fig,ax=plt.subplots(figsize=(6.3,4.4))
    positions=[]; data=[]; labels=[]; p=1
    for k in K_VALUES:
        for status in ['Correct floor','Wrong floor']:
            vals=err[(err.k.eq(k))&(err.floor_status.eq(status))].median_error_m.dropna().to_numpy(float)
            data.append(vals); positions.append(p); labels.append(f'K={k}\n{status}'); p+=1
        p+=.5
    ax.boxplot(data,positions=positions,widths=.65,showfliers=False); ax.set_xticks(positions); ax.set_xticklabels(labels,rotation=20,ha='right'); ax.set_ylabel('Condition-level median 2D error (m)'); ax.grid(axis='y',alpha=.35); ax.tick_params(direction='in',top=True,right=True); fig.tight_layout()
    fig.savefig(FIGS/'fig_horizontal_error_by_floor_status.png',bbox_inches='tight',pad_inches=.03); fig.savefig(FIGS/'fig_horizontal_error_by_floor_status.pdf',bbox_inches='tight',pad_inches=.03); plt.close(fig)

    # Association robustness figure.
    top=['SQS','nearest_rp_distance','sigma_fps','I_k','rss_gradient_proxy','D_cand']
    lab={'SQS':'SQS','nearest_rp_distance':'Nearest-RP distance','sigma_fps':'Candidate spatial spread','I_k':'Cumulative-neighborhood instability','rss_gradient_proxy':'RSS-gradient proxy','D_cand':'Candidate-set diameter'}
    fig,ax=plt.subplots(figsize=(6.8,4.5))
    xx=np.arange(4); xt=['All scans','K=3','K=5','K=10']
    for iid in top:
        allv=float(a3assoc.loc[a3assoc.indicator_id.eq(iid),'median_aligned_rho'].iloc[0]); vals=[allv]
        for k in K_VALUES:
            s=assoc_sum[(assoc_sum.k.eq(k))&(assoc_sum.indicator_id.eq(iid))]
            vals.append(float(s.median_aligned_rho.iloc[0]) if len(s) else np.nan)
        ax.plot(xx,vals,marker='o',label=lab[iid])
    ax.set_xticks(xx); ax.set_xticklabels(xt); ax.set_ylabel('Median aligned Spearman association'); ax.grid(axis='y',alpha=.35); ax.tick_params(direction='in',top=True,right=True); ax.legend(frameon=False,ncol=2,fontsize=6.7); fig.tight_layout()
    fig.savefig(FIGS/'fig_floor_correct_association_robustness.png',bbox_inches='tight',pad_inches=.03); fig.savefig(FIGS/'fig_floor_correct_association_robustness.pdf',bbox_inches='tight',pad_inches=.03); plt.close(fig)

    # Findings text.
    lines=[]
    lines.append('A4 floor-aware robustness findings')
    lines.append(hit_summary.to_string(index=False))
    for k in K_VALUES:
        wrong=err[(err.k.eq(k))&(err.floor_status.eq('Wrong floor'))]
        correct=err[(err.k.eq(k))&(err.floor_status.eq('Correct floor'))]
        lines.append(f'K={k}: median condition-level median error correct={correct.median_error_m.median():.3f} m, wrong={wrong.median_error_m.median():.3f} m; median wrong-floor cases within 7m={wrong.horizontally_within_7m_pct.median():.1f}%')
        s=comp[(comp.k.eq(k))&(comp.indicator_id.eq('SQS'))].iloc[0]
        lines.append(f'K={k}: floor-correct SQS rho={s.median_aligned_rho_floor_correct:.3f}, AUROC={s.median_auroc_floor_correct:.3f}, AUPRC={s.median_auprc_floor_correct:.3f}')
    (OUT/'A4_findings.txt').write_text('\n'.join(lines),encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__': main()
