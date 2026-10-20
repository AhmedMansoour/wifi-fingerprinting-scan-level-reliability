package com.wifiintegrity.inspector.model;

import java.util.Collections;
import java.util.Map;

public final class ReferenceTemplate {
    public final long id;
    public final int localId;
    public final double x;
    public final double y;
    public final Map<Integer, Double> fingerprint;

    public ReferenceTemplate(long id, int localId, double x, double y, Map<Integer, Double> fingerprint) {
        this.id = id;
        this.localId = localId;
        this.x = x;
        this.y = y;
        this.fingerprint = Collections.unmodifiableMap(fingerprint);
    }
}
