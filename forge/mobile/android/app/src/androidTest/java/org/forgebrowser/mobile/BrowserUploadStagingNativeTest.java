package org.forgebrowser.mobile;

import android.content.Context;
import android.system.Os;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.nio.file.Files;
import java.util.UUID;
import java.util.concurrent.CancellationException;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public final class BrowserUploadStagingNativeTest {
    private File directory;
    private BrowserUploadStaging staging;

    @Before public void prepare() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        directory = new File(context.getCacheDir(), "forge-upload-native-" + UUID.randomUUID());
        assertTrue(directory.mkdir());
        staging = new BrowserUploadStaging(directory);
    }
    @After public void clean() throws Exception {
        if (directory == null) return;
        File[] children = directory.listFiles();
        if (children != null) for (File child : children) {
            File[] files = child.listFiles();
            if (files != null) for (File file : files) Files.deleteIfExists(file.toPath());
            Files.deleteIfExists(child.toPath());
        }
        Files.deleteIfExists(directory.toPath());
    }
    @Test public void nativeCacheCopyIsOwnerOnlyAndReleasedWithoutTouchingOriginal() throws Exception {
        byte[] original = new byte[]{1, 2, 3};
        try (BrowserUploadStaging.Lease lease = staging.stage(new ByteArrayInputStream(original), "../../fixture.txt", 3, () -> false)) {
            assertEquals("fixture.txt", lease.file.getName());
            assertArrayEquals(original, Files.readAllBytes(lease.file.toPath()));
            assertEquals(0600, Os.stat(lease.file.getPath()).st_mode & 0777);
            assertEquals(0700, Os.stat(lease.file.getParent()).st_mode & 0777);
            assertEquals(directory.getCanonicalFile(), lease.file.getParentFile().getParentFile().getCanonicalFile());
        }
        assertArrayEquals(new byte[]{1, 2, 3}, original);
        assertEquals(0, directory.list().length);
    }
    @Test public void nativeCancellationAndTruncationLeaveNoCachedBytes() throws Exception {
        assertThrows(CancellationException.class,
            () -> staging.stage(new ByteArrayInputStream(new byte[8]), "fixture.txt", 8, () -> true));
        assertThrows(java.io.IOException.class,
            () -> staging.stage(new ByteArrayInputStream(new byte[8]), "fixture.txt", 9, () -> false));
        assertEquals(0, directory.list().length);
    }
    @Test public void independentCopiesWithSameNameDoNotOverwriteOrDeleteEachOther() throws Exception {
        BrowserUploadStaging.Lease first = staging.stage(new ByteArrayInputStream(new byte[]{1}), "fixture.txt", 1, () -> false);
        try (BrowserUploadStaging.Lease second = staging.stage(new ByteArrayInputStream(new byte[]{2}), "fixture.txt", 1, () -> false)) {
            assertNotEquals(first.file, second.file);
            first.close();
            assertArrayEquals(new byte[]{2}, Files.readAllBytes(second.file.toPath()));
        } finally { first.close(); }
        assertEquals(0, directory.list().length);
    }
}
