# Mobile source checkpoint — 2026-11-07

This is a development-source checkpoint, not a binary release or daily-use
readiness claim. The owner authorized committing/pushing these sources to the
`forge` branch. That authorization does not include a new TestFlight upload,
release publication, website deployment or Apple capability request.

## Validation scope

| Scope | Latest completed evidence |
| --- | --- |
| Source checks | Node 56/56; Python 98/98; Python compilation and diff whitespace checks passed |
| iOS current production sources | Native 64/64 per language and UI 9/9 per language, 146 executions across separate ru/en native/UI runs |
| Android previous stage-4a snapshot | Native 41/41, unit 27/27; lint only OldTargetApi |
| Android current OS-link-entry delta | Native 49/49, unit 31/31, plus separate startup controls 2/2; lint only OldTargetApi. Earlier failures remain preserved |
| Android local staging/navigation delta | Native 53/53, unit 40/40; targeted regression 2/2; lint only OldTargetApi. Picker not integrated |
| iOS local form-test delta | Targeted 3/3 per language (ru/en), six executions; no destination POST sent |
| Android experimental picker delta | Native 63/63, unit 43/43; targeted controller/lifecycle 10/10; lint only OldTargetApi |

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
