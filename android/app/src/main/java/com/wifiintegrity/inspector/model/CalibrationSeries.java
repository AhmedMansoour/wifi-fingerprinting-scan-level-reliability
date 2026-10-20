package com.wifiintegrity.inspector.model;

public final class CalibrationSeries {
    public final String indicatorId;
    public final String adverseDirection;
    public final double q05;
    public final double q95;
    public final double[] sortedValues;

    public CalibrationSeries(String indicatorId, String adverseDirection, double q05, double q95, double[] sortedValues) {
        this.indicatorId = indicatorId;
        this.adverseDirection = adverseDirection;
        this.q05 = q05;
        this.q95 = q95;
        this.sortedValues = sortedValues;
    }
}
