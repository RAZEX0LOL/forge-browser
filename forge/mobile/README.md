# Forge mobile prototypes

See [SOURCE_CHECKPOINT.md](SOURCE_CHECKPOINT.md) for the 2026-11-07 source-push
scope, accepted checks and pending Android OS-link validation. Publishing these
sources does not replace TestFlight build 5 or any existing public package.

These are **new, minimal mobile applications**, not a port of the desktop XUL
interface, not Firefox/Fenix with a changed name, and not stable browsers.

## Unreleased local development

The next mobile-first product increment adds a dedicated native text-only tab
overview and a separate browser menu on both platforms. Search matches titles/URLs
within the current group; rows close independently, regular/private modes are
explicit, closing the private group requires confirmation, and the last closed
tab becomes a blank tab. Closing from the overview does not auto-load a saved
neighbor. Private overview uses an inactive-content cover on iOS and FLAG_SECURE
on Android; no tab screenshots/favicons are fetched or saved for previews.
Media requests are blocked/cancelled while the overview is open, and granted media
pages unload on entry. These changes are local and NOT in TestFlight build 5.
Runtime validation is in progress. The complete product backlog (navigation,
bookmarks/history/share/find, links/forms, recovery, downloads/settings, desktop)
is tracked in `../RELEASE_ROADMAP.md`; it is not claimed implemented yet.

The tab-overview stage subsequently passed iOS full ru/en 38/38 each and UI 6/6
each (plus a separate focused UI check), Android 26/26 native +12/12 unit and 90
source checks. Earlier failed iterations are preserved; see the roadmap.

The next local navigation increment adds explicit address-edit cancellation,
stop/reload state, page progress and fixed localized network/timeout/security
messages without raw sensitive error strings. Cancelling an edit does not submit
or save the draft. TLS/Safe Browsing behavior stays native. Android's informational
status text is hidden rather than permanently consuming page space; errors and
storage failures stay visible. Navigation validation is in progress, separate from
tab-overview results, and these changes are NOT in uploaded TestFlight build 5.

Navigation acceptance subsequently passed: iOS full ru/en 43/43 and UI 7/7 each;
final Android 29/29 native, 18/18 unit; Python 91/91. Exact stage snapshots remain
separate from later source changes.

Share/find is the next local increment under validation: native system sharing
of a validated HTTPS link, an extra warning before private-link sharing, native
WKWebView/Gecko find APIs, and ephemeral Android query/highlight cleanup on leaving
the page/app. Sharing always needs the user's destination choice; tests do not send
to recipients. No automatic website request is used to prepare a share action.
Bookmarks/history remain pending, and this increment is not in TestFlight build 5.

The latest share/find iOS full ru attempt failed 45/47: native cookie clearing
did not complete within its deadline, cookie postconditions failed, and the next
tab-close test was also blocked (consistent with the pending process-wide clear).
UI/en phases did not run. Production guards were not reset or weakened; a separate
two-test iOS26.4 control with test-only diagnostics is pending. Earlier Android
share/find checks passed 31/31 native and 21/21 unit; they do not validate this iOS
failure. All reports remain separate in the roadmap.

Library storage models and test scaffolding have been added locally (500 history,
200 bookmarks, separate bounded atomic file, private-write rejection and corrupt
file protection), but are not yet compiled/runtime-validated or connected to UI
and visit recording. Do not treat them as working bookmark/history features.

Subsequent local work connected the library UI and visit hooks on both platforms.
Only successful regular visits are eligible; private visits/bookmarks are rejected.
History and bookmarks have separate limits (500/200), searchable native lists,
explicit row opening/deletion and cancel-first history clearing. Site-data clearing
keeps library entries and says so. Storage failure preserves old data and shows an
unavailable/read-only state; no corrupt-file repair is automatic.

