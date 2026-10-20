package com.wifiintegrity.inspector.model;

/**
 * Processing-time breakdown for one live scan-level inspection.
 * Scan acquisition is reported separately because Android controls the radio scan cadence.
 */
public final class ProcessingTimes {
    public final double scanAcquisitionMs;
    public final double floorInferenceMs;
    public final double radioMapLoadMs;
    public final double fingerprintPreparationMs;
    public final double candidateRetrievalMs;
    public final double positionEstimationMs;
    public final double indicatorComputationMs;
    public final double diagnosisTotalMs;
    public final double postScanProcessingMs;
    public final double persistenceMs;

    public ProcessingTimes(double scanAcquisitionMs,
                           double floorInferenceMs,
                           double radioMapLoadMs,
                           double fingerprintPreparationMs,
                           double candidateRetrievalMs,
                           double positionEstimationMs,
                           double indicatorComputationMs,
                           double diagnosisTotalMs,
                           double postScanProcessingMs,
                           double persistenceMs) {
        this.scanAcquisitionMs = scanAcquisitionMs;
        this.floorInferenceMs = floorInferenceMs;
        this.radioMapLoadMs = radioMapLoadMs;
        this.fingerprintPreparationMs = fingerprintPreparationMs;
        this.candidateRetrievalMs = candidateRetrievalMs;
        this.positionEstimationMs = positionEstimationMs;
        this.indicatorComputationMs = indicatorComputationMs;
        this.diagnosisTotalMs = diagnosisTotalMs;
        this.postScanProcessingMs = postScanProcessingMs;
        this.persistenceMs = persistenceMs;
    }

    public static ProcessingTimes engineOnly(double fingerprintPreparationMs,
                                             double candidateRetrievalMs,
                                             double positionEstimationMs,
                                             double indicatorComputationMs,
                                             double diagnosisTotalMs) {
        return new ProcessingTimes(Double.NaN, Double.NaN, Double.NaN,
                fingerprintPreparationMs, candidateRetrievalMs,
                positionEstimationMs, indicatorComputationMs,
                diagnosisTotalMs, diagnosisTotalMs, Double.NaN);
    }

    public static ProcessingTimes unavailable(double diagnosisTotalMs) {
        return new ProcessingTimes(Double.NaN, Double.NaN, Double.NaN,
                Double.NaN, Double.NaN, Double.NaN, Double.NaN,
                diagnosisTotalMs, diagnosisTotalMs, Double.NaN);
    }

    public ProcessingTimes withPipeline(double scanAcquisitionMs,
                                        double floorInferenceMs,
                                        double radioMapLoadMs,
                                        double postScanProcessingMs,
                                        double persistenceMs) {
        return new ProcessingTimes(scanAcquisitionMs, floorInferenceMs, radioMapLoadMs,
                fingerprintPreparationMs, candidateRetrievalMs, positionEstimationMs,
                indicatorComputationMs, diagnosisTotalMs, postScanProcessingMs, persistenceMs);
    }
}
