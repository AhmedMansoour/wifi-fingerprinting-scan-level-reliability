# Native positioning estimators

| CLI identifier | Estimator | Dependency |
|---|---|---|
| `knn` | K-nearest neighbors | Core |
| `wknn` | Weighted K-nearest neighbors | Core |
| `random_forest` | Random forest | Core |
| `extra_trees` | Extra trees | Core |
| `hgb` | Histogram-based gradient boosting | Core |
| `catboost` | CatBoost multi-output regression | `catboost` extra |
| `transformer_ap` | AP-token Transformer | `transformer` extra |
| `residual_cnn` | Residual CNN | `cnn` extra |

```bash
python -m pip install -e ".[dev,catboost,transformer,cnn]"
python scripts/check_native_estimators.py --require-all
python scripts/prepare_hk_data.py
python -m wifi_integrity benchmark-native --units U09 --estimators catboost,transformer_ap,residual_cnn
```

The smoke command fits all eight adapters on a small synthetic problem. Neural adapters run only two epochs in this check; this establishes executable fit/inference paths, not scientific accuracy.

The neural training functions were recovered from the original source workspace. The public adapters retain their training logic and return fitted models and training-only transforms for separate inference. AP-token defaults are 128 selected APs, 60 maximum epochs, batch size 256, and seed 42. The residual CNN uses the recovered residual architecture, train-only standardization, and a training/validation partition for early stopping. Source hashes and adaptations are recorded in `metadata/source_provenance.json`.

The CatBoost adapter selects up to 128 APs using training observation frequency/variance, supplies RSS and observation-mask features, uses a 15% training-validation split, and defaults to 800 iterations, depth 6, learning rate 0.05, and seed 42. KNN/WKNN settings are read from the stored per-unit study estimator names.

Fresh outputs go to `results/predictions/estimator_predictions_native.csv.gz`. They are kept distinct from reference predictions. Exact historical equality is not promised for all estimators or environments. The validation record states which native experiments were actually run.
