package com.wifiintegrity.inspector.model;

public final class IndicatorDiagnostic {
    public final int position;
    public final String id;
    public final String label;
    public final String group;
    public final double rawValue;
    public final double adversePercentile;
    public final boolean warning;

    public IndicatorDiagnostic(int position, String id, String label, String group,
                               double rawValue, double adversePercentile, boolean warning) {
        this.position = position;
        this.id = id;
        this.label = label;
        this.group = group;
        this.rawValue = rawValue;
        this.adversePercentile = adversePercentile;
        this.warning = warning;
    }
}
