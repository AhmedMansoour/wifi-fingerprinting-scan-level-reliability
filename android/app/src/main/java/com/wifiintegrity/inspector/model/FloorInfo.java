package com.wifiintegrity.inspector.model;

public final class FloorInfo {
    public final long id;
    public final long buildingId;
    public final int number;
    public final String name;
    public final String uniqueId;
    public final double rotationAngle;
    public final double minX;
    public final double minY;
    public final double maxX;
    public final double maxY;
    public final byte[] floorPlan;
    public final double densityRadius;
    public final String calibrationMode;

    public FloorInfo(long id, long buildingId, int number, String name, String uniqueId,
                     double rotationAngle, double minX, double minY, double maxX, double maxY,
                     byte[] floorPlan, double densityRadius, String calibrationMode) {
        this.id = id;
        this.buildingId = buildingId;
        this.number = number;
        this.name = name;
        this.uniqueId = uniqueId;
        this.rotationAngle = rotationAngle;
        this.minX = minX;
        this.minY = minY;
        this.maxX = maxX;
        this.maxY = maxY;
        this.floorPlan = floorPlan;
        this.densityRadius = densityRadius;
        this.calibrationMode = calibrationMode;
    }

    public boolean hasFloorPlan() { return floorPlan != null && floorPlan.length > 0; }
    @Override public String toString() { return name + (hasFloorPlan() ? "  • image" : "  • coordinate view"); }
}
