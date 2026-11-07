package org.forgebrowser.mobile;

import org.junit.Test;
import org.junit.Before;
import static org.junit.Assert.*;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.MessageDigest;
import java.security.Signature;
import java.util.Base64;

public class UpdatePolicyTest {
    private static final long NOW = 1800000000;
    private KeyPair key;
    private JSONObject payload;
    private final byte[] data = "APK fixture, not an installable package".getBytes(StandardCharsets.UTF_8);

    @Before public void setup() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA"); generator.initialize(2048); key = generator.generateKeyPair();
        JSONObject artifact = new JSONObject().put("url", "https://razex.shop/forge/downloads/Forge-android-test-arm64.apk")
            .put("bytes", data.length).put("sha256", UpdatePolicy.hex(MessageDigest.getInstance("SHA-256").digest(data)));
        payload = new JSONObject().put("schemaVersion", 1).put("channel", UpdatePolicy.CHANNEL).put("packageName", UpdatePolicy.PACKAGE)
            .put("sequence", 10).put("issued", NOW - 10).put("expires", NOW + 3600).put("versionCode", 2)
            .put("versionName", "0.1.0-dev.2").put("certificateSha256", "a".repeat(64))
            .put("artifacts", new JSONObject().put("arm64-v8a", artifact));
    }
    private byte[] signed() throws Exception {
        byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
        Signature signer = Signature.getInstance("SHA256withRSA"); signer.initSign(key.getPrivate()); signer.update(bytes);
        return new JSONObject().put("payload", Base64.getEncoder().encodeToString(bytes))
            .put("signature", Base64.getEncoder().encodeToString(signer.sign())).toString().getBytes(StandardCharsets.UTF_8);
    }
    private UpdatePolicy.Offer verify(byte[] envelope, long sequence, String abi) throws Exception {
        return UpdatePolicy.verify(envelope, NOW, sequence, abi, Base64.getEncoder().encodeToString(key.getPublic().getEncoded()));
    }
    private void rejects() throws Exception {
        try { verify(signed(), 10, "arm64-v8a"); fail("Accepted unsafe metadata"); } catch (java.io.IOException | org.json.JSONException expected) { }
    }
    @Test public void signedOfferAndExactStreamingBytesPass() throws Exception {
        UpdatePolicy.Offer offer = verify(signed(), 10, "arm64-v8a");
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        UpdatePolicy.copy(new ByteArrayInputStream(data), output, offer, () -> false);
        assertArrayEquals(data, output.toByteArray()); assertEquals(2, offer.versionCode);
    }
    @Test public void productionKeyRejectsTestSigner() throws Exception {
        try { UpdatePolicy.verify(signed(), NOW, 0, "arm64-v8a"); fail(); } catch (java.security.SignatureException | java.io.IOException expected) { }
    }
    @Test public void tamperedPayloadRejected() throws Exception {
        JSONObject envelope = new JSONObject(new String(signed(), StandardCharsets.UTF_8));
        payload.put("versionCode", 99); envelope.put("payload", Base64.getEncoder().encodeToString(payload.toString().getBytes(StandardCharsets.UTF_8)));
        try { verify(envelope.toString().getBytes(StandardCharsets.UTF_8), 0, "arm64-v8a"); fail(); } catch (java.io.IOException expected) { }
    }
    @Test public void expiredRejected() throws Exception { payload.put("expires", NOW); rejects(); }
    @Test public void futureAndLongLivedRejected() throws Exception {
        payload.put("issued", NOW + 301); rejects(); payload.put("issued", NOW - 1).put("expires", NOW + UpdatePolicy.MAX_LIFETIME); rejects();
    }
    @Test public void rollbackRejected() throws Exception { payload.put("sequence", 9); rejects(); }
    @Test public void wrongChannelOrPackageRejected() throws Exception {
        payload.put("channel", "stable"); rejects(); payload.put("channel", UpdatePolicy.CHANNEL).put("packageName", "other.app"); rejects();
    }
    @Test public void unsupportedABIRejected() throws Exception {
        try { verify(signed(), 0, "x86_64"); fail(); } catch (org.json.JSONException expected) { }
    }
    @Test public void invalidNumbersAndHashesRejected() throws Exception {
        payload.put("versionCode", 2.5); rejects(); payload.put("versionCode", 0); rejects();
        payload.put("versionCode", 2).put("certificateSha256", "no"); rejects();
    }
    @Test public void unsafeURLsRejected() {
        for (String url : new String[]{"http://razex.shop/forge/downloads/Forge-android-test.apk", "https://evil.test/forge/downloads/Forge-android-test.apk",
            "https://razex.shop:443/forge/downloads/Forge-android-test.apk", "https://user@razex.shop/forge/downloads/Forge-android-test.apk",
            "https://razex.shop/forge/downloads/../Forge-android-test.apk", "https://razex.shop/forge/downloads/Forge-android-test.apk?q=1",
            "https://razex.shop/forge/downloads/Forge-android-test.apk#x", "https://razex.shop/forge/downloads/Forge-android-%2e%2e.apk"}) assertFalse(url, UpdatePolicy.allowsURL(url));
    }
    @Test public void shortLongCorruptAndCancelledDownloadsRejected() throws Exception {
        UpdatePolicy.Offer offer = verify(signed(), 0, "arm64-v8a");
        for (byte[] input : new byte[][]{new byte[1], new byte[data.length + 1], new byte[data.length]}) {
            try { UpdatePolicy.copy(new ByteArrayInputStream(input), new ByteArrayOutputStream(), offer, () -> false); fail(); }
            catch (java.io.IOException expected) { }
        }
        try { UpdatePolicy.copy(new ByteArrayInputStream(data), new ByteArrayOutputStream(), offer, () -> true); fail(); }
        catch (java.io.IOException expected) { }
    }
    @Test public void oversizedManifestAndArtifactRejected() throws Exception {
        try { verify(new byte[65537], 0, "arm64-v8a"); fail(); } catch (java.io.IOException expected) { }
        payload.getJSONObject("artifacts").getJSONObject("arm64-v8a").put("bytes", UpdatePolicy.MAX_BYTES + 1); rejects();
    }
}
