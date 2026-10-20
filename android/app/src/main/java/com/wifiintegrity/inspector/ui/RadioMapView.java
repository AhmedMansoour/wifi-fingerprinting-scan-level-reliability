package com.wifiintegrity.inspector.ui;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;

import com.wifiintegrity.inspector.model.Candidate;
import com.wifiintegrity.inspector.model.DiagnosticResult;
import com.wifiintegrity.inspector.model.FloorData;

import java.util.Locale;

public final class RadioMapView extends View {
    public interface OnValidationPointListener {
        void onValidationPoint(double x, double y);
    }

    public interface OnCandidateTapListener {
        void onCandidateTapped(Candidate candidate);
    }

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final ScaleGestureDetector scaleDetector;
    private FloorData floorData;
    private DiagnosticResult result;
    private Bitmap floorBitmap;
    private boolean useFloorPlan = true;
    private boolean showRps = true;
    private boolean showCandidates = true;
    private boolean showCentroid = true;
    private boolean showEstimate = true;
    private boolean validationMode = false;
    private boolean localViewportEnabled = false;
    private boolean interactionEnabled = true;
    private double localHalfSpanMeters = 15.0;
    private Double validationX;
    private Double validationY;
    private float scale = 1f;
    private float translateX = 0f;
    private float translateY = 0f;
    private float lastX;
    private float lastY;
    private float downX;
    private float downY;
    private boolean moved;
    private double displayMinX;
    private double displayMinY;
    private double displayMaxX;
    private double displayMaxY;
    private OnValidationPointListener validationListener;
    private OnCandidateTapListener candidateTapListener;

    public RadioMapView(Context context) { this(context, null); }

    public RadioMapView(Context context, AttributeSet attrs) {
        super(context, attrs);
        scaleDetector = new ScaleGestureDetector(context, new ScaleListener());
        paint.setTypeface(android.graphics.Typeface.create("sans", android.graphics.Typeface.NORMAL));
        setFocusable(true);
    }

    public void setFloorData(FloorData value) {
        floorData = value;
        result = null;
        validationX = validationY = null;
        resetView();
        if (floorBitmap != null) floorBitmap.recycle();
        floorBitmap = null;
        if (value != null && value.floor.floorPlan != null) {
            Bitmap decoded = BitmapFactory.decodeByteArray(value.floor.floorPlan, 0, value.floor.floorPlan.length);
            floorBitmap = rotateFloorPlan(decoded, (float) value.floor.rotationAngle);
        }
        computeDisplayBounds();
        invalidate();
    }

    public void setResult(DiagnosticResult value) {
        result = value;
        if (localViewportEnabled) {
            computeDisplayBounds();
            resetView();
        } else {
            invalidate();
        }
    }

    /**
     * Uses a fixed square metric viewport centered on the current estimate.
     * A half span of 15 m produces a 30 m × 30 m local inspection window.
     */
    public void setLocalViewportAroundEstimate(double halfSpanMeters) {
        localViewportEnabled = true;
        localHalfSpanMeters = Math.max(1.0, halfSpanMeters);
        computeDisplayBounds();
        resetView();
    }

    public void setFullViewport() {
        localViewportEnabled = false;
        computeDisplayBounds();
        resetView();
    }

    public void setInteractionEnabled(boolean value) {
        interactionEnabled = value;
        setClickable(value);
        setFocusable(value);
    }

    public void setUseFloorPlan(boolean value) {
        useFloorPlan = value;
        computeDisplayBounds();
        resetView();
        invalidate();
    }

    public void setShowRps(boolean value) { showRps = value; invalidate(); }
    public void setShowCandidates(boolean value) { showCandidates = value; invalidate(); }
    public void setShowCentroid(boolean value) { showCentroid = value; invalidate(); }
    public void setShowEstimate(boolean value) { showEstimate = value; invalidate(); }
    public void setValidationMode(boolean value) { validationMode = value; }
    public boolean isValidationMode() { return validationMode; }

    public void setOnValidationPointListener(OnValidationPointListener listener) {
        validationListener = listener;
    }

    public void setOnCandidateTapListener(OnCandidateTapListener listener) {
        candidateTapListener = listener;
    }

    public void setValidationPoint(Double x, Double y) {
        validationX = x;
        validationY = y;
        invalidate();
    }

