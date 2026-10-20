# Verified reproducibility scope and release status

The source repository was published on `main` in commit `4178c3bf559004e223c437a74dc6c06b7057d748` on **2026-10-20**. The public source and completely synthetic fixtures are available at:

https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability

The GitHub Actions workflow for that commit completed successfully:

https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/actions/runs/39465309756

| Verification | Status and scope |
|---|---|
| Python environment installation | Passed on GitHub Actions runner |
| Python tests | Passed on GitHub Actions; 20/20 also passed in independent local extraction of predecessor candidate |
| Generated synthetic combined dataset | Validated: 68,149 fabricated records across ten input slots |
| Synthetic KNN/WKNN demo | Passed; software operation only |
| Source privacy gate | Passed in CI and predecessor candidate; not equivalent to legal redistribution clearance |
| Android SDK 35 / Java 17 Gradle build | `testDebugUnitTest` and `assembleDebug` passed in GitHub Actions |
| Real smartphone deployment/field test | Not established by GitHub CI |
| Historical Android 99-run timing experiment | Separate study; its reported timing is post-retrieval indicator/composite/warning computation only |
| Complete original empirical training/evaluation | Not established; required real research inputs are withheld |
| Empirical scalar-reference replay and native SQS equivalence | Not established by the public checkout |

The public ten-unit fixture is **100% synthetic**, not a sanitized or shifted copy of the empirical study. No private HK map, vector floor plan, real BSSID, original HK reference coordinates or empirical radio map is licensed for repository distribution. The code archive does not establish dataset-specific redistribution rights.

**Maintainer checks still needed:** software/contributor license clearance, journal double-blind policy, tests on physical Android hardware where claimed, and any empirical reproduction undertaken privately using licensed datasets. Do not claim statistical empirical reproducibility from the synthetic fixture or infer new-environment robustness from the ten original evaluation units.

## Release manifest

After making changes in a *private checkout* and completing confidentiality review, generate `metadata/public_release_manifest.json` with `python scripts/refresh_release_manifest.py --write`, review the diff, and verify using `--check`. This manifest excludes itself and any uncommitted generated combined CSV. Updating the manifest is a bookkeeping operation, **not** permission to publish additional data.
