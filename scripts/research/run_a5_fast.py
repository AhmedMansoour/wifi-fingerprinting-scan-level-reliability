from __future__ import annotations
from research_paths import REPO, WORKSPACE, output_dir

import json, importlib.util
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr, rankdata
from sklearn.metrics import roc_auc_score, average_precision_score

BASE = Path(__file__).with_name("run_a5_sensitivity.py")
spec=importlib.util.spec_from_file_location('basea5',BASE); b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

OUT=b.OUT; T=b.TABLE_DIR; F=b.FIG_DIR

import torch

def torch_topk(train_X, test_X, k, chunk_size=256):
    train=np.asarray(train_X,dtype=np.float32); test=np.asarray(test_X,dtype=np.float32)
    k=min(int(k),len(train)); xt=torch.from_numpy(train); qt=torch.from_numpy(test)
    try: torch.set_num_threads(min(16, max(1, torch.get_num_threads())))
    except Exception: pass
    all_d=[]; all_i=[]
    scale=float(np.sqrt(max(1,train.shape[1])))
    with torch.no_grad():
        for st in range(0,len(test),chunk_size):
            d=torch.cdist(qt[st:st+chunk_size],xt,p=2)/scale
            vals,inds=torch.topk(d,k,largest=False,dim=1)
            all_d.append(vals.cpu().numpy().astype(np.float32)); all_i.append(inds.cpu().numpy().astype(np.int64))
    return np.vstack(all_d),np.vstack(all_i)

b.m20.topk_euclidean_neighbors=torch_topk

