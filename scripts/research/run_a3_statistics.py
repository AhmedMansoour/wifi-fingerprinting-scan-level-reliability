from __future__ import annotations
from research_paths import REPO, WORKSPACE, output_dir


from pathlib import Path
import json
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.neighbors import KDTree
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

ROOT = WORKSPACE
A2 = (WORKSPACE / "reference/A2")
OUT = output_dir("A3")
TABLES = OUT / 'tables'
FIGS = OUT / 'figures'
SCRIPTS = OUT / 'scripts'
for d in [OUT, TABLES, FIGS, SCRIPTS]: d.mkdir(parents=True, exist_ok=True)

FEATURE_PATH = ROOT/'data/processed/scan_level_reliability_indicator_features.csv.gz'
PRED_PATH = ROOT/'data/processed/all_estimator_predictions_10like_units_plus_catboost.csv.gz'
COMBINED_PATH = ROOT/'data/interim/datasets_combined_all/combined_all_datasets.csv'
GROSS_ADP_PATH = ROOT/'results/tables/gross_error_discrimination_by_condition_adaptive_iqr.csv'
GROSS_FIX_PATH = ROOT/'results/tables/gross_error_discrimination_by_condition_fixed_7m.csv'
CW_PATH = ROOT/'results/tables/confidently_wrong_indicator_discrimination_by_condition.csv'
A2_DICT_PATH = A2/'A2_core_indicator_dictionary_18.csv'

EST_ORDER = ['KNN','WKNN','Random Forest','Extra Trees','Gradient Boosting','CatBoost','Transformer','Residual CNN']
EST_SHORT = {'KNN':'KNN','WKNN':'WKNN','Random Forest':'RF','Extra Trees':'ET','Gradient Boosting':'HGB','CatBoost':'Cat','Transformer':'Trf','Residual CNN':'ResCNN'}
FAMILY_COLORS = {
    'Scan statistics':'#56B4E9',
    'Radio-map compatibility':'#E69F00',
    'Local spatial support':'#0072B2',
    'Candidate geometry':'#D55E00',
    'Map ambiguity':'#CC79A7',
    'Composite support':'#009E73',
}
SEED = 20260725
B = 10000
ALPHA = 0.05


def ensure_unit_label(df):
    df=df.copy()
    if 'unit_label' not in df:
        if 'unit' in df: df['unit_label']=df['unit'].astype(str)
        else: df['unit_label']=df['dataset'].astype(str)+' / '+df['group'].astype(str)
    return df


def safe_xy(df):
    x='x' if 'x' in df.columns else 'x_true'; y='y' if 'y' in df.columns else 'y_true'
    return df[[x,y]].apply(pd.to_numeric, errors='coerce').to_numpy(float)


def add_nearest_rp(long_df, combined):
    long_df=long_df.copy(); long_df['nearest_rp_distance']=np.nan
    for unit, idx in long_df.groupby('unit_label', observed=False).groups.items():
        part=long_df.loc[idx]; ds=str(part.dataset.iloc[0]); group=str(part.group.iloc[0])
        train=combined[(combined.dataset.astype(str)==ds)&(combined.group.astype(str)==group)&(combined.split.astype(str).str.lower()=='train')]
        if train.empty: continue
        xy=safe_xy(train); xy=xy[np.isfinite(xy).all(1)]
        if not len(xy): continue
        tree=KDTree(np.unique(xy,axis=0))
        predxy=long_df.loc[idx,['x_pred','y_pred']].apply(pd.to_numeric, errors='coerce').to_numpy(float)
        valid=np.isfinite(predxy).all(1); d=np.full(len(predxy),np.nan)
        if valid.any(): d[valid]=tree.query(predxy[valid],k=1)[0][:,0]
        long_df.loc[idx,'nearest_rp_distance']=d
    return long_df


def bh_adjust(pvalues):
    p=np.asarray(pvalues,float); n=len(p)
    order=np.argsort(p); ranked=p[order]
    q=ranked*n/np.arange(1,n+1)
    q=np.minimum.accumulate(q[::-1])[::-1]
    q=np.clip(q,0,1)
    out=np.empty(n,float); out[order]=q
    return out


def _bootstrap_unit_counts(units, b=B, seed=SEED):
    units=list(units)
    rng=np.random.default_rng(seed)
    counts=rng.multinomial(len(units), np.full(len(units),1.0/len(units)), size=b)
    return units, counts


