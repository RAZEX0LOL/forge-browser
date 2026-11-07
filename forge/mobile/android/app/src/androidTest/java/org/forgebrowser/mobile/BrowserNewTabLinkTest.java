package org.forgebrowser.mobile;

import android.app.AlertDialog;
import android.content.Context;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.file.Files;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.AllowOrDeny;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserNewTabLinkTest {
    private File file;
    private byte[] previous;
    private static final String LINK = "https://new-tab-fixture.invalid/target";

    private static final class Link extends GeckoSession.ContentDelegate.ContextElement {
        Link(String url) { super("https://source-fixture.invalid/", url, "Fixture", null, null, null, "Fixture"); }
    }

    @Before public void prepare() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        file = new File(context.getNoBackupFilesDir(), "session-v1.json");
        previous = file.exists() ? Files.readAllBytes(file.toPath()) : null;
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(new BrowserTabs());
    }
    @After public void restore() throws Exception {
        if (previous == null) Files.deleteIfExists(file.toPath()); else Files.write(file.toPath(), previous);
    }
    private static GeckoSession page(BrowserActivity activity) {
        return ((GeckoView)activity.getWindow().getDecorView().findViewWithTag("forge-browser")).getSession();
    }
    private static void source(BrowserActivity activity) {
        GeckoSession page = page(activity);
        page.getNavigationDelegate().onLocationChange(page, "https://source-fixture.invalid/", Collections.emptyList(), true);
    }
    private static AlertDialog menu(BrowserActivity activity) {
        try {
            java.lang.reflect.Field field = BrowserActivity.class.getDeclaredField("tabDialog"); field.setAccessible(true);
            return (AlertDialog)field.get(activity);
        } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
    }
    private static void showLink(BrowserActivity activity, String url) {
        GeckoSession page = page(activity);
        page.getContentDelegate().onContextMenu(page, 0, 0, new Link(url));
    }

    @Test public void cancellingNativeLinkActionDoesNotCreateOrPersistTab() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> { source(activity); showLink(activity, LINK); });
            awaitDialogFocus(scenario);
            byte[] before = Files.readAllBytes(file.toPath());
            scenario.onActivity(activity -> {
                assertNotNull(menu(activity)); assertTrue(menu(activity).isShowing());
                menu(activity).getButton(AlertDialog.BUTTON_NEGATIVE).performClick();
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                try { assertEquals(1, activity.tabsSnapshot().all().size()); }
                catch (Exception error) { throw new AssertionError(error); }
            });
            assertArrayEquals(before, Files.readAllBytes(file.toPath()));
        }
    }

    @Test public void confirmedLinkCreatesSeparateRegularTab() throws Exception { checkConfirmed(false); }
    @Test public void confirmedPrivateLinkStaysPrivateAndOffDisk() throws Exception { checkConfirmed(true); }

    private void checkConfirmed(boolean privateMode) throws Exception {
        AtomicReference<GeckoSession> original = new AtomicReference<>();
        StringBuilder trace = new StringBuilder();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                if (privateMode) activity.setPrivateBrowsing(true);
            });
            awaitLocalEngineReady(scenario);
            scenario.onActivity(activity -> {
                source(activity); original.set(page(activity));
                trace.append("before-menu: ").append(state(activity)).append('\n');
                showLink(activity, LINK);
            });
            awaitDialogFocus(scenario);
            scenario.onActivity(activity -> {
                assertNotNull(menu(activity));
                if (privateMode) assertTrue((menu(activity).getWindow().getAttributes().flags
                    & android.view.WindowManager.LayoutParams.FLAG_SECURE) != 0);
                trace.append("before-click: ").append(state(activity)).append('\n');
                try { assertEquals(trace.toString(), "https://source-fixture.invalid/", activity.tabsSnapshot().selected().url()); }
                catch (Exception error) { throw new AssertionError(error); }
                menu(activity).getButton(AlertDialog.BUTTON_POSITIVE).performClick();
            });
            // AlertDialog dispatches its button listener through a Handler.
            // Assert the result only after that listener and dismissal have run.
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                trace.append("after-dispatch: ").append(state(activity)).append('\n');
                android.os.Bundle diagnostic = new android.os.Bundle();
                diagnostic.putString("forge_new_tab_trace", trace.toString());
                InstrumentationRegistry.getInstrumentation().sendStatus(2, diagnostic);
                try {
                    assertEquals(trace.toString(), 2, activity.tabsSnapshot().all().size());
                    assertEquals(LINK, activity.tabsSnapshot().selected().url());
                } catch (Exception error) { throw new AssertionError(error); }
                assertEquals(privateMode, activity.isPrivateBrowsing());
                assertNotSame(original.get(), page(activity));
                page(activity).stop();
            });
            if (privateMode) assertFalse(new String(Files.readAllBytes(file.toPath()),
                java.nio.charset.StandardCharsets.UTF_8).contains("new-tab-fixture"));
        }
    }

    private static void awaitLocalEngineReady(ActivityScenario<BrowserActivity> scenario) throws Exception {
        CountDownLatch loaded = new CountDownLatch(1);
        AtomicReference<Boolean> successful = new AtomicReference<>();
        AtomicReference<GeckoSession.ProgressDelegate> original = new AtomicReference<>();
        scenario.onActivity(activity -> {
            GeckoSession current = page(activity);
            original.set(current.getProgressDelegate());
            current.setProgressDelegate(new GeckoSession.ProgressDelegate() {
                @Override public void onPageStart(GeckoSession session, String url) { original.get().onPageStart(session, url); }
                @Override public void onProgressChange(GeckoSession session, int progress) { original.get().onProgressChange(session, progress); }
                @Override public void onSecurityChange(GeckoSession session, SecurityInformation info) { original.get().onSecurityChange(session, info); }
                @Override public void onPageStop(GeckoSession session, boolean success) {
                    original.get().onPageStop(session, success);
                    successful.set(success);
                    loaded.countDown();
                }
            });
            // Wait for a real engine lifecycle event, not main-queue idleness:
            // opening a private session can deliver its initial blank URL late.
            current.loadUri("about:blank");
        });
        assertTrue("Local Gecko fixture initialization", loaded.await(30, TimeUnit.SECONDS));
        assertEquals("Local about:blank fixture must load successfully", Boolean.TRUE, successful.get());
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        scenario.onActivity(activity -> page(activity).setProgressDelegate(original.get()));
    }

    private static void awaitDialogFocus(ActivityScenario<BrowserActivity> scenario) throws Exception {
        CountDownLatch focused = new CountDownLatch(1);
        AtomicReference<android.view.View> decor = new AtomicReference<>();
        android.view.ViewTreeObserver.OnWindowFocusChangeListener listener = hasFocus -> {
            if (hasFocus) focused.countDown();
        };
        scenario.onActivity(activity -> {
            assertNotNull(menu(activity));
            decor.set(menu(activity).getWindow().getDecorView());
            decor.get().getViewTreeObserver().addOnWindowFocusChangeListener(listener);
            if (decor.get().hasWindowFocus()) focused.countDown();
        });
        try {
            assertTrue("Native link confirmation window must gain focus before a user click", focused.await(10, TimeUnit.SECONDS));
        } finally {
            scenario.onActivity(activity -> decor.get().getViewTreeObserver().removeOnWindowFocusChangeListener(listener));
        }
    }

    private static String state(BrowserActivity activity) {
        try {
            java.lang.reflect.Field field = BrowserActivity.class.getDeclaredField("state"); field.setAccessible(true);
            Object browserState = field.get(activity);
            java.lang.reflect.Field pages = browserState.getClass().getDeclaredField("pages"); pages.setAccessible(true);
            BrowserTabs tabs = activity.tabsSnapshot();
            Object runtime = ((java.util.Map<?, ?>)pages.get(browserState)).get(tabs.selectedId());
            java.lang.reflect.Field version = runtime.getClass().getDeclaredField("permissionVersion"); version.setAccessible(true);
            java.lang.reflect.Field pending = runtime.getClass().getDeclaredField("pendingLoad"); pending.setAccessible(true);
            java.lang.reflect.Field epoch = BrowserActivity.class.getDeclaredField("linkActionVersion"); epoch.setAccessible(true);
            AlertDialog dialog = menu(activity);
            return "private=" + activity.isPrivateBrowsing() + ",url=" + tabs.selected().url()
                + ",version=" + version.get(runtime) + ",pending=" + pending.get(runtime)
                + ",epoch=" + epoch.get(activity) + ",activityFocus=" + activity.hasWindowFocus()
                + ",dialogFocus=" + (dialog != null && dialog.getWindow().getDecorView().hasWindowFocus());
        } catch (Exception error) { throw new AssertionError(error); }
    }

    @Test public void changedSourceAndUnsupportedLinkCannotCreateTab() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                source(activity); showLink(activity, "javascript:alert(1)"); assertNull(menu(activity));
                showLink(activity, LINK);
            });
            awaitDialogFocus(scenario);
            scenario.onActivity(activity -> {
                assertNotNull(menu(activity));
                GeckoSession page = page(activity);
                page.getNavigationDelegate().onLocationChange(page, "https://changed-fixture.invalid/", Collections.emptyList(), false);
                menu(activity).getButton(AlertDialog.BUTTON_POSITIVE).performClick();
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                try { assertEquals(1, activity.tabsSnapshot().all().size()); }
                catch (Exception error) { throw new AssertionError(error); }
            });
        }
    }

    @Test public void auxiliaryWindowRequestsAreDeniedEvenWithGesture() throws Exception {
        java.lang.reflect.Constructor<GeckoSession.NavigationDelegate.LoadRequest> constructor =
            GeckoSession.NavigationDelegate.LoadRequest.class.getDeclaredConstructor(String.class, String.class,
                int.class, int.class, boolean.class, boolean.class);
        constructor.setAccessible(true);
        GeckoSession.NavigationDelegate.LoadRequest request = constructor.newInstance(LINK, null, 2, 0, true, false);
        assertEquals(GeckoSession.NavigationDelegate.TARGET_WINDOW_NEW, request.target);
        AtomicReference<AllowOrDeny> result = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                GeckoSession page = page(activity);
                page.getNavigationDelegate().onLoadRequest(page, request).accept(result::set);
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            assertEquals(AllowOrDeny.DENY, result.get());
        }
    }
}
