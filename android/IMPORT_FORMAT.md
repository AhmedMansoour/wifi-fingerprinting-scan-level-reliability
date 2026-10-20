# Reusable Radio-Map Package Format

The app imports one building from a ZIP package.

```text
building_package.zip
├── manifest.json
├── floors.csv
├── reference_points.csv
├── fingerprints.csv
├── calibration.csv       optional
└── floorplans/            optional
```

## `manifest.json`

```json
{
  "building": {
    "name": "Example Building",
    "unique_id": "ExampleBuilding"
  }
}
```

## `floors.csv`

Required columns:

```text
floor_unique_id,number,name,min_x,min_y,max_x,max_y
```

Optional columns:

```text
rotation_angle,density_radius,floorplan_file
```

Leave `floorplan_file` empty when no floor image exists. The app will use coordinate-only mode.

## `reference_points.csv`

```text
rp_id,floor_unique_id,x,y,lat,lng
```

Only `rp_id`, `floor_unique_id`, `x`, and `y` are mandatory.

## `fingerprints.csv`

```text
rp_id,bssid,rss
```

Use real phone-readable BSSIDs. The importer normalizes case and separators and creates floor-specific numeric AP IDs internally.

## Optional `calibration.csv`

```text
floor_unique_id,estimator,indicator_id,adverse_direction,q05,q95,sorted_values_json
```

`estimator` must exactly match the application setting, for example `WKNN-k10`. A complete profile requires all 18 indicators. The current application uses `M = 10`.

When no exact calibration is imported, the app still provides floor inference, WKNN estimation, candidates, geometry, and raw indicator values. It does not silently reuse another floor or estimator calibration.
