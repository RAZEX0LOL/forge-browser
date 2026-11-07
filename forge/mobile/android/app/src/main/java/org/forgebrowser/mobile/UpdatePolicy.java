/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
package org.forgebrowser.mobile;

import java.io.InputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.function.BooleanSupplier;
import org.json.JSONObject;

/** Independent of Gecko, profiles, browsing history and cookies. Fail closed. */
final class UpdatePolicy {
    static final String ENDPOINT = "https://razex.shop/forge/updates/android-development.json";
    static final String PACKAGE = "org.forgebrowser.mobile.development";
    static final String CHANNEL = "android-development";
    static final long MAX_BYTES = 300L * 1024 * 1024;
    static final long MAX_LIFETIME = 14L * 86400;
    static final String PUBLIC_KEY = "MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAxTcplNZKRu82IwDG4cVdeah2JnTXdfMaTEwGlLRM1xlqqAmVvPITqVl0SwGtEoXE7QImpVoDFxNQsgD+MOnfDgLftJTVfpX9jORUGGDnUyXxsz2r5soQ/YglN4Krp0PZQdc5nPgAlmv2jx8fmmB2Pggjm4QkyvIHke3ZILdobY6IKpyumbPSuHk1d0BZUqKN9bDKZ60nWWR5ox4PmzfvrYl0+q54xzvs7AF9W80E7i9MnTgT0jpnt8nQwytQqU93JskiL6kPj4UBBCbM/1GR8pGuo1Wdc1/LyVKX4yJmETVYX9fafBZy49xboPgFvlAeBvo43GhyO7qtUnFNvEymlUJNxJi3XBEeID8ZXBFFOoh2p4/LgVkaTEQAnZlB/V+OQukxgWempaO5noJ7K41HRoyWXIOGrK0SfGGNDMDfQ20Cs48KJdUgyHOtSh6XdtAI9rCUfqWQydONB7+/TCqZa6xy6c1RcR4UiLXU4UIe7ye+DeAPOXkg1QvqS9PdYXE3AgMBAAE=";

    static final class Offer {
        final long sequence, expires, versionCode, bytes;
        final String versionName, url, sha256, certificate, abi;
        Offer(JSONObject payload, String abi) throws Exception {
            sequence = integer(payload, "sequence"); expires = integer(payload, "expires");
            versionCode = integer(payload, "versionCode");
            versionName = payload.getString("versionName");
            JSONObject artifact = payload.getJSONObject("artifacts").getJSONObject(abi);
            this.abi = abi; url = artifact.getString("url"); bytes = integer(artifact, "bytes");
            sha256 = artifact.getString("sha256"); certificate = payload.getString("certificateSha256");
        }
    }

    private static long integer(JSONObject value, String key) throws Exception {
        Object raw = value.get(key);
        if (!(raw instanceof Integer) && !(raw instanceof Long)) throw new IOException("Integer required");
        return ((Number) raw).longValue();
    }

    static Offer verify(byte[] envelope, long now, long minimumSequence, String abi) throws Exception {
        return verify(envelope, now, minimumSequence, abi, PUBLIC_KEY);
    }

    // Key argument only used by independent policy tests; production always pins PUBLIC_KEY.
    static Offer verify(byte[] envelope, long now, long minimumSequence, String abi, String key) throws Exception {
        if (envelope.length > 65536) throw new IOException("Manifest too large");
        JSONObject signed = new JSONObject(new String(envelope, StandardCharsets.UTF_8));
        if (signed.length() != 2) throw new IOException("Unexpected envelope fields");
        byte[] payloadBytes = Base64.getDecoder().decode(signed.getString("payload"));
        Signature verifier = Signature.getInstance("SHA256withRSA");
        verifier.initVerify(KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(key))));
        verifier.update(payloadBytes);
        if (!verifier.verify(Base64.getDecoder().decode(signed.getString("signature")))) throw new IOException("Invalid manifest signature");
        JSONObject payload = new JSONObject(new String(payloadBytes, StandardCharsets.UTF_8));
        if (integer(payload, "schemaVersion") != 1 || !PACKAGE.equals(payload.getString("packageName"))
            || !CHANNEL.equals(payload.getString("channel"))) throw new IOException("Wrong channel/package");
        long issued = integer(payload, "issued");
        Offer offer = new Offer(payload, abi);
        if (issued > now + 300 || issued < 0 || offer.expires <= now || offer.expires <= issued
            || offer.expires - issued > MAX_LIFETIME || offer.sequence < minimumSequence || offer.sequence <= 0
            || offer.versionCode <= 0 || offer.versionCode > Integer.MAX_VALUE || offer.bytes <= 0 || offer.bytes > MAX_BYTES
            || !offer.sha256.matches("[a-f0-9]{64}") || !offer.certificate.matches("[a-f0-9]{64}")
            || !offer.versionName.matches("[A-Za-z0-9][A-Za-z0-9. _+-]{0,63}") || !allowsURL(offer.url)) {
            throw new IOException("Invalid or expired update metadata");
        }
        return offer;
    }

    static boolean allowsURL(String value) {
        try {
            URI uri = new URI(value);
            return "https".equals(uri.getScheme()) && "razex.shop".equals(uri.getHost()) && uri.getPort() == -1
                && uri.getRawUserInfo() == null && uri.getRawQuery() == null && uri.getRawFragment() == null
                && uri.getRawPath().matches("/forge/downloads/Forge-android-[A-Za-z0-9._-]+\\.apk");
        } catch (Exception error) { return false; }
    }

    static void copy(InputStream input, OutputStream output, Offer offer, BooleanSupplier cancelled) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[65536]; long total = 0; int count;
        while ((count = input.read(buffer)) != -1) {
            if (cancelled.getAsBoolean() || Thread.currentThread().isInterrupted()) throw new IOException("Cancelled");
            total += count;
            if (total > offer.bytes || total > MAX_BYTES) throw new IOException("Update exceeds declared size");
            output.write(buffer, 0, count); digest.update(buffer, 0, count);
        }
        if (cancelled.getAsBoolean() || total != offer.bytes || !hex(digest.digest()).equals(offer.sha256))
            throw new IOException("Update integrity mismatch");
    }

    static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder();
        for (byte value : bytes) result.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
        return result.toString();
    }
}