    public void clearValidationPoint() {
        validationX = validationY = null;
        invalidate();
    }

    public void resetView() {
        scale = 1f;
        translateX = 0f;
        translateY = 0f;
        invalidate();
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        canvas.drawColor(Color.WHITE);
        RectF plot = plotRect();
        if (floorData == null) {
            drawCenteredText(canvas, "Select a floor to load its radio map.");
            return;
        }

        canvas.save();
        canvas.translate(translateX, translateY);
        canvas.scale(scale, scale, plot.centerX(), plot.centerY());

        if (useFloorPlan && floorBitmap != null) {
            drawFloorPlan(canvas, plot);
        } else {
            drawGrid(canvas, plot);
        }

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(dp(1));
        paint.setColor(Color.rgb(80, 80, 80));
        canvas.drawRect(plot, paint);
        paint.setStyle(Paint.Style.FILL);

        canvas.save();
        canvas.clipRect(plot);
        if (showRps) {
            paint.setColor(Color.rgb(145, 145, 145));
            for (double[] rp : floorData.referencePoints) {
                float[] point = screenPoint(rp[0], rp[1], plot);
                canvas.drawCircle(point[0], point[1], dp(1.8f), paint);
            }
        }

        if (result != null) {
            float[] estimate = screenPoint(result.estimateX, result.estimateY, plot);
            if (showCandidates) drawCandidates(canvas, plot, estimate);
            if (showCentroid) drawCentroid(canvas, plot);
            if (showEstimate) drawEstimate(canvas, estimate);
            if (validationX != null && validationY != null) drawValidation(canvas, plot, estimate);
        }
        canvas.restore();
        canvas.restore();

        drawLegend(canvas, plot);
        paint.setTextAlign(Paint.Align.LEFT);
        paint.setColor(Color.DKGRAY);
        paint.setTextSize(sp(10));
        String footer;
        if (localViewportEnabled && result != null) {
            footer = String.format(Locale.US, "Local estimate view • ±%.0f m • %.0f m × %.0f m",
                    localHalfSpanMeters, 2.0 * localHalfSpanMeters, 2.0 * localHalfSpanMeters);
        } else if (useFloorPlan && floorBitmap != null) {
            footer = interactionEnabled
                    ? "Floor-plan-aligned metric view • pinch to zoom • drag to pan"
                    : "Floor-plan-aligned metric view";
        } else {
            footer = String.format(Locale.US, "Coordinate view • x: %.1f–%.1f m", displayMinX, displayMaxX);
        }
        canvas.drawText(footer, plot.left, getHeight() - dp(10), paint);
    }

    private void drawFloorPlan(Canvas canvas, RectF plot) {
        paint.setAlpha(115);
        if (hasValidStoredBounds()) {
            double spanX = Math.max(1e-9, displayMaxX - displayMinX);
            double spanY = Math.max(1e-9, displayMaxY - displayMinY);
            float left = plot.left + (float) ((floorData.floor.minX - displayMinX) / spanX) * plot.width();
            float right = plot.left + (float) ((floorData.floor.maxX - displayMinX) / spanX) * plot.width();
            float top = plot.bottom - (float) ((floorData.floor.maxY - displayMinY) / spanY) * plot.height();
            float bottom = plot.bottom - (float) ((floorData.floor.minY - displayMinY) / spanY) * plot.height();
            RectF destination = new RectF(left, top, right, bottom);
            canvas.save();
            canvas.clipRect(plot);
            canvas.drawBitmap(floorBitmap, null, destination, paint);
            canvas.restore();
        } else {
            canvas.drawBitmap(floorBitmap, null, plot, paint);
        }
        paint.setAlpha(255);
    }

