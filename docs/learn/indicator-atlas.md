# Scan-level reliability indicators: interactive atlas

The framework retains **15 diagnostic quantities and three composite scores**, covering query RSS statistics, compatibility with the training radio map, candidate geometry, reference-point support and ambiguity. Each indicator is defined in the [equation reference](../INDICATORS.md) and computed by the existing Python source.

Choose an indicator below to view its **definition, equation, units, adverse direction and animated visual interpretation**. Select a public measured scan to inspect its source-derived value. The interface distinguishes measured-data representations from schematic illustrations, and does not manufacture estimator outputs.

<div class="wf-interactive-frame" markdown="1">
<iframe title="Interactive mathematical atlas for eighteen scan-level reliability indicators" src="../../assets/indicator-atlas/index.html" loading="lazy" referrerpolicy="no-referrer" style="width:100%;height:1970px;border:0;border-radius:12px;background:#f4f7f9;"></iframe>
</div>

## Computation and reproducibility

The browser does not calculate diagnostic quantities. Its displayed values come from the published UJIIndoorLoc U01–U03 and HK U09 native scan-level output files. The equations are drawn directly from `src/wifi_integrity/reliability/indicators.py` and `sqs.py`.

Three interpretation rules apply throughout: **SQS is not a calibrated accuracy probability**; the stored reference coordinates are not substitute estimator predictions; and the prespecified adverse signs do not all hold consistently, particularly RSS range and RSS standard deviation.

**Next:** [Read the complete formulas and implementation notes](../INDICATORS.md) · [Explore retrieved candidates for a measured scan](interactive-explorer.md) · [Run the native computation](../start/quickstart.md).