def _weighted_median_replicates(values, unit_codes, counts):
    """Median after repeating every condition row by its sampled unit count."""
    order=np.argsort(values)
    v=values[order]
    uc=unit_codes[order]
    w=counts[:,uc]
    cum=np.cumsum(w,axis=1)
    total=cum[:,-1]
    k1=(total-1)//2
    k2=total//2
    i1=(cum>k1[:,None]).argmax(axis=1)
    i2=(cum>k2[:,None]).argmax(axis=1)
    return (v[i1]+v[i2])/2.0


def cluster_boot_ci(df, value_col, stat='median', b=B, seed=SEED):
    d=df[['unit_label',value_col]].copy()
    d[value_col]=pd.to_numeric(d[value_col], errors='coerce')
    d=d[np.isfinite(d[value_col])]
    if d.empty: return np.nan,np.nan,np.nan
    vals=d[value_col].to_numpy(float)
    point=float(np.median(vals) if stat=='median' else np.mean(vals))
    units=sorted(d.unit_label.unique().tolist())
    code_map={u:i for i,u in enumerate(units)}
    codes=d.unit_label.map(code_map).to_numpy(int)
    _,counts=_bootstrap_unit_counts(units,b=b,seed=seed)
    if stat=='median':
        boots=_weighted_median_replicates(vals,codes,counts)
    else:
        w=counts[:,codes]
        boots=(w*vals[None,:]).sum(axis=1)/w.sum(axis=1)
    lo,hi=np.quantile(boots,[.025,.975])
    return point,float(lo),float(hi)


def cluster_boot_prop_ci(df, bool_col, b=B, seed=SEED):
    d=df[['unit_label',bool_col]].dropna().copy()
    if d.empty: return np.nan,np.nan,np.nan
    d[bool_col]=d[bool_col].astype(float)
    return cluster_boot_ci(d.rename(columns={bool_col:'value'}),'value',stat='mean',b=b,seed=seed)

def build_long():
    feat=ensure_unit_label(pd.read_csv(FEATURE_PATH,dtype={'row_id':str},low_memory=False))
    pred=ensure_unit_label(pd.read_csv(PRED_PATH,dtype={'row_id':str},low_memory=False))
    comb=ensure_unit_label(pd.read_csv(COMBINED_PATH,low_memory=False))
    pred=pred[pred.estimator_display.isin(EST_ORDER)].copy()
    keep=['dataset','group','unit_label','row_id','estimator_display','error_m','x_pred','y_pred']
    long=pred[keep].merge(feat.drop(columns=[c for c in ['x_true','y_true'] if c in feat]),on=['dataset','group','unit_label','row_id'],how='left',validate='many_to_one')
    long=add_nearest_rp(long,comb)
    return long


def association_analysis(long, specs):
    rows=[]
    for (unit,est),g in long.groupby(['unit_label','estimator_display'],observed=False):
        for _,s in specs.iterrows():
            iid=s.indicator_id
            x=pd.to_numeric(g[iid],errors='coerce').to_numpy(float)
            y=pd.to_numeric(g.error_m,errors='coerce').to_numpy(float)
            v=np.isfinite(x)&np.isfinite(y)
            if v.sum()<20 or np.unique(x[v]).size<2 or np.unique(y[v]).size<2: continue
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                rho,p=spearmanr(x[v],y[v])
            if not (np.isfinite(rho) and np.isfinite(p)): continue
            sign=int(s.expected_sign)
            rows.append({
                'indicator_id':iid,'label':s.label,'family':s.family,'expected_sign':sign,
                'unit_label':unit,'estimator_display':est,'estimator_short':EST_SHORT.get(est,est),
                'n_valid_scans':int(v.sum()),'rho':float(rho),'aligned_rho':float(sign*rho),'p_value':float(p),
            })
    out=pd.DataFrame(rows)
    out['q_value_bh']=np.nan
    for _,idx in out.groupby(['unit_label','estimator_display'],observed=False).groups.items():
        out.loc[idx,'q_value_bh']=bh_adjust(out.loc[idx,'p_value'].to_numpy(float))
    out['significant_raw']=out.p_value<ALPHA
    out['significant_bh']=out.q_value_bh<ALPHA
    return out


