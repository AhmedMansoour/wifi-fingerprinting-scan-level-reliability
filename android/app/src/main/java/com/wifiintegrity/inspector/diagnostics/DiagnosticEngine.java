package com.wifiintegrity.inspector.diagnostics;

import com.wifiintegrity.inspector.model.CalibrationSeries;
import com.wifiintegrity.inspector.model.Candidate;
import com.wifiintegrity.inspector.model.DiagnosticResult;
import com.wifiintegrity.inspector.model.FloorData;
import com.wifiintegrity.inspector.model.IndicatorDiagnostic;
import com.wifiintegrity.inspector.model.ProcessingTimes;
import com.wifiintegrity.inspector.model.ReferenceTemplate;
import com.wifiintegrity.inspector.model.ScanObservation;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class DiagnosticEngine {
    public static final double RSS_FLOOR = -110.0;
    public static final double WARNING_CUTOFF = 0.80;
    public static final int DIAGNOSTIC_M = 10;
    private static final double EPS = 1e-6;

    private static final Definition[] DEFINITIONS = new Definition[]{
            new Definition(1, "ap_count", "AP count", "Scan characteristics", "low"),
            new Definition(2, "rss_std", "RSS std.", "Scan characteristics", "high"),
            new Definition(3, "rss_range", "RSS range", "Scan characteristics", "high"),
            new Definition(4, "min_rss_distance", "Min. RSS distance", "Scan–radio-map compatibility", "high"),
            new Definition(5, "nearest_match_isolation", "Match isolation", "Scan–radio-map compatibility", "low"),
            new Definition(6, "max_cosine_similarity", "Cosine similarity", "Scan–radio-map compatibility", "low"),
            new Definition(7, "ap_overlap", "Max. AP overlap", "Scan–radio-map compatibility", "low"),
            new Definition(8, "mean_ap_overlap", "Mean AP overlap", "Scan–radio-map compatibility", "low"),
            new Definition(9, "ap_set_novelty", "AP-set novelty", "Scan–radio-map compatibility", "high"),
            new Definition(10, "nearest_rp_distance", "Nearest-RP distance", "Spatial support", "high"),
            new Definition(11, "local_rp_density", "Local RP density", "Spatial support", "low"),
            new Definition(12, "sigma_fps", "Candidate spread", "Candidate geometry", "high"),
            new Definition(13, "D_cand", "Candidate diameter", "Candidate geometry", "high"),
            new Definition(14, "I_k", "Neighborhood instability", "Candidate geometry", "high"),
            new Definition(15, "rss_gradient_proxy", "RSS-gradient proxy", "Radio-map ambiguity", "high"),
            new Definition(16, "SQS", "SQS", "Composite indicators", "low"),
            new Definition(17, "C_sigma", "Cσ", "Composite indicators", "low"),
            new Definition(18, "FII", "FII", "Composite indicators", "low"),
    };

    public DiagnosticResult analyze(FloorData floorData, List<ScanObservation> observations, int wknnK) {
        long started = System.nanoTime();
        if (floorData.templates.isEmpty()) throw new IllegalStateException("The selected floor has no radio-map templates.");
        if (floorData.apIds.isEmpty()) throw new IllegalStateException("The selected floor has no access-point vocabulary.");

        Map<String, Double> strongestByBssid = new LinkedHashMap<>();
        for (ScanObservation observation : observations) {
            String bssid = normalizeBssid(observation.bssid);
            if (bssid.isEmpty() || !Double.isFinite(observation.rss)) continue;
            Double old = strongestByBssid.get(bssid);
            if (old == null || observation.rss > old) strongestByBssid.put(bssid, observation.rss);
        }
        if (strongestByBssid.isEmpty()) throw new IllegalStateException("The phone returned no usable Wi-Fi observations.");

        Map<Integer, Double> mapped = new HashMap<>();
        List<Double> rawRss = new ArrayList<>();
        int mappedBssidCount = 0;
        for (Map.Entry<String, Double> entry : strongestByBssid.entrySet()) {
            rawRss.add(entry.getValue());
            Integer apId = floorData.bssidToAp.get(entry.getKey());
            if (apId == null) continue;
            mappedBssidCount++;
            Double old = mapped.get(apId);
            if (old == null || entry.getValue() > old) mapped.put(apId, entry.getValue());
        }
        if (mapped.isEmpty()) {
            throw new IllegalStateException("None of the scanned BSSIDs occur in the selected floor radio map. Check the building and floor selection.");
        }
        int observedApCount = strongestByBssid.size();
        int novelApCount = Math.max(0, observedApCount - mappedBssidCount);

        int p = floorData.apIds.size();
        Map<Integer, Integer> columnByAp = new HashMap<>();
        for (int i = 0; i < p; i++) columnByAp.put(floorData.apIds.get(i), i);
        double[] query = new double[p];
        boolean[] queryPresence = new boolean[p];
        Arrays.fill(query, RSS_FLOOR);
        for (Map.Entry<Integer, Double> entry : mapped.entrySet()) {
            Integer column = columnByAp.get(entry.getKey());
            if (column != null) {
                query[column] = entry.getValue();
                queryPresence[column] = true;
            }
        }
        long fingerprintPrepared = System.nanoTime();

        List<TemplateVector> vectors = new ArrayList<>(floorData.templates.size());
        for (ReferenceTemplate template : floorData.templates) {
            double[] values = new double[p];
            boolean[] presence = new boolean[p];
            Arrays.fill(values, RSS_FLOOR);
            for (Map.Entry<Integer, Double> entry : template.fingerprint.entrySet()) {
                Integer column = columnByAp.get(entry.getKey());
                if (column != null) {
                    values[column] = entry.getValue();
                    presence[column] = true;
                }
            }
            double distance = normalizedEuclidean(query, values);
            vectors.add(new TemplateVector(template, values, presence, distance));
        }
        vectors.sort(Comparator.comparingDouble(v -> v.distance));

        int m = Math.min(DIAGNOSTIC_M, vectors.size());
        List<TemplateVector> selected = vectors.subList(0, m);
        double centroidX = 0.0;
        double centroidY = 0.0;
        List<Candidate> candidates = new ArrayList<>();
        for (int i = 0; i < m; i++) {
            TemplateVector vector = selected.get(i);
            centroidX += vector.template.x;
            centroidY += vector.template.y;
            candidates.add(new Candidate(i + 1, vector.template.id, vector.template.x, vector.template.y, vector.distance));
        }
        centroidX /= m;
        centroidY /= m;
        long candidatesRetrieved = System.nanoTime();

        int k = Math.max(1, Math.min(wknnK, vectors.size()));
        double weightSum = 0.0;
        double estimateX = 0.0;
        double estimateY = 0.0;
        for (int i = 0; i < k; i++) {
            TemplateVector vector = vectors.get(i);
            double weight = 1.0 / (vector.distance + EPS);
            weightSum += weight;
            estimateX += weight * vector.template.x;
            estimateY += weight * vector.template.y;
        }
        estimateX /= weightSum;
        estimateY /= weightSum;
        long positionEstimated = System.nanoTime();

        Map<String, Double> raw = calculateRawIndicators(
                floorData, query, queryPresence, rawRss, novelApCount,
                selected, centroidX, centroidY, estimateX, estimateY);
        addCompositeIndicators(raw, floorData.calibration);

        List<IndicatorDiagnostic> indicators = new ArrayList<>();
        int warningCount = floorData.calibrationAvailable ? 0 : -1;
        for (Definition definition : DEFINITIONS) {
            double value = raw.getOrDefault(definition.id, Double.NaN);
            CalibrationSeries series = floorData.calibration.get(definition.id);
            double adversePercentile = series == null || series.sortedValues.length == 0
                    ? Double.NaN : adversePercentile(value, series.sortedValues, series.adverseDirection);
            boolean warning = Double.isFinite(adversePercentile) && adversePercentile >= WARNING_CUTOFF;
            if (warning && warningCount >= 0) warningCount++;
            indicators.add(new IndicatorDiagnostic(definition.position, definition.id, definition.label,
                    definition.group, value, adversePercentile, warning));
        }

        long completed = System.nanoTime();
        double fingerprintPreparationMs = (fingerprintPrepared - started) / 1_000_000.0;
        double candidateRetrievalMs = (candidatesRetrieved - fingerprintPrepared) / 1_000_000.0;
        double positionEstimationMs = (positionEstimated - candidatesRetrieved) / 1_000_000.0;
        double indicatorComputationMs = (completed - positionEstimated) / 1_000_000.0;
        double elapsedMs = (completed - started) / 1_000_000.0;
        ProcessingTimes processingTimes = ProcessingTimes.engineOnly(
                fingerprintPreparationMs, candidateRetrievalMs, positionEstimationMs,
                indicatorComputationMs, elapsedMs);
        return new DiagnosticResult(
                estimateX, estimateY, centroidX, centroidY, candidates, indicators, mapped,
                observedApCount, mapped.size(), novelApCount, warningCount,
                raw.getOrDefault("SQS", Double.NaN), raw.getOrDefault("C_sigma", Double.NaN),
                raw.getOrDefault("FII", Double.NaN), elapsedMs, processingTimes,
                floorData.floor.calibrationMode, k);
    }

    private static Map<String, Double> calculateRawIndicators(
            FloorData floorData,
            double[] query,
            boolean[] queryPresence,
            List<Double> rawRss,
            int novelApCount,
            List<TemplateVector> selected,
            double centroidX,
            double centroidY,
            double estimateX,
            double estimateY) {
        Map<String, Double> raw = new HashMap<>();
        raw.put("ap_count", (double) (countTrue(queryPresence) + novelApCount));
        raw.put("rss_std", standardDeviation(rawRss));
        raw.put("rss_range", range(rawRss));

        double minDistance = selected.get(0).distance;
        double secondDistance = selected.size() > 1 ? selected.get(1).distance : minDistance;
        double isolation = Math.max(secondDistance - minDistance, 0.0) / (secondDistance + EPS);
        raw.put("min_rss_distance", minDistance);
        raw.put("nearest_match_isolation", isolation);
        raw.put("max_cosine_similarity", cosineSimilarity(query, selected.get(0).values));

        double maxOverlap = 0.0;
        double overlapSum = 0.0;
        for (TemplateVector vector : selected) {
            int intersection = 0;
            int union = novelApCount;
            for (int i = 0; i < queryPresence.length; i++) {
                if (queryPresence[i] && vector.presence[i]) intersection++;
                if (queryPresence[i] || vector.presence[i]) union++;
            }
            double overlap = union == 0 ? 0.0 : intersection / (double) union;
            maxOverlap = Math.max(maxOverlap, overlap);
            overlapSum += overlap;
        }
        raw.put("ap_overlap", maxOverlap);
        raw.put("mean_ap_overlap", overlapSum / selected.size());
        raw.put("ap_set_novelty", 1.0 - maxOverlap);

        double spreadSquared = 0.0;
        double diameter = 0.0;
        for (TemplateVector a : selected) {
            double dx = a.template.x - centroidX;
            double dy = a.template.y - centroidY;
            spreadSquared += dx * dx + dy * dy;
            for (TemplateVector b : selected) {
                diameter = Math.max(diameter, Math.hypot(a.template.x - b.template.x, a.template.y - b.template.y));
            }
        }
        double spread = Math.sqrt(spreadSquared / selected.size());
        raw.put("sigma_fps", spread);
        raw.put("D_cand", diameter);

        double cumulativeX = 0.0;
        double cumulativeY = 0.0;
        double instability = 0.0;
        for (int i = 0; i < selected.size(); i++) {
            cumulativeX += selected.get(i).template.x;
            cumulativeY += selected.get(i).template.y;
            double meanX = cumulativeX / (i + 1.0);
            double meanY = cumulativeY / (i + 1.0);
            instability = Math.max(instability, Math.hypot(meanX - centroidX, meanY - centroidY));
        }
        raw.put("I_k", instability);
        double kthDistance = selected.get(selected.size() - 1).distance;
        raw.put("rss_gradient_proxy", spread / Math.max(kthDistance - minDistance, EPS));

        int density = 0;
        double nearestRp = Double.POSITIVE_INFINITY;
        for (double[] point : floorData.referencePoints) {
            if (Math.hypot(point[0] - centroidX, point[1] - centroidY) <= floorData.floor.densityRadius) density++;
            nearestRp = Math.min(nearestRp, Math.hypot(point[0] - estimateX, point[1] - estimateY));
        }
        raw.put("local_rp_density", (double) density);
        raw.put("nearest_rp_distance", Double.isFinite(nearestRp) ? nearestRp : 0.0);
        return raw;
    }

    private static void addCompositeIndicators(Map<String, Double> raw, Map<String, CalibrationSeries> calibration) {
        String[] required = {"min_rss_distance", "sigma_fps", "D_cand", "ap_set_novelty",
                "ap_count", "ap_overlap", "local_rp_density", "nearest_match_isolation"};
        for (String id : required) {
            CalibrationSeries series = calibration.get(id);
            if (series == null || series.sortedValues.length == 0) {
                raw.put("SQS", Double.NaN);
                raw.put("C_sigma", Double.NaN);
                raw.put("FII", Double.NaN);
                return;
            }
        }
        double riskMin = robust01(raw.get("min_rss_distance"), calibration.get("min_rss_distance"));
        double riskSpread = robust01(raw.get("sigma_fps"), calibration.get("sigma_fps"));
        double riskDiameter = robust01(raw.get("D_cand"), calibration.get("D_cand"));
        double riskNovelty = robust01(raw.get("ap_set_novelty"), calibration.get("ap_set_novelty"));
        double signalSupport = 1.0 - riskMin;
        double geometrySupport = 1.0 - (riskSpread + riskDiameter) / 2.0;
        double apCountSupport = robust01(raw.get("ap_count"), calibration.get("ap_count"));
        double overlapSupport = robust01(raw.get("ap_overlap"), calibration.get("ap_overlap"));
        double densitySupport = robust01(raw.get("local_rp_density"), calibration.get("local_rp_density"));
        double isolationSupport = robust01(raw.get("nearest_match_isolation"), calibration.get("nearest_match_isolation"));
        raw.put("SQS", mean(signalSupport, geometrySupport, apCountSupport, overlapSupport, densitySupport));
        raw.put("C_sigma", signalSupport / (1.0 + riskSpread));
        raw.put("FII", mean(signalSupport, apCountSupport, overlapSupport, isolationSupport, 1.0 - riskNovelty));
    }

    private static double robust01(Double value, CalibrationSeries series) {
        if (value == null || !Double.isFinite(value)) return 0.5;
        if (series == null || series.q95 <= series.q05) return 0.5;
        return clamp01((value - series.q05) / (series.q95 - series.q05));
    }

    private static double adversePercentile(double value, double[] sortedValues, String direction) {
        if (!Double.isFinite(value) || sortedValues.length == 0) return Double.NaN;
        if ("low".equalsIgnoreCase(direction)) {
            int firstGreaterOrEqual = lowerBound(sortedValues, value);
            return clamp01((sortedValues.length - firstGreaterOrEqual) / (double) sortedValues.length);
        }
        int lastLessOrEqual = upperBound(sortedValues, value);
        return clamp01(lastLessOrEqual / (double) sortedValues.length);
    }

    private static int lowerBound(double[] values, double target) {
        int low = 0, high = values.length;
        while (low < high) {
            int mid = (low + high) >>> 1;
            if (values[mid] < target) low = mid + 1; else high = mid;
        }
        return low;
    }

    private static int upperBound(double[] values, double target) {
        int low = 0, high = values.length;
        while (low < high) {
            int mid = (low + high) >>> 1;
            if (values[mid] <= target) low = mid + 1; else high = mid;
        }
        return low;
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
        double denom = Math.sqrt(aa) * Math.sqrt(bb);
        return denom <= 0.0 ? 0.0 : dot / denom;
    }

    private static int countTrue(boolean[] values) {
        int count = 0;
        for (boolean value : values) if (value) count++;
        return count;
    }

    private static double standardDeviation(List<Double> values) {
        if (values.isEmpty()) return 0.0;
        double mean = 0.0;
        for (double value : values) mean += value;
        mean /= values.size();
        double sum = 0.0;
        for (double value : values) {
            double d = value - mean;
            sum += d * d;
        }
        return Math.sqrt(sum / values.size());
    }

    private static double range(List<Double> values) {
        if (values.isEmpty()) return 0.0;
        double min = Collections.min(values);
        double max = Collections.max(values);
        return max - min;
    }

    private static double mean(double... values) {
        double sum = 0.0;
        for (double value : values) sum += value;
        return sum / values.length;
    }

    private static double clamp01(double value) { return Math.max(0.0, Math.min(1.0, value)); }

    private static String normalizeBssid(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.US).replace('-', ':');
    }

    public static String formatValue(IndicatorDiagnostic indicator) {
        if (!Double.isFinite(indicator.rawValue)) return "—";
        if (indicator.id.equals("ap_count") || indicator.id.equals("local_rp_density")) {
            return String.format(Locale.US, "%.0f", indicator.rawValue);
        }
        if (indicator.id.equals("SQS") || indicator.id.equals("C_sigma") || indicator.id.equals("FII") ||
                indicator.id.contains("overlap") || indicator.id.contains("similarity") || indicator.id.contains("novelty") ||
                indicator.id.contains("isolation")) {
            return String.format(Locale.US, "%.3f", indicator.rawValue);
        }
        return String.format(Locale.US, "%.2f", indicator.rawValue);
    }

    private static final class Definition {
        final int position;
        final String id;
        final String label;
        final String group;
        final String adverseDirection;

        Definition(int position, String id, String label, String group, String adverseDirection) {
            this.position = position;
            this.id = id;
            this.label = label;
            this.group = group;
            this.adverseDirection = adverseDirection;
        }
    }

    private static final class TemplateVector {
        final ReferenceTemplate template;
        final double[] values;
        final boolean[] presence;
        final double distance;

        TemplateVector(ReferenceTemplate template, double[] values, boolean[] presence, double distance) {
            this.template = template;
            this.values = values;
            this.presence = presence;
            this.distance = distance;
        }
    }
}
