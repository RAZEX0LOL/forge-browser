package org.forgebrowser.mobile;

import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.widget.EditText;
import android.widget.TextView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mozilla.geckoview.GeckoSession;
import org.mozilla.geckoview.GeckoView;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserActivityTest {
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
