package com.wifiintegrity.inspector.scanner;

import android.annotation.SuppressLint;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.wifi.ScanResult;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;

import com.wifiintegrity.inspector.model.ScanObservation;

import java.util.ArrayList;
import java.util.List;

public final class WifiScanner {
    public interface Callback {
        void onScanReady(List<ScanObservation> observations, boolean fresh, String message);
        void onScanError(String message);
    }

    private final Context context;
    private final WifiManager wifiManager;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private BroadcastReceiver receiver;
    private boolean registered;

    public WifiScanner(Context context) {
        this.context = context.getApplicationContext();
        this.wifiManager = (WifiManager) this.context.getSystemService(Context.WIFI_SERVICE);
    }

    @SuppressLint("MissingPermission")
    public void start(Callback callback) {
        if (wifiManager == null) {
            callback.onScanError("Wi-Fi service is unavailable on this device.");
            return;
        }
        unregister();
        receiver = new BroadcastReceiver() {
            @Override public void onReceive(Context ignored, Intent intent) {
                if (!WifiManager.SCAN_RESULTS_AVAILABLE_ACTION.equals(intent.getAction())) return;
                boolean updated = intent.getBooleanExtra(WifiManager.EXTRA_RESULTS_UPDATED, false);
                List<ScanObservation> observations = convert(wifiManager.getScanResults());
                unregister();
                if (observations.isEmpty()) callback.onScanError("The Wi-Fi scan returned no access points.");
                else callback.onScanReady(observations, updated, updated ? "Fresh scan received." : "Android returned cached scan results.");
            }
        };
        IntentFilter filter = new IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION);
        if (Build.VERSION.SDK_INT >= 33) context.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED);
        else context.registerReceiver(receiver, filter);
        registered = true;

        boolean started = wifiManager.startScan();
        if (!started) {
            handler.postDelayed(() -> {
                if (!registered) return;
                List<ScanObservation> cached = convert(wifiManager.getScanResults());
                unregister();
                if (cached.isEmpty()) callback.onScanError("Android rejected the scan request and no cached results are available.");
                else callback.onScanReady(cached, false, "The scan request was throttled; cached results are being diagnosed.");
            }, 1500L);
        } else {
            handler.postDelayed(() -> {
                if (!registered) return;
                List<ScanObservation> cached = convert(wifiManager.getScanResults());
                unregister();
                if (cached.isEmpty()) callback.onScanError("Timed out while waiting for Wi-Fi scan results.");
                else callback.onScanReady(cached, false, "Timed out waiting for the broadcast; the latest cached results are being diagnosed.");
            }, 12000L);
        }
    }

    public void release() { unregister(); }

    private void unregister() {
        if (!registered || receiver == null) return;
        try { context.unregisterReceiver(receiver); } catch (IllegalArgumentException ignored) { }
        registered = false;
        receiver = null;
    }

    private static List<ScanObservation> convert(List<ScanResult> results) {
        List<ScanObservation> observations = new ArrayList<>();
        if (results == null) return observations;
        for (ScanResult result : results) {
            if (result.BSSID == null || result.BSSID.trim().isEmpty()) continue;
            observations.add(new ScanObservation(result.BSSID, result.level, result.timestamp));
        }
        return observations;
    }
}
