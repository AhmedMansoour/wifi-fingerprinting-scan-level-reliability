package com.wifiintegrity.inspector.model;

import java.util.Collections;
import java.util.List;
import java.util.Map;

public final class FloorInferenceProfile {
    public final Building building;
    public final FloorInfo floor;
    public final Map<String, Integer> bssidToAp;
    public final List<Integer> apIds;
    public final List<ReferenceTemplate> templates;

    public FloorInferenceProfile(Building building, FloorInfo floor,
                                 Map<String, Integer> bssidToAp,
                                 List<Integer> apIds,
                                 List<ReferenceTemplate> templates) {
        this.building = building;
        this.floor = floor;
        this.bssidToAp = Collections.unmodifiableMap(bssidToAp);
        this.apIds = Collections.unmodifiableList(apIds);
        this.templates = Collections.unmodifiableList(templates);
    }
}
