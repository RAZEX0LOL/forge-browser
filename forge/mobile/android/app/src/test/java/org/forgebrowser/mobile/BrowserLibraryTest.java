package org.forgebrowser.mobile;

import java.util.UUID;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public final class BrowserLibraryTest {
    @Test public void historyIsDeduplicatedAndMovesMostRecentVisitFirst() throws Exception {
        BrowserLibrary library = new BrowserLibrary();
        library.recordVisit("https://one.invalid", "One", false, 1);
        String id = library.history().get(0).id;
        library.recordVisit("https://two.invalid", "Two", false, 2);
        library.recordVisit("https://one.invalid", "Renamed", false, 3);
        assertEquals(2, library.history().size());
        assertEquals(id, library.history().get(0).id);
        assertEquals("Renamed", library.history().get(0).title);
        assertEquals(library.encode(), BrowserLibrary.decode(library.encode()).encode());
    }

    @Test public void privateVisitsAndBookmarksNeverChangeLibrary() throws Exception {
        BrowserLibrary library = new BrowserLibrary();
        String before = library.encode();
        assertFalse(library.recordVisit("https://private.invalid", "Secret", true, 1));
        assertFalse(library.addBookmark("https://private.invalid", "Secret", true, 1));
        assertEquals(before, library.encode());
        assertFalse(library.recordVisit("about:blank", "Blank", false, 1));
        assertFalse(library.addBookmark("https://user:secret@example.invalid", "Credentials", false, 1));
    }

    @Test public void entryLimitsEvictOnlyOldHistoryAndDoNotDropBookmarks() throws Exception {
        BrowserLibrary library = new BrowserLibrary();
        for (int i = 0; i < BrowserLibrary.MAXIMUM_HISTORY + 5; i++)
            assertTrue(library.recordVisit("https://history.invalid/" + i, "Visit", false, i + 1));
        assertEquals(BrowserLibrary.MAXIMUM_HISTORY, library.history().size());
        for (int i = 0; i < BrowserLibrary.MAXIMUM_BOOKMARKS; i++)
            assertTrue(library.addBookmark("https://bookmark.invalid/" + i, "Bookmark", false, i + 1));
        assertFalse(library.addBookmark("https://bookmark.invalid/overflow", "Overflow", false, 999));
        assertEquals(BrowserLibrary.MAXIMUM_BOOKMARKS, library.bookmarks().size());
        assertTrue(library.addBookmark("https://bookmark.invalid/0", "Updated", false, 1000));
        assertEquals("Updated", library.bookmarks().get(0).title);
        library.clearHistory();
        assertTrue(library.history().isEmpty());
        assertEquals(BrowserLibrary.MAXIMUM_BOOKMARKS, library.bookmarks().size());
        BrowserLibrary.decode(library.encode());
    }

    @Test public void decodingRejectsFutureDuplicateAndHostileEntries() throws Exception {
        JSONObject future = new JSONObject(new BrowserLibrary().encode()).put("schemaVersion", 2);
        assertThrows(org.json.JSONException.class, () -> BrowserLibrary.decode(future.toString()));
        JSONObject entry = new JSONObject().put("id", UUID.randomUUID().toString())
            .put("url", "https://example.invalid").put("title", "Example").put("updatedAt", 1);
        JSONObject duplicate = new JSONObject(new BrowserLibrary().encode()).put("history", new JSONArray().put(entry).put(entry));
        assertThrows(org.json.JSONException.class, () -> BrowserLibrary.decode(duplicate.toString()));
        entry.put("url", "file:///private");
        JSONObject hostile = new JSONObject(new BrowserLibrary().encode()).put("history", new JSONArray().put(entry));
        assertThrows(org.json.JSONException.class, () -> BrowserLibrary.decode(hostile.toString()));
    }

    @Test public void snapshotsAndEntryListsCannotMutateOriginalLibrary() {
        BrowserLibrary library = new BrowserLibrary();
        library.recordVisit("https://example.invalid", "Visit", false, 1);
        BrowserLibrary copy = library.copy(); copy.clearHistory();
        assertEquals(1, library.history().size());
        assertThrows(UnsupportedOperationException.class, () -> library.history().clear());
    }

    @Test public void titleLimitDoesNotSplitUnicodeCodePoints() throws Exception {
        BrowserLibrary library = new BrowserLibrary();
        library.addBookmark("https://example.invalid", "😀".repeat(200), false, 1);
        assertEquals(160, library.bookmarks().get(0).title.codePointCount(0, library.bookmarks().get(0).title.length()));
        BrowserLibrary.decode(library.encode());
    }
}