def summarize_assoc(cond):
    rows=[]
    for iid,g in cond.groupby('indicator_id',sort=False):
        r=g.iloc[0]
        med,lo,hi=cluster_boot_ci(g,'aligned_rho',seed=SEED+sum(map(ord,str(iid))))
        cons,conslo,conshi=cluster_boot_prop_ci(g.assign(expected_direction=g.aligned_rho>0),'expected_direction',seed=SEED+100+sum(map(ord,str(iid))))
        raw,rawlo,rawhi=cluster_boot_prop_ci(g.assign(sig=g.significant_raw),'sig',seed=SEED+200+sum(map(ord,str(iid))))
        bh,bhlo,bhhi=cluster_boot_prop_ci(g.assign(sig=g.significant_bh),'sig',seed=SEED+300+sum(map(ord,str(iid))))
        rows.append({
            'indicator_id':iid,'label':r.label,'family':r.family,'expected_sign':int(r.expected_sign),
            'n_conditions':len(g),'median_aligned_rho':med,'ci95_low_aligned_rho':lo,'ci95_high_aligned_rho':hi,
            'direction_consistency_pct':100*cons,'ci95_low_direction_pct':100*conslo,'ci95_high_direction_pct':100*conshi,
            'raw_significant_pct':100*raw,'ci95_low_raw_significant_pct':100*rawlo,'ci95_high_raw_significant_pct':100*rawhi,
            'bh_significant_pct':100*bh,'ci95_low_bh_significant_pct':100*bhlo,'ci95_high_bh_significant_pct':100*bhhi,
            'n_bh_significant':int(g.significant_bh.sum()),
        })
    return pd.DataFrame(rows).sort_values(['median_aligned_rho','n_conditions'],ascending=[False,False]).reset_index(drop=True)


def normalize_gross_labels(df,specs):
    m=specs.set_index('indicator_id')[['label','family','expected_sign']]
    d=df.copy()
    for c in ['label','family','expected_sign']:
        d[c]=d.indicator_id.map(m[c])
    return d


def summarize_metric_ci(cond, prefix=''):
    rows=[]
    for iid,g in cond.groupby('indicator_id',sort=False):
        r=g.iloc[0]
        au,al,ah=cluster_boot_ci(g,'auroc',seed=SEED+400+sum(map(ord,str(prefix)+str(iid)+'a')))
        ap,pl,ph=cluster_boot_ci(g,'auprc',seed=SEED+500+sum(map(ord,str(prefix)+str(iid)+'p')))
        lift,ll,lh=cluster_boot_ci(g,'auprc_lift',seed=SEED+600+sum(map(ord,str(prefix)+str(iid)+'l')))
        prev,vl,vh=cluster_boot_ci(g,'gross_error_prevalence_pct',seed=SEED+700+sum(map(ord,str(prefix)+str(iid)+'v')))
        rows.append({
            'indicator_id':iid,'label':r.label,'family':r.family,'n_conditions':len(g),
            'median_auroc':au,'ci95_low_auroc':al,'ci95_high_auroc':ah,
            'median_auprc':ap,'ci95_low_auprc':pl,'ci95_high_auprc':ph,
            'median_auprc_lift':lift,'ci95_low_auprc_lift':ll,'ci95_high_auprc_lift':lh,
            'median_prevalence_pct':prev,'ci95_low_prevalence_pct':vl,'ci95_high_prevalence_pct':vh,
        })
    return pd.DataFrame(rows).sort_values(['median_auroc','median_auprc'],ascending=[False,False]).reset_index(drop=True)


