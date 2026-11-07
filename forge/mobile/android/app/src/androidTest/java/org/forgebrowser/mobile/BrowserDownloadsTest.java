package org.forgebrowser.mobile;

import android.content.Context;
import android.net.Uri;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.mozilla.geckoview.WebResponse;
import static org.junit.Assert.*;

public class BrowserDownloadsTest {
    private BrowserDownloads downloads;
    private File root;
    private final byte[] bytes = "Forge download fixture".getBytes(java.nio.charset.StandardCharsets.UTF_8);

    private void main(Runnable action) { InstrumentationRegistry.getInstrumentation().runOnMainSync(action); }

    @Before public void prepare() {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        root = new File(context.getCacheDir(), "download-test-" + UUID.randomUUID());
        main(() -> downloads = new BrowserDownloads(context, root));
    }

    @After public void cleanup() {
        main(() -> downloads.dispose());
        File[] files = root.listFiles();
        if (files != null) for (File file : files) file.delete();
        root.delete();
    }

    private WebResponse response(InputStream input, long length) {
        return new WebResponse.Builder("https://example.invalid/file").statusCode(200).isSecure(true)
            .header("Content-Length", Long.toString(length)).header("Content-Disposition", "attachment; filename=\"../../fixture.txt\"")
            .body(input).build();
    }

    private void await(BrowserDownloads.Stage expected) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(15);
        AtomicReference<BrowserDownloads.Stage> actual = new AtomicReference<>();
        do {
            main(() -> actual.set(downloads.stage));
            if (actual.get() == expected) return;
            Thread.sleep(25);
        } while (System.nanoTime() < deadline);
        assertEquals(expected, actual.get());
    }

    @Test public void stagesThenExportsAndHandlesDuplicateNames() throws Exception {
        for (int index = 0; index < 2; index++) {
            main(() -> {
                assertTrue(downloads.offer(response(new ByteArrayInputStream(bytes), bytes.length)));
                assertEquals(BrowserDownloads.Stage.CONFIRM, downloads.stage);
                assertEquals("fixture.txt", downloads.name);
                downloads.start();
            });
            await(BrowserDownloads.Stage.READY);
            main(() -> {
                Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
                BrowserDownloads another = new BrowserDownloads(context, root);
                another.dispose();
            });
            File destination = new File(root, "export-" + index + ".txt");
            main(() -> downloads.save(Uri.fromFile(destination)));
            await(BrowserDownloads.Stage.SAVED);
            assertArrayEquals(bytes, Files.readAllBytes(destination.toPath()));
        }
    }

    @Test public void failedExportKeepsStagedFileForExplicitRetry() throws Exception {
        main(() -> { assertTrue(downloads.offer(response(new ByteArrayInputStream(bytes), bytes.length))); downloads.start(); });
        await(BrowserDownloads.Stage.READY);
        main(() -> downloads.save(Uri.fromFile(new File(root, "missing/fixture.txt"))));
        await(BrowserDownloads.Stage.SAVE_FAILED);
        File destination = new File(root, "retry.txt");
        main(() -> downloads.save(Uri.fromFile(destination)));
        await(BrowserDownloads.Stage.SAVED);
        assertArrayEquals(bytes, Files.readAllBytes(destination.toPath()));
    }

    @Test public void truncatedTransferFailsAndRemovesPartialFile() throws Exception {
        main(() -> { assertTrue(downloads.offer(response(new ByteArrayInputStream(bytes), bytes.length + 1))); downloads.start(); });
        await(BrowserDownloads.Stage.FAILED);
        File[] partials = root.listFiles((directory, name) -> name.endsWith(".part"));
        assertNotNull(partials);
        assertEquals(0, partials.length);
    }

    @Test public void cancelClosesBlockedStreamAndRejectsUnsafeResponses() throws Exception {
        CountDownLatch reading = new CountDownLatch(1), closed = new CountDownLatch(1);
        InputStream slow = new InputStream() {
            @Override public int read() throws java.io.IOException {
                reading.countDown();
                try { if (!closed.await(10, TimeUnit.SECONDS)) throw new java.io.IOException("Timeout"); }
                catch (InterruptedException error) { throw new java.io.IOException(error); }
                return -1;
            }
            @Override public void close() { closed.countDown(); }
        };
        main(() -> {
            assertFalse(downloads.offer(new WebResponse.Builder("http://example.invalid/file")
                .statusCode(200).body(new ByteArrayInputStream(bytes)).build()));
            assertTrue(downloads.offer(response(slow, -1)));
            downloads.start();
        });
        assertTrue(reading.await(10, TimeUnit.SECONDS));
        main(() -> downloads.cancel());
        await(BrowserDownloads.Stage.CANCELLED);
        assertEquals(0, closed.getCount());
    }
}
