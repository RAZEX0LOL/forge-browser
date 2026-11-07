package org.forgebrowser.mobile;

import android.Manifest;
import android.app.AlertDialog;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class BrowserPermissionsNativeTest {
    private static final class FakeSystem implements BrowserPermissions.SystemAccess {
        final Set<String> granted = new HashSet<>();
        final CountDownLatch requested = new CountDownLatch(1);
        int code, requests;
        public boolean granted(String permission) { return granted.contains(permission); }
        public void request(String[] permissions, int code) { this.code = code; requests++; requested.countDown(); }
    }

    private void awaitFocus(ActivityScenario<BrowserActivity> scenario, BrowserPermissions permissions) throws Exception {
        CountDownLatch focused = new CountDownLatch(1);
        AtomicReference<android.view.View> target = new AtomicReference<>();
        android.view.ViewTreeObserver.OnWindowFocusChangeListener listener = value -> { if (value) focused.countDown(); };
        scenario.onActivity(activity -> {
            android.view.View view = permissions == null ? activity.getWindow().getDecorView()
                : permissions.pendingDialog().getWindow().getDecorView();
            target.set(view);
            view.getViewTreeObserver().addOnWindowFocusChangeListener(listener);
            if (view.hasWindowFocus()) focused.countDown();
        });
        try { assertTrue("Window did not receive focus", focused.await(15, TimeUnit.SECONDS)); }
        finally { scenario.onActivity(activity -> target.get().getViewTreeObserver().removeOnWindowFocusChangeListener(listener)); }
    }

    @Test public void mediaNeedsExplicitSiteConsentEvenWithSystemAccess() throws Exception {
        FakeSystem system = new FakeSystem(); system.granted.add(Manifest.permission.CAMERA);
        AtomicReference<BrowserPermissions> permissions = new AtomicReference<>();
        AtomicInteger calls = new AtomicInteger();
        CountDownLatch done = new CountDownLatch(1);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitFocus(scenario, null);
            scenario.onActivity(activity -> {
                permissions.set(new BrowserPermissions(activity, () -> false, system));
                permissions.get().requestMedia("https://example.com/private?q=secret", true, false, () -> true,
                    allowed -> { assertTrue(allowed); calls.incrementAndGet(); done.countDown(); });
                assertNotNull(permissions.get().pendingDialog());
                assertEquals(0, calls.get());
            });
            awaitFocus(scenario, permissions.get());
            scenario.onActivity(activity -> {
                permissions.get().pendingDialog().getButton(AlertDialog.BUTTON_POSITIVE).performClick();
            });
            assertTrue(done.await(15, TimeUnit.SECONDS));
            scenario.onActivity(activity -> {
                permissions.get().cancel();
                assertEquals(1, calls.get());
                assertEquals(0, system.requests);
            });
        }
    }

    @Test public void changedDocumentAndMissingOSAccessNeverGrantMedia() throws Exception {
        FakeSystem system = new FakeSystem();
        AtomicReference<BrowserPermissions> permissions = new AtomicReference<>();
        AtomicInteger rejects = new AtomicInteger();
        CountDownLatch done = new CountDownLatch(2);
        java.util.concurrent.atomic.AtomicBoolean valid = new java.util.concurrent.atomic.AtomicBoolean(true);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitFocus(scenario, null);
            scenario.onActivity(activity -> {
                permissions.set(new BrowserPermissions(activity, () -> false, system));
                permissions.get().requestMedia("https://example.com", true, false, valid::get,
                    allowed -> { assertFalse(allowed); rejects.incrementAndGet(); done.countDown(); });
                assertNull(permissions.get().pendingDialog());
                system.granted.add(Manifest.permission.CAMERA);
                permissions.get().requestMedia("https://example.com", true, false, valid::get,
                    allowed -> { assertFalse(allowed); rejects.incrementAndGet(); done.countDown(); });
                assertNotNull(permissions.get().pendingDialog());
            });
            awaitFocus(scenario, permissions.get());
            scenario.onActivity(activity -> {
                valid.set(false);
                permissions.get().pendingDialog().getButton(AlertDialog.BUTTON_POSITIVE).performClick();
            });
            assertTrue(done.await(15, TimeUnit.SECONDS));
            assertEquals(2, rejects.get());
        }
    }

    @Test public void systemAuthorizationResultIsBoundToOneRequestAndCanBeCancelled() throws Exception {
        FakeSystem system = new FakeSystem();
        AtomicReference<BrowserPermissions> permissions = new AtomicReference<>();
        AtomicInteger rejects = new AtomicInteger();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitFocus(scenario, null);
            scenario.onActivity(activity -> {
                permissions.set(new BrowserPermissions(activity, () -> false, system));
                permissions.get().requestSystem("https://example.com", new String[]{Manifest.permission.CAMERA}, () -> true,
                    allowed -> { assertFalse(allowed); rejects.incrementAndGet(); });
            });
            awaitFocus(scenario, permissions.get());
            scenario.onActivity(activity -> {
                permissions.get().pendingDialog().getButton(AlertDialog.BUTTON_POSITIVE).performClick();
            });
            assertTrue(system.requested.await(15, TimeUnit.SECONDS));
            scenario.onActivity(activity -> {
                assertEquals(1, system.requests);
                permissions.get().cancel();
                system.granted.add(Manifest.permission.CAMERA);
                assertFalse(permissions.get().onSystemResult(system.code));
                assertEquals(1, rejects.get());
            });
        }
    }

    @Test public void systemApprovalIsNotInferredFromCallbackWithoutActualOSGrant() throws Exception {
        FakeSystem system = new FakeSystem();
        AtomicReference<BrowserPermissions> permissions = new AtomicReference<>();
        AtomicInteger rejects = new AtomicInteger();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitFocus(scenario, null);
            scenario.onActivity(activity -> {
                permissions.set(new BrowserPermissions(activity, () -> false, system));
                permissions.get().requestSystem("https://example.com", new String[]{Manifest.permission.CAMERA}, () -> true,
                    allowed -> { assertFalse(allowed); rejects.incrementAndGet(); });
            });
            awaitFocus(scenario, permissions.get());
            scenario.onActivity(activity -> permissions.get().pendingDialog().getButton(AlertDialog.BUTTON_POSITIVE).performClick());
            assertTrue(system.requested.await(15, TimeUnit.SECONDS));
            awaitFocus(scenario, null);
            scenario.onActivity(activity -> {
                assertFalse(permissions.get().onSystemResult(system.code + 1));
                assertTrue(permissions.get().onSystemResult(system.code));
                permissions.get().onWindowFocus();
                assertEquals(1, rejects.get());
            });
        }
    }

    @Test public void actualEngineDelegateRejectsUnsupportedContentAndUnverifiedMedia() throws Exception {
        CountDownLatch denied = new CountDownLatch(1);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                FakeSystem system = new FakeSystem();
                AtomicInteger earlyRejects = new AtomicInteger();
                BrowserPermissions blocked = new BrowserPermissions(activity, () -> true, system);
                blocked.requestSystem("https://example.com", new String[]{Manifest.permission.CAMERA}, () -> true,
                    allowed -> { assertFalse(allowed); earlyRejects.incrementAndGet(); });
                BrowserPermissions foreground = new BrowserPermissions(activity, () -> false, system);
                foreground.requestSystem("https://example.com", new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, () -> true,
                    allowed -> { assertFalse(allowed); earlyRejects.incrementAndGet(); });
                assertEquals(2, earlyRejects.get());
                assertEquals(0, system.requests);
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                GeckoSession.PermissionDelegate delegate = view.getSession().getPermissionDelegate();
                assertNotNull(delegate);
                delegate.onContentPermissionRequest(view.getSession(), new GeckoSession.PermissionDelegate.ContentPermission() {})
                    .accept(value -> { assertEquals(GeckoSession.PermissionDelegate.ContentPermission.VALUE_DENY, value.intValue()); denied.countDown(); });
                AtomicInteger rejects = new AtomicInteger();
                delegate.onMediaPermissionRequest(view.getSession(), "https://example.com", null, null,
                    new GeckoSession.PermissionDelegate.MediaCallback() { @Override public void reject() { rejects.incrementAndGet(); } });
                assertEquals(1, rejects.get());
            });
            assertTrue(denied.await(15, TimeUnit.SECONDS));
        }
    }
}
