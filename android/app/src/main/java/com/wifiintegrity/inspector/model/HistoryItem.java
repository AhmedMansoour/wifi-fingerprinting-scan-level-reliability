package com.wifiintegrity.inspector.model;

public final class HistoryItem {
    public final long id;
    public final long createdAt;
    public final String buildingName;
    public final String floorName;
    public final String estimator;
    public final double sqs;
    public final int warnings;
    public final int mappedAps;
    public final double x;
    public final double y;
    public final boolean floorInferred;
    public final String floorConfidence;
    public final Double validationErrorM;

    public HistoryItem(long id, long createdAt, String buildingName, String floorName,
                       String estimator, double sqs, int warnings, int mappedAps,
                       double x, double y, boolean floorInferred,
                       String floorConfidence, Double validationErrorM) {
        this.id = id;
        this.createdAt = createdAt;
        this.buildingName = buildingName;
        this.floorName = floorName;
        this.estimator = estimator;
        this.sqs = sqs;
        this.warnings = warnings;
        this.mappedAps = mappedAps;
        this.x = x;
        this.y = y;
        this.floorInferred = floorInferred;
        this.floorConfidence = floorConfidence;
        this.validationErrorM = validationErrorM;
    }
}
