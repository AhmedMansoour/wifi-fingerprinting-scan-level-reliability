package com.wifiintegrity.inspector.data;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import java.io.File;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.io.IOException;
import java.io.InputStream;

public final class DatabaseHelper {
    private static final String DATABASE_NAME = "wifi_integrity_v103.db";
    private static final String LEGACY_DATABASE_NAME = "wifi_integrity.db";
    private static final String SCHEMA_PATH = "database/schema.sql";
    private static volatile DatabaseHelper instance;

    private final Context appContext;
    private final File databaseFile;
    private SQLiteDatabase database;

    private DatabaseHelper(Context context) {
        this.appContext = context.getApplicationContext();
        this.databaseFile = appContext.getDatabasePath(DATABASE_NAME);
    }

    public static DatabaseHelper getInstance(Context context) {
        if (instance == null) {
            synchronized (DatabaseHelper.class) {
                if (instance == null) instance = new DatabaseHelper(context);
            }
        }
        return instance;
    }

    public synchronized SQLiteDatabase getDatabase() {
        if (database == null || !database.isOpen()) {
            ensureDatabaseCopied();
            database = SQLiteDatabase.openDatabase(databaseFile.getAbsolutePath(), null, SQLiteDatabase.OPEN_READWRITE);
            database.execSQL("PRAGMA foreign_keys=ON");
            ensureRuntimeSchema(database);
            migrateLegacyHistory(database);
        }
        return database;
    }

    private void ensureDatabaseCopied() {
        if (databaseFile.exists() && databaseFile.length() > 0) return;
        File parent = databaseFile.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IllegalStateException("Cannot create database directory: " + parent);
        }
        try (InputStream input = appContext.getAssets().open(SCHEMA_PATH);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) >= 0) output.write(buffer, 0, read);
            SQLiteDatabase db = SQLiteDatabase.openOrCreateDatabase(databaseFile, null);
            try {
                db.beginTransaction();
                try {
                    String schema = new String(output.toByteArray(), StandardCharsets.UTF_8);
                    for (String statement : schema.split(";")) {
                        if (!statement.trim().isEmpty()) db.execSQL(statement.trim());
                    }
                    db.setTransactionSuccessful();
                } finally { db.endTransaction(); }
            } finally { db.close(); }
        } catch (IOException error) {
            throw new IllegalStateException("Cannot create the empty radio-map database", error);
        } catch (RuntimeException error) {
            SQLiteDatabase.deleteDatabase(databaseFile);
            throw error;
        }
    }

    private static void ensureRuntimeSchema(SQLiteDatabase db) {
        addColumnIfMissing(db, "scan_inspections", "floor_inferred", "INTEGER NOT NULL DEFAULT 0");
        addColumnIfMissing(db, "scan_inspections", "floor_score", "REAL");
        addColumnIfMissing(db, "scan_inspections", "floor_margin", "REAL");
        addColumnIfMissing(db, "scan_inspections", "floor_confidence", "TEXT");
        addColumnIfMissing(db, "scan_inspections", "validation_x", "REAL");
        addColumnIfMissing(db, "scan_inspections", "validation_y", "REAL");
        addColumnIfMissing(db, "scan_inspections", "validation_error_m", "REAL");
        addColumnIfMissing(db, "scan_inspections", "floor_ranking_json", "TEXT");
        addColumnIfMissing(db, "scan_inspections", "scan_acquisition_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "floor_inference_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "radio_map_load_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "fingerprint_preparation_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "candidate_retrieval_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "position_estimation_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "indicator_computation_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "diagnosis_total_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "post_scan_processing_ms", "REAL");
        addColumnIfMissing(db, "scan_inspections", "persistence_ms", "REAL");
    }

    private static void addColumnIfMissing(SQLiteDatabase db, String table, String column, String definition) {
        boolean exists = false;
        try (Cursor cursor = db.rawQuery("PRAGMA table_info(" + table + ")", null)) {
            while (cursor.moveToNext()) {
                if (column.equals(cursor.getString(1))) {
                    exists = true;
                    break;
                }
            }
        }
        if (!exists) db.execSQL("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition);
    }

    private void migrateLegacyHistory(SQLiteDatabase db) {
        File legacy = appContext.getDatabasePath(LEGACY_DATABASE_NAME);
        if (!legacy.exists() || legacy.length() == 0) return;
        String migrated = null;
        try (Cursor cursor = db.rawQuery("SELECT value FROM metadata WHERE key='legacy_history_migrated'", null)) {
            if (cursor.moveToFirst()) migrated = cursor.getString(0);
        } catch (Exception ignored) { }
        if ("1".equals(migrated)) return;

        try {
            db.execSQL("ATTACH DATABASE ? AS legacy_db", new Object[]{legacy.getAbsolutePath()});
            db.execSQL("INSERT INTO scan_inspections(created_at,building_name,floor_name,floor_id,estimator," +
                    "observed_aps,mapped_aps,novel_aps,estimate_x,estimate_y,sqs,warning_count,processing_ms,scan_json,result_json) " +
                    "SELECT created_at,building_name,floor_name,floor_id,estimator,observed_aps,mapped_aps,novel_aps," +
                    "estimate_x,estimate_y,sqs,warning_count,processing_ms,scan_json,result_json FROM legacy_db.scan_inspections");
        } catch (Exception ignored) {
            // History migration is best-effort and must never block opening the new radio map.
        } finally {
            try { db.execSQL("DETACH DATABASE legacy_db"); } catch (Exception ignored) { }
            try { db.execSQL("INSERT OR REPLACE INTO metadata(key,value) VALUES('legacy_history_migrated','1')"); }
            catch (Exception ignored) { }
        }
    }
}