def candidate_features_vectorized(combined, pred, baseline_feat):
    from sklearn.neighbors import KDTree
    test_ids_by_pair={(str(d),str(g)):set(ids.astype(str)) for (d,g),ids in pred.groupby(['dataset','group'])['row_id']}
    outputs=[]; ikouts=[]
    base_stats=baseline_feat[['dataset','group','unit_label','row_id','ap_count','rss_std','rss_range']].copy()
    for (dataset,group),ids in test_ids_by_pair.items():
        unit=f'{dataset} / {group}'
        ud=combined[(combined['dataset'].astype(str)==dataset)&(combined['group'].astype(str)==group)].copy()
        tr=ud[ud['split'].astype(str).str.lower().eq('train')].copy(); te=ud[ud['row_id'].astype(str).isin(ids)].copy()
        trxy=b.m20.safe_xy(tr); texy=b.m20.safe_xy(te); vt=np.isfinite(trxy).all(1); vq=np.isfinite(texy).all(1)
        tr=tr.loc[vt].reset_index(drop=True); trxy=trxy[vt]; te=te.loc[vq].reset_index(drop=True)
        trr=[b.m20.parse_rss_json(x) for x in tr.rss_json]; ter=[b.m20.parse_rss_json(x) for x in te.rss_json]
        aps=b.m20.select_ap_list(trr,ter,b.m20.MAX_APS_PER_UNIT)
        X,P=b.m20.make_dense_matrix(trr,aps); Q,QP=b.m20.make_dense_matrix(ter,aps)
        X,P,trxy,nt=b.m20.aggregate_training_templates(X,P,trxy,tr.floor.to_numpy())
        maxm=min(max(b.CANDIDATE_SIZES),len(X)); dists,idx=torch_topk(X,Q,maxm,b.m20.DISTANCE_CHUNK_SIZE)
        candxy=trxy[idx]  # n x maxm x 2
        unique=np.unique(trxy,axis=0); tree=KDTree(unique); radius=b.m20.adaptive_density_radius(unique)
        rid=te.row_id.astype(str).to_numpy(); n=len(te)
        bs=base_stats[(base_stats.dataset.astype(str)==dataset)&(base_stats.group.astype(str)==group)].set_index('row_id').reindex(rid)
        for M in [m for m in b.CANDIDATE_SIZES if m<=maxm]:
            pts=candxy[:,:M,:]; centroid=pts.mean(1); delta=pts-centroid[:,None,:]
            spread=np.sqrt(np.mean(np.sum(delta*delta,axis=2),axis=1))
            diff=pts[:,:,None,:]-pts[:,None,:,:]; diam=np.sqrt(np.sum(diff*diff,axis=3)).max(axis=(1,2))
            cc=np.cumsum(pts,axis=1)/np.arange(1,M+1)[None,:,None]; ik=np.linalg.norm(cc-cc[:,-1:, :],axis=2).max(axis=1)
            minrss=dists[:,0]; second=dists[:,1] if dists.shape[1]>1 else minrss
            isolation=np.maximum(second-minrss,0)/(second+b.BASE_EPS); contrast=np.maximum(dists[:,M-1]-minrss,b.BASE_EPS); grad=spread/contrast
            CP=P[idx[:,:M]]; TP=QP[:,None,:]
            inter=np.logical_and(CP,TP).sum(axis=2).astype(float); union=np.logical_or(CP,TP).sum(axis=2).astype(float)
            jac=np.divide(inter,union,out=np.zeros_like(inter),where=union>0); maxj=jac.max(1); meanj=jac.mean(1); novelty=1-maxj
            density=tree.query_radius(centroid,r=radius,count_only=True).astype(float)
            f=pd.DataFrame({'dataset':dataset,'group':group,'unit_label':unit,'row_id':rid,'M':M,
                'min_rss_distance':minrss,'nearest_match_isolation':isolation,'sigma_fps':spread,'D_cand':diam,'I_k':ik,
                'rss_gradient_proxy':grad,'ap_overlap':maxj,'mean_ap_overlap':meanj,'ap_set_novelty':novelty,
                'local_rp_density':density,'ap_count':bs.ap_count.to_numpy(float),'rss_std':bs.rss_std.to_numpy(float),'rss_range':bs.rss_range.to_numpy(float)})
            ids2=np.arange(n); riskmin=b.robust01(f.min_rss_distance); risksp=b.robust01(f.sigma_fps); riskd=b.robust01(f.D_cand); riskn=b.robust01(f.ap_set_novelty)
            ss=1-riskmin; sg=1-np.nanmean(np.vstack([risksp,riskd]),axis=0); sa=b.robust01(f.ap_count); so=b.robust01(f.ap_overlap); sd=b.robust01(f.local_rp_density); si=b.robust01(f.nearest_match_isolation)
            f['SQS']=np.nanmean(np.vstack([ss,sg,sa,so,sd]),axis=0); f['C_sigma']=ss/(1+risksp); f['FII']=np.nanmean(np.vstack([ss,sa,so,si,1-riskn]),axis=0)
            outputs.append(f)
        for K in [k for k in b.IK_HORIZONS if k<=maxm]:
            pts=candxy[:,:K,:]; cc=np.cumsum(pts,axis=1)/np.arange(1,K+1)[None,:,None]
            ik=np.linalg.norm(cc-cc[:,-1:, :],axis=2).max(axis=1)
            ikouts.append(pd.DataFrame({'dataset':dataset,'group':group,'unit_label':unit,'row_id':rid,'k_horizon':K,'I_k':ik}))
        print(f'[candidate-fast] {unit}: test={n}, templates={nt}, APs={len(aps)}',flush=True)
    return pd.concat(outputs,ignore_index=True),pd.concat(ikouts,ignore_index=True)

b.candidate_features=candidate_features_vectorized


def arr(s): return pd.to_numeric(s,errors='coerce').to_numpy(float)

def make_cache(df, indicator_ids=None):
    if indicator_ids is None: indicator_ids=[s['id'] for s in b.INDICATOR_SPECS if s['id'] in df]
    scores={iid:b.SPEC_BY_ID[iid]['expected_sign']*arr(df[iid]) for iid in indicator_ids}
    err=arr(df['error_m'])
    groups=[]
    for (u,e),idx in df.groupby(['unit_label','estimator_display'],sort=False,observed=False).indices.items():
        groups.append((u,e,np.asarray(idx,int)))
    return {'df':df,'ids':indicator_ids,'scores':scores,'err':err,'groups':groups}