Android integration passed 36/36 native and 27/27 unit, lint 0 errors/OldTargetApi.
The separate iOS26.4 native-clear control passed 2/2 (callback took 48.239s), not a
replacement for the failed full iOS27 run. Focused library model/store/integration
and real menu/search ru/en checks passed on iOS26.4: 10 native +1 UI per language,
22 focused executions. These are not the full 57-native/9-UI suite; full iOS acceptance and
physical-device validation remain open. Host-only Java 9/9 and Swift/Foundation
6/6 checks are not mobile UI or OS data-protection acceptance. Nothing after
TestFlight build 5 has been uploaded.

Latest library evidence: `forge-mobile-library-20261106/stage3b-summary.json`.
Both platform source snapshots still match the working tree. A fresh integrated
iOS baseline is required before stage-4 new-window changes; the earlier failed
iOS27 clearing run remains open, independently of focused iOS26.4 successes.

The subsequent integrated iOS27 baseline passed **57 native +9 UI per language**
(ru/en, 132 successful executions, zero failures), with all 35 source hashes
matching the working tree. Native clearing completed in 4.023s/2.197s and released
the process-wide gate. Evidence: `forge-mobile-library-full-20261106-ios-v1/`.
This validates current integrated simulator sources; the earlier failed run is
preserved and its timeout cause remains unproven. Physical-device checks remain
pending. Next: gated explicit new-tab links, then OS URL entry/forms/files.
No new TestFlight upload or publication occurred.

### New-tab links (local, 2026-11-07; validation pending)

iOS now offers a cancel-first native confirmation for HTTPS main-frame GET links
requesting a new window. Forms, automatic window.open and unsupported schemes
are not replayed. A confirmed address opens in a fresh native tab in the current
regular/private group, with no opener, subject to the 32-tab bound and active
source/window checks. Native confirmation also prevents synthetic anchor clicks
from creating tabs without a user decision.

Android adds Open link in new tab to HTTPS link context menus, with explicit
confirmation and stale-source/background checks. TARGET_WINDOW_NEW requests stay
blocked: Gecko does not expose their HTTP method/body, so replaying them as an
address could break POST forms. Automatic target=_blank compatibility is not yet
implemented on Android. Both implementations are local and not yet runtime
accepted; six new iOS/five Android native regressions are awaiting validation.
Forms/file uploads and OS URL entry remain separate pending work. No upload/push.

Validation found two Android fixture prerequisites: wait for Gecko's initial
local blank navigation before injecting a source callback, and wait for the link
dialog's real window-focus event before programmatic clicks. Production source
and focus guards remain unchanged; the latest full run is still FAILED40/41.
On iOS, private activity was rewriting the unchanged regular JSON snapshot;
no-op saves are now skipped, retaining the strict file-byte regression and adding
inode/mtime checks plus a regular-write control. Fresh iOS full ru/en 64+9 checks
are running; stage-4a is not accepted yet. Failed results remain in the roadmap.

Stage4a subsequently passed its local automated acceptance: iOS native64/64 per
language (v3) plus UI9/9 per language (v4),146 executions across separate runs;
Android41/41 native +27/27 unit, lint only OldTargetApi. The accepted iOS runs differ
only in the UI test's explicit state wait. All36 iOS/35 Android working source
hashes match the accepted snapshots. Earlier failed runs remain preserved.
Evidence: `forge-mobile-new-tab-links-20261107-stage4a/stage4a-summary.json`.
These fixture/helper/dialog checks are not comprehensive real-site target=_blank
or long-press testing, and no physical device was used. Android auxiliary-window
requests remain blocked; use the explicit link context action. OS HTTPS URL entry,
forms and uploads remain pending. No new TestFlight upload, publication or push.

### Incoming OS links (Android local; validation pending)

Android can receive HTTPS ACTION_VIEW addresses on cold/warm entry. A cancel-first
native prompt must be confirmed before a fresh tab is loaded; it preserves the
current regular/private group and tab bound. Only the validated address is used,
not extras, app-provided headers, files or form data. Pending URLs are in memory
only, dropped on pause, and not replayed on recreation. Duplicate Intents cannot
replace a visible prompt's address. The OS/other apps may retain the original link;
private mode cannot erase those copies. No default-browser role is requested.

