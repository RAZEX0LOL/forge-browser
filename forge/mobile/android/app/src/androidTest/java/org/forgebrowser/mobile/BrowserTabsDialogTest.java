package org.forgebrowser.mobile;

import android.view.View;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.ListView;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserTabsDialogTest {
    @Test public void tabLabelIsAnIndependentSelectionTargetBesideCloseButton() {
        Host host = new Host();
        String first = host.regular.selectedId(); host.regular.add();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                BrowserTabsDialog dialog = new BrowserTabsDialog(activity, host); dialog.show();
                ListView list = dialog.getWindow().getDecorView().findViewWithTag("forge-tabs-list");
                View row = list.getAdapter().getView(0, null, list);
                ((android.widget.LinearLayout)row).getChildAt(0).performClick();
                assertEquals(first, host.selected); assertEquals(first, host.regular.selectedId());
                assertFalse(dialog.isShowing());
            });
        }
    }
    private static final class Host implements BrowserTabsDialog.Host {
        final BrowserTabs regular = new BrowserTabs(), privateTabs = new BrowserTabs();
        boolean privateMode;
        String selected;
        @Override public BrowserTabs tabs() { return privateMode ? privateTabs : regular; }
        @Override public boolean isPrivate() { return privateMode; }
        @Override public void select(String id) { selected = id; tabs().select(id); }
        @Override public void close(String id) { tabs().close(id); }
        @Override public void add() { tabs().add(); }
        @Override public void changeMode(boolean value) { privateMode = value; }
        @Override public void closePrivate() { privateMode = false; }
    }

    @Test public void searchAndIndependentCloseDoNotSelectOrNavigate() {
        Host host = new Host();
        String first = host.regular.selectedId();
        host.regular.update(first, "https://example.invalid/docs", "Documentation");
        String second = host.regular.add().id;
        AtomicReference<BrowserTabsDialog> dialog = new AtomicReference<>();
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                dialog.set(new BrowserTabsDialog(activity, host)); dialog.get().show();
                EditText search = dialog.get().getWindow().getDecorView().findViewWithTag("forge-tabs-search");
                search.setText("EXAMPLE.INVALID");
            });
            InstrumentationRegistry.getInstrumentation().waitForIdleSync();
            scenario.onActivity(activity -> {
                View root = dialog.get().getWindow().getDecorView();
                ListView list = root.findViewWithTag("forge-tabs-list");
                assertEquals(1, list.getAdapter().getCount());
                assertNotNull(root.findViewWithTag("forge-tab-close-" + first));
                root.findViewWithTag("forge-tab-close-" + first).performClick();
                assertNull(host.regular.find(first));
                assertEquals(second, host.regular.selectedId());
                assertNull(host.selected);
                assertEquals(0, list.getAdapter().getCount());
                dialog.get().dismiss();
            });
        }
    }

    @Test public void privateOverviewUsesSecureWindowAndIsolatesSearchResults() {
        Host host = new Host();
        host.regular.update(host.regular.selectedId(), "https://regular.invalid", "Regular");
        host.privateTabs.update(host.privateTabs.selectedId(), "https://private.invalid", "Secret");
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                BrowserTabsDialog dialog = new BrowserTabsDialog(activity, host); dialog.show();
                View root = dialog.getWindow().getDecorView();
                EditText search = root.findViewWithTag("forge-tabs-search");
                ListView list = root.findViewWithTag("forge-tabs-list");
                search.setText("Secret");
                assertEquals(0, list.getAdapter().getCount());
                root.findViewWithTag("forge-tabs-private").performClick();
                assertEquals("", search.getText().toString());
                assertEquals(1, list.getAdapter().getCount());
                assertEquals("Secret", ((BrowserTabs.Tab)list.getAdapter().getItem(0)).title());
                assertTrue((dialog.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE) != 0);
                root.findViewWithTag("forge-tabs-regular").performClick();
                assertEquals(0, dialog.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE);
                assertEquals("Regular", ((BrowserTabs.Tab)list.getAdapter().getItem(0)).title());
                dialog.dismiss();
            });
        }
    }

    @Test public void overviewBoundDisablesAddAndLastCloseCreatesBlankTab() {
        Host host = new Host();
        while (host.regular.add() != null) {}
        try (ActivityScenario<BrowserActivity> scenario = ActivityScenario.launch(BrowserActivity.class)) {
            scenario.onActivity(activity -> {
                BrowserTabsDialog dialog = new BrowserTabsDialog(activity, host); dialog.show();
                assertFalse(dialog.getWindow().getDecorView().findViewWithTag("forge-tabs-add").isEnabled());
                ListView list = dialog.getWindow().getDecorView().findViewWithTag("forge-tabs-list");
                java.util.List<BrowserTabs.Tab> original = new java.util.ArrayList<>(host.regular.all());
                for (BrowserTabs.Tab tab : original) {
                    View row = list.getAdapter().getView(0, null, list);
                    row.findViewWithTag("forge-tab-close-" + tab.id).performClick();
                }
                assertEquals(1, host.regular.all().size());
                assertEquals("about:blank", host.regular.selected().url());
                assertTrue(dialog.getWindow().getDecorView().findViewWithTag("forge-tabs-add").isEnabled());
                dialog.dismiss();
            });
        }
    }
}
