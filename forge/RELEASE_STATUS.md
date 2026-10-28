# Distribution status — 2026-10-28

## Published development packages

[Download the public multiplatform prerelease](https://github.com/RAZEX0LOL/forge-browser/releases/tag/v0.1.0-dev.20261028-multiplatform),
published under **RAZEX0LOL**. It contains six desktop packages, three Android debug
APKs, an iOS Simulator ZIP, an unsigned iOS device XCArchive ZIP, `MANIFEST.json`
and `SHA256SUMS`. All 13 uploaded asset digests matched the published integrity
data. Per-package source commits are recorded in the manifest, not inferred from
the release tag.

The macOS Apple Silicon development bundle uses the pinned Mozilla artifact
runtime, Forge source changes and pinned Russian locale resources. It is
ad-hoc signed, not Developer ID signed or notarized. A disk image is transport
for that same development bundle, not a signed production installer.

The maintainer's original local run passed 285 browser checks, 123 source tests and
10 additional restarts with 200 temporary tabs. These observations apply only
to that macOS package. They do not validate Windows, Linux, Android or iOS.

Manual VoiceOver, external OS accessibility transport, long-duration signed-in
workflows, sleep/wake, real printing and packet-level traffic capture remain
unverified. Native Gecko macOS accessibility-bridge tests are not VoiceOver tests.

## Desktop validation and remaining release work

All six desktop CI targets built and passed browser checks: Windows x64/ARM64 and
Linux x64/ARM64 passed 260 each; Intel and Apple Silicon macOS passed 270 each.
The shipped Apple Silicon DMG is the separately validated native-Russian package,
not the CI ZIP. Other published desktop packages use en-US upstream resources
with Forge ru/en UI. See [BUILD_MATRIX.md](BUILD_MATRIX.md) for validation origins.
Latest source checks passed 77 Python and 56 JavaScript tests (133 total).

- Replace and audit all remaining platform branding and package metadata.
- Extend native tests to physical devices and long-duration real-world workflows.
- Continue auditing dependency notices and distribution metadata.
- Design and operate a supported security-update process before claiming stable status.
- Arrange platform signing/notarization separately; never disable trust checks.

## Mobile work

The Android GeckoView shell in `mobile/android` has published ABI-specific debug
APKs for arm64-v8a, armeabi-v7a and x86_64. Unit tests, lint and two native UI/Gecko
tests passed on an x86_64 emulator. Physical ARM devices remain untested; no
production-signed APK/AAB is available. Feature parity and durable sessions still require work.
The desktop XUL overlay is not an Android UI.

iOS/iPadOS now has an initial WKWebView application in `mobile/ios`, with a successful
Simulator build, an unsigned device archive and four native tests passing in both
English and Russian on Simulator. This is not Gecko or a
claim of alternate-engine eligibility. Phone distribution requires Apple's
provisioning/signing process; no installable Forge IPA exists yet.

## Deliberately not included in the public source export

User profiles, credentials, local reports/screenshots, virtual environments,
binary build trees, signing keys and machine-specific caches. Do not upload
these directories when reproducing a build.
