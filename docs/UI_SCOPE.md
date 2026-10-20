# Interface status

`dashboard/` is a standalone static HTML/CSS/JavaScript interface whose prebuilt payload is computed **only from fabricated example scans**. Its two displayed estimator summaries are not ESWA experimental results. Regenerate them with `python scripts/build_synthetic_dashboard.py`, then serve the repository directory with `python -m http.server 8000`.

`web/index.html` and `web/assets/` retain generic research UI source; some research-specific views need nonpublic generated tables and therefore are **not asserted to be functional in this public source-only checkout**. No floor-plan or vector map assets are bundled.