def make_assoc_figure(cond,summ):
    plt.rcParams.update({'figure.dpi':130,'savefig.dpi':500,'font.family':'serif','font.size':8,'axes.titlesize':9,'axes.labelsize':8.2,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':6.8,'pdf.fonttype':42,'ps.fonttype':42})
    fig=plt.figure(figsize=(7.3,9.2)); gs=fig.add_gridspec(3,2,height_ratios=[1.65,.9,1.35],width_ratios=[1.38,.95],hspace=.34,wspace=.08)
    ax1=fig.add_subplot(gs[0:2,0]); ax2=fig.add_subplot(gs[0:2,1]); ax3=fig.add_subplot(gs[2,:])
    order=summ.indicator_id.tolist(); ypos=np.arange(len(order)); lm=summ.set_index('indicator_id').label.to_dict(); fm=summ.set_index('indicator_id').family.to_dict()
    for i,iid in enumerate(order):
        g=cond[cond.indicator_id.eq(iid)]; vals=g.aligned_rho.to_numpy(float); color=FAMILY_COLORS.get(fm[iid],'0.4')
        rng=np.random.default_rng(SEED+i); jit=rng.uniform(-.12,.12,len(vals)); ax1.scatter(vals,np.full(len(vals),i)+jit,s=7,color='0.75',alpha=.5,edgecolor='none')
        rr=summ[summ.indicator_id.eq(iid)].iloc[0]
        ax1.hlines(i,rr.ci95_low_aligned_rho,rr.ci95_high_aligned_rho,color=color,lw=2.2)
        ax1.scatter(rr.median_aligned_rho,i,s=24,color=color,edgecolor='black',lw=.3,zorder=3)
    ax1.axvline(0,color='.25',lw=.75,ls='--'); ax1.set_yticks(ypos); ax1.set_yticklabels([lm[x] for x in order],fontsize=7); ax1.invert_yaxis(); ax1.set_xlabel('Aligned Spearman association'); ax1.set_title('(a) Median association with 95% CI',loc='left',pad=3)
    vals=summ.direction_consistency_pct.to_numpy(float); colors=[FAMILY_COLORS.get(x,'0.4') for x in summ.family]
    ax2.barh(ypos,vals,color=colors,edgecolor='.35',lw=.3,height=.62)
    low=vals-summ.ci95_low_direction_pct.to_numpy(float); high=summ.ci95_high_direction_pct.to_numpy(float)-vals
    ax2.errorbar(vals,ypos,xerr=np.vstack([low,high]),fmt='none',ecolor='0.2',elinewidth=.7,capsize=1.5)
    ax2.axvline(50,color='.25',lw=.75,ls='--'); ax2.set_xlim(0,103); ax2.set_yticks(ypos); ax2.set_yticklabels(['']*len(ypos)); ax2.invert_yaxis(); ax2.set_xlabel('Expected-direction consistency (%)'); ax2.set_title('(b) Direction consistency with 95% CI',loc='left',pad=3)
    for y,v,n in zip(ypos,vals,summ.n_conditions): ax2.text(v-1.2 if v>=85 else v+1.2,y,f'{v:.0f}% ({n})',ha='right' if v>=85 else 'left',va='center',fontsize=5.8)
    top=summ.head(10).indicator_id.tolist(); mat=cond[cond.indicator_id.isin(top)].pivot_table(index='indicator_id',columns='estimator_display',values='aligned_rho',aggfunc='median').reindex(index=top,columns=EST_ORDER); data=mat.to_numpy(float); finite=data[np.isfinite(data)]; vmax=max(np.percentile(finite,95),.25)
    im=ax3.imshow(data,aspect='auto',cmap='viridis',vmin=0,vmax=vmax); ax3.set_xticks(range(len(EST_ORDER))); ax3.set_xticklabels([EST_SHORT[x] for x in EST_ORDER]); ax3.set_yticks(range(len(top))); ax3.set_yticklabels([lm[x] for x in top],fontsize=7); ax3.set_title('(c) Estimator-wise median aligned association',loc='left',pad=3)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isfinite(data[i,j]): ax3.text(j,i,f'{data[i,j]:.2f}',ha='center',va='center',fontsize=5.6,color='white' if data[i,j]>vmax*.62 else 'black')
    cb=fig.colorbar(im,ax=ax3,fraction=.028,pad=.015); cb.set_label('Median aligned Spearman',fontsize=7); cb.ax.tick_params(labelsize=6)
    for ax in [ax1,ax2]: ax.tick_params(direction='in',top=True,right=True); ax.grid(True,axis='x',color='.86',lw=.4,alpha=.7); ax.set_axisbelow(True)
    handles=[Patch(facecolor=c,edgecolor='.35',label=f) for f,c in FAMILY_COLORS.items()]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.006),ncol=3,frameon=False,fontsize=7)
    fig.subplots_adjust(left=.22,right=.985,top=.98,bottom=.085)
    fig.savefig(FIGS/'fig_indicator_error_association_A3.png',dpi=500,bbox_inches='tight',pad_inches=.025); fig.savefig(FIGS/'fig_indicator_error_association_A3.pdf',bbox_inches='tight',pad_inches=.025); plt.close(fig)