    private void drawCandidates(Canvas canvas, RectF plot, float[] estimate) {
        paint.setStrokeWidth(dp(1));
        paint.setColor(Color.argb(105, 143, 45, 45));
        for (Candidate candidate : result.candidates) {
            float[] point = screenPoint(candidate.x, candidate.y, plot);
            canvas.drawLine(estimate[0], estimate[1], point[0], point[1], paint);
        }

        for (Candidate candidate : result.candidates) {
            float[] point = screenPoint(candidate.x, candidate.y, plot);
            double angle = (candidate.rank - 1) * (Math.PI * 2.0 / Math.max(8, result.candidates.size()));
            float radius = dp(10 + (candidate.rank % 2) * 4);
            float labelX = point[0] + (float) Math.cos(angle) * radius;
            float labelY = point[1] + (float) Math.sin(angle) * radius;
            paint.setColor(Color.rgb(120, 55, 55));
            canvas.drawCircle(point[0], point[1], dp(2.8f), paint);
            paint.setStrokeWidth(dp(0.8f));
            canvas.drawLine(point[0], point[1], labelX, labelY, paint);
            paint.setColor(Color.WHITE);
            canvas.drawCircle(labelX, labelY, dp(6.5f), paint);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(dp(1.3f));
            paint.setColor(Color.rgb(120, 55, 55));
            canvas.drawCircle(labelX, labelY, dp(6.5f), paint);
            paint.setStyle(Paint.Style.FILL);
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTextSize(sp(7.5f));
            paint.setColor(Color.rgb(95, 35, 35));
            canvas.drawText(Integer.toString(candidate.rank), labelX, labelY + dp(2.7f), paint);
        }
    }

    private void drawCentroid(Canvas canvas, RectF plot) {
        float[] centroid = screenPoint(result.centroidX, result.centroidY, plot);
        paint.setColor(Color.rgb(199, 122, 0));
        paint.setStrokeWidth(dp(2.5f));
        canvas.drawLine(centroid[0] - dp(5), centroid[1] - dp(5), centroid[0] + dp(5), centroid[1] + dp(5), paint);
        canvas.drawLine(centroid[0] - dp(5), centroid[1] + dp(5), centroid[0] + dp(5), centroid[1] - dp(5), paint);
    }

    private void drawEstimate(Canvas canvas, float[] estimate) {
        Path diamond = new Path();
        diamond.moveTo(estimate[0], estimate[1] - dp(9));
        diamond.lineTo(estimate[0] + dp(9), estimate[1]);
        diamond.lineTo(estimate[0], estimate[1] + dp(9));
        diamond.lineTo(estimate[0] - dp(9), estimate[1]);
        diamond.close();
        paint.setColor(Color.rgb(45, 99, 153));
        canvas.drawPath(diamond, paint);
        paint.setStyle(Paint.Style.STROKE);
        paint.setColor(Color.BLACK);
        paint.setStrokeWidth(dp(1));
        canvas.drawPath(diamond, paint);
        paint.setStyle(Paint.Style.FILL);
    }

    private void drawValidation(Canvas canvas, RectF plot, float[] estimate) {
        float[] truth = screenPoint(validationX, validationY, plot);
        paint.setColor(Color.rgb(45, 125, 55));
        paint.setStrokeWidth(dp(1.5f));
        canvas.drawLine(estimate[0], estimate[1], truth[0], truth[1], paint);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(dp(2));
        canvas.drawCircle(truth[0], truth[1], dp(7), paint);
        paint.setStyle(Paint.Style.FILL);
        canvas.drawCircle(truth[0], truth[1], dp(2.5f), paint);
    }

    private void drawGrid(Canvas canvas, RectF plot) {
        paint.setColor(Color.rgb(235, 235, 235));
        paint.setStrokeWidth(dp(1));
        for (int i = 0; i <= 5; i++) {
            float x = plot.left + i * plot.width() / 5f;
            float y = plot.top + i * plot.height() / 5f;
            canvas.drawLine(x, plot.top, x, plot.bottom, paint);
            canvas.drawLine(plot.left, y, plot.right, y, paint);
        }
    }

