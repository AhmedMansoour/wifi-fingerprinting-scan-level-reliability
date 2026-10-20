"""Reconstruct the synthetic combined table from versioned synthetic unit CSV.gz files.

All input observations are entirely generated and unrelated to real APs or maps.
"""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples/synthetic_combined"


def main():
    meta = json.loads((BASE / "validation_summary.json").read_text())
    header = b"dataset,group,split,row_id,floor,x,y,rss_json\\n".replace(b"\\n", b"\n")
    data = [header]
    for index in range(1, 11):
        name = f"U{index:02d}"
        with gzip.open(BASE / "units" / f"{name}.csv.gz", "rb") as stream:
            raw = stream.read()
        unit = next(item for item in meta["units"] if item["unit_id"] == name)
        if hashlib.sha256(raw).hexdigest() != unit["sha256"] or not raw.startswith(header):
            raise ValueError(f"Synthetic unit integrity check failed: {name}")
        data.append(raw[len(header):])
    combined = b"".join(data)
    digest = hashlib.sha256(combined).hexdigest()
    if digest != meta["combined_sha256"]:
        raise ValueError("Synthetic combined-data SHA-256 mismatch")
    output = BASE / "combined_all_datasets.csv.gz"
    with output.open("wb") as dest:
        with gzip.GzipFile(filename="", mode="wb", fileobj=dest, compresslevel=7, mtime=0) as gz:
            gz.write(combined)
    print(f"Generated {output} (SHA-256: {digest})")


if __name__ == "__main__":
    main()
