package org.forgebrowser.mobile;

import org.junit.Test;
import static org.junit.Assert.*;

public final class BrowserLinkActionsTest {
    @Test public void shareKeepsHTTPSAddressButDoesNotCreateANetworkRequest() {
        String url = "https://example.invalid/page?q=value#part";
        assertEquals(url, BrowserLinkActions.shareURL(url));
    }

    @Test public void shareRejectsInternalExternalAndCredentialBearingURLs() {
        for (String value : new String[]{null, "about:blank", "http://example.invalid", "file:///private",
                "javascript:alert(1)", "mailto:user@example.invalid", "https://user:secret@example.invalid"}) {
            assertNull(BrowserLinkActions.shareURL(value));
        }
    }

    @Test public void shareRefusesOversizedAddresses() {
        assertNull(BrowserLinkActions.shareURL("https://example.invalid/" + "a".repeat(8192)));
    }
}