def make_gross_figure(cond,summ):
    plt.rcParams.update({'figure.dpi':130,'savefig.dpi':500,'font.family':'serif','font.size':8,'axes.titlesize':8.8,'axes.labelsize':8.1,'xtick.labelsize':6.8,'ytick.labelsize':6.8,'legend.fontsize':6.7,'pdf.fonttype':42,'ps.fonttype':42})
    # prevalence matrix from first indicator per condition because prevalence is common within condition
    prev=cond.drop_duplicates(['unit_label','estimator_display']).pivot_table(index='unit_label',columns='estimator_display',values='gross_error_prevalence_pct',aggfunc='first').reindex(columns=EST_ORDER)
    fig=plt.figure(figsize=(8.35,9.2)); gs=fig.add_gridspec(3,2,height_ratios=[1.15,1.38,1.28],width_ratios=[1,1],hspace=.38,wspace=.72)
    axa=fig.add_subplot(gs[0,:]); axb=fig.add_subplot(gs[1,0]); axc=fig.add_subplot(gs[1,1]); axd=fig.add_subplot(gs[2,:])
    data=prev.to_numpy(float); vmax=max(5,np.nanpercentile(data,95)); im=axa.imshow(data,aspect='auto',cmap='YlOrRd',vmin=0,vmax=vmax); axa.set_xticks(range(len(EST_ORDER))); axa.set_xticklabels([EST_SHORT[e] for e in EST_ORDER]); axa.set_yticks(range(len(prev.index))); axa.set_yticklabels([x.split(' / ')[-1].replace('Database_','').replace('Building','B') for x in prev.index],fontsize=6.5)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isfinite(data[i,j]): axa.text(j,i,f'{data[i,j]:.1f}',ha='center',va='center',fontsize=5.7,color='black' if data[i,j]<vmax*.63 else 'white')
    axa.set_title('(a) Adaptive gross-error prevalence (%)',loc='left',pad=3); cb=fig.colorbar(im,ax=axa,fraction=.024,pad=.012); cb.set_label('Gross-error prevalence (%)',fontsize=7); cb.ax.tick_params(labelsize=6.3,direction='in')
    def panel(ax,metric,title,xlabel,topn=14):
        main=summ.sort_values(metric,ascending=False).head(topn); ids=main.indicator_id.tolist(); y=np.arange(len(ids)); condcol='auroc' if metric=='median_auroc' else 'auprc'; lcol='ci95_low_auroc' if condcol=='auroc' else 'ci95_low_auprc'; hcol='ci95_high_auroc' if condcol=='auroc' else 'ci95_high_auprc'
        for i,iid in enumerate(ids):
            rr=main[main.indicator_id.eq(iid)].iloc[0]; color=FAMILY_COLORS.get(rr.family,'0.4'); vals=cond.loc[cond.indicator_id.eq(iid),condcol].to_numpy(float); rng=np.random.default_rng(SEED+1000+i); jit=rng.uniform(-.13,.13,len(vals)); ax.scatter(vals,np.full(len(vals),i)+jit,s=8,color='0.75',alpha=.48,edgecolor='none'); ax.hlines(i,rr[lcol],rr[hcol],color=color,lw=2.1); ax.scatter(rr[metric],i,s=25,color=color,edgecolor='black',lw=.35,zorder=4)
        ax.set_yticks(y); ax.set_yticklabels(main.label.tolist(), fontsize=6.3); ax.invert_yaxis(); ax.set_xlabel(xlabel); ax.set_title(title,loc='left',pad=3); ax.xaxis.set_major_locator(MaxNLocator(5)); ax.tick_params(direction='in',top=True,right=True); ax.grid(True,axis='x',color='.86',lw=.42,alpha=.7); ax.set_axisbelow(True)
        if condcol=='auroc': ax.axvline(.5,color='.25',lw=.75,ls='--'); ax.set_xlim(.40,1.0)
        else: ax.set_xlim(0,max(.25,min(1,np.nanmax(cond.auprc)*1.1)))
    panel(axb,'median_auroc','(b) Median AUROC with 95% CI','AUROC'); panel(axc,'median_auprc','(c) Median AUPRC with 95% CI','AUPRC')
    top=summ.head(10).indicator_id.tolist(); mat=cond[cond.indicator_id.isin(top)].pivot_table(index='indicator_id',columns='estimator_display',values='auroc',aggfunc='median').reindex(index=top,columns=EST_ORDER); arr=mat.to_numpy(float); im2=axd.imshow(arr,aspect='auto',cmap='YlGnBu',vmin=.5,vmax=1); labelmap=summ.set_index('indicator_id').label.to_dict(); axd.set_xticks(range(len(EST_ORDER))); axd.set_xticklabels([EST_SHORT[e] for e in EST_ORDER]); axd.set_yticks(range(len(top))); axd.set_yticklabels([labelmap[i] for i in top]); axd.set_title('(d) Estimator-wise median AUROC',loc='left',pad=3)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            if np.isfinite(arr[i,j]): axd.text(j,i,f'{arr[i,j]:.2f}',ha='center',va='center',fontsize=5.7,color='black' if arr[i,j]<.74 else 'white')
    cb2=fig.colorbar(im2,ax=axd,fraction=.024,pad=.012); cb2.set_label('Median AUROC',fontsize=7); cb2.ax.tick_params(labelsize=6.3,direction='in')
    handles=[Patch(facecolor=c,edgecolor='.35',label=f) for f,c in FAMILY_COLORS.items()]; fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.008),ncol=3,frameon=False,columnspacing=1.1,handlelength=1.2,handletextpad=.45); fig.subplots_adjust(left=.165,right=.988,top=.975,bottom=.085)
    fig.savefig(FIGS/'fig_gross_error_discrimination_A3.png',dpi=500,bbox_inches='tight',pad_inches=.025); fig.savefig(FIGS/'fig_gross_error_discrimination_A3.pdf',bbox_inches='tight',pad_inches=.025); plt.close(fig)


