package com.wifiintegrity.inspector.diagnostics;

import com.wifiintegrity.inspector.model.FloorInferenceProfile;
import com.wifiintegrity.inspector.model.FloorInferenceResult;
import com.wifiintegrity.inspector.model.FloorInferenceScore;
import com.wifiintegrity.inspector.model.ReferenceTemplate;
import com.wifiintegrity.inspector.model.ScanObservation;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Infers the most likely floor inside the user-selected building before the
 * two-dimensional WKNN estimate is calculated. The score combines mapped-AP
 * support, mapped fraction, nearest-template RSS compatibility, and cosine
 * similarity. It is intentionally transparent and deterministic.
 */
public final class FloorInferenceEngine {
    private static final double RSS_FLOOR = DiagnosticEngine.RSS_FLOOR;

    public FloorInferenceResult infer(List<ScanObservation> observations,
                                      List<FloorInferenceProfile> profiles) {
        if (profiles == null || profiles.isEmpty()) {
            throw new IllegalStateException("No floor profiles are available for floor inference.");
        }
        Map<String, Double> scan = strongestScan(observations);
        if (scan.isEmpty()) {
            throw new IllegalStateException("The phone returned no usable Wi-Fi observations.");
        }

        List<FloorInferenceScore> ranking = new ArrayList<>();
        for (FloorInferenceProfile profile : profiles) {
            ranking.add(scoreFloor(scan, profile));
        }
        ranking.sort(Comparator.comparingDouble((FloorInferenceScore value) -> value.score).reversed());

        FloorInferenceScore best = ranking.get(0);
        if (best.mappedApCount == 0 || !Double.isFinite(best.nearestRssDistance)) {
            throw new IllegalStateException("The scan does not match any floor radio map in the selected building.");
        }
        double second = ranking.size() > 1 ? ranking.get(1).score : 0.0;
        double margin = Math.max(0.0, best.score - second);
        String confidence;
        if (best.score >= 0.62 && margin >= 0.08 && best.mappedApCount >= 8) {
            confidence = "high";
        } else if (best.score >= 0.45 && margin >= 0.03 && best.mappedApCount >= 5) {
            confidence = "moderate";
        } else {
            confidence = "low";
        }
        return new FloorInferenceResult(best.floor, best.score, margin, confidence, ranking);
    }

    private FloorInferenceScore scoreFloor(Map<String, Double> scan,
                                           FloorInferenceProfile profile) {
        Map<Integer, Double> mapped = new HashMap<>();
        for (Map.Entry<String, Double> entry : scan.entrySet()) {
            Integer apId = profile.bssidToAp.get(entry.getKey());
            if (apId == null) continue;
            Double old = mapped.get(apId);
            if (old == null || entry.getValue() > old) mapped.put(apId, entry.getValue());
        }
        int observed = scan.size();
        int mappedCount = mapped.size();
        if (mappedCount == 0 || profile.apIds.isEmpty() || profile.templates.isEmpty()) {
            return new FloorInferenceScore(profile.floor, 0.0, mappedCount, observed,
                    0.0, Double.POSITIVE_INFINITY, 0.0);
        }

        Map<Integer, Integer> columnByAp = new HashMap<>();
        for (int i = 0; i < profile.apIds.size(); i++) columnByAp.put(profile.apIds.get(i), i);
        double[] query = new double[profile.apIds.size()];
        Arrays.fill(query, RSS_FLOOR);
        for (Map.Entry<Integer, Double> entry : mapped.entrySet()) {
            Integer column = columnByAp.get(entry.getKey());
            if (column != null) query[column] = entry.getValue();
        }

        double nearestDistance = Double.POSITIVE_INFINITY;
        double nearestCosine = 0.0;
        for (ReferenceTemplate template : profile.templates) {
            double[] candidate = new double[profile.apIds.size()];
            Arrays.fill(candidate, RSS_FLOOR);
            for (Map.Entry<Integer, Double> entry : template.fingerprint.entrySet()) {
                Integer column = columnByAp.get(entry.getKey());
                if (column != null) candidate[column] = entry.getValue();
            }
            double distance = normalizedEuclidean(query, candidate);
            if (distance < nearestDistance) {
                nearestDistance = distance;
                nearestCosine = cosineSimilarity(query, candidate);
            }
        }

        double mappedFraction = mappedCount / (double) Math.max(1, observed);
        double mappedSupport = Math.min(1.0, mappedCount / 20.0);
        double distanceSupport = Math.exp(-nearestDistance / 18.0);
        double cosineSupport = clamp01(nearestCosine);
        double score = 0.35 * mappedFraction
                + 0.20 * mappedSupport
                + 0.25 * cosineSupport
                + 0.20 * distanceSupport;

        return new FloorInferenceScore(profile.floor, clamp01(score), mappedCount,
                observed, mappedFraction, nearestDistance, nearestCosine);
    }

    public static String summarize(FloorInferenceResult result) {
        if (result == null) return "Manual floor selection";
        return String.format(Locale.US, "%s inferred (%s confidence; score %.3f; margin %.3f)",
                result.floor.name, result.confidence, result.score, result.margin);
    }

    private static Map<String, Double> strongestScan(List<ScanObservation> observations) {
        Map<String, Double> strongest = new LinkedHashMap<>();
        if (observations == null) return strongest;
        for (ScanObservation observation : observations) {
            if (observation == null || !Double.isFinite(observation.rss)) continue;
            String bssid = normalizeBssid(observation.bssid);
            if (bssid.isEmpty()) continue;
            Double old = strongest.get(bssid);
            if (old == null || observation.rss > old) strongest.put(bssid, observation.rss);
        }
        return strongest;
    }

    private static double normalizedEuclidean(double[] a, double[] b) {
        double sum = 0.0;
        for (int i = 0; i < a.length; i++) {
            double d = a[i] - b[i];
            sum += d * d;
        }
        return Math.sqrt(sum / Math.max(1, a.length));
    }

    private static double cosineSimilarity(double[] a, double[] b) {
        double dot = 0.0, aa = 0.0, bb = 0.0;
        for (int i = 0; i < a.length; i++) {
            double x = a[i] - RSS_FLOOR;
            double y = b[i] - RSS_FLOOR;
            dot += x * y;
            aa += x * x;
            bb += y * y;
        }
        double denominator = Math.sqrt(aa) * Math.sqrt(bb);
        return denominator <= 0.0 ? 0.0 : dot / denominator;
    }

    private static String normalizeBssid(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.US).replace('-', ':');
    }

    private static double clamp01(double value) {
        return Math.max(0.0, Math.min(1.0, value));
    }
}
