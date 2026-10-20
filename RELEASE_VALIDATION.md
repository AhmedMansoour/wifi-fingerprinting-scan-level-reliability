# Integration validation: public-release review candidate

The integration described here was performed in a local Python/Java filesystem. The result has not yet been uploaded to public GitHub when this report was prepared; an MIT source license is included.

| Verification | Actual outcome |
|---|---|
| Comparison to recovered 211-file implementation | Completed; preserved Python estimator code and Android Studio Gradle project |
| Python unit suite (`PYTHONPATH=src pytest -q`) | **20 passed** |
| Synthetic ten-unit CSV validator | **68,149 fabricated rows**, 54,520 train / 13,629 test, 10 units; combined CSV SHA-256 verified |
| Synthetic demo retrieval | **Passed**, 300 train + 150 test; KNN and WKNN |
| Synthetic workspace preparation | **Passed** on the fabricated combined table |
| Native estimator smoke | **7 passed**, residual CNN **skipped** because optional dependency unavailable; not study-level accuracy validation |
| Java diagnostic and floor-inference smoke | **2 passed** under installed Java runtime |
| Android Gradle compile/build and on-device run | **Not executed in this environment**, Android SDK/Gradle build infrastructure unavailable; recovered prior-package validation records historical Android build only |
| JavaScript syntax | Dashboard and browser UI JavaScript checked with Node.js |
| Source/privacy gate | **Passed**; permitted only fabricated `.csv.gz` files and checksum-pinned official Gradle wrapper and generic app icon |
| Original HK floor-plan images, vector files, BSSIDs, real HK coordinates | **Not included in candidate**; privacy gate checked staged bytes and extracted archive |
| Research reference tests | **Not applicable to public checkout**: the original reference/processed outputs are deliberately withheld. Existing reference suite failures must not be hidden or reported as passes |
| Empirical eight-estimator retraining, native SQS equivalence | **Not established** |

The public-data example is **fully synthetic** and is not a transformed or anonymized sample of the empirical study. The empirical study reference predictions, per-scan reliability features, and all real radio fingerprint tables are absent.

**Verification boundary:** this local environment cannot download the Android SDK or Gradle distribution due unavailable DNS; the repository CI workflow is configured to build on GitHub-hosted runners. A GitHub CI build result is the appropriate Android verification. Do not interpret synthetic demonstrations as independent reproduction of manuscript accuracy. Original third-party dependencies retain their licenses; see `THIRD_PARTY_NOTICES.md`.

The ten versioned synthetic unit files recreate the entire combined table using `python scripts/assemble_synthetic_combined.py`; the script checks all source and combined SHA-256 hashes. The combined gzip file is generated locally, not committed.
