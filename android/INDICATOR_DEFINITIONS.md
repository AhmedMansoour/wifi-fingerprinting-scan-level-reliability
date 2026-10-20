# Indicator Definitions Implemented in Java

The application calculates the following 18 diagnostics in this order.

| # | ID | Display label | Adverse direction |
|---:|---|---|---|
| 1 | `ap_count` | AP count | low |
| 2 | `rss_std` | RSS std. | high |
| 3 | `rss_range` | RSS range | high |
| 4 | `min_rss_distance` | Min. RSS distance | high |
| 5 | `nearest_match_isolation` | Match isolation | low |
| 6 | `max_cosine_similarity` | Cosine similarity | low |
| 7 | `ap_overlap` | Max. AP overlap | low |
| 8 | `mean_ap_overlap` | Mean AP overlap | low |
| 9 | `ap_set_novelty` | AP-set novelty | high |
| 10 | `nearest_rp_distance` | Nearest-RP distance | high |
| 11 | `local_rp_density` | Local RP density | low |
| 12 | `sigma_fps` | Candidate spread | high |
| 13 | `D_cand` | Candidate diameter | high |
| 14 | `I_k` | Neighborhood instability | high |
| 15 | `rss_gradient_proxy` | RSS-gradient proxy | high |
| 16 | `SQS` | SQS | low |
| 17 | `C_sigma` | Cσ | low |
| 18 | `FII` | FII | low |

The Java implementation uses a missing-RSS value of −110 dBm and retrieves ten diagnostic candidates. Condition-relative warning bars use adverse percentiles. A warning is displayed when the adverse percentile reaches or exceeds 0.80.

SQS combines signal support, candidate-geometry support, AP-count support, AP-overlap support, and local-density support. Cσ combines signal support with candidate spread. FII combines signal, AP-count, overlap, match-isolation, and AP-novelty support.
