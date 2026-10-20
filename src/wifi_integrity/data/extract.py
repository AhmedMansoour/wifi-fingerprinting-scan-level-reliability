"""Secure extraction and direct access to frozen source archives."""
from __future__ import annotations

from pathlib import Path
import shutil
import zipfile


class UnsafeArchiveError(ValueError):
    """Raised if an archive member would escape the destination."""


def safe_extract_archive(archive: str | Path, destination: str | Path) -> Path:
    archive_path = Path(archive)
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    base = destination_path.resolve()
    with zipfile.ZipFile(archive_path) as zf:
        for member in zf.infolist():
            target = (destination_path / member.filename).resolve()
            if target != base and base not in target.parents:
                raise UnsafeArchiveError(f"Unsafe archive member: {member.filename}")
        zf.extractall(destination_path)
    return destination_path


def extract_member(archive: str | Path, member: str, output: str | Path) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        if member not in zf.namelist():
            raise FileNotFoundError(f"Archive member not found: {member}")
        with zf.open(member) as source, output_path.open("wb") as target:
            shutil.copyfileobj(source, target)
    return output_path
