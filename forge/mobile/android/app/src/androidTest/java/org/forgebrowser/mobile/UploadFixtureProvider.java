package org.forgebrowser.mobile;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;
import java.nio.file.Files;

// Fixed public fixture bytes only; no arbitrary provider paths, inputs or writes.
public final class UploadFixtureProvider extends ContentProvider {
    static final Uri URI = Uri.parse("content://org.forgebrowser.mobile.uploadfixture/fixture");
    static final byte[] BYTES = "forge-selected-upload-fixture".getBytes(java.nio.charset.StandardCharsets.UTF_8);
    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri uri) { return "text/plain"; }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
        if (!URI.equals(uri) || projection == null || projection.length != 1 || !OpenableColumns.DISPLAY_NAME.equals(projection[0]))
            throw new IllegalArgumentException("Only display-name fixture queries are allowed");
        MatrixCursor cursor = new MatrixCursor(projection);
        cursor.addRow(new Object[]{"../../fixture.txt"});
        return cursor;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!URI.equals(uri) || !"r".equals(mode)) throw new FileNotFoundException("Unknown fixture");
        File file = new File(getContext().getCacheDir(), "upload-provider-fixture.txt");
        try { Files.write(file.toPath(), BYTES); }
        catch (java.io.IOException error) { throw new FileNotFoundException("Fixture unavailable"); }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException(); }
}
