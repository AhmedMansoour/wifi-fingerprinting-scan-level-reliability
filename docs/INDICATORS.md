# Scan-level diagnostic indicators: definitions and equations

**15 diagnostic measurements and three composite scores**, grouped by the source implementation. This page specifies the formulas implemented in `src/wifi_integrity/reliability/indicators.py` and `src/wifi_integrity/reliability/sqs.py`. The direction column is the study’s **prespecified adverse direction**, not a fitted classification threshold or a universal direction of association.

[Open the animated indicator atlas](learn/indicator-atlas.md){ .md-button .md-button--primary } [Inspect measured scans](learn/interactive-explorer.md){ .md-button }

## Notation and computation scope

- $\mathbf q\in\mathbb R^D$: RSS vector for one query, with absent AP features filled at $-110$ dBm; $\mathbf t_j$: training templates, ordered by normalized RSS distance $d_1\leq d_2\leq\cdots$.
- $A_q$ and $A_j$: sets of observed APs in the query and retrieved reference template $j$.
- $\mathbf p_j\in\mathbb R^2$: local reference coordinate of the $j$-th retrieved template; $\bar{\mathbf p}=\frac1{10}\sum_{j=1}^{10}\mathbf p_j$.
- $\mathcal P$: set of distinct training reference coordinates, $\hat{\mathbf x}$: independently produced position estimate.
- The native retrieval first considers up to **20 nearest RSS templates**; the spatial and overlap diagnostics use the first **10**. Repeated training observations at the same location/floor are aggregated into reference templates.
- Define $R(z)=\operatorname{clip}\!\left(\frac{z-Q_{0.05}}{Q_{0.95}-Q_{0.05}},0,1\right)$, where the quantiles are fitted within the complete evaluation unit. For a degenerate finite range, $R(z)=0.5$. Unavailable observations remain missing.

## Scan statistics

### Observed AP count (`ap_count`)

Number of access points retained in the query RSS feature vector.

\[
N_{AP}=|A_q|
\]

**Units:** APs. **Adverse direction:** Low. **Implementation note:** The count measures scan visibility, not the number of installed or discovered access points. AP labels remain unit-local.

### RSS standard deviation (`rss_std`)

Population standard deviation across all RSS observations in the current query.

\[
\sigma_{RSS}=\sqrt{\frac{1}{N}\sum_{a\in A_q}(r_a-\bar r)^2}
\]

**Units:** dBm. **Adverse direction:** High*. **Implementation note:** A wide RSS distribution is not necessarily harmful; the prespecified direction did not remain consistent across evaluation conditions.

### RSS range (`rss_range`)

Difference between strongest and weakest recorded RSS in a query.

\[
R_{RSS}=\max_{a\in A_q}r_a-\min_{a\in A_q}r_a
\]

**Units:** dB. **Adverse direction:** High*. **Implementation note:** The range summarizes signal-strength dispersion; it is not directly a measure of positioning error.

## Scan–map compatibility

### Nearest RSS-template distance (`min_rss_distance`)

Smallest normalized Euclidean distance from the query RSS vector to a reference template.

\[
d_1=\min_j\frac{\|\mathbf q-\mathbf t_j\|_2}{\sqrt D}
\]

**Units:** normalized RSS distance. **Adverse direction:** High. **Implementation note:** Missing AP features are filled at −110 dBm in the native computation. Training scans at the same reference coordinate/floor are averaged into a template.

### Nearest-match isolation (`nearest_match_isolation`)

Relative separation of the first two nearest RSS-template distances.

\[
I_{\mathrm{near}}=\frac{\max(d_2-d_1,0)}{d_2+10^{-6}}
\]

**Units:** ratio. **Adverse direction:** Low. **Implementation note:** A larger gap makes the nearest RSS template more distinguishable from the runner-up, but does not independently establish positioning accuracy.

### Nearest-template cosine similarity (`max_cosine_similarity`)

Cosine similarity between the query and its nearest RSS template after offsetting each vector by the RSS floor.

\[
C_{\mathrm{cos}}=\frac{(\mathbf q+110)\cdot(\mathbf t_1+110)}{\|\mathbf q+110\|_2\,\|\mathbf t_1+110\|_2}
\]

**Units:** similarity. **Adverse direction:** Low. **Implementation note:** A result is unavailable when the shifted vector norm is zero. The display illustrates a vector-angle comparison; per-AP template RSS values are not included in the browser sample.

### Maximum AP-set overlap (`ap_overlap`)

Largest Jaccard agreement between the observed query AP set and one of the ten retrieved reference-template AP sets.

\[
J_{\max}=\max_{j\leq10}\frac{|A_q\cap A_j|}{|A_q\cup A_j|}
\]

**Units:** Jaccard index. **Adverse direction:** Low. **Implementation note:** The reference AP set is the union of observed APs from scans aggregated into the template.

### Mean AP-set overlap (`mean_ap_overlap`)

Mean Jaccard agreement between query APs and the ten retrieved templates.

\[
\bar J=\frac1{10}\sum_{j=1}^{10}\frac{|A_q\cap A_j|}{|A_q\cup A_j|}
\]

**Units:** Jaccard index. **Adverse direction:** Low. **Implementation note:** Unlike maximum overlap, this describes the whole retrieved candidate group.

### AP-set novelty (`ap_set_novelty`)

Complement of the maximum query-to-template AP-set overlap.

\[
N_{APset}=1-J_{\max}
\]

**Units:** fraction. **Adverse direction:** High. **Implementation note:** Novelty increases as the query AP set becomes less compatible with the best reference template.