    private void drawLegend(Canvas canvas, RectF plot) {
        float x = plot.left + dp(8);
        float y = plot.top + dp(14);
        paint.setTextSize(sp(8.7f));
        paint.setTextAlign(Paint.Align.LEFT);
        if (showRps) {
            paint.setColor(Color.rgb(145, 145, 145));
            canvas.drawCircle(x, y, dp(3), paint);
            paint.setColor(Color.DKGRAY);
            canvas.drawText("RPs", x + dp(8), y + dp(3), paint);
        }
        if (result != null && showCandidates) {
            paint.setColor(Color.rgb(120, 55, 55));
            canvas.drawCircle(x + dp(50), y, dp(3.5f), paint);
            paint.setColor(Color.DKGRAY);
            canvas.drawText("Candidates", x + dp(58), y + dp(3), paint);
        }
        if (result != null && showEstimate) {
            paint.setColor(Color.rgb(45, 99, 153));
            canvas.drawCircle(x + dp(126), y, dp(3.5f), paint);
            paint.setColor(Color.DKGRAY);
            canvas.drawText("Estimate", x + dp(134), y + dp(3), paint);
        }
        if (validationX != null && validationY != null) {
            paint.setColor(Color.rgb(45, 125, 55));
            canvas.drawCircle(x + dp(194), y, dp(3.5f), paint);
            paint.setColor(Color.DKGRAY);
            canvas.drawText("Known", x + dp(202), y + dp(3), paint);
        }
    }

    private RectF plotRect() {
        float leftPad = dp(28);
        float rightPad = dp(10);
        float topPad = dp(16);
        float bottomPad = dp(34);
        float availableWidth = Math.max(1f, getWidth() - leftPad - rightPad);
        float availableHeight = Math.max(1f, getHeight() - topPad - bottomPad);
        if (localViewportEnabled) {
            float size = Math.min(availableWidth, availableHeight);
            float left = leftPad + (availableWidth - size) / 2f;
            float top = topPad + (availableHeight - size) / 2f;
            return new RectF(left, top, left + size, top + size);
        }
        return new RectF(leftPad, topPad, getWidth() - rightPad, getHeight() - bottomPad);
    }

    private float[] screenPoint(double x, double y, RectF plot) {
        double spanX = Math.max(1e-9, displayMaxX - displayMinX);
        double spanY = Math.max(1e-9, displayMaxY - displayMinY);
        float screenX = plot.left + (float) ((x - displayMinX) / spanX) * plot.width();
        float screenY = plot.bottom - (float) ((y - displayMinY) / spanY) * plot.height();
        return new float[]{screenX, screenY};
    }

    private double[] metricPoint(float touchX, float touchY, RectF plot) {
        float baseX = plot.centerX() + (touchX - translateX - plot.centerX()) / scale;
        float baseY = plot.centerY() + (touchY - translateY - plot.centerY()) / scale;
        double nx = (baseX - plot.left) / Math.max(1f, plot.width());
        double ny = (plot.bottom - baseY) / Math.max(1f, plot.height());
        nx = Math.max(0.0, Math.min(1.0, nx));
        ny = Math.max(0.0, Math.min(1.0, ny));
        return new double[]{displayMinX + nx * (displayMaxX - displayMinX),
                displayMinY + ny * (displayMaxY - displayMinY)};
    }

    private float[] transformedScreenPoint(double x, double y, RectF plot) {
        float[] base = screenPoint(x, y, plot);
        float sx = translateX + plot.centerX() + scale * (base[0] - plot.centerX());
        float sy = translateY + plot.centerY() + scale * (base[1] - plot.centerY());
        return new float[]{sx, sy};
    }

    private Candidate nearestCandidate(float touchX, float touchY, RectF plot) {
        if (result == null) return null;
        Candidate best = null;
        double bestDistance = dp(24);
        for (Candidate candidate : result.candidates) {
            float[] point = transformedScreenPoint(candidate.x, candidate.y, plot);
            double distance = Math.hypot(touchX - point[0], touchY - point[1]);
            if (distance < bestDistance) {
                bestDistance = distance;
                best = candidate;
            }
        }
        return best;
    }

    private Bitmap rotateFloorPlan(Bitmap source, float angleDegrees) {
        if (source == null || Math.abs(angleDegrees) < 1e-6f) return source;
        Matrix matrix = new Matrix();
        matrix.postRotate(angleDegrees);
        Bitmap rotated = Bitmap.createBitmap(source, 0, 0, source.getWidth(), source.getHeight(), matrix, true);
        if (rotated != source) source.recycle();
        return rotated;
    }

