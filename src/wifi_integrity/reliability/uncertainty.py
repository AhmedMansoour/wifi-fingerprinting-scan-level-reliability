"""Unit-cluster bootstrap from the A3 numerical analysis."""

import numpy as np
import pandas as pd
B = 10000
SEED = 20260725

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
