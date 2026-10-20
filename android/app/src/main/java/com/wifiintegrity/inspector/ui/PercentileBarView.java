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

/** Compact horizontal adverse-percentile bar with the 0.80 warning cutoff. */
public final class PercentileBarView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dashed = new Paint(Paint.ANTI_ALIAS_FLAG);
    private double percentile = Double.NaN;
    private boolean warning;

    public PercentileBarView(Context context) { super(context); initialize(); }
    public PercentileBarView(Context context, AttributeSet attrs) { super(context, attrs); initialize(); }
    public PercentileBarView(Context context, AttributeSet attrs, int style) { super(context, attrs, style); initialize(); }

    private void initialize() {
        setMinimumHeight((int) dp(30));
        dashed.setColor(Color.rgb(135, 135, 135));
        dashed.setStrokeWidth(dp(1.5f));
        dashed.setPathEffect(new DashPathEffect(new float[]{dp(5), dp(4)}, 0));
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
    }

    public void setPercentile(double value, boolean isWarning) {
        percentile = value;
        warning = isWarning;
        invalidate();
    }

    @Override protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        int height = resolveSize((int) dp(32), heightMeasureSpec);
        setMeasuredDimension(MeasureSpec.getSize(widthMeasureSpec), height);
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        final float width = getWidth();
        final float height = getHeight();
        final float top = dp(5);
        final float bottom = height - dp(5);

        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.rgb(247, 247, 247));
        canvas.drawRect(0, top, width, bottom, paint);

        for (int tick = 1; tick < 5; tick++) {
            float x = width * tick / 5f;
            paint.setColor(Color.rgb(224, 224, 224));
            paint.setStrokeWidth(dp(0.7f));
            canvas.drawLine(x, top, x, bottom, paint);
        }

        if (Double.isFinite(percentile)) {
            float end = (float) Math.max(0.0, Math.min(1.0, percentile)) * width;
            paint.setColor(warning ? Color.rgb(184, 58, 58) : Color.rgb(63, 134, 179));
            canvas.drawRect(new RectF(0, top, end, bottom), paint);
        } else {
            paint.setColor(Color.rgb(190, 190, 190));
            canvas.drawRect(new RectF(0, top, width * 0.04f, bottom), paint);
        }

        float cutoffX = (float) DiagnosticEngine.WARNING_CUTOFF * width;
        canvas.drawLine(cutoffX, top, cutoffX, bottom, dashed);

        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(dp(0.8f));
        paint.setColor(Color.rgb(75, 75, 75));
        canvas.drawRect(0, top, width, bottom, paint);
        paint.setStyle(Paint.Style.FILL);
    }

    private float dp(float value) {
        return value * getResources().getDisplayMetrics().density;
    }
}
