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

final class BrowserLibrary {
    static final int MAXIMUM_HISTORY = 500, MAXIMUM_BOOKMARKS = 200, MAXIMUM_BYTES = 8 * 1024 * 1024;
    static final class Entry {
        final String id, url, title;
        final long updatedAt;
        Entry(String id, String url, String title, long updatedAt) {
            this.id = id; this.url = url; this.title = title; this.updatedAt = updatedAt;
        }
    }
    private final ArrayList<Entry> bookmarks = new ArrayList<>(), history = new ArrayList<>();
    List<Entry> bookmarks() { return Collections.unmodifiableList(new ArrayList<>(bookmarks)); }
    List<Entry> history() { return Collections.unmodifiableList(new ArrayList<>(history)); }
    BrowserLibrary copy() {
        BrowserLibrary copy = new BrowserLibrary(); copy.bookmarks.addAll(bookmarks); copy.history.addAll(history); return copy;
    }

    private static Entry entry(String url, String title, long now, List<Entry> list) {
        String id = null;
        for (Entry old : list) if (old.url.equals(url)) { id = old.id; break; }
        if (title == null) title = "";
        int count = Math.min(160, title.codePointCount(0, title.length()));
        title = title.substring(0, title.offsetByCodePoints(0, count));
        return new Entry(id == null ? UUID.randomUUID().toString() : id, url, title, now);
    }

    boolean recordVisit(String url, String title, boolean privateMode, long now) {
        if (privateMode || now <= 0 || BrowserLinkActions.shareURL(url) == null) return false;
        Entry entry = entry(url, title, now, history);
        history.removeIf(old -> old.url.equals(url)); history.add(0, entry);
        while (history.size() > MAXIMUM_HISTORY) history.remove(history.size() - 1);
        return true;
    }

    boolean addBookmark(String url, String title, boolean privateMode, long now) {
        if (privateMode || now <= 0 || BrowserLinkActions.shareURL(url) == null) return false;
        boolean exists = false;
        for (Entry old : bookmarks) if (old.url.equals(url)) { exists = true; break; }
        if (!exists && bookmarks.size() >= MAXIMUM_BOOKMARKS) return false;
        Entry entry = entry(url, title, now, bookmarks);
        bookmarks.removeIf(old -> old.url.equals(url)); bookmarks.add(0, entry); return true;
    }

    void remove(String id, boolean bookmark) { (bookmark ? bookmarks : history).removeIf(entry -> entry.id.equals(id)); }
    void clearHistory() { history.clear(); }

    String encode() throws JSONException {
        JSONObject root = new JSONObject().put("schemaVersion", 1);
        root.put("bookmarks", encodeEntries(bookmarks)); root.put("history", encodeEntries(history));
        String data = root.toString();
        if (data.getBytes(StandardCharsets.UTF_8).length > MAXIMUM_BYTES) throw new JSONException("Library too large");
        return data;
    }

    private static JSONArray encodeEntries(List<Entry> entries) throws JSONException {
        JSONArray data = new JSONArray();
        for (Entry entry : entries) data.put(new JSONObject().put("id", entry.id).put("url", entry.url)
            .put("title", entry.title).put("updatedAt", entry.updatedAt));
        return data;
    }

    static BrowserLibrary decode(String data) throws JSONException {
        if (data.getBytes(StandardCharsets.UTF_8).length > MAXIMUM_BYTES) throw new JSONException("Library too large");
        JSONObject root = new JSONObject(data);
        if (!Integer.valueOf(1).equals(root.get("schemaVersion"))) throw new JSONException("Unsupported library schema");
        BrowserLibrary library = new BrowserLibrary();
        HashSet<String> ids = new HashSet<>();
        decodeEntries(root.getJSONArray("bookmarks"), MAXIMUM_BOOKMARKS, library.bookmarks, ids);
        decodeEntries(root.getJSONArray("history"), MAXIMUM_HISTORY, library.history, ids);
        return library;
    }

    private static void decodeEntries(JSONArray entries, int maximum, List<Entry> target, HashSet<String> ids) throws JSONException {
        if (entries.length() > maximum) throw new JSONException("Too many library entries");
        HashSet<String> urls = new HashSet<>();
        for (int index = 0; index < entries.length(); index++) {
            JSONObject item = entries.getJSONObject(index);
            String id = item.getString("id"), url = item.getString("url"), title = item.getString("title");
            try { if (!UUID.fromString(id).toString().equals(id)) throw new IllegalArgumentException(); }
            catch (IllegalArgumentException error) { throw new JSONException("Invalid library ID"); }
            long date = item.getLong("updatedAt");
            if (!ids.add(id) || !urls.add(url) || BrowserLinkActions.shareURL(url) == null
                || title.getBytes(StandardCharsets.UTF_8).length > 1024 || date <= 0) throw new JSONException("Invalid library entry");
            target.add(new Entry(id, url, title, date));
        }
    }
}
