# Documentation map and maintenance

The documentation is organized by **reader question**, not the source-code folder structure.

| Reader | Recommended journey | Key files |
|---|---|---|
| New to indoor Wi-Fi positioning | Why reliability matters → one-scan walkthrough → FAQ | `learn/overview.md`, `learn/walkthrough.md`, `help/faq.md` |
| Wants to run the repository | Public empirical quick start → output interpretation | `start/quickstart.md`, `results/how-to-read.md` |
| Has a new data source | Data format → import → local processing | `start/your-data.md`, `DATASET_DOWNLOADS_AND_FORMAT.md` |
| Reviews the scientific evidence | Evidence levels → archived results → calibration | `results/evidence.md`, `EXISTING_RESEARCH_ASSETS.md`, `CALIBRATION.md` |
| Builds Android applications | Android guide → radio-map import → warning calibration | `ANDROID.md`, `WARNING_CALIBRATION.md` |

## Navigation ownership

- `mkdocs.yml` is the single source of truth for the site navigation.
- The `docs/learn/`, `docs/start/`, `docs/results/`, and `docs/help/` folders contain **reader-facing explainers**.
- The existing root-level `docs/*.md` scientific guides remain authoritative for commands, tables, definitions and research limitations.
- New user-facing claims should link to a verified command, output or original result. Synthetic illustrations must be identified as synthetic.

## Build locally

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
# Open http://127.0.0.1:8000
```

Check the output with `python -m mkdocs build --clean`.

## GitHub Pages

A GitHub Actions workflow (`.github/workflows/docs.yml`) builds this site, verifies expected HTML pages and search index, and publishes the `gh-pages` branch on pushes to `main`. The repository owner may need to select **Settings → Pages → Deploy from a branch → gh-pages / (root)** once before the canonical URL becomes available. Do not claim that the public documentation URL works until GitHub Pages reports a successful deployment and the URL is reachable.

The documentation uses MkDocs Material; the separate project-code and empirical-data licenses are described in the main repository.
