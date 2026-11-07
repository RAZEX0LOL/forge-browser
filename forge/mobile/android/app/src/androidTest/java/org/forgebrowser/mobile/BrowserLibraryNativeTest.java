package org.forgebrowser.mobile;

import android.app.AlertDialog;
import android.content.Context;
import android.view.View;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.File;
import java.nio.file.Files;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Before;
import org.junit.After;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import org.mozilla.geckoview.WebRequestError;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserLibraryNativeTest {
    private File directory, sessionFile;
    private byte[] previousSession;
    private java.lang.reflect.Field libraryField;
    private Object previousLibrary;
    private BrowserLibraryStore store;

    @Before public void prepare() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        directory = new File(context.getNoBackupFilesDir(), "forge-library-native-" + UUID.randomUUID());
        assertTrue(directory.mkdir()); store = new BrowserLibraryStore(directory);
        libraryField = BrowserActivity.class.getDeclaredField("libraryStore"); libraryField.setAccessible(true);
        previousLibrary = libraryField.get(null); libraryField.set(null, store);
        sessionFile = new File(context.getNoBackupFilesDir(), "session-v1.json");
        previousSession = sessionFile.exists() ? Files.readAllBytes(sessionFile.toPath()) : null;
        new BrowserSessionStore(context.getNoBackupFilesDir()).save(new BrowserTabs());
    }
    @After public void restore() throws Exception {
        if (libraryField != null) libraryField.set(null, previousLibrary);
        if (sessionFile != null) {
            if (previousSession == null) Files.deleteIfExists(sessionFile.toPath());
            else Files.write(sessionFile.toPath(), previousSession);
        }
        if (directory != null) {
            for (String name : new String[]{"library-v1.json", "library-v1.json.bak", "library-v1.json.new"})
                Files.deleteIfExists(new File(directory, name).toPath());
            Files.deleteIfExists(directory.toPath());
        }
    }

    @Test public void atomicRoundTripRejectsPrivateWritesAndClearsOnlyHistory() throws Exception {
        assertFalse(store.recordVisit("https://private.invalid", "Secret", true));
        assertFalse(new File(directory, "library-v1.json").exists());
        assertTrue(store.recordVisit("https://regular.invalid", "Visit", false));
        assertTrue(store.addBookmark("https://regular.invalid", "Bookmark", false));
        BrowserLibraryStore reopened = new BrowserLibraryStore(directory);
        assertEquals(store.snapshot().encode(), reopened.snapshot().encode());
        byte[] before = Files.readAllBytes(new File(directory, "library-v1.json").toPath());
        assertFalse(reopened.addBookmark("https://private.invalid", "Secret", true));
        assertArrayEquals(before, Files.readAllBytes(new File(directory, "library-v1.json").toPath()));
        reopened.clearHistory();
        BrowserLibraryStore cleared = new BrowserLibraryStore(directory);
        assertTrue(cleared.snapshot().history().isEmpty()); assertEquals(1, cleared.snapshot().bookmarks().size());
        cleared.remove(cleared.snapshot().bookmarks().get(0).id, true);
        assertTrue(new BrowserLibraryStore(directory).snapshot().bookmarks().isEmpty());
    }

    @Test public void corruptAndFutureFilesCannotBeOverwrittenByEdits() throws Exception {
        File file = new File(directory, "library-v1.json");
        for (String fixture : new String[]{"corrupt", "{\"schemaVersion\":2,\"history\":[],\"bookmarks\":[]}"}) {
            byte[] bytes = fixture.getBytes(java.nio.charset.StandardCharsets.UTF_8); Files.write(file.toPath(), bytes);
            BrowserLibraryStore unavailable = new BrowserLibraryStore(directory);
            assertFalse(unavailable.isAvailable());
            assertThrows(java.io.IOException.class, () -> unavailable.clearHistory());
            assertThrows(java.io.IOException.class, () -> unavailable.addBookmark("https://new.invalid", "New", false));
            assertArrayEquals(bytes, Files.readAllBytes(file.toPath()));
        }
    }

    @Test public void dialogFiltersByCollectionConfirmsClearAndKeepsPrivateWindowSecure() throws Exception {
        store.addBookmark("https://bookmark.invalid", "Bookmark", false);
        store.recordVisit("https://history.invalid", "History", false);
        AtomicReference<String> opened = new AtomicReference<>();
        AtomicReference<BrowserLibraryDialog> overview = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                BrowserLibraryDialog dialog = new BrowserLibraryDialog(activity, store, true, true, opened::set);
                overview.set(dialog); dialog.show();
                View root = dialog.getWindow().getDecorView();
                assertTrue((dialog.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE) != 0);
                EditText search = root.findViewWithTag("forge-library-search");
                ListView list = root.findViewWithTag("forge-library-list");
                search.setText("HISTORY.INVALID"); assertEquals(0, list.getAdapter().getCount());
                root.findViewWithTag("forge-library-history").performClick();
                assertEquals("", search.getText().toString()); assertEquals(1, list.getAdapter().getCount());
                root.findViewWithTag("forge-library-clear-history").performClick();
                confirmation(dialog).getButton(AlertDialog.BUTTON_NEGATIVE).performClick();
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                assertEquals(1, store.snapshot().history().size());
                BrowserLibraryDialog dialog = overview.get();
                dialog.getWindow().getDecorView().findViewWithTag("forge-library-clear-history").performClick();
                confirmation(dialog).getButton(AlertDialog.BUTTON_POSITIVE).performClick();
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                BrowserLibraryDialog dialog = overview.get();
                View root = dialog.getWindow().getDecorView();
                ListView list = root.findViewWithTag("forge-library-list");
                assertTrue(store.snapshot().history().isEmpty()); assertEquals(1, store.snapshot().bookmarks().size());
                assertNull(opened.get());
                root.findViewWithTag("forge-library-bookmarks").performClick();
                View row = list.getAdapter().getView(0, null, list);
                ((LinearLayout)row).getChildAt(0).performClick();
                assertEquals("https://bookmark.invalid", opened.get()); assertFalse(dialog.isShowing());
            });
        }
    }

    private static AlertDialog confirmation(BrowserLibraryDialog dialog) {
        try {
            java.lang.reflect.Field field = BrowserLibraryDialog.class.getDeclaredField("confirmation"); field.setAccessible(true);
            return (AlertDialog)field.get(dialog);
        } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
    }

    @Test public void completedRegularCallbacksRecordHistoryButPrivateAndFailedVisitsDoNot() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                GeckoView view = activity.getWindow().getDecorView().findViewWithTag("forge-browser");
                try {
                    visit(activity, view.getSession(), "https://regular.invalid", true);
                    assertEquals(1, store.snapshot().history().size()); assertTrue(activity.bookmarkSelected());
                    activity.setPrivateBrowsing(true);
                    visit(activity, view.getSession(), "https://private.invalid", true);
                    assertFalse(activity.bookmarkSelected());
                    assertEquals(1, store.snapshot().history().size()); assertEquals(1, store.snapshot().bookmarks().size());
                    activity.setPrivateBrowsing(false);
                    visit(activity, view.getSession(), "https://failed.invalid", false);
                    assertEquals(1, store.snapshot().history().size());
                } catch (Exception error) { throw new AssertionError(error); }
                // Injected lifecycle callbacks: no remote navigation is performed.
            });
        }
    }

    @Test public void lateInitialBlankCannotReplaceRequestedAddressOrRecordAnUnvisitedPage() {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                android.widget.EditText address = activity.getWindow().getDecorView().findViewWithTag("forge-address");
                String target = "https://requested-page-fixture.invalid/";
                address.setText(target);
                address.onEditorAction(android.view.inputmethod.EditorInfo.IME_ACTION_GO);
                GeckoSession page = ((GeckoView)activity.getWindow().getDecorView().findViewWithTag("forge-browser")).getSession();
                page.getNavigationDelegate().onLocationChange(page, "about:blank", java.util.Collections.emptyList(), false);
                page.getProgressDelegate().onPageStart(page, "about:blank");
                page.getProgressDelegate().onPageStop(page, true);
                try { assertEquals(target, activity.tabsSnapshot().selected().url()); }
                catch (Exception error) { throw new AssertionError(error); }
                assertTrue("An initial blank completion is not a successful HTTPS visit", store.snapshot().history().isEmpty());
                assertNotNull(activity.getWindow().getDecorView().findViewWithTag("forge-stop"));
                page.getProgressDelegate().onPageStart(page, target);
                page.getNavigationDelegate().onLocationChange(page, target, java.util.Collections.emptyList(), false);
                page.getProgressDelegate().onPageStop(page, true);
                assertEquals(1, store.snapshot().history().size());
                assertEquals(target, store.snapshot().history().get(0).url);
                address.setText("about:blank");
                address.onEditorAction(android.view.inputmethod.EditorInfo.IME_ACTION_GO);
                page.getNavigationDelegate().onLocationChange(page, "about:blank", java.util.Collections.emptyList(), true);
                try { assertEquals("about:blank", activity.tabsSnapshot().selected().url()); }
                catch (Exception error) { throw new AssertionError(error); }
                page.stop();
            });
        }
    }

    private static void visit(BrowserActivity activity, GeckoSession session, String url, boolean success) throws Exception {
        java.lang.reflect.Field stateField = BrowserActivity.class.getDeclaredField("state"); stateField.setAccessible(true);
        Object state = stateField.get(activity);
        java.lang.reflect.Field pagesField = state.getClass().getDeclaredField("pages"); pagesField.setAccessible(true);
        Object page = ((Map<?, ?>)pagesField.get(state)).get(activity.tabsSnapshot().selectedId());
        java.lang.reflect.Field started = page.getClass().getDeclaredField("userNavigationStarted"); started.setAccessible(true); started.setBoolean(page, true);
        session.getProgressDelegate().onPageStart(session, url);
        session.getNavigationDelegate().onLocationChange(session, url, java.util.Collections.emptyList(), false);
        session.getContentDelegate().onTitleChange(session, "Fixture");
        if (!success) session.getNavigationDelegate().onLoadError(session, url,
            new WebRequestError(WebRequestError.ERROR_NET_TIMEOUT, WebRequestError.ERROR_CATEGORY_NETWORK));
        session.getProgressDelegate().onPageStop(session, success);
    }
}
