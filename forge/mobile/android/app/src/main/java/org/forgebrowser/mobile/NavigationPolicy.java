/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import java.net.URI;
import java.net.URLEncoder;
import java.io.UnsupportedEncodingException;

public final class NavigationPolicy {
    private NavigationPolicy() {}

    public static boolean allows(String value) {
        if (value == null) return false;
        if (value.equals("about:blank")) return true;
        try {
            URI uri = new URI(value);
            return "https".equalsIgnoreCase(uri.getScheme()) && uri.getHost() != null
                && uri.getRawUserInfo() == null;
        } catch (Exception error) { return false; }
    }

    public static String fromInput(String input) {
        String value = input.trim();
        if (value.isEmpty()) throw new IllegalArgumentException("Empty input");
        if (value.matches("(?i)^[a-z][a-z0-9+.-]*:.*")) {
            if (!allows(value)) throw new IllegalArgumentException("Unsupported scheme or address");
            return value;
        }
        if (!value.contains(" ") && value.contains(".")) {
            String candidate = "https://" + value;
            if (allows(candidate)) return candidate;
        }
        try { return "https://duckduckgo.com/?q=" + URLEncoder.encode(value, "UTF-8"); }
        catch (UnsupportedEncodingException impossible) { throw new AssertionError(impossible); }
    }
}
