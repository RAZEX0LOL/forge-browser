package org.forgebrowser.mobile;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.EnumSet;
import java.util.concurrent.CancellationException;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import static org.junit.Assert.*;

public final class BrowserUploadStagingTest {
    private Path directory;
    private BrowserUploadStaging staging;

    @Before public void prepare() throws Exception {
        directory = Files.createTempDirectory("forge-upload-staging-");
        staging = new BrowserUploadStaging(directory.resolve("cache").toFile());
    }
    @After public void clean() throws Exception {
        // Only this test's newly created directory; never user files or profiles.
        try (java.util.stream.Stream<Path> paths = Files.walk(directory)) {
            for (Path path : paths.sorted(java.util.Comparator.reverseOrder()).toArray(Path[]::new)) Files.deleteIfExists(path);
        }
    }
    private void assertNoCopies() throws Exception {
        Path cache = directory.resolve("cache");
        if (!Files.exists(cache)) return;
        try (java.util.stream.Stream<Path> files = Files.list(cache)) { assertEquals(0, files.count()); }
    }

    @Test public void completeCopyHasSafeNameExactBytesAndOwnerOnlyPermissions() throws Exception {
        byte[] data = "Selected fixture bytes".getBytes(StandardCharsets.UTF_8);
        try (BrowserUploadStaging.Lease lease = staging.stage(new ByteArrayInputStream(data), "../../invoice.pdf", data.length, () -> false)) {
            assertEquals("invoice.pdf", lease.file.getName());
            assertEquals(data.length, lease.bytes);
            assertArrayEquals(data, Files.readAllBytes(lease.file.toPath()));
            assertTrue(lease.file.getCanonicalPath().startsWith(directory.resolve("cache").toFile().getCanonicalPath() + File.separator));
            assertEquals(EnumSet.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE), Files.getPosixFilePermissions(lease.file.toPath()));
        }
        assertNoCopies();
    }
    @Test public void closeIsIdempotentAndReleasesOnlyItsOwnCopy() throws Exception {
        BrowserUploadStaging.Lease first = staging.stage(new ByteArrayInputStream(new byte[]{1}), "same.txt", -1, () -> false);
        BrowserUploadStaging.Lease second = staging.stage(new ByteArrayInputStream(new byte[]{2}), "same.txt", -1, () -> false);
        assertNotEquals(first.file, second.file);
        first.close(); first.close();
        assertTrue(second.file.isFile()); assertArrayEquals(new byte[]{2}, Files.readAllBytes(second.file.toPath()));
        second.close(); assertNoCopies();
    }
    @Test public void metadataCannotBypassTheHardStreamingLimit() throws Exception {
        AtomicBoolean closed = new AtomicBoolean();
        InputStream oversized = new InputStream() {
            long left = BrowserUploadStaging.MAXIMUM_BYTES + 1;
            @Override public int read() { return left-- > 0 ? 0 : -1; }
            @Override public int read(byte[] data, int offset, int count) {
                if (left <= 0) return -1;
                int copied = (int)Math.min(count, left); java.util.Arrays.fill(data, offset, offset + copied, (byte)0);
                left -= copied; return copied;
            }
            @Override public void close() { closed.set(true); }
        };
        assertThrows(IOException.class, () -> staging.stage(oversized, "large.bin", -1, () -> false));
        assertTrue(closed.get()); assertNoCopies();
        assertEquals(32L * 1024 * 1024, BrowserUploadStaging.MAXIMUM_BYTES);
    }
    @Test public void oversizeMetadataRejectsWithoutReadingAndClosesInput() throws Exception {
        AtomicBoolean closed = new AtomicBoolean();
        InputStream input = new InputStream() {
            @Override public int read() { throw new AssertionError("Oversize source was read"); }
            @Override public void close() { closed.set(true); }
        };
        assertThrows(IOException.class, () -> staging.stage(input, "large.bin", BrowserUploadStaging.MAXIMUM_BYTES + 1, () -> false));
        assertTrue(closed.get()); assertNoCopies();
    }
    @Test public void cancellationDuringReadDeletesThePartialCopyAndClosesInput() throws Exception {
        AtomicBoolean cancelled = new AtomicBoolean(), closed = new AtomicBoolean();
        InputStream input = new ByteArrayInputStream(new byte[32768]) {
            @Override public synchronized int read(byte[] data, int offset, int length) {
                int read = super.read(data, offset, length); cancelled.set(true); return read;
            }
            @Override public void close() { closed.set(true); }
        };
        assertThrows(CancellationException.class, () -> staging.stage(input, "fixture.txt", -1, cancelled::get));
        assertTrue(closed.get()); assertNoCopies();
    }
    @Test public void truncatedAndMismatchedMetadataNeverReturnAFile() throws Exception {
        for (long expected : new long[]{0, 12, -2}) {
            assertThrows(IOException.class, () -> staging.stage(new ByteArrayInputStream(new byte[8]), "fixture.txt", expected, () -> false));
            assertNoCopies();
        }
    }
    @Test public void readFailuresAndNoProgressLeaveNoCopy() throws Exception {
        InputStream broken = new InputStream() { @Override public int read() throws IOException { throw new IOException("Fixture read failure"); } };
        assertThrows(IOException.class, () -> staging.stage(broken, "fixture.txt", -1, () -> false)); assertNoCopies();
        InputStream idle = new InputStream() {
            @Override public int read() { return 0; }
            @Override public int read(byte[] data, int offset, int length) { return 0; }
        };
        assertThrows(IOException.class, () -> staging.stage(idle, "fixture.txt", -1, () -> false)); assertNoCopies();
    }
    @Test public void hostileNamesCannotEscapeTheCacheOrOverwriteAnExistingFile() throws Exception {
        Path outside = directory.resolve("keep.txt"); Files.write(outside, new byte[]{9});
        for (String name : new String[]{"../../keep.txt", ".pending", "...", "CON.txt", "name\u202E.exe\u0000", "я".repeat(2000)}) {
            try (BrowserUploadStaging.Lease lease = staging.stage(new ByteArrayInputStream(new byte[]{1}), name, 1, () -> false)) {
                assertTrue(lease.file.getName().getBytes(StandardCharsets.UTF_8).length <= 160);
                assertFalse(lease.file.getName().startsWith("."));
                assertArrayEquals(new byte[]{9}, Files.readAllBytes(outside));
            }
        }
        assertNoCopies();
    }
    @Test public void emptyFilesAreValidAndPreCancelledStreamsAreClosed() throws Exception {
        try (BrowserUploadStaging.Lease lease = staging.stage(new ByteArrayInputStream(new byte[0]), null, 0, () -> false)) {
            assertEquals("upload", lease.file.getName()); assertEquals(0, lease.bytes);
        }
        AtomicBoolean closed = new AtomicBoolean();
        InputStream input = new ByteArrayInputStream(new byte[]{1}) { @Override public void close() { closed.set(true); } };
        assertThrows(CancellationException.class, () -> staging.stage(input, "fixture", -1, () -> true));
        assertTrue(closed.get()); assertNoCopies();
    }

    @Test public void startupRemovesOnlyAbandonedOwnedCopies() throws Exception {
        BrowserUploadStaging.Lease abandoned = staging.stage(new ByteArrayInputStream(new byte[]{1}), "fixture.txt", 1, () -> false);
        assertTrue(abandoned.file.exists());
        staging.clearAbandoned();
        assertFalse(abandoned.file.exists());
        assertNoCopies();
    }

    @Test public void startupPreservesUnexpectedEntriesInsteadOfRecursivelyDeleting() throws Exception {
        Path unexpected = directory.resolve("cache/keep.txt");
        Files.createDirectories(unexpected.getParent()); Files.write(unexpected, new byte[]{9});
        assertThrows(IOException.class, staging::clearAbandoned);
        assertArrayEquals(new byte[]{9}, Files.readAllBytes(unexpected));
    }

    @Test public void startupNeverFollowsSymlinksToOtherDirectories() throws Exception {
        Path outside = directory.resolve("outside"); Files.createDirectories(outside);
        Path keep = outside.resolve("keep.txt"); Files.write(keep, new byte[]{9});
        Path cache = directory.resolve("cache"); Files.createDirectories(cache);
        Files.createSymbolicLink(cache.resolve(java.util.UUID.randomUUID().toString()), outside);
        assertThrows(IOException.class, staging::clearAbandoned);
        assertArrayEquals(new byte[]{9}, Files.readAllBytes(keep));
    }
}
