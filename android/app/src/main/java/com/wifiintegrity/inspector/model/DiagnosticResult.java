package com.wifiintegrity.inspector.model;

import java.util.Collections;
import java.util.List;
import java.util.Map;

public final class DiagnosticResult {
    public final double estimateX;
    public final double estimateY;
    public final double centroidX;
    public final double centroidY;
    public final List<Candidate> candidates;
    public final List<IndicatorDiagnostic> indicators;
    public final Map<Integer, Double> mappedFingerprint;
    public final int observedApCount;
    public final int mappedApCount;
    public final int novelApCount;
    public final int warningCount;
    public final double sqs;
    public final double cSigma;
    public final double fii;
    public final double processingMs;
    public final ProcessingTimes processingTimes;
    public final String calibrationMode;
    public final int wknnK;

    public DiagnosticResult(double estimateX, double estimateY, double centroidX, double centroidY,
                            List<Candidate> candidates, List<IndicatorDiagnostic> indicators,
                            Map<Integer, Double> mappedFingerprint,
                            int observedApCount, int mappedApCount, int novelApCount,
                            int warningCount, double sqs, double cSigma, double fii,
                            double processingMs, ProcessingTimes processingTimes,
                            String calibrationMode, int wknnK) {
        this.estimateX = estimateX;
        this.estimateY = estimateY;
        this.centroidX = centroidX;
        this.centroidY = centroidY;
        this.candidates = Collections.unmodifiableList(candidates);
        this.indicators = Collections.unmodifiableList(indicators);
        this.mappedFingerprint = Collections.unmodifiableMap(mappedFingerprint);
        this.observedApCount = observedApCount;
        this.mappedApCount = mappedApCount;
        this.novelApCount = novelApCount;
        this.warningCount = warningCount;
        this.sqs = sqs;
        this.cSigma = cSigma;
        this.fii = fii;
        this.processingMs = processingMs;
        this.processingTimes = processingTimes == null
                ? ProcessingTimes.unavailable(processingMs) : processingTimes;
        this.calibrationMode = calibrationMode;
        this.wknnK = wknnK;
    }
    public DiagnosticResult withProcessingTimes(ProcessingTimes updatedTimes) {
        return new DiagnosticResult(estimateX, estimateY, centroidX, centroidY,
                candidates, indicators, mappedFingerprint, observedApCount, mappedApCount,
                novelApCount, warningCount, sqs, cSigma, fii, processingMs, updatedTimes,
                calibrationMode, wknnK);
    }

}
