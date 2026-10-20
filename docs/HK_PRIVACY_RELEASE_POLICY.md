# HK building-data and reproducibility release boundary (ESWA R3)

This policy applies to the public GitHub source candidate and any future pull request, release archive, dashboard payload, or test fixture. The repository is not yet published as a completed reproducibility package.

## Hard exclusions

* **No HK building floor-plan images or recreations**: no PNG/JPEG/PDF maps, stitched screenshots, scans, and no traced/embedded SVG, CAD, GIS, DXF, vector PDFs, GeoJSON polygons, path descriptions, SVG strings or HTML/JS canvas representations containing identifiable HK floor geometry.
* **No real HK access-point identifiers**, including BSSID/MAC addresses, SSIDs, AP-to-floor lookup tables, ordered AP identifiers that can be linked back to the HK system, fingerprints or raw Wi-Fi captures. Java code implementing the BSSID interface may be released without any observational values.
* **No absolute site coordinates or georeferences**: no latitude/longitude, projected eastings/northings, per-floor origins, coordinate transform back to a true survey frame, surveyed floor footprints or actual reference-point clouds.
* **No trajectory/map reconstruction through indirect means**: even origin-shifted HK RP coordinates, dense query coordinates, ordered tracks, heat maps, vector figures, candidate scatter diagrams, and derived raster grids are blocked from the public release unless a separate disclosure review expressly approves them.

## Data representation

The source-only public candidate uses (1) fully synthetic local XY examples and dummy, locally administered AP addresses, and (2) condition-level scalar summaries with pseudonymous unit labels. The real HK radio maps, scans, positions, and research floor geometry are **not present**.

The separately held full scalar-review ZIP contains per-query indicator values and estimator error-vector residuals, subject to dataset-derivative sharing permission. For a private local-metric observation with ground truth `g=(gx,gy)` and estimator output `p=(px,py)`, define:

`delta_x = px - gx`, `delta_y = py - gy`, `error_2d = sqrt(delta_x**2 + delta_y**2)`.

If an internal local origin `o` is used, `p_local = p - o` and `g_local = g - o`, but their difference is unchanged: `(p-o) - (g-o) = p-g`. **The public release must not include** either actual `p_local` or `g_local` for HK; it may use *approved displacement errors* or higher-level statistical aggregates. Merely subtracting an origin does not anonymize a recognizable building layout.

Use `scripts/export_relative_errors.py` only on private input files already expressed in consistent local **metres**. The script exports only pseudonymous IDs and relative residuals and does not write the input coordinate columns, BSSIDs, floor geometry, or reference origin. It does not establish legal permission to publish the output.

## Enforcement and review

* CI calls `scripts/check_release_safety.py` and `tests/test_privacy_gate.py` before the synthetic demonstration. They reject geo/vector/image files, disguised binary payloads, embedded floor maps, BSSID literals except four documented fictitious addresses in the synthetic importer demonstration, live research record CSVs, nonempty SQLite tables, altered Android vector XML, and unexpected local coordinate payloads.
* The Android asset database in the public source contains an empty schema. The only XML vector drawable with a path is the hash-locked generic Wi-Fi app launcher icon. The legacy website includes one empty SVG plotting surface, not a map.
* Avoid adding a new image or vector to the public source without an explicit inspection and approval, even when the file appears generic. External build artifacts, APKs, screenshots, manuscripts and supplementary materials are not included.
* Before any upload, perform a clean-archive re-extraction, rerun privacy tests, review every new/changed asset manually, and obtain authorization for third-party derived datasets and code licensing. Git ignore rules are secondary; they do not prevent already-tracked or forced additions.

**Do not upload the separate full scalar review ZIP to the public GitHub repository** unless a new review and derivative-distribution authorization explicitly approve each table.
