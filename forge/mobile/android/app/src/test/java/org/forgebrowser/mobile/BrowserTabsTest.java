package org.forgebrowser.mobile;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONException;
import org.junit.Test;
import static org.junit.Assert.*;

public class BrowserTabsTest {
    @Test public void addSelectCloseAndRoundTrip() throws Exception {
        BrowserTabs tabs = new BrowserTabs();
        String first = tabs.selectedId();
        assertTrue(tabs.update(first, "https://example.com/path?q=hello#part", "Первый сайт"));
        String second = tabs.add().id;
        assertTrue(tabs.select(first));
        BrowserTabs restored = BrowserTabs.decode(tabs.encode());
        assertEquals(2, restored.all().size());
        assertEquals(first, restored.selectedId());
        assertEquals("https://example.com/path?q=hello#part", restored.selected().url());
        restored.close(second);
        assertEquals(first, restored.selectedId());
        restored.close(first);
        assertEquals(1, restored.all().size());
        assertEquals("about:blank", restored.selected().url());
        assertNotEquals(first, restored.selectedId());
    }

    @Test public void tabLimitAndInvalidUpdatesDoNotMutateState() throws Exception {
        BrowserTabs tabs = new BrowserTabs();
        for (int count = 1; count < BrowserTabs.MAXIMUM_TABS; count++) assertNotNull(tabs.add());
        String before = tabs.encode();
        assertNull(tabs.add());
        assertFalse(tabs.select("missing"));
        assertFalse(tabs.update(tabs.selectedId(), "javascript:alert(1)", "bad"));
        assertEquals(before, tabs.encode());
    }

    @Test public void hostileCorruptAndFutureSessionsAreRejected() throws Exception {
        JSONObject valid = new JSONObject(new BrowserTabs().encode());
        for (String url : new String[]{"javascript:alert(1)", "http://example.com", "file:///private", "https://user:pass@example.com"}) {
            JSONObject data = new JSONObject(valid.toString());
            data.getJSONArray("tabs").getJSONObject(0).put("url", url);
            reject(data.toString());
        }
        reject("not json");
        reject(new JSONObject(valid.toString()).put("schemaVersion", 2).toString());
        reject(new JSONObject(valid.toString()).put("schemaVersion", 1.5).toString());
        reject(new JSONObject(valid.toString()).put("selectedID", "missing").toString());
        reject(new JSONObject(valid.toString()).put("tabs", new JSONArray()).toString());
        JSONObject duplicate = new JSONObject(valid.toString());
        duplicate.getJSONArray("tabs").put(duplicate.getJSONArray("tabs").getJSONObject(0));
        reject(duplicate.toString());
    }

    private void reject(String data) {
        try { BrowserTabs.decode(data); fail("Invalid session accepted"); }
        catch (JSONException expected) { }
    }
}