Four unit/eight native regressions are added; full31-unit/49-native validation is
pending. This new Android delta is not covered by the earlier stage4a snapshot.
iOS generic HTTPS delivery remains gated on Apple's default-browser entitlement
and provisioning; no fake https URL scheme, entitlement request or upload was added.
Forms/file uploads and real-device OS chooser workflows remain unverified.

The working sources now add native tab creation/selection/closure (up to 32),
independent live engine sessions and versioned atomic persistence of tab URLs,
titles and selection. Cold launch restores the list without navigating saved
remote pages; Reload or explicit tab selection loads them. In-memory history is
retained while a tab's engine instance remains alive. History/form-state recovery
after process termination is **not** implemented. Invalid/future saved files are
left untouched and persistence failures are shown in the UI. iOS storage is
file-protected and excluded from backups; Android uses private no-backup storage.

Local changes do not alter published APKs or the landing page. Internal TestFlight
build 3 contains the earlier tabs/download increment, not the subsequent UI or
private-browsing work. Validation and a separately approved release are required
before claiming later features for downloadable builds.

### Private tab groups (local, 2026-11-01)

Both mobile engines now have a separate in-memory private tab group and explicit
mode/group-close controls (up to 32 tabs per group). Only regular snapshots reach session storage. Android
uses native Gecko private mode; iOS shares an ephemeral WebKit data store between
private tabs and replaces it when the group is closed. Private downloads are
unavailable in this increment. Android blocks screenshots in private mode; iOS
covers private content when inactive but cannot prohibit user screenshots.
These are local sources, not a published build. See `../RELEASE_ROADMAP.md` for
validation and remaining platform gates. Private mode is not network anonymity.

### Site-data clearing (local, 2026-11-01)

The tab menu offers a separate confirmation for clearing cookies, engine caches
and website storage. It affects all currently registered app windows, unloads
their engines, closes private groups and cancels downloads. While a system export
picker or file-copy operation is active, clearing is refused; exported files are
never deleted. Regular tab IDs/addresses/titles remain, and no saved remote page
is automatically loaded after clearing. This is not browsing-history deletion or
secure erasure, and OS permissions/password stores are not reset.

Android requests COOKIES, ALL_CACHES, DOM_STORAGES and AUTH_SESSIONS from Gecko's
StorageController, not its broad ALL flag. iOS uses WebKit's allWebsiteDataTypes,
then checks remaining records and cookies because its deletion callback has no
error parameter. Navigation/tab mutations are blocked process-wide until the API
finishes. Failures remain visible and can be retried; corrupt session files are
not replaced. Completion is not a durable background job: killing the app during
clearing may leave partial results, so repeat the confirmed operation after
restart. Isolated validation passed 17 Android native tests and 22 iOS simulator
tests (excluding the network-dependent iOS download test), plus 9 Android unit
tests. Physical-device validation remains separate. No downloadable build includes
this increment yet.

Internal TestFlight **0.1.0 (3)** was subsequently uploaded with these local mobile
changes after the iOS suites passed 13 tests in each language. Build 2 and public
downloads remain unchanged. Build 3 is available through the existing internal
group, not submitted for external review; see `../RELEASE_ROADMAP.md` for exact
validation scope, simulator-network workaround and remaining device/export checks.

### iPhone interface refresh (local, 2026-10-31)

The current iOS sources replace the empty white tab with a native dark start page,
move the address field and navigation into a bottom dock, give the address field
explicit readable colors and horizontal priority, and keep controls at least 44 pt.
The dock follows UIKit's keyboard layout guide; editing hides the navigation row,
and the start page supports interactive keyboard dismissal. Restored remote tabs
have a native explicit-load placeholder, never an automatic startup request.
Normal informational status text is hidden; errors and storage warnings remain
visible. Actual website content is not recolored or injected with theme CSS.

This refresh is **not in TestFlight build 3**. Screenshot review and new UI/layout
tests are local work; no subsequent TestFlight upload is authorized by the visual
feedback alone. Earlier functional test counts are not evidence of visual quality.

