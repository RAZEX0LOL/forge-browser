package org.forgebrowser.mobile;

import android.app.AlertDialog;
import android.content.Context;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.file.Files;
import java.util.Collections;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserSiteDataTest {
    private File file;
    private byte[] previous;

    @Before public void prepare() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        file = new File(context.getNoBackupFilesDir(), "session-v1.json");
        previous = file.exists() ? Files.readAllBytes(file.toPath()) : null;
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(new BrowserTabs());
    }

    @After public void restore() throws Exception {
        if (previous == null) Files.deleteIfExists(file.toPath()); else Files.write(file.toPath(), previous);
    }

    @Test public void cancellingConfirmationDoesNotCallEngineOrCloseTabs() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                GeckoSession original = view.getSession();
                activity.siteDataClearer = flags -> { throw new AssertionError("Clear called before confirmation"); };
                AlertDialog confirmation = activity.requestClearSiteData();
                assertNotNull(confirmation);
                confirmation.getButton(AlertDialog.BUTTON_NEGATIVE).performClick();
                assertSame(original, view.getSession());
                assertTrue(original.isOpen());
                assertFalse(activity.isClearingSiteData());
            });
        }
    }

    @Test public void nativeClearingClosesEnginesAndPreservesOnlyRegularSnapshot() throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<Boolean> success = new AtomicReference<>();
        AtomicReference<String> regular = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                try {
                    GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                    GeckoSession old = view.getSession();
                    GeckoSession.NavigationDelegate staleDelegate = old.getNavigationDelegate();
                    staleDelegate.onLocationChange(old, "https://example.invalid/saved-clear-tab", Collections.emptyList(), false);
                    regular.set(activity.tabsSnapshot().encode());
                    activity.setPrivateBrowsing(true);
                    GeckoSession privatePage = view.getSession();
                    BrowserActivity.SiteDataClearer nativeClearer = activity.siteDataClearer;
                    activity.siteDataClearer = flags -> {
                        assertEquals(55L, flags);
                        assertFalse(old.isOpen());
                        assertFalse(privatePage.isOpen());
                        assertNull(view.getSession());
                        assertFalse(activity.addTab());
                        staleDelegate.onLocationChange(old, "https://example.invalid/stale-write", Collections.emptyList(), false);
                        return nativeClearer.clear(flags);
                    };
                    activity.clearSiteDataConfirmed(value -> { success.set(value); done.countDown(); });
                } catch (Exception error) { throw new AssertionError(error); }
            });
            assertTrue("Native storage clearing timed out", done.await(60, TimeUnit.SECONDS));
            assertEquals(Boolean.TRUE, success.get());
            scenario.onActivity(activity -> {
                try {
                    assertFalse(activity.isClearingSiteData());
                    assertFalse(activity.isPrivateBrowsing());
                    assertEquals(regular.get(), activity.tabsSnapshot().encode());
                    GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                    assertTrue(view.getSession().isOpen());
                    TextView status = activity.getWindow().getDecorView().findViewWithTag("forge-status");
                    assertEquals(activity.getString(R.string.site_data_cleared), status.getText().toString());
                } catch (Exception error) { throw new AssertionError(error); }
            });
        }
        assertEquals(regular.get(), new String(Files.readAllBytes(file.toPath()), java.nio.charset.StandardCharsets.UTF_8));
    }

    @Test public void destructiveConfirmationCallsEngineOnlyAfterPositiveAction() throws Exception {
        CountDownLatch requested = new CountDownLatch(1);
        AtomicReference<GeckoResult<Void>> pending = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                activity.siteDataClearer = flags -> {
                    GeckoResult<Void> result = new GeckoResult<>();
                    pending.set(result);
                    requested.countDown();
                    return result;
                };
                AlertDialog confirmation = activity.requestClearSiteData();
                assertEquals(1, requested.getCount());
                confirmation.getButton(AlertDialog.BUTTON_POSITIVE).performClick();
            });
            assertTrue(requested.await(15, TimeUnit.SECONDS));
            scenario.onActivity(activity -> pending.get().complete(null));
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                assertFalse(activity.isClearingSiteData());
                TextView status = activity.getWindow().getDecorView().findViewWithTag("forge-status");
                assertEquals(activity.getString(R.string.site_data_cleared), status.getText().toString());
            });
        }
    }

    @Test public void clearingFailureSurvivesRecreationWithoutOverwritingCorruptFile() throws Exception {
        byte[] corrupt = "not a session".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        Files.write(file.toPath(), corrupt);
        AtomicReference<GeckoResult<Void>> pending = new AtomicReference<>();
        CountDownLatch done = new CountDownLatch(1);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                GeckoResult<Void> result = new GeckoResult<>();
                pending.set(result);
                activity.siteDataClearer = flags -> result;
                activity.clearSiteDataConfirmed(success -> { assertFalse(success); done.countDown(); });
                assertTrue(activity.isClearingSiteData());
                assertFalse(activity.addTab());
                activity.setPrivateBrowsing(true);
                assertFalse(activity.isPrivateBrowsing());
            });
            scenario.recreate();
            scenario.onActivity(activity -> {
                assertTrue(activity.isClearingSiteData());
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                assertNull(view.getSession());
                pending.get().completeExceptionally(new IllegalStateException("Test failure"));
            });
            assertTrue(done.await(15, TimeUnit.SECONDS));
            scenario.onActivity(activity -> {
                assertFalse(activity.isClearingSiteData());
                TextView status = activity.getWindow().getDecorView().findViewWithTag("forge-status");
                assertTrue(status.getText().toString().contains(activity.getString(R.string.site_data_failed)));
                assertTrue(status.getText().toString().contains(activity.getString(R.string.session_unavailable)));
            });
        }
        assertArrayEquals(corrupt, Files.readAllBytes(file.toPath()));
    }
}
