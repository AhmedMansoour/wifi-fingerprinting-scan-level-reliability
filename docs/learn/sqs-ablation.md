# Interactive SQS anatomy and ablation study

Examine the five normalized support components of the **Scan Quality and Support Score (SQS)** for one recorded Wi-Fi scan and compare the **11 archived A1 study variants** using their reported aggregate statistics. The figure distinguishes individual scan measurements from retrospective experimental ablation results.

<div class="wf-interactive-frame" markdown="1">
<iframe title="Interactive SQS decomposition and archived component ablations" src="../../assets/interactive/sqs-lab.html" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:2200px;border:0;border-radius:12px;background:#f3f7f9"></iframe>
</div>

!!! info "Measured scan versus archived study outcomes"
    The upper panel reconstructs the native full SQS from its **five equally weighted** components using a stored measured scan. The lower panel displays archived **study-level** results for the full SQS, five conceptual leave-one-out variants, and five individual support components, each evaluated in up to **80 dataset–estimator conditions**. Changing the measured scan does **not** change the historical ablation results. The shown 25th–75th percentile intervals are *interquartile ranges*, not 95% confidence intervals. No operational warning probability is inferred.

**Sources:** [Archived A1 ablation summary](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/blob/main/results/approved/revision_summaries/A1/A1_SQS_main_component_ablation_summary.csv) · [Public empirical integrity computation](../PUBLIC_EMPIRICAL_INTEGRITY.md) · [Indicator definitions](../INDICATORS.md) · [Reproducibility limits](../REPRODUCIBILITY.md).

For comparison of different observed scans, see the [side-by-side scan explorer](compare-scans.md). For results across indicators and estimators, see the [research evidence matrix](../results/evidence-matrix.md).
