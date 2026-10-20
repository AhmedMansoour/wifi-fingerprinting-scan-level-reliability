package com.wifiintegrity.inspector.util;

import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Build;

import com.wifiintegrity.inspector.BuildConfig;

import com.wifiintegrity.inspector.model.DiagnosticResult;
import com.wifiintegrity.inspector.model.IndicatorDiagnostic;
import com.wifiintegrity.inspector.model.ProcessingTimes;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** Exports all saved scan-level inspections in paper-ready CSV and JSONL formats. */
public final class InspectionExporter {
    private InspectionExporter() { }

    public static void export(SQLiteDatabase db, OutputStream output) throws IOException {
        StringBuilder summaries = new StringBuilder();
        StringBuilder indicators = new StringBuilder();
        StringBuilder timings = new StringBuilder();
        StringBuilder rankings = new StringBuilder();
        StringBuilder jsonLines = new StringBuilder();
        Map<String, List<Double>> timingSamples = new LinkedHashMap<>();
        for (String stage : new String[]{"scan_acquisition_ms", "floor_inference_ms", "radio_map_load_ms",
                "fingerprint_preparation_ms", "candidate_retrieval_ms", "position_estimation_ms",
                "indicator_computation_ms", "diagnosis_total_ms", "post_scan_processing_ms", "persistence_ms"}) {
            timingSamples.put(stage, new ArrayList<>());
        }

        summaries.append("inspection_id,timestamp_utc,building,floor,floor_inferred,floor_score,floor_margin,floor_confidence,estimator,observed_aps,mapped_aps,novel_aps,estimate_x,estimate_y,sqs,c_sigma,fii,warning_count,validation_x,validation_y,validation_error_m,calibration_mode\n");
        indicators.append("inspection_id,timestamp_utc,building,floor,estimator,indicator_position,indicator_id,indicator_label,indicator_group,raw_value,adverse_percentile,warning\n");
        timings.append("inspection_id,timestamp_utc,building,floor,estimator,scan_acquisition_ms,floor_inference_ms,radio_map_load_ms,fingerprint_preparation_ms,candidate_retrieval_ms,position_estimation_ms,indicator_computation_ms,diagnosis_total_ms,post_scan_processing_ms,persistence_ms\n");
        rankings.append("inspection_id,timestamp_utc,building,selected_floor,rank,floor_id,floor_name,floor_number,score,mapped_aps,observed_aps,mapped_fraction,nearest_rss_distance,nearest_cosine_similarity\n");

        String sql = "SELECT id,created_at,building_name,floor_name,estimator,observed_aps,mapped_aps,novel_aps," +
                "estimate_x,estimate_y,sqs,warning_count,scan_json,result_json,floor_inferred,floor_score,floor_margin," +
                "floor_confidence,validation_x,validation_y,validation_error_m,floor_ranking_json FROM scan_inspections ORDER BY created_at";

        try (Cursor cursor = db.rawQuery(sql, null)) {
            while (cursor.moveToNext()) {
                long id = cursor.getLong(0);
                long createdAt = cursor.getLong(1);
                String timestamp = utcTimestamp(createdAt);
                String building = cursor.getString(2);
                String floor = cursor.getString(3);
                String estimator = cursor.getString(4);
                String scanJson = cursor.getString(12);
                String resultJson = cursor.getString(13);
                String rankingJson = cursor.isNull(21) ? "[]" : cursor.getString(21);

                try {
                    DiagnosticResult result = JsonCodec.resultFromJson(resultJson);
                    summaries.append(row(
                            id, timestamp, building, floor, cursor.getInt(14),
                            nullable(cursor, 15), nullable(cursor, 16), nullable(cursor, 17), estimator,
                            cursor.getInt(5), cursor.getInt(6), cursor.getInt(7),
                            cursor.getDouble(8), cursor.getDouble(9), result.sqs, result.cSigma,
                            result.fii, cursor.getInt(11), nullable(cursor, 18), nullable(cursor, 19),
                            nullable(cursor, 20), result.calibrationMode));

                    for (IndicatorDiagnostic indicator : result.indicators) {
                        indicators.append(row(id, timestamp, building, floor, estimator,
                                indicator.position, indicator.id, indicator.label, indicator.group,
                                finite(indicator.rawValue), finite(indicator.adversePercentile),
                                indicator.warning ? 1 : 0));
                    }

                    ProcessingTimes t = result.processingTimes;
                    timings.append(row(id, timestamp, building, floor, estimator,
                            finite(t.scanAcquisitionMs), finite(t.floorInferenceMs), finite(t.radioMapLoadMs),
                            finite(t.fingerprintPreparationMs), finite(t.candidateRetrievalMs),
                            finite(t.positionEstimationMs), finite(t.indicatorComputationMs),
                            finite(t.diagnosisTotalMs), finite(t.postScanProcessingMs), finite(t.persistenceMs)));
                    addTiming(timingSamples.get("scan_acquisition_ms"), t.scanAcquisitionMs);
                    addTiming(timingSamples.get("floor_inference_ms"), t.floorInferenceMs);
                    addTiming(timingSamples.get("radio_map_load_ms"), t.radioMapLoadMs);
                    addTiming(timingSamples.get("fingerprint_preparation_ms"), t.fingerprintPreparationMs);
                    addTiming(timingSamples.get("candidate_retrieval_ms"), t.candidateRetrievalMs);
                    addTiming(timingSamples.get("position_estimation_ms"), t.positionEstimationMs);
                    addTiming(timingSamples.get("indicator_computation_ms"), t.indicatorComputationMs);
                    addTiming(timingSamples.get("diagnosis_total_ms"), t.diagnosisTotalMs);
                    addTiming(timingSamples.get("post_scan_processing_ms"), t.postScanProcessingMs);
                    addTiming(timingSamples.get("persistence_ms"), t.persistenceMs);

                    JSONArray ranking = new JSONArray(rankingJson);
                    for (int index = 0; index < ranking.length(); index++) {
                        JSONObject item = ranking.getJSONObject(index);
                        rankings.append(row(id, timestamp, building, floor, index + 1,
                                item.optLong("floorId"), item.optString("floorName"),
                                item.optInt("floorNumber"), finite(item.optDouble("score", Double.NaN)),
                                item.optInt("mappedApCount"), item.optInt("observedApCount"),
                                finite(item.optDouble("mappedFraction", Double.NaN)),
                                finite(item.optDouble("nearestRssDistance", Double.NaN)),
                                finite(item.optDouble("nearestCosineSimilarity", Double.NaN))));
                    }

                    JSONObject record = new JSONObject();
                    record.put("inspectionId", id);
                    record.put("createdAt", createdAt);
                    record.put("timestampUtc", timestamp);
                    record.put("building", building);
                    record.put("floor", floor);
                    record.put("floorInferred", cursor.getInt(14) == 1);
                    if (!cursor.isNull(15)) record.put("floorScore", cursor.getDouble(15));
                    if (!cursor.isNull(16)) record.put("floorMargin", cursor.getDouble(16));
                    if (!cursor.isNull(17)) record.put("floorConfidence", cursor.getString(17));
                    record.put("floorRanking", ranking);
                    record.put("estimator", estimator);
                    record.put("scan", new JSONArray(scanJson));
                    record.put("result", new JSONObject(resultJson));
                    if (!cursor.isNull(18)) record.put("validationX", cursor.getDouble(18));
                    if (!cursor.isNull(19)) record.put("validationY", cursor.getDouble(19));
                    if (!cursor.isNull(20)) record.put("validationErrorM", cursor.getDouble(20));
                    jsonLines.append(record).append('\n');
                } catch (JSONException error) {
                    throw new IOException("Cannot export inspection " + id, error);
                }
            }
        }

        try (ZipOutputStream zip = new ZipOutputStream(output, StandardCharsets.UTF_8)) {
            put(zip, "scan_summary.csv", summaries.toString());
            put(zip, "indicator_results.csv", indicators.toString());
            put(zip, "processing_times.csv", timings.toString());
            put(zip, "processing_summary.csv", processingSummary(timingSamples));
            put(zip, "floor_inference_ranking.csv", rankings.toString());
            put(zip, "inspections.jsonl", jsonLines.toString());
            put(zip, "device_metadata.csv", deviceMetadata());
            put(zip, "README.txt", "Wi-Fi Integrity Inspector export\n" +
                    "scan_summary.csv: one row per scan-level inspection.\n" +
                    "indicator_results.csv: all 18 raw values, adverse percentiles, and warnings.\n" +
                    "processing_times.csv: on-device stage-level timing measurements.\n" +
                    "processing_summary.csv: count, mean, median, quartiles, and 95th percentile by stage.\n" +
                    "floor_inference_ranking.csv: ranked floor results when inference was enabled.\n" +
                    "inspections.jsonl: complete scans and diagnostic outputs.\n" +
                    "device_metadata.csv: phone, Android, and application version used for the export.\n");
        }
    }

