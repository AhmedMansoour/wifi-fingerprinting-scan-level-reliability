package com.wifiintegrity.inspector.ui;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import com.wifiintegrity.inspector.R;
import com.wifiintegrity.inspector.importer.RadioMapPackageImporter;
import com.wifiintegrity.inspector.repository.RadioMapRepository;

import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class RadioMapManagerActivity extends Activity {
    private static final int REQUEST_IMPORT = 3101;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private RadioMapRepository repository;
    private TextView status;
    private ListView list;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_manager);
        repository = new RadioMapRepository(this);
        status = findViewById(R.id.textImportStatus);
        list = findViewById(R.id.listRadioMaps);
        findViewById(R.id.buttonImportPackage).setOnClickListener(view -> selectPackage());
        refreshList();
    }

    private void selectPackage() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/zip");
        startActivityForResult(intent, REQUEST_IMPORT);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != REQUEST_IMPORT || resultCode != RESULT_OK || data == null) return;
        Uri uri = data.getData();
        if (uri == null) return;
        status.setText("Importing and validating the selected package…");
        executor.execute(() -> {
            try {
                String report = new RadioMapPackageImporter(this, repository).importPackage(uri);
                runOnUiThread(() -> {
                    status.setText(report);
                    Toast.makeText(this, report, Toast.LENGTH_LONG).show();
                    refreshList();
                });
            } catch (Exception error) {
                runOnUiThread(() -> status.setText("Import failed: " + error.getMessage()));
            }
        });
    }

    private void refreshList() {
        executor.execute(() -> {
            List<String> rows = repository.listRadioMapSummary();
            runOnUiThread(() -> list.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, rows)));
        });
    }

    @Override protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
