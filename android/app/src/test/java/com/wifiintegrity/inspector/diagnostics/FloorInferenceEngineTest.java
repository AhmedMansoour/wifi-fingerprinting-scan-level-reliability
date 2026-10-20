package com.wifiintegrity.inspector.diagnostics;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.wifiintegrity.inspector.model.Building;
import com.wifiintegrity.inspector.model.FloorInfo;
import com.wifiintegrity.inspector.model.FloorInferenceProfile;
import com.wifiintegrity.inspector.model.FloorInferenceResult;
import com.wifiintegrity.inspector.model.ReferenceTemplate;
import com.wifiintegrity.inspector.model.ScanObservation;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class FloorInferenceEngineTest {
    @Test public void selectsFloorWithMatchingBssidsAndRss() {
        Building building = new Building(1, "Synthetic", "Synthetic");
        FloorInfo floor1 = new FloorInfo(1,1,1,"1F","F1",0,0,0,10,10,null,5,"test");
        FloorInfo floor2 = new FloorInfo(2,1,2,"2F","F2",0,0,0,10,10,null,5,"test");
        List<Integer> apIds = Arrays.asList(1,2);

        Map<String,Integer> map1 = new HashMap<>();
        map1.put("synthetic_ap_001",1); map1.put("synthetic_ap_002",2);
        Map<String,Integer> map2 = new HashMap<>();
        map2.put("synthetic_ap_003",1); map2.put("synthetic_ap_004",2);

        List<ReferenceTemplate> t1 = new ArrayList<>();
        Map<Integer,Double> fp1 = new HashMap<>(); fp1.put(1,-50.0); fp1.put(2,-65.0);
        t1.add(new ReferenceTemplate(1,1,0,0,fp1));
        List<ReferenceTemplate> t2 = new ArrayList<>();
        Map<Integer,Double> fp2 = new HashMap<>(); fp2.put(1,-50.0); fp2.put(2,-65.0);
        t2.add(new ReferenceTemplate(2,1,0,0,fp2));

        List<FloorInferenceProfile> profiles = Arrays.asList(
                new FloorInferenceProfile(building,floor1,map1,apIds,t1),
                new FloorInferenceProfile(building,floor2,map2,apIds,t2));
        List<ScanObservation> scan = Arrays.asList(
                new ScanObservation("synthetic_ap_003",-51,0),
                new ScanObservation("synthetic_ap_004",-66,0));
        FloorInferenceResult result = new FloorInferenceEngine().infer(scan,profiles);
        assertEquals(2L,result.floor.id);
        assertTrue(result.score > 0.5);
    }
}