    private static void addTiming(List<Double> values, double value) {
        if (values != null && Double.isFinite(value)) values.add(value);
    }

    private static String processingSummary(Map<String, List<Double>> samples) {
        StringBuilder text = new StringBuilder("stage,n,mean_ms,median_ms,p25_ms,p75_ms,p95_ms,min_ms,max_ms\n");
        for (Map.Entry<String, List<Double>> entry : samples.entrySet()) {
            List<Double> values = entry.getValue();
            Collections.sort(values);
            if (values.isEmpty()) {
                text.append(row(entry.getKey(), 0, "", "", "", "", "", "", ""));
                continue;
            }
            double sum = 0.0;
            for (double value : values) sum += value;
            text.append(row(entry.getKey(), values.size(),
                    formatNumber(sum / values.size()), formatNumber(percentile(values, 0.50)),
                    formatNumber(percentile(values, 0.25)), formatNumber(percentile(values, 0.75)),
                    formatNumber(percentile(values, 0.95)), formatNumber(values.get(0)),
                    formatNumber(values.get(values.size() - 1))));
        }
        return text.toString();
    }

    private static double percentile(List<Double> sorted, double probability) {
        if (sorted.isEmpty()) return Double.NaN;
        if (sorted.size() == 1) return sorted.get(0);
        double position = probability * (sorted.size() - 1);
        int lower = (int) Math.floor(position);
        int upper = (int) Math.ceil(position);
        if (lower == upper) return sorted.get(lower);
        double fraction = position - lower;
        return sorted.get(lower) * (1.0 - fraction) + sorted.get(upper) * fraction;
    }

