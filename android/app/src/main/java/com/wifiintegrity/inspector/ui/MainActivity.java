package com.wifiintegrity.inspector.ui;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.content.pm.PackageManager;
import android.location.LocationManager;
import android.net.Uri;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.Spinner;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import com.wifiintegrity.inspector.R;
import com.wifiintegrity.inspector.diagnostics.DiagnosticEngine;
import com.wifiintegrity.inspector.diagnostics.FloorInferenceEngine;
import com.wifiintegrity.inspector.model.Building;
import com.wifiintegrity.inspector.model.Candidate;
import com.wifiintegrity.inspector.model.DiagnosticResult;
import com.wifiintegrity.inspector.model.FloorData;
import com.wifiintegrity.inspector.model.FloorInfo;
import com.wifiintegrity.inspector.model.FloorInferenceProfile;
import com.wifiintegrity.inspector.model.FloorInferenceResult;
import com.wifiintegrity.inspector.model.FloorInferenceScore;
import com.wifiintegrity.inspector.model.ScanObservation;
import com.wifiintegrity.inspector.model.ProcessingTimes;
import com.wifiintegrity.inspector.repository.RadioMapRepository;
import com.wifiintegrity.inspector.scanner.WifiScanner;
import com.wifiintegrity.inspector.util.InspectionExporter;

