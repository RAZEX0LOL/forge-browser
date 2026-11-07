/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.res.AssetFileDescriptor;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.database.Cursor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.IOException;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoSession.PromptDelegate;

// UI-thread coordinator. Provider IO uses one bounded worker; provider URIs are
// never handed to Gecko. One attachment per engine lifetime bounds retained data.
final class BrowserUploads {
    private static final java.util.concurrent.atomic.AtomicInteger NEXT_PICKER = new java.util.concurrent.atomic.AtomicInteger(4200);
    interface Host {
        boolean current(GeckoSession session, String document, long version);
        void unavailable();
    }
    private final Activity activity;
    private final Host host;
    private final Handler main = new Handler(Looper.getMainLooper());
    private static final ThreadPoolExecutor WORKER = new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(1));
    private static final java.util.concurrent.atomic.AtomicBoolean IO_BUSY = new java.util.concurrent.atomic.AtomicBoolean();
    private static boolean initializationStarted;
    private static volatile boolean storageReady;
    private final Map<GeckoSession, BrowserUploadStaging.Lease> leases = new IdentityHashMap<>();
    private Request pending;
    private volatile boolean copying;
    private boolean destroyed;
    // Never reuse a request code while an old picker can still return.
    private boolean pickerOutstanding;
    private int pickerCode;

    private static final class Request {
        final GeckoSession session;
        final String document;
        final long version;
        final PromptDelegate.FilePrompt prompt;
        final GeckoResult<PromptDelegate.PromptResponse> result = new GeckoResult<>();
        volatile boolean cancelled;
        boolean picker;
        AlertDialog dialog;
        Request(GeckoSession session, String document, long version, PromptDelegate.FilePrompt prompt) {
            this.session = session; this.document = document; this.version = version; this.prompt = prompt;
        }
    }

    BrowserUploads(Activity activity, Host host) {
        this.activity = activity; this.host = host;
        if (!initializationStarted) {
            initializationStarted = true;
            File root = new File(activity.getApplicationContext().getCacheDir(), "upload-copies-v1");
            WORKER.execute(() -> {
                try { new BrowserUploadStaging(root).clearAbandoned(); storageReady = true; }
                catch (IOException | RuntimeException error) { /* Preserve unexpected entries; disable uploads. */ }
            });
        }
    }

    GeckoResult<PromptDelegate.PromptResponse> request(GeckoSession session, String document,
        long version, PromptDelegate.FilePrompt prompt) {
        if (destroyed || !storageReady || pending != null || copying || IO_BUSY.get() || pickerOutstanding || !leases.isEmpty()
            || prompt.type != PromptDelegate.FilePrompt.Type.SINGLE
            || prompt.capture != PromptDelegate.FilePrompt.Capture.NONE
            || !NavigationPolicy.allows(document) || "about:blank".equals(document)
            || !host.current(session, document, version)) {
            host.unavailable();
            return GeckoResult.fromValue(prompt.dismiss());
        }
        Request request = new Request(session, document, version, prompt);
        pending = request;
        prompt.setDelegate(new PromptDelegate.PromptInstanceDelegate() {
            @Override public void onPromptDismiss(PromptDelegate.BasePrompt ignored) { cancel(); }
            @Override public void onPromptUpdate(PromptDelegate.BasePrompt ignored) { cancel(); }
        });
        // Gecko FilePrompt supplies no requesting-frame origin. Label the
        // top-level page explicitly rather than claiming it is the frame origin.
        request.dialog = new AlertDialog.Builder(activity).setTitle(R.string.upload_title)
            .setMessage(activity.getString(R.string.upload_warning, BrowserPermissions.origin(document)))
            .setNegativeButton(android.R.string.cancel, (dialog, which) -> cancel())
            .setPositiveButton(R.string.upload_choose, (dialog, which) -> choose(request)).create();
        request.dialog.setOnCancelListener(dialog -> cancel());
        if ((activity.getWindow().getAttributes().flags & android.view.WindowManager.LayoutParams.FLAG_SECURE) != 0)
            request.dialog.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        request.dialog.setOnShowListener(dialog -> request.dialog.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
        request.dialog.show();
        request.dialog.getWindow().getDecorView().setTag("forge-upload-confirmation");
        return request.result;
    }

    private boolean valid(Request request) {
        return !destroyed && pending == request && !request.cancelled && !request.prompt.isComplete()
            && host.current(request.session, request.document, request.version);
    }

    private void choose(Request request) {
        if (!valid(request)) { cancel(); return; }
        Intent intent = pickerIntent();
        int code = NEXT_PICKER.getAndIncrement();
        if (code > 65535) { cancel(); host.unavailable(); return; }
        try {
            request.picker = true;
            pickerOutstanding = true;
            pickerCode = code;
            activity.startActivityForResult(intent, code);
        } catch (android.content.ActivityNotFoundException | SecurityException error) {
            pickerOutstanding = false;
            cancel(); host.unavailable();
        }
    }

    static Intent pickerIntent() {
        // No camera intent, folder grants, write grants or persistent grants.
        return new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType("*/*").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
    }

    boolean result(int requestCode, int resultCode, Intent data) {
        if (!pickerOutstanding || requestCode != pickerCode) return false;
        pickerOutstanding = false;
        Request request = pending;
        if (request == null || !request.picker) return true;
        request.picker = false;
        Uri uri = selectedDocument(data);
        if (resultCode != Activity.RESULT_OK || uri == null || !valid(request)) { cancel(); return true; }
        if (!IO_BUSY.compareAndSet(false, true)) { cancel(); host.unavailable(); return true; }
        copying = true;
        long deadline = android.os.SystemClock.elapsedRealtime() + 60_000;
        // A broken provider can block its one worker, but cannot create an
        // unbounded queue or cause UI-thread provider reads.
        WORKER.execute(() -> {
            BrowserUploadStaging.Lease copy = null;
            try {
                BrowserUploadStaging staging = new BrowserUploadStaging(new File(activity.getCacheDir(), "upload-copies-v1"));
                String name = "upload";
                try (Cursor cursor = activity.getContentResolver().query(uri,
                    new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst() && !cursor.isNull(0)) name = cursor.getString(0);
                }
                try (AssetFileDescriptor descriptor = activity.getContentResolver().openAssetFileDescriptor(uri, "r")) {
                    if (descriptor == null) throw new IOException("Upload source unavailable");
                    copy = staging.stage(descriptor.createInputStream(), name, descriptor.getLength(),
                        () -> request.cancelled || android.os.SystemClock.elapsedRealtime() > deadline);
                }
            } catch (IOException | RuntimeException error) { /* No provider paths or content in logs. */ }
            BrowserUploadStaging.Lease staged = copy;
            main.post(() -> finish(request, staged));
        });
        return true;
    }

    static Uri selectedDocument(Intent data) {
        Uri uri = data == null ? null : data.getData();
        if (uri == null || !"content".equals(uri.getScheme()) || uri.getAuthority() == null) return null;
        android.content.ClipData clip = data.getClipData();
        if (clip != null && (clip.getItemCount() != 1 || !uri.equals(clip.getItemAt(0).getUri())
            || clip.getItemAt(0).getIntent() != null)) return null;
        return uri;
    }

    private void finish(Request request, BrowserUploadStaging.Lease copy) {
        copying = false;
        IO_BUSY.set(false);
        if (copy == null || !valid(request)) {
            release(copy);
            if (pending == request) { cancel(); if (copy == null) host.unavailable(); }
            return;
        }
        leases.put(request.session, copy);
        pending = null;
        request.prompt.setDelegate(null);
        request.result.complete(request.prompt.confirm(activity, Uri.fromFile(copy.file)));
    }

    void pause() {
        if (pending != null && !pending.picker) cancel();
    }

    void navigation(GeckoSession session) {
        if (pending != null && pending.session == session) cancel();
    }

    void cancel() {
        Request request = pending;
        if (request == null) return;
        pending = null;
        request.cancelled = true;
        request.prompt.setDelegate(null);
        if (request.dialog != null) request.dialog.dismiss();
        if (!request.prompt.isComplete()) request.result.complete(request.prompt.dismiss());
    }

    boolean hasAccess(GeckoSession session) { return leases.containsKey(session); }

    // Caller MUST close the Gecko engine before this method. Unlinking alone
    // does not revoke open file descriptors.
    void engineClosed(GeckoSession session) {
        if (pending != null && pending.session == session) cancel();
        release(leases.remove(session));
    }

    private void release(BrowserUploadStaging.Lease lease) {
        if (lease == null) return;
        try { lease.close(); }
        catch (IOException error) { host.unavailable(); }
    }

    void destroy() {
        destroyed = true;
        cancel();
        // Leases are released only by engineClosed, never by destroying UI.
    }
}
