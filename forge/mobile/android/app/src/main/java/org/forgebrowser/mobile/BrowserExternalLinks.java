/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

final class BrowserExternalLinks {
    private BrowserExternalLinks() {}

    static String fromViewIntent(String action, String address) {
        if (!"android.intent.action.VIEW".equals(action)) return null;
        return BrowserLinkActions.shareURL(address);
    }
}
