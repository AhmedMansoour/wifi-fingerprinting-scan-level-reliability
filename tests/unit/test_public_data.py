"""Public checkout has synthetic-only benchmark records."""
from pathlib import Path
import importlib.util
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def test_public_fixture_has_expected_schema_counts_and_synthetic_id():
    path=ROOT/'examples/synthetic_combined/combined_all_datasets.csv.gz'
    df=pd.read_csv(path,dtype={'row_id':'string'})
    assert len(df)==68149
    assert df.split.value_counts().to_dict()=={'train':54520,'test':13629}
    assert df.row_id.str.fullmatch(r'SYN_U\d{2}_(train|test)_\d{6}').all()
    assert df.row_id.is_unique
    assert np.isfinite(df[['x','y']].to_numpy()).all()
    assert not (ROOT/'data/public/hk_relative.csv.gz').exists()
    assert not (ROOT/'reference/approved/legacy_canonical/estimator_predictions_approved.csv.gz').exists()


def test_training_only_ap_vocabulary_excludes_unseen_query_keys():
    from wifi_integrity.data.harmonize import training_ap_vocabulary,dense_matrix,parse_rss_json
    train=[{'AP_00001':-60.0},{'AP_00002':-65.0}]
    query=[{'AP_00003':-55.0,'AP_00001':-70.0}]
    vocab=training_ap_vocabulary(train)
    assert vocab==['AP_00001','AP_00002']
    dense,mask=dense_matrix(query,vocab)
    assert dense.shape==(1,2)
    assert mask.shape==(1,2)
    assert mask.sum()==1


def test_hk_sanitizer_strips_private_identifier_fields_in_isolated_example():
    spec=importlib.util.spec_from_file_location('sanitize',ROOT/'scripts/sanitize_hk_data.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    frame=pd.DataFrame(dict(dataset=['d']*3,group=['g']*3,split=['train','train','test'],
      row_id=['example1','example2','example3'],floor=[2,2,2],x=[20,23,26],y=[30,34,38],
      rss_json=['{"private_device":-50}']*3,latitude=[99]*3))
    public,mapping=module.transform(frame)
    assert 'latitude' not in public
    assert 'private_device' not in public.to_csv(index=False)
    assert public.rss_json.iloc[0]=='{"AP_00001":-50}'
    np.testing.assert_allclose(np.linalg.norm(np.diff(public[['x','y']],axis=0),axis=1),[5,5])
