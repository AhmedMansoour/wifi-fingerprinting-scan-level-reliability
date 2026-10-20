"""Non-sensitive external-source CSV conversion tests."""
from pathlib import Path
import json
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from import_external_unit import export


def test_import_paired_with_missing_sentinel_and_one_translation(tmp_path):
    src=tmp_path/'source';src.mkdir()
    pd.DataFrame([[-60,100,-80],[-65,-90,100]]).to_csv(src/'train_rss.csv',index=False)
    pd.DataFrame([[100,200,0],[102,205,1]]).to_csv(src/'train_xy.csv',index=False)
    pd.DataFrame([[-68,-85,100]]).to_csv(src/'test_rss.csv',index=False)
    pd.DataFrame([[103,207,1]]).to_csv(src/'test_xy.csv',index=False)
    meta=export('U04','paired',tmp_path/'units',train_rss=src/'train_rss.csv',
      train_coords=src/'train_xy.csv',test_rss=src/'test_rss.csv',test_coords=src/'test_xy.csv',floor_index=2)
    assert meta['train']==2 and meta['test']==1
    frame=pd.read_csv(tmp_path/'units/U04.csv.gz')
    assert frame.columns.tolist()==['dataset','group','split','row_id','floor','x','y','rss_json']
    assert (frame['x'].tolist(),frame['y'].tolist())==([0,2,3],[0,5,7])
    assert json.loads(frame.iloc[0]['rss_json'])=={'AP1':-60.0,'AP3':-80.0}
    assert json.loads(frame.iloc[2]['rss_json'])=={'AP1':-68.0,'AP2':-85.0}


def test_import_wide_building_filter(tmp_path):
    src=tmp_path/'source';src.mkdir()
    train=pd.DataFrame({'BUILDINGID':[0,1,0],'LONGITUDE':[10,20,12],
                        'LATITUDE':[100,150,101],'FLOOR':[0,1,2],
                        'WAP001':[-60,-70,100],'WAP002':[-80,100,-75]})
    test=pd.DataFrame({'BUILDINGID':[0,1],'LONGITUDE':[14,18],
                       'LATITUDE':[104,148],'FLOOR':[1,0],
                       'WAP001':[-65,-67],'WAP002':[-82,-70]})
    train.to_csv(src/'train.csv',index=False);test.to_csv(src/'test.csv',index=False)
    meta=export('U01','wide',tmp_path/'out',train=src/'train.csv',test=src/'test.csv',
        x_column='LONGITUDE',y_column='LATITUDE',floor_column='FLOOR',
        building_column='BUILDINGID',building_value='0',ap_prefix='WAP')
    assert meta['train']==2 and meta['test']==1
    frame=pd.read_csv(tmp_path/'out/U01.csv.gz')
    assert frame['x'].tolist()==[0,2,4]
    assert frame['y'].tolist()==[0,1,4]
    assert json.loads(frame.iloc[1]['rss_json'])=={'AP2':-75.0}