import java.io.OutputStream;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int REQUEST_SCAN_PERMISSIONS = 2001;
    private static final int REQUEST_EXPORT_RESULTS = 2002;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final DiagnosticEngine engine = new DiagnosticEngine();
    private final FloorInferenceEngine floorInferenceEngine = new FloorInferenceEngine();

    private RadioMapRepository repository;
    private WifiScanner scanner;
    private Spinner buildingSpinner;
    private Spinner floorSpinner;
    private Spinner kSpinner;
    private CheckBox inferFloorCheck;
    private CheckBox floorPlanCheck;
    private CheckBox showRpsCheck;
    private CheckBox showCandidatesCheck;
    private CheckBox showCentroidCheck;
    private CheckBox showEstimateCheck;
    private CheckBox validationModeCheck;
    private Button scanButton;
    private Button exportButton;
    private TextView statusText;
    private TextView reliabilityBadgeText;
    private TextView summarySubtitleText;
    private TextView floorValueText;
    private TextView floorDetailText;
    private TextView positionValueText;
    private TextView positionDetailText;
    private TextView sqsValueText;
    private TextView warningValueText;
    private TextView apValueText;
    private TextView processingValueText;
    private TextView timingBreakdownText;
    private TextView recordValueText;
    private TextView recommendedActionText;
    private TextView calibrationValueText;
    private ProgressBar sqsProgress;
    private ProgressBar warningProgress;
    private ProgressBar apCoverageProgress;
    private TextView conditionStatusText;
    private TextView mapStatusText;
    private TextView validationText;
    private TextView diagnosticSummaryText;
    private TextView diagnosticBadgeText;
    private TextView diagnosticSqsText;
    private TextView diagnosticWarningsText;
    private TextView diagnosticCsigmaText;
    private TextView diagnosticFiiText;
    private RadioMapView radioMapView;
    private RadioMapView liveLocalMapView;
    private TextView localMapStatusText;
    private View localMapPanel;
    private IndicatorDiagnosticsView indicatorDiagnosticsView;
    private View pageLive;
    private View pageMap;
    private View pageDiagnostics;

    private List<Building> buildings = new ArrayList<>();
    private List<FloorInfo> floors = new ArrayList<>();
    private List<FloorInferenceProfile> inferenceProfiles = new ArrayList<>();
    private FloorData activeFloorData;
    private DiagnosticResult lastResult;
    private FloorInferenceResult lastInference;
    private long lastHistoryId = -1L;
    private Double validationX;
    private Double validationY;
    private Double validationErrorM;
    private boolean suppressFloorSelection;
    private int floorLoadToken;
    private long scanRequestedNs;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        repository = new RadioMapRepository(this);
        scanner = new WifiScanner(this);
        bindViews();
        configureKSpinner();
        configureListeners();
        showPage(pageLive);
        loadBuildings();
    }

    private void bindViews() {
        buildingSpinner = findViewById(R.id.spinnerBuilding);
        floorSpinner = findViewById(R.id.spinnerFloor);
        kSpinner = findViewById(R.id.spinnerK);
        inferFloorCheck = findViewById(R.id.checkInferFloor);
        floorPlanCheck = findViewById(R.id.checkFloorPlan);
        showRpsCheck = findViewById(R.id.checkShowRps);
        showCandidatesCheck = findViewById(R.id.checkShowCandidates);
        showCentroidCheck = findViewById(R.id.checkShowCentroid);
        showEstimateCheck = findViewById(R.id.checkShowEstimate);
        validationModeCheck = findViewById(R.id.checkValidationMode);
        scanButton = findViewById(R.id.buttonScan);
        exportButton = findViewById(R.id.buttonExportResults);
        statusText = findViewById(R.id.textStatus);
        reliabilityBadgeText = findViewById(R.id.textReliabilityBadge);
        summarySubtitleText = findViewById(R.id.textSummarySubtitle);
        floorValueText = findViewById(R.id.textFloorValue);
        floorDetailText = findViewById(R.id.textFloorDetail);
        positionValueText = findViewById(R.id.textPositionValue);
        positionDetailText = findViewById(R.id.textPositionDetail);
        sqsValueText = findViewById(R.id.textSqsValue);
        warningValueText = findViewById(R.id.textWarningValue);
        apValueText = findViewById(R.id.textApValue);
        processingValueText = findViewById(R.id.textProcessingValue);
        timingBreakdownText = findViewById(R.id.textTimingBreakdown);
        recordValueText = findViewById(R.id.textRecordValue);
        recommendedActionText = findViewById(R.id.textRecommendedAction);
        calibrationValueText = findViewById(R.id.textCalibrationValue);
        sqsProgress = findViewById(R.id.progressSqs);
        warningProgress = findViewById(R.id.progressWarnings);
        apCoverageProgress = findViewById(R.id.progressApCoverage);
        conditionStatusText = findViewById(R.id.textConditionStatus);
        mapStatusText = findViewById(R.id.textMapStatus);
        validationText = findViewById(R.id.textValidation);
        diagnosticSummaryText = findViewById(R.id.textDiagnosticSummary);
        diagnosticBadgeText = findViewById(R.id.textDiagnosticBadge);
        diagnosticSqsText = findViewById(R.id.textDiagnosticSqs);
        diagnosticWarningsText = findViewById(R.id.textDiagnosticWarnings);
        diagnosticCsigmaText = findViewById(R.id.textDiagnosticCsigma);
        diagnosticFiiText = findViewById(R.id.textDiagnosticFii);
        radioMapView = findViewById(R.id.radioMapView);
        liveLocalMapView = findViewById(R.id.liveLocalMapView);
        localMapStatusText = findViewById(R.id.textLocalMapStatus);
        localMapPanel = findViewById(R.id.localMapPanel);
        indicatorDiagnosticsView = findViewById(R.id.indicatorDiagnosticsView);
        pageLive = findViewById(R.id.pageLive);
        pageMap = findViewById(R.id.pageMap);
        pageDiagnostics = findViewById(R.id.pageDiagnostics);
    }

    private void configureKSpinner() {
        String[] values = {"WKNN k = 1", "WKNN k = 3", "WKNN k = 5", "WKNN k = 10"};
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, values);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        kSpinner.setAdapter(adapter);
        kSpinner.setSelection(3);
    }

    private void configureListeners() {
        buildingSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (position >= 0 && position < buildings.size()) loadFloors(buildings.get(position));
            }
            @Override public void onNothingSelected(AdapterView<?> parent) { }
        });

        floorSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (!suppressFloorSelection && position >= 0 && position < floors.size()) {
                    loadFloorPreview(floors.get(position));
                }
            }
            @Override public void onNothingSelected(AdapterView<?> parent) { }
        });

        kSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (!floors.isEmpty() && floorSpinner.getSelectedItemPosition() >= 0) {
                    loadFloorPreview(floors.get(floorSpinner.getSelectedItemPosition()));
                }
            }
            @Override public void onNothingSelected(AdapterView<?> parent) { }
        });

        inferFloorCheck.setOnCheckedChangeListener((button, checked) -> {
            scanButton.setText(checked ? "SCAN, INFER FLOOR, AND DIAGNOSE" : "SCAN SELECTED FLOOR AND DIAGNOSE");
            floorSpinner.setEnabled(!checked);
            conditionStatusText.setText(checked
                    ? "Floor inference is active. The 2D estimate will be calculated only after the floor is selected from the scan."
                    : "Manual floor mode is active. The selected floor will be used directly.");
        });
        floorSpinner.setEnabled(false);

        floorPlanCheck.setOnCheckedChangeListener((button, checked) -> {
            radioMapView.setUseFloorPlan(checked);
            liveLocalMapView.setUseFloorPlan(checked);
        });
        showRpsCheck.setOnCheckedChangeListener((button, checked) -> radioMapView.setShowRps(checked));
        showCandidatesCheck.setOnCheckedChangeListener((button, checked) -> radioMapView.setShowCandidates(checked));
        showCentroidCheck.setOnCheckedChangeListener((button, checked) -> radioMapView.setShowCentroid(checked));
        showEstimateCheck.setOnCheckedChangeListener((button, checked) -> radioMapView.setShowEstimate(checked));
        validationModeCheck.setOnCheckedChangeListener((button, checked) -> {
            radioMapView.setValidationMode(checked);
            validationText.setText(checked
                    ? "Validation mode is active. Tap the known physical position on the map."
                    : "Validation mode is off. Tap a diagnostic candidate to inspect it; drag or pinch to navigate.");
        });

        radioMapView.setOnValidationPointListener(this::handleValidationPoint);
        radioMapView.setOnCandidateTapListener(this::showCandidateDetails);

        liveLocalMapView.setLocalViewportAroundEstimate(15.0);
        liveLocalMapView.setInteractionEnabled(false);
        liveLocalMapView.setShowRps(true);
        liveLocalMapView.setShowCandidates(true);
        liveLocalMapView.setShowCentroid(true);
        liveLocalMapView.setShowEstimate(true);

        scanButton.setOnClickListener(view -> beginScan());
        exportButton.setOnClickListener(view -> requestResultsExport());
        findViewById(R.id.buttonResetMap).setOnClickListener(view -> radioMapView.resetView());
        findViewById(R.id.buttonClearValidation).setOnClickListener(view -> clearValidation());
        findViewById(R.id.buttonOpenMap).setOnClickListener(view -> showPage(pageMap));
        findViewById(R.id.buttonOpenDiagnostics).setOnClickListener(view -> showPage(pageDiagnostics));

        findViewById(R.id.navLive).setOnClickListener(view -> showPage(pageLive));
        findViewById(R.id.navMap).setOnClickListener(view -> showPage(pageMap));
        findViewById(R.id.navDiagnostics).setOnClickListener(view -> showPage(pageDiagnostics));
        findViewById(R.id.navHistory).setOnClickListener(view -> startActivity(new Intent(this, HistoryActivity.class)));
        findViewById(R.id.navMaps).setOnClickListener(view -> startActivity(new Intent(this, RadioMapManagerActivity.class)));
    }

    private void showPage(View page) {
        pageLive.setVisibility(page == pageLive ? View.VISIBLE : View.GONE);
        pageMap.setVisibility(page == pageMap ? View.VISIBLE : View.GONE);
        pageDiagnostics.setVisibility(page == pageDiagnostics ? View.VISIBLE : View.GONE);
        if (page == pageDiagnostics) {
            indicatorDiagnosticsView.requestLayout();
            indicatorDiagnosticsView.invalidate();
        }
    }

    private void loadBuildings() {
        scanButton.setEnabled(false);
        statusText.setText("Loading installed radio maps…");
        executor.execute(() -> {
            try {
                List<Building> loaded = repository.listBuildings();
                mainHandler.post(() -> {
                    buildings = loaded;
                    ArrayAdapter<Building> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, buildings);
                    adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                    buildingSpinner.setAdapter(adapter);
                    statusText.setText(loaded.isEmpty() ? "No radio maps are installed." : "Select a building and request a scan.");
                });
            } catch (Exception error) {
                showError("Cannot load the radio-map database: " + error.getMessage());
            }
        });
    }

    private void loadFloors(Building building) {
        final long buildingId = building.id;
        scanButton.setEnabled(false);
        inferenceProfiles = new ArrayList<>();
        conditionStatusText.setText("Preparing floor radio maps for inference…");
        executor.execute(() -> {
            try {
                List<FloorInfo> loadedFloors = repository.listFloors(buildingId);
                List<FloorInferenceProfile> profiles = repository.loadFloorInferenceProfiles(building, loadedFloors);
                mainHandler.post(() -> {
                    Building selected = selectedBuilding();
                    if (selected == null || selected.id != buildingId) return;
                    floors = loadedFloors;
                    inferenceProfiles = profiles;
                    ArrayAdapter<FloorInfo> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, floors);
                    adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                    suppressFloorSelection = true;
                    floorSpinner.setAdapter(adapter);
                    int defaultIndex = defaultFloorIndex(building, floors);
                    if (defaultIndex >= 0) floorSpinner.setSelection(defaultIndex);
                    suppressFloorSelection = false;
                    conditionStatusText.setText(String.format(Locale.US,
                            "Ready to infer among %d floors in %s. A matching selected-floor/WKNN calibration is required; diagnostic M = %d.",
                            profiles.size(), building.name, DiagnosticEngine.DIAGNOSTIC_M));
                    if (defaultIndex >= 0) loadFloorPreview(floors.get(defaultIndex));
                    else scanButton.setEnabled(!profiles.isEmpty());
                });
            } catch (Exception error) {
                showError("Cannot prepare floor inference: " + error.getMessage());
            }
        });
    }

    private int defaultFloorIndex(Building building, List<FloorInfo> loaded) {
        return loaded.isEmpty() ? -1 : 0;
    }

    private void loadFloorPreview(FloorInfo floor) {
        Building building = selectedBuilding();
        if (building == null) return;
        int k = selectedK();
        int token = ++floorLoadToken;
        scanButton.setEnabled(false);
        statusText.setText("Loading " + building.name + " — " + floor.name + " with WKNN k=" + k + " calibration…");
        executor.execute(() -> {
            try {
                FloorData data = repository.loadFloorData(building, floor, k);
                mainHandler.post(() -> {
                    if (token != floorLoadToken) return;
                    activeFloorData = data;
                    radioMapView.setFloorData(data);
                    liveLocalMapView.setFloorData(data);
                    liveLocalMapView.setLocalViewportAroundEstimate(15.0);
                    localMapPanel.setVisibility(View.GONE);
                    floorPlanCheck.setEnabled(floor.hasFloorPlan());
                    floorPlanCheck.setChecked(floor.hasFloorPlan());
                    radioMapView.setUseFloorPlan(floor.hasFloorPlan());
                    conditionStatusText.setText(data.calibrationDescription() + ". Floor inference profiles: " + inferenceProfiles.size() + ".");
                    statusText.setText(String.format(Locale.US, "%s — %s loaded: %d RPs, %d templates, %d mapped BSSIDs.",
                            building.name, floor.name, data.referencePoints.size(), data.templates.size(), data.bssidToAp.size()));
                    scanButton.setEnabled(!data.templates.isEmpty() && (!inferFloorCheck.isChecked() || !inferenceProfiles.isEmpty()));
                });
            } catch (Exception error) {
                showError("Cannot load the selected floor: " + error.getMessage());
            }
        });
    }

    private void beginScan() {
        if (selectedBuilding() == null) {
            Toast.makeText(this, "Select a building first.", Toast.LENGTH_SHORT).show();
            return;
        }
        if (inferFloorCheck.isChecked() && inferenceProfiles.isEmpty()) {
            Toast.makeText(this, "Floor-inference profiles are still loading.", Toast.LENGTH_SHORT).show();
            return;
        }
        if (!hasScanPermissions()) {
            requestScanPermissions();
            return;
        }
        LocationManager locationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
        if (locationManager != null && !isLocationEnabled(locationManager)) {
            Toast.makeText(this, "Enable device location services before requesting the Wi-Fi scan.", Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS));
            return;
        }
        scanButton.setEnabled(false);
        statusText.setText("Requesting a Wi-Fi scan…");
        scanRequestedNs = System.nanoTime();
        scanner.start(new WifiScanner.Callback() {
            @Override public void onScanReady(List<ScanObservation> observations, boolean fresh, String message) {
                double acquisitionMs = scanRequestedNs == 0L ? Double.NaN
                        : (System.nanoTime() - scanRequestedNs) / 1_000_000.0;
                diagnose(observations, message, acquisitionMs);
            }
            @Override public void onScanError(String message) {
                scanButton.setEnabled(true);
                showError(message);
            }
        });
    }

    private void diagnose(List<ScanObservation> observations, String scanMessage, double scanAcquisitionMs) {
        Building building = selectedBuilding();
        List<FloorInfo> floorSnapshot = new ArrayList<>(floors);
        List<FloorInferenceProfile> profileSnapshot = new ArrayList<>(inferenceProfiles);
        boolean inferFloor = inferFloorCheck.isChecked();
        int selectedFloorPosition = floorSpinner.getSelectedItemPosition();
        FloorInfo manualFloor = selectedFloorPosition >= 0 && selectedFloorPosition < floorSnapshot.size()
                ? floorSnapshot.get(selectedFloorPosition) : null;
        int k = selectedK();

        statusText.setText(scanMessage + (inferFloor
                ? " Inferring the floor before the 2D estimate…"
                : " Loading the selected floor and calculating the 2D estimate…"));

        executor.execute(() -> {
            try {
                long pipelineStarted = System.nanoTime();

                long floorInferenceStarted = System.nanoTime();
                FloorInferenceResult inference = inferFloor
                        ? floorInferenceEngine.infer(observations, profileSnapshot)
                        : null;
                double floorInferenceMs = inferFloor
                        ? (System.nanoTime() - floorInferenceStarted) / 1_000_000.0 : 0.0;

                FloorInfo selectedFloor = inference != null ? inference.floor : manualFloor;
                if (selectedFloor == null) throw new IllegalStateException("No floor is selected.");

                long radioMapLoadStarted = System.nanoTime();
                FloorData data = repository.loadFloorData(building, selectedFloor, k);
                double radioMapLoadMs = (System.nanoTime() - radioMapLoadStarted) / 1_000_000.0;

                DiagnosticResult engineResult = engine.analyze(data, observations, k);
                double postScanProcessingMs = (System.nanoTime() - pipelineStarted) / 1_000_000.0;
                ProcessingTimes pipelineTimes = engineResult.processingTimes.withPipeline(
                        scanAcquisitionMs, floorInferenceMs, radioMapLoadMs,
                        postScanProcessingMs, Double.NaN);
                DiagnosticResult resultBeforeSave = engineResult.withProcessingTimes(pipelineTimes);

                long persistenceStarted = System.nanoTime();
                long historyId = repository.saveInspection(data, observations, resultBeforeSave, inference);
                double persistenceMs = (System.nanoTime() - persistenceStarted) / 1_000_000.0;

                DiagnosticResult finalResult = resultBeforeSave.withProcessingTimes(
                        pipelineTimes.withPipeline(scanAcquisitionMs, floorInferenceMs,
                                radioMapLoadMs, postScanProcessingMs, persistenceMs));
                repository.updateInspectionResult(historyId, finalResult);
                mainHandler.post(() -> displayResult(data, finalResult, inference, historyId, scanMessage));
            } catch (Exception error) {
                showError("Diagnosis failed: " + error.getMessage());
            }
        });
    }

    private void displayResult(FloorData data, DiagnosticResult result,
                               FloorInferenceResult inference, long historyId,
                               String scanMessage) {
        activeFloorData = data;
        lastResult = result;
        lastInference = inference;
        lastHistoryId = historyId;
        validationX = validationY = validationErrorM = null;
        radioMapView.setFloorData(data);
        radioMapView.setResult(result);
        radioMapView.clearValidationPoint();

        liveLocalMapView.setFloorData(data);
        liveLocalMapView.setLocalViewportAroundEstimate(15.0);
        liveLocalMapView.setResult(result);
        liveLocalMapView.setUseFloorPlan(data.floor.hasFloorPlan());
        localMapStatusText.setText(String.format(Locale.US,
                "%s — %s • centered at (%.2f, %.2f) • 30 m × 30 m local window (±15 m)",
                data.building.name, data.floor.name, result.estimateX, result.estimateY));
        localMapPanel.setVisibility(View.VISIBLE);

        indicatorDiagnosticsView.setDiagnostics(result.indicators);
        floorPlanCheck.setEnabled(data.floor.hasFloorPlan());
        floorPlanCheck.setChecked(data.floor.hasFloorPlan());
        selectFloorInSpinner(data.floor.id);
        refreshSummary();
        refreshMapStatus();
        refreshDiagnosticSummary(data, result);
        statusText.setText(scanMessage + " Inspection saved at "
                + DateFormat.getTimeInstance(DateFormat.MEDIUM).format(new Date()) + ".");
        scanButton.setEnabled(true);
    }

    private void refreshSummary() {
        if (activeFloorData == null || lastResult == null) return;

        final String status = describeSupport(lastResult);
        final int statusColor = supportColor(lastResult);
        reliabilityBadgeText.setText(status.toUpperCase(Locale.US));
        reliabilityBadgeText.getBackground().mutate().setTint(statusColor);

        String floorSource;
        if (lastInference == null) {
            floorSource = "Manual floor selection";
        } else {
            floorSource = String.format(Locale.US, "%s confidence • score %.3f • margin %.3f",
                    capitalize(lastInference.confidence), lastInference.score, lastInference.margin);
        }
        summarySubtitleText.setText(activeFloorData.building.name + " • " + activeFloorData.floor.name
                + " • WKNN k=" + lastResult.wknnK + " • diagnostic M=" + activeFloorData.diagnosticM);
        floorValueText.setText(activeFloorData.floor.name);
        floorDetailText.setText(floorSource);
        positionValueText.setText(String.format(Locale.US, "x %.2f\ny %.2f", lastResult.estimateX, lastResult.estimateY));
        positionDetailText.setText(lastResult.candidates.size() + " diagnostic candidates");

        sqsValueText.setText("SQS " + formatMetric(lastResult.sqs));
        int sqsPercent = Double.isFinite(lastResult.sqs)
                ? (int) Math.round(Math.max(0.0, Math.min(1.0, lastResult.sqs)) * 100.0) : 0;
        sqsProgress.setProgress(sqsPercent);
        sqsProgress.setProgressTintList(ColorStateList.valueOf(lastResult.sqs >= 0.60
                ? Color.rgb(46, 125, 50) : lastResult.sqs >= 0.25
                ? Color.rgb(214, 128, 29) : Color.rgb(184, 58, 58)));

        warningValueText.setText(lastResult.warningCount < 0 ? "N/A" : lastResult.warningCount + " / 18");
        warningProgress.setProgress(Math.max(0, lastResult.warningCount));
        warningProgress.setProgressTintList(ColorStateList.valueOf(lastResult.warningCount < 0
                ? Color.GRAY : lastResult.warningCount >= 10
                ? Color.rgb(184, 58, 58) : lastResult.warningCount >= 4
                ? Color.rgb(214, 128, 29) : Color.rgb(46, 125, 50)));

        int coveragePercent = lastResult.observedApCount <= 0 ? 0
                : (int) Math.round(100.0 * lastResult.mappedApCount / lastResult.observedApCount);
        apValueText.setText(String.format(Locale.US, "%d/%d mapped • %d novel",
                lastResult.mappedApCount, lastResult.observedApCount, lastResult.novelApCount));
        apCoverageProgress.setProgress(Math.max(0, Math.min(100, coveragePercent)));
        apCoverageProgress.setProgressTintList(ColorStateList.valueOf(Color.rgb(63, 134, 179)));

        ProcessingTimes timing = lastResult.processingTimes;
        processingValueText.setText(String.format(Locale.US, "%.2f ms post-scan",
                finiteOrFallback(timing.postScanProcessingMs, lastResult.processingMs)));
        timingBreakdownText.setText(String.format(Locale.US,
                "Scan acquisition %s ms • floor inference %s ms • radio-map load %s ms\n" +
                        "fingerprint %s ms • candidates %s ms • position %s ms • indicators %s ms • save %s ms",
                formatTime(timing.scanAcquisitionMs), formatTime(timing.floorInferenceMs),
                formatTime(timing.radioMapLoadMs), formatTime(timing.fingerprintPreparationMs),
                formatTime(timing.candidateRetrievalMs), formatTime(timing.positionEstimationMs),
                formatTime(timing.indicatorComputationMs), formatTime(timing.persistenceMs)));
        recordValueText.setText("Saved inspection #" + lastHistoryId);
        recommendedActionText.setText(recommendedAction(lastResult));

        String validation = validationErrorM == null ? "Validation position not supplied"
                : String.format(Locale.US, "Validation error %.2f m at (%.2f, %.2f)",
                validationErrorM, validationX, validationY);
        calibrationValueText.setText("Calibration: " + activeFloorData.calibrationDescription()
                + " • Cσ " + formatMetric(lastResult.cSigma)
                + " • FII " + formatMetric(lastResult.fii) + " • " + validation);
    }

    private void refreshMapStatus() {
        if (activeFloorData == null || lastResult == null) {
            mapStatusText.setText("No scan result is available.");
            return;
        }
        String inference = lastInference == null ? "Manual floor: " + activeFloorData.floor.name
                : FloorInferenceEngine.summarize(lastInference) + "\nTop floors: " + topFloorSummary(lastInference);
        mapStatusText.setText(inference + String.format(Locale.US,
                "\nWKNN estimate: (%.2f, %.2f); diagnostic candidates: %d.",
                lastResult.estimateX, lastResult.estimateY, lastResult.candidates.size()));
    }

    private void refreshDiagnosticSummary(FloorData data, DiagnosticResult result) {
        String warnings = result.warningCount < 0 ? "unavailable" : result.warningCount + "/18";
        String status = describeSupport(result);
        int statusColor = supportColor(result);
        diagnosticBadgeText.setText(status.toUpperCase(Locale.US));
        diagnosticBadgeText.getBackground().mutate().setTint(statusColor);
        diagnosticSummaryText.setText("Condition: " + data.building.name + " — " + data.floor.name
                + " — " + data.calibrationEstimator + " — M=" + data.diagnosticM
                + "\nCalibration: " + (data.calibrationAvailable ? data.floor.calibrationMode : "not available")
                + "\nEvery row reports the raw value, adverse percentile, and binary warning status.");
        diagnosticSqsText.setText("SQS\n" + formatMetric(result.sqs));
        diagnosticWarningsText.setText("WARNINGS\n" + warnings);
        diagnosticCsigmaText.setText("Cσ\n" + formatMetric(result.cSigma));
        diagnosticFiiText.setText("FII\n" + formatMetric(result.fii));
        indicatorDiagnosticsView.setDiagnostics(result.indicators);
    }

    private void requestResultsExport() {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/zip");
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date());
        intent.putExtra(Intent.EXTRA_TITLE, "wifi_integrity_results_" + stamp + ".zip");
        startActivityForResult(intent, REQUEST_EXPORT_RESULTS);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_EXPORT_RESULTS || resultCode != RESULT_OK || data == null) return;
        Uri uri = data.getData();
        if (uri == null) return;
        exportButton.setEnabled(false);
        statusText.setText("Writing the complete scan, indicator, floor-inference, and timing export…");
        executor.execute(() -> {
            try (OutputStream output = getContentResolver().openOutputStream(uri, "w")) {
                if (output == null) throw new IllegalStateException("The selected export file cannot be opened.");
                InspectionExporter.export(repository.writableDatabase(), output);
                mainHandler.post(() -> {
                    exportButton.setEnabled(true);
                    statusText.setText("Results exported. The ZIP contains summary, indicator, processing-time, floor-ranking, and JSONL files.");
                    Toast.makeText(this, "Results export completed.", Toast.LENGTH_LONG).show();
                });
            } catch (Exception error) {
                mainHandler.post(() -> {
                    exportButton.setEnabled(true);
                    showError("Results export failed: " + error.getMessage());
                });
            }
        });
    }

    private static double finiteOrFallback(double value, double fallback) {
        return Double.isFinite(value) ? value : fallback;
    }

    private static String formatTime(double value) {
        return Double.isFinite(value) ? String.format(Locale.US, "%.2f", value) : "—";
    }

    private void handleValidationPoint(double x, double y) {
        if (lastResult == null || lastHistoryId < 0) {
            validationText.setText("Run a scan before supplying a validation position.");
            return;
        }
        double error = Math.hypot(x - lastResult.estimateX, y - lastResult.estimateY);
        validationX = x;
        validationY = y;
        validationErrorM = error;
        validationText.setText(String.format(Locale.US,
                "Known position: (%.2f, %.2f) • estimated position: (%.2f, %.2f) • horizontal error: %.2f m%s",
                x, y, lastResult.estimateX, lastResult.estimateY, error,
                error >= 7.0 ? " • exceeds 7 m" : " • below 7 m"));
        refreshSummary();
        long historyId = lastHistoryId;
        executor.execute(() -> repository.saveValidation(historyId, x, y, error));
    }

    private void clearValidation() {
        validationX = validationY = validationErrorM = null;
        radioMapView.clearValidationPoint();
        validationText.setText("Validation cleared. Enable Validation tap and select a known position when required.");
        refreshSummary();
    }

    private void showCandidateDetails(Candidate candidate) {
        validationText.setText(String.format(Locale.US,
                "Candidate %d • position (%.2f, %.2f) • normalized RSS distance %.3f • template ID %d",
                candidate.rank, candidate.x, candidate.y, candidate.distance, candidate.templateId));
    }

    private void selectFloorInSpinner(long floorId) {
        for (int i = 0; i < floors.size(); i++) {
            if (floors.get(i).id == floorId) {
                suppressFloorSelection = true;
                floorSpinner.setSelection(i);
                suppressFloorSelection = false;
                return;
            }
        }
    }

    private Building selectedBuilding() {
        int position = buildingSpinner == null ? -1 : buildingSpinner.getSelectedItemPosition();
        return position >= 0 && position < buildings.size() ? buildings.get(position) : null;
    }

    private static String topFloorSummary(FloorInferenceResult result) {
        StringBuilder text = new StringBuilder();
        int count = Math.min(3, result.ranking.size());
        for (int i = 0; i < count; i++) {
            FloorInferenceScore score = result.ranking.get(i);
            if (i > 0) text.append("; ");
            text.append(score.floor.name).append(' ')
                    .append(String.format(Locale.US, "%.3f", score.score))
                    .append(" (").append(score.mappedApCount).append(" APs)");
        }
        return text.toString();
    }

    private static int supportColor(DiagnosticResult result) {
        if (result.warningCount < 0 || !Double.isFinite(result.sqs)) return Color.GRAY;
        if (result.warningCount <= 3 && result.sqs >= 0.60) return Color.rgb(46, 125, 50);
        if (result.warningCount >= 10 || result.sqs < 0.25) return Color.rgb(184, 58, 58);
        return Color.rgb(214, 128, 29);
    }

    private static String recommendedAction(DiagnosticResult result) {
        if (result.warningCount < 0 || !Double.isFinite(result.sqs)) {
            return "Use the raw diagnostics only; a matching calibration is unavailable.";
        }
        if (result.warningCount <= 3 && result.sqs >= 0.60) {
            return "Strong scan support: the estimated coordinate may continue to be used normally.";
        }
        if (result.warningCount >= 10 || result.sqs < 0.25) {
            return "Broad diagnostic concern: request another scan and consider down-weighting, fallback, or withholding the fix.";
        }
        return "Use with caution: retain the coordinate with increased uncertainty or reduced temporal-filter weight.";
    }

    private static String capitalize(String value) {
        if (value == null || value.isEmpty()) return "Unknown";
        return Character.toUpperCase(value.charAt(0)) + value.substring(1);
    }

    private static String describeSupport(DiagnosticResult result) {
        if (result.warningCount < 0 || !Double.isFinite(result.sqs)) return "raw diagnostics only";
        if (result.warningCount <= 3 && result.sqs >= 0.60) return "reliable fix";
        if (result.warningCount >= 10 || result.sqs < 0.25) return "broad diagnostic concern";
        return "use the fix with caution";
    }

    private static String formatMetric(double value) {
        return Double.isFinite(value) ? String.format(Locale.US, "%.3f", value) : "N/A";
    }

    private int selectedK() {
        int position = kSpinner.getSelectedItemPosition();
        if (position == 0) return 1;
        if (position == 1) return 3;
        if (position == 2) return 5;
        return 10;
    }

    private static boolean isLocationEnabled(LocationManager manager) {
        if (Build.VERSION.SDK_INT >= 28) return manager.isLocationEnabled();
        try {
            return manager.isProviderEnabled(LocationManager.GPS_PROVIDER)
                    || manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER);
        } catch (Exception ignored) {
            return false;
        }
    }

    private boolean hasScanPermissions() {
        boolean fine = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        boolean nearby = Build.VERSION.SDK_INT < 33
                || checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) == PackageManager.PERMISSION_GRANTED;
        return fine && nearby;
    }

    private void requestScanPermissions() {
        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.NEARBY_WIFI_DEVICES}, REQUEST_SCAN_PERMISSIONS);
        } else {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, REQUEST_SCAN_PERMISSIONS);
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQUEST_SCAN_PERMISSIONS) return;
        if (hasScanPermissions()) beginScan();
        else showError("Wi-Fi scan and location permissions are required for indoor positioning.");
    }

    private void showError(String message) {
        mainHandler.post(() -> {
            statusText.setText(message);
            scanButton.setEnabled(selectedBuilding() != null);
            Toast.makeText(this, message, Toast.LENGTH_LONG).show();
        });
    }

    @Override protected void onDestroy() {
        scanner.release();
        executor.shutdownNow();
        super.onDestroy();
    }
}
