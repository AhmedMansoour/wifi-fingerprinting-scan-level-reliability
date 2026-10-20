"""Build the dashboard entirely from fabricated demo scans, never research results."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from wifi_integrity.data.harmonize import parse_rss_json, training_ap_vocabulary, dense_matrix
from wifi_integrity.estimators.base import UnitData
from wifi_integrity.estimators.retrieval import RetrievalEstimator

ROOT=Path(__file__).resolve().parents[1]

def main():
    from subprocess import run
    from sys import executable
    source=ROOT/'results/demo/synthetic_scans.csv'
    if not source.is_file():
        run([executable,str(ROOT/'scripts/generate_synthetic_demo.py'),'--output',str(source)],check=True)
    df=pd.read_csv(source)
    tr=df[df.split=='train'];te=df[df.split=='test']
    tr_dicts=[parse_rss_json(x) for x in tr.rss_json];te_dicts=[parse_rss_json(x) for x in te.rss_json]
    vocab=training_ap_vocabulary(tr_dicts)
    train_mat,train_mask=dense_matrix(tr_dicts,vocab);test_mat,test_mask=dense_matrix(te_dicts,vocab)
    unit=UnitData('SYN','Synthetic demo','synthetic','demo',train_mat,train_mask,test_mat,test_mask,
        tr[['x','y']].to_numpy(float),te[['x','y']].to_numpy(float),tr.row_id.to_numpy(),te.row_id.to_numpy())
    rows=[]
    for estimator_id, label, power in [('knn','KNN',None),('wknn','WKNN',1.0)]:
        prediction=RetrievalEstimator(estimator_id=estimator_id,estimator_label=label,k=5,metric='euclidean',weight_power=power).fit_predict(unit).predictions
        e=prediction.error_2d.to_numpy(float)
        rows.append(dict(unit_id='SYN',estimator=label,n_scans=int(len(e)),mean_error_m=float(e.mean()),
                    median_error_m=float(np.median(e)),p95_error_m=float(np.percentile(e,95)),gross_error_n=int((e>7).sum())))
    result=dict(summary=dict(scan_count=len(te),prediction_count=2*len(te),unit_count=1,estimator_count=2,
        indicator_count=0,condition_count=2,analysis_records=0,
        scope='fully fabricated synthetic demo, no empirical study performance'),estimators=rows,indicators=[])
    target=ROOT/'dashboard/data/metrics.json';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    print(json.dumps({'status':'generated_synthetic_dashboard','records':2,'query_scans':len(te)},indent=2))

if __name__=='__main__':main()