### Local download implementation

The working sources now handle Android GeckoView external responses and native
WKWebView downloads. They use the engine's existing response/session rather than
re-fetching URLs in a separate HTTP client. Downloads require confirmation, allow
only credential-free HTTPS, keep platform certificate validation, sanitize bounded
filenames and accept one pending file at a time. The file-size limit is 256 MiB.
On iOS, progress updates trigger cancellation if that limit is exceeded, and the
completed file is checked again before export; native buffering can exceed the
threshold before cancellation is delivered.

Files are staged in private, non-backed-up cache storage, not directly in a public
Downloads folder. Android exports through `ACTION_CREATE_DOCUMENT`; iOS uses an
export-only Files document picker. The person chooses the destination and resolves
name collisions using the system UI. No file or external application is opened
automatically. A failed Android export keeps the staged source for explicit retry;
removing a partially written provider document is best-effort.

Transfers cancel when the app enters the background (Android configuration changes
retain the transfer). Ready staged files remain available for explicit export while
the process lives. There is no background download service, durable download queue,
resume after process death, automatic retry, blob/data download support or popup
download support. Partial/staged leftovers are cleaned on the next process start;
the OS may also evict cache files. Existing published downloads still have no
download UI. Native runtime/export validation of this increment is tracked in
`../RELEASE_ROADMAP.md`, separately from earlier tab/session results.

Network-dependent download tests use the small public HTTPS checksum fixture at
`https://razex.shop/forge/SHA256SUMS`. Android's host export check pins its byte
count and SHA-256, then drives the native confirmation and system document picker:

```sh
python3.12 tests/download_export.py --adb "$ANDROID_HOME/platform-tools/adb" \
  --serial emulator-5580 --output /path/to/new-download-export-results
```

Run this command from `android/` on an isolated Forge AVD with the debug APK
installed. It creates a uniquely named test file and removes only that fixture
after checking its contents. HTTPS/network failures fail the tests rather than
being skipped or bypassing certificate checks. iOS performs a separate native
HTTPS HEAD probe in its download test to distinguish connectivity failure from
WKDownload integration failure; the application itself does not re-fetch files.

| Project | Engine | Initial scope |
| --- | --- | --- |
| Android | Mozilla GeckoView `159.0.20261022150525` | HTTPS navigation/search, back/forward/reload, native address field, ru/en strings |
| iOS/iPadOS | Apple's system WKWebView | HTTPS navigation/search, back/forward/reload, native address field, phone/tablet layout |

Both start without remote page navigation and reject active/local/external URL
schemes and credential-bearing URLs. Neither overrides certificate failures.
This is not a claim that the underlying engine or OS sends no background traffic.
HTTP is deliberately unsupported in these initial prototypes. Search goes to
DuckDuckGo only when the person submits a search. Popups, general site-permission management,
password management, extensions, workspaces, desktop themes, browser sync and full
history/form-state recovery are not implemented. Data is local to the
app; Android backup is disabled. No telemetry SDK is added, but these apps have
not received a full engine/network privacy audit. Desktop privacy claims and
test counts must not be applied to them.

### Camera/microphone permissions (local, 2026-11-01)

Local sources add a deny-first site confirmation for camera/microphone and a
separate OS-authorization gate. Dialogs show a canonical HTTPS origin (not page
titles, paths or query strings). Only the selected foreground tab and same-origin
frames qualify; cross-origin iframe requests, stale documents, unknown Android
OS permissions and unsupported capture sources are rejected. Android also
requires Gecko's secure/non-exception security information. iOS uses public
WKUIDelegate and AVFoundation APIs, with localized camera/microphone usage strings.

Only one request per controller is pending. Navigation, tab/mode changes, data
clearing, backgrounding and controller destruction invalidate pending requests;
late OS results cannot grant access to a replacement page. Granted media pages
are unloaded when left or backgrounded, retaining only the existing safe URL
snapshot; reopening requires explicit navigation. This deliberately interrupts
calls when switching tabs/apps, rather than offering background capture.

