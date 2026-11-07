# Server update channels

## Android development channel

The first updater-enabled build uses versionCode 2, the existing development
package ID and the same debug APK certificate as versionCode 1. This preserves
Android's in-place update path; it does **not** convert that development identity
into a production signing key. Keep the original keystore backed up outside Git.
An incompatible existing signature must fail, never be bypassed by uninstalling.

Bootstrap: install the new APK once manually over the old development app.
Thereafter open **Menu → Forge updates → Check now**. No periodic/background
network checks are made, including in private browsing. Explicit checks send an
IP address and a fixed updater User-Agent to razex.shop, not URLs, history,
profile contents or Gecko cookies. No analytics identifier or account is used.
The server's usual access logs may record these requests.

Endpoint: `https://razex.shop/forge/updates/android-development.json`.
An RSA-3072/SHA-256 signature authenticates the exact base64-decoded payload;
the public key is pinned in `UpdatePolicy.java`. HTTPS validation remains native.
Only same-origin `/forge/downloads/Forge-android-*.apk` URLs without redirects,
credentials, custom ports, query strings or fragments are accepted.

Payload schema 1 contains channel/package, monotonic sequence, issued/expires
Unix seconds, versionCode/versionName, APK certificate SHA-256 and per-ABI URL,
size and SHA-256. Lifetime is at most 14 days. Highest accepted sequence persists
outside browsing data; expired/older metadata fails closed. A wrong local clock
can prevent checking. VersionCode must increase before download/installation.
APK size is streamed with a 300-MiB cap and exact length/hash verification.
Package archive ID, version and signer must match the signed metadata and the
installed application. Android independently enforces installation signatures.

Downloads remain in app-private cache; unverified `.part` paths cannot be served
by the non-exported, read-only provider. A fresh random URI identifies each
verified APK and receives a temporary read grant only via the installer intent.
Cancellation/backgrounding stops work; a later attempt uses a different file.
Old staging files are eligible for cleanup after 24 hours on the next updater
use. No broad storage permission, root, silent install or accessibility service.
If installation from Forge is not allowed, the app explicitly offers the OS
settings screen. Return and repeat the check after granting permission; the app
does not automatically continue or change the permission itself.

### Publishing (operator only)

1. Freeze source inputs; run unit/native/lint checks on an owned emulator.
2. Build a higher versionCode using the same keystore; verify certificate, package
   ID, ABI, version and full SHA-256. Use a new immutable artifact filename.
3. Transfer into private server staging and verify the full hash before atomically
   exposing it under downloads. Never overwrite any previous APK bytes.
4. Prepare payload with increased sequence and short expiry; sign offline:

   ```sh
   python3.12 forge/scripts/sign_update_manifest.py \
     --payload /private/staging/payload.json \
     --private-key "$HOME/.config/forge-signing/updates/android-development-manifest-v1.env" \
     --output /private/staging/android-development.json
   ```

5. Verify the signature against the pinned public key, then atomically replace
   only the channel metadata, preserving previous envelopes/receipts privately.
   Recheck public HTTPS bytes, HEAD/ranges and updater UI on an owned emulator.
6. Renew metadata **before expiry**, even if no newer package exists, using a
   higher sequence. No server cron has the signing key. An expired feed is an
   error, not proof that the installed browser is current/security-supported.

This is a manually operated development channel, not a maintained security-update
SLA. Stable signing migration, key rotation/recovery and physical-device behavior
remain release gates. Installed v1 builds cannot discover updates by themselves.

## Other platforms

iOS stays on Apple's TestFlight update mechanism. It must not download/install
an App Store IPA from this server. Desktop artifact packages do not yet have a
Forge-keyed native update service. Mozilla MAR signature verification must not
be disabled or redirected to unsigned Forge payloads. Desktop integration is a
separate stage; merely hosting files is not a working desktop auto-updater.
