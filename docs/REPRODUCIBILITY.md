# Reproducibility and execution scope

[Home](../README.md) · [Research overview](RESEARCH_OVERVIEW.md) · [Availability](ROADMAP.md)

## Choose the evidence you need

| Route | Purpose | What it establishes | Current public availability |
| --- | --- | --- | --- |
| Synthetic demonstration | Verify installation and estimator interfaces using generated scans | An executable example, separate from the paper's evidence | Being prepared |
| Stored-reference replay | Recalculate summaries from saved manuscript outputs | Agreement of summaries with the supplied reference artifacts | Being prepared; requires a documented input bundle |
| Native recomputation | Recalculate features or fit supported estimators from input data | Behavior of the current implementation in the recorded environment | Being reconciled with the manuscript protocol |
| Android live operation | Process new scans against an imported radio map | On-device execution and inspectable diagnostic outputs | Java source release being prepared |

The term `published` appears in some older internal filenames and command names. It denotes stored manuscript-reference outputs and does not indicate that the paper is published.

## Implementation coverage in the supplied Python package

| Estimator | Stored reference predictions | Native adapter in the supplied package |
| --- | --- | --- |
| KNN | Present in the private source package | Present |
| WKNN | Present in the private source package | Present |
| Random Forest | Present in the private source package | Present |
| Extra Trees | Present in the private source package | Present |
| Histogram-Based Gradient Boosting | Present in the private source package | Present |
| CatBoost | Present in the private source package | Present; optional dependency and protocol reconciliation required |
| AP-token Transformer | Present in the private source package | Not included |
| Residual CNN | Present in the private source package | Not included |

Adapter availability is distinct from demonstrated equivalence to the manuscript training protocol. Installing an additional dependency does not supply a missing adapter.

## Reproduction records

Each eventual executable route should record its inputs, configuration, random seeds, software environment, output schema, and validation scope. Stored-reference replay and native recomputation must have separate output names and provenance labels. Matching a summary statistic is weaker evidence than matching the complete scan-level outputs.

The preparation process has identified differences between stored-reference and native SQS values. These need explanation before the native pipeline is described as an exact reconstruction of the study. Arithmetic reconstruction of SQS from an existing reference-feature table is a separate check.

The first source release is planned around a small synthetic example that runs without downloading research datasets. Full reference reproduction will require an explicit artifact list; data-dependent tests will be identified separately from data-free unit tests.

## Data and calibration

The planned source release does not bundle research scans or radio maps. Dataset source records and any redistributable artifacts will be documented separately. Calibration derived from an offline evaluation population must be distinguished from calibration available before an unseen live scan. This distinction matters for AP selection, scaling, quantiles, and condition-relative warnings.

The public repository currently contains documentation and placeholders. No installation or full-reproduction command is presented as ready to run from the current public checkout.
