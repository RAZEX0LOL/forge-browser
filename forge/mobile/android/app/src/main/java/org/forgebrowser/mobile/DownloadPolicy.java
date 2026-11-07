/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.CancellationException;
import java.util.function.BooleanSupplier;
import java.util.function.LongConsumer;

public final class DownloadPolicy {
    public static final long MAXIMUM_BYTES = 256L * 1024 * 1024;
    private DownloadPolicy() {}

    public static boolean allows(String url) {
        return url != null && !url.equals("about:blank") && NavigationPolicy.allows(url);
    }

    public static String filename(String suggested) {
        StringBuilder result = new StringBuilder();
        if (suggested != null) suggested.codePoints().forEach(point -> {
            if (Character.isLetterOrDigit(point) || " ._-()".indexOf(point) >= 0) {
                String next = new String(Character.toChars(point));
                if ((result.toString() + next).getBytes(StandardCharsets.UTF_8).length <= 160) result.append(next);
            }
        });
        String name = result.toString().replaceAll("^[ .]+|[ .]+$", "");
        String stem = name.split("\\.", 2)[0].toUpperCase(Locale.ROOT);
        if (name.isEmpty() || stem.matches("CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]")) return "download";
        return name;
    }

    public static long copy(InputStream input, OutputStream output, long expected,
                            BooleanSupplier cancelled, LongConsumer progress) throws IOException {
        if (expected > MAXIMUM_BYTES) throw new IOException("Download exceeds size limit");
        byte[] buffer = new byte[32768];
        long received = 0;
        while (true) {
            if (cancelled.getAsBoolean()) throw new CancellationException();
            int count = input.read(buffer);
            if (count < 0) break;
            if (cancelled.getAsBoolean()) throw new CancellationException();
            if (received + count > MAXIMUM_BYTES) throw new IOException("Download exceeds size limit");
            output.write(buffer, 0, count);
            received += count;
            progress.accept(received);
        }
        if (cancelled.getAsBoolean()) throw new CancellationException();
        if (expected >= 0 && received != expected) throw new IOException("Incomplete download");
        return received;
    }
}
