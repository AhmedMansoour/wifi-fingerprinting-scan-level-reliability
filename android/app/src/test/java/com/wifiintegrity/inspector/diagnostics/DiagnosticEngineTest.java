package com.wifiintegrity.inspector.diagnostics;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.wifiintegrity.inspector.model.Building;
import com.wifiintegrity.inspector.model.CalibrationSeries;
import com.wifiintegrity.inspector.model.DiagnosticResult;
import com.wifiintegrity.inspector.model.FloorData;
import com.wifiintegrity.inspector.model.FloorInfo;
import com.wifiintegrity.inspector.model.ReferenceTemplate;
import com.wifiintegrity.inspector.model.ScanObservation;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class DiagnosticEngineTest {
    @Test public void returnsEighteenIndicators() {
        Building building = new Building(1, "Synthetic", "Synthetic");
        FloorInfo floor = new FloorInfo(1, 1, 1, "1F", "Synthetic1", 0, 0, 0, 30, 20, null, 5, "test");
        Map<String,Integer> bssid = new HashMap<>();
        bssid.put("synthetic_ap_001",1);
        bssid.put("synthetic_ap_002",2);
        bssid.put("synthetic_ap_003",3);
        List<Integer> apIds = Arrays.asList(1,2,3);
        List<double[]> rps = Arrays.asList(new double[]{0,0}, new double[]{10,0}, new double[]{20,0}, new double[]{0,10}, new double[]{10,10}, new double[]{20,10});
        List<ReferenceTemplate> templates = new ArrayList<>();
        for (int i=0;i<rps.size();i++) {
            Map<Integer,Double> fp = new HashMap<>();
            fp.put(1,-45.0-i*3);
            fp.put(2,-70.0+i*4);
            fp.put(3,-82.0+i*5);
            templates.add(new ReferenceTemplate(i+1,i+1,rps.get(i)[0],rps.get(i)[1],fp));
        }
        String[] ids = {"ap_count","rss_std","rss_range","min_rss_distance","nearest_match_isolation","max_cosine_similarity","ap_overlap","mean_ap_overlap","ap_set_novelty","nearest_rp_distance","local_rp_density","sigma_fps","D_cand","I_k","rss_gradient_proxy","SQS","C_sigma","FII"};
        Set<String> low = new HashSet<>(Arrays.asList("ap_count","nearest_match_isolation","max_cosine_similarity","ap_overlap","mean_ap_overlap","local_rp_density","SQS","C_sigma","FII"));
        Map<String,CalibrationSeries> calibration = new HashMap<>();
        for (String id: ids) calibration.put(id,new CalibrationSeries(id,low.contains(id)?"low":"high",0,100,new double[]{0,0.2,0.4,0.6,0.8,1,5,10,20,50,100}));
        FloorData data = new FloorData(building,floor,bssid,apIds,rps,templates,calibration,"WKNN-k3",10);
        List<ScanObservation> scan = Arrays.asList(
                new ScanObservation("synthetic_ap_001",-50,0),
                new ScanObservation("synthetic_ap_002",-63,0),
                new ScanObservation("synthetic_ap_003",-75,0));
        DiagnosticResult result = new DiagnosticEngine().analyze(data,scan,3);
        assertEquals(18, result.indicators.size());
        assertEquals(6, result.candidates.size());
        assertTrue(Double.isFinite(result.estimateX));
        assertTrue(Double.isFinite(result.sqs));
    }
}
