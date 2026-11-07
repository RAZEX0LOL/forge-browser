# Mobile source checkpoint — 2026-11-07

This remains development software, not a daily-use readiness claim. The earlier
authorization covered source pushes only. On 2026-11-07 the owner additionally
authorized all source pushes, a new TestFlight upload and deployment of the
download website. No default-browser entitlement or other Apple capability
request is implied by that release authorization.

## Authorized distribution — 2026-11-07

`forge-testflight-20261107-build6-qa1` passed the current iOS snapshot with build-6
overrides: native 67/67 and UI 9/9 in each of ru/en (152 executions, no skips).
The separate Files-panel test initially hit a runner startup abort in XCTest's
stall handler while UIKit accessibility loaded, before the test method ran
(`ios-v5`). A control used `test-without-building` on the same owned simulator
and verified identical app/runner/test executable hashes. It passed 1/1 and
recorded zero POST attempts (`ios-v6`). This validates default WebKit Files
opening/cancellation on iOS27, not successful file submission, custom upload
guards, exact iOS17/18.4 behavior or the cause of the earlier stall.

After a load-blocked archive preflight, build 6 was signed, Apple-validated,
uploaded once and processed VALID. External state is BETA_APPROVED; build 6 is
assigned to the public group: https://testflight.apple.com/join/4hvp4sk8.
IPA SHA-256: `1e04e71b7ab0fbfb2a22a29d3036ed781b3a05468e7060ffd47327d84eefab76`.
The website https://razex.shop/forge/ now offers that invitation and the newly
named Android ARM64 debug APK, matching the accepted 64-native/43-unit/three-E2E
snapshot. Android source commit is `9ed729458ba9a5746d2bfcc257b1a2dc56c4100d`;
build-6 iOS inputs are recorded in the private frozen source manifest, with build
number 6 supplied explicitly. Later documentation/site commits do not rebuild
either binary. Older packages and failed/interrupted evidence remain preserved.

## Validation scope

### Android server-updater candidate (later 2026-11-07)

VersionCode 2 keeps the published v1 APK certificate and adds manual signed-feed
checks via razex.shop. Frozen `forge-updates-20261107-android-v1` passed 55 unit
and 66 native tests; lint reports only OldTargetApi. The HTTPS download regression
now checks the exact November checksum file (1375 bytes and SHA-256), replacing
the obsolete October length rather than removing the assertion. The earlier
permission-allowlist source failure was addressed with the exact expanded list
and non-exported/read-grant provider assertions. Source checks: 111 Python/56 JS.

The signed sequence-1 feed and immutable v2 ARM64 APK are published; the main
website offers v2 and preserves the previous APK under its original name.
A lower-version updater-enabled **test-only** seed rejected the genuinely absent
feed before publication and retained versionCode 1. The initial host selector
failure is retained. ATD cannot resolve MANAGE_UNKNOWN_APP_SOURCES; no appops/root
bypass was used. Full-system API35 Google APIs validation subsequently passed the
real updater flow: signed public feed, actual HTTPS APK download, explicit OS
Settings permission, app confirmation and real Android installer Update.
VersionCode increased 1 → 2; synthetic canary and regular session hashes stayed
identical. This seed is test-only, not the original public v1. Acceptance is in
`forge-updates-20261107-flow-v2/install-v2`. A separate current-version check passed
and the install-source permission was disabled again via Settings. Earlier ATD,
selector, transport startup and post-installer foreground failures are retained.

`forge-updates-20261108-android-tests-v2` then passed all 66 native tests on the
exact APK installed by that updater. The only test-source delta pins the HTTPS
download fixture to immutable `.bin` bytes (same 1375-byte/hash assertion), so
future release checksum changes cannot break it. No APK rebuild or replacement
for this test delta, and no physical-device acceptance claim.
See `../UPDATE_CHANNEL.md` for trust, expiry, rollback protection and bootstrap.

| Scope | Latest completed evidence |
| --- | --- |
| Source checks | Node 56/56; Python 111/111; Python compilation and diff whitespace checks passed |
| iOS build-6 sources | Native 67/67 per language and UI 9/9 per language, 152 executions; separate same-binary Files cancellation 1/1 |
| Android previous stage-4a snapshot | Native 41/41, unit 27/27; lint only OldTargetApi |
| Android current OS-link-entry delta | Native 49/49, unit 31/31, plus separate startup controls 2/2; lint only OldTargetApi. Earlier failures remain preserved |
| Android local staging/navigation delta | Native 53/53, unit 40/40; targeted regression 2/2; lint only OldTargetApi. Picker not integrated |
| iOS local form-test delta | Targeted 3/3 per language (ru/en), six executions; no destination POST sent |
| Android experimental picker delta | Native 63/63, unit 43/43; targeted controller/lifecycle 10/10; lint only OldTargetApi |
| Android later private-snapshot fix | Native 64/64, unit 43/43; strict private bytes/inode/mtime regression plus real regular-write control |