def make_uncertainty_table(assoc,adp,fix,cw_adp,cw_fix):
    leading=['SQS','nearest_rp_distance','sigma_fps','I_k','rss_gradient_proxy','D_cand']
    rows=[]
    for iid in leading:
        ar=assoc.set_index('indicator_id').loc[iid]
        adr=adp.set_index('indicator_id').loc[iid]
        fxr=fix.set_index('indicator_id').loc[iid]
        car=cw_adp.set_index('indicator_id').loc[iid]
        cfr=cw_fix.set_index('indicator_id').loc[iid]
        rows.append({
            'indicator_id':iid,'label':ar.label,
            'rho':ar.median_aligned_rho,'rho_lo':ar.ci95_low_aligned_rho,'rho_hi':ar.ci95_high_aligned_rho,
            'adp_auroc':adr.median_auroc,'adp_auroc_lo':adr.ci95_low_auroc,'adp_auroc_hi':adr.ci95_high_auroc,
            'adp_auprc':adr.median_auprc,'adp_auprc_lo':adr.ci95_low_auprc,'adp_auprc_hi':adr.ci95_high_auprc,
            'fix_auroc':fxr.median_auroc,'fix_auroc_lo':fxr.ci95_low_auroc,'fix_auroc_hi':fxr.ci95_high_auroc,
            'fix_auprc':fxr.median_auprc,'fix_auprc_lo':fxr.ci95_low_auprc,'fix_auprc_hi':fxr.ci95_high_auprc,
            'cw_adp_auroc':car.median_auroc,'cw_adp_auroc_lo':car.ci95_low_auroc,'cw_adp_auroc_hi':car.ci95_high_auroc,
            'cw_fix_auroc':cfr.median_auroc,'cw_fix_auroc_lo':cfr.ci95_low_auroc,'cw_fix_auroc_hi':cfr.ci95_high_auroc,
        })
    return pd.DataFrame(rows)


