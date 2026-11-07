/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.util.UUID;
import java.util.concurrent.CancellationException;
import java.util.function.BooleanSupplier;

// Owns only copies under an app-private cache root. Provider paths and _data
// columns are never accepted: the caller supplies the selected document stream.
final class BrowserUploadStaging {
    static final long MAXIMUM_BYTES = 32L * 1024 * 1024;
    private final File root;

    BrowserUploadStaging(File privateCacheRoot) throws IOException {
        root = privateCacheRoot.getCanonicalFile();
    }

    // Only at process startup, before any new engine can obtain a lease. No
    // recursive traversal: preserve unexpected entries and fail closed.
    void clearAbandoned() throws IOException {
        if (!root.exists()) return;
        int count = 0;
        try (java.nio.file.DirectoryStream<java.nio.file.Path> entries = Files.newDirectoryStream(root.toPath())) {
            for (java.nio.file.Path entry : entries) {
                if (++count > 256) throw new IOException("Too many upload copies");
                String name = entry.getFileName().toString();
                try { if (!UUID.fromString(name).toString().equals(name)) throw new IllegalArgumentException(); }
                catch (IllegalArgumentException error) { throw new IOException("Unexpected upload entry", error); }
                if (!Files.isDirectory(entry, java.nio.file.LinkOption.NOFOLLOW_LINKS)) throw new IOException("Unexpected upload entry");
                int files = 0;
                try (java.nio.file.DirectoryStream<java.nio.file.Path> children = Files.newDirectoryStream(entry)) {
                    for (java.nio.file.Path child : children) {
                        if (++files > 2 || !Files.isRegularFile(child, java.nio.file.LinkOption.NOFOLLOW_LINKS))
                            throw new IOException("Unexpected upload entry");
                        Files.delete(child);
                    }
                }
                Files.delete(entry);
            }
        }
    }

    static String filename(String suggested) {
        String bounded = suggested == null ? "" : suggested.substring(0, Math.min(suggested.length(), 1024));
        String name = DownloadPolicy.filename(bounded);
        return name.equals("download") ? "upload" : name;
    }

    // Takes ownership of input even when metadata or cancellation rejects it.
    Lease stage(InputStream selected, String suggestedName, long expectedBytes, BooleanSupplier cancelled) throws IOException {
        File directory = null, partial = null, destination = null;
        try (InputStream input = selected) {
            if (input == null) throw new IOException("Upload source unavailable");
            if (expectedBytes < -1 || expectedBytes > MAXIMUM_BYTES) throw new IOException("Upload exceeds size limit");
            if (cancelled.getAsBoolean()) throw new CancellationException();
            if (!root.isDirectory() && !root.mkdirs()) throw new IOException("Upload staging unavailable");
            directory = new File(root, UUID.randomUUID().toString());
            if (!directory.mkdir()) throw new IOException("Upload staging unavailable");
            ownerOnly(directory, true);
            partial = new File(directory, ".pending");
            destination = new File(directory, filename(suggestedName));
            if (!partial.createNewFile()) throw new IOException("Upload staging unavailable");
            ownerOnly(partial, false);
            long received = 0;
            try (FileOutputStream output = new FileOutputStream(partial)) {
                byte[] buffer = new byte[32768];
                while (true) {
                    if (cancelled.getAsBoolean()) throw new CancellationException();
                    int count = input.read(buffer);
                    if (cancelled.getAsBoolean()) throw new CancellationException();
                    if (count < 0) break;
                    if (count == 0) throw new IOException("Upload source made no progress");
                    if (received + count > MAXIMUM_BYTES) throw new IOException("Upload exceeds size limit");
                    output.write(buffer, 0, count);
                    received += count;
                }
                if (expectedBytes >= 0 && received != expectedBytes) throw new IOException("Incomplete upload source");
                output.getFD().sync();
            }
            if (cancelled.getAsBoolean()) throw new CancellationException();
            if (!partial.renameTo(destination)) throw new IOException("Upload staging unavailable");
            return new Lease(directory, destination, received);
        } catch (IOException | RuntimeException error) {
            try { remove(directory, partial, destination); }
            catch (IOException cleanup) { error.addSuppressed(cleanup); }
            throw error;
        }
    }

    private static void ownerOnly(File file, boolean directory) throws IOException {
        if (!file.setReadable(false, false) || !file.setWritable(false, false) || !file.setExecutable(false, false)
            || !file.setReadable(true, true) || !file.setWritable(true, true)
            || (directory && !file.setExecutable(true, true))) throw new IOException("Upload staging protection unavailable");
    }

    private static void remove(File directory, File partial, File destination) throws IOException {
        IOException failure = null;
        for (File file : new File[]{partial, destination, directory}) {
            if (file == null) continue;
            try { Files.deleteIfExists(file.toPath()); }
            catch (IOException error) {
                if (failure == null) failure = error; else failure.addSuppressed(error);
            }
        }
        if (failure != null) throw failure;
    }

    static final class Lease implements AutoCloseable {
        private final File directory;
        final File file;
        final long bytes;

        private Lease(File directory, File file, long bytes) {
            this.directory = directory; this.file = file; this.bytes = bytes;
        }

        // The integration must close the engine's access before releasing this
        // lease; unlinking a file alone cannot revoke an already-open descriptor.
        @Override public void close() throws IOException { remove(directory, null, file); }
    }
}
