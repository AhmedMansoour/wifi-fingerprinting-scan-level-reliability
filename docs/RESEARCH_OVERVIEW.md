# Research overview

The framework examines whether scan-level observations and radio-map support can help diagnose unreliable Wi-Fi fingerprinting estimates. Its evidence covers 10 retained dataset units, 54,520 training scans, 13,629 query scans, and eight positioning estimators.

The 18 diagnostics combine scan statistics, radio-map compatibility, local spatial support, candidate geometry, map ambiguity, and three composite scores. SQS uses equally weighted signal, geometry, AP-count, overlap, and density support. It is an interpretable summary, not a learned probability of correctness.

The analyses examine indicator–error associations, discrimination of adaptive and fixed-threshold gross errors, SQS components and ablations, unit-cluster uncertainty, floor-aware behavior, sensitivity, runtime, and confidently wrong fixes.

Interpretation is bounded by the evaluated units, splits, estimator settings, and acquisition conditions. Cross-dataset consistency does not establish invariance to arbitrary buildings or devices. Auxiliary floor inference is not a general vertical-positioning guarantee. Strong nominal RSS matching does not guarantee spatial coherence or low position error.

Historical cohort-relative analysis, independent prospective calibration, fresh estimator training, stored-reference checks, and device runtime measurements answer different questions. The [reproducibility guide](REPRODUCIBILITY.md) and [calibration protocol](CALIBRATION.md) keep these distinctions explicit.
