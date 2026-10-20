# Getting started with the public fixture

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/reproduce_release.py --mode demo
python scripts/validate_synthetic_combined.py
```

The fabricated ten-unit input is `examples/synthetic_combined/combined_all_datasets.csv.gz`. It is not anonymized empirical data. To prepare a local processing workspace, run:

```bash
python scripts/prepare_research_workspace.py --combined examples/synthetic_combined/combined_all_datasets.csv.gz
```

Private empirical study references are **not included**. `scripts/reproduce_release.py --mode reference` needs authorized reference files and cannot run by default.
