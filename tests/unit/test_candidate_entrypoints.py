import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import subprocess

import numpy as np
import pandas as pd
import pytest
from wifi_integrity.reliability.sqs import reconstruct_sqs

ROOT = Path(__file__).resolve().parents[2]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_ignores_query_only_aps():
    demo = load_script('demo', ROOT / 'scripts/run_synthetic_demo.py')
    frame = pd.DataFrame([
        {'split':'train','rss_json':json.dumps({'AP1':-50-i}),'x':i,'y':0,'row_id':f't{i}'}
        for i in range(6)
    ] + [{'split':'test','rss_json':'{"AP1":-52}','x':2,'y':0,'row_id':'q'}])
    baseline = demo.evaluate(frame)
    frame.loc[frame.split.eq('test'), 'rss_json'] = '{"AP1":-52,"QUERY_ONLY":-10}'
    assert demo.evaluate(frame) == baseline
    assert baseline['training_ap_count'] == 1


def test_reference_preflight_has_no_output_side_effects(tmp_path):
    runner = load_script('runner', ROOT / 'scripts/reproduce_release.py')
    assert len(runner.missing_reference_inputs(tmp_path)) == 4
    assert list(tmp_path.iterdir()) == []


def test_reference_preflight_fails_before_running_when_inputs_absent(tmp_path):
    import shutil
    (tmp_path/'scripts').mkdir()
    shutil.copy2(ROOT/'scripts/reproduce_release.py',tmp_path/'scripts/reproduce_release.py')
    completed = subprocess.run([sys.executable,str(tmp_path/'scripts/reproduce_release.py'),
                                '--mode','reference','--check-only'],capture_output=True,text=True)
    assert completed.returncode == 2
    assert 'No outputs were generated' in completed.stderr
    assert 'Traceback' not in completed.stderr
    assert not (tmp_path/'results').exists()


def test_empty_android_database_contains_no_records_and_preserves_existing_file(tmp_path):
    android = load_script('empty_db', ROOT / 'android/tools/prepare_empty_database.py')
    output = tmp_path / 'empty.db'
    android.create_empty_database(output)
    with sqlite3.connect(output) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        assert len(tables) == 11
        for (name,) in tables:
            assert con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] == 0
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        android.create_empty_database(output)
    assert output.read_bytes() == before


def test_sqs_direction_and_equal_weight_endpoints():
    features = pd.DataFrame({'unit_label':['u']*3,'min_rss_distance':[0,1,2],
                             'sigma_fps':[0,1,2],'D_cand':[0,1,2],
                             'ap_count':[2,1,0],'ap_overlap':[2,1,0],
                             'local_rp_density':[2,1,0]})
    np.testing.assert_allclose(reconstruct_sqs(features), [1,0.5,0])


def test_sqs_all_missing_stays_unavailable():
    features = pd.DataFrame({'unit_label':['u'], **{k:[np.nan] for k in
                             ['min_rss_distance','sigma_fps','D_cand','ap_count','ap_overlap','local_rp_density']}})
    assert reconstruct_sqs(features).isna().all()
