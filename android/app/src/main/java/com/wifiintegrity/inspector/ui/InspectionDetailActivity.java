package com.wifiintegrity.inspector.ui;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import android.widget.Toast;

import com.wifiintegrity.inspector.R;
import com.wifiintegrity.inspector.model.Building;
import com.wifiintegrity.inspector.model.FloorData;
import com.wifiintegrity.inspector.model.FloorInfo;
import com.wifiintegrity.inspector.model.ProcessingTimes;
import com.wifiintegrity.inspector.model.SavedInspection;
import com.wifiintegrity.inspector.repository.RadioMapRepository;

import java.text.DateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class InspectionDetailActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_detail);
        long id = getIntent().getLongExtra("inspection_id", -1L);
        if (id < 0) {
            finish();
            return;
        }
        RadioMapRepository repository = new RadioMapRepository(this);
        TextView summary = findViewById(R.id.textDetailSummary);
        RadioMapView mapView = findViewById(R.id.detailMapView);
        IndicatorBarView indicatorView = findViewById(R.id.detailIndicatorView);
        executor.execute(() -> {
            try {
                SavedInspection inspection = repository.loadInspection(id);
                FloorInfo floor = repository.getFloor(inspection.floorId);
                Building building = repository.getBuilding(floor.buildingId);
                int k = parseK(inspection.estimator);
                FloorData floorData = repository.loadFloorData(building, floor, k);
                runOnUiThread(() -> {
                    String inferred = inspection.floorInferred
                            ? String.format(Locale.US, "yes (%s; score %s; margin %s)",
                            inspection.floorConfidence == null ? "unknown" : inspection.floorConfidence,
                            formatNullable(inspection.floorScore), formatNullable(inspection.floorMargin))
                            : "no — manual floor";
                    String validation = inspection.validationErrorM == null ? "not supplied"
                            : String.format(Locale.US, "(%.2f, %.2f), error %.2f m",
                            inspection.validationX, inspection.validationY, inspection.validationErrorM);
                    ProcessingTimes timing = inspection.result.processingTimes;
                    summary.setText(String.format(Locale.US,
                            "Date          %s\nBuilding      %s\nFloor         %s\nFloor inferred %s\nEstimator     %s, M=%d\nObserved APs  %d\nMapped APs    %d\nNovel APs     %d\nEstimate      x=%.2f, y=%.2f\nSQS           %s\nCσ / FII      %s / %s\nWarnings      %s\nCalibration   %s\nValidation    %s\n\nON-DEVICE TIMES\nScan acquisition %s ms\nFloor inference  %s ms\nRadio-map load   %s ms\nFingerprint prep %s ms\nCandidate search %s ms\n2D estimation    %s ms\nIndicators       %s ms\nDiagnosis total  %s ms\nPost-scan total  %s ms\nPersistence      %s ms",
                            DateFormat.getDateTimeInstance().format(new Date(inspection.createdAt)),
                            inspection.buildingName, inspection.floorName, inferred, inspection.estimator,
                            floorData.diagnosticM, inspection.result.observedApCount,
                            inspection.result.mappedApCount, inspection.result.novelApCount,
                            inspection.result.estimateX, inspection.result.estimateY,
                            formatValue(inspection.result.sqs), formatValue(inspection.result.cSigma),
                            formatValue(inspection.result.fii),
                            inspection.result.warningCount < 0 ? "N/A" : inspection.result.warningCount + "/18",
                            floorData.calibrationDescription(), validation,
                            formatTime(timing.scanAcquisitionMs), formatTime(timing.floorInferenceMs),
                            formatTime(timing.radioMapLoadMs), formatTime(timing.fingerprintPreparationMs),
                            formatTime(timing.candidateRetrievalMs), formatTime(timing.positionEstimationMs),
                            formatTime(timing.indicatorComputationMs), formatTime(timing.diagnosisTotalMs),
                            formatTime(timing.postScanProcessingMs), formatTime(timing.persistenceMs)));
                    mapView.setFloorData(floorData);
                    mapView.setResult(inspection.result);
                    if (inspection.validationX != null && inspection.validationY != null) {
                        mapView.setValidationPoint(inspection.validationX, inspection.validationY);
                    }
                    indicatorView.setIndicators(inspection.result.indicators);
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    Toast.makeText(this, "Cannot open inspection: " + error.getMessage(), Toast.LENGTH_LONG).show();
                    finish();
                });
            }
        });
    }

    private static int parseK(String estimator) {
        if (estimator == null) return 3;
        int index = estimator.lastIndexOf('k');
        if (index < 0 || index + 1 >= estimator.length()) return 3;
        try { return Integer.parseInt(estimator.substring(index + 1)); }
        catch (NumberFormatException ignored) { return 3; }
    }

    private static String formatValue(double value) {
        return Double.isFinite(value) ? String.format(Locale.US, "%.3f", value) : "N/A";
    }

    private static String formatNullable(Double value) {
        return value == null ? "N/A" : String.format(Locale.US, "%.3f", value);
    }

    private static String formatTime(double value) {
        return Double.isFinite(value) ? String.format(Locale.US, "%.2f", value) : "N/A";
    }

    @Override protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
