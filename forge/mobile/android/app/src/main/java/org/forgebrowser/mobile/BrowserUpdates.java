/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.net.URL;
import java.security.MessageDigest;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.net.ssl.HttpsURLConnection;

/** Manual, cookie-free check. No browsing data, background job or silent install. */
final class BrowserUpdates {
    private final Activity activity;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile HttpsURLConnection connection;
    private volatile boolean cancelled;
    private boolean busy, disposed;
    private AlertDialog dialog;

    BrowserUpdates(Activity activity) {
        this.activity = activity;
        worker.execute(() -> {
            File[] files = new File(activity.getCacheDir(), "forge-updates").listFiles();
            if (files != null) for (File file : files) {
                if (file.isFile() && file.lastModified() < System.currentTimeMillis() - 86400000L) file.delete();
            }
        });
    }

    private static long version(PackageInfo info) {
        return Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
    }

    @SuppressWarnings("deprecation")
    static String signer(PackageInfo info) throws Exception {
        Signature[] signatures;
        if (Build.VERSION.SDK_INT >= 28) {
            if (info.signingInfo == null || info.signingInfo.hasMultipleSigners()) throw new IOException("Multiple/missing signers");
            signatures = info.signingInfo.getApkContentsSigners();
        } else signatures = info.signatures;
        if (signatures == null || signatures.length != 1) throw new IOException("One signer required");
        return UpdatePolicy.hex(MessageDigest.getInstance("SHA-256").digest(signatures[0].toByteArray()));
    }

    @SuppressWarnings("deprecation")
    private static int signatureFlags() {
        return Build.VERSION.SDK_INT >= 28 ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
    }

    private PackageInfo installed() throws Exception {
        return activity.getPackageManager().getPackageInfo(activity.getPackageName(), signatureFlags());
    }

    private HttpsURLConnection connect(String url, long maximum) throws Exception {
        HttpsURLConnection value = (HttpsURLConnection) new URL(url).openConnection();
        connection = value;
        value.setInstanceFollowRedirects(false); value.setConnectTimeout(15000); value.setReadTimeout(30000);
        value.setUseCaches(false);
        value.setRequestProperty("Accept-Encoding", "identity");
        value.setRequestProperty("User-Agent", "Forge-Android-Update/1");
        if (cancelled || value.getResponseCode() != 200 || value.getContentLengthLong() > maximum
            || (value.getContentEncoding() != null && !"identity".equalsIgnoreCase(value.getContentEncoding())))
            throw new IOException("Unexpected update response");
        return value;
    }

    private byte[] fetchManifest() throws Exception {
        HttpsURLConnection request = connect(UpdatePolicy.ENDPOINT, 65536);
        try (InputStream input = request.getInputStream(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096]; int count;
            while ((count = input.read(buffer)) != -1) {
                if (cancelled || output.size() + count > 65536) throw new IOException("Cancelled/oversize manifest");
                output.write(buffer, 0, count);
            }
            return output.toByteArray();
        } finally { request.disconnect(); connection = null; }
    }

