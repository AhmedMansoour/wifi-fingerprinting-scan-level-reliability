package com.wifiintegrity.inspector.model;

import java.util.List;

public final class SavedInspection {
    public final long id;
    public final long floorId;
    public final long createdAt;
    public final String buildingName;
    public final String floorName;
    public final String estimator;
    public final List<ScanObservation> scan;
    public final DiagnosticResult result;
    public final boolean floorInferred;
    public final Double floorScore;
    public final Double floorMargin;
    public final String floorConfidence;
    public final Double validationX;
    public final Double validationY;
    public final Double validationErrorM;

    public SavedInspection(long id, long floorId, long createdAt, String buildingName,
                           String floorName, String estimator, List<ScanObservation> scan,
                           DiagnosticResult result, boolean floorInferred,
                           Double floorScore, Double floorMargin, String floorConfidence,
                           Double validationX, Double validationY, Double validationErrorM) {
        this.id = id;
        this.floorId = floorId;
        this.createdAt = createdAt;
        this.buildingName = buildingName;
        this.floorName = floorName;
        this.estimator = estimator;
        this.scan = scan;
        this.result = result;
        this.floorInferred = floorInferred;
        this.floorScore = floorScore;
        this.floorMargin = floorMargin;
        this.floorConfidence = floorConfidence;
        this.validationX = validationX;
        this.validationY = validationY;
        this.validationErrorM = validationErrorM;
    }
}
