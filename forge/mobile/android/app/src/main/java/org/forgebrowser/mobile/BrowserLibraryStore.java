/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import android.util.AtomicFile;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import org.json.JSONException;

final class BrowserLibraryStore {
    private final AtomicFile file;
    private BrowserLibrary library = new BrowserLibrary();
    private boolean available = true;

    BrowserLibraryStore(File directory) {
        file = new AtomicFile(new File(directory, "library-v1.json"));
        try (FileInputStream input = file.openRead(); ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096]; int count;
            while ((count = input.read(buffer)) != -1) {
                if (bytes.size() + count > BrowserLibrary.MAXIMUM_BYTES) throw new IOException("Library too large");
                bytes.write(buffer, 0, count);
            }
            library = BrowserLibrary.decode(bytes.toString("UTF-8"));
        } catch (FileNotFoundException error) { if (file.getBaseFile().exists()) available = false; }
        catch (IOException | JSONException error) { available = false; }
    }

    synchronized boolean isAvailable() { return available; }
    synchronized BrowserLibrary snapshot() { return library.copy(); }

    private void save(BrowserLibrary next) throws IOException, JSONException {
        if (!available) throw new IOException("Library unavailable; existing file untouched");
        FileOutputStream output = null;
        try {
            byte[] data = next.encode().getBytes(java.nio.charset.StandardCharsets.UTF_8);
            output = file.startWrite(); output.write(data); output.getFD().sync(); file.finishWrite(output);
            library = next;
        } catch (IOException | JSONException error) {
            if (output != null) file.failWrite(output);
            available = false; throw error;
        }
    }

    synchronized boolean recordVisit(String url, String title, boolean privateMode) throws IOException, JSONException {
        if (privateMode) return false;
        if (!available) throw new IOException("Library unavailable");
        BrowserLibrary next = library.copy();
        if (!next.recordVisit(url, title, false, System.currentTimeMillis())) return false;
        save(next); return true;
    }

    synchronized boolean addBookmark(String url, String title, boolean privateMode) throws IOException, JSONException {
        if (privateMode) return false;
        if (!available) throw new IOException("Library unavailable");
        BrowserLibrary next = library.copy();
        if (!next.addBookmark(url, title, false, System.currentTimeMillis())) return false;
        save(next); return true;
    }

    synchronized void remove(String id, boolean bookmark) throws IOException, JSONException {
        BrowserLibrary next = library.copy(); next.remove(id, bookmark); save(next);
    }

    synchronized void clearHistory() throws IOException, JSONException {
        BrowserLibrary next = library.copy(); next.clearHistory(); save(next);
    }
}
