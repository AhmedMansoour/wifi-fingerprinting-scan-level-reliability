# Adverse-percentile warnings: calibration boundary

The Inspector v1.0.9 `DiagnosticEngine` computes each raw indicator first, then (when an exact floor/estimator calibration exists) maps its value to an adverse percentile using a sorted reference distribution. For sorted values \(r_1,...,r_n\):

- adverse **high**: `count(r <= observed) / n` (inclusive upper-tail rank in code terminology);
- adverse **low**: `count(r >= observed) / n` (inclusive lower-tail rank);
- warning when the resulting adverse fraction is `>= 0.80`.

Ties are handled by inclusive comparisons; the code uses `upperBound` for adverse-high and `lowerBound` for adverse-low. A warning is **not** a validated probability of positioning error, and when a matching profile is absent the warning count is unavailable rather than silently calibrated from another floor or estimator.

**Retrospective results:** calibration reference distributions formed from the analyzed study population summarize that population. They should not be characterized as fitted exclusively before its held-out evaluation unless that separation is documented.

**Prospective application:** to apply the procedure to a new scan, acquire a separate **training/development/calibration** population for the exact configured estimator/floor, fit the ordered reference distributions and required SQS scaling parameters without the held-out query, freeze the resulting artifact, and then evaluate queries only against those frozen values. Sensor scan observations themselves do not supply unknown GT errors; any choice of calibration populations must be explicit.

`scripts/calibrate_warning_states.py` is a separate executable split-isolated illustrative procedure. It rejects overlapping calibration/evaluation identifiers, records its calibration input hash, and does not claim that its quantiles reconstruct the original retrospective manuscript statistics.