def write_latex_tables(assoc,adp,fix,cw_adp,cw_fix):
    # All 18 association summary.
    lines=[]
    lines.append(r'\begin{longtable}{@{}p{3.1cm}rrrrrr@{}}')
    lines.append(r'\caption{Association uncertainty and multiple-comparison results for the 18 comparative indicators. The 95\% CIs refer to the cross-condition median and were obtained by resampling evaluation units.}\label{tab:sm_a3_assoc_ci}\\')
    lines.append(r'\toprule')
    lines.append(r'\textbf{Indicator} & \textbf{$N_c$} & \textbf{Median $\tilde\rho$} & \textbf{95\% CI} & \textbf{Direction (\%)} & \textbf{Raw sig. (\%)} & \textbf{BH sig. (\%)}\\')
    lines.append(r'\midrule\endfirsthead')
    lines.append(r'\caption[]{Association uncertainty and multiple-comparison results (continued).}\\\toprule')
    lines.append(r'\textbf{Indicator} & \textbf{$N_c$} & \textbf{Median $\tilde\rho$} & \textbf{95\% CI} & \textbf{Direction (\%)} & \textbf{Raw sig. (\%)} & \textbf{BH sig. (\%)}\\\midrule\endhead')
    for _,r in assoc.iterrows():
        label=str(r.label).replace('&',r'\&')
        lines.append(f"{label} & {int(r.n_conditions)} & {r.median_aligned_rho:.3f} & [{r.ci95_low_aligned_rho:.3f}, {r.ci95_high_aligned_rho:.3f}] & {r.direction_consistency_pct:.1f} & {r.raw_significant_pct:.1f} & {r.bh_significant_pct:.1f} \\\\")
    lines.append(r'\bottomrule\end{longtable}')
    (TABLES/'A3_association_ci_table.tex').write_text('\n'.join(lines),encoding='utf-8')

    for name,df,caption,label in [
        ('adaptive',adp,'Condition-adaptive gross-error discrimination with 95\% CIs for the cross-condition medians.','tab:sm_a3_adp_ci'),
        ('fixed7m',fix,'Fixed 7 m gross-error discrimination with 95\% CIs for the cross-condition medians.','tab:sm_a3_fix_ci'),
    ]:
        lines=[r'\begin{longtable}{@{}p{3.1cm}rrrrr@{}}',f'\\caption{{{caption}}}\\label{{{label}}}\\\\',r'\toprule',r'\textbf{Indicator} & \textbf{$N_c$} & \textbf{AUROC} & \textbf{95\% CI} & \textbf{AUPRC} & \textbf{95\% CI}\\',r'\midrule\endfirsthead',r'\caption[]{Continued.}\\\toprule',r'\textbf{Indicator} & \textbf{$N_c$} & \textbf{AUROC} & \textbf{95\% CI} & \textbf{AUPRC} & \textbf{95\% CI}\\\midrule\endhead']
        for _,r in df.iterrows():
            lbl=str(r.label).replace('&',r'\&')
            lines.append(f"{lbl} & {int(r.n_conditions)} & {r.median_auroc:.3f} & [{r.ci95_low_auroc:.3f}, {r.ci95_high_auroc:.3f}] & {r.median_auprc:.3f} & [{r.ci95_low_auprc:.3f}, {r.ci95_high_auprc:.3f}] \\\\")
        lines.append(r'\bottomrule\end{longtable}')
        (TABLES/f'A3_{name}_ci_table.tex').write_text('\n'.join(lines),encoding='utf-8')

    cw=pd.concat([cw_adp.assign(strategy='Adaptive'),cw_fix.assign(strategy='Fixed 7 m')],ignore_index=True)
    lines=[r'\begin{longtable}{@{}p{2.3cm}p{3.0cm}rrrrr@{}}',r'\caption{Confidently wrong discrimination with 95\% CIs for cross-condition medians.}\label{tab:sm_a3_cw_ci}\\',r'\toprule',r'\textbf{Strategy} & \textbf{Indicator} & \textbf{$N_c$} & \textbf{AUROC} & \textbf{95\% CI} & \textbf{AUPRC} & \textbf{95\% CI}\\',r'\midrule\endfirsthead',r'\caption[]{Continued.}\\\toprule',r'\textbf{Strategy} & \textbf{Indicator} & \textbf{$N_c$} & \textbf{AUROC} & \textbf{95\% CI} & \textbf{AUPRC} & \textbf{95\% CI}\\\midrule\endhead']
    for _,r in cw.iterrows():
        lbl=str(r.label).replace('&',r'\&')
        lines.append(f"{r.strategy} & {lbl} & {int(r.n_conditions)} & {r.median_auroc:.3f} & [{r.ci95_low_auroc:.3f}, {r.ci95_high_auroc:.3f}] & {r.median_auprc:.3f} & [{r.ci95_low_auprc:.3f}, {r.ci95_high_auprc:.3f}] \\\\")
    lines.append(r'\bottomrule\end{longtable}')
    (TABLES/'A3_confidently_wrong_ci_table.tex').write_text('\n'.join(lines),encoding='utf-8')


