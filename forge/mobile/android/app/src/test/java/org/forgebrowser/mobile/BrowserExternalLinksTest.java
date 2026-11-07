package org.forgebrowser.mobile;

import org.junit.Test;
import static org.junit.Assert.*;

public final class BrowserExternalLinksTest {
    private static final String VIEW = "android.intent.action.VIEW";

    @Test public void onlyViewIntentAddressesAreAccepted() {
        String url = "https://external-fixture.invalid/path?q=value#part";
        assertEquals(url, BrowserExternalLinks.fromViewIntent(VIEW, url));
        for (String action : new String[]{null, "android.intent.action.MAIN", "android.intent.action.SEND"})
            assertNull(BrowserExternalLinks.fromViewIntent(action, url));
    }
    @Test public void unsupportedOrCredentialBearingAddressesFailClosed() {
        for (String url : new String[]{null, "", "about:blank", "http://external-fixture.invalid",
            "file:///private", "content://provider/private", "javascript:alert(1)",
            "https://user:secret@external-fixture.invalid", "https:///missing-host", "https://external-fixture.invalid/\n"})
            assertNull(url, BrowserExternalLinks.fromViewIntent(VIEW, url));
    }
    @Test public void externalAddressesHaveTheSameUTF8BoundAsNativeLinks() {
        assertNull(BrowserExternalLinks.fromViewIntent(VIEW, "https://external-fixture.invalid/" + "a".repeat(8192)));
    }
    @Test public void validationNeverRewritesAnAddressAsSearchInput() {
        assertNull(BrowserExternalLinks.fromViewIntent(VIEW, "external-fixture.invalid"));
        assertNull(BrowserExternalLinks.fromViewIntent(VIEW, "two words"));
    }
}