Forge does not add a persistent site-consent database. OS permissions remain
application-wide, including outside private mode, and clearing website data does
not revoke them. WebKit/Gecko may keep document-scoped media state until unload.
Geolocation and other site capabilities remain separate work: Android content
permissions are denied, iOS motion is denied, and the public per-site location
delegate is denied on iOS 27+. Older iOS versions have no Forge location grant or
custom per-site location UI. No location usage authorization is enabled here.

Local validation passed 22 Android native tests, 12 Android unit tests, 29 iOS
simulator tests and 88 Python source/resource checks. Android lint has no errors
and the known OldTargetApi warning. The network-dependent iOS download test was
excluded, not counted as passed. Permission-flow tests inject OS outcomes and do
not prove physical camera/microphone capture, hardware release,
real OS-dialog behavior, WebRTC calls or privacy indicators on actual devices.
Those remain release gates. No upload/distribution is part of this increment.

### Keyboard test host and real-window UI checks

The keyboard unit test borrows the active scene's existing normal key window,
restores its original root controller afterward, and waits for keyboard hide
before restoring the host. It retains the first-responder and above-keyboard
geometry assertions, with diagnostic attachments that exclude entered text/URLs.
An additional `ForgeMobileKeyboardUI` scheme tests actual taps and typed text in
the unmodified SwiftUI app window, rather than constructing a competing window.
Run only on an explicitly selected isolated Forge simulator:

```sh
xcodegen generate
xcodebuild -project ForgeMobile.xcodeproj -scheme ForgeMobileKeyboardUI \
  -destination "platform=iOS Simulator,id=$FORGE_SIMULATOR_ID" \
  -testLanguage ru -testRegion RU -parallel-testing-enabled NO \
  FORGE_UI_TEST_LANGUAGE=ru CODE_SIGN_IDENTITY=- test
```

Use `en`/`US` for the English run. Whole-xcodebuild deadlines must allow cold
runner startup; the keyboard event itself still has a 30-second test deadline.
Final ru/en runs passed all three fixed repetitions: 180 full-test executions
(30 tests per language) and 12 UI executions (two tests per language), with zero
failures. These host changes remove a potential race, not proof of the exact
cause of the earlier first-responder failure. Production Sources remain unchanged;
see the roadmap and local `focus-investigation-summary.json` for exact evidence.
Previous signed candidates and blocked reports are not silently replaced or
automatically cleared for upload by this investigation.

**Later build-5 check:** fresh ru validation failed (29/30) on duplicate keyboard
expectation fulfillment; en/UI phases did not run. The historical green results
above are not a passing build-5 candidate report. The corrected test-only observer
consumes the first matching event and unregisters before its callback, including
for hide cleanup. Two new regressions cover duplicate/reentrant/cancelled events.
Separate `forge-device-candidates-20261101-v5-qa2` records the test-only hash delta;
32-test full ru/en and two-test UI ru/en checks are pending. Failed v5 evidence,
signed packages and the original blocked build-4 kit are preserved. No TestFlight
upload has occurred.

The QA2 process was interrupted by a harness server restart (incomplete xcresult;
no completed tests reported). On 2026-11-05, the identical hash-verified snapshot
was restarted separately as `forge-device-candidates-20261105-v5-qa3` for all four
ru/en full/UI phases. Interrupted and failed runs remain preserved.

QA3 subsequently failed to launch its runner (`Host is down`; zero tests executed),
not a keyboard assertion result. After rebooting only the isolated Forge simulator,
SpringBoard and direct Forge launch/termination preflights passed. One new run in
`forge-device-candidates-20261105-v5-qa4` is pending with unchanged frozen sources;
all older failed/interrupted evidence remains preserved. No automatic retry loop.

QA4 failed full ru (31/32): keyboard did-show arrived 34.623 seconds after the
focus request returned, exceeding the unchanged 30-second wait. Focus/key-window
ownership remained intact at did-show and layout; both new notification regression
tests passed. en/UI phases did not run. Post-run high host load suggests, but does
not prove, environment slowdown. Candidate remains blocked; no automatic rerun,
timeout relaxation, finalization or upload. Exact evidence: local QA4
`qa4-failure-analysis.json`.

