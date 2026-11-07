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
import java.nio.charset.StandardCharsets;
import org.json.JSONException;

public final class BrowserSessionStore {
    private final AtomicFile file;

    public BrowserSessionStore(File directory) {
        file = new AtomicFile(new File(directory, "session-v1.json"));
    }

    public BrowserTabs load() throws IOException, JSONException {
        try (FileInputStream input = file.openRead(); ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) {
                if (bytes.size() + count > BrowserTabs.MAXIMUM_BYTES) throw new IOException("Session too large");
                bytes.write(buffer, 0, count);
            }
            return BrowserTabs.decode(bytes.toString("UTF-8"));
        } catch (FileNotFoundException error) {
            if (file.getBaseFile().exists()) throw error;
            return null;
        }
    }

    public void save(BrowserTabs tabs) throws IOException, JSONException {
        byte[] data = tabs.encode().getBytes(StandardCharsets.UTF_8);
        FileOutputStream output = null;
        try {
            output = file.startWrite();
            output.write(data);
            file.finishWrite(output);
        } catch (IOException error) {
            if (output != null) file.failWrite(output);
            throw error;
        }
    }
}
