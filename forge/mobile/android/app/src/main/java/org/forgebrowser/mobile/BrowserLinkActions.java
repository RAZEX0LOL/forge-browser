/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

final class BrowserLinkActions {
    static String shareURL(String value) {
        if (value == null || value.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 8192
            || value.equals("about:blank") || !NavigationPolicy.allows(value)) return null;
        return value;
    }
}
