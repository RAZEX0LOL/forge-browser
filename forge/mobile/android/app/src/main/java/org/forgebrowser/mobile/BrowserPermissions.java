/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.PackageManager;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;

final class BrowserPermissions {
    interface SystemAccess {
        boolean granted(String permission);
        void request(String[] permissions, int code);
    }
    private static int nextRequestCode = 1000;
    private final Activity activity;
    private final BooleanSupplier blocked;
    private final SystemAccess system;
    private Pending pending;

    private static final class Pending {
        final BooleanSupplier valid;
        final Consumer<Boolean> completion;
        AlertDialog dialog;
        String[] permissions;
        int requestCode;
        boolean waitingSystem, systemReturned;
        Pending(BooleanSupplier valid, Consumer<Boolean> completion) { this.valid = valid; this.completion = completion; }
    }

    BrowserPermissions(Activity activity, BooleanSupplier blocked) {
        this(activity, blocked, new SystemAccess() {
            public boolean granted(String permission) { return activity.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED; }
            public void request(String[] permissions, int code) { activity.requestPermissions(permissions, code); }
        });
    }

    BrowserPermissions(Activity activity, BooleanSupplier blocked, SystemAccess system) {
        this.activity = activity; this.blocked = blocked; this.system = system;
    }

    static String origin(String raw) {
        if (raw == null) return null;
        try {
            URI uri = new URI(raw);
            String host = uri.getHost();
            int port = uri.getPort();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getRawUserInfo() != null || host == null
                || port == 0 || port > 65535 || port < -1) return null;
            host = host.toLowerCase(Locale.ROOT);
            if (host.contains(":" ) && !host.startsWith("[")) host = "[" + host + "]";
            return "https://" + host + (port == -1 || port == 443 ? "" : ":" + port);
        } catch (URISyntaxException error) { return null; }
    }

    static boolean supported(String[] permissions) {
        if (permissions == null || permissions.length == 0) return false;
        for (String permission : permissions)
            if (!Manifest.permission.CAMERA.equals(permission) && !Manifest.permission.RECORD_AUDIO.equals(permission)) return false;
        return true;
    }

    private boolean available(BooleanSupplier valid) {
        return pending == null && !blocked.getAsBoolean() && !activity.isFinishing()
            && activity.hasWindowFocus() && valid.getAsBoolean();
    }

    void requestSystem(String site, String[] permissions, BooleanSupplier valid, Consumer<Boolean> completion) {
        if (origin(site) == null || !supported(permissions) || !available(valid)) { completion.accept(false); return; }
        boolean authorized = true;
        for (String permission : permissions) authorized &= system.granted(permission);
        if (authorized) { completion.accept(true); return; }
        Pending request = new Pending(valid, completion);
        request.permissions = permissions.clone();
        pending = request;
        request.dialog = new AlertDialog.Builder(activity).setTitle(R.string.device_access_title)
            .setMessage(activity.getString(R.string.device_access_message, origin(site)))
            .setNegativeButton(R.string.permission_deny, (dialog, which) -> finish(request, false))
            .setPositiveButton(R.string.permission_continue, (dialog, which) -> {
                if (!request.valid.getAsBoolean() || blocked.getAsBoolean() || nextRequestCode > 65534) { finish(request, false); return; }
                request.waitingSystem = true;
                request.requestCode = nextRequestCode++;
                try { system.request(request.permissions, request.requestCode); }
                catch (RuntimeException error) { finish(request, false); }
            }).create();
        show(request);
    }

    void requestMedia(String site, boolean camera, boolean microphone, BooleanSupplier valid, Consumer<Boolean> completion) {
        if (origin(site) == null || (!camera && !microphone) || !available(valid)
            || (camera && !system.granted(Manifest.permission.CAMERA))
            || (microphone && !system.granted(Manifest.permission.RECORD_AUDIO))) { completion.accept(false); return; }
        Pending request = new Pending(valid, completion);
        request.permissions = camera && microphone ? new String[]{Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO}
            : new String[]{camera ? Manifest.permission.CAMERA : Manifest.permission.RECORD_AUDIO};
        pending = request;
        String kind = activity.getString(camera && microphone ? R.string.permission_camera_microphone
            : camera ? R.string.permission_camera : R.string.permission_microphone);
        request.dialog = new AlertDialog.Builder(activity).setTitle(R.string.site_access_title)
            .setMessage(activity.getString(R.string.site_access_message, origin(site), kind))
            .setNegativeButton(R.string.permission_deny, (dialog, which) -> finish(request, false))
            .setPositiveButton(R.string.permission_allow, (dialog, which) -> finish(request, true)).create();
        show(request);
    }

    private void show(Pending request) {
        request.dialog.setOnDismissListener(dialog -> { if (!request.waitingSystem) finish(request, false); });
        request.dialog.setOnShowListener(dialog -> request.dialog.getButton(AlertDialog.BUTTON_NEGATIVE).requestFocus());
        request.dialog.show();
    }

    private void finish(Pending request, boolean allowed) {
        if (pending != request) return;
        boolean focused = activity.hasWindowFocus() || (request.dialog != null && request.dialog.getWindow() != null
            && request.dialog.getWindow().getDecorView().hasWindowFocus());
        boolean authorized = true;
        if (allowed) for (String permission : request.permissions) authorized &= system.granted(permission);
        pending = null;
        if (request.dialog != null) request.dialog.dismiss();
        request.completion.accept(allowed && authorized && !blocked.getAsBoolean() && request.valid.getAsBoolean() && focused);
    }

    boolean onSystemResult(int code) {
        Pending request = pending;
        if (request == null || !request.waitingSystem || request.requestCode != code) return false;
        request.systemReturned = true;
        onWindowFocus();
        return true;
    }

    void onWindowFocus() {
        Pending request = pending;
        if (request == null || !request.systemReturned || !activity.hasWindowFocus()) return;
        boolean allowed = true;
        for (String permission : request.permissions) allowed &= system.granted(permission);
        finish(request, allowed);
    }

    void cancel() { if (pending != null) finish(pending, false); }
    AlertDialog pendingDialog() { return pending == null ? null : pending.dialog; }
}
