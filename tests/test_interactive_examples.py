"""Regression and provenance checks for browser-only measured data examples."""
import json
from pathlib import Path
import subprocess
import sys
import hashlib

ROOT=Path(__file__).resolve().parents[1]
JSON_PATH=ROOT/'docs/assets/interactive/sample_scans.json'


def test_measured_samples_have_original_sqs_components():
    data=json.loads(JSON_PATH.read_text(encoding='utf-8'))
    assert data['data_kind']=='measured_empirical_fresh_native_computation'
    assert data['no_calibrated_warning_labels'] is True
    assert data['no_retrained_models'] is True
    assert set(data['units'])=={'U01','U02','U03','U09'}
    for unit,meta in data['units'].items():
        samples=meta['examples']
        assert len(samples)==22
        assert len(set(s['row_id'] for s in samples))==22
        assert sum(meta['sqs_histogram_20_bins'])==meta['total_query_scans']
        assert [s['sqs'] for s in samples]==sorted(s['sqs'] for s in samples)
        for row in samples:
            scores=row['components']
            assert set(scores)=={'signal_match','candidate_geometry','ap_count','ap_overlap','local_density'}
            assert all(v is not None and 0<=v<=1 for v in scores.values())
            assert abs(sum(scores.values())/5-row['sqs'])<1e-9
            assert len(row['candidates'])==10
            assert [c['rank'] for c in row['candidates']]==list(range(1,11))
            assert len(row['strongest_ap'])<=10
            assert row['ap_observations']>=len(row['strongest_ap'])
            assert all(ap.startswith('AP') and ap[2:].isdigit() for ap,rss in row['strongest_ap'])
            assert all(-110<=rss<=0 for _,rss in row['strongest_ap'])
            assert len(row['reference'])==len(row['diagnostic_centroid'])==2
            assert all(v>=0 for v in [row['indicators']['sigma_fps'],row['indicators']['D_cand']])


def test_exporter_regenerates_identical_examples():
    proc=subprocess.run([sys.executable,str(ROOT/'scripts/export_interactive_examples.py'),'--check'],
                        cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    assert proc.returncode==0, proc.stdout+'\n'+proc.stderr


def test_visual_assets_are_local_and_linked():
    html=(ROOT/'docs/assets/interactive/index.html').read_text(encoding='utf8')
    js=(ROOT/'docs/assets/interactive/explorer.js').read_text(encoding='utf8')
    guide=(ROOT/'docs/learn/interactive-explorer.md').read_text(encoding='utf8')
    assert 'explorer.js' in html and 'explorer.css' in html
    assert "fetch('sample_scans.json'" in js
    assert 'assets/interactive/index.html' in guide
    assert 'not a calibrated' in guide.lower()
    assert not any(term in html+js for term in ('<'+'svg','data:'+'image/','path'+'Data'))
