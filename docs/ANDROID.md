# Android implementation

The Java application performs Wi-Fi scan inspection, floor inference, WKNN positioning, and scan-level diagnostic presentation. The public project contains source and an empty schema, with no private radio-map database or Block Z floor plans.

## Build

The source declares Android Gradle Plugin 8.13.0, Gradle 8.13, JDK 17, compile/target SDK 35, and minimum API 26. These Gradle/JDK/build-tools requirements follow the [official AGP 8.13 compatibility table](https://developer.android.com/build/releases/agp-8-13-0-release-notes).

Open `android/` in Android Studio, install SDK 35 and Build Tools 35.0.0, then run:

```bash
cd android
./gradlew testDebugUnitTest assembleDebug
# Windows: gradlew.bat testDebugUnitTest assembleDebug
```

The included wrapper uses the official distribution checksum. APKs, build outputs, local SDK paths, signing files, and scan histories are not committed. See [the current integration validation report](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/blob/main/RELEASE_VALIDATION.md) for independent checks and limitations.

## First launch and local data

The app creates an empty SQLite database from `app/src/main/assets/database/schema.sql`. Import an authorized local radio-map package through the Radio Maps screen using [IMPORT_FORMAT.md](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/blob/main/android/IMPORT_FORMAT.md). No default private building or floor is selected in source.

The fabricated AP tokens in the public synthetic fixture cannot identify live access points and are not a replacement for an authorized local radio-map import. Imported calibrations must match the selected floor, WKNN setting, and diagnostic candidate count. Missing calibration leaves raw diagnostics available without pretending that calibrated warning outputs exist.

[CALIBRATION.md](CALIBRATION.md) defines the independent-reference/held-out protocol. Imported profile provenance must be retained separately; Android's CSV importer alone does not prove independent calibration.

## Interpretation of the 99-run timing experiment

The historical record describes 99 runs and an indicator/composite/warning computation median of approximately 0.43 ms. This source release does not independently verify the recorded device metadata or original 99 raw timings.

That interval begins **after candidate retrieval and coordinate estimation**. It excludes Wi-Fi acquisition, floor inference, radio-map loading, fingerprint preparation, candidate retrieval, coordinate estimation, rendering, and persistence. It is a computational-cost measurement, not an end-to-end latency benchmark, accuracy test, or independent live warning-effectiveness evaluation. These historical device measurements have not been newly repeated as part of the repository build checks.
