# Explore one measured Wi-Fi scan interactively

Choose a measured query scan from UJIIndoorLoc (U01–U03) or the anonymous HK unit (U09). The viewer follows its **recorded Wi-Fi observations → retrieved radio-map candidates → geometry diagnostics → five SQS components → interpretation**.

The example values come directly from the [public native integrity computation](../PUBLIC_EMPIRICAL_INTEGRITY.md) and are **not synthetic**. There are 22 deterministic SQS-spanning samples from each of the four units, drawn from 5,041 evaluated scans. The SQS components are computed from the *full* unit, following the original code, not normalized against the 22 displayed samples.

<div class="wf-interactive-frame" markdown="1">
<iframe title="Interactive measured-data Wi-Fi fingerprinting integrity explorer" src="../../assets/interactive/index.html" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:2360px;border:0;border-radius:12px;background:#f5f8fa;" allow="fullscreen"></iframe>
</div>

!!! info "A teaching view, not a calibrated alarm system"
    The viewer **does not assign warnings or estimate probabilities of correctness**. The candidate centroid shown on the local-X/Y plot is a diagnostic summary, not a fitted positioning estimator output. Ground-truth locations can be revealed only for retrospective illustration. Candidate coordinates are relative metres, not a floor-plan image.

## How this interactive data is produced

The site includes only a compact deterministic subset of records; the full results stay available in the repository. Regenerate the identical browser data from the existing native Python outputs:

```bash
python scripts/export_interactive_examples.py
python scripts/export_interactive_examples.py --check
```

The exporter verifies that each displayed SQS equals the equal-weight average of the five values obtained from the existing `robust_unit_scale` implementation, using all held-out scans for each unit. No estimator training or original manuscript results are modified.

**Next:** [Understand every indicator](../INDICATORS.md) · [Run all four units](../start/quickstart.md) · [What the archived evidence proves](../results/evidence.md).

**Next:** [Compare two measured scans](compare-scans.md) · [Examine research evidence](../results/evidence-matrix.md).
