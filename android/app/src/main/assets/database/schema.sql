CREATE TABLE access_points(
            floor_id INTEGER NOT NULL REFERENCES floors(id) ON DELETE CASCADE,
            ap_id INTEGER NOT NULL,
            bssid TEXT NOT NULL,
            PRIMARY KEY(floor_id, ap_id),
            UNIQUE(floor_id, bssid)
        );
CREATE TABLE buildings(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            unique_id TEXT NOT NULL UNIQUE
        );
CREATE TABLE calibration_values(
            floor_id INTEGER NOT NULL REFERENCES floors(id) ON DELETE CASCADE,
            estimator TEXT NOT NULL,
            indicator_id TEXT NOT NULL,
            adverse_direction TEXT NOT NULL,
            q05 REAL NOT NULL,
            q95 REAL NOT NULL,
            sorted_values_json TEXT NOT NULL,
            PRIMARY KEY(floor_id, estimator, indicator_id)
        );
CREATE TABLE floors(
            id INTEGER PRIMARY KEY,
            building_id INTEGER NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
            number INTEGER NOT NULL,
            name TEXT NOT NULL,
            unique_id TEXT NOT NULL UNIQUE,
            rotation_angle REAL NOT NULL DEFAULT 0,
            min_x REAL NOT NULL,
            min_y REAL NOT NULL,
            max_x REAL NOT NULL,
            max_y REAL NOT NULL,
            max_pressure REAL,
            min_pressure REAL,
            mean_pressure REAL,
            floor_plan_path TEXT,
            density_radius REAL NOT NULL DEFAULT 5,
            calibration_mode TEXT NOT NULL DEFAULT 'provisional',
            UNIQUE(building_id, number)
        );
CREATE TABLE indicator_definitions(
            position INTEGER PRIMARY KEY,
            indicator_id TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            group_name TEXT NOT NULL,
            adverse_direction TEXT NOT NULL
        );
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE reference_points(
            id INTEGER PRIMARY KEY,
            floor_id INTEGER NOT NULL REFERENCES floors(id) ON DELETE CASCADE,
            x REAL NOT NULL,
            y REAL NOT NULL,
            lat REAL,
            lng REAL,
            accuracy REAL,
            magnetic REAL
        );
CREATE TABLE rp_observations(
            rp_id INTEGER NOT NULL REFERENCES reference_points(id) ON DELETE CASCADE,
            ap_id INTEGER NOT NULL,
            rss REAL NOT NULL,
            PRIMARY KEY(rp_id, ap_id)
        );
CREATE TABLE scan_inspections(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at INTEGER NOT NULL,
            building_name TEXT NOT NULL,
            floor_name TEXT NOT NULL,
            floor_id INTEGER NOT NULL,
            estimator TEXT NOT NULL,
            observed_aps INTEGER NOT NULL,
            mapped_aps INTEGER NOT NULL,
            novel_aps INTEGER NOT NULL,
            estimate_x REAL NOT NULL,
            estimate_y REAL NOT NULL,
            sqs REAL NOT NULL,
            warning_count INTEGER NOT NULL,
            processing_ms REAL NOT NULL,
            scan_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        , floor_inferred INTEGER NOT NULL DEFAULT 0, floor_score REAL, floor_margin REAL, floor_confidence TEXT, validation_x REAL, validation_y REAL, validation_error_m REAL, floor_ranking_json TEXT, scan_acquisition_ms REAL, floor_inference_ms REAL, radio_map_load_ms REAL, fingerprint_preparation_ms REAL, candidate_retrieval_ms REAL, position_estimation_ms REAL, indicator_computation_ms REAL, diagnosis_total_ms REAL, post_scan_processing_ms REAL, persistence_ms REAL);
CREATE TABLE template_observations(
            template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
            ap_id INTEGER NOT NULL,
            rss REAL NOT NULL,
            PRIMARY KEY(template_id, ap_id)
        );
CREATE TABLE templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            floor_id INTEGER NOT NULL REFERENCES floors(id) ON DELETE CASCADE,
            local_id INTEGER NOT NULL,
            x REAL NOT NULL,
            y REAL NOT NULL,
            UNIQUE(floor_id, local_id)
        );
CREATE INDEX idx_ap_floor_bssid ON access_points(floor_id, bssid);
CREATE INDEX idx_calibration_floor ON calibration_values(floor_id, estimator);
CREATE INDEX idx_floors_building ON floors(building_id);
CREATE INDEX idx_rp_floor ON reference_points(floor_id);
CREATE INDEX idx_template_floor ON templates(floor_id);