package com.wifiintegrity.inspector.ui;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.util.AttributeSet;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.wifiintegrity.inspector.diagnostics.DiagnosticEngine;
import com.wifiintegrity.inspector.model.IndicatorDiagnostic;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/**
 * Reliable mobile rendering of all 18 indicator diagnostics.
 * Uses ordinary child views rather than one tall Canvas, avoiding zero-height or clipped charts in ScrollView.
 */
public final class IndicatorDiagnosticsView extends LinearLayout {
    private final int warningColor = Color.rgb(184, 58, 58);
    private final int safeColor = Color.rgb(63, 134, 179);

    public IndicatorDiagnosticsView(Context context) { super(context); initialize(); }
    public IndicatorDiagnosticsView(Context context, AttributeSet attrs) { super(context, attrs); initialize(); }
    public IndicatorDiagnosticsView(Context context, AttributeSet attrs, int style) { super(context, attrs, style); initialize(); }

    private void initialize() {
        setOrientation(VERTICAL);
        setBackgroundColor(Color.WHITE);
        setPadding(dp(4), dp(4), dp(4), dp(10));
        showEmptyState();
    }

    public void setDiagnostics(List<IndicatorDiagnostic> diagnostics) {
        removeAllViews();
        List<IndicatorDiagnostic> values = diagnostics == null ? Collections.emptyList() : diagnostics;
        if (values.isEmpty()) {
            showEmptyState();
            return;
        }

        // Put the three composite indicators first so the most concise overall
        // reliability summary is visible immediately when the page opens.
        List<IndicatorDiagnostic> ordered = new ArrayList<>(values);
        ordered.sort(Comparator
                .comparingInt((IndicatorDiagnostic item) -> groupPriority(item.group))
                .thenComparingInt(item -> item.position));

        addColumnHeader();
        String previousGroup = null;
        for (IndicatorDiagnostic indicator : ordered) {
            if (!indicator.group.equals(previousGroup)) {
                addGroupHeader(indicator.group);
                previousGroup = indicator.group;
            }
            addIndicatorRow(indicator);
        }
        addAxisRow();
        addLegend();
    }


    private int groupPriority(String group) {
        if ("Composite indicators".equals(group)) return 0;
        if ("Scan characteristics".equals(group)) return 1;
        if ("Scan–radio-map compatibility".equals(group)
                || "Scan--radio-map compatibility".equals(group)) return 2;
        if ("Spatial support".equals(group)) return 3;
        if ("Candidate geometry".equals(group)) return 4;
        if ("Radio-map ambiguity".equals(group) || "Ambiguity".equals(group)) return 5;
        return 6;
    }

    private void showEmptyState() {
        TextView empty = text("Run a Wi-Fi scan to populate the 18 condition-relative diagnostics.", 14, Color.DKGRAY, Gravity.CENTER);
        empty.setPadding(dp(18), dp(44), dp(18), dp(44));
        addView(empty, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
    }

    private void addColumnHeader() {
        LinearLayout row = horizontalRow();
        row.setPadding(dp(4), dp(6), dp(4), dp(6));
        row.setBackgroundColor(Color.rgb(250, 250, 250));
        row.addView(weightedText("Indicator", 10, Color.DKGRAY, Gravity.START, 1.28f));
        row.addView(weightedText("Raw", 10, Color.DKGRAY, Gravity.END, 0.45f));
        row.addView(weightedText("Adverse percentile", 10, Color.DKGRAY, Gravity.CENTER, 1.40f));
        row.addView(weightedText("", 10, Color.DKGRAY, Gravity.CENTER, 0.20f));
        addView(row);
    }

    private void addGroupHeader(String group) {
        TextView header = text(group, 11, Color.rgb(82, 82, 82), Gravity.START | Gravity.CENTER_VERTICAL);
        header.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        header.setBackgroundColor(Color.rgb(242, 242, 242));
        header.setPadding(dp(9), dp(7), dp(9), dp(7));
        LayoutParams params = new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(3);
        addView(header, params);
    }

    private void addIndicatorRow(IndicatorDiagnostic indicator) {
        LinearLayout row = horizontalRow();
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setMinimumHeight(dp(48));
        row.setPadding(dp(4), dp(3), dp(4), dp(3));
        row.setBackgroundColor(indicator.warning ? Color.rgb(255, 249, 249) : Color.WHITE);

        TextView label = weightedText(indicator.label, 12, Color.rgb(32, 32, 32), Gravity.END | Gravity.CENTER_VERTICAL, 1.28f);
        label.setPadding(0, 0, dp(8), 0);
        row.addView(label);

        TextView raw = weightedText(DiagnosticEngine.formatValue(indicator), 10, Color.rgb(95, 95, 95), Gravity.END | Gravity.CENTER_VERTICAL, 0.45f);
        raw.setPadding(0, 0, dp(6), 0);
        row.addView(raw);

        PercentileBarView bar = new PercentileBarView(getContext());
        bar.setPercentile(indicator.adversePercentile, indicator.warning);
        LayoutParams barParams = new LayoutParams(0, dp(34), 1.40f);
        row.addView(bar, barParams);

        String marker = !Double.isFinite(indicator.adversePercentile) ? "—" : indicator.warning ? "W" : "";
        TextView status = weightedText(marker, 13, indicator.warning ? warningColor : safeColor, Gravity.CENTER, 0.20f);
        status.setTypeface(Typeface.SERIF, Typeface.BOLD);
        row.addView(status);

        addView(row, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));

        TextView separator = new TextView(getContext());
        separator.setBackgroundColor(Color.rgb(232, 232, 232));
        addView(separator, new LayoutParams(LayoutParams.MATCH_PARENT, dp(1)));
    }

    private void addAxisRow() {
        LinearLayout row = horizontalRow();
        row.setPadding(dp(4), dp(2), dp(4), 0);
        row.addView(weightedText("", 9, Color.GRAY, Gravity.CENTER, 1.28f));
        row.addView(weightedText("", 9, Color.GRAY, Gravity.CENTER, 0.45f));
        TextView ticks = weightedText("0.0      0.2      0.4      0.6      0.8      1.0", 9, Color.DKGRAY, Gravity.CENTER, 1.40f);
        row.addView(ticks);
        row.addView(weightedText("", 9, Color.GRAY, Gravity.CENTER, 0.20f));
        addView(row);
    }

    private void addLegend() {
        TextView legend = text("Dashed line: 80th-percentile warning cutoff. Red bar and W: warning; blue bar: below cutoff.",
                10, Color.DKGRAY, Gravity.END);
        legend.setPadding(dp(8), dp(6), dp(8), dp(2));
        addView(legend, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
    }

    private LinearLayout horizontalRow() {
        LinearLayout row = new LinearLayout(getContext());
        row.setOrientation(HORIZONTAL);
        row.setLayoutParams(new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
        return row;
    }

    private TextView weightedText(String value, float sizeSp, int color, int gravity, float weight) {
        TextView view = text(value, sizeSp, color, gravity);
        view.setSingleLine(false);
        view.setLayoutParams(new LayoutParams(0, LayoutParams.WRAP_CONTENT, weight));
        return view;
    }

    private TextView text(String value, float sizeSp, int color, int gravity) {
        TextView view = new TextView(getContext());
        view.setText(value);
        view.setTextSize(sizeSp);
        view.setTextColor(color);
        view.setGravity(gravity);
        view.setIncludeFontPadding(false);
        return view;
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
