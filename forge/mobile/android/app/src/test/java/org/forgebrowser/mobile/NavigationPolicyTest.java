package org.forgebrowser.mobile;

import org.junit.Test;
import static org.junit.Assert.*;

public class NavigationPolicyTest {
    @Test public void httpsAddressesAndSearch() {
        assertEquals("https://example.com", NavigationPolicy.fromInput("example.com"));
        assertEquals("https://example.com/path", NavigationPolicy.fromInput("https://example.com/path"));
        assertTrue(NavigationPolicy.fromInput("two words").contains("q=two+words"));
    }
    @Test public void rejectLocalActiveCleartextAndCredentialUrls() {
        for (String value : new String[]{"javascript:alert(1)", "file:///etc/passwd", "content://local",
                "data:text/html,test", "http://example.com", "https://user:pass@example.com", "https:///missing"}) {
            assertFalse(value, NavigationPolicy.allows(value));
            try { NavigationPolicy.fromInput(value); fail(value); }
            catch (IllegalArgumentException expected) {}
        }
    }
}
