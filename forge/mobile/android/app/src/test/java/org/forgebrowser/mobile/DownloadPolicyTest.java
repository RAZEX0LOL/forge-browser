package org.forgebrowser.mobile;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CancellationException;
import org.junit.Test;
import static org.junit.Assert.*;

public class DownloadPolicyTest {
    @Test public void allowsOnlyHTTPSAndSafeNames() {
        assertTrue(DownloadPolicy.allows("https://example.com/file"));
        for (String url : new String[]{"about:blank", "http://example.com", "file:///secret", "https://user:pass@example.com"})
            assertFalse(DownloadPolicy.allows(url));
        assertEquals("secret.txt", DownloadPolicy.filename("../../secret.txt"));
        assertEquals("photo.exe", DownloadPolicy.filename("photo\u202E.exe\u0000"));
        assertEquals("download", DownloadPolicy.filename("CON.txt"));
        assertEquals("download", DownloadPolicy.filename("..."));
        assertEquals("Пример.pdf", DownloadPolicy.filename("Пример.pdf"));
        assertTrue(DownloadPolicy.filename("я".repeat(200)).getBytes(StandardCharsets.UTF_8).length <= 160);
    }

    @Test public void copiesCompleteAndUnknownLengthWithoutOpeningAnything() throws Exception {
        byte[] bytes = "Forge fixture".getBytes(StandardCharsets.UTF_8);
        for (long expected : new long[]{bytes.length, -1}) {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            assertEquals(bytes.length, DownloadPolicy.copy(new ByteArrayInputStream(bytes), output, expected, () -> false, count -> {}));
            assertArrayEquals(bytes, output.toByteArray());
        }
    }

    @Test public void rejectsIncompleteOversizedAndCancelledTransfers() throws Exception {
        byte[] bytes = new byte[32];
        try {
            DownloadPolicy.copy(new ByteArrayInputStream(bytes), new ByteArrayOutputStream(), 33, () -> false, count -> {});
            fail("Truncated transfer accepted");
        } catch (IOException expected) { }
        try {
            DownloadPolicy.copy(new ByteArrayInputStream(bytes), new ByteArrayOutputStream(), DownloadPolicy.MAXIMUM_BYTES + 1, () -> false, count -> {});
            fail("Oversized transfer accepted");
        } catch (IOException expected) { }
        try {
            DownloadPolicy.copy(new ByteArrayInputStream(bytes), new ByteArrayOutputStream(), -1, () -> true, count -> {});
            fail("Cancelled transfer accepted");
        } catch (CancellationException expected) { }
    }

    @Test public void propagatesDiskFullAndNetworkErrors() throws Exception {
        OutputStream full = new OutputStream() { @Override public void write(int value) throws IOException { throw new IOException("No space"); } };
        try {
            DownloadPolicy.copy(new ByteArrayInputStream(new byte[32]), full, -1, () -> false, count -> {});
            fail("Write error ignored");
        } catch (IOException expected) { }
        java.io.InputStream broken = new java.io.InputStream() { @Override public int read() throws IOException { throw new IOException("Disconnected"); } };
        try {
            DownloadPolicy.copy(broken, new ByteArrayOutputStream(), -1, () -> false, count -> {});
            fail("Network error ignored");
        } catch (IOException expected) { }
    }
}
