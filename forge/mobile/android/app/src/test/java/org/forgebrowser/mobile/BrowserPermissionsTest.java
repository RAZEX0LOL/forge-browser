package org.forgebrowser.mobile;

import android.Manifest;
import org.junit.Test;
import static org.junit.Assert.*;

public class BrowserPermissionsTest {
    @Test public void originsNeverDisplayPathsSecretsOrCredentials() {
        assertEquals("https://example.com", BrowserPermissions.origin("https://EXAMPLE.com:443/private?q=secret#fragment"));
        assertEquals("https://example.com:8443", BrowserPermissions.origin("https://example.com:8443/path"));
        assertEquals("https://[::1]", BrowserPermissions.origin("https://[::1]:443/path"));
    }
    @Test public void invalidAndNonHTTPSOriginsAreRejected() {
        for (String value : new String[]{null, "about:blank", "http://example.com", "https://user:secret@example.com", "data:text/html,test",
            "https://example.com:0", "https://example.com:65536", "https://example.com\n.evil", "https:///missing-host"})
            assertNull(value, BrowserPermissions.origin(value));
    }
    @Test public void onlyExplicitCameraAndMicrophoneSystemPermissionsAreSupported() {
        assertTrue(BrowserPermissions.supported(new String[]{Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO}));
        assertTrue(BrowserPermissions.supported(new String[]{Manifest.permission.RECORD_AUDIO}));
        assertFalse(BrowserPermissions.supported(null));
        assertFalse(BrowserPermissions.supported(new String[]{}));
        assertFalse(BrowserPermissions.supported(new String[]{Manifest.permission.CAMERA, Manifest.permission.ACCESS_FINE_LOCATION}));
        assertFalse(BrowserPermissions.supported(new String[]{"unknown.permission"}));
    }
}
