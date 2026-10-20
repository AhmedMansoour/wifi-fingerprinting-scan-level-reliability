"""Build or verify SHA-256 checksums for exactly the tracked public files.

Run after reviewing file changes:
    python scripts/refresh_release_manifest.py --write
    python scripts/refresh_release_manifest.py --check
The manifest itself is excluded to avoid a circular checksum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "metadata" / "public_release_manifest.json"
EXCLUDE = {"metadata/public_release_manifest.json"}


def make_manifest():
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        check=True, capture_output=True
    )
    entries = []
    for name in sorted(x.decode("utf-8") for x in result.stdout.split(b"\x00") if x):
        if name in EXCLUDE:
            continue
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Tracked file missing or symlink: {name}")
        contents = path.read_bytes()
        entries.append({
            "path": name,
            "size_bytes": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
        })
    return {
        "release_kind": "PUBLIC_SOURCE_SYNTHETIC_HK_UJI",
        "empirical_data_included": True,
        "synthetic_fixture_scans": 68149,
        "source": "byte-accurate tracked checkout",
        "files": entries,
    }


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = make_manifest()
    if args.write:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(expected['files'])} checksums")
        return 0
    if not MANIFEST.is_file():
        print("Manifest missing", file=sys.stderr)
        return 1
    actual = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if actual == expected:
        print(f"PASS: verified {len(expected['files'])} tracked file checksums")
        return 0
    old = {row["path"]: row for row in actual.get("files", [])}
    new = {row["path"]: row for row in expected["files"]}
    print(json.dumps({
        "missing": sorted(new.keys() - old.keys()),
        "obsolete": sorted(old.keys() - new.keys()),
        "changed": sorted(k for k in new.keys() & old.keys() if new[k] != old[k]),
        "release_kind_mismatch": actual.get("release_kind") != expected["release_kind"],
    }, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
