# Indicator guide

[Home](../README.md) · [Research overview](RESEARCH_OVERVIEW.md)

The 18 retained indicators include three composites. The table preserves the supplied configuration identifiers and maps them to the historical output-column names where these differ. “Adverse direction” is the prespecified analysis convention, not a guarantee that the direction holds in every condition.

| Configuration ID | Output column | Indicator | Group | Prespecified adverse direction |
| --- | --- | --- | --- | --- |
| `ap_count` | `ap_count` | AP count | Scan statistics | Low |
| `rss_std` | `rss_std` | RSS standard deviation | Scan statistics | High |
| `rss_range` | `rss_range` | RSS range | Scan statistics | High |
| `min_rss_distance` | `min_rss_distance` | Minimum RSS distance | Scan–map compatibility | High |
| `nearest_match_isolation` | `nearest_match_isolation` | Nearest-match isolation | Scan–map compatibility | Low |
| `max_cosine_similarity` | `max_cosine_similarity` | Nearest-match cosine similarity | Scan–map compatibility | Low |
| `ap_overlap` | `ap_overlap` | Maximum AP overlap | Scan–map compatibility | Low |
| `mean_ap_overlap` | `mean_ap_overlap` | Mean AP overlap | Scan–map compatibility | Low |
| `ap_set_novelty` | `ap_set_novelty` | AP-set novelty | Scan–map compatibility | High |
| `nearest_rp_distance` | `nearest_rp_distance` | Nearest-RP distance | Spatial support | High |
| `local_rp_density` | `local_rp_density` | Local RP density | Spatial support | Low |
| `sigma_fps` | `sigma_fps` | Candidate spatial spread | Candidate geometry | High |
| `d_cand` | `D_cand` | Candidate-set diameter | Candidate geometry | High |
| `i_k` | `I_k` | Cumulative-neighborhood instability | Candidate geometry | High |
| `rss_gradient_proxy` | `rss_gradient_proxy` | RSS-gradient uncertainty proxy | Radio-map ambiguity | High |
| `sqs` | `SQS` | Scan Quality and Support Score | Composite support | Low |
| `c_sigma` | `C_sigma` | Signal-to-spread support score | Composite support | Low |
| `fii` | `FII` | Fingerprint Integrity Index | Composite support | Low |

## SQS and warning interpretation

SQS combines signal support, candidate-geometry support, AP-count support, AP-overlap support, and local-density support. Its nominal component weights are equal. It summarizes diagnostic support; it is not a learned error predictor or a calibrated probability.

A condition-relative adverse percentile describes the position of an indicator within a reference distribution. The reference population, fitted scaling, unavailable-value policy, and warning threshold must be stated when interpreting a score or moving from offline analysis to new live scans.

RSS standard deviation and RSS range do not consistently follow their prespecified adverse directions in the current study. Their configuration signs must not be presented as universal reliability rules. Similarly, favorable RSS matching alone does not establish that candidate locations are spatially coherent.
