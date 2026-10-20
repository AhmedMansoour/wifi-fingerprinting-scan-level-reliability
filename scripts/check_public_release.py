"""Fail closed on restricted material in a prepared GitHub checkout.

Not a legal privacy certification; inspect generated release archives independently.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MAC = re.compile(rb'(?<![A-Fa-f0-9])(?:[A-Fa-f0-9]{2}[:-]){5}[A-Fa-f0-9]{2}(?![A-Fa-f0-9])')
PROHIBITED = {'.png','.jpg','.jpeg','.gif','.webp','.bmp','.tiff','.svg','.pdf','.tex','.docx',
    '.dxf','.dwg','.geojson','.kml','.kmz','.gpx','.shp','.gpkg','.zip','.7z','.rar',
    '.db','.sqlite','.sqlite3','.apk','.aab','.npz','.npy','.pkl','.pickle','.parquet',
    '.onnx','.pt','.pth','.h5','.bin','.so','.class'}
IGNORE_PARTS = {'.git','__pycache__','.pytest_cache','.venv','.mypy_cache','.gradle','build','dist','results','site','.ruff_cache'}
APP_ICON = 'android/app/src/main/res/drawable/ic_launcher_foreground.xml'
APP_ICON_SHA256 = '62759400e1f289a522f3b7c1f441828a3f39908f0837ebb2ceb12e8cee78e73a'
WRAPPER = 'android/gradle/wrapper/gradle-wrapper.jar'
WRAPPER_SHA256 = '81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f'
GZ_PREFIX = 'examples/synthetic_combined/'
GZ_PATHS = {'data/empirical/U01.csv.gz','data/empirical/U02.csv.gz','data/empirical/U03.csv.gz'} | {'data/empirical/hk_u09_test_ordered.csv.gz','data/radio_maps/hk_u09_train.csv.gz'} | {'data/empirical/hk_u09_ap_relative.csv.gz'} | {GZ_PREFIX+'combined_all_datasets.csv.gz'} | {GZ_PREFIX+f'units/U{i:02d}.csv.gz' for i in range(1,11)}
ALLOWED_DATA = {'data/.gitkeep','data/public/README.md','reference/.gitkeep','reference/README.md','data/empirical/hk_u09_ap_relative.csv.gz','data/empirical/hk_u09_test_ordered.csv.gz','data/radio_maps/hk_u09_train.csv.gz','data/empirical/U01.csv.gz','data/empirical/U02.csv.gz','data/empirical/U03.csv.gz'}
EMBED = re.compile(rb'(?:data:image/|<svg\b|<image\b|\bpathData\s*=)', re.I)


def check(root=ROOT):
    root=Path(root).resolve()
    fail=[]; scanned=0
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(x in IGNORE_PARTS for x in path.relative_to(root).parts):continue
        rel=path.relative_to(root).as_posix();data=path.read_bytes();scanned+=1
        if path.is_symlink():fail.append(rel+': symlink not permitted');continue
        if path.suffix.lower() in PROHIBITED or path.name.endswith(('.tar.gz','.tgz')):fail.append(rel+': restricted extension');continue
        if rel.startswith(('reference/approved/','reference/public/')) or (rel.startswith('data/') and rel not in ALLOWED_DATA):
            fail.append(rel+': empirical records not permitted')
        if path.suffix=='.gz':
            if rel not in GZ_PATHS:fail.append(rel+': compressed data not allowlisted')
            elif data[:2]!=b'\x1f\x8b':fail.append(rel+': malformed gzip')
            continue  # Explicitly validated in validate_synthetic_combined.py, not decoded as ordinary UTF-8
        if rel==WRAPPER:
            if hashlib.sha256(data).hexdigest()!=WRAPPER_SHA256:fail.append(rel+': unverified Gradle wrapper binary')
            continue
        if path.suffix in {'.jar','.class'}: fail.append(rel+': unapproved binary');continue
        if b'SQLite format 3' in data[:32] or data.startswith((b'\x89PNG\r\n\x1a\n',b'%PDF-',b'PK\x03\x04')):
            fail.append(rel+': embedded prohibited format');continue
        try:text=data.decode('utf8')
        except UnicodeDecodeError:fail.append(rel+': unknown binary');continue
        if MAC.search(data):fail.append(rel+': MAC/BSSID literal')
        if EMBED.search(data):
            # Generic app launcher symbol is the only approved vector, pinned by hash.
            if rel != APP_ICON or hashlib.sha256(data).hexdigest()!=APP_ICON_SHA256:
                # Empty plot <svg id="casePlot" ...></svg> contains no vector path or map.
                if not (rel=='web/index.html' and
                    b'<svg id="casePlot"' in data and b'<path' not in data and b'<polygon' not in data):
                    if rel!='scripts/check_public_release.py':fail.append(rel+': image/vector markup')
        if rel.startswith('examples/') and path.suffix=='.csv' and rel not in {'examples/.gitkeep'}:
            fail.append(rel+': unapproved plain CSV')
        if rel.endswith('.json'):
            try:
                value=json.loads(text)
                if isinstance(value,dict) and (value.get('type') in ('FeatureCollection','Feature','Polygon','MultiPolygon','LineString','GeometryCollection')
                    or 'geometry' in value and rel!='dashboard/data/metrics.json'):
                    fail.append(rel+': GIS payload')
            except ValueError:fail.append(rel+': invalid JSON')
        if re.search(r'(?i)(?:^|/)(?:floorplans?|site_geometry|raw_scans|private_data|raw_wifi)(?:/|$)',rel):
            fail.append(rel+': restricted directory')
        if rel!='scripts/check_public_release.py' and ('C:\\Users\\' in text or '/Users/ahmd' in text):
            fail.append(rel+': personal absolute path')
    from validate_synthetic_combined import validate
    try: fixture=validate()
    except Exception as exc:fail.append('synthetic fixture failed validation: '+str(exc));fixture={'result':'failed'}
    from validate_hk_empirical import validate as validate_hk
    try: hk = validate_hk(root/'data/empirical/hk_u09_ap_relative.csv.gz')
    except Exception as exc: fail.append('HK validation failed: '+str(exc));hk={'result':'failed'}
    schema=root/'android/app/src/main/assets/database/schema.sql'
    if not schema.is_file():fail.append('Android empty schema missing')
    if list((root/'android/app/src/main/assets/database').glob('*.db')):fail.append('Populated or stored Android DB present')
    license_file=root/'LICENSE'
    if not license_file.is_file() or not license_file.read_text().startswith('MIT License'):
        fail.append('MIT source license missing or invalid')
    return {'result':'passed' if not fail else 'failed','files_scanned':scanned,
        'synthetic_fixture':fixture,'hk_empirical':hk,'errors':fail,'scope':'source, synthetic example and HK empirical U09'}

if __name__ == '__main__':
    x=check();print(json.dumps(x,indent=2));sys.exit(1 if x['errors'] else 0)
