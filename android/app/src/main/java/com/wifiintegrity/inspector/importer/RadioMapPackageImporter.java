package com.wifiintegrity.inspector.importer;

import android.content.ContentValues;
import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.net.Uri;

import com.wifiintegrity.inspector.repository.RadioMapRepository;
import com.wifiintegrity.inspector.util.CsvTable;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public final class RadioMapPackageImporter {
    private final Context context;
    private final RadioMapRepository repository;

    public RadioMapPackageImporter(Context context, RadioMapRepository repository) {
        this.context = context.getApplicationContext();
        this.repository = repository;
    }

    public String importPackage(Uri uri) throws Exception {
        Map<String, byte[]> entries = readZip(uri);
        JSONObject manifest = new JSONObject(requireText(entries, "manifest.json"));
        JSONObject buildingJson = manifest.getJSONObject("building");
        String buildingName = buildingJson.getString("name").trim();
        String buildingUniqueId = buildingJson.getString("unique_id").trim();
        if (buildingName.isEmpty() || buildingUniqueId.isEmpty()) throw new IllegalArgumentException("Building name and unique_id are required.");

        List<Map<String, String>> floors = CsvTable.parse(requireText(entries, "floors.csv"));
        List<Map<String, String>> rps = CsvTable.parse(requireText(entries, "reference_points.csv"));
        List<Map<String, String>> fingerprints = CsvTable.parse(requireText(entries, "fingerprints.csv"));
        List<Map<String, String>> calibration = entries.containsKey("calibration.csv")
                ? CsvTable.parse(new String(entries.get("calibration.csv"), StandardCharsets.UTF_8)) : new ArrayList<>();
        if (floors.isEmpty()) throw new IllegalArgumentException("floors.csv contains no floors.");
        if (rps.isEmpty()) throw new IllegalArgumentException("reference_points.csv contains no reference points.");
        if (fingerprints.isEmpty()) throw new IllegalArgumentException("fingerprints.csv contains no observations.");

        SQLiteDatabase db = repository.writableDatabase();
        db.beginTransaction();
        try {
            ContentValues buildingValues = new ContentValues();
            buildingValues.put("name", buildingName);
            buildingValues.put("unique_id", buildingUniqueId);
            long buildingId = db.insertOrThrow("buildings", null, buildingValues);

            Map<String, Long> floorIds = new HashMap<>();
            Map<String, Map<String, Integer>> apIdsByFloor = new HashMap<>();
            Map<String, Integer> nextApByFloor = new HashMap<>();
            for (Map<String, String> row : floors) {
                String uniqueFloor = required(row, "floor_unique_id");
                ContentValues values = new ContentValues();
                values.put("building_id", buildingId);
                values.put("number", parseInt(row.get("number"), 0));
                values.put("name", row.getOrDefault("name", uniqueFloor));
                values.put("unique_id", uniqueFloor);
                values.put("rotation_angle", parseDouble(row.get("rotation_angle"), 0.0));
                values.put("min_x", parseDouble(required(row, "min_x"), 0.0));
                values.put("min_y", parseDouble(required(row, "min_y"), 0.0));
                values.put("max_x", parseDouble(required(row, "max_x"), 1.0));
                values.put("max_y", parseDouble(required(row, "max_y"), 1.0));
                values.put("density_radius", parseDouble(row.get("density_radius"), 5.0));
                values.put("calibration_mode", calibration.isEmpty() ? "uncalibrated" : "imported");
                String planFile = row.getOrDefault("floorplan_file", "").trim();
                if (!planFile.isEmpty()) {
                    byte[] image = entries.get(planFile);
                    if (image == null) image = entries.get("floorplans/" + planFile);
                    if (image != null) {
                        File directory = new File(context.getFilesDir(), "floorplans");
                        if (!directory.exists() && !directory.mkdirs()) throw new IOException("Cannot create floor-plan directory.");
                        File imageFile = new File(directory, uniqueFloor + ".png");
                        try (FileOutputStream output = new FileOutputStream(imageFile)) { output.write(image); }
                        values.put("floor_plan_path", "file:" + imageFile.getAbsolutePath());
                    }
                }
                long floorId = db.insertOrThrow("floors", null, values);
                floorIds.put(uniqueFloor, floorId);
                apIdsByFloor.put(uniqueFloor, new LinkedHashMap<>());
                nextApByFloor.put(uniqueFloor, 1);
            }

            Map<String, Long> rpIds = new HashMap<>();
            Map<String, Long> templateIds = new HashMap<>();
            Map<String, String> rpFloor = new HashMap<>();
            Map<String, Integer> localTemplateCount = new HashMap<>();
            for (Map<String, String> row : rps) {
                String rpKey = required(row, "rp_id");
                String floorKey = required(row, "floor_unique_id");
                Long floorId = floorIds.get(floorKey);
                if (floorId == null) throw new IllegalArgumentException("Unknown floor in reference_points.csv: " + floorKey);
                double x = parseDouble(required(row, "x"), 0.0);
                double y = parseDouble(required(row, "y"), 0.0);
                ContentValues values = new ContentValues();
                values.put("floor_id", floorId);
                values.put("x", x);
                values.put("y", y);
                if (row.containsKey("lat") && !row.get("lat").isEmpty()) values.put("lat", parseDouble(row.get("lat"), 0.0));
                if (row.containsKey("lng") && !row.get("lng").isEmpty()) values.put("lng", parseDouble(row.get("lng"), 0.0));
                long rpId = db.insertOrThrow("reference_points", null, values);
                rpIds.put(rpKey, rpId);
                rpFloor.put(rpKey, floorKey);
                int local = localTemplateCount.getOrDefault(floorKey, 0) + 1;
                localTemplateCount.put(floorKey, local);
                ContentValues template = new ContentValues();
                template.put("floor_id", floorId);
                template.put("local_id", local);
                template.put("x", x);
                template.put("y", y);
                templateIds.put(rpKey, db.insertOrThrow("templates", null, template));
            }

            for (Map<String, String> row : fingerprints) {
                String rpKey = required(row, "rp_id");
                Long rpId = rpIds.get(rpKey);
                Long templateId = templateIds.get(rpKey);
                String floorKey = rpFloor.get(rpKey);
                if (rpId == null || templateId == null || floorKey == null) throw new IllegalArgumentException("Unknown rp_id in fingerprints.csv: " + rpKey);
                String bssid = RadioMapRepository.normalizeBssid(required(row, "bssid"));
                double rss = parseDouble(required(row, "rss"), -110.0);
                Map<String, Integer> apMap = apIdsByFloor.get(floorKey);
                Integer apId = apMap.get(bssid);
                if (apId == null) {
                    apId = nextApByFloor.get(floorKey);
                    nextApByFloor.put(floorKey, apId + 1);
                    apMap.put(bssid, apId);
                    ContentValues ap = new ContentValues();
                    ap.put("floor_id", floorIds.get(floorKey));
                    ap.put("ap_id", apId);
                    ap.put("bssid", bssid);
                    db.insertOrThrow("access_points", null, ap);
                }
                ContentValues obs = new ContentValues();
                obs.put("rp_id", rpId);
                obs.put("ap_id", apId);
                obs.put("rss", rss);
                db.insertWithOnConflict("rp_observations", null, obs, SQLiteDatabase.CONFLICT_REPLACE);
                ContentValues templateObs = new ContentValues();
                templateObs.put("template_id", templateId);
                templateObs.put("ap_id", apId);
                templateObs.put("rss", rss);
                db.insertWithOnConflict("template_observations", null, templateObs, SQLiteDatabase.CONFLICT_REPLACE);
            }

            for (Map<String, String> row : calibration) {
                String floorKey = required(row, "floor_unique_id");
                Long floorId = floorIds.get(floorKey);
                if (floorId == null) continue;
                ContentValues values = new ContentValues();
                values.put("floor_id", floorId);
                values.put("estimator", row.getOrDefault("estimator", "WKNN-k3"));
                values.put("indicator_id", required(row, "indicator_id"));
                values.put("adverse_direction", required(row, "adverse_direction"));
                values.put("q05", parseDouble(required(row, "q05"), 0.0));
                values.put("q95", parseDouble(required(row, "q95"), 1.0));
                values.put("sorted_values_json", required(row, "sorted_values_json"));
                db.insertOrThrow("calibration_values", null, values);
            }

            db.setTransactionSuccessful();
            return String.format(Locale.US, "Imported %s with %d floor(s), %d reference point(s), and %d fingerprint observations.",
                    buildingName, floors.size(), rps.size(), fingerprints.size());
        } finally {
            db.endTransaction();
        }
    }

    private Map<String, byte[]> readZip(Uri uri) throws IOException {
        Map<String, byte[]> entries = new HashMap<>();
        try (InputStream input = context.getContentResolver().openInputStream(uri);
             ZipInputStream zip = new ZipInputStream(input)) {
            ZipEntry entry;
            byte[] buffer = new byte[32 * 1024];
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                String name = entry.getName().replace('\\', '/');
                if (name.contains("../")) throw new IOException("Unsafe ZIP path: " + name);
                ByteArrayOutputStream output = new ByteArrayOutputStream();
                int read;
                while ((read = zip.read(buffer)) >= 0) output.write(buffer, 0, read);
                entries.put(name, output.toByteArray());
                zip.closeEntry();
            }
        }
        return entries;
    }

    private static String requireText(Map<String, byte[]> entries, String name) {
        byte[] value = entries.get(name);
        if (value == null) throw new IllegalArgumentException("Missing required package file: " + name);
        return new String(value, StandardCharsets.UTF_8);
    }

    private static String required(Map<String, String> row, String key) {
        String value = row.get(key);
        if (value == null || value.trim().isEmpty()) throw new IllegalArgumentException("Missing required CSV value: " + key);
        return value.trim();
    }

    private static int parseInt(String value, int fallback) {
        try { return Integer.parseInt(value); } catch (Exception ignored) { return fallback; }
    }

    private static double parseDouble(String value, double fallback) {
        try { return Double.parseDouble(value); } catch (Exception ignored) { return fallback; }
    }
}
