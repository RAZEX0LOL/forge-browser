package org.forgebrowser.mobile;

import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.TextView;
import android.content.Context;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.file.Files;
import java.util.UUID;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.Before;
import org.junit.After;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import org.mozilla.geckoview.WebResponse;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserActivityTest {
    @Test public void realGeckoHTTPSDownloadReturnsSecureResponseStream() throws Exception {
        CountDownLatch received = new CountDownLatch(1);
        AtomicReference<WebResponse> external = new AtomicReference<>();
        AtomicReference<String> failure = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                GeckoSession.NavigationDelegate downstream = view.getSession().getNavigationDelegate();
                view.getSession().setNavigationDelegate(new GeckoSession.NavigationDelegate() {
                    @Override public org.mozilla.geckoview.GeckoResult<org.mozilla.geckoview.AllowOrDeny> onLoadRequest(
                        GeckoSession current, LoadRequest request) {
                        return downstream.onLoadRequest(current, request);
                    }
                    @Override public org.mozilla.geckoview.GeckoResult<String> onLoadError(GeckoSession current,
                        String uri, org.mozilla.geckoview.WebRequestError error) {
                        failure.set("Gecko error category=" + error.category + " code=" + error.code);
                        received.countDown();
                        return downstream.onLoadError(current, uri, error);
                    }
                });
                view.getSession().setContentDelegate(new GeckoSession.ContentDelegate() {
                    @Override public void onExternalResponse(GeckoSession session, WebResponse response) {
                        external.set(response);
                        received.countDown();
                    }
                });
                view.getSession().loadUri("https://razex.shop/forge/SHA256SUMS");
            });
            assertTrue("Native HTTPS download response timed out", received.await(120, TimeUnit.SECONDS));
            assertNull(failure.get(), failure.get());
            WebResponse response = external.get();
            assertNotNull(response);
            assertTrue(response.isSecure);
            assertTrue(DownloadPolicy.allows(response.uri));
            assertEquals(200, response.statusCode);
            java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
            response.setReadTimeoutMillis(30000);
            try (java.io.InputStream input = response.body) {
                DownloadPolicy.copy(input, bytes, -1, () -> false, count -> {});
            }
            assertEquals(1266, bytes.size());
            assertTrue(bytes.toString("UTF-8").contains("Forge"));
        } finally {
            WebResponse response = external.get();
            if (response != null && response.body != null) response.body.close();
        }
    }

    private File sessionFile;
    private byte[] previousSession;

    @Test public void tabsButtonOpensOverviewAndCloseDoesNotLoadSavedNeighbor() throws Exception {
        BrowserTabs saved = new BrowserTabs();
        String neighbor = saved.selectedId();
        saved.update(neighbor, "https://example.invalid/saved", "Saved neighbor");
        String current = saved.add().id;
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(saved);
        AtomicReference<android.app.Dialog> overview = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                activity.getWindow().getDecorView().findViewWithTag("forge-tabs").performClick();
                try {
                    java.lang.reflect.Field field = BrowserActivity.class.getDeclaredField("tabDialog");
                    field.setAccessible(true);
                    overview.set((android.app.Dialog)field.get(activity));
                } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
                assertTrue(overview.get() instanceof BrowserTabsDialog);
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                View root = overview.get().getWindow().getDecorView();
                assertNotNull(root.findViewWithTag("forge-tab-close-" + current));
                root.findViewWithTag("forge-tab-close-" + current).performClick();
                try {
                    assertEquals(neighbor, activity.tabsSnapshot().selectedId());
                    assertEquals(1, activity.tabsSnapshot().all().size());
                } catch (Exception error) { throw new AssertionError(error); }
                TextView status = activity.getWindow().getDecorView().findViewWithTag("forge-status");
                assertEquals(activity.getString(R.string.session_restored), status.getText().toString());
                root.findViewWithTag("forge-tabs-done").performClick();
                assertFalse(overview.get().isShowing());
            });
        }
    }

    @Test public void privateTabsUseNativeModeButNeverPersistAndCloseAsGroup() throws Exception {
        AtomicReference<String> regular = new AtomicReference<>();
        AtomicReference<GeckoSession> privatePage = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    activity.addTab();
                    regular.set(activity.tabsSnapshot().encode());
                    activity.setPrivateBrowsing(true);
                    GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                    privatePage.set(view.getSession());
                    assertTrue(view.getSession().getSettings().getUsePrivateMode());
                    assertTrue((activity.getWindow().getAttributes().flags
                        & android.view.WindowManager.LayoutParams.FLAG_SECURE) != 0);
                    view.getSession().getNavigationDelegate().onLocationChange(view.getSession(),
                        "https://forge-private.invalid/secret", java.util.Collections.emptyList(), false);
                    view.getSession().getContentDelegate().onTitleChange(view.getSession(), "Private secret title");
                    assertTrue(activity.addTab());
                    assertEquals(regular.get(), new BrowserSessionStore(activity.getNoBackupFilesDir()).load().encode());
                } catch (Exception error) { throw new AssertionError(error); }
            });
            scenario.recreate();
            scenario.onActivity(activity -> {
                try {
                    assertTrue(activity.isPrivateBrowsing());
                    assertEquals(2, activity.tabsSnapshot().all().size());
                    activity.closePrivateTabs();
                    assertFalse(privatePage.get().isOpen());
                    assertFalse(activity.isPrivateBrowsing());
                    assertEquals(0, activity.getWindow().getAttributes().flags
                        & android.view.WindowManager.LayoutParams.FLAG_SECURE);
                    assertEquals(regular.get(), activity.tabsSnapshot().encode());
                    activity.setPrivateBrowsing(true);
                    assertEquals(1, activity.tabsSnapshot().all().size());
                } catch (Exception error) { throw new AssertionError(error); }
            });
        }
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                assertFalse(activity.isPrivateBrowsing());
                try { assertEquals(regular.get(), activity.tabsSnapshot().encode()); }
                catch (Exception error) { throw new AssertionError(error); }
            });
        }
    }

    @Before public void prepareSessionFixture() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        sessionFile = new File(context.getNoBackupFilesDir(), "session-v1.json");
        previousSession = sessionFile.exists() ? Files.readAllBytes(sessionFile.toPath()) : null;
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(new BrowserTabs());
    }

    @Test public void unchangedRegularSnapshotKeepsBytesInodeAndMtimeThroughoutPrivateLifecycle() throws Exception {
        byte[] original = Files.readAllBytes(sessionFile.toPath());
        long inode = android.system.Os.stat(sessionFile.getPath()).st_ino;
        java.nio.file.attribute.FileTime modified = Files.getLastModifiedTime(sessionFile.toPath());
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                activity.setPrivateBrowsing(true);
                assertTrue(activity.addTab());
                GeckoSession page = ((GeckoView)activity.getWindow().getDecorView().findViewWithTag("forge-browser")).getSession();
                page.getNavigationDelegate().onLocationChange(page, "https://private-snapshot-fixture.invalid/", java.util.Collections.emptyList(), false);
                page.getContentDelegate().onTitleChange(page, "Private fixture");
                assertTrue(activity.addTab());
            });
            assertSessionFileUnchanged(original, inode, modified);
            scenario.recreate();
            assertSessionFileUnchanged(original, inode, modified);
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED);
            assertSessionFileUnchanged(original, inode, modified);
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.RESUMED);
            scenario.onActivity(activity -> {
                assertTrue(activity.isPrivateBrowsing());
                activity.setPrivateBrowsing(false);
                assertTrue(activity.addTab());
            });
            assertFalse("Real regular edits must still be persisted", java.util.Arrays.equals(original, Files.readAllBytes(sessionFile.toPath())));
        }
    }

    private void assertSessionFileUnchanged(byte[] data, long inode, java.nio.file.attribute.FileTime modified) throws Exception {
        assertArrayEquals(data, Files.readAllBytes(sessionFile.toPath()));
        assertEquals("Private lifecycle must not replace the regular file", inode, android.system.Os.stat(sessionFile.getPath()).st_ino);
        assertEquals("Private lifecycle must not rewrite the regular file", modified, Files.getLastModifiedTime(sessionFile.toPath()));
    }

    @After public void restoreSessionFixture() throws Exception {
        if (sessionFile == null) return;
        if (previousSession != null) Files.write(sessionFile.toPath(), previousSession);
        else Files.deleteIfExists(sessionFile.toPath());
    }

    @Test public void coldActivityLaunchKeepsSavedAddressWithoutLoadingIt() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        BrowserTabs saved = new BrowserTabs();
        saved.update(saved.selectedId(), "https://example.invalid/restore-test", "Saved page");
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(saved);
        for (int launch = 0; launch < 2; launch++) {
            try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
                InstrumentationRegistry.getInstrumentation().waitForIdleSync();
                scenario.onActivity(activity -> {
                    View root = activity.getWindow().getDecorView();
                    EditText address = root.findViewWithTag("forge-address");
                    TextView status = root.findViewWithTag("forge-status");
                    assertEquals(saved.selected().url(), address.getText().toString());
                    assertEquals(activity.getString(R.string.session_restored), status.getText().toString());
                    try { assertEquals(saved.encode(), activity.tabsSnapshot().encode()); }
                    catch (Exception error) { throw new AssertionError(error); }
                });
            }
        }
    }

    @Test public void corruptSessionIsNotOverwrittenByTabEditsOrRecreation() throws Exception {
        byte[] corrupt = "not json".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        Files.write(sessionFile.toPath(), corrupt);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                TextView status = activity.getWindow().getDecorView().findViewWithTag("forge-status");
                assertTrue(status.getText().toString().contains(activity.getString(R.string.session_unavailable)));
                assertTrue(activity.addTab());
            });
            scenario.recreate();
        }
        assertArrayEquals(corrupt, Files.readAllBytes(sessionFile.toPath()));
    }

    @Test public void memoryPressureUnloadsOnlyInactiveTabAndAllowsReopening() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                GeckoSession firstPage = view.getSession();
                String firstId;
                try { firstId = activity.tabsSnapshot().selectedId(); }
                catch (Exception error) { throw new AssertionError(error); }
                assertTrue(activity.addTab());
                GeckoSession selectedPage = view.getSession();
                activity.onTrimMemory(android.content.ComponentCallbacks2.TRIM_MEMORY_RUNNING_LOW);
                assertFalse(firstPage.isOpen());
                assertTrue(selectedPage.isOpen());
                assertSame(selectedPage, view.getSession());
                activity.selectTab(firstId);
                assertNotSame(firstPage, view.getSession());
                assertTrue(view.getSession().isOpen());
            });
        }
    }

    @Test public void nativeTabsHaveIndependentSessionsAndSelectionSurvivesRecreation() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            AtomicReference<String> firstId = new AtomicReference<>();
            AtomicReference<String> secondId = new AtomicReference<>();
            AtomicReference<GeckoSession> firstPage = new AtomicReference<>();
            scenario.onActivity(activity -> {
                try { firstId.set(activity.tabsSnapshot().selectedId()); }
                catch (Exception error) { throw new AssertionError(error); }
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                firstPage.set(view.getSession());
                assertTrue(activity.addTab());
                assertNotSame(firstPage.get(), view.getSession());
                try { secondId.set(activity.tabsSnapshot().selectedId()); }
                catch (Exception error) { throw new AssertionError(error); }
                activity.selectTab(firstId.get());
                assertSame(firstPage.get(), view.getSession());
            });
            scenario.recreate();
            scenario.onActivity(activity -> {
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                assertSame(firstPage.get(), view.getSession());
                activity.closeTab(secondId.get());
                try { assertEquals(firstId.get(), activity.tabsSnapshot().selectedId()); }
                catch (Exception error) { throw new AssertionError(error); }
            });
        }
    }

    @Test public void atomicSessionStorePreservesCorruptFileAndRoundTripsTabs() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File directory = new File(context.getNoBackupFilesDir(), "session-test-" + UUID.randomUUID());
        assertTrue(directory.mkdir());
        File file = new File(directory, "session-v1.json");
        try {
            BrowserSessionStore store = new BrowserSessionStore(directory);
            assertNull(store.load());
            BrowserTabs tabs = new BrowserTabs();
            String first = tabs.selectedId();
            tabs.update(first, "https://example.com/", "Example");
            tabs.add(); tabs.select(first);
            store.save(tabs);
            assertEquals(tabs.encode(), store.load().encode());
            byte[] corrupt = "not json".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            Files.write(file.toPath(), corrupt);
            try { store.load(); fail("Corrupt session accepted"); }
            catch (org.json.JSONException expected) { }
            assertArrayEquals(corrupt, Files.readAllBytes(file.toPath()));
        } finally {
            for (String name : new String[]{"session-v1.json", "session-v1.json.bak", "session-v1.json.new"}) {
                File fixture = new File(directory, name);
                if (fixture.exists()) assertTrue(fixture.delete());
            }
            assertTrue(directory.delete());
        }
    }

    @Test public void nativeControlsRejectActiveUrlsAndKeepSessionOnRecreate() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            AtomicReference<GeckoSession> original = new AtomicReference<>();
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                GeckoView browser = root.findViewWithTag("forge-browser");
                EditText address = root.findViewWithTag("forge-address");
                TextView status = root.findViewWithTag("forge-status");
                assertNotNull(browser.getSession());
                original.set(browser.getSession());
                address.setText("javascript:alert(1)");
                address.onEditorAction(EditorInfo.IME_ACTION_GO);
                assertEquals(activity.getString(R.string.blocked), status.getText().toString());
            });
            scenario.recreate();
            scenario.onActivity(activity -> {
                GeckoView browser = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                assertSame(original.get(), browser.getSession());
                assertTrue(browser.getSession().isOpen());
            });
        }
    }

    @Test public void realGeckoEngineLoadsLocalBlankDocument() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            CountDownLatch finished = new CountDownLatch(1);
            AtomicBoolean success = new AtomicBoolean(false);
            scenario.onActivity(activity -> {
                GeckoView browser = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                GeckoSession session = browser.getSession();
                GeckoSession.ProgressDelegate downstream = session.getProgressDelegate();
                session.setProgressDelegate(new GeckoSession.ProgressDelegate() {
                    @Override public void onPageStart(GeckoSession current, String url) {
                        if (downstream != null) downstream.onPageStart(current, url);
                    }
                    @Override public void onPageStop(GeckoSession current, boolean loaded) {
                        if (downstream != null) downstream.onPageStop(current, loaded);
                        success.set(loaded); finished.countDown();
                    }
                });
                session.loadUri("about:blank");
            });
            assertTrue("Gecko load event timed out", finished.await(45, TimeUnit.SECONDS));
            assertTrue("Gecko failed to load local document", success.get());
        }
    }
}
