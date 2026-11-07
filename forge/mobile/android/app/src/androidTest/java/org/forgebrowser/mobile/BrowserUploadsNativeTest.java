package org.forgebrowser.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Instrumentation;
import android.content.ClipData;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.Before;
import org.junit.After;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoSession.PromptDelegate;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserUploadsNativeTest {
    private static final String DOCUMENT = "https://upload-fixture.invalid/";
    private java.io.File sessionFile;
    private byte[] originalSession;
    @Before public void isolateSession() throws Exception {
        java.io.File directory = InstrumentationRegistry.getInstrumentation().getTargetContext().getNoBackupFilesDir();
        sessionFile = new java.io.File(directory, "session-v1.json");
        originalSession = sessionFile.exists() ? Files.readAllBytes(sessionFile.toPath()) : null;
        new BrowserSessionStore(directory).save(new BrowserTabs());
    }
    @After public void restoreSession() throws Exception {
        if (originalSession == null) Files.deleteIfExists(sessionFile.toPath());
        else Files.write(sessionFile.toPath(), originalSession);
    }

    private static Object field(Object target, String name) {
        try { Field field = target.getClass().getDeclaredField(name); field.setAccessible(true); return field.get(target); }
        catch (ReflectiveOperationException error) { throw new AssertionError(error); }
    }
    private static PromptDelegate.FilePrompt prompt(int type, int capture) {
        try {
            Constructor<?> constructor = PromptDelegate.FilePrompt.class.getDeclaredConstructors()[0];
            constructor.setAccessible(true);
            return (PromptDelegate.FilePrompt)constructor.newInstance("fixture", "", type, capture, new String[]{"text/plain"}, null);
        } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
    }
    private static PromptDelegate.FilePrompt single() {
        return prompt(PromptDelegate.FilePrompt.Type.SINGLE, PromptDelegate.FilePrompt.Capture.NONE);
    }
    private static BrowserUploads controller(Activity activity, AtomicBoolean current) {
        return new BrowserUploads(activity, new BrowserUploads.Host() {
            @Override public boolean current(GeckoSession session, String document, long version) { return current.get(); }
            @Override public void unavailable() {}
        });
    }
    private static void awaitStorage() throws Exception {
        Field ready = BrowserUploads.class.getDeclaredField("storageReady"); ready.setAccessible(true);
        long deadline = android.os.SystemClock.elapsedRealtime() + 10_000;
        while (!ready.getBoolean(null) && android.os.SystemClock.elapsedRealtime() < deadline) Thread.sleep(10);
        assertTrue("Upload startup cleanup completed", ready.getBoolean(null));
    }
    private static int choose(BrowserUploads uploads) {
        Object pending = field(uploads, "pending");
        // Coordinator fixture, not real picker UI acceptance. Invoke the exact
        // positive action synchronously; AlertDialog posts button callbacks.
        try {
            java.lang.reflect.Method choose = BrowserUploads.class.getDeclaredMethod("choose", pending.getClass());
            choose.setAccessible(true); choose.invoke(uploads, pending);
        } catch (ReflectiveOperationException error) { throw new AssertionError(error); }
        ((AlertDialog)field(pending, "dialog")).dismiss();
        return (Integer)field(uploads, "pickerCode");
    }

    private static GeckoSession page(BrowserActivity activity) {
        return ((org.mozilla.geckoview.GeckoView)activity.getWindow().getDecorView().findViewWithTag("forge-browser")).getSession();
    }
    private static BrowserUploadStaging.Lease engineLease(BrowserActivity activity) {
        try {
            BrowserUploadStaging staging = new BrowserUploadStaging(new java.io.File(activity.getCacheDir(), "upload-copies-v1"));
            BrowserUploadStaging.Lease lease = staging.stage(new java.io.ByteArrayInputStream(new byte[]{1}), "fixture.txt", 1, () -> false);
            @SuppressWarnings("unchecked")
            Map<GeckoSession, BrowserUploadStaging.Lease> leases = (Map<GeckoSession, BrowserUploadStaging.Lease>)field(field(activity, "uploads"), "leases");
            leases.put(page(activity), lease);
            return lease;
        } catch (java.io.IOException error) { throw new AssertionError(error); }
    }

    @Test public void leavingAnAttachedTabClosesEngineBeforeRemovingItsCopy() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                GeckoSession original = page(activity); BrowserUploadStaging.Lease lease = engineLease(activity);
                assertTrue(original.isOpen()); assertTrue(lease.file.exists());
                assertTrue(activity.addTab());
                assertFalse(original.isOpen()); assertFalse(lease.file.exists());
                assertNotSame(original, page(activity));
            });
        }
    }

    @Test public void backgroundingPrivateAttachmentClosesEngineAndDeletesCopy() throws Exception {
        AtomicReference<GeckoSession> original = new AtomicReference<>();
        AtomicReference<BrowserUploadStaging.Lease> lease = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                activity.setPrivateBrowsing(true); original.set(page(activity)); lease.set(engineLease(activity));
            });
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED);
            InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
                assertFalse(original.get().isOpen()); assertFalse(lease.get().file.exists());
            });
        }
    }

    @Test public void manualNavigationRetiresAttachedEngineBeforeOpeningNewAddress() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                GeckoSession original = page(activity); BrowserUploadStaging.Lease lease = engineLease(activity);
                android.widget.EditText address = activity.getWindow().getDecorView().findViewWithTag("forge-address");
                address.setText(DOCUMENT);
                address.onEditorAction(android.view.inputmethod.EditorInfo.IME_ACTION_GO);
                assertFalse(original.isOpen()); assertFalse(lease.file.exists());
                assertNotSame(original, page(activity));
                try { assertEquals(DOCUMENT, activity.tabsSnapshot().selected().url()); }
                catch (Exception error) { throw new AssertionError(error); }
                page(activity).stop();
            });
        }
    }

    @Test public void pickerRequestsOnlyOneOpenableReadOnlyDocument() {
        Intent intent = BrowserUploads.pickerIntent();
        assertEquals(Intent.ACTION_OPEN_DOCUMENT, intent.getAction());
        assertTrue(intent.hasCategory(Intent.CATEGORY_OPENABLE));
        assertEquals("*/*", intent.getType());
        assertEquals(Intent.FLAG_GRANT_READ_URI_PERMISSION, intent.getFlags());
        assertFalse(intent.getBooleanExtra(Intent.EXTRA_ALLOW_MULTIPLE, false));
        assertNull(intent.getClipData()); assertNull(intent.getSelector());
    }
    @Test public void resultRejectsPathsAndAmbiguousMultipleSelections() {
        assertNull(BrowserUploads.selectedDocument(new Intent().setData(Uri.parse("file:///secret"))));
        assertNull(BrowserUploads.selectedDocument(new Intent().setData(Uri.parse("https://fixture.invalid/"))));
        Intent valid = new Intent().setData(UploadFixtureProvider.URI);
        assertEquals(UploadFixtureProvider.URI, BrowserUploads.selectedDocument(valid));
        valid.setClipData(ClipData.newRawUri("fixture", UploadFixtureProvider.URI));
        assertEquals(UploadFixtureProvider.URI, BrowserUploads.selectedDocument(valid));
        valid.getClipData().addItem(new ClipData.Item(Uri.parse("content://other/fixture")));
        assertNull(BrowserUploads.selectedDocument(valid));
    }
    @Test public void cameraMultipleAndFolderPromptsAreDismissed() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                BrowserUploads uploads = controller(activity, new AtomicBoolean(true));
                GeckoSession session = new GeckoSession();
                for (PromptDelegate.FilePrompt prompt : new PromptDelegate.FilePrompt[]{
                    prompt(PromptDelegate.FilePrompt.Type.SINGLE, PromptDelegate.FilePrompt.Capture.ANY),
                    prompt(PromptDelegate.FilePrompt.Type.MULTIPLE, PromptDelegate.FilePrompt.Capture.NONE),
                    prompt(PromptDelegate.FilePrompt.Type.FOLDER, PromptDelegate.FilePrompt.Capture.NONE)}) {
                    uploads.request(session, DOCUMENT, 1, prompt);
                    assertTrue(prompt.isComplete()); assertNull(field(uploads, "pending"));
                }
                uploads.destroy();
            });
        }
    }
    @Test public void cancelBackgroundAndDuplicatePromptsCompleteWithoutEngineAccess() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                BrowserUploads uploads = controller(activity, new AtomicBoolean(true));
                GeckoSession session = new GeckoSession();
                PromptDelegate.FilePrompt first = single(), second = single();
                uploads.request(session, DOCUMENT, 1, first);
                uploads.request(session, DOCUMENT, 1, second);
                assertTrue(second.isComplete()); assertFalse(first.isComplete());
                uploads.navigation(new GeckoSession());
                assertFalse("Other sessions cannot cancel this document's prompt", first.isComplete());
                uploads.pause();
                assertTrue(first.isComplete()); assertFalse(uploads.hasAccess(session));
                assertNull(field(uploads, "pending")); uploads.destroy();
            });
        }
    }

    @Test public void sameURLDocumentStartInvalidatesAnActualPagesPendingPrompt() throws Exception {
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                activity.setPrivateBrowsing(true);
                android.widget.EditText address = activity.getWindow().getDecorView().findViewWithTag("forge-address");
                address.setText(DOCUMENT);
                address.onEditorAction(android.view.inputmethod.EditorInfo.IME_ACTION_GO);
                GeckoSession session = page(activity);
                session.getProgressDelegate().onPageStart(session, DOCUMENT);
                session.getNavigationDelegate().onLocationChange(session, DOCUMENT, java.util.Collections.emptyList(), false);
                session.getProgressDelegate().onPageStop(session, true);
                Object retained = field(activity, "state");
                Map<?, ?> pages = (Map<?, ?>)field(retained, "pages");
                Object runtime;
                try { runtime = pages.get(activity.tabsSnapshot().selectedId()); }
                catch (Exception error) { throw new AssertionError(error); }
                long before = (Long)field(runtime, "permissionVersion");
                BrowserUploads uploads = (BrowserUploads)field(activity, "uploads");
                PromptDelegate.FilePrompt prompt = single();
                uploads.request(session, DOCUMENT, before, prompt);
                assertFalse(prompt.isComplete()); assertNotNull(field(uploads, "pending"));
                session.getProgressDelegate().onPageStart(session, DOCUMENT);
                assertTrue(prompt.isComplete()); assertNull(field(uploads, "pending"));
                assertTrue((Long)field(runtime, "permissionVersion") > before);
                session.stop();
            });
        }
    }
    @Test public void stalePickerResultCannotReadProviderOrGrantEngineAccess() throws Exception {
        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        Instrumentation.ActivityMonitor monitor = instrumentation.addMonitor(new IntentFilter(Intent.ACTION_OPEN_DOCUMENT),
            new Instrumentation.ActivityResult(Activity.RESULT_CANCELED, null), true);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                AtomicBoolean current = new AtomicBoolean(true);
                BrowserUploads uploads = controller(activity, current);
                GeckoSession session = new GeckoSession(); PromptDelegate.FilePrompt prompt = single();
                uploads.request(session, DOCUMENT, 1, prompt); int code = choose(uploads);
                current.set(false);
                assertTrue(uploads.result(code, Activity.RESULT_OK, new Intent().setData(UploadFixtureProvider.URI)));
                assertTrue(prompt.isComplete()); assertFalse(uploads.hasAccess(session));
                assertFalse((Boolean)field(uploads, "copying")); uploads.destroy();
            });
        } finally { instrumentation.removeMonitor(monitor); }
    }
    @Test public void selectedProviderBytesBecomePrivateCopyUntilEngineIsClosed() throws Exception {
        Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
        Instrumentation.ActivityMonitor monitor = instrumentation.addMonitor(new IntentFilter(Intent.ACTION_OPEN_DOCUMENT),
            new Instrumentation.ActivityResult(Activity.RESULT_CANCELED, null), true);
        AtomicReference<BrowserUploads> owner = new AtomicReference<>();
        AtomicReference<GeckoSession> engine = new AtomicReference<>();
        CountDownLatch completed = new CountDownLatch(1);
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            awaitStorage();
            scenario.onActivity(activity -> {
                BrowserUploads uploads = controller(activity, new AtomicBoolean(true)); owner.set(uploads);
                GeckoSession session = new GeckoSession(); engine.set(session);
                uploads.request(session, DOCUMENT, 1, single()).accept(value -> completed.countDown(), error -> completed.countDown());
                int code = choose(uploads);
                assertFalse(uploads.result(code + 1, Activity.RESULT_OK, new Intent().setData(UploadFixtureProvider.URI)));
                assertTrue(uploads.result(code, Activity.RESULT_OK, new Intent().setData(UploadFixtureProvider.URI)));
            });
            assertTrue("Provider copy completed", completed.await(15, TimeUnit.SECONDS));
            scenario.onActivity(activity -> {
                BrowserUploads uploads = owner.get(); GeckoSession session = engine.get();
                assertTrue(uploads.hasAccess(session));
                Map<?, ?> leases = (Map<?, ?>)field(uploads, "leases");
                BrowserUploadStaging.Lease lease = (BrowserUploadStaging.Lease)leases.get(session);
                try {
                    assertEquals("fixture.txt", lease.file.getName());
                    assertArrayEquals(UploadFixtureProvider.BYTES, Files.readAllBytes(lease.file.toPath()));
                    assertEquals(0600, android.system.Os.stat(lease.file.getPath()).st_mode & 0777);
                } catch (Exception error) { throw new AssertionError(error); }
                // This controller fixture has no open engine. Activity lifecycle
                // integration is tested separately; no server upload is claimed.
                assertFalse(session.isOpen()); uploads.engineClosed(session);
                assertFalse(lease.file.exists()); assertFalse(uploads.hasAccess(session)); uploads.destroy();
            });
        } finally {
            instrumentation.removeMonitor(monitor);
            instrumentation.runOnMainSync(() -> {
                if (owner.get() != null) { owner.get().engineClosed(engine.get()); owner.get().destroy(); }
            });
        }
    }
}
