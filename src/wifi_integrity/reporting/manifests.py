"""Release-manifest construction."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path

from wifi_integrity.hashing import sha256_file


def build_release_manifest(root: str | Path, output: str | Path) -> dict[str, object]:
    root_path = Path(root)
    records = []
    excluded_parts = {".git", ".pytest_cache", "__pycache__"}
    selected = subprocess.check_output(["git", "-C", str(root_path), "ls-files", "-z"]).decode().split("\0")
    for path in sorted(root_path / name for name in selected if name):
        if not path.is_file() or any(part in excluded_parts for part in path.parts):
            continue
        if path.resolve() == Path(output).resolve():
            continue
        records.append(
            {
                "path": path.relative_to(root_path).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "scope": "tracked publication files",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(records),
        "files": records,
    }
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
