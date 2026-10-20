package com.wifiintegrity.inspector.model;

import java.util.Collections;
import java.util.List;

public final class FloorInferenceResult {
    public final FloorInfo floor;
    public final double score;
    public final double margin;
    public final String confidence;
    public final List<FloorInferenceScore> ranking;

    public FloorInferenceResult(FloorInfo floor, double score, double margin,
                                String confidence, List<FloorInferenceScore> ranking) {
        this.floor = floor;
        this.score = score;
        this.margin = margin;
        this.confidence = confidence;
        this.ranking = Collections.unmodifiableList(ranking);
    }
}
