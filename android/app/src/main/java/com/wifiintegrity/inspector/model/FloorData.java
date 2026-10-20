package com.wifiintegrity.inspector.model;

import java.util.Collections;
import java.util.List;
import java.util.Map;

public final class FloorData {
    public final Building building;
    public final FloorInfo floor;
    public final Map<String, Integer> bssidToAp;
    public final List<Integer> apIds;
    public final List<double[]> referencePoints;
    public final List<ReferenceTemplate> templates;
    public final Map<String, CalibrationSeries> calibration;
    public final String calibrationEstimator;
    public final int diagnosticM;
    public final boolean calibrationAvailable;

    public FloorData(Building building, FloorInfo floor, Map<String, Integer> bssidToAp,
                     List<Integer> apIds, List<double[]> referencePoints,
                     List<ReferenceTemplate> templates, Map<String, CalibrationSeries> calibration,
                     String calibrationEstimator, int diagnosticM) {
        this.building = building;
        this.floor = floor;
        this.bssidToAp = Collections.unmodifiableMap(bssidToAp);
        this.apIds = Collections.unmodifiableList(apIds);
        this.referencePoints = Collections.unmodifiableList(referencePoints);
        this.templates = Collections.unmodifiableList(templates);
        this.calibration = Collections.unmodifiableMap(calibration);
        this.calibrationEstimator = calibrationEstimator;
        this.diagnosticM = diagnosticM;
        this.calibrationAvailable = calibration.size() == 18;
    }

    public String calibrationDescription() {
        if (!calibrationAvailable) {
            return "No matching calibration for " + calibrationEstimator + ", M=" + diagnosticM;
        }
        return floor.calibrationMode + " calibration: " + calibrationEstimator + ", M=" + diagnosticM;
    }
}