    void show() {
        if (busy || disposed) return;
        dialog = new AlertDialog.Builder(activity).setTitle(R.string.update_title)
            .setMessage(R.string.update_privacy).setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.update_check, (d, which) -> check()).create();
        dialog.show();
    }

    private void check() {
        busy = true; cancelled = false;
        progress(R.string.update_checking);
        worker.execute(() -> {
            try {
                PackageInfo current = installed();
                String abi = Build.SUPPORTED_ABIS[0];
                long sequence = activity.getSharedPreferences("forge-updates", 0).getLong("sequence", 0);
                UpdatePolicy.Offer offer = UpdatePolicy.verify(fetchManifest(), System.currentTimeMillis() / 1000, sequence, abi);
                if (!signer(current).equals(offer.certificate)) throw new IOException("Signing identity mismatch");
                if (cancelled) return;
                if (!activity.getSharedPreferences("forge-updates", 0).edit().putLong("sequence", offer.sequence).commit())
                    throw new IOException("Cannot persist rollback protection");
                main.post(() -> {
                    if (cancelled || disposed) return;
                    busy = false; dismiss();
                    if (offer.versionCode <= version(current)) { message(R.string.update_current); return; }
                    dialog = new AlertDialog.Builder(activity).setTitle(R.string.update_title)
                        .setMessage(activity.getString(R.string.update_offer, offer.versionName, offer.bytes / 1048576))
                        .setNegativeButton(android.R.string.cancel, null)
                        .setPositiveButton(R.string.update_download, (d, which) -> download(offer)).create();
                    dialog.show();
                });
            } catch (Exception error) { failed(); }
            finally { main.post(() -> { if (cancelled) busy = false; }); }
        });
    }

    private void download(UpdatePolicy.Offer offer) {
        busy = true; cancelled = false; progress(R.string.update_downloading);
        worker.execute(() -> {
            File directory = new File(activity.getCacheDir(), "forge-updates");
            File file = new File(directory, java.util.UUID.randomUUID() + ".apk");
            File partial = new File(directory, file.getName() + ".part");
            boolean ready = false;
            try {
                if (offer.expires <= System.currentTimeMillis() / 1000) throw new IOException("Expired offer");
                if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Cannot create update cache");
                HttpsURLConnection request = connect(offer.url, offer.bytes);
                try (InputStream input = request.getInputStream(); FileOutputStream output = new FileOutputStream(partial)) {
                    UpdatePolicy.copy(input, output, offer, () -> cancelled);
                    output.getFD().sync();
                } finally { request.disconnect(); connection = null; }
                PackageInfo archive = activity.getPackageManager().getPackageArchiveInfo(partial.getPath(), signatureFlags());
                PackageInfo current = installed();
                if (archive == null || !UpdatePolicy.PACKAGE.equals(archive.packageName)
                    || version(archive) != offer.versionCode || version(archive) <= version(current)
                    || !offer.certificate.equals(signer(archive)) || !offer.certificate.equals(signer(current))
                    || offer.expires <= System.currentTimeMillis() / 1000 || cancelled) throw new IOException("APK identity/version mismatch");
                if (!partial.renameTo(file)) throw new IOException("Cannot activate verified cache file");
                ready = true;
                main.post(() -> {
                    if (cancelled || disposed) { file.delete(); return; }
                    busy = false; dismiss();
                    dialog = new AlertDialog.Builder(activity).setTitle(R.string.update_title)
                        .setMessage(R.string.update_verified).setNegativeButton(android.R.string.cancel, (d, w) -> file.delete())
                        .setOnCancelListener(d -> file.delete())
                        .setPositiveButton(R.string.update_install, (d, w) -> install(file)).create();
                    dialog.show();
                });
            } catch (Exception error) { failed(); }
            finally {
                partial.delete(); if (!ready) file.delete();
                main.post(() -> { if (cancelled) busy = false; });
            }
        });
    }

    private void install(File file) {
        if (!file.isFile() || disposed) return;
        if (!activity.getPackageManager().canRequestPackageInstalls()) {
            dialog = new AlertDialog.Builder(activity).setTitle(R.string.update_title).setMessage(R.string.update_permission)
                .setNegativeButton(android.R.string.cancel, (d, w) -> file.delete())
                .setPositiveButton(R.string.update_settings, (d, w) -> {
                    file.delete();
                    try { activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + activity.getPackageName()))); }
                    catch (RuntimeException error) { message(R.string.update_failed); }
                }).create();
            dialog.show(); return;
        }
        try {
            Uri uri = new Uri.Builder().scheme("content").authority(activity.getPackageName() + ".updates").appendPath(file.getName()).build();
            Intent intent = new Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            activity.startActivity(intent);
        } catch (RuntimeException error) { file.delete(); message(R.string.update_failed); }
    }

    private void progress(int text) {
        dismiss(); dialog = new AlertDialog.Builder(activity).setTitle(R.string.update_title).setMessage(text)
            .setNegativeButton(android.R.string.cancel, (d, w) -> cancel()).setOnCancelListener(d -> cancel()).create();
        dialog.show();
    }
    private void dismiss() { if (dialog != null) { dialog.dismiss(); dialog = null; } }
    private void message(int text) {
        if (disposed) return;
        dialog = new AlertDialog.Builder(activity).setTitle(R.string.update_title).setMessage(text)
            .setPositiveButton(android.R.string.ok, null).create(); dialog.show();
    }
    private void failed() { main.post(() -> { if (!disposed && !cancelled) { busy = false; dismiss(); message(R.string.update_failed); } }); }
    private void cancel() {
        cancelled = true;
        HttpsURLConnection active = connection;
        if (active != null) workerDisconnect(active);
        // Keep busy until the worker's finally block; never overlap writers after cancellation.
    }
    private static void workerDisconnect(HttpsURLConnection active) {
        Thread closer = new Thread(active::disconnect, "forge-update-cancel"); closer.start();
    }
    void dispose() { disposed = true; cancel(); dismiss(); worker.shutdownNow(); }
}
