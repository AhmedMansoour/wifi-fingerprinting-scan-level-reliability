"""Freeze and inventory the legacy research state."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
import zipfile

from wifi_integrity.hashing import sha256_file, sha256_stream


def inventory_zip(archive: str | Path, output_csv: str | Path) -> int:
    archive_path = Path(archive)
    rows: list[dict[str, object]] = []
    with zipfile.ZipFile(archive_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            with zf.open(member) as handle:
                digest = sha256_stream(handle)
            rows.append(
                {
                    "archive": archive_path.name,
                    "member": member.filename,
                    "bytes": member.file_size,
                    "compressed_bytes": member.compress_size,
                    "crc32": f"{member.CRC:08x}",
                    "sha256": digest,
                }
            )
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["member"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def inventory_directory(directory: str | Path, output_csv: str | Path) -> int:
    root = Path(directory)
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "modified_utc": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["path"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
