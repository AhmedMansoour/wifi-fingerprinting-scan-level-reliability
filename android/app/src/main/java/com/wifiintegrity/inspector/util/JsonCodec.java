package com.wifiintegrity.inspector.util;

import com.wifiintegrity.inspector.model.Candidate;
import com.wifiintegrity.inspector.model.DiagnosticResult;
import com.wifiintegrity.inspector.model.IndicatorDiagnostic;
import com.wifiintegrity.inspector.model.FloorInferenceScore;
import com.wifiintegrity.inspector.model.ProcessingTimes;
import com.wifiintegrity.inspector.model.ScanObservation;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class JsonCodec {
    private JsonCodec() {}

    public static String scanToJson(List<ScanObservation> scan) {
        JSONArray array = new JSONArray();
        for (ScanObservation observation : scan) {
            JSONObject object = new JSONObject();
            try {
                object.put("bssid", observation.bssid);
                object.put("rss", observation.rss);
                object.put("timestampMicros", observation.timestampMicros);
            } catch (JSONException ignored) { }
            array.put(object);
        }
        return array.toString();
    }

    public static List<ScanObservation> scanFromJson(String json) throws JSONException {
        JSONArray array = new JSONArray(json);
        List<ScanObservation> result = new ArrayList<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject object = array.getJSONObject(i);
            result.add(new ScanObservation(object.getString("bssid"), object.getDouble("rss"), object.optLong("timestampMicros", 0L)));
        }
        return result;
    }


    public static String floorRankingToJson(List<FloorInferenceScore> ranking) {
        JSONArray array = new JSONArray();
        if (ranking == null) return array.toString();
        for (FloorInferenceScore score : ranking) {
            JSONObject item = new JSONObject();
            try {
                item.put("floorId", score.floor.id);
                item.put("floorName", score.floor.name);
                item.put("floorNumber", score.floor.number);
                item.put("score", score.score);
                item.put("mappedApCount", score.mappedApCount);
                item.put("observedApCount", score.observedApCount);
                item.put("mappedFraction", score.mappedFraction);
                putFinite(item, "nearestRssDistance", score.nearestRssDistance);
                item.put("nearestCosineSimilarity", score.nearestCosineSimilarity);
            } catch (JSONException ignored) { }
            array.put(item);
        }
        return array.toString();
    }

    public static String resultToJson(DiagnosticResult result) {
        JSONObject root = new JSONObject();
        try {
            root.put("estimateX", result.estimateX);
            root.put("estimateY", result.estimateY);
            root.put("centroidX", result.centroidX);
            root.put("centroidY", result.centroidY);
            root.put("observedApCount", result.observedApCount);
            root.put("mappedApCount", result.mappedApCount);
            root.put("novelApCount", result.novelApCount);
            root.put("warningCount", result.warningCount);
            putFinite(root, "sqs", result.sqs);
            putFinite(root, "cSigma", result.cSigma);
            putFinite(root, "fii", result.fii);
            root.put("processingMs", result.processingMs);
            JSONObject timings = new JSONObject();
            putFinite(timings, "scanAcquisitionMs", result.processingTimes.scanAcquisitionMs);
            putFinite(timings, "floorInferenceMs", result.processingTimes.floorInferenceMs);
            putFinite(timings, "radioMapLoadMs", result.processingTimes.radioMapLoadMs);
            putFinite(timings, "fingerprintPreparationMs", result.processingTimes.fingerprintPreparationMs);
            putFinite(timings, "candidateRetrievalMs", result.processingTimes.candidateRetrievalMs);
            putFinite(timings, "positionEstimationMs", result.processingTimes.positionEstimationMs);
            putFinite(timings, "indicatorComputationMs", result.processingTimes.indicatorComputationMs);
            putFinite(timings, "diagnosisTotalMs", result.processingTimes.diagnosisTotalMs);
            putFinite(timings, "postScanProcessingMs", result.processingTimes.postScanProcessingMs);
            putFinite(timings, "persistenceMs", result.processingTimes.persistenceMs);
            root.put("processingTimes", timings);
            root.put("calibrationMode", result.calibrationMode);
            root.put("wknnK", result.wknnK);

            JSONArray candidates = new JSONArray();
            for (Candidate candidate : result.candidates) {
                JSONObject item = new JSONObject();
                item.put("rank", candidate.rank);
                item.put("templateId", candidate.templateId);
                item.put("x", candidate.x);
                item.put("y", candidate.y);
                item.put("distance", candidate.distance);
                candidates.put(item);
            }
            root.put("candidates", candidates);

            JSONArray indicators = new JSONArray();
            for (IndicatorDiagnostic indicator : result.indicators) {
                JSONObject item = new JSONObject();
                item.put("position", indicator.position);
                item.put("id", indicator.id);
                item.put("label", indicator.label);
                item.put("group", indicator.group);
                putFinite(item, "rawValue", indicator.rawValue);
                putFinite(item, "adversePercentile", indicator.adversePercentile);
                item.put("warning", indicator.warning);
                indicators.put(item);
            }
            root.put("indicators", indicators);

            JSONObject fingerprint = new JSONObject();
            for (Map.Entry<Integer, Double> entry : result.mappedFingerprint.entrySet()) {
                fingerprint.put(Integer.toString(entry.getKey()), entry.getValue());
            }
            root.put("mappedFingerprint", fingerprint);
        } catch (JSONException error) {
            throw new IllegalStateException("Cannot serialize diagnostic result", error);
        }
        return root.toString();
    }

    private static void putFinite(JSONObject object, String key, double value) throws JSONException {
        object.put(key, Double.isFinite(value) ? value : JSONObject.NULL);
    }

    private static double finiteOrNaN(JSONObject object, String key) {
        if (object.isNull(key)) return Double.NaN;
        double value = object.optDouble(key, Double.NaN);
        return Double.isFinite(value) ? value : Double.NaN;
    }

    public static DiagnosticResult resultFromJson(String json) throws JSONException {
        JSONObject root = new JSONObject(json);
        List<Candidate> candidates = new ArrayList<>();
        JSONArray candidateArray = root.getJSONArray("candidates");
        for (int i = 0; i < candidateArray.length(); i++) {
            JSONObject item = candidateArray.getJSONObject(i);
            candidates.add(new Candidate(item.getInt("rank"), item.getLong("templateId"), item.getDouble("x"), item.getDouble("y"), item.getDouble("distance")));
        }

        List<IndicatorDiagnostic> indicators = new ArrayList<>();
        JSONArray indicatorArray = root.getJSONArray("indicators");
        for (int i = 0; i < indicatorArray.length(); i++) {
            JSONObject item = indicatorArray.getJSONObject(i);
            indicators.add(new IndicatorDiagnostic(
                    item.getInt("position"), item.getString("id"), item.getString("label"),
                    item.optString("group", ""), finiteOrNaN(item, "rawValue"),
                    finiteOrNaN(item, "adversePercentile"), item.getBoolean("warning")));
        }

        Map<Integer, Double> fingerprint = new HashMap<>();
        JSONObject fingerprintJson = root.optJSONObject("mappedFingerprint");
        if (fingerprintJson != null) {
            JSONArray names = fingerprintJson.names();
            if (names != null) {
                for (int i = 0; i < names.length(); i++) {
                    String key = names.getString(i);
                    fingerprint.put(Integer.parseInt(key), fingerprintJson.getDouble(key));
                }
            }
        }

        double legacyProcessingMs = root.optDouble("processingMs", Double.NaN);
        JSONObject timingJson = root.optJSONObject("processingTimes");
        ProcessingTimes processingTimes = timingJson == null
                ? ProcessingTimes.unavailable(legacyProcessingMs)
                : new ProcessingTimes(
                finiteOrNaN(timingJson, "scanAcquisitionMs"),
                finiteOrNaN(timingJson, "floorInferenceMs"),
                finiteOrNaN(timingJson, "radioMapLoadMs"),
                finiteOrNaN(timingJson, "fingerprintPreparationMs"),
                finiteOrNaN(timingJson, "candidateRetrievalMs"),
                finiteOrNaN(timingJson, "positionEstimationMs"),
                finiteOrNaN(timingJson, "indicatorComputationMs"),
                finiteOrNaN(timingJson, "diagnosisTotalMs"),
                finiteOrNaN(timingJson, "postScanProcessingMs"),
                finiteOrNaN(timingJson, "persistenceMs"));

        return new DiagnosticResult(
                root.getDouble("estimateX"), root.getDouble("estimateY"),
                root.getDouble("centroidX"), root.getDouble("centroidY"),
                candidates, indicators, fingerprint,
                root.getInt("observedApCount"), root.getInt("mappedApCount"), root.getInt("novelApCount"),
                root.getInt("warningCount"), finiteOrNaN(root, "sqs"), finiteOrNaN(root, "cSigma"),
                finiteOrNaN(root, "fii"), legacyProcessingMs, processingTimes,
                root.optString("calibrationMode", "unknown"), root.optInt("wknnK", 3));
    }
}
