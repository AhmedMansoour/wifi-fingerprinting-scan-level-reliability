"""Website indicator atlas provenance, formula and source-link regression checks."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

EXPECTED_IDS={'ap_count','rss_std','rss_range','min_rss_distance','nearest_match_isolation',
' max_cosine_similarity','ap_overlap','mean_ap_overlap','ap_set_novelty',
'nearest_rp_distance','local_rp_density','sigma_fps','d_cand','i_k','rss_gradient_proxy',
'sqs','c_sigma','fii'}
EXPECTED_IDS={key.strip() for key in EXPECTED_IDS}

def inventory():
    return json.loads((ROOT/'docs/assets/indicator-atlas/indicators.json').read_text())

def test_all_eighteen_with_exact_ids_and_equations():
    rows=inventory()
    assert len(rows)==18
    assert {r['id'] for r in rows}==EXPECTED_IDS
    assert len([r for r in rows if r['group']=='Composite support'])==3
    assert all(r['definition'] and r['eq'] and r['details'] and r['adverse'] for r in rows)
    assert next(r for r in rows if r['id']=='nearest_rp_distance')['kind']=='estimator'

def test_indicator_math_and_interpretation():
    by={r['id']:r for r in inventory()}
    assert 'd_2-d_1' in by['nearest_match_isolation']['eq']
    assert '10^{-6}' in by['rss_gradient_proxy']['eq']
    assert r'\sigma_{FP}' in by['sigma_fps']['eq']
    assert 'R(' in by['sqs']['eq'] and 'R(' in by['fii']['eq']
    assert by['rss_std']['adverse']=='High*'
    assert by['rss_range']['adverse']=='High*'
    md=(ROOT/'docs/INDICATORS.md').read_text()
    assert sum(f'(`{key}`)' in md for key in EXPECTED_IDS)==18
    assert 'Q_{0.95}' in md

def test_site_links_and_dynamic_local_assets():
    doc=(ROOT/'docs/learn/indicator-atlas.md').read_text()
    index=(ROOT/'docs/assets/indicator-atlas/index.html').read_text()
    js=(ROOT/'docs/assets/indicator-atlas/atlas.js').read_text()
    css=(ROOT/'docs/assets/indicator-atlas/atlas.css').read_text()
    assert '../../assets/indicator-atlas/index.html' in doc
    assert 'atlas.js' in index and 'indicators.json' in js
    assert 'diagram-container' in index and '<'+'svg' not in index
    assert '../interactive/sample_scans.json' in js
    assert 'nearest_rp_distance' in js
    assert 'Pause animation' in index and '@keyframes' in css
    assert 'schematic' in js and 'no' in doc.lower()
    assert 'indicator-atlas.md' in (ROOT/'mkdocs.yml').read_text()

def test_original_native_composites_reconstruct():
    import subprocess,sys
    result=subprocess.run([sys.executable,str(ROOT/'scripts/export_indicator_composites.py'),'--check'],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0, result.stdout+'\n'+result.stderr
    data=json.loads((ROOT/'docs/assets/indicator-atlas/composites.json').read_text())
    assert sum(map(len,data['units'].values()))==88
    assert data['no_fabricated_warning_labels'] is True
    assert all(set(row)=={'signal','spread_risk','ap_count','ap_overlap','isolation','inverse_novelty'} for unit in data['units'].values() for row in unit.values())