At the user's request, QA5 repeated the unchanged tests with host-load sampling.
Full ru failed 31/32 on HTTPS preflight timeout (-1001), before exercising the
download body; en/UI phases did not run. Keyboard passed (did-show after 3.780s),
including focus/geometry, and both notification regressions passed. In-run load
peaked at 113.87 on eight logical CPUs. A later host request also timed out before
TCP connection, but subsequent direct and restricted-relay probes returned 200
without weakening TLS. Neither transient network nor host-load causality is
conclusive. Further full runs are paused while host load remains high; the
candidate remains blocked. Local QA5 analysis and all earlier failures are kept.

**Latest status — QA6 (2026-11-05):** full ru/en each passed 32/32, UI ru/en each
passed 2/2: 68 successful executions, zero failures/skips, without timeout changes
or automatic retries. Separate finalized local kit:
`forge-device-candidates-20261105-v5-qa6/artifacts` (next to the workspace).
All 12 checksum-covered files and package signatures verified; old blocked v4 kit
remains unchanged (10/10 hashes). Includes iOS 0.1.0 (5), three byte-identical v5
debug APKs, corrected QA6 source archive and an explicit test-only delta/report.
Historical Android checks and earlier failed/interrupted QA are kept distinct
from fresh QA6 results. Workspace source checks also passed 89/89.

This kit passed local automated validation, not physical-device acceptance. Older
focus/network/runner failure causes are not conclusively established. iOS IPA is
for App Store Connect processing, not direct install. No upload occurred; separate
approval and build-number availability check are required. Real iPhone/Android
media, privacy indicators/hardware release, networking and Files export still need
the DEVICE_TESTING.md checks. See the kit's CANDIDATE_STATUS.md and QA-REPORT.json.

**Subsequent authorized action (2026-11-05):** the user approved uploading build 5
to TestFlight. App Store Connect preflight confirmed the expected app/bundle and
an unused build number; Apple validation/upload is running on the exact QA6 IPA.
Completion/processing remains pending. Receipts are separate in
`forge-testflight-20261105-build5`; frozen kit manifests retain their creation-time
not-uploaded state. Existing internal group access may be automatic after processing;
no external submission, invitations or manual notifications were requested.

**Upload outcome (2026-11-05):** Apple validation and upload both returned exit 0.
A post-upload API transport error did not trigger another upload. Read-only status
then confirmed **0.1.0 (5): VALID, IN_BETA_TESTING**, not expired; marketing version
was checked via preReleaseVersion. No external submission or manual notification
was sent. Apple's `autoNotifyEnabled` is true, so automatic notifications may occur.
Exact beta-group membership was not separately confirmed (GET_RELATED unsupported);
no group access changes were made. Sanitized receipts/status are in
`forge-testflight-20261105-build5`. Frozen kit manifests remain historical snapshots.
Next: real iPhone/Android checks in DEVICE_TESTING.md; those are not yet validated.

### Local device-test candidates (2026-11-01)

Device candidates are staged outside the repository in
`forge-device-candidates-20261101-v4/artifacts` under the maintainer's local build
folder: three Android debug APKs and Apple Distribution signed iOS 0.1.0 (4).
The iOS IPA is an App Store Connect export, not a direct-install IPA, and has not
been uploaded or Apple-server-validated. Android packages retain versionCode 1;
identify the exact build by SHA-256, not the prototype version label alone.
Their signing certificate matches the previously tested local debug APKs.

The snapshot preserves all mobile source hashes. Android candidate dex/native
libraries/manifest/resources match the earlier native-tested packages across all
three ABIs; a fresh frozen-source build passed 12 unit tests and lint (0 errors,
the known OldTargetApi warning). The full ru iOS run including HTTPS download
passed 29/30: the keyboard appeared, but the address field lost first-responder
status at the final assertion. A same-snapshot focused control timed out after
300 seconds without a completed summary; full ru/en reruns were not started.
The cause is unresolved. Candidate QA is **BLOCKED**, not cleared for upload.
Reports are retained without weakening the assertion. Package manifests and
SHA256SUMS verify local files, not runtime readiness; see `CANDIDATE_STATUS.md`
inside the artifact folder.

