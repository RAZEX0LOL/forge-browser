package org.forgebrowser.mobile;

import android.content.Context;
import android.view.View;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.file.Files;
import java.util.Map;
import org.junit.Before;
import org.junit.After;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import org.mozilla.geckoview.WebRequestError;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserNavigationNativeTest {
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

    @Test public void cancellingDraftRestoresSavedAddressWithoutPersistingOrLoadingDraft() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        BrowserTabs saved = new BrowserTabs();
        saved.update(saved.selectedId(), "https://saved.invalid/page", "Saved");
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(saved);
        byte[] before = Files.readAllBytes(file.toPath());
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                EditText address = root.findViewWithTag("forge-address");
                address.requestFocus();
                address.setText("https://draft.invalid/not-submitted");
                assertNotNull(root.findViewWithTag("forge-address-cancel"));
                root.findViewWithTag("forge-address-cancel").performClick();
                assertFalse(address.hasFocus());
                assertEquals(saved.selected().url(), address.getText().toString());
                try { assertEquals(saved.encode(), activity.tabsSnapshot().encode()); }
                catch (Exception error) { throw new AssertionError(error); }
            });
        }
        assertArrayEquals(before, Files.readAllBytes(file.toPath()));
    }

    @Test public void progressAndStopReflectNativeCallbacksWithoutNavigating() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                GeckoSession session = ((GeckoView)root.findViewWithTag("forge-browser")).getSession();
                try {
                    java.lang.reflect.Field stateField = BrowserActivity.class.getDeclaredField("state"); stateField.setAccessible(true);
                    Object state = stateField.get(activity);
                    java.lang.reflect.Field pagesField = state.getClass().getDeclaredField("pages"); pagesField.setAccessible(true);
                    Object page = ((Map<?, ?>)pagesField.get(state)).get(activity.tabsSnapshot().selectedId());
                    java.lang.reflect.Field navigationField = page.getClass().getDeclaredField("navigation"); navigationField.setAccessible(true);
                    ((BrowserNavigationState)navigationField.get(page)).start();
                } catch (Exception error) { throw new AssertionError(error); }
                session.getProgressDelegate().onProgressChange(session, 42);
                ProgressBar progress = root.findViewWithTag("forge-page-progress");
                assertEquals(View.VISIBLE, progress.getVisibility());
                assertEquals(42, progress.getProgress());
                root.findViewWithTag("forge-stop").performClick();
                assertEquals(View.GONE, progress.getVisibility());
                assertNotNull(root.findViewWithTag("forge-reload"));
                TextView status = root.findViewWithTag("forge-status");
                assertEquals(activity.getString(R.string.loading_stopped), status.getText().toString());
            });
        }
    }

    @Test public void nativeFailuresAreActionableAndNeverEchoSensitiveURLs() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                GeckoSession session = ((GeckoView)root.findViewWithTag("forge-browser")).getSession();
                session.getNavigationDelegate().onLoadError(session, "https://sensitive.invalid/?token=secret",
                    new WebRequestError(WebRequestError.ERROR_SECURITY_BAD_CERT, WebRequestError.ERROR_CATEGORY_SECURITY));
                TextView status = root.findViewWithTag("forge-status");
                assertEquals(View.VISIBLE, status.getVisibility());
                assertEquals(activity.getString(R.string.connection_secure_failed), status.getText().toString());
                assertFalse(status.getText().toString().contains("secret"));
                session.getNavigationDelegate().onLoadError(session, "https://sensitive.invalid/?token=secret",
                    new WebRequestError(WebRequestError.ERROR_NET_TIMEOUT, WebRequestError.ERROR_CATEGORY_NETWORK));
                assertEquals(activity.getString(R.string.connection_timed_out), status.getText().toString());
                assertNotNull(root.findViewWithTag("forge-reload"));
            });
        }
    }

    @Test public void shareIntentContainsOnlyExplicitLinkAndDoesNotPersistPrivateURL() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                assertNull(activity.makeShareIntent());
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                GeckoSession session = view.getSession();
                session.getNavigationDelegate().onLocationChange(session, "https://example.invalid/shared",
                    java.util.Collections.emptyList(), false);
                android.content.Intent share = activity.makeShareIntent();
                assertEquals(android.content.Intent.ACTION_SEND, share.getAction());
                assertEquals("text/plain", share.getType());
                assertEquals("https://example.invalid/shared", share.getStringExtra(android.content.Intent.EXTRA_TEXT));
                assertNull(share.getClipData());
                assertEquals(0, share.getFlags());
                activity.setPrivateBrowsing(true);
                GeckoSession privatePage = view.getSession();
                privatePage.getNavigationDelegate().onLocationChange(privatePage, "https://private.invalid/shared",
                    java.util.Collections.emptyList(), false);
                assertEquals("https://private.invalid/shared", activity.makeShareIntent().getStringExtra(android.content.Intent.EXTRA_TEXT));
                try {
                    assertFalse(new BrowserSessionStore(activity.getNoBackupFilesDir()).load().encode().contains("private.invalid"));
                } catch (Exception error) { throw new AssertionError(error); }
                // No chooser or external recipient is launched by this test.
            });
        }
    }

    @Test public void findQueryIsClearedOnTabChangeAndLeavingForeground() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                activity.showFindInPage();
                EditText query = root.findViewWithTag("forge-find-query");
                assertFalse(query.isSaveEnabled());
                assertEquals(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS, query.getImportantForAutofill());
                assertTrue((query.getImeOptions() & android.view.inputmethod.EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING) != 0);
                query.setText("forge-private-search-fixture");
                activity.addTab();
                assertEquals(View.GONE, root.findViewWithTag("forge-find-panel").getVisibility());
                assertEquals("", query.getText().toString());
                activity.showFindInPage();
                query.setText("forge-private-search-fixture");
            });
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED);
            scenario.onActivity(activity -> {
                View root = activity.getWindow().getDecorView();
                assertEquals(View.GONE, root.findViewWithTag("forge-find-panel").getVisibility());
                assertEquals("", ((EditText)root.findViewWithTag("forge-find-query")).getText().toString());
            });
        }
        assertFalse(new String(Files.readAllBytes(file.toPath()), java.nio.charset.StandardCharsets.UTF_8)
            .contains("forge-private-search-fixture"));
    }
}
