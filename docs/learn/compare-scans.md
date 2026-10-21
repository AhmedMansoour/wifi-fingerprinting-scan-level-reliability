# Compare two measured Wi-Fi scans

This interactive comparison displays native observations from two independently selected held-out query scans within the **same evaluation unit**. All displayed values are taken from the previously exported measured data; the viewer does not calculate scores, infer error labels, or display floor-plan geometry.

<div class="wf-interactive-frame" markdown="1">
<iframe title="Side-by-side scientific comparison of measured Wi-Fi scan diagnostics" src="../../assets/interactive/comparison.html" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:2300px;border:0;border-radius:12px;background:#f3f7f9"></iframe>
</div>

!!! info "Comparison is not a positioning error measurement"
    All 22 selections per unit retain the original SQS and indicator values normalized using the **full evaluation unit**. The stored examples contain scan observations, candidate RSS distances and diagnostic values, but not verified estimator-specific position errors. A higher SQS must not be interpreted as a calibrated probability or a guarantee of lower error.

**Source:** [Measured-scan export and validation](../PUBLIC_EMPIRICAL_INTEGRITY.md) · [Single-scan explorer](interactive-explorer.md) · [Full indicator definitions](../INDICATORS.md) · [Research limitations](../REPRODUCIBILITY.md).

**Related:** [Inspect original SQS components and ablations](sqs-ablation.md).
