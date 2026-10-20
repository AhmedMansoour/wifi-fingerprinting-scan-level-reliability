package com.wifiintegrity.inspector.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;

import com.wifiintegrity.inspector.diagnostics.DiagnosticEngine;
import com.wifiintegrity.inspector.model.IndicatorDiagnostic;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Responsive mobile chart for the 18 condition-relative diagnostics. */
public final class IndicatorBarView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dashed = new Paint(Paint.ANTI_ALIAS_FLAG);
    private List<IndicatorDiagnostic> indicators = new ArrayList<>();

    private final int warningColor = Color.rgb(184, 58, 58);
    private final int safeColor = Color.rgb(63, 134, 179);
    private final int unavailableColor = Color.rgb(185, 185, 185);
    private final int axisColor = Color.rgb(45, 45, 45);

    private final float rowHeightDp = 46f;
    private final float groupHeightDp = 28f;
    private final float axisHeightDp = 62f;
    private final float emptyHeightDp = 220f;

    public IndicatorBarView(Context context) { super(context); initialize(); }
    public IndicatorBarView(Context context, AttributeSet attrs) { super(context, attrs); initialize(); }
    public IndicatorBarView(Context context, AttributeSet attrs, int style) { super(context, attrs, style); initialize(); }

    private void initialize() {
        paint.setTypeface(android.graphics.Typeface.create("serif", android.graphics.Typeface.NORMAL));
        dashed.setColor(Color.rgb(145, 145, 145));
        dashed.setStrokeWidth(dp(1.6f));
        dashed.setStyle(Paint.Style.STROKE);
        dashed.setPathEffect(new DashPathEffect(new float[]{dp(6), dp(5)}, 0));
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
        setMinimumHeight((int) dp(emptyHeightDp));
    }

    public void setIndicators(List<IndicatorDiagnostic> values) {
        indicators = values == null ? new ArrayList<>() : new ArrayList<>(values);
        requestLayout();
        invalidate();
    }

    @Override protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int width = MeasureSpec.getSize(widthMeasureSpec);
        int desiredHeight;
        if (indicators.isEmpty()) {
            desiredHeight = (int) dp(emptyHeightDp);
        } else {
            int groups = 0;
            String previous = null;
            for (IndicatorDiagnostic indicator : indicators) {
                if (!indicator.group.equals(previous)) {
                    groups++;
                    previous = indicator.group;
                }
            }
            desiredHeight = (int) dp(12 + indicators.size() * rowHeightDp + groups * groupHeightDp + axisHeightDp);
        }
        int height = resolveSize(desiredHeight, heightMeasureSpec);
        setMeasuredDimension(width, height);
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        canvas.drawColor(Color.WHITE);
        float width = getWidth();
        float pad = dp(10);

        if (indicators.isEmpty()) {
            paint.setColor(Color.GRAY);
            paint.setTextSize(sp(14));
            paint.setTextAlign(Paint.Align.CENTER);
            canvas.drawText("Run a Wi-Fi scan to populate the 18 diagnostics.", width / 2f, getHeight() / 2f, paint);
            return;
        }

        // Responsive columns: label | raw value | percentile bar | W.
        float labelRight = width * 0.40f;
        float valueRight = width * 0.51f;
        float plotLeft = width * 0.53f;
        float warningColumn = width - dp(22);
        float plotRight = warningColumn - dp(13);
        float plotWidth = Math.max(dp(90), plotRight - plotLeft);
        float y = dp(8);
        String previousGroup = null;

        // Determine chart bottom before drawing the shared grid.
        int groups = 0;
        for (IndicatorDiagnostic indicator : indicators) {
            if (!indicator.group.equals(previousGroup)) {
                groups++;
                previousGroup = indicator.group;
            }
        }
        float chartTop = y;
        float chartBottom = chartTop + dp(groups * groupHeightDp + indicators.size() * rowHeightDp);

        for (int tick = 0; tick <= 5; tick++) {
            float value = tick / 5f;
            float x = plotLeft + value * plotWidth;
            paint.setColor(Color.rgb(226, 226, 226));
            paint.setStrokeWidth(dp(0.7f));
            canvas.drawLine(x, chartTop, x, chartBottom, paint);
        }
        float cutoffX = plotLeft + (float) DiagnosticEngine.WARNING_CUTOFF * plotWidth;
        canvas.drawLine(cutoffX, chartTop, cutoffX, chartBottom, dashed);

        previousGroup = null;
        for (IndicatorDiagnostic indicator : indicators) {
            if (!indicator.group.equals(previousGroup)) {
                paint.setColor(Color.rgb(247, 247, 247));
                canvas.drawRect(0, y, width, y + dp(groupHeightDp), paint);
                paint.setColor(Color.rgb(95, 95, 95));
                paint.setTextAlign(Paint.Align.LEFT);
                paint.setTypeface(android.graphics.Typeface.create("sans", android.graphics.Typeface.BOLD));
                paint.setTextSize(sp(10.5f));
                canvas.drawText(indicator.group, pad, y + dp(19), paint);
                y += dp(groupHeightDp);
                previousGroup = indicator.group;
            }

            float rowTop = y;
            float centerY = rowTop + dp(rowHeightDp / 2f);
            paint.setColor(Color.rgb(235, 235, 235));
            paint.setStrokeWidth(dp(0.5f));
            canvas.drawLine(pad, rowTop + dp(rowHeightDp), width - pad, rowTop + dp(rowHeightDp), paint);

            paint.setTypeface(android.graphics.Typeface.create("serif", android.graphics.Typeface.NORMAL));
            paint.setTextSize(sp(11.5f));
            paint.setTextAlign(Paint.Align.RIGHT);
            paint.setColor(Color.rgb(30, 30, 30));
            canvas.drawText(indicator.label, labelRight, centerY + dp(4), paint);

            paint.setTextSize(sp(9.5f));
            paint.setColor(Color.rgb(95, 95, 95));
            canvas.drawText(DiagnosticEngine.formatValue(indicator), valueRight, centerY + dp(3.5f), paint);

            boolean available = Double.isFinite(indicator.adversePercentile);
            double percentile = available ? Math.max(0.0, Math.min(1.0, indicator.adversePercentile)) : 0.0;
            float barEnd = plotLeft + (float) percentile * plotWidth;
            paint.setColor(!available ? unavailableColor : indicator.warning ? warningColor : safeColor);
            RectF bar = new RectF(plotLeft, rowTop + dp(8), barEnd, rowTop + dp(rowHeightDp - 8));
            canvas.drawRect(bar, paint);

            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTypeface(android.graphics.Typeface.create("serif", android.graphics.Typeface.BOLD));
            paint.setTextSize(sp(11));
            if (!available) {
                paint.setColor(Color.DKGRAY);
                canvas.drawText("—", warningColumn, centerY + dp(4), paint);
            } else if (indicator.warning) {
                paint.setColor(warningColor);
                canvas.drawText("W", warningColumn, centerY + dp(4), paint);
            }
            y += dp(rowHeightDp);
        }

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(dp(1));
        paint.setColor(axisColor);
        canvas.drawRect(plotLeft, chartTop, plotRight, chartBottom, paint);
        paint.setStyle(Paint.Style.FILL);

        float tickY = chartBottom + dp(18);
        for (int tick = 0; tick <= 5; tick++) {
            float value = tick / 5f;
            float x = plotLeft + value * plotWidth;
            paint.setColor(axisColor);
            paint.setTextSize(sp(9.5f));
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTypeface(android.graphics.Typeface.create("serif", android.graphics.Typeface.NORMAL));
            canvas.drawText(String.format(Locale.US, "%.1f", value), x, tickY, paint);
        }

        paint.setColor(axisColor);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTextSize(sp(10.5f));
        canvas.drawText("Adverse percentile within the same floor–estimator condition",
                (plotLeft + plotRight) / 2f, chartBottom + dp(39), paint);
        paint.setTextAlign(Paint.Align.RIGHT);
        paint.setTextSize(sp(9.2f));
        paint.setColor(Color.DKGRAY);
        canvas.drawText("- -  80th-percentile warning cutoff", plotRight, chartBottom + dp(57), paint);
    }

    private float dp(float value) { return value * getResources().getDisplayMetrics().density; }
    private float sp(float value) { return value * getResources().getDisplayMetrics().scaledDensity; }
}
