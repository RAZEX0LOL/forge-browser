/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.content.Context;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.provider.DocumentsContract;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URLDecoder;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CancellationException;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import org.mozilla.geckoview.WebResponse;

final class BrowserDownloads {
    private static final java.util.Set<String> cleanedDirectories = new java.util.HashSet<>();
    enum Stage { EMPTY, CONFIRM, RECEIVING, READY, SAVE_FAILED, SAVING, SAVED, CANCELLED, FAILED }
    private final Context context;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final File directory;
    private WebResponse response;
    private File file;
    private volatile boolean cancelled;
    private volatile InputStream activeInput;
    private boolean disposed;
    long expected = -1;
    Stage stage = Stage.EMPTY;
    String name = "download";
    long received;
    Runnable listener;

    BrowserDownloads(Context context) {
        this(context, new File(context.getCacheDir(), "forge-downloads"));
    }

    BrowserDownloads(Context context, File directory) {
        this.context = context.getApplicationContext();
        this.directory = directory;
        synchronized (cleanedDirectories) {
            if (cleanedDirectories.add(directory.getAbsolutePath())) {
                File[] stale = directory.listFiles();
                if (stale != null) for (File item : stale) if (item.isFile() && item.getName().endsWith(".part")) item.delete();
            }
        }
    }

    private static String header(WebResponse response, String key) {
        for (Map.Entry<String, String> item : response.headers.entrySet())
            if (item.getKey().equalsIgnoreCase(key)) return item.getValue();
        return "";
    }

    private void notifyChanged() { if (listener != null && !disposed) listener.run(); }

    boolean offer(WebResponse value) {
        if (stage == Stage.CONFIRM || stage == Stage.RECEIVING || stage == Stage.SAVING || stage == Stage.READY
            || stage == Stage.SAVE_FAILED || !DownloadPolicy.allows(value.uri) || !value.isSecure || value.body == null
            || value.statusCode < 200 || value.statusCode >= 300 || value.statusCode == 204 || value.statusCode == 206) {
            closeLater(value.body);
            return false;
        }
        expected = -1;
        String encoding = header(value, "content-encoding");
        if (encoding.isEmpty() || encoding.equalsIgnoreCase("identity")) {
            try { expected = Long.parseLong(header(value, "content-length")); }
            catch (NumberFormatException ignored) { }
        }
        if (expected > DownloadPolicy.MAXIMUM_BYTES) { closeLater(value.body); return false; }
        discardFile();
        response = value;
        cancelled = false;
        received = 0;
        String disposition = header(value, "content-disposition");
        java.util.regex.Matcher extended = java.util.regex.Pattern.compile("(?i)filename\\*=UTF-8''([^;]+)").matcher(disposition);
        java.util.regex.Matcher plain = java.util.regex.Pattern.compile("(?i)filename=\"([^\"]*)\"|filename=([^;]+)").matcher(disposition);
        String suggested = "download";
        if (extended.find()) {
            try { suggested = URLDecoder.decode(extended.group(1).replace("+", "%2B"), "UTF-8"); }
            catch (IllegalArgumentException | java.io.UnsupportedEncodingException ignored) { }
        } else if (plain.find()) suggested = plain.group(1) != null ? plain.group(1) : plain.group(2);
        else {
            try { suggested = new java.net.URI(value.uri).getPath().replaceAll(".*/", ""); }
            catch (java.net.URISyntaxException ignored) { }
        }
        name = DownloadPolicy.filename(suggested);
        stage = Stage.CONFIRM;
        notifyChanged();
        return true;
    }

    void start() {
        if (stage != Stage.CONFIRM) return;
        WebResponse current = response;
        response = null;
        activeInput = current.body;
        current.setReadTimeoutMillis(30000);
        stage = Stage.RECEIVING;
        notifyChanged();
        worker.execute(() -> {
            boolean success = false;
            File partial = new File(directory, UUID.randomUUID() + ".part");
            try (InputStream input = current.body) {
                if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Cannot create staging directory");
                try (OutputStream output = new FileOutputStream(partial)) {
                    long[] last = {0};
                    DownloadPolicy.copy(input, output, expected, () -> cancelled, count -> {
                        if (count - last[0] < 65536 && count != expected) return;
                        last[0] = count;
                        main.post(() -> { if (!cancelled) { received = count; notifyChanged(); } });
                    });
                }
                success = !cancelled;
            } catch (IOException | RuntimeException error) { success = false; }
            activeInput = null;
            boolean complete = success;
            main.post(() -> {
                if (complete && !cancelled && !disposed) {
                    file = partial;
                    received = partial.length();
                    stage = Stage.READY;
                } else {
                    partial.delete();
                    stage = cancelled ? Stage.CANCELLED : Stage.FAILED;
                }
                notifyChanged();
            });
        });
    }

    void save(Uri destination) {
        if ((stage != Stage.READY && stage != Stage.SAVE_FAILED) || destination == null) return;
        File source = file;
        stage = Stage.SAVING;
        cancelled = false;
        notifyChanged();
        worker.execute(() -> {
            boolean success = false;
            try (InputStream input = new java.io.FileInputStream(source);
                 OutputStream output = context.getContentResolver().openOutputStream(destination, "w")) {
                if (output == null) throw new IOException("Destination unavailable");
                activeInput = input;
                DownloadPolicy.copy(input, output, source.length(), () -> cancelled, count -> { });
                success = !cancelled;
            } catch (IOException | RuntimeException error) { success = false; }
            activeInput = null;
            boolean complete = success;
            if (!complete) {
                try { DocumentsContract.deleteDocument(context.getContentResolver(), destination); }
                catch (Exception ignored) { }
            }
            main.post(() -> {
                if (complete && !cancelled) { discardFile(); stage = Stage.SAVED; }
                else if (cancelled) { discardFile(); stage = Stage.CANCELLED; }
                else stage = Stage.SAVE_FAILED;
                notifyChanged();
            });
        });
    }

    void cancel() {
        if (stage == Stage.SAVED || stage == Stage.CANCELLED || stage == Stage.FAILED) {
            stage = Stage.EMPTY;
            notifyChanged();
            return;
        }
        if (stage == Stage.RECEIVING || stage == Stage.SAVING) {
            cancelled = true;
            InputStream input = activeInput;
            new Thread(() -> close(input), "forge-download-cancel").start();
            return;
        }
        if (response != null) { closeLater(response.body); response = null; }
        discardFile();
        stage = Stage.CANCELLED;
        notifyChanged();
    }

    void dispose() {
        disposed = true;
        listener = null;
        cancel();
        worker.shutdown();
    }

    private void discardFile() { if (file != null) { file.delete(); file = null; } }
    private static void close(InputStream input) { if (input != null) try { input.close(); } catch (IOException ignored) { } }
    private void closeLater(InputStream input) { worker.execute(() -> close(input)); }
}
