# Distribution status — 2026-10-28

## Available locally

The macOS Apple Silicon development bundle uses the pinned Mozilla artifact
runtime, Forge source changes and pinned Russian locale resources. It is
ad-hoc signed, not Developer ID signed or notarized. A disk image is transport
for that same development bundle, not a signed production installer.

The maintainer's local run passed 285 browser checks, 123 source tests and
10 additional restarts with 200 temporary tabs. These observations apply only
to that macOS package. They do not validate Windows, Linux, Android or iOS.

Manual VoiceOver, external OS accessibility transport, long-duration signed-in
workflows, sleep/wake, real printing and packet-level traffic capture remain
unverified. Native Gecko macOS accessibility-bridge tests are not VoiceOver tests.

## Before publishing other desktop packages

Linux x64 and Intel macOS now have successful native CI builds and smoke checks;
Windows x64 has a built archive with a test-harness fix under retest.
See [BUILD_MATRIX.md](BUILD_MATRIX.md) for exact counts and remaining work.

- Build the pinned source/runtime on appropriate Windows, Linux and Intel macOS runners.
- Replace and audit all remaining platform branding and package metadata.
- Add platform-specific packaging rather than relabeling upstream installers.
- Run native launch/session, security, localization and UI tests on each target.
- Supply source/provenance and license notices for every shipped dependency.
- Design and operate a supported security-update process before claiming stable status.
- Arrange platform signing/notarization separately; never disable trust checks.

## Mobile work

An initial Android GeckoView shell now exists in `mobile/android`, with separate
unit and native emulator tests. Builds are being brought up; no production APK/AAB
is available. Touch feature parity and state persistence still require work.
The desktop XUL overlay is not an Android UI.

iOS/iPadOS now has an initial WKWebView application in `mobile/ios`, with a successful
Simulator build and four locally passing native tests. This is not Gecko or a
claim of alternate-engine eligibility. Phone distribution requires Apple's
provisioning/signing process; no installable Forge IPA exists yet.

## Deliberately not included in the public source export

User profiles, credentials, local reports/screenshots, virtual environments,
binary build trees, signing keys and machine-specific caches. Do not upload
these directories when reproducing a build.
