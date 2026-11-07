package org.forgebrowser.mobile;

import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.view.ViewTreeObserver;
import android.view.WindowManager;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.file.Files;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserExternalLinkNativeTest {
    private static final String URL = "https://external-fixture.invalid/path?value=fixture";
    private File file;
    private byte[] previous;
    private Context context;

    @Before public void prepare() throws Exception {
        context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        file = new File(context.getNoBackupFilesDir(), "session-v1.json");
        previous = file.exists() ? Files.readAllBytes(file.toPath()) : null;
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(new BrowserTabs());
    }
    @After public void restore() throws Exception {
        if (previous == null) Files.deleteIfExists(file.toPath()); else Files.write(file.toPath(), previous);
    }
    private Intent viewIntent(String url) { return new Intent(Intent.ACTION_VIEW, Uri.parse(url), context, BrowserActivity.class); }
    private static GeckoSession page(BrowserActivity activity) {
        return ((GeckoView)activity.getWindow().getDecorView().findViewWithTag("forge-browser")).getSession();
    }
    private static AlertDialog dialog(BrowserActivity activity) {
        try {
            java.lang.reflect.Field field = BrowserActivity.class.getDeclaredField("externalLinkDialog"); field.setAccessible(true);
            return (AlertDialog)field.get(activity);
        } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
    }
    private static void assertTabs(BrowserActivity activity, int count, String url) {
        try {
            assertEquals(count, activity.tabsSnapshot().all().size());
            if (url != null) assertEquals(url, activity.tabsSnapshot().selected().url());
        } catch (Exception error) { throw new AssertionError(error); }
    }
    private static void awaitActivityFocus(ActivityScenario<BrowserActivity> scenario) throws Exception {
        CountDownLatch focused = new CountDownLatch(1);
        AtomicReference<View> root = new AtomicReference<>();
        ViewTreeObserver.OnWindowFocusChangeListener listener = hasFocus -> { if (hasFocus) focused.countDown(); };
        scenario.onActivity(activity -> {
            root.set(activity.getWindow().getDecorView());
            root.get().getViewTreeObserver().addOnWindowFocusChangeListener(listener);
            if (activity.hasWindowFocus()) focused.countDown();
        });
        try { assertTrue("Browser window focus", focused.await(10, TimeUnit.SECONDS)); }
        finally { scenario.onActivity(activity -> root.get().getViewTreeObserver().removeOnWindowFocusChangeListener(listener)); }
    }
    private static void awaitConfirmation(ActivityScenario<BrowserActivity> scenario) throws Exception {
        CountDownLatch focused = new CountDownLatch(1);
        AtomicReference<View> root = new AtomicReference<>(), observedDialog = new AtomicReference<>();
        ViewTreeObserver.OnWindowFocusChangeListener dialogFocus = hasFocus -> { if (hasFocus) focused.countDown(); };
        AtomicReference<Runnable> inspect = new AtomicReference<>();
        ViewTreeObserver.OnWindowFocusChangeListener activityFocus = hasFocus -> root.get().post(inspect.get());
        scenario.onActivity(activity -> {
            root.set(activity.getWindow().getDecorView());
            inspect.set(() -> {
                AlertDialog confirmation = dialog(activity);
                if (confirmation == null) return;
                View decor = confirmation.getWindow().getDecorView();
                if (observedDialog.get() != decor) {
                    observedDialog.set(decor);
                    decor.getViewTreeObserver().addOnWindowFocusChangeListener(dialogFocus);
                }
                if (decor.hasWindowFocus()) focused.countDown();
            });
            root.get().getViewTreeObserver().addOnWindowFocusChangeListener(activityFocus);
            inspect.get().run();
        });
        try { assertTrue("External link confirmation must have real window focus", focused.await(10, TimeUnit.SECONDS)); }
        finally {
            scenario.onActivity(activity -> {
                root.get().getViewTreeObserver().removeOnWindowFocusChangeListener(activityFocus);
                if (observedDialog.get() != null)
                    observedDialog.get().getViewTreeObserver().removeOnWindowFocusChangeListener(dialogFocus);
            });
        }
    }
    private static void click(ActivityScenario<BrowserActivity> scenario, int button) {
        scenario.onActivity(activity -> { assertNotNull(dialog(activity)); dialog(activity).getButton(button).performClick(); });
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
    }

    @Test public void coldViewEntryDoesNotLoadOrSaveBeforeConfirmationAndCanCancel() throws Exception {
        byte[] before = Files.readAllBytes(file.toPath());
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(viewIntent(URL))) {
            awaitConfirmation(scenario);
            scenario.onActivity(activity -> {
                assertTabs(activity, 1, "about:blank");
                assertEquals(Uri.parse(URL), activity.getIntent().getData());
                assertEquals(Intent.ACTION_VIEW, activity.getIntent().getAction());
                assertEquals(activity.getComponentName(), activity.getIntent().getComponent());
                assertNull(activity.getIntent().getExtras());
                assertNull(activity.getIntent().getClipData());
                assertNull(activity.getIntent().getSelector());
                assertEquals(0, activity.getIntent().getFlags());
            });
            assertArrayEquals(before, Files.readAllBytes(file.toPath()));
            click(scenario, AlertDialog.BUTTON_NEGATIVE);
            scenario.onActivity(activity -> assertTabs(activity, 1, "about:blank"));
        }
    }
    @Test public void confirmedColdEntryCreatesANewRegularSessionAndIgnoresExtras() throws Exception {
        Intent incoming = viewIntent(URL).putExtra(Intent.EXTRA_TEXT, "https://ignored-fixture.invalid/")
            .putExtra("com.android.browser.headers", new android.os.Bundle());
        incoming.setClipData(android.content.ClipData.newPlainText("Fixture", "Ignored payload"));
        AtomicReference<GeckoSession> original = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(incoming)) {
            awaitConfirmation(scenario);
            scenario.onActivity(activity -> {
                original.set(page(activity));
                assertNull(activity.getIntent().getExtras());
                assertNull(activity.getIntent().getClipData());
            });
            click(scenario, AlertDialog.BUTTON_POSITIVE);
            scenario.onActivity(activity -> {
                assertTabs(activity, 2, URL); assertFalse(activity.isPrivateBrowsing());
                assertNotSame(original.get(), page(activity)); page(activity).stop();
            });
        }
    }
    @Test public void warmPrivateEntryIsConfirmedInPrivateGroupAndNeverSaved() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitActivityFocus(scenario);
            scenario.onActivity(activity -> { activity.setPrivateBrowsing(true); activity.onNewIntent(viewIntent(URL)); });
            awaitConfirmation(scenario);
            scenario.onActivity(activity -> {
                assertTabs(activity, 1, "about:blank");
                assertTrue((dialog(activity).getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE) != 0);
            });
            click(scenario, AlertDialog.BUTTON_POSITIVE);
            scenario.onActivity(activity -> { assertTabs(activity, 2, URL); assertTrue(activity.isPrivateBrowsing()); page(activity).stop(); });
            assertFalse(new String(Files.readAllBytes(file.toPath()), java.nio.charset.StandardCharsets.UTF_8).contains("external-fixture"));
        }
    }
    @Test public void unsupportedSchemesAndNonViewActionsCannotPromptOrNavigate() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitActivityFocus(scenario);
            scenario.onActivity(activity -> {
                for (String url : new String[]{"http://external-fixture.invalid", "javascript:alert(1)", "file:///private",
                    "https://user:secret@external-fixture.invalid"}) activity.onNewIntent(viewIntent(url));
                activity.onNewIntent(new Intent(Intent.ACTION_SEND).setData(Uri.parse(URL)));
                assertNull(dialog(activity)); assertTabs(activity, 1, "about:blank");
            });
        }
    }
    @Test public void anotherIntentCannotReplaceTheAddressBehindAnOpenConfirmation() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(viewIntent(URL))) {
            awaitConfirmation(scenario);
            scenario.onActivity(activity -> {
                AlertDialog first = dialog(activity);
                activity.onNewIntent(viewIntent("https://replacement-fixture.invalid/"));
                assertSame(first, dialog(activity));
            });
            click(scenario, AlertDialog.BUTTON_POSITIVE);
            scenario.onActivity(activity -> { assertTabs(activity, 2, URL); page(activity).stop(); });
        }
    }
    @Test public void leavingForegroundDropsPendingConfirmationWithoutReplay() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(viewIntent(URL))) {
            awaitConfirmation(scenario);
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED);
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.RESUMED);
            awaitActivityFocus(scenario);
            scenario.onActivity(activity -> { assertNull(dialog(activity)); assertTabs(activity, 1, "about:blank"); });
        }
    }
    @Test public void recreationDoesNotReplayTheOriginalViewIntent() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(viewIntent(URL))) {
            awaitConfirmation(scenario);
            scenario.recreate();
            awaitActivityFocus(scenario);
            scenario.onActivity(activity -> { assertNull(dialog(activity)); assertTabs(activity, 1, "about:blank"); });
        }
    }
    @Test public void confirmedExternalLinkRespectsTabBound() throws Exception {
        BrowserTabs saved = new BrowserTabs(); while (saved.add() != null) {}
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(saved);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(viewIntent(URL))) {
            awaitConfirmation(scenario);
            click(scenario, AlertDialog.BUTTON_POSITIVE);
            scenario.onActivity(activity -> assertTabs(activity, BrowserTabs.MAXIMUM_TABS, "about:blank"));
        }
    }
}
