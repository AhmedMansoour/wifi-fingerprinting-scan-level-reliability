package com.wifiintegrity.inspector.model;

public final class ScanObservation {
    public final String bssid;
    public final double rss;
    public final long timestampMicros;

    public ScanObservation(String bssid, double rss, long timestampMicros) {
        this.bssid = bssid;
        this.rss = rss;
        this.timestampMicros = timestampMicros;
    }
}
