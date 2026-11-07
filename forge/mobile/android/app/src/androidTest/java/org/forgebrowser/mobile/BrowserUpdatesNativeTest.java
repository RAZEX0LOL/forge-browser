package org.forgebrowser.mobile;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import java.io.File;
import java.nio.file.Files;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class BrowserUpdatesNativeTest {
    @Test public void providerOnlyReadsOneGrantedUUIDPathAndRejectsWrites() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        File directory = new File(context.getCacheDir(), "forge-updates"); directory.mkdirs();
        String name = java.util.UUID.randomUUID() + ".apk";
        File file = new File(directory, name);
        byte[] bytes = {1, 0, 2, 3}; Files.write(file.toPath(), bytes);
        Uri uri = Uri.parse("content://" + context.getPackageName() + ".updates/" + name);
        try {
            try (ParcelFileDescriptor descriptor = context.getContentResolver().openFileDescriptor(uri, "r")) {
                assertNotNull(descriptor); assertEquals(bytes.length, descriptor.getStatSize());
            }
            for (String mode : new String[]{"w", "rw", "rwt"}) {
                try (ParcelFileDescriptor ignored = context.getContentResolver().openFileDescriptor(uri, mode)) { fail("Allowed write"); }
                catch (java.io.FileNotFoundException expected) { }
            }
            for (String suffix : new String[]{"/../files/profile", "/" + name + ".part", "/" + name + "?x=1", "/%2e%2e/" + name}) {
                try (ParcelFileDescriptor ignored = context.getContentResolver().openFileDescriptor(
                    Uri.parse("content://" + context.getPackageName() + ".updates" + suffix), "r")) { fail("Allowed unsafe path"); }
                catch (java.io.FileNotFoundException expected) { }
            }
        } finally { file.delete(); }
    }

    @Test public void providerIsNotExportedAndInstalledCertificateIsAvailable() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        android.content.pm.ProviderInfo provider = context.getPackageManager().resolveContentProvider(context.getPackageName() + ".updates", 0);
        assertNotNull(provider); assertFalse(provider.exported); assertTrue(provider.grantUriPermissions);
        android.content.pm.PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(),
            PackageManager.GET_SIGNING_CERTIFICATES);
        assertEquals("4faadf5155d5d72c0b48b19139da9b4c9a2dabc4111374cf3c6acdee3cbf942d", BrowserUpdates.signer(info));
        assertEquals(2, info.getLongVersionCode());
    }
}
