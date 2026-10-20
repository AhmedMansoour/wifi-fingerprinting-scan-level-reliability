package com.wifiintegrity.inspector.repository;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import com.wifiintegrity.inspector.data.DatabaseHelper;
import com.wifiintegrity.inspector.diagnostics.DiagnosticEngine;
import com.wifiintegrity.inspector.model.Building;
import com.wifiintegrity.inspector.model.CalibrationSeries;
import com.wifiintegrity.inspector.model.DiagnosticResult;
import com.wifiintegrity.inspector.model.FloorData;
import com.wifiintegrity.inspector.model.FloorInfo;
import com.wifiintegrity.inspector.model.FloorInferenceProfile;
import com.wifiintegrity.inspector.model.FloorInferenceResult;
import com.wifiintegrity.inspector.model.HistoryItem;
import com.wifiintegrity.inspector.model.ReferenceTemplate;
import com.wifiintegrity.inspector.model.SavedInspection;
import com.wifiintegrity.inspector.model.ScanObservation;
import com.wifiintegrity.inspector.util.JsonCodec;

import org.json.JSONArray;
import org.json.JSONException;

import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public final class RadioMapRepository {
    private final DatabaseHelper helper;
    private final Context appContext;

    public RadioMapRepository(Context context) {
        appContext = context.getApplicationContext();
        helper = DatabaseHelper.getInstance(appContext);
    }

    public List<Building> listBuildings() {
        List<Building> result = new ArrayList<>();
        try (Cursor cursor = helper.getDatabase().rawQuery(
                "SELECT id,name,unique_id FROM buildings ORDER BY name", null)) {
            while (cursor.moveToNext()) {
                result.add(new Building(cursor.getLong(0), cursor.getString(1), cursor.getString(2)));
            }
        }
        return result;
    }

    public List<FloorInfo> listFloors(long buildingId) {
        List<FloorInfo> result = new ArrayList<>();
        try (Cursor cursor = helper.getDatabase().rawQuery(
                "SELECT id,building_id,number,name,unique_id,rotation_angle,min_x,min_y,max_x,max_y," +
                        "floor_plan_path,density_radius,calibration_mode FROM floors WHERE building_id=? ORDER BY number",
                new String[]{Long.toString(buildingId)})) {
            while (cursor.moveToNext()) result.add(readFloor(cursor));
        }
        return result;
    }

    public FloorInfo getFloor(long floorId) {
        try (Cursor cursor = helper.getDatabase().rawQuery(
                "SELECT id,building_id,number,name,unique_id,rotation_angle,min_x,min_y,max_x,max_y," +
                        "floor_plan_path,density_radius,calibration_mode FROM floors WHERE id=?",
                new String[]{Long.toString(floorId)})) {
            if (!cursor.moveToFirst()) throw new IllegalArgumentException("Unknown floor: " + floorId);
            return readFloor(cursor);
        }
    }

    private FloorInfo readFloor(Cursor cursor) {
        String planPath = cursor.isNull(10) ? null : cursor.getString(10);
        return new FloorInfo(
                cursor.getLong(0), cursor.getLong(1), cursor.getInt(2), cursor.getString(3), cursor.getString(4),
                cursor.getDouble(5), cursor.getDouble(6), cursor.getDouble(7), cursor.getDouble(8), cursor.getDouble(9),
                readFloorPlan(planPath), cursor.getDouble(11), cursor.getString(12));
    }

    private byte[] readFloorPlan(String path) {
        if (path == null || path.isEmpty()) return null;
        try (InputStream input = path.startsWith("asset:")
                ? appContext.getAssets().open(path.substring("asset:".length()))
                : new FileInputStream(path.startsWith("file:") ? path.substring("file:".length()) : path);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) output.write(buffer, 0, read);
            return output.toByteArray();
        } catch (Exception ignored) {
            return null;
        }
    }

    public FloorData loadFloorData(Building building, FloorInfo floor, int calibrationK) {
        SQLiteDatabase db = helper.getDatabase();
        List<Integer> apIds = new ArrayList<>();
        Map<String, Integer> bssidToAp = loadAccessPoints(db, floor.id, apIds);
        List<double[]> referencePoints = loadReferencePoints(db, floor.id);
        List<ReferenceTemplate> templates = loadTemplates(db, floor.id);

        String estimator = "WKNN-k" + calibrationK;
        Map<String, CalibrationSeries> calibration = loadCalibration(db, floor.id, estimator);
        return new FloorData(building, floor, bssidToAp, apIds, referencePoints, templates,
                calibration, estimator, DiagnosticEngine.DIAGNOSTIC_M);
    }

    public List<FloorInferenceProfile> loadFloorInferenceProfiles(Building building, List<FloorInfo> floors) {
        SQLiteDatabase db = helper.getDatabase();
        List<FloorInferenceProfile> profiles = new ArrayList<>();
        for (FloorInfo floor : floors) {
            List<Integer> apIds = new ArrayList<>();
            Map<String, Integer> bssidToAp = loadAccessPoints(db, floor.id, apIds);
            List<ReferenceTemplate> templates = loadTemplates(db, floor.id);
            if (!apIds.isEmpty() && !templates.isEmpty()) {
                profiles.add(new FloorInferenceProfile(building, floor, bssidToAp, apIds, templates));
            }
        }
        return profiles;
    }

    private Map<String, Integer> loadAccessPoints(SQLiteDatabase db, long floorId, List<Integer> apIds) {
        Map<String, Integer> bssidToAp = new HashMap<>();
        try (Cursor cursor = db.rawQuery(
                "SELECT ap_id,bssid FROM access_points WHERE floor_id=? ORDER BY ap_id",
                new String[]{Long.toString(floorId)})) {
            while (cursor.moveToNext()) {
                int apId = cursor.getInt(0);
                apIds.add(apId);
                bssidToAp.put(normalizeBssid(cursor.getString(1)), apId);
            }
        }
        return bssidToAp;
    }

    private List<double[]> loadReferencePoints(SQLiteDatabase db, long floorId) {
        List<double[]> referencePoints = new ArrayList<>();
        try (Cursor cursor = db.rawQuery(
                "SELECT x,y FROM reference_points WHERE floor_id=? ORDER BY id",
                new String[]{Long.toString(floorId)})) {
            while (cursor.moveToNext()) referencePoints.add(new double[]{cursor.getDouble(0), cursor.getDouble(1)});
        }
        return referencePoints;
    }

    private List<ReferenceTemplate> loadTemplates(SQLiteDatabase db, long floorId) {
        Map<Long, TemplateBuilder> builders = new LinkedHashMap<>();
        try (Cursor cursor = db.rawQuery(
                "SELECT id,local_id,x,y FROM templates WHERE floor_id=? ORDER BY local_id",
                new String[]{Long.toString(floorId)})) {
            while (cursor.moveToNext()) {
                long id = cursor.getLong(0);
                builders.put(id, new TemplateBuilder(id, cursor.getInt(1), cursor.getDouble(2), cursor.getDouble(3)));
            }
        }
        try (Cursor cursor = db.rawQuery(
                "SELECT o.template_id,o.ap_id,o.rss FROM template_observations o " +
                        "JOIN templates t ON t.id=o.template_id WHERE t.floor_id=? ORDER BY o.template_id,o.ap_id",
                new String[]{Long.toString(floorId)})) {
            while (cursor.moveToNext()) {
                TemplateBuilder builder = builders.get(cursor.getLong(0));
                if (builder != null) builder.fingerprint.put(cursor.getInt(1), cursor.getDouble(2));
            }
        }
        List<ReferenceTemplate> templates = new ArrayList<>();
        for (TemplateBuilder builder : builders.values()) templates.add(builder.build());
        return templates;
    }

    private Map<String, CalibrationSeries> loadCalibration(SQLiteDatabase db, long floorId, String estimator) {
        Map<String, CalibrationSeries> calibration = new HashMap<>();
        try (Cursor cursor = db.rawQuery(
                "SELECT indicator_id,adverse_direction,q05,q95,sorted_values_json FROM calibration_values " +
                        "WHERE floor_id=? AND estimator=?",
                new String[]{Long.toString(floorId), estimator})) {
            while (cursor.moveToNext()) {
                String id = cursor.getString(0);
                calibration.put(id, new CalibrationSeries(id, cursor.getString(1), cursor.getDouble(2),
                        cursor.getDouble(3), parseDoubleArray(cursor.getString(4))));
            }
        }
        // Deliberately no fallback: warnings must use the exact floor-estimator calibration.
        return calibration;
    }

    private static double[] parseDoubleArray(String json) {
        try {
            JSONArray array = new JSONArray(json);
            double[] values = new double[array.length()];
            for (int i = 0; i < values.length; i++) values[i] = array.getDouble(i);
            return values;
        } catch (JSONException error) {
            return new double[0];
        }
    }

    public long saveInspection(FloorData floorData, List<ScanObservation> scan,
                               DiagnosticResult result, FloorInferenceResult inference) {
        ContentValues values = new ContentValues();
        values.put("created_at", System.currentTimeMillis());
        values.put("building_name", floorData.building.name);
        values.put("floor_name", floorData.floor.name);
        values.put("floor_id", floorData.floor.id);
        values.put("estimator", "WKNN-k" + result.wknnK);
        values.put("observed_aps", result.observedApCount);
        values.put("mapped_aps", result.mappedApCount);
        values.put("novel_aps", result.novelApCount);
        values.put("estimate_x", result.estimateX);
        values.put("estimate_y", result.estimateY);
        values.put("sqs", Double.isFinite(result.sqs) ? result.sqs : -1.0);
        values.put("warning_count", result.warningCount);
        values.put("processing_ms", result.processingMs);
        values.put("scan_json", JsonCodec.scanToJson(scan));
        values.put("result_json", JsonCodec.resultToJson(result));
        values.put("floor_inferred", inference == null ? 0 : 1);
        if (inference != null) {
            values.put("floor_score", inference.score);
            values.put("floor_margin", inference.margin);
            values.put("floor_confidence", inference.confidence);
            values.put("floor_ranking_json", JsonCodec.floorRankingToJson(inference.ranking));
        }
        putProcessingTimes(values, result);
        return helper.getDatabase().insertOrThrow("scan_inspections", null, values);
    }

    public void updateInspectionResult(long historyId, DiagnosticResult result) {
        ContentValues values = new ContentValues();
        values.put("processing_ms", result.processingMs);
        values.put("result_json", JsonCodec.resultToJson(result));
        putProcessingTimes(values, result);
        helper.getDatabase().update("scan_inspections", values, "id=?", new String[]{Long.toString(historyId)});
    }

    private static void putProcessingTimes(ContentValues values, DiagnosticResult result) {
        putFinite(values, "scan_acquisition_ms", result.processingTimes.scanAcquisitionMs);
        putFinite(values, "floor_inference_ms", result.processingTimes.floorInferenceMs);
        putFinite(values, "radio_map_load_ms", result.processingTimes.radioMapLoadMs);
        putFinite(values, "fingerprint_preparation_ms", result.processingTimes.fingerprintPreparationMs);
        putFinite(values, "candidate_retrieval_ms", result.processingTimes.candidateRetrievalMs);
        putFinite(values, "position_estimation_ms", result.processingTimes.positionEstimationMs);
        putFinite(values, "indicator_computation_ms", result.processingTimes.indicatorComputationMs);
        putFinite(values, "diagnosis_total_ms", result.processingTimes.diagnosisTotalMs);
        putFinite(values, "post_scan_processing_ms", result.processingTimes.postScanProcessingMs);
        putFinite(values, "persistence_ms", result.processingTimes.persistenceMs);
    }

    private static void putFinite(ContentValues values, String key, double value) {
        if (Double.isFinite(value)) values.put(key, value); else values.putNull(key);
    }

    public long saveInspection(FloorData floorData, List<ScanObservation> scan, DiagnosticResult result) {
        return saveInspection(floorData, scan, result, null);
    }

    public void saveValidation(long historyId, double x, double y, double errorM) {
        ContentValues values = new ContentValues();
        values.put("validation_x", x);
        values.put("validation_y", y);
        values.put("validation_error_m", errorM);
        helper.getDatabase().update("scan_inspections", values, "id=?", new String[]{Long.toString(historyId)});
    }

    public List<HistoryItem> listHistory() {
        List<HistoryItem> result = new ArrayList<>();
        try (Cursor cursor = helper.getDatabase().rawQuery(
                "SELECT id,created_at,building_name,floor_name,estimator,sqs,warning_count,mapped_aps,estimate_x,estimate_y," +
                        "floor_inferred,floor_confidence,validation_error_m FROM scan_inspections ORDER BY created_at DESC", null)) {
            while (cursor.moveToNext()) {
                result.add(new HistoryItem(cursor.getLong(0), cursor.getLong(1), cursor.getString(2), cursor.getString(3),
                        cursor.getString(4), cursor.getDouble(5), cursor.getInt(6), cursor.getInt(7), cursor.getDouble(8),
                        cursor.getDouble(9), cursor.getInt(10) == 1, cursor.isNull(11) ? null : cursor.getString(11),
                        cursor.isNull(12) ? null : cursor.getDouble(12)));
            }
        }
        return result;
    }

    public SavedInspection loadInspection(long id) {
        try (Cursor cursor = helper.getDatabase().rawQuery(
                "SELECT id,floor_id,created_at,building_name,floor_name,estimator,scan_json,result_json," +
                        "floor_inferred,floor_score,floor_margin,floor_confidence,validation_x,validation_y,validation_error_m " +
                        "FROM scan_inspections WHERE id=?", new String[]{Long.toString(id)})) {
            if (!cursor.moveToFirst()) throw new IllegalArgumentException("Unknown inspection: " + id);
            try {
                List<ScanObservation> scan = JsonCodec.scanFromJson(cursor.getString(6));
                DiagnosticResult result = JsonCodec.resultFromJson(cursor.getString(7));
                return new SavedInspection(cursor.getLong(0), cursor.getLong(1), cursor.getLong(2), cursor.getString(3),
                        cursor.getString(4), cursor.getString(5), scan, result,
                        cursor.getInt(8) == 1,
                        cursor.isNull(9) ? null : cursor.getDouble(9),
                        cursor.isNull(10) ? null : cursor.getDouble(10),
                        cursor.isNull(11) ? null : cursor.getString(11),
                        cursor.isNull(12) ? null : cursor.getDouble(12),
                        cursor.isNull(13) ? null : cursor.getDouble(13),
                        cursor.isNull(14) ? null : cursor.getDouble(14));
            } catch (JSONException error) {
                throw new IllegalStateException("Saved inspection is corrupted", error);
            }
        }
    }

    public Building getBuilding(long buildingId) {
        try (Cursor cursor = helper.getDatabase().rawQuery(
                "SELECT id,name,unique_id FROM buildings WHERE id=?", new String[]{Long.toString(buildingId)})) {
            if (!cursor.moveToFirst()) throw new IllegalArgumentException("Unknown building: " + buildingId);
            return new Building(cursor.getLong(0), cursor.getString(1), cursor.getString(2));
        }
    }

    public List<String> listRadioMapSummary() {
        List<String> rows = new ArrayList<>();
        try (Cursor cursor = helper.getDatabase().rawQuery(
                "SELECT b.name,f.name,f.calibration_mode,CASE WHEN f.floor_plan_path IS NULL THEN 0 ELSE 1 END," +
                        "(SELECT COUNT(*) FROM reference_points r WHERE r.floor_id=f.id)," +
                        "(SELECT COUNT(*) FROM access_points a WHERE a.floor_id=f.id)," +
                        "(SELECT COUNT(DISTINCT estimator) FROM calibration_values c WHERE c.floor_id=f.id) " +
                        "FROM floors f JOIN buildings b ON b.id=f.building_id ORDER BY b.name,f.number", null)) {
            while (cursor.moveToNext()) {
                rows.add(String.format(Locale.US, "%s — %s\nRPs: %d  APs: %d  View: %s  Calibration profiles: %d (%s)",
                        cursor.getString(0), cursor.getString(1), cursor.getInt(4), cursor.getInt(5),
                        cursor.getInt(3) == 1 ? "floor image" : "coordinates", cursor.getInt(6), cursor.getString(2)));
            }
        }
        return rows;
    }

    public SQLiteDatabase writableDatabase() { return helper.getDatabase(); }

    public static String normalizeBssid(String value) {
        if (value == null) return "";
        return value.trim().toLowerCase(Locale.US).replace('-', ':');
    }

    private static final class TemplateBuilder {
        final long id;
        final int localId;
        final double x;
        final double y;
        final Map<Integer, Double> fingerprint = new HashMap<>();

        TemplateBuilder(long id, int localId, double x, double y) {
            this.id = id;
            this.localId = localId;
            this.x = x;
            this.y = y;
        }

        ReferenceTemplate build() { return new ReferenceTemplate(id, localId, x, y, fingerprint); }
    }
}