def main():
    specs=pd.read_csv(A2_DICT_PATH)[['indicator_id','label','family','expected_sign']]
    # Clean family labels for plotting and manuscript terminology.
    fmap={'Composite indicators':'Composite support','Extended reliability':'Candidate geometry'}
    specs['family']=specs.family.replace(fmap)
    specs.loc[specs.indicator_id.eq('rss_gradient_proxy'),'family']='Map ambiguity'
    specs.loc[specs.indicator_id.eq('ap_set_novelty'),'family']='Radio-map compatibility'

    long=build_long()
    assoc_cond=association_analysis(long,specs)
    assoc_sum=summarize_assoc(assoc_cond)

    adp_cond=normalize_gross_labels(pd.read_csv(GROSS_ADP_PATH),specs)
    fix_cond=normalize_gross_labels(pd.read_csv(GROSS_FIX_PATH),specs)
    adp_sum=summarize_metric_ci(adp_cond,'adp')
    fix_sum=summarize_metric_ci(fix_cond,'fix')

    cw=normalize_gross_labels(pd.read_csv(CW_PATH),specs)
    cw_adp_cond=cw[cw.strategy.eq('adaptive_iqr')].copy(); cw_fix_cond=cw[cw.strategy.eq('fixed_7m')].copy()
    cw_adp_sum=summarize_metric_ci(cw_adp_cond,'cw_adp'); cw_fix_sum=summarize_metric_ci(cw_fix_cond,'cw_fix')

    # Save tables.
    assoc_cond.to_csv(TABLES/'A3_indicator_error_association_by_condition_with_bh.csv',index=False)
    assoc_sum.to_csv(TABLES/'A3_indicator_error_association_summary_ci_bh.csv',index=False)
    adp_cond.to_csv(TABLES/'A3_gross_error_adaptive_by_condition.csv',index=False)
    adp_sum.to_csv(TABLES/'A3_gross_error_adaptive_summary_ci.csv',index=False)
    fix_cond.to_csv(TABLES/'A3_gross_error_fixed7m_by_condition.csv',index=False)
    fix_sum.to_csv(TABLES/'A3_gross_error_fixed7m_summary_ci.csv',index=False)
    cw_adp_sum.to_csv(TABLES/'A3_confidently_wrong_adaptive_summary_ci.csv',index=False)
    cw_fix_sum.to_csv(TABLES/'A3_confidently_wrong_fixed7m_summary_ci.csv',index=False)
    uncertainty=make_uncertainty_table(assoc_sum,adp_sum,fix_sum,cw_adp_sum,cw_fix_sum)
    uncertainty.to_csv(TABLES/'A3_leading_indicator_uncertainty_summary.csv',index=False)

    # Correction-family audit.
    fam=(assoc_cond.groupby(['unit_label','estimator_display'],observed=False).agg(n_tests=('p_value','count'),n_raw_sig=('significant_raw','sum'),n_bh_sig=('significant_bh','sum')).reset_index())
    fam.to_csv(TABLES/'A3_bh_correction_families.csv',index=False)
    audit={'n_families':int(len(fam)),'min_tests_per_family':int(fam.n_tests.min()),'max_tests_per_family':int(fam.n_tests.max()),'total_tests':int(len(assoc_cond)),'alpha':ALPHA,'bootstrap_repetitions':B,'bootstrap_cluster':'evaluation unit'}
    (TABLES/'A3_statistical_design.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')

    make_assoc_figure(assoc_cond,assoc_sum)
    make_gross_figure(adp_cond,adp_sum)
    write_latex_tables(assoc_sum,adp_sum,fix_sum,cw_adp_sum,cw_fix_sum)

    # Validation against A2 / submitted point estimates.
    a2=pd.read_csv(A2/'A2_indicator_error_association_summary_18.csv').set_index('indicator_id')
    chk=assoc_sum.set_index('indicator_id').join(a2[['median_aligned_rho']],rsuffix='_a2')
    maxdiff=float((chk.median_aligned_rho-chk.median_aligned_rho_a2).abs().max())
    submitted_adp=pd.read_csv(ROOT/'results/tables/gross_error_discrimination_summary_adaptive_iqr.csv').set_index('indicator_id')
    maxdiff_adp=float((adp_sum.set_index('indicator_id').median_auroc-submitted_adp.median_auroc).abs().max())
    summary_text=[
        'A3 STATISTICAL UNCERTAINTY AND MULTIPLE-COMPARISON ANALYSIS',
        '==========================================================',
        f"BH/FDR families: {len(fam)} unit-estimator conditions; {fam.n_tests.min()}-{fam.n_tests.max()} valid indicator tests per family; {len(assoc_cond)} total tests.",
        f"Cluster bootstrap: {B:,} repetitions, resampling evaluation units and retaining all estimator conditions within each selected unit.",
        f"Maximum difference from A2 median aligned association: {maxdiff:.3e}.",
        f"Maximum difference from submitted adaptive median AUROC: {maxdiff_adp:.3e}.",
        '',
        'Leading association results:',
        assoc_sum.head(8)[['label','median_aligned_rho','ci95_low_aligned_rho','ci95_high_aligned_rho','bh_significant_pct']].to_string(index=False),
        '',
        'Leading adaptive discrimination results:',
        adp_sum.head(8)[['label','median_auroc','ci95_low_auroc','ci95_high_auroc','median_auprc','ci95_low_auprc','ci95_high_auprc']].to_string(index=False),
    ]
    (OUT/'A3_findings.txt').write_text('\n'.join(summary_text),encoding='utf-8')
    print('\n'.join(summary_text[:8]))
    print('\nAssociation top:')
    print(assoc_sum.head(8).to_string(index=False))
    print('\nAdaptive top:')
    print(adp_sum.head(8).to_string(index=False))
    print('\nFixed top:')
    print(fix_sum.head(8).to_string(index=False))
    print('\nCW adaptive top:')
    print(cw_adp_sum.head(6).to_string(index=False))

if __name__=='__main__': main()
