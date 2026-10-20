import com.wifiintegrity.inspector.diagnostics.FloorInferenceEngine;
import com.wifiintegrity.inspector.model.*;

import java.util.*;

public final class FloorInferenceSmokeTest {
    public static void main(String[] args) {
        Building building = new Building(1, "Synthetic", "Synthetic");
        FloorInfo f1 = new FloorInfo(1,1,1,"1F","F1",0,0,0,10,10,null,5,"test");
        FloorInfo f2 = new FloorInfo(2,1,2,"2F","F2",0,0,0,10,10,null,5,"test");
        List<Integer> apIds = Arrays.asList(1,2);
        Map<String,Integer> map1 = new HashMap<>(); map1.put("synthetic_ap_001",1); map1.put("synthetic_ap_002",2);
        Map<String,Integer> map2 = new HashMap<>(); map2.put("synthetic_ap_003",1); map2.put("synthetic_ap_004",2);
        Map<Integer,Double> fp = new HashMap<>(); fp.put(1,-50.0); fp.put(2,-65.0);
        List<ReferenceTemplate> templates = Collections.singletonList(new ReferenceTemplate(1,1,0,0,fp));
        List<FloorInferenceProfile> profiles = Arrays.asList(
                new FloorInferenceProfile(building,f1,map1,apIds,templates),
                new FloorInferenceProfile(building,f2,map2,apIds,templates));
        List<ScanObservation> scan = Arrays.asList(
                new ScanObservation("synthetic_ap_003",-51,0),
                new ScanObservation("synthetic_ap_004",-66,0));
        FloorInferenceResult result = new FloorInferenceEngine().infer(scan,profiles);
        if (result.floor.id != 2L) throw new AssertionError("Wrong inferred floor: " + result.floor.name);
        System.out.println("Floor inference smoke test passed: " + result.floor.name + ", score=" + result.score);
    }
}
