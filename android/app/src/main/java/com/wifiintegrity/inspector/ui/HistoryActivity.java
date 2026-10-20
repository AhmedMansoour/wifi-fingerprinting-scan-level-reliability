package com.wifiintegrity.inspector.ui;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.ListView;
import android.widget.TextView;

import com.wifiintegrity.inspector.R;
import com.wifiintegrity.inspector.model.HistoryItem;
import com.wifiintegrity.inspector.repository.RadioMapRepository;

import java.text.DateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class HistoryActivity extends Activity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private RadioMapRepository repository;
    private ListView listView;
    private TextView emptyText;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_history);
        repository = new RadioMapRepository(this);
        listView = findViewById(R.id.listHistory);
        emptyText = findViewById(R.id.textHistoryEmpty);
        loadHistory();
    }

    private void loadHistory() {
        executor.execute(() -> {
            List<HistoryItem> items = repository.listHistory();
            runOnUiThread(() -> {
                emptyText.setVisibility(items.isEmpty() ? View.VISIBLE : View.GONE);
                HistoryAdapter adapter = new HistoryAdapter(items);
                listView.setAdapter(adapter);
                listView.setOnItemClickListener((parent, view, position, id) -> {
                    Intent intent = new Intent(this, InspectionDetailActivity.class);
                    intent.putExtra("inspection_id", items.get(position).id);
                    startActivity(intent);
                });
            });
        });
    }

    @Override protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private final class HistoryAdapter extends BaseAdapter {
        private final List<HistoryItem> items;
        HistoryAdapter(List<HistoryItem> items) { this.items = items; }
        @Override public int getCount() { return items.size(); }
        @Override public Object getItem(int position) { return items.get(position); }
        @Override public long getItemId(int position) { return items.get(position).id; }

        @Override public View getView(int position, View convertView, ViewGroup parent) {
            View view = convertView;
            if (view == null) view = LayoutInflater.from(HistoryActivity.this)
                    .inflate(android.R.layout.simple_list_item_2, parent, false);
            TextView line1 = view.findViewById(android.R.id.text1);
            TextView line2 = view.findViewById(android.R.id.text2);
            HistoryItem item = items.get(position);
            String floorMode = item.floorInferred
                    ? "inferred" + (item.floorConfidence == null ? "" : "-" + item.floorConfidence)
                    : "manual";
            line1.setText(item.buildingName + " — " + item.floorName + "   " + item.estimator + "   [" + floorMode + "]");
            String sqs = Double.isFinite(item.sqs) ? String.format(Locale.US, "%.3f", item.sqs) : "N/A";
            String warnings = item.warnings < 0 ? "N/A" : item.warnings + "/18";
            String validation = item.validationErrorM == null ? "" : String.format(Locale.US, "  |  Error %.2f m", item.validationErrorM);
            line2.setText(String.format(Locale.US, "%s  |  SQS %s  |  Warnings %s  |  APs %d  |  (%.1f, %.1f)%s",
                    DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(new Date(item.createdAt)),
                    sqs, warnings, item.mappedAps, item.x, item.y, validation));
            line1.setTextColor(getColor(R.color.primary_dark));
            return view;
        }
    }
}
