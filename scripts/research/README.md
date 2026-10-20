# Recovered numerical analysis drivers

These drivers were recovered from the supplied research versions. Changes are restricted to local paths and integration; their experimental definitions remain inspectable. Generated tables and figures are written into ignored `results/advanced/` folders and are not included in the public package.

| Driver | Scope | Prerequisites |
|---|---|---|
| `run_a1_sqs_ablation.py` | SQS components and ablations | Included reference records |
| `run_a3_statistics.py` | Original complete A3 statistical analysis | Original combined scans and intermediate gross-error/confidently-wrong tables |
| `run_a4_floor_analysis.py`, `run_a4_phase2.py` | Floor-aware analysis | Authorized combined scans and outputs from the preceding stage |
| `run_a5_sensitivity.py`, `run_a5_fast.py` | Candidate-count and threshold sensitivity | Authorized combined scans and original diagnostic recomputation |
| `run_a6_runtime.py` | Python phase timing | Authorized combined scans and diagnostic probe |
| `run_a7_extension.py` | Confidently-wrong extension | Authorized combined scans and legacy condition tables |
| `legacy/20_*`, `21_*`, `23_*`, `24_*` | Original diagnostic, gross-error, confidently-wrong, and robustness stages | Authorized combined scans and study reference records |

For the runnable public SQS route:

```bash
python scripts/prepare_research_workspace.py
python scripts/research/run_a1_sqs_ablation.py
```

For additional raw-data experiments, supply the original combined table locally:

```bash
python scripts/prepare_research_workspace.py --combined /private/combined_all_datasets.csv
```

The preparer selects the 10 registered units, validates their split counts, and writes a translated/opaque-token working view. It does not publish the original table or inverse mappings. Generate the original stage 21 and 23 condition tables before running the complete original A3 driver. Inspect each driver's input paths before execution; these research drivers are not all validated as fresh full runs in this package.

For an independently executable A3 interval check using only included inputs, use `python scripts/reproduce_release.py --mode reference` followed by `python scripts/reproduce_uncertainty.py`.

The original confidently-wrong analyses use nominal RSS-match confidence. The convenience case selector in `src/wifi_integrity/reliability/cases.py` uses upper-quartile SQS for its own illustrative selection. These are different definitions and should not be substituted when reproducing A7.