## Spatial support

### Nearest reference-point distance (`nearest_rp_distance`)

Distance between an estimator-produced position and the closest radio-map reference point.

\[
d_{RP}=\min_{\mathbf p\in\mathcal P}\|\hat{\mathbf x}-\mathbf p\|_2
\]

**Units:** metres. **Adverse direction:** High. **Implementation note:** Estimator-specific. Unlike the other examples, it requires a separately generated predicted position; no estimator prediction is supplied by this browser-only atlas.

### Local reference-point density (`local_rp_density`)

Number of distinct training reference coordinates within an adaptive radius around the candidate centroid.

\[
\rho_{RP}=\sum_{\mathbf p\in\mathcal P}\mathbf1\{\|\mathbf p-\bar{\mathbf c}\|_2\leq r\}
\]

**Units:** reference points. **Adverse direction:** Low. **Implementation note:** The radius is r = clip(3 × median positive nearest-neighbor spacing, 2 m, 25 m); default 5 m if the spacing cannot be resolved. The live candidate plot shows only the top ten, not every RP counted.

## Candidate geometry

### Candidate spatial spread (`sigma_fps`)

Root mean squared spatial distance of the ten retrieved reference coordinates from their centroid.

\[
\sigma_{FP}=\sqrt{\frac1{10}\sum_{j=1}^{10}\|\mathbf p_j-\bar{\mathbf p}\|_2^2}
\]

**Units:** metres. **Adverse direction:** High. **Implementation note:** A high value indicates retrieved fingerprints spread across local coordinates. Floor categories are not added as a vertical metric in this 2D calculation.

### Candidate-set diameter (`d_cand`)

Largest pairwise 2D separation among the ten retrieved reference coordinates.

\[
D_{cand}=\max_{1\leq i,j\leq10}\|\mathbf p_i-\mathbf p_j\|_2
\]

**Units:** metres. **Adverse direction:** High. **Implementation note:** Highlights distant outlying candidate references even if most candidates are clustered.

### Cumulative-neighborhood instability (`i_k`)

Maximum displacement between a cumulative rank-k candidate centroid and the final ten-candidate centroid.

\[
I_k=\max_{1\leq k\leq10}\left\|\frac1k\sum_{j=1}^k\mathbf p_j-\bar{\mathbf p}\right\|_2
\]

**Units:** metres. **Adverse direction:** High. **Implementation note:** Ordered by RSS-template similarity. This is a diagnostic of rank-dependent spatial stability, not a time-series displacement.

## Radio-map ambiguity

### RSS-gradient uncertainty proxy (`rss_gradient_proxy`)

Candidate spatial spread divided by the RSS-distance contrast across ranks 1–10.

\[
G_{RSS}=\frac{\sigma_{FP}}{\max(d_{10}-d_1,10^{-6})}
\]

**Units:** metres per normalized RSS distance. **Adverse direction:** High. **Implementation note:** Large spatial spread with a narrow RSS-distance range indicates spatial ambiguity relative to signal-space separation.

## Composite support

### Scan Quality and Support Score (SQS) (`sqs`)

Equal-weight average of signal-match, candidate-geometry, AP-count, overlap and local-density support.

\[
SQS=\operatorname{mean}(1-R(d_1),\ 1-\tfrac{R(\sigma_{FP})+R(D_{cand})}{2},\ R(N_{AP}),\ R(J_{\max}),\ R(\rho_{RP}))
\]

**Units:** [0,1]. **Adverse direction:** Low. **Implementation note:** R(z) is 5th–95th percentile clipped scaling within the full evaluation unit. Missing component values are omitted from the mean. SQS is not a calibrated probability.

### Signal-to-spread support (Cσ) (`c_sigma`)

Signal-match support reduced by normalized candidate spread.

\[
C_{\sigma}=\frac{1-R(d_1)}{1+R(\sigma_{FP})}
\]

**Units:** [0,1]. **Adverse direction:** Low. **Implementation note:** The denominator penalizes diffuse spatial candidate sets while preserving the normalized RSS-match numerator.

### Fingerprint Integrity Index (FII) (`fii`)

Average of signal support, AP count, maximum overlap, match isolation and inverse AP novelty.

\[
FII=\operatorname{mean}(1-R(d_1),\ R(N_{AP}),\ R(J_{\max}),\ R(I_{near}),\ 1-R(N_{APset}))
\]

**Units:** [0,1]. **Adverse direction:** Low. **Implementation note:** Five component terms are unit-relative. FII and SQS use different component definitions and cannot be interpreted as interchangeable probabilities.

## Interpreting the directions and scores

The adverse-direction labels are **a priori analysis conventions**. In particular, higher `rss_std` and `rss_range` did not show a stable adverse relationship throughout the evaluated conditions; their signs should not be generalized. Nearest-RP distance is defined **per estimator prediction** and is not available in the native scan-only example CSV.

SQS, Cσ and FII are **dimensionless relative support summaries**, not calibrated probabilities, error bounds or standalone gross-error decisions. To use a score for accepting or rejecting a position, first fit a threshold on independent calibration data and evaluate it on held-out scans. The browser atlas is descriptive and read-only: it never fabricates estimator predictions or operational warnings.

**Source mapping:** `nearest_rp_distance` is added to prediction outputs by `add_estimator_specific_nearest_rp`; `D_cand`, `I_k`, `C_sigma` and `FII` are the exact emitted CSV column spellings, while the configuration names use `d_cand`, `i_k`, `c_sigma` and `fii`.
