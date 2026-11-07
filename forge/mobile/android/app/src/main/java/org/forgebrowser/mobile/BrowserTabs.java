/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public final class BrowserTabs {
    public static final int MAXIMUM_TABS = 32;
    public static final int MAXIMUM_BYTES = 512 * 1024;

    public static final class Tab {
        public final String id;
        private String url;
        private String title;

        private Tab(String id, String url, String title) {
            this.id = id;
            this.url = url;
            this.title = title;
        }

        public String url() { return url; }
        public String title() { return title; }
    }

    private final ArrayList<Tab> tabs = new ArrayList<>();
    private String selectedId;

    public BrowserTabs() { add(); }
    public List<Tab> all() { return Collections.unmodifiableList(tabs); }
    public String selectedId() { return selectedId; }
    public Tab selected() { return find(selectedId); }

    public Tab find(String id) {
        for (Tab tab : tabs) if (tab.id.equals(id)) return tab;
        return null;
    }

    public Tab add() {
        if (tabs.size() >= MAXIMUM_TABS) return null;
        Tab tab = new Tab(UUID.randomUUID().toString(), "about:blank", "");
        tabs.add(tab);
        selectedId = tab.id;
        return tab;
    }

    public boolean select(String id) {
        if (find(id) == null) return false;
        selectedId = id;
        return true;
    }

    public void close(String id) {
        Tab tab = find(id);
        if (tab == null) return;
        int index = tabs.indexOf(tab);
        tabs.remove(index);
        if (tabs.isEmpty()) { add(); return; }
        if (id.equals(selectedId)) selectedId = tabs.get(Math.min(index, tabs.size() - 1)).id;
    }

    public boolean update(String id, String url, String title) {
        Tab tab = find(id);
        if (tab == null) return false;
        if (url != null) {
            if (!NavigationPolicy.allows(url) || url.getBytes(StandardCharsets.UTF_8).length > 8192) return false;
            tab.url = url;
        }
        if (title != null) tab.title = title.substring(0, Math.min(160, title.length()));
        return true;
    }

    public String encode() throws JSONException {
        JSONObject root = new JSONObject();
        root.put("schemaVersion", 1);
        root.put("selectedID", selectedId);
        JSONArray items = new JSONArray();
        for (Tab tab : tabs) {
            JSONObject item = new JSONObject();
            item.put("id", tab.id); item.put("url", tab.url); item.put("title", tab.title);
            items.put(item);
        }
        root.put("tabs", items);
        String encoded = root.toString();
        if (encoded.getBytes(StandardCharsets.UTF_8).length > MAXIMUM_BYTES) throw new JSONException("Session too large");
        return encoded;
    }

    public static BrowserTabs decode(String encoded) throws JSONException {
        if (encoded.getBytes(StandardCharsets.UTF_8).length > MAXIMUM_BYTES) throw new JSONException("Session too large");
        JSONObject root = new JSONObject(encoded);
        if (!Integer.valueOf(1).equals(root.get("schemaVersion"))) throw new JSONException("Unsupported session version");
        JSONArray items = root.getJSONArray("tabs");
        if (items.length() < 1 || items.length() > MAXIMUM_TABS) throw new JSONException("Invalid tab count");
        BrowserTabs state = new BrowserTabs();
        state.tabs.clear();
        HashSet<String> ids = new HashSet<>();
        for (int index = 0; index < items.length(); index++) {
            JSONObject item = items.getJSONObject(index);
            String id = item.getString("id");
            String normalized;
            try {
                normalized = UUID.fromString(id).toString();
                if (!normalized.equalsIgnoreCase(id)) throw new IllegalArgumentException();
            }
            catch (IllegalArgumentException error) { throw new JSONException("Invalid tab identifier"); }
            String url = item.getString("url"), title = item.getString("title");
            if (!ids.add(normalized) || !NavigationPolicy.allows(url) || url.getBytes(StandardCharsets.UTF_8).length > 8192
                || title.getBytes(StandardCharsets.UTF_8).length > 1024) throw new JSONException("Invalid saved tab");
            state.tabs.add(new Tab(id, url, title));
        }
        if (!state.select(root.getString("selectedID"))) throw new JSONException("Missing selected tab");
        return state;
    }
}