ADB listed no Android devices; CoreDevice records had no connected tunnel. No
physical device was selected for testing and no device app was installed.
Use [DEVICE_TESTING.md](DEVICE_TESTING.md) and the local-only
`fixtures/media-permissions.html` for the separately authorized hardware phase.
The fixture is not deployed, records/sends no media, and does not stop tracks on
visibility events (which would mask a browser lifecycle bug).

## Android

JDK 17, compile SDK 37 (target SDK 35), Gradle 9.3.1, Android Gradle Plugin 9.1.1.
The engine is downloaded over HTTPS from Mozilla's Maven repository and is
independently versioned from desktop Gecko. Its exact source and license notices
are available from the same Maven coordinates (`-sources.jar`) and Mozilla.
The full native engine source revision declared by that version's official POM is
[`5add844c26613d7e4d84c799d6e23cf987b1240d`](https://hg.mozilla.org/releases/mozilla-release/rev/5add844c26613d7e4d84c799d6e23cf987b1240d).
This differs from the desktop source base. GeckoView also has AndroidX, Kotlin,
media and FIDO dependencies with their own applicable licenses; their upstream
notices are not replaced by Forge's MPL notice.
No production signing keys are committed.

```sh
cd android
gradle --no-daemon :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

The resulting APK uses a development/debug signing identity, not a stable
publisher key. A successful compile is not a device or emulator runtime test.
Separate APKs are generated for arm64-v8a, armeabi-v7a and x86_64; choose the
matching ABI rather than downloading every engine architecture in one APK.
Native CI runtime tests currently exercise x86_64 in an Android emulator, not
physical ARM phones. The prototype does not register itself as the default browser.

For local runtime validation, select an isolated emulator explicitly:

```sh
ANDROID_SERIAL=emulator-5580 gradle --no-daemon :app:connectedDebugAndroidTest
```

The host-side process-restart check is separate from Activity recreation. Install
the ARM64 debug APK on a dedicated AVD whose name starts with `forge-` (the Gradle
test task may uninstall the app on completion), then run from `android/`:

```sh
python3.12 tests/process_death.py --adb "$ANDROID_HOME/platform-tools/adb" \
  --serial emulator-5580 --output /path/to/new-process-test-results
```

The check refuses physical devices/non-Forge AVDs, uses native controls to add a
tab, verifies its persisted snapshot after `am force-stop` and a new process, and
checks that a saved remote address waits for explicit reload. It restores the
previous session fixture and leaves the test app stopped. Output includes native
UI XML and a JSON summary. It does not simulate the OS low-memory killer, recover
full history/forms, or capture background network traffic.

Backup remains disabled. Explicit XML exclusions also cover legacy full backup,
Android 12+ cloud backup and device transfer for all supported storage domains;
actual OEM device-transfer behavior still requires physical-device validation.

## iOS / iPadOS

Xcode + XcodeGen, minimum iOS 17. Uses **WebKit**, not Gecko. It is not a claim of
Apple alternative-engine eligibility, App Store review, or iPhone distribution.

```sh
cd ios
xcodegen generate
xcodebuild -project ForgeMobile.xcodeproj -scheme ForgeMobile -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath build CODE_SIGNING_ALLOWED=NO build
```

Simulator `.app` archives cannot be installed as an iPhone IPA. Device distribution
requires an appropriate Apple account, provisioning and signing; no personal
credentials, team IDs or signing material are assumed or uploaded.
The workflow also compiles an **unsigned device `.xcarchive`** for developers.
It is not an installable or App Store-approved IPA and does not bypass provisioning.

The mobile workflow is manually dispatched and uploads only development artifacts,
not automatic public releases. Source is MPL-2.0, with engine/platform licenses
remaining applicable.
