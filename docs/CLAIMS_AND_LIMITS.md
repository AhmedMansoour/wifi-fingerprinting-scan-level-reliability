# ESWA R3 reproducibility and interpretation audit

| R3 issue | Evidence present | Remaining limitation |
| --- | --- | --- |
| Replace repository placeholder and verify accessibility | The GitHub repository exists and its link can be verified; this local package contains a reproducible scalar-reference analyzer | Candidate is not yet uploaded/approved; public links in manuscript must match actually released files |
| Warning calibration | Java percentile direction/ties/0.80 cutoff and an explicit split-isolation script; `docs/WARNING_CALIBRATION.md` | Retrospective study references must not be presented as prospective withheld calibration |
| 99-run timing | Java source and `docs/ANDROID_TIMING.md` record the exact post-candidate diagnostic computation boundary | Device build/raw 99-run logfile still requires separate verification |
| Cross-dataset robustness | Per-query 10-unit, 8-estimator evaluation residuals and scale-free indicators | Evidence limited to observed units, source conditions, estimators and the manuscript evaluation design |

**Original research package limitations found in the September audit:** native SQS was different from frozen reference on 8,166 of 13,629 rows (max difference ≈0.194591); stored-feature arithmetic reconstruction was exact, but no causal explanation of native discrepancies was established. Native AP-token Transformer and residual CNN adapters were missing, while frozen predictions exist for all eight estimators. CatBoost preprocessing/hyperparameter equivalence remains unverified. The SQS-only case explorer differs from the manuscript's eight-indicator confidence rule. These are **not** repaired or silently declared resolved here.

Source-scan licensing, archive DOI, software license, exact private calibration-input identity, compiled Android build and full end-to-end regeneration are not asserted. Do not upload the manuscript or sensitive floor-plan sources.
