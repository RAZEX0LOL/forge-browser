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

### First published bootstrap and evidence

`https://razex.shop/forge/downloads/Forge-android-20261107-v2-arm64-v8a-debug.apk`
is versionCode 2 (`0.1.0-dev.2`), 198,948,829 bytes, SHA-256
`87e83a323b662754e751acbda0e7e0f0a7ae2824bf21eb6613dc8102bf1932ce`.
Source: `49d0031726f33faebc0f77ce6137e3dca06d2f00` (frozen Android inputs).
Sequence 1 expires **2026-11-20 19:33:43 UTC**; sign a higher sequence before
expiry. Private manifest key stays on the maintainer machine, not the server.

55 unit/66 native tests passed, lint only OldTargetApi. A full-system API35
emulator used an explicitly test-only lower-version seed, fetched the signed feed,
downloaded the published APK and confirmed the real OS installer (1 → 2).
Synthetic canary and regular session bytes stayed identical. Current-version
checking passed afterward; the source permission was disabled via Settings.
The exact updater-installed APK passed another 66 native tests. ATD lacked the
required Settings activity; its failed run and host-selector/foreground failures
are retained, not counted as install passes. No physical-device acceptance.

## Other platforms

iOS stays on Apple's TestFlight update mechanism. It must not download/install
an App Store IPA from this server. The owner selected full-package desktop
updates, starting with macOS, rather than replacing/disabling Mozilla MAR checks.
The implementation and native test/build procedure are in
[updater/README.md](updater/README.md). Historical desktop archives do not contain
the new helper. macOS bootstrap signing/notarization and signed replacement
acceptance are separate gates; Windows/Linux installation remains disabled until
their native implementation and validation exist. Merely hosting files is not a
working desktop auto-updater.

### Published macOS ARM64 bootstrap — 2026-11-08

The accepted bootstrap is build **2026110802**, not the earlier blocked v3.
Download:
`https://razex.shop/forge/downloads/Forge-development-20261108-v2-updater-macos-arm64-notarized.zip`.
It is 168,733,014 bytes, SHA-256
`c3560f04b0565584244638ed5cb328a264664e81286ccd2390c8cf49bc3c3045`,
source `8eb6bf35596b54828c5f844c3566eb492e236e6d`, notarization
`361167e9-2e0c-4998-95da-985f24f102c1`. Developer ID, stapled ticket, Gatekeeper
and 285 signed native-launcher browser checks passed. Minimum macOS13 is declared;
the exact macOS13 browser runtime and a complete newer-version GUI upgrade are
not claimed as tested. macOS15 CI covers the helper, not a full browser install.

Endpoint: `https://razex.shop/forge/updates/desktop-macos-arm64.json`.
Sequence 1 expires **2026-11-20 21:40:59 UTC**. It uses the same offline release
key as Android, with strict desktop channel/package/target separation.
Install this first ZIP manually; thereafter use the control center's
**Check for Forge updates**. Installation is never silent and requires fully
quitting Forge. Signed owned-copy replacement, retained backup, outside-app
canary preservation, actual Firefox process guarding and child survival across
normal browser shutdown passed. The native Go client also verified the live
HTTPS channel using its real pinned key and current clock. This does not stand
in for automation of the real consent dialogs or a different-version GUI install.

Windows, Linux and Intel remain manual-download-only here; no feeds or claimed
native replacement support were fabricated for those targets.

### Manual DMG installer and icon correction

The website also offers `Forge-development-20261108-v2-macos-arm64.dmg` for normal
drag-to-Applications installation. Its application has metadata revision 1 of the
same native build 2026110802: remove Firefox's inherited asset-catalog icon name
so macOS resolves Forge's ICNS. That metadata variant is separately signed and
notarized; it is not byte-identical to the original ZIP application.

Neither signed feed nor any previous ZIP is rewritten for this manual installer.
The updater still accepts ZIP packages, not DMG installers, and a same-build
metadata variant is not presented as a newer native runtime. Future new packages
must retain the icon fix from `package_macos.py`. Installation details and exact
validation limits are in `DMG_PACKAGING.md`.