def threshold_map(cache, mode, p1, p2=None):
    out={}; prev=[]; vals=[]
    for u,e,idx in cache['groups']:
        er=cache['err'][idx]; er=er[np.isfinite(er)]
        if mode=='fixed': t=float(p1)
        else:
            q=float(p1); lam=float(p2); lo=np.quantile(er,1-q); hi=np.quantile(er,q); t=float(hi+lam*(hi-lo))
        out[(u,e)]=t; prev.append(float(np.mean(er>t))); vals.append(t)
    return out,np.asarray(prev),np.asarray(vals)

def eval_disc(cache,tmap, ids=None, nominal=None):
    ids=ids or cache['ids']; rows=[]
    for u,e,idx in cache['groups']:
        er=cache['err'][idx]; y=(er>tmap[(u,e)]).astype(int)
        if nominal is not None:
            keep=nominal[idx].astype(bool); idx2=idx[keep]; y=y[keep]
        else: idx2=idx
        if len(idx2)<b.MIN_SCANS: continue
        for iid in ids:
            sc=cache['scores'][iid][idx2]; yy=y
            v=np.isfinite(sc)&np.isfinite(yy)
            if v.sum()<b.MIN_SCANS: continue
            yv=yy[v].astype(int); sv=sc[v]
            np1=int(yv.sum()); nn=len(yv)-np1
            if np1<b.MIN_POS or nn<b.MIN_NEG: continue
            # Exact rank-based AUROC and average precision, avoiding repeated estimator overhead.
            ranks=rankdata(sv,method='average')
            auroc=(ranks[yv==1].sum()-np1*(np1+1)/2)/(np1*nn)
            order=np.argsort(-sv,kind='mergesort'); ss=sv[order]; ys=yv[order]
            tps_all=np.cumsum(ys)
            distinct=np.r_[np.flatnonzero(np.diff(ss)),len(ss)-1]
            tps=tps_all[distinct].astype(float); fps=(distinct+1)-tps
            precision=tps/(tps+fps); recall=tps/np1
            auprc=float(np.sum(np.diff(np.r_[0.0,recall])*precision))
            rows.append({'indicator_id':iid,'label':b.SPEC_BY_ID[iid]['label'],'family':b.SPEC_BY_ID[iid]['family'],
                         'unit_label':u,'estimator_display':e,'n':len(yv),'n_pos':np1,'prevalence':np1/len(yv),
                         'auroc':float(auroc),'auprc':auprc})
    by=pd.DataFrame(rows)
    sm=(by.groupby(['indicator_id','label','family'],as_index=False)
          .agg(n_conditions=('auroc','size'),median_auroc=('auroc','median'),median_auprc=('auprc','median'),median_prevalence=('prevalence','median'))
          .sort_values(['median_auroc','median_auprc'],ascending=False)) if len(by) else by
    return by,sm

def eval_assoc(cache,ids=None):
    ids=ids or cache['ids']; rows=[]
    for u,e,idx in cache['groups']:
        er=cache['err'][idx]
        for iid in ids:
            sc=cache['scores'][iid][idx] # aligned risk score
            v=np.isfinite(sc)&np.isfinite(er)
            if v.sum()<8 or np.unique(sc[v]).size<2: continue
            rho=float(spearmanr(sc[v],er[v]).statistic)
            rows.append({'indicator_id':iid,'label':b.SPEC_BY_ID[iid]['label'],'family':b.SPEC_BY_ID[iid]['family'],
                         'unit_label':u,'estimator_display':e,'aligned_rho':rho})
    by=pd.DataFrame(rows)
    sm=(by.groupby(['indicator_id','label','family'],as_index=False)
          .agg(n_conditions=('aligned_rho','size'),median_aligned_rho=('aligned_rho','median'),direction_consistency=('aligned_rho',lambda x:np.mean(np.asarray(x)>0)))
          .sort_values('median_aligned_rho',ascending=False)) if len(by) else by
    return by,sm

