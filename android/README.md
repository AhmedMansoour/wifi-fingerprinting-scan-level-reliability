# Wi-Fi Integrity Inspector

Java implementation of Wi-Fi scan inspection, floor inference, WKNN positioning, and reliability diagnostics. Open this directory as the Android Studio project root.

```bash
./gradlew testDebugUnitTest assembleDebug
```

Requires JDK 17 and SDK 35. The app creates an empty local database from its SQL schema. Import your authorized local radio map; no site database, private BSSIDs, or Block Z floor-plan assets are bundled. Synthetic AP tokens do not correspond to any real access points.

See [build and runtime scope](../docs/ANDROID.md), [import format](IMPORT_FORMAT.md), and [calibration](../docs/CALIBRATION.md).
