# Which results prove what?

**A reproducible software example, a stored research result, and a freshly retrained model are not interchangeable.** This project makes these evidence levels explicit so that anyone using the repository can understand what they can execute and what has been archived.

| Evidence type | Where | What is verified | What is not claimed |
|---|---|---|---|
| **Fresh public measured-data computation** | `scripts/reproduce_public_integrity.py`, `examples/empirical_integrity/` | Scan-level feature and SQS calculation on four released measured units | Original historical eight-estimator predictions or prospective alarm validation |
| **New HK estimator baseline** | `scripts/reproduce_release.py --mode hk-u09` | Existing KNN/WKNN/Random Forest training and held-out 2D scoring | The full manuscript experiment |
| **Original HK stored results** | `results/empirical/hk_u09/` | 831 scans, eight stored estimator outputs and recorded decisions; consistency checks | Re-fitting all original models and achieving byte-for-byte equality |
| **Approved research summaries** | `results/approved/` | Archived aggregate analysis over ten units/eight estimators, checked for integrity | Reconstructing missing measurements or proprietary source recordings |
| **Fully synthetic test fixture** | `examples/synthetic_combined/` and `dashboard/` | Pipeline integration and software examples | Experimental evidence about actual positioning accuracy |

## Research evaluation scope

The original experiment used 10 units, 54,520 training scans, 13,629 test scans and eight estimators. Its analyses concerned associations between diagnostic quantities and positioning error, gross-error diagnosis, floor-aware behavior, SQS ablation, and computation time.

The four measured units distributed here are **U01–U03 and U09**. For U04–U08 and U10, [obtain the source data from publishers](../DATASET_DOWNLOADS_AND_FORMAT.md). A newly formatted or newly split copy may be useful for a scientific extension, but is not automatically identical to the harmonized original.

## Reproduce and inspect responsibly

```bash
python scripts/reproduce_public_integrity.py
python scripts/check_public_integrity_release.py
python scripts/verify_existing_research_assets.py
```

The first command computes **new outputs**. The next two validate committed records and historical research assets. None of these commands, by itself, establishes a complete eight-estimator retraining of the ten-unit manuscript study.

The numerical checker permits a documented **0.001 difference in U09 mean/median SQS** across supported numerical environments, with per-scan drift reported; near-tie candidate rankings can differ. It does not silently replace frozen historical values.

## Scientific and deployment cautions

- SQS is relative scan-support information, not a calibrated per-scan probability of correctness.
- A low or high indicator is not a universal error rule across every building or device.
- Historical Android post-retrieval diagnostic computation timing is **not** full scan-to-position latency.
- Real floor-plan images/vectors and source HK AP identities are not published.

**Further reading:** [Reproducibility boundaries](../REPRODUCIBILITY.md) · [Original research asset guide](../EXISTING_RESEARCH_ASSETS.md) · [Calibration](../CALIBRATION.md).