def rankcorr(sm,base,metric='median_auroc'):
    d=base[['indicator_id',metric]].merge(sm[['indicator_id',metric]],on='indicator_id',suffixes=('_b','_v')).dropna()
    return float(spearmanr(d[metric+'_b'],d[metric+'_v']).statistic)

def topoverlap(sm,base,n=6,metric='median_auroc'):
    return len(set(sm.nlargest(n,metric).indicator_id)&set(base.nlargest(n,metric).indicator_id))/n

def main():
    pred,feat,combined,long_df=b.load_long()
    cache=make_cache(long_df)
    print('[FAST data]',long_df.shape,flush=True)
    base_tm,_,_=threshold_map(cache,'adaptive',b.BASE_Q,b.BASE_LAMBDA)
    _,base_adapt=eval_disc(cache,base_tm)
    base_fm,_,_=threshold_map(cache,'fixed',b.BASE_FIXED)
    _,base_fixed=eval_disc(cache,base_fm)

    ad_grid=[];ad_by=[];ad_sm=[]
    for q in b.ADAPTIVE_QUANTILES:
      for lam in b.ADAPTIVE_MULTIPLIERS:
        tm,prev,tvals=threshold_map(cache,'adaptive',q,lam); by,sm=eval_disc(cache,tm)
        sq=sm.loc[sm.indicator_id.eq('SQS')].iloc[0]
        ad_grid.append({'tail_quantile':q,'multiplier':lam,'median_threshold_m':np.median(tvals),'median_prevalence_pct':100*np.median(prev),
                        'rank_concordance':rankcorr(sm,base_adapt),'top6_overlap':topoverlap(sm,base_adapt),
                        'SQS_median_auroc':sq.median_auroc,'SQS_median_auprc':sq.median_auprc})
        by['tail_quantile']=q;by['multiplier']=lam;sm['tail_quantile']=q;sm['multiplier']=lam;ad_by.append(by);ad_sm.append(sm)
      print('[adaptive q]',q,flush=True)
    ad_grid=pd.DataFrame(ad_grid);ad_by=pd.concat(ad_by);ad_sm=pd.concat(ad_sm)

    fx_grid=[];fx_by=[];fx_sm=[]
    for t in b.FIXED_THRESHOLDS:
      tm,prev,tvals=threshold_map(cache,'fixed',t);by,sm=eval_disc(cache,tm);sq=sm.loc[sm.indicator_id.eq('SQS')].iloc[0]
      fx_grid.append({'fixed_threshold_m':t,'median_prevalence_pct':100*np.median(prev),'rank_concordance':rankcorr(sm,base_fixed),
                      'top6_overlap':topoverlap(sm,base_fixed),'SQS_median_auroc':sq.median_auroc,'SQS_median_auprc':sq.median_auprc})
      by['fixed_threshold_m']=t;sm['fixed_threshold_m']=t;fx_by.append(by);fx_sm.append(sm)
    fx_grid=pd.DataFrame(fx_grid);fx_by=pd.concat(fx_by);fx_sm=pd.concat(fx_sm)
    print('[fixed done]',flush=True)

    # confidence score merged once
    confscan=b.build_confidence_scan(feat)
    lconf=long_df[['dataset','group','unit_label','row_id']].merge(confscan,on=['dataset','group','unit_label','row_id'],how='left',validate='many_to_one')
    confvals=arr(lconf.baseline_confidence)
    nominal_by_q={}
    for q in b.CONFIDENCE_QUANTILES:
      nom=np.zeros(len(long_df),bool)
      for unit,idx in long_df.groupby('unit_label',sort=False).indices.items():
        ids=np.asarray(idx,int); unique=long_df.iloc[ids][['row_id']].copy(); unique['c']=confvals[ids]
        uq=unique.drop_duplicates('row_id'); th=np.nanquantile(uq.c,q); nom[ids]=confvals[ids]>=th
      nominal_by_q[q]=nom
    conf_rows=[];conf_by=[];conf_sm=[]
    baselines={}
    for scheme,tm in [('Adaptive',base_tm),('Fixed 7 m',base_fm)]:
      for q,nom in nominal_by_q.items():
        by,sm=eval_disc(cache,tm,b.RISK_INDICATORS,nominal=nom)
        if q==b.BASE_CONF_Q: baselines[scheme]=sm
        # condition prevalences
        cvals=[];allvals=[];grossvals=[]
        for u,e,idx in cache['groups']:
          y=(cache['err'][idx]>tm[(u,e)]); n=nom[idx]; nw=np.sum(y&n); nc=np.sum(n); ng=np.sum(y)
          cvals.append(100*nw/nc if nc else np.nan);allvals.append(100*nw/len(idx));grossvals.append(100*nw/ng if ng else np.nan)
        conf_rows.append({'scheme':scheme,'confidence_quantile':q,'median_confident_pct':100*np.mean(nom),
                          'median_cw_all_pct':np.nanmedian(allvals),'median_cw_among_confident_pct':np.nanmedian(cvals),
                          'median_cw_among_gross_pct':np.nanmedian(grossvals)})
        by['scheme']=scheme;by['confidence_quantile']=q;sm['scheme']=scheme;sm['confidence_quantile']=q;conf_by.append(by);conf_sm.append(sm)
    conf_summary=pd.DataFrame(conf_rows);conf_by=pd.concat(conf_by);conf_sm=pd.concat(conf_sm)
    rr=[]
    for (scheme,q),g in conf_sm.groupby(['scheme','confidence_quantile']):
      rr.append({'scheme':scheme,'confidence_quantile':q,'risk_rank_concordance':rankcorr(g,baselines[scheme]),'top6_overlap':topoverlap(g,baselines[scheme])})
    conf_summary=conf_summary.merge(pd.DataFrame(rr),on=['scheme','confidence_quantile'])
    print('[confidence done]',flush=True)

    # candidate features actual rebuild (reuse completed feature grid when available)
    cand_csv=T/'A5_candidate_features_by_M.csv'
    ikh_csv=T/'A5_Ik_by_horizon.csv'
    if cand_csv.exists() and ikh_csv.exists():
      cand=pd.read_csv(cand_csv,dtype={'row_id':str},low_memory=False)
      ikh=pd.read_csv(ikh_csv,dtype={'row_id':str},low_memory=False)
      print('[candidate grid reused]',cand.shape,ikh.shape,flush=True)
    else:
      cand,ikh=b.candidate_features(combined,pred,feat)
      cand.to_csv(cand_csv,index=False); ikh.to_csv(ikh_csv,index=False)
    predsmall=pred[['dataset','group','unit_label','row_id','estimator_display','error_m']]
    keys=['dataset','group','unit_label','row_id']
    cb=[];cs=[];cab=[];cas=[]
    for M,g in cand.groupby('M'):
      ld=predsmall.merge(g,on=keys,how='left',validate='many_to_one');cc=make_cache(ld,b.CANDIDATE_SENSITIVE)
      by,sm=eval_disc(cc,base_tm,b.CANDIDATE_SENSITIVE);ab,asm=eval_assoc(cc,b.CANDIDATE_SENSITIVE)
      by['M']=M;sm['M']=M;ab['M']=M;asm['M']=M;cb.append(by);cs.append(sm);cab.append(ab);cas.append(asm)
      print('[candidate M]',M,flush=True)
    cb=pd.concat(cb);cs=pd.concat(cs);cab=pd.concat(cab);cas=pd.concat(cas)
    basecs=cs[cs.M.eq(10)];baseas=cas[cas.M.eq(10)]
    stab=[]
    for M,g in cs.groupby('M'):
      ag=cas[cas.M.eq(M)]
      d=baseas[['indicator_id','median_aligned_rho']].merge(ag[['indicator_id','median_aligned_rho']],on='indicator_id',suffixes=('_b','_v'))
      stab.append({'M':M,'auroc_rank_concordance':rankcorr(g,basecs),'association_rank_concordance':float(spearmanr(d.median_aligned_rho_b,d.median_aligned_rho_v).statistic),'top6_overlap':topoverlap(g,basecs)})
    stab=pd.DataFrame(stab)

    ib=[];ism=[];iab=[];ias=[]
    for K,g in ikh.groupby('k_horizon'):
      ld=predsmall.merge(g,on=keys,how='left',validate='many_to_one');cc=make_cache(ld,['I_k'])
      by,sm=eval_disc(cc,base_tm,['I_k']);ab,asm=eval_assoc(cc,['I_k'])
      by['k_horizon']=K;sm['k_horizon']=K;ab['k_horizon']=K;asm['k_horizon']=K;ib.append(by);ism.append(sm);iab.append(ab);ias.append(asm)
    ib=pd.concat(ib);ism=pd.concat(ism);iab=pd.concat(iab);ias=pd.concat(ias)
    print('[candidate all done]',flush=True)

    # constants using fast eval
    const=[];keys=['dataset','group','unit_label','row_id']
    scan=feat[keys+['min_rss_distance','nearest_match_isolation','sigma_fps','rss_gradient_proxy']].copy()
    iso=arr(scan.nearest_match_isolation);d1=arr(scan.min_rss_distance);second=np.where(np.isfinite(iso)&(iso<1),(d1+iso*b.BASE_EPS)/(1-iso),np.nan)
    sp=arr(scan.sigma_fps);gp=arr(scan.rss_gradient_proxy);contrast=np.where(np.isfinite(gp)&(gp>0),sp/gp,b.BASE_EPS)
    for eps in b.EPS_VALUES:
      v=scan[keys].copy();v['nearest_match_isolation']=(second-d1)/(second+eps);v['rss_gradient_proxy']=sp/np.maximum(contrast,eps)
      ld=long_df.drop(columns=['nearest_match_isolation','rss_gradient_proxy']).merge(v,on=keys,how='left',validate='many_to_one');cc=make_cache(ld,['nearest_match_isolation','rss_gradient_proxy'])
      _,asm=eval_assoc(cc);_,dsm=eval_disc(cc,base_tm)
      for iid in ['nearest_match_isolation','rss_gradient_proxy']:
        const.append({'constant_type':'epsilon','value':eps,'indicator_id':iid,'median_aligned_rho':asm.loc[asm.indicator_id.eq(iid),'median_aligned_rho'].iloc[0],
                      'median_auroc':dsm.loc[dsm.indicator_id.eq(iid),'median_auroc'].iloc[0]})
    scan2=feat[keys+['min_rss_distance','sigma_fps']].copy();scan2['sup']=np.nan;scan2['risk']=np.nan
    for u,idx in scan2.groupby('unit_label').indices.items():
      ids=np.asarray(idx,int);scan2.loc[ids,'sup']=1-b.robust01(scan2.loc[ids,'min_rss_distance']);scan2.loc[ids,'risk']=b.robust01(scan2.loc[ids,'sigma_fps'])
    for c in b.CSIGMA_CONSTANTS:
      v=scan2[keys].copy();v['C_sigma']=scan2.sup/(c+scan2.risk)
      ld=long_df.drop(columns=['C_sigma']).merge(v,on=keys,how='left',validate='many_to_one');cc=make_cache(ld,['C_sigma'])
      _,asm=eval_assoc(cc);_,dsm=eval_disc(cc,base_tm)
      const.append({'constant_type':'C_sigma denominator','value':c,'indicator_id':'C_sigma','median_aligned_rho':asm.median_aligned_rho.iloc[0],'median_auroc':dsm.median_auroc.iloc[0]})
    const=pd.DataFrame(const)

    # save
    tables={
      'A5_adaptive_rule_summary.csv':ad_grid,'A5_adaptive_rule_by_condition.csv':ad_by,'A5_adaptive_rule_indicator_summary.csv':ad_sm,
      'A5_fixed_threshold_summary.csv':fx_grid,'A5_fixed_threshold_by_condition.csv':fx_by,'A5_fixed_threshold_indicator_summary.csv':fx_sm,
      'A5_confidence_quantile_summary.csv':conf_summary,'A5_confidence_quantile_by_condition.csv':conf_by,'A5_confidence_quantile_indicator_summary.csv':conf_sm,
      'A5_candidate_M_by_condition.csv':cb,'A5_candidate_M_indicator_summary.csv':cs,'A5_candidate_M_association_by_condition.csv':cab,
      'A5_candidate_M_association_summary.csv':cas,'A5_candidate_M_stability_summary.csv':stab,
      'A5_Ik_horizon_by_condition.csv':ib,'A5_Ik_horizon_discrimination_summary.csv':ism,'A5_Ik_horizon_association_by_condition.csv':iab,
      'A5_Ik_horizon_association_summary.csv':ias,'A5_additive_constant_summary.csv':const,
    }
    for name,df in tables.items(): df.to_csv(T/name,index=False)

    rank=[]
    for _,r in ad_grid.iterrows():
      if r.tail_quantile==.75 and r.multiplier==1.5:continue
      rank.append({'family':'Adaptive rule','label':f"A{int(r.tail_quantile*100)}-{r.multiplier:g}",'rank_concordance':r.rank_concordance})
    for _,r in fx_grid.iterrows():
      if r.fixed_threshold_m==7:continue
      rank.append({'family':'Fixed threshold','label':f"F{r.fixed_threshold_m:g}m",'rank_concordance':r.rank_concordance})
    for _,r in conf_summary[conf_summary.scheme.eq('Adaptive')].iterrows():
      if r.confidence_quantile==.75:continue
      rank.append({'family':'Confidence cutoff','label':f"C{int(r.confidence_quantile*100)}",'rank_concordance':r.risk_rank_concordance})
    for _,r in stab.iterrows():
      if r.M==10:continue
      rank.append({'family':'Candidate size','label':f"M{int(r.M)}",'rank_concordance':r.auroc_rank_concordance})
    rank=pd.DataFrame(rank);rank.to_csv(T/'A5_rank_stability_summary.csv',index=False)
    b.create_figures(rank,fx_sm,conf_summary,stab,ism,const)
    findings={'adaptive_min_rank_concordance':float(ad_grid.rank_concordance.min()),'adaptive_min_top6_overlap':float(ad_grid.top6_overlap.min()),
      'adaptive_sqs_auroc_range':[float(ad_grid.SQS_median_auroc.min()),float(ad_grid.SQS_median_auroc.max())],
      'fixed_min_rank_concordance':float(fx_grid.rank_concordance.min()),'fixed_sqs_auroc_range':[float(fx_grid.SQS_median_auroc.min()),float(fx_grid.SQS_median_auroc.max())],
      'confidence_min_rank_concordance':float(conf_summary.risk_rank_concordance.min()),'confidence_cw_range':[float(conf_summary.median_cw_among_confident_pct.min()),float(conf_summary.median_cw_among_confident_pct.max())],
      'candidate_min_auroc_rank_concordance':float(stab.auroc_rank_concordance.min()),'candidate_min_assoc_rank_concordance':float(stab.association_rank_concordance.min())}
    (OUT/'A5_findings.json').write_text(json.dumps(findings,indent=2));print(json.dumps(findings,indent=2),flush=True)
    print('\nADAPT\n',ad_grid.to_string(index=False),'\nFIX\n',fx_grid.to_string(index=False),'\nCONF\n',conf_summary.to_string(index=False),'\nM\n',stab.to_string(index=False),'\nIK\n',ism.to_string(index=False),'\nCONST\n',const.to_string(index=False),flush=True)

if __name__=='__main__': main()
