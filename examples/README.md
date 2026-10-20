# Runnable examples

All datasets under `examples/synthetic_combined/` are **wholly fabricated** and used only for exercising the software.

```bash
python scripts/reproduce_release.py --mode demo
python scripts/validate_synthetic_combined.py
python scripts/prepare_research_workspace.py --combined examples/synthetic_combined/combined_all_datasets.csv.gz
python scripts/check_public_release.py
```

For a synthetic dashboard with illustrative KNN/WKNN errors, run `python scripts/build_synthetic_dashboard.py` and serve the repository using `python -m http.server 8000`. Open `http://localhost:8000/dashboard/`.

No historical reference predictions or measured HK scans are published in this candidate. Reference commands require separately approved private inputs.
