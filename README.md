# An Intelligent Framework for Scan-Level Reliability, Accuracy Diagnostics, and Gross-Error Detection in Wi-Fi Fingerprinting-Based Indoor Positioning Systems

<p align="center"><strong>Scan-level diagnosis · Reproducible evaluation · On-device inspection</strong></p>
<p align="center">Under review in <em>Expert Systems with Applications</em></p>

<p align="center">
  <a href="docs/RESEARCH_OVERVIEW.md">Research overview</a> ·
  <a href="docs/REPRODUCIBILITY.md">Reproducibility</a> ·
  <a href="docs/ANDROID.md">Android implementation</a> ·
  <a href="docs/ROADMAP.md">Availability</a>
</p>

## Reliability information for individual Wi-Fi position fixes

A Wi-Fi scan can closely resemble stored fingerprints while still producing a poor position estimate. This project examines scan-level diagnostics that describe signal compatibility, spatial support, candidate-neighborhood geometry, and radio-map ambiguity, so that reliability information can accompany each Wi-Fi fingerprinting fix.

The repository will host the Python analysis pipeline and Android implementation associated with the paper. The software is organized around a common diagnostic layer that can be examined across positioning estimators and building-level radio maps.

> **Code and reproducibility materials are being prepared for the public release.**
>
> The public repository currently provides the project overview and documentation. Python source, Android source, examples, and research outputs will be added in stages. Installation commands will accompany the corresponding source release.

## Study at a glance

| Evaluation scope | Coverage |
| :--- | :--- |
| Building-level evaluation units | **10** |
| Training fingerprints | **54,520** |
| Held-out query scans | **13,629** |
| Positioning estimators | **8** |
| Retained scan-level indicators | **18**, including SQS and the other composite indicators |

These numbers describe the manuscript evaluation. They do not imply that the underlying datasets or all estimator-training implementations are currently distributed here.

## What the project supports

| Component | Research purpose | Planned material |
| :--- | :--- | :--- |
| **Python analysis** | Examine associations with positioning error, gross-error discrimination, and behavior across conditions | Package, configuration, examples, and reproducibility instructions |
| **Reliability diagnostics** | Interpret scan statistics, RSS matching, spatial support, candidate geometry, and composite support scores | Indicator definitions and implementation mapping |
| **Android inspection** | Inspect a live scan, a floor-specific WKNN estimate, and its diagnostic information | Java project, radio-map import specification, and timing/export documentation |
| **Result exploration** | Inspect estimator comparisons and representative diagnostic cases | A documented results interface after the supporting artifacts are ready |

For the distinction between reference-result replay, native recomputation, and live implementation, see the [reproducibility guide](docs/REPRODUCIBILITY.md).

## Start with your research question

- **Understand the method:** read the [research overview](docs/RESEARCH_OVERVIEW.md) and [indicator guide](docs/INDICATORS.md).
- **Plan a reproducibility study:** review the [execution modes and validation boundaries](docs/REPRODUCIBILITY.md).
- **Prepare a radio map for the app:** consult the [Android implementation guide](docs/ANDROID.md).
- **Check what is available:** follow the [availability and development roadmap](docs/ROADMAP.md).

## Repository structure

| Path | Intended role |
| :--- | :--- |
| `src/` | Python package and diagnostic implementations |
| `scripts/` | Demonstration and reproduction entry points |
| `android/` | Android Studio Java project |
| `config/` | Scientific configuration and evaluation-unit definitions |
| `examples/` | Small, clearly labeled usage examples |
| `docs/` | Research, reproducibility, and implementation documentation |
| `results/` | Locally generated outputs |
| `metadata/` | Version and provenance information |

The software directories currently contain placeholders. Documentation describes the intended organization and the supplied implementations being prepared for release.

## Interpretation and scope

The indicators are diagnostic quantities, not calibrated probabilities that a position is correct. SQS combines five support components with equal nominal weights; it is not a learned fusion model. Warning thresholds require application-specific evaluation. The offline floor-aware analysis uses an auxiliary RSS-based floor assignment and should not be read as a vertical-error benchmark for the eight positioning estimators.

The Android implementation demonstrates floor inference, floor-specific WKNN positioning, and scan-level diagnosis. It serves a different purpose from the controlled eight-estimator offline evaluation. See [research scope](docs/RESEARCH_OVERVIEW.md#interpretation-boundaries) for further details.

Questions about the project or documentation can be raised through [GitHub Issues](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/issues). Include the relevant component and software version when reporting an implementation issue.
