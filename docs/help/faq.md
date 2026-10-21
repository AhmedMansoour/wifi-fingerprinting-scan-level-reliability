# Frequently asked questions

??? question "What is Wi-Fi fingerprinting?"
    It estimates a location by comparing observed Wi-Fi signal strengths with a radio map collected at reference positions.

??? question "What is a radio map? Do I need a building floor plan?"
    A radio map is an RSS/position table, not an architectural map. No original HK floor-plan image or vector file is needed to run the released examples.

??? question "What does SQS mean?"
    The **Scan Quality and Support Score** combines five kinds of diagnostic support (signal match, candidate geometry, AP count, AP overlap and local density). It is not a calibrated probability of correctness.

??? question "Does a high SQS prove that a position is accurate?"
    No. Some strong-looking fingerprint matches can produce large errors. Use SQS as diagnostic evidence, and calibrate and evaluate any operational warning rule separately.

??? question "Do I need ten datasets just to try the method?"
    No. Four measured units, U01–U03 and U09, are included and runnable. Six further units link to official dataset publishers for local preparation.

??? question "What is the difference between newly computed and historical results?"
    The public runner computes fresh indicators from distributed measurements. Historical files contain stored predictions and analyses from the original experiment. See [evidence types](../results/evidence.md).

??? question "What if my input dataset has a different CSV layout?"
    Use [`scripts/import_external_unit.py`](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/blob/main/scripts/import_external_unit.py) and the [dataset-format guide](../DATASET_DOWNLOADS_AND_FORMAT.md). A new split or different transformation will not automatically match the manuscript results.

??? question "Can I run the Android app immediately with my building?"
    The app builds from Java source, but initializes an empty database. Import a radio map you are authorized to use and review calibration as described in the [Android guide](../ANDROID.md).

??? question "Are all datasets under the MIT license?"
    No. MIT applies to original code and synthetic fixtures. The UJIIndoorLoc data are under their source CC BY 4.0 terms, and other data require checking the source publisher's terms.

??? question "Is there a hosted interactive results dashboard?"
    Yes, the [interactive measured-scan explorer](../learn/interactive-explorer.md) visualizes 88 selected query scans from the four available measured units. It uses the original computed indicator/SQS values. The separate `dashboard/` is synthetic, and the original `web/` research interface is not a complete public live-positioning service.

**Still need help?** [Open a GitHub issue](https://github.com/AhmedMansoour/wifi-fingerprinting-scan-level-reliability/issues) with the unit ID, command, error message and non-sensitive input schema.
