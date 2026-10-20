"""Generate a deterministic, fully synthetic Wi-Fi fingerprinting demo dataset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("examples/synthetic_demo/synthetic_wifi_fingerprints.csv"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    aps = np.array([[0., 0.], [20., 0.], [0., 20.], [20., 20.], [10., 10.], [30., 10.]])
    rows = []
    points = [(x, y) for x in np.linspace(1, 29, 15) for y in np.linspace(1, 19, 10)]
    for split, n_repeat in [("train", 2), ("test", 1)]:
        for i, (x, y) in enumerate(points):
            for rep in range(n_repeat):
                dist = np.linalg.norm(aps - np.array([x, y]), axis=1)
                rss = -35.0 - 20.0 * np.log10(np.maximum(dist, 1.0)) + rng.normal(0, 1.5, len(aps))
                observed = {f"AP{j+1:02d}": float(round(v, 2)) for j, v in enumerate(rss) if v > -88}
                row_id = f"synthetic/{split}/{i:04d}/{rep}"
                rows.append({
                    "dataset": "SYNTHETIC_DEMO", "group": "single_floor", "building": "demo",
                    "floor": 0, "split": split, "row_id": row_id,
                    "source_split": "synthetic", "source_row": len(rows), "x": x, "y": y,
                    "z": 0.0, "latitude": np.nan, "longitude": np.nan,
                    "coordinate_system": "synthetic_local_xy", "rss_format": "sparse_wifi_scan_json",
                    "rss_json": json.dumps(observed, separators=(",", ":")), "rss_count": len(observed),
                    "rss_feature_count": len(aps), "label_0": np.nan, "label_1": np.nan,
                    "label_2": np.nan, "label_3": np.nan, "label_4": np.nan,
                    "label_5": np.nan, "extra_json": json.dumps({"seed": args.seed})
                })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"Wrote {len(rows)} synthetic scans to {args.output}")


if __name__ == "__main__":
    main()
