package com.wifiintegrity.inspector.model;

public final class Candidate {
    public final int rank;
    public final long templateId;
    public final double x;
    public final double y;
    public final double distance;

    public Candidate(int rank, long templateId, double x, double y, double distance) {
        this.rank = rank;
        this.templateId = templateId;
        this.x = x;
        this.y = y;
        this.distance = distance;
    }
}