    private void computeDisplayBounds() {
        if (floorData == null) return;
        if (localViewportEnabled && result != null
                && Double.isFinite(result.estimateX) && Double.isFinite(result.estimateY)) {
            displayMinX = result.estimateX - localHalfSpanMeters;
            displayMaxX = result.estimateX + localHalfSpanMeters;
            displayMinY = result.estimateY - localHalfSpanMeters;
            displayMaxY = result.estimateY + localHalfSpanMeters;
            return;
        }
        if (useFloorPlan && floorBitmap != null && hasValidStoredBounds()) {
            displayMinX = floorData.floor.minX;
            displayMinY = floorData.floor.minY;
            displayMaxX = floorData.floor.maxX;
            displayMaxY = floorData.floor.maxY;
            return;
        }
        if (!floorData.referencePoints.isEmpty()) {
            displayMinX = Double.POSITIVE_INFINITY;
            displayMinY = Double.POSITIVE_INFINITY;
            displayMaxX = Double.NEGATIVE_INFINITY;
            displayMaxY = Double.NEGATIVE_INFINITY;
            for (double[] rp : floorData.referencePoints) {
                displayMinX = Math.min(displayMinX, rp[0]);
                displayMinY = Math.min(displayMinY, rp[1]);
                displayMaxX = Math.max(displayMaxX, rp[0]);
                displayMaxY = Math.max(displayMaxY, rp[1]);
            }
            double marginX = Math.max(1.0, (displayMaxX - displayMinX) * 0.03);
            double marginY = Math.max(1.0, (displayMaxY - displayMinY) * 0.03);
            displayMinX -= marginX;
            displayMaxX += marginX;
            displayMinY -= marginY;
            displayMaxY += marginY;
            return;
        }
        displayMinX = floorData.floor.minX;
        displayMinY = floorData.floor.minY;
        displayMaxX = floorData.floor.maxX;
        displayMaxY = floorData.floor.maxY;
    }

    private boolean hasValidStoredBounds() {
        return Double.isFinite(floorData.floor.minX)
                && Double.isFinite(floorData.floor.minY)
                && Double.isFinite(floorData.floor.maxX)
                && Double.isFinite(floorData.floor.maxY)
                && floorData.floor.maxX > floorData.floor.minX
                && floorData.floor.maxY > floorData.floor.minY;
    }

    private void drawCenteredText(Canvas canvas, String text) {
        paint.setColor(Color.GRAY);
        paint.setTextSize(sp(14));
        paint.setTextAlign(Paint.Align.CENTER);
        canvas.drawText(text, getWidth() / 2f, getHeight() / 2f, paint);
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        if (!interactionEnabled) return false;
        scaleDetector.onTouchEvent(event);
        if (event.getPointerCount() == 1 && !scaleDetector.isInProgress()) {
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    lastX = downX = event.getX();
                    lastY = downY = event.getY();
                    moved = false;
                    return true;
                case MotionEvent.ACTION_MOVE:
                    float dx = event.getX() - lastX;
                    float dy = event.getY() - lastY;
                    if (Math.hypot(event.getX() - downX, event.getY() - downY) > dp(7)) moved = true;
                    translateX += dx;
                    translateY += dy;
                    lastX = event.getX();
                    lastY = event.getY();
                    invalidate();
                    return true;
                case MotionEvent.ACTION_UP:
                    if (!moved && floorData != null) {
                        RectF plot = plotRect();
                        if (validationMode) {
                            double[] metric = metricPoint(event.getX(), event.getY(), plot);
                            validationX = metric[0];
                            validationY = metric[1];
                            if (validationListener != null) validationListener.onValidationPoint(metric[0], metric[1]);
                            invalidate();
                        } else if (candidateTapListener != null) {
                            Candidate candidate = nearestCandidate(event.getX(), event.getY(), plot);
                            if (candidate != null) candidateTapListener.onCandidateTapped(candidate);
                        }
                    }
                    performClick();
                    return true;
                default:
                    break;
            }
        }
        return true;
    }

    @Override public boolean performClick() {
        super.performClick();
        return true;
    }

    private final class ScaleListener extends ScaleGestureDetector.SimpleOnScaleGestureListener {
        @Override public boolean onScale(ScaleGestureDetector detector) {
            scale *= detector.getScaleFactor();
            scale = Math.max(0.8f, Math.min(scale, 7f));
            invalidate();
            return true;
        }
    }

    private float dp(float value) { return value * getResources().getDisplayMetrics().density; }
    private float sp(float value) { return value * getResources().getDisplayMetrics().scaledDensity; }
}
