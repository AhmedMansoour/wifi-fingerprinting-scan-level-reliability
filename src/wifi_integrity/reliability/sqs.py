"""Verified Scan Quality and Support Score (SQS)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def robust_unit_scale(series: pd.Series) -> pd.Series:
    """Clip 5th–95th percentile scaling to [0, 1].

    A degenerate finite range is assigned 0.5, matching the approved implementation.
    """
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    scaled = np.full(values.shape, np.nan, dtype=float)
    finite = np.isfinite(values)
    if not finite.any():
        return pd.Series(scaled, index=series.index)
    lo, hi = np.percentile(values[finite], [5, 95])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        scaled[finite] = 0.5
    else:
        scaled[finite] = np.clip((values[finite] - lo) / (hi - lo), 0.0, 1.0)
    return pd.Series(scaled, index=series.index)


def reconstruct_sqs(features: pd.DataFrame, unit_column: str = "unit_label") -> pd.Series:
    required = {
        unit_column,
        "min_rss_distance",
        "sigma_fps",
        "D_cand",
        "ap_count",
        "ap_overlap",
        "local_rp_density",
    }
    missing = required - set(features.columns)
    if missing:
        raise KeyError(f"Missing SQS columns: {sorted(missing)}")

    result = pd.Series(index=features.index, dtype=float)
    for _, index in features.groupby(unit_column, sort=False).groups.items():
        block = features.loc[index]
        signal = 1.0 - robust_unit_scale(block["min_rss_distance"])
        spread_risk = robust_unit_scale(block["sigma_fps"])
        diameter_risk = robust_unit_scale(block["D_cand"])
        geometry = 1.0 - pd.concat([spread_risk, diameter_risk], axis=1).mean(axis=1, skipna=True)
        ap_count = robust_unit_scale(block["ap_count"])
        overlap = robust_unit_scale(block["ap_overlap"])
        density = robust_unit_scale(block["local_rp_density"])
        result.loc[index] = pd.concat(
            [signal, geometry, ap_count, overlap, density], axis=1
        ).mean(axis=1, skipna=True)
    return result