iOS accepted evidence: `forge-mobile-new-tab-links-20261107-ios-v3` (native) and
`forge-mobile-new-tab-links-20261107-ios-v4` (UI-only test delta). Android stage-4a:
`forge-mobile-new-tab-links-20261107-android-v7`. The current Android OS-link work
is recorded separately in `forge-mobile-external-links-20261107-android-v2`.
That run passed unit checks but lifecycle-dependent native tests failed after
replacement of the Activity's launch Intent. A correction preserves OS launch
filter identity while stripping extras/ClipData/selector/grants, and does not
replace the launch identity for warm entry. Two startup controls passed under
`forge-mobile-external-links-20261107-android-v4-focused`; the full native suite
passed 49/49 in `forge-mobile-external-links-20261107-android-v5-full`.
Its `stage4b-summary.json` records the scope, preserved failures and all 38 verified
Android source files. This validates isolated emulator/Intent/dialog fixtures,
not actual default-browser role selection or physical-device chooser workflows.
The original launch URL may remain in Android's framework/task records; no app
queue, saved session, library or log should be used to persist an unconfirmed URL.
These are local evidence-directory names, not files shipped in this repository.
Earlier failed runs remain preserved; the chronological record is in
`../RELEASE_ROADMAP.md`.

## What this checkpoint contains

- Native tabs/menu, navigation/error states, share/find, bounded bookmarks/history,
  private groups, confirmed downloads/export, site-data clearing and regression tests.
- Native-confirmed HTTPS link opening: iOS filters main-frame GET link requests;
  Android offers a link context action and still denies auxiliary-window requests
  rather than replaying possible form POST requests as GET.
- Draft Android HTTPS ACTION_VIEW entry: explicit confirmation, regular/private
  group preservation, bounded ephemeral pending URL and pause/recreation cleanup.

## Remaining gates

### End-to-end upload follow-up (local, after `7bae3ebde0f`)

A fresh upload-only AVD (`ForgeUpload20261107`, port 5584) exercised a real HTTPS
HTML file input, Forge confirmation, Android DocumentsUI selection and multipart
POST. The fixed 28-byte payload includes NUL/non-UTF8 bytes; the receiver checks
the exact filename and SHA-256. TLS uses a one-day CA trusted only by this new
Gecko profile. An untrusted-CA control and a same-CA wrong-IP-SAN control both
failed closed; production certificate handling is unchanged.

The initial `forge-mobile-upload-e2e-20261107-android-v1` preserved two harness
failures (uppercase native-button selector and incomplete NSS DB transfer), then
passed regular upload/cancellation but FAILED private storage invariants: regular
session bytes were unchanged, yet its inode/mtime changed. `persistSession()`
unconditionally rewrote the regular snapshot on private actions and picker
backgrounding. It now skips unchanged regular encodings, retaining its marker
across Activity recreation and updating it only after a successful save.

The deterministic private lifecycle regression passed 1/1, including inode/mtime
checks across recreation/background and a real regular-edit save control. The
complete `forge-mobile-private-snapshot-20261107-android-v2-full` snapshot passed
native 64/64, unit 43/43 and lint with only OldTargetApi. APK SHA-256:
`ff2350deef8ff8bdebd378a742720eb6fed744df93a03202776afdd62c7ad250`.
The corrected `android-v2` E2E snapshot passed regular, cancellation and private
cases with unchanged private-session/library bytes/inode/mtime. A final E2E
recheck `forge-mobile-upload-e2e-20261107-android-v3` counts every POST attempt,
including rejected bodies, rather than only accepted receipts; it passed all
three cases with the same APK hash. No POST attempt occurred on cancellation.

Source checks passed Python 106/106, Node 56/56, compileall and whitespace checks
(`forge-upload-e2e-20261107-source-v1`). A separate manual-only iOS upload UI
scheme remains a local, uncommitted experiment for default WebKit Files-panel
cancellation, separate from this accepted Android source delta. The first
`forge-mobile-upload-e2e-20261107-ios-v1` run FAILED 0/1 after opening the actual
Files panel: its selector expected a Browse navigation title, but Files exported
`Browse View (Picker)` with `FullDocumentManagerViewControllerNavigationBar` and
the Recents tab selected. The selector now targets that real picker and its
scoped Cancel button, retaining panel/cancellation/no-POST assertions and all
timeouts. The next `ios-v2` attempt was blocked by host load before simulator
creation or xcodebuild; it is not a test result. The `ios-v3` run was interrupted
by a harness/server restart after test start; its xcresult has no final Info.plist
and is not accepted. Its orphaned owned simulator was shut down after confirming
that no fixture/xcodebuild worker remained. A v4 launch was load-blocked before
root/simulator creation (follow-up load receipt: 14.05 on eight logical CPUs).
Failed attachments/video, interrupted bundles and blocked receipts remain
preserved. Available
runtimes are 26.0/26.4/27.0/27.1, not 17 or 18.4; no runtime was downloaded, no
deployment target was raised and no custom iOS upload guard is claimed.

### Experimental picker integration — local automated scope

