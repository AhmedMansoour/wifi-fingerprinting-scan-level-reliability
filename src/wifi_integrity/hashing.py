"""Hashing utilities used by manifests and regression gates."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024


def sha256_stream(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    while chunk := handle.read(CHUNK_SIZE):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: str | Path) -> str:
    with Path(path).open("rb") as handle:
        return sha256_stream(handle)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