    private static String formatNumber(double value) {
        return Double.isFinite(value) ? String.format(Locale.US, "%.6f", value) : "";
    }

    private static String deviceMetadata() {
        StringBuilder text = new StringBuilder();
        text.append("field,value\n");
        text.append(row("app_version", BuildConfig.VERSION_NAME));
        text.append(row("manufacturer", Build.MANUFACTURER));
        text.append(row("model", Build.MODEL));
        text.append(row("device", Build.DEVICE));
        text.append(row("android_release", Build.VERSION.RELEASE));
        text.append(row("sdk_int", Build.VERSION.SDK_INT));
        text.append(row("export_timestamp_utc", utcTimestamp(System.currentTimeMillis())));
        text.append(row("locale", Locale.getDefault().toLanguageTag()));
        return text.toString();
    }

    private static Object nullable(Cursor cursor, int index) {
        if (cursor.isNull(index)) return "";
        int type = cursor.getType(index);
        if (type == Cursor.FIELD_TYPE_INTEGER) return cursor.getLong(index);
        if (type == Cursor.FIELD_TYPE_FLOAT) return cursor.getDouble(index);
        return cursor.getString(index);
    }

    private static Object finite(double value) {
        return Double.isFinite(value) ? String.format(Locale.US, "%.9f", value) : "";
    }

    private static String row(Object... values) {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < values.length; i++) {
            if (i > 0) builder.append(',');
            builder.append(csv(values[i]));
        }
        return builder.append('\n').toString();
    }

    private static String csv(Object value) {
        String text = value == null ? "" : String.valueOf(value);
        if (text.indexOf(',') >= 0 || text.indexOf('"') >= 0 || text.indexOf('\n') >= 0) {
            return '"' + text.replace("\"", "\"\"") + '"';
        }
        return text;
    }

    private static String utcTimestamp(long millis) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(millis));
    }

    private static void put(ZipOutputStream zip, String name, String content) throws IOException {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(content.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }
}