After the accepted Android 53/53 staging/navigation snapshot, a local
`BrowserUploads` coordinator was connected to Gecko FilePrompt. It uses native
confirmation and ACTION_OPEN_DOCUMENT, accepts one read-only content URI, queries
only DISPLAY_NAME and copies its stream before confirming Gecko with the owned
file path. Camera, folder and multiple-file prompts are rejected. Gecko does not
expose a requesting-frame origin here; the confirmation explicitly identifies
the top-level page and warns that embedded frames may receive the file.

Completion is tied to the selected session, document address and navigation
version. Codes are not reused during the process lifetime. Copies are retained
until engine closure; upload-bearing engines unload when leaving the tab/app,
on manual address navigation, reload or configuration destruction. Startup
cleanup removes only bounded UUID-owned entries without following symlinks;
unexpected entries disable uploads. A process-global single worker and streaming
limit bound resources. The 60-second copy budget is cooperative, not a guarantee
that a malicious provider's blocking query/read can be interrupted.

`forge-mobile-file-picker-20261107-android-v1-focused` passed APK/test-APK build,
43/43 unit tests and lint (only OldTargetApi), then was blocked by the host-load
guard before emulator launch. The next `android-v2-focused` snapshot passed
9/9 native controller/lifecycle tests, unit 43/43 and lint with only OldTargetApi.
Review then added session-scoped cancellation on document start, including
same-URL reloads, and a tenth native regression. The resulting `android-v3-focused`
snapshot passed native 10/10 and unit 43/43. The complete `android-v4-full`
snapshot then passed native 63/63 and unit 43/43, lint only OldTargetApi.
APK SHA-256: `2e0b271f228ad6800161f595bbe778d83fd91fe3be3758f0d56c819e6d1404b6`.
APK manifest inspection confirmed the fixture provider
is absent from the browser APK and present only in the test APK. These controller fixtures use synthetic Gecko
prompts and a test-only fixed-byte provider; they do not establish real HTML file
input, OS document-grant or server multipart interoperability. This is a
source-only development checkpoint, not a binary release or daily-use claim.

The isolated iOS forms run `forge-mobile-forms-20261107-ios-v2` passed all three
tests in each of ru/en (six executions). This does not validate iOS file pickers
or change iOS 17 support. The prior load-blocked `ios-v1` launch remains retained.

### Local forms/upload work after the pushed OS-link checkpoint

At the initial staging checkpoint, the core was not connected to Gecko's file
prompt or a document picker. Its 32-MiB streaming cap, owner-only private-cache copies, safe filenames
and cleanup leases passed nine host tests and three Android native tests. The
first complete staging snapshot nevertheless FAILED 51/52 native checks:
`anotherIntentCannotReplaceTheAddressBehindAnOpenConfirmation` observed a late
startup `about:blank` replacing the requested address. Its evidence remains in
`forge-mobile-upload-staging-20261107-android-v1`.

The navigation correction separates requested and observed document addresses,
ignores startup-blank progress while awaiting explicit navigation, and records
history only for an observed document. A deterministic regression also checks
that explicit blank navigation still works. The first targeted run FAILED 1/2:
the loading button was not refreshed synchronously after address submission.
That assertion was retained and production control refresh corrected; the next
targeted run passed 2/2 with unit 40/40 and only OldTargetApi lint warning
(`android-v2-focused` and `android-v3-focused` respectively, under the same
`forge-mobile-upload-staging-20261107-` prefix). The complete `android-v4-full`
snapshot then passed native 53/53 and unit 40/40, with only OldTargetApi lint.
Its APK SHA-256 is
`a7d28b2c820bae9d792f5b40e491fb9e7fd93171ebddd8f5eb3c2d2a92522b3c`.

Source checks for the staging delta passed Python 97/97, Node 56/56, compileall
and diff whitespace checks (`forge-upload-staging-20261107-source-v1`). The later
picker source checks passed Python 98/98, Node 56/56, compileall and whitespace
checks (`forge-file-picker-20261107-source-v1`). The three iOS local-form tests
cover required-field/POST policy, private storage exclusion and cancellation of
new-window POST without GET replay; their accepted run is recorded above. Destination
requests are cancelled by a test observer; these are not end-to-end server or
file-picker checks. Their first preflight (`forge-mobile-forms-20261107-ios-v1`)
was blocked by the host-load guard before simulator boot or xcodebuild. This is
not a test failure or pass; the blocked receipt and process diagnostic are kept.
Custom WebKit open-panel interception requires iOS 18.4;
the project still supports iOS 17 and older-system Safari-style default behavior
must not be described as custom-guarded upload handling.

- Actual Android OS chooser/default
  browser and real-site long-press/target=_blank interoperability.
- iOS generic HTTPS OS delivery: default-browser entitlement/provisioning is not
  configured, requested or validated. No fake https URL scheme is registered.
- Forms/file uploads, additional recovery/download/site-settings work and desktop
  hardening/security-update infrastructure remain on the roadmap.
- Physical-device privacy, capture, OS permission dialogs, direct networking and
  Files-provider workflows are not established by simulator/fixture checks.

TestFlight 0.1.0 (5) and existing public packages are separate frozen artifacts;
they do not contain these later source changes. No private keys, credentials,
profiles, app binaries, generated projects, caches or raw device logs belong in
this source checkpoint.
