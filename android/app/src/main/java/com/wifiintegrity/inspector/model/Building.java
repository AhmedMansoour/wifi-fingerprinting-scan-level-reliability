package com.wifiintegrity.inspector.model;

public final class Building {
    public final long id;
    public final String name;
    public final String uniqueId;

    public Building(long id, String name, String uniqueId) {
        this.id = id;
        this.name = name;
        this.uniqueId = uniqueId;
    }

    @Override public String toString() { return name; }
}
