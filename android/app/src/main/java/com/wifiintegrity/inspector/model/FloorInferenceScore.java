package com.wifiintegrity.inspector.model;

public final class FloorInferenceScore {
    public final FloorInfo floor;
    public final double score;
    public final int mappedApCount;
    public final int observedApCount;
    public final double mappedFraction;
    public final double nearestRssDistance;
    public final double nearestCosineSimilarity;

    public FloorInferenceScore(FloorInfo floor, double score, int mappedApCount,
                               int observedApCount, double mappedFraction,
                               double nearestRssDistance, double nearestCosineSimilarity) {
        this.floor = floor;
        this.score = score;
        this.mappedApCount = mappedApCount;
        this.observedApCount = observedApCount;
        this.mappedFraction = mappedFraction;
        this.nearestRssDistance = nearestRssDistance;
        this.nearestCosineSimilarity = nearestCosineSimilarity;
    }
}
