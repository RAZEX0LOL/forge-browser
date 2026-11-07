# Release hardening roadmap

This is an implementation tracker, not a claim that every platform is ready.
Public downloads and the live landing page remain unchanged during local work.
Internal TestFlight build 0.1.0 (3) was uploaded separately as recorded below;
the redesigned iPhone interface and later privacy work are not in that build.

## Cross-platform daily-use gates (2026-11-01)

### Android signed server updates (2026-11-07/08)

The owner requested updates through razex.shop, selecting Android first, then
desktop full-package updates rather than disabling/replacing Mozilla MAR checks.
Android bootstrap v2 preserves the package ID/debug certificate and raises
versionCode to 2. It manually fetches an RSA-3072/SHA-256 signed, expiring,
monotonic feed, restricts APK URLs to the server, verifies streamed size/hash and
installed/archive package/version/certificate, and opens the OS installer only
after consent. No schedule, cookies/history upload, root or silent installation.

Frozen v2: source `49d0031726f33faebc0f77ce6137e3dca06d2f00`, SHA-256
`87e83a323b662754e751acbda0e7e0f0a7ae2824bf21eb6613dc8102bf1932ce`,
198,948,829 bytes. 55 unit/66 native tests passed; only existing OldTargetApi lint.
The full-system API35 flow installed the real public v2 via updater/OS installer
from a test-only lower-version seed, preserving synthetic canary and regular
session bytes. Current-version checking passed and source-install permission was
disabled again via Settings. An immutable HTTPS-fixture test delta then passed
all 66 native tests on the exact same updater-installed APK. Earlier ATD missing-
activity, selectors, startup and foreground failures remain preserved.

Site `20261107-updates-landing-v5` offers v2 and all earlier files; root/Matrix
routes unchanged. Sequence 1 expires 2026-11-20; renewal is explicit offline
signing, not an unattended security-update SLA. Desktop full-package helper is
a separate in-progress stage; historical desktop downloads have no new updater.
iOS remains TestFlight.

### macOS full-package updater candidate (2026-11-08)

The owner chose full-package replacement, starting with macOS, then separate
Windows/Linux work. A small native helper checks a desktop-specific signed feed,
verifies URL/size/hash/ZIP safety and Developer ID/bundle identity/Gatekeeper,
requires a closed browser and separate consent, keeps the old app as a sibling
backup and never accepts a profile path or unattended install flag. Mozilla MAR
and OS trust protections remain unchanged. UI includes localized ru/en update
commands and consent messages; unsupported platforms fail with a localized notice.

macOS v1 was blocked for an SDK-default 27.2 deployment target. v2's final minos
13.0 still concealed newer-OS CGo objects; it was blocked, not signed/published.
The v3 builder pins both CGo compilation/link flags, rebuilds all objects and
rejects mixed deployment warnings. Source native UI's exact action count was
updated from 13 to 14 **and** asserts the new localized update command; earlier
failed QA is preserved, not overwritten or converted into a pass.

Process-guard tests exposed `ps comm` path truncation. The helper now uses native
libproc paths and kernel executable-name fallback for privacy-restricted processes,
without reading argv; possible bundle matches block installation. The owned live-
process test and race-enabled Go tests passed. No root or privileged service.

Candidate v3 was Developer ID signed, notarized once (submission
`3e91d624-12fb-4eab-aea6-76663376d5b9`), stapled and Gatekeeper-assessed.
Signed raw-runtime QA passed 283 checks; the separate native launcher run passed
285, including verified restarts and resource-seal validity. Real extraction and
replacement of two notarized same-build **test copies** passed with a retained
backup and unchanged outside-app canary. This is not newer-version/GUI-consent
installation acceptance. The browser-child lifetime control initially confused
proc_pidpath failure with proof of process exit; that failure is retained. The
corrected control waits for the owned parent Popen and observed app processes to
exit, with the same 30-second deadline and unchanged production bytes. It passed:
actual Firefox blocks replacement, fully closed Firefox permits it, and the
nsIProcess child survives normal browser shutdown. The exact transient PID cause
is not proven; mozprofile interpreter-teardown warnings are retained separately.

Immutable candidate ZIP: `Forge-development-20261108-updater-macos-arm64-notarized.zip`,
168,730,310 bytes; SHA-256
`c3daacee8fd62c7ffa09c74f000e7c0b7c46871fc04611f9605ff1766af2d29d`.
Build number 2026110801, minimum macOS 13 declared; actual macOS13 runtime is not
available locally. Server staging is not public activation. Windows/Linux and
native Intel release validation remain separate gates.

The added macOS15 CI then rejected v3: an unrelated closed-directory process
guard was blocked by an unidentified process. That CI failure is retained and
the v3 ZIP is **not** activated. A correction adds a public read-only kernel
name/state fallback when both libproc path and identity are restricted. It never
reads argv or ignores unidentified live processes; existing guard assertions
remain intact. Fresh CI and a newly numbered/signed candidate are required.

### New release/site authorization and build-6 QA (2026-11-07)

The owner explicitly authorized all source pushes, a new TestFlight release and
deployment of the browser/download website. This supersedes earlier source-only
publication limits for these actions, not Apple capability requests or claims
of physical-device/daily-use readiness. Existing build-5 artifacts stay frozen.

Current iOS sources passed build-6 candidate QA under
`forge-testflight-20261107-build6-qa1`: native 67/67 and UI 9/9 in each ru/en,
152 successful executions with no skips. The corrected standard Files-panel
test then hit a runner startup abort before any test method (`ios-v5`): the main
thread was loading UIKit accessibility, and XCTest's stall handler aborted.
An explicit same-compiled-binary `test-without-building` control on that owned
simulator passed 1/1 with no POST (`ios-v6`). Original failure and crash report
remain preserved; green control does not prove the underlying stall cause.

Read-only ASC preflight confirmed latest build 5, build-6 availability, an internal
all-builds group and an external group with its public link disabled. Build-6
archive preflight was initially load-blocked before root or archive creation.
After load subsided, the frozen candidate was signed, Apple-validated and uploaded
once: 0.1.0 (6), VALID, internal IN_BETA_TESTING, external BETA_APPROVED. Build UUID
`b5e82a2e-15f3-450f-b8c3-9668b4921ef3`; IPA SHA-256
`1e04e71b7ab0fbfb2a22a29d3036ed781b3a05468e7060ffd47327d84eefab76`.
Build 6 is assigned to the externally approved group with public enrollment:
https://testflight.apple.com/join/4hvp4sk8. Public landing and group membership
were independently verified. ru/en-US beta descriptions and build notes were
updated; review contact unchanged, no manual invitations/notifications sent.

A newly named current Android ARM64 APK is published on the website:
debug signing/versionCode 1 disclosed, accepted SHA-256
`ff2350deef8ff8bdebd378a742720eb6fed744df93a03202776afdd62c7ad250`.
Its first SCP timed out after 194,534,400 of 199,182,256 bytes; that partial was
preserved, the local prefix matched, and an append/resume completed with the full
expected SHA-256. No incomplete file was publicly exposed.

The refreshed https://razex.shop/forge/ is active as `20261107-landing-v3`.
Ten static files were verified byte-for-byte; three local downloads passed
server hashes and HEAD/range checks. Previous release and all old filenames are
retained, root/Matrix discovery responses unchanged. nginx configuration and
services were not changed/reloaded. Source-only earlier limits are historical;
this release does not establish physical-device or production readiness.

### Real upload-form follow-up (2026-11-07; local, after `7bae3ebde0f`)

The dedicated upload AVD now exercises a real HTML file input, native consent,
Android DocumentsUI selection and HTTPS multipart POST. The fixed 28-byte binary
fixture is validated by exact name/bytes/SHA-256. A one-day CA is confined to the
new isolated Gecko profile; both untrusted-CA and wrong-IP-SAN controls reject
the connection. No production trust/TLS settings or personal profiles changed.

Preserved `forge-mobile-upload-e2e-20261107-android-v1` evidence includes a native
uppercase-selector failure, an incomplete NSS DB transfer (cert9 without the
modified key4) and a real private-storage invariant failure. Private POST bytes
were correct, but unchanged regular-session contents were rewritten, changing
inode/mtime. The fix skips unchanged regular encodings and retains the last
successful marker across Activity recreation. The strict assertions were kept.
Its deterministic regression passed 1/1 with a positive regular-write control;
the complete `forge-mobile-private-snapshot-20261107-android-v2-full` passed native
64/64 and unit 43/43, lint only OldTargetApi. APK SHA-256:
`ff2350deef8ff8bdebd378a742720eb6fed744df93a03202776afdd62c7ad250`.

Corrected E2E `android-v2` passed regular, cancellation and private cases; session
and library bytes/inode/mtime remained identical during private upload. Final
recheck `forge-mobile-upload-e2e-20261107-android-v3` strengthened the cancellation
oracle to count **all** POST attempts, including rejected requests, instead of
accepted receipts alone; all three cases passed with the same APK hash.
Python source checks passed 106/106, Node 56/56, compileall and whitespace checks.
The isolated iOS27 default-panel check FAILED 0/1 after successfully opening the
real Files picker: a Browse-title selector did not match its Recents view. The
saved AX hierarchy identifies the actual picker/navigation bar; the corrected
test scopes Cancel to those elements and keeps all original assertions/deadlines.
Its next preflight was blocked by host load before simulator creation/build.
The v3 test was then interrupted by a harness/server restart, with an unfinished
xcresult and no test result; its owned orphaned simulator was shut down. A v4
launch was again load-blocked (follow-up receipt: 14.05 on eight logical CPUs).
The corrected iOS UI scheme/test remains local and uncommitted, separate from
the accepted Android delta. Failed, blocked and interrupted evidence is retained.
Exact iOS17/18.4 runtime validation is blocked by unavailable runtimes;
support target remains 17 and no custom open-panel interception is claimed.
No newer TestFlight build, public package or deployment was authorized or made.

### Forms/upload staging checkpoint (2026-11-07; local, not a release)

Latest follow-up: iOS local-form checks passed 3/3 in ru and 3/3 in en under
`forge-mobile-forms-20261107-ios-v2`. No requests reached a destination server.
Android now has an experimental FilePrompt coordinator with local automated checks: native explicit
confirmation, a single read-only ACTION_OPEN_DOCUMENT selection, selected-stream
staging (never provider path resolution), session/document/version checks and
engine-close-before-copy-cleanup lifecycle hooks. The native warning labels the
top-level page, not an unobservable requesting-frame origin. Camera/folder/multiple
selection is rejected. Startup cleanup is bounded and does not follow symlinks.
One process-global copy worker cannot guarantee interruption of a provider that
blocks indefinitely; the 60-second byte-copy deadline is cooperative.

`forge-mobile-file-picker-20261107-android-v1-focused` passed APK/test-APK build,
unit 43/43 and lint with only OldTargetApi, but host-load preflight blocked native
launch. The next `android-v2-focused` snapshot passed native 9/9, unit 43/43 and
lint with only OldTargetApi. Review then added session-scoped cancellation on
document start (including a new document at the same URL) and a tenth regression.
`android-v3-focused` passed native 10/10 and unit 43/43. The complete
`forge-mobile-file-picker-20261107-android-v4-full` snapshot passed native 63/63,
unit 43/43 and lint with only OldTargetApi. APK SHA-256:
`2e0b271f228ad6800161f595bbe778d83fd91fe3be3758f0d56c819e6d1404b6`.
Manifest inspection confirmed that the provider is shipped
only in the test APK, never the browser APK. Real file-input/picker/grant/multipart acceptance
is not established. The existing 53/53 native result below applies only to the
earlier staging/navigation sources; the 63/63 result covers this new integration
within the fixture scope above. This is a source-only checkpoint, not a release.

- Added an Android upload-copy core, not a picker integration: selected streams
  only, no provider `_data` resolution, 32-MiB hard streaming cap, bounded safe
  names, private-cache 0600/0700 permissions and explicit cleanup leases. Host
  tests passed 9/9; Android unit tests passed 40/40 and all three new native
  staging checks passed. Lint reports only the existing OldTargetApi warning.
- Complete `forge-mobile-upload-staging-20261107-android-v1` FAILED 51/52:
  a late initial `about:blank` replaced the address in the existing duplicate
  external-intent scenario. Failed evidence is retained, not accepted wholesale.
- Navigation now distinguishes requested from observed document addresses and
  avoids recording unvisited pages. A deterministic blank-callback regression
  keeps assertions for loading controls, history and explicit blank navigation.
  The first focused run (`android-v2-focused`) FAILED 1/2 because address submit
  did not synchronously refresh the loading button. Production refresh was
  corrected, without removing the assertion or extending deadlines; the next
  focused snapshot (`android-v3-focused`) passed 2/2 and unit 40/40. The complete
  `android-v4-full` snapshot then passed native 53/53 and unit 40/40; lint still
  reports only OldTargetApi. APK SHA-256:
  `a7d28b2c820bae9d792f5b40e491fb9e7fd93171ebddd8f5eb3c2d2a92522b3c`.
- Source checks passed Python 97/97, Node 56/56, compileall and diff whitespace
  checks in `forge-upload-staging-20261107-source-v1`.
- Three iOS form-policy/privacy tests were initially unrun (later ru/en acceptance
  is recorded above). They use
  local HTML and cancel destination requests after observing Forge's decision;
  no fixture credentials are submitted to a server. Custom upload-panel APIs
  start at iOS 18.4; deployment target remains iOS 17. Native provider/picker,
  lifecycle-bound completion and engine-access/lease cleanup remain outstanding.
- The first iOS forms preflight (`forge-mobile-forms-20261107-ios-v1`) stopped
  at the host-load guard before simulator boot or xcodebuild. A follow-up receipt
  recorded load 9.00 on eight logical CPUs, with mediaanalysisd and Raycast among
  the busiest processes. No unrelated process was stopped and the guard was not
  relaxed. This blocked launch is not a form-test result.
- These are later source changes, not TestFlight build 5 or published packages.

### Daily-use product work authorized (2026-11-05)

The owner requested the complete mobile-first improvement program, followed by
desktop hardening. This authorizes local implementation/testing, not automatic
uploads, pushes or public releases. TestFlight build 5 and frozen kits stay intact.

1. **Passed local automated acceptance:** native tab overview + separate browser menu on iOS/Android:
   per-row close, title/URL search scoped to one group, visible regular/private
   switching, group-close confirmation, accessible controls and private previews.
   Text-only rows intentionally avoid screenshot/favicon network or cache storage.
   Closing inside the overview does not navigate a saved replacement tab.
2. **Passed local automated acceptance:** address editing/cancel, coherent navigation/progress/error states.
3. **In progress (share/find first; bookmarks/history pending):** local bookmarks/history, share and find-in-page, with private-data
   exclusion, bounded stores and explicit deletion behavior.
4. **Pending:** user-initiated new windows/tabs, OS URL entry, forms/file uploads;
   retain TLS checks, scheme validation and explicit external-app decisions.
5. **Pending:** engine-process failure recovery and better bounded session recovery;
   never persist private session contents or silently navigate restored URLs.
6. **Pending:** usable downloads management and site settings; background/resume
   must use platform-supported lifecycle/storage and not bypass user consent.
7. **Pending desktop:** shell/native-feature compatibility, upgrade/profile tests,
   security-baseline/update design and platform release gates. Existing Firefox
   features must be preserved; daily-use readiness is not claimed without updates.

Stage 1 currently changes production sources locally and is not in TestFlight 5.
Android initially failed compilation after widening the dialog field type; a local
typed confirmation reference fixed the compile error without changing cancel-first
data-clearing behavior. Rebuild/unit/lint and test APK compilation passed. iOS
full/UI ru/en checks are running against a separate hash-frozen snapshot under
`forge-mobile-tabs-20261105/ios-v1`; Android native checks are not yet complete.
No stage is complete merely because its UI exists; later stages remain outstanding.

Stage-1 runtime progress: Android final rebuild passed 12/12 unit tests, APK/test
APK compilation and lint with only the existing OldTargetApi warning. A freshly
created, isolated Forge ARM64/API35 AVD passed **26/26 native tests**, including
title/URL search, independent close without selection, private-window FLAG_SECURE,
group-isolated results, the 32-tab bound and saved-neighbor no-autoload behavior.
The AVD was shut down; no physical device was used. Python safeguards passed 90/90.

iOS `ios-v1` FAILED full ru 36/37: clearing search synchronously refreshed the mode
control before its new selection was read. The handler now captures/applies the
chosen mode before clearing the query. `ios-v2` passed full ru 38/38, then FAILED
UI ru 4/5 because the test queried a SegmentedControl container absent from UIKit's
exported accessibility tree. The tree contains both real mode buttons under the
table; UI tests now target those buttons without removing the mode assertions.
Search ends on mode switch, and overview exit dismisses the entire presenting
chain rather than only a nested search presentation. Added a real UI search-result
selection/exit scenario. `ios-v3` full ru/en (38 each), UI ru/en (six each) is pending.
All earlier failures are retained under `forge-mobile-tabs-20261105`; none is
reclassified as passed. TestFlight build5 kit checksums remain 12/12 unchanged.

`ios-v3` again passed full ru 38/38, but UI ru FAILED 5/6: the private-group action
was not found after tapping the group control during search. The failed recording
is retained; en phases did not run. The modal UISearchController architecture was
replaced by an inline native UISearchBar so search cannot replace navigation's Done
control or create a nested presentation. Query updates now refresh only matches,
not mode/toolbar state. The long localized private-group action is a separately
labelled trash button in the navigation bar rather than a potential overflow item
beside New tab. All mode/group/exit assertions remain; UI attachments now capture
the post-switch screenshot and accessibility tree. These are design changes under
test, not a proven attribution of the v3 failure. `ios-v4` runs the failing real UI
scenario once first, then full ru/en 38+6 phases only if that focused test passes.

Stage 1 local automated acceptance passed in `ios-v4`: the focused private-mode
scenario 1/1, full ru/en 38/38 each (76 executions), UI ru/en 6/6 each (12 executions).
Android remains 26/26 native +12/12 unit, lint 0 errors/OldTargetApi only; source
checks 90/90. Exact results and preserved failures are indexed in
`forge-mobile-tabs-20261105/stage1-summary.json`. This is not physical-device
acceptance or a new uploaded build. Stage 2 (address cancellation, stop/progress,
actionable errors) starts separately; later product work remains pending.

Stage 2 local implementation: the address action becomes an explicit edit-cancel
control while typing; keyboard Go still submits. Cancel/blur restores the selected
tab URL without persisting the unsubmitted draft. Android Back cancels editing
before navigating. Reload becomes Stop during loading, with per-tab bounded Gecko
progress/state and native WKWebView loading/progress. Late cancellation does not
replace a stopped-state message. Fixed localized error categories distinguish
network, timeout and certificate/security failure, with Safe Browsing distinct on
Android; no raw error description, URL echo, error-page override or trust bypass.
Android routine prototype/loading/ready status text is hidden while failures and
storage warnings remain. No history/bookmark implementation is implied here.

Initial stage-2 Android passed 29/29 native and 18/18 unit, lint 0 errors/OldTargetApi.
A follow-up resets navigation state before an explicit retry (so an early failure
after Stop is not ignored) and makes blank-tab Reload a no-op; its final rebuild
passed 18/18 unit/lint but native revalidation is pending separately in
`forge-mobile-navigation-20261105-android-v2`. Stage-2 iOS full ru/en 43 tests each
and UI ru/en seven each are running in `forge-mobile-navigation-20261105/ios-v1`.
New state/progress/error tests inject engine callbacks or NSError values; they are
not live certificate-failure, real slow-transfer or physical-network validation.

Stage 2 final acceptance passed: iOS full ru/en 43/43 each and UI ru/en 7/7 each
(100 successful executions); final Android-v2 native 29/29 and unit 18/18, lint
0 errors/OldTargetApi only. Python 91/91. Exact evidence is indexed by
`forge-mobile-navigation-20261105/stage2-summary.json`; no upload or physical test.

Stage 3a (share/find) is local and under validation. iOS uses UIActivityViewController
with a validated HTTPS URL only, and WKWebView's native find interaction. Android
uses explicit ACTION_SEND through the system chooser and Gecko's SessionFinder,
with bounded ephemeral query input, previous/next controls and versioned late-result
guards. Android queries/highlights clear on tab/navigation/background transitions;
WebKit owns its native in-memory find state and its navigator closes on tab switch. Private
sharing has an extra cancel-first warning that copies outside Forge cannot be erased;
no recipient is chosen automatically. Tests prepare intents/sheets without sending.
No history/bookmark store exists yet. Initial Android build passed 21/21 unit,
lint 0 errors/OldTargetApi; native 31-test validation is running. iOS hash-frozen
47-test full and eight-test UI ru/en validation is staged under
`forge-mobile-link-actions-20261105/ios-v1`. Native sensor/device/export limitations
remain; API wiring tests do not prove search compatibility with all sites.

Stage-3a Android initial native validation passed 31/31, unit 21/21, lint only
OldTargetApi. A later privacy hardening sets find-query saveEnabled false,
autofill exclusion, no-suggestions input and IME_FLAG_NO_PERSONALIZED_LEARNING;
these are OS requests, not control over third-party keyboards. The follow-up
Android-v2 build was interrupted by the harness's 120-second shell timeout before
Gradle produced a final result. No Gradle process remained; the partial log stays
under `forge-mobile-link-actions-20261105-android-v2`. Post-timeout host load was
60.31/74.18/49.16, so no automatic rebuild/native rerun was started. Initial green
results do not validate this final input-hardening delta. iOS validation is still
running; the whole stage is not marked accepted. Source checks passed 92/92 before
the final Android input hardening; current diff check remains a separate gate.

Stage-3a iOS full ru passed 47/47, then UI ru FAILED during runner preparation:
zero UI tests executed. Crash report shows SIGABRT in XCTWaiter handleStalledWait;
the main thread was loading a system UIKit accessibility bundle through dyld.
en phases did not run. In-run one-minute host load ranged 9.27–217.92 (99 samples).
This does not prove a browser fault or establish a conclusive environment cause.
The Android rebuild overlapped this run on an 8-GiB host; project Gradle defaults
to a 3-GiB heap. Resource contention is a plausible contributor, not a proven fix.

A single controlled recovery is staged in `forge-mobile-link-actions-20261105-serial`:
host-load preflight below eight, then Android build (max two workers, no parallel,
command-only 1-GiB heap override), Android native, and only then iOS full/UI ru/en
with xcodebuild jobs limited to two. No overlapping heavy jobs or retry loop, no
test-timeout changes. The frozen iOS snapshot is identical to the failed-runner
snapshot; current Android includes the final input privacy flags. Recovery is
pending. Original partial builds, failed xcresults and crash analysis are retained.

The serialized recovery passed final Android 31/31 native and 21/21 unit, with
only OldTargetApi warning, including the query privacy flags. iOS full ru passed
47/47; UI ru FAILED 7/8 on test cleanup: the system action sheet was a popover,
with a PopoverDismissRegion and no separate Cancel button. Both disabled Share/
Find checks had already passed; en phases did not run. This failed run is retained.
On 2026-11-06 only that test cleanup changed: it uses the real menu's Tabs action
then closes the blank tab it created. Separate hash-frozen evidence directory
`forge-mobile-link-actions-20261106-ios-v2` records the exact test-only delta;
production sources match the serial run. Fresh full/UI ru/en 47+8 checks are
running with two xcodebuild jobs and unchanged expectations/timeouts. No upload.

The 2026-11-06 iOS-v2 full ru run FAILED 45/47: native site-data clearing exceeded
its 60-second expectation; subsequent cookie assertions also failed and no fresh
WKWebView could be unwrapped. That test took 217.083 seconds including later
WebKit queries. The following tab-close test failed selection and fresh-view
assertions, consistent with the process-wide clear gate still blocking tab
mutations. This is not conclusively attributed to host load (post-run load was
114.00/274.59/206.78), nor treated as an independent fixed tab bug. UI and en did
not run; no retry was launched. The last green 47-test runs do not clear this run.

Added test-only clear timing/store-count/callback attachments and an explicit
process-wide-gate precondition in the tab-close regression. The original 60-second
expectation and cookie/selection assertions remain. After a failed expectation,
the native clear test now returns instead of waiting indefinitely on more WebKit
callbacks. It neither resets nor bypasses the production clearing gate. These
diagnostics are not yet validated on a simulator; no production clear change.

Stage 3b storage scaffold is added but NOT integrated into navigation or menu UI:
bounded separate `library-v1.json` models/stores (500 history, 200 bookmarks,
8-MiB cap), regular-only validated HTTPS entries, atomic saves, corrupt/future
file fail-closed protection and no-backup/file-protection behavior on iOS.
Model/storage tests and Python source safeguards are added; new Swift/Java library
code and native diagnostics still need compilation/runtime validation. No claim
that bookmarks/history are user-accessible or working in any shipped build.

Source safeguards now pass 93/93; `git diff --check` is clean. With host one-minute
load down to 2.09, one targeted control is running in a newly created isolated
Forge iPhone 17 Pro/iOS26.4 simulator, without erasing or reusing personal devices.
It uses the failed iOS27 production snapshot plus only the two test diagnostic
deltas, and executes native clear followed by the saved-neighbor tab-close case.
No network relay is needed for these two local-cookie/session tests. Expectations
remain 60 seconds for clear; xcodebuild has two jobs, no parallel tests/retries.
Evidence: `forge-site-data-diagnostic-20261106`. This runtime control cannot clear
the original failed full iOS27 run; outcome is pending. No other heavy job runs.

The isolated iOS26.4 control passed 2/2. Trace: four data stores (one persistent),
native clearing callback success after 48.239 seconds, processWideClearPending=false;
the next tab-close fixture also saw the gate false. This is near the unchanged
60-second limit and does NOT erase the failed full iOS27 run or establish its cause.

Stage-3b host-only checks passed: Java library/link models 9/9 (256-MiB JVM, two
processors) and Swift/Foundation model/store groups 6/6 on macOS. These do not
validate Android AtomicFile or iOS data-protection semantics. The library has now
been connected locally on both platforms: searchable Bookmarks/History screens,
explicit add/remove, cancel-first history clearing, regular-success visit hooks,
private-write rejection, and visible unavailable/read-only storage state. Library
opening does not navigate until a row is chosen. Site-data clearing messages now
explicitly keep bookmarks/history; history has a separate confirmation.

Final Android integration build passed 27/27 unit and native 36/36 on the isolated
ARM64/API35 AVD, lint 0 errors/OldTargetApi only. Native checks include AtomicFile
roundtrip/corrupt-file protection, private-write rejection, history-clear scope,
library search/open controls and injected visit success/failure callbacks. Callback
injection is not real-site workflow validation. Tab labels are independent open
targets alongside close buttons, with a regression for that selection action.
Evidence: `forge-mobile-library-20261106-android-v2`.

iOS current library production sources are frozen separately under
`forge-mobile-library-20261106/ios-v1`. Focused ru/en checks (six library model/store
tests +four integration tests, plus one real UI menu/search test per language)
passed: 10/10 native and 1/1 UI in each language, 22 executions total, on the
isolated iOS26.4 simulator with one build job. This is NOT a fresh
full-suite validation, and it cannot clear the earlier iOS27 failure. Local HTML
fixtures use HTTPS base URLs and a no-resource CSP; no real remote visit is needed
for the new history hook test. Full device/OS/privacy/export and release gates remain.

Stage-3b evidence is indexed in `forge-mobile-library-20261106/stage3b-summary.json`.
All 35 frozen iOS files and 34 Android app-source files matched the working tree
when recording this result. Full integrated iOS inventory is 57 native +9 UI tests
per language; focused library success must not be reported as that full suite.
Before changing new-window navigation in stage 4, run this integrated baseline
serially in a new evidence directory. Preserve the original iOS27 45/47 failure,
unchanged cookie-clear deadline and all existing assertions. No release/upload.

Integrated library-enabled baseline is now running in
`forge-mobile-library-full-20261106-ios-v1` on the original isolated iOS27 device.
It uses the exact focused-library source snapshot, including clear timing/gate
diagnostics, with one build job, no parallel tests and stop-on-first-failed-phase.
Expected ru/en phases are 57 native and 9 UI each; no assertions or test deadlines
changed. The restricted test-only CONNECT relay still permits only razex.shop:443;
native TLS validation is unchanged. Stage-4 navigation production edits wait for
this baseline's result. A new run is not evidence that the older failure is fixed.

The integrated baseline PASSED all four phases on the original isolated iOS27
simulator: native ru/en 57/57 each, UI ru/en 9/9 each, **132 successful executions**,
zero failures. All 35 frozen source files and working-tree counterparts matched
their recorded hashes. Evidence: `forge-mobile-library-full-20261106-ios-v1/`
(`ios-candidate-tests.json`, `integrated-summary.json`, logs and xcresults).
Native clear callbacks succeeded after 4.023s (ru) and 2.197s (en), across four
stores/one persistent; both traces ended with processWideClearPending=false.
No production clearing change, timeout increase or assertion removal was used.
The older iOS27 45/47 failure remains preserved and its root cause is unproven;
this run validates current integrated sources, not a claimed fix for that timeout.
Physical-device acceptance and release/security-update gates remain separate.

Next stage-4 increment: explicit user-initiated HTTPS new-tab links, preserving
the current regular/private group and the 32-tab bound. Reject automatic popups,
stale/background sources and unsupported schemes; create native tabs without
window.opener. Add native regressions before broadening to OS URL entry or
forms/file uploads. No stage-4 production code or new release is implied here.

### Stage 4a implementation under validation (2026-11-07)

Local iOS new-window navigation cancels the engine's auxiliary window, accepts
only HTTPS main-frame linkActivated GET requests (not forms/download actions),
and offers a cancel-first native confirmation. The extra confirmation is required
because WKNavigationType alone does not establish a trusted user gesture. On
confirmation, a fresh native tab opens only the validated address, without opener,
form body or content-provided headers. The current regular/private group and
32-tab bound remain; stale source, modal, inactive/non-key-window and clearing
states fail closed. Backgrounding invalidates outstanding action versions.

Android exposes a cancel-first Open link in new tab action for a validated HTTPS
context-menu link. Native confirmation is private-window protected and checks
source/session identity, document/action version and foreground focus again.
All TARGET_WINDOW_NEW loads are denied for now: Gecko LoadRequest exposes no
HTTP method/body, so replaying its URI could silently convert a form POST to GET.
This intentionally does not claim automatic target=_blank compatibility on Android.

Added six iOS and five Android native regression tests. These include injected
Gecko callbacks/native dialog clicks and local WebKit source documents; they do
not establish real long-press/target=_blank interoperability across websites.
The iOS helper tests initiate only reserved .invalid destination addresses and
stop their loads. New tests are not yet accepted. Full expected inventory is
iOS 63 native +9 UI per language, Android 41 native +27 unit.

The first Android offline build stopped before compilation because the dependency
artifact cache was absent (modules-2/files-2.1). Log retained in
`forge-mobile-new-tab-links-20261107-android-v1`. A single online build is restoring
the same pinned versions from the existing repositories, with one worker/1-GiB
heap; no dependency versions, TLS checks or signing configuration changed.
iOS is frozen in `forge-mobile-new-tab-links-20261107-ios-v1`; no parallel heavy
validation, retries or timeout increases. Stage 4 forms/files/OS entry remain pending.

The pinned-dependency online Android build passed: 27/27 unit tests, app/test APK
compilation and lint with only OldTargetApi. No dependency changes were needed.
Evidence: `forge-mobile-new-tab-links-20261107-android-v2`. Its 41-test isolated
native run is now in progress. The generated frozen iOS project is ready for
63-native/9-UI ru/en checks after Android stops; no concurrent simulator tests.

Stage-4a Android-v2 native run FAILED 39/41: both positive-confirmation tests
asserted two tabs immediately after Button.performClick(), before AlertDialog's
Handler dispatched its listener. Cancellation and other regressions passed, but
this run does not validate successful opening. In Android-v3 only the native test
file changes: assertions execute after waitForIdleSync in a separate onActivity
callback. The stale-source rejection assertion is likewise moved after dispatch,
so it cannot pass merely because the click listener has not run. All tab-count,
separate-session and private-disk-exclusion assertions remain. Production hashes
match the failed run; exact delta is recorded in Android-v3/test-only-delta.json.
A fresh build/full native run is in progress; no timeout changes or retry loop.

Android-v3 rebuilt with 27/27 unit/lint (OldTargetApi only), but full native FAILED
40/41: regular new-tab confirmation passed; private confirmation still saw one
tab after dispatch. The handler-order test correction was insufficient to explain
the private failure. No production guard is weakened. A single targeted diagnostic
run in `forge-mobile-new-tab-links-20261107-android-diagnostic-v4` adds source URL,
permission/action version, pending-load and activity/dialog focus to the existing
assertion's failure message. Only that private case is selected; this is not full
acceptance or retry-until-success. iOS remains staged, not yet runtime validated.

The isolated private diagnostic passed 1/1 with unchanged production; this does
not resolve the prior full 40/41 failure or prove its cause. Test tracing now also
emits a dedicated instrumentation status bundle on success, so a future full
diagnostic run can retain source/version/focus state instead of losing it when
the isolated case passes. That new trace emission has not been rebuilt yet.

iOS-v1 stopped before simulator launch: the historical external relay import
file was absent. iOS-v2 preserves identical app/test sources and uses a self-contained
test-only relay. ConnectHandler/ProxyServer ASTs match the surviving reviewed
2026-10-30 implementation; four forbidden method/host/port cases returned 403.
It only forwards opaque CONNECT traffic to razex.shop:443, without TLS termination
or trust changes. Harness delta and relay check are recorded in
`forge-mobile-new-tab-links-20261107-ios-v2`. Full 63+9 ru/en validation is now
running serially with one Xcode job; no Android build/emulator runs concurrently.

iOS-v2 full ru FAILED 62/63: private new-tab opening succeeded, but the regular
session file's byte comparison changed (same 157-byte size). Other native tests,
including clearing, passed; UI/en did not run. Inspection found private tab actions
and KVO repeatedly save the unchanged regular model. A separate Foundation host
check saved one model 20 times: zero decoded-model differences, 20 byte differences
from the initial JSON encoding. Evidence: `forge-ios-session-write-diagnostic-20261107`.
This demonstrates unstable JSON representation, not private URL persistence.

iOS-v3 now remembers the last successfully persisted regular model and skips
unchanged saves, including no-op private activity. It retains the original byte
assertion and adds a regression checking file bytes/inode/mtime across private tab
mutations, followed by a regular mutation which must still persist. Expected full
inventory is now 64 native +9 UI per language; source delta is frozen separately.
It has not run yet. Original failures are retained. In parallel with lightweight
snapshot preparation only, Android-diagnostic-v5 is running its full 41-test suite
with persistent version/source/focus trace output; no iOS build overlaps it.

Android-diagnostic-v5 reproduced FAILED40/41 and retained the decisive trace:
private source URL was https://source-fixture.invalid/ before menu presentation,
but about:blank before confirmation (version=1, pending=false). The newly opened
private Gecko session delivered its native initial location after the injected
test callback. The production HTTPS-source check correctly refused that stale
fixture. Android-v6 changes only the test: finish an explicit local about:blank
navigation via an engine completion latch before injecting the source, and assert
the source HTTPS URL again before clicking. Tab count/privacy/separate-session
assertions and diagnostic output remain. No production guard or existing test
deadline changed. Full 41-native/27-unit validation is running separately; the
prepared iOS-v3 64+9 ru/en run still awaits Android completion.

Android-v6 again FAILED40/41, now only the regular confirmation case. The private
case passed after engine initialization. Trace confirmed a stable HTTPS source
and document version, but both Activity and dialog window focus were false at the
programmatic click. The production focus guard correctly rejected it; idleness is
not proof of window focus. A test-only OnWindowFocusChangeListener precondition
now waits for the actual dialog focus event (10s cap) before clicks, keeping all
source/tab/privacy assertions and the production guard. This change is not yet
built. Existing keyboard and clear deadlines are unchanged. iOS-v3 full ru/en
64+9 is now running alone; Android revalidation will follow, not overlap it.

iOS-v3 native ru/en PASSED64/64 each (128 native executions), including unchanged
private-file bytes plus inode/mtime and regular-write controls. UI ru passed9/9;
UI en FAILED8/9 in the existing private-group-close scenario: immediate absence
assertion after tapping destructive confirmation. The retained recording ends in
the regular group with no close-private control; no production fix is inferred
from this final frame. iOS-v4 changes only that UI test to await BOTH control
nonexistence and regular-segment selection (5s cap), retaining the original
absence assertion. It stages all9 UI tests per language; production and native
tests match v3, whose64/64 per-language results remain separate evidence.

Android-v7's first launch was blocked by the high-load preflight before any build
or emulator; receipt preserved. A later explicit preflight observed one-minute
load3.97 below8 CPUs and started the prepared one-worker/1-GiB validation. iOS-v4
is only staged; no concurrent heavy run. Stage4 remains unaccepted pending results.

Android-v7 PASSED41/41 native and27/27 unit; lint only OldTargetApi, with the same
production APK SHA256 as prior stage-4 builds:
`35a44a41b783a7ba97a79dc100ef0757f8c6ee4561bac09eb9024bc311b165eb`.
Retained traces show both confirmed cases kept the HTTPS source/version stable
and had dialogFocus=true before clicking; both created a fresh tab in the correct
group. The private case also passed disk-exclusion checks. Earlier failures and
their fixture diagnostics remain intact; no production safety guard was weakened.
iOS-v4's full UI ru/en9+9 run is now in progress alone. Its production/native
sources still match iOS-v3 native64/64 per-language results; no iOS release claim.

Stage4a local automated acceptance is recorded in
`forge-mobile-new-tab-links-20261107-stage4a/stage4a-summary.json`:
- iOS native64/64 per language in v3, UI9/9 per language in v4:146 successful
  executions across separate native/UI runs. The only source delta between these
  accepted runs is the UI test's explicit close-state wait. No native/production
  delta; v3's failed UI-en result remains failed and preserved.
- Android-v7 native41/41, unit27/27; lint0 errors/OldTargetApi only.
- Current working files match all36 accepted iOS hashes and35 Android hashes.

The increment supports explicit native-confirmed HTTPS link-address opening, not
universal popup/form compatibility. iOS tests cover helper gating with local source
documents; real-site target=_blank plus confirmation UX is not comprehensively
tested. Android tests inject a context-link callback and click the native dialog;
actual site long-press interoperability remains unverified, and auxiliary-window
requests are still denied. Neither physical-device readiness nor a new uploaded
build is claimed. Next stage4b: OS HTTPS URL entry with explicit validation and
confirmation; forms/file uploads stay a separate subsequent scope. Existing
release, update/security and physical-device gates remain open.

### Stage4b: OS HTTPS entry (local, 2026-11-07; under validation)

Android now declares a HTTPS-only BROWSABLE ACTION_VIEW filter and singleTop
delivery. Cold starts and onNewIntent validate a bounded credential-free HTTPS
address; extras, ClipData, supplied headers/referrers and URI grants are never
consumed. The Activity's stored Intent is replaced with a blank MAIN intent, and
recreation does not reoffer the original VIEW address. There is no automatic
navigation, role request or default-browser change.

One address may wait only in memory for the resumed/focused Activity. A cancel-first
native confirmation identifies the host and current regular/private group; private
confirmation uses FLAG_SECURE and explains that OS/other-app copies cannot be
erased. Confirmation creates a fresh native tab within the existing bound, and
rechecks resumed state, focus, group, selected tab and action version. Backgrounding
cancels the prompt and drops the address. Duplicate arrivals cannot replace the
URL behind a visible dialog; no durable external-link queue is implemented.

Added four unit and eight native regressions: cold/warm entry, no pre-confirmation
load/write, cancellation, separate regular/private sessions, ignored extras,
unsupported actions/schemes, duplicate arrivals, pause/recreation replay rejection
and the tab bound. Full Android validation (31 unit/49 native) is running with one
worker and1-GiB heap under `forge-mobile-external-links-20261107-android-v1`.
These tests use direct test Intents/native dialogs, not physical-device chooser
or default-browser-role acceptance. New Android sources are not yet accepted.

iOS does not currently configure Apple's default-web-browser entitlement. Generic
HTTPS OS delivery cannot be claimed merely by adding onOpenURL or registering a
fake https URL scheme. Apple entitlement/provisioning and actual OS dispatch remain
an explicit iOS gate; no Apple request, capability change or upload was performed.
Existing iOS stage4a sources remain unchanged. Forms/file uploads are still pending.

Git state checked for the owner's question: local HEAD and the saved tracking ref
forge-public/forge both equal79238d746a6b5daae3eeae717120c1efc18cfd81. All later
mobile work remains local/uncommitted/unpushed; this was not a live remote fetch.
No new push was authorized or performed.

Stage4b Android-v1 FAILED compilation: a duplicate onWindowFocusChanged override
was introduced alongside the existing permissions callback. Android-v2 merges the
new focus hook into that existing callback, retaining permission handling, and
cancels a pending permission request/find UI before accepting an external address
so native prompts cannot compete. The new build/full49-test run is in progress;
the original compile log is preserved.

Initial Python96-test run failed the older blanket ACTION_VIEW source restriction
which protected downloads from automatic external opening. The safeguard now
distinguishes direction: downloads still contain no ACTION_VIEW; Activity may have
exactly one occurrence in the incoming-action check, and outgoing VIEW Intent
construction/setAction remains forbidden. No download auto-open behavior was
added. Current Python safeguards pass96/96; native acceptance is still pending.

### Source publication authorized (2026-11-07)

The owner explicitly authorized a GitHub push and continued development. This
supersedes the earlier no-push authorization state for the present source
checkpoint only; it does not authorize new TestFlight/release uploads, signing
capability requests or deployment. Live remote forge HEAD was checked at79238d7
before publication. Only Forge source/tests/status docs and the manual signed-macOS
validation workflow are in scope. The local overlay-state file, generated projects,
build outputs, profiles, credentials and raw evidence stay outside the commit.

`mobile/SOURCE_CHECKPOINT.md` distinguishes accepted stage-4a/iOS evidence from the
new Android external-link delta still under validation. Source pre-push checks:
Node56/56, Python96/96, compileall and diff whitespace checks passed. GitHub Actions
audit: push triggers source checks only; mobile/desktop builds and release
publication remain manual workflows. Do not dispatch them as part of this push.

Source checkpoint committed and pushed as516edebcd5f6788466ee7b18f9a8ac6560b08500;
live remote forge SHA confirmed equal. Exactly80 reviewed source/test/doc/manual-CI
files were included (650956 bytes at pre-push audit); no artifact/credential pattern
findings. Local overlay state was deliberately excluded. This is source publication,
not a new app package, release or TestFlight upload.

The pending Android-v2 run later reported31/31 unit, lint only OldTargetApi, but
native instrumentation exceeded its unchanged900s limit:7 pass statuses,19 failure
statuses, then an unfinished27th case out of49. Lifecycle failures started at the
first Activity-dependent test; do not classify this as49 tests completed or green.
Incomplete log and analysis are retained in that evidence directory.

ActivityScenario1.7 bytecode confirms activityMatchesIntent compares original and
current Activity action/data/type/component/categories on every lifecycle event.
Replacing the launch Intent with a blank MAIN removed that identity and made the
monitor ignore CREATED/RESUMED after PRE_ON_CREATE. This is a confirmed harness
compatibility failure, not proof that the real app never reached those lifecycle
states. The corrective implementation preserves the framework launch filter via
cloneFilter, strips extras/ClipData/selector/grants, and leaves the original filter
unchanged on warm onNewIntent. Re-creation replay is still explicitly rejected by
savedInstanceState handling. Android may retain its original launch URL outside
Forge; no secure-erasure claim is made for framework/task records.

Cold-entry tests retain no-load/no-write/privacy checks and now verify preserved
launch identity plus stripped payload/grants rather than a blank MAIN action.
Two native startup controls (existing local Gecko launch +cold VIEW cancellation)
are being checked first in `forge-mobile-external-links-20261107-android-v3-focused`;
no full retry or timeout increase before that result. Forms/files work is paused
until the entry regression is checked. These corrections are local after the push.

GitHub source checks for516edebcd5f completed successfully:
https://github.com/RAZEX0LOL/forge-browser/actions/runs/42380950777 .
The first local corrective build compiled app/unit code but failed native-test
compilation because Intent.setClipData returns void and was chained in a test;
that test construction was corrected without removing payload assertions.

Android-v4-focused then PASSED31/31 unit, lint only OldTargetApi, and2/2 native
startup controls (existing Gecko blank load and cold VIEW cancellation). App SHA256:
9380d6699b91fc1333be6a67400270fb7ed31f093afe4af39f6a6803aa1bd41c.
The immediately following full launch was blocked before tests by ADB still
listing5582 after focused-runner shutdown. Follow-up inspection found adb devices
empty and no qemu/ForgeTabs process; no process was killed or evidence overwritten.
The blocked-launch receipt is preserved in Android-v5-full. Its full49-test run
is now in progress, with the same source/APK and unchanged test timeouts.

Stage4b Android local automated acceptance PASSED: Android-v5-full49/49 native,
unit31/31, lint only OldTargetApi; separate startup controls2/2. All38 working
app-source files matched the build manifest and were frozen alongside
`stage4b-summary.json`. Cold/warm confirmation, rejected actions/schemes,
regular/private preservation, no pre-confirmation navigation/write, ignored
payloads, duplicate-address protection, pause/recreation rejection and tab bound
all passed. Prior compile failures and the incomplete900s run remain preserved.

This validates isolated Intent/native-dialog fixtures, not physical OS chooser
selection or default-browser role compatibility. iOS default-browser entitlement
and provisioning remain unconfigured; forms/file uploads are still pending.
The corrective launch-identity code/status will be committed/pushed as a follow-up
to the owner's source-publication request, without app/release/TestFlight uploads.

| Platform | Existing baseline | Remaining release gates |
| --- | --- | --- |
| Windows x64/ARM64 | Native Firefox artifact builds, 260 checks per target in earlier CI | Publisher signing, install/upgrade/profile migration, security-update pipeline, real daily use |
| macOS ARM64/Intel | Developer ID signing/notarization completed separately; ARM64 signed runtime passed 285 checks | Signed Intel runtime validation (Rosetta timed out), upgrade tests, security-update pipeline |
| Linux x64/ARM64 | Native portable builds, 260 checks per target in earlier CI | Packaging/integration, upgrade/profile tests, security-update pipeline |
| Android | GeckoView, local tabs/session/download tests | Private-mode validation, permissions, data clearing, durable recovery, release signing, physical-device testing |
| iOS/iPadOS | WKWebView, internal build 3; local UI passed 16 checks | Private-mode validation, permissions, data clearing, Files-provider export, direct real-device networking and UI testing |

Desktop counts are historical evidence, not tests of today's uncommitted sources.
Desktop remains an artifact-development fork, not a maintained production Gecko
security distribution. Native Firefox private windows are preserved; mobile has
its own engine-specific implementation and does not inherit desktop capabilities.

### Current local increment: private mobile tab groups

Android uses GeckoSessionSettings.usePrivateMode; iOS shares a nonpersistent
WKWebsiteDataStore within one private group. Only regular tab snapshots are saved.
Mode switching retains live tabs; Close all private tabs tears down their engines
and starts a fresh private group on next entry. Process termination restores only
regular tabs. Private downloads are rejected before shared cache staging; regular
downloads remain a separate regular-mode operation. Android private windows use
FLAG_SECURE; iOS covers private content while inactive for app-switcher previews.

Native persistence/mode and WebKit cookie-isolation tests were added. Android's
focused private test passed; the rebuilt full native suite passed 12/13 including
FLAG_SECURE checks. The HTTPS download test failed with ERROR_UNKNOWN_HOST (37),
also reproduced by emulator ping; host curl verified HTTPS 200 and 1266 bytes.
The emulator startup log confirmed that system DNS discovery failed and name
resolution was disabled. Restarting only the isolated AVD with explicit DNS
servers (1.1.1.1, 8.8.8.8) yielded **13/13 native tests passed**, including the
HTTPS transfer. TLS/security checks were unchanged. The initial iOS run passed
18/18 including WebKit cookie isolation; the final Russian-language run with
preview-cover and additional persistence assertions also passed **18/18**, with
0 failures (`ios-private-final.xcresult`, `ios-final-summary.json`). The network-dependent
iOS download test is excluded, not counted as passed.
Android's 9 unit tests passed; lint has 0 errors and the known OldTargetApi warning.
Build/unit/lint commands succeeded, and desktop/source suites passed 56 JS and
87 Python tests. Logs are local under `forge-private-tabs-20261101` in the build
folder. Do not treat source implementation as a verified privacy promise.
Private browsing is not anonymity and cannot hide traffic from sites/providers,
erase OS diagnostics, or prevent user screenshots on iOS. Clearing regular site
data is tracked as the following increment. Nothing is pushed, uploaded or distributed.

### Next local increment: confirmed site-data clearing

Both tab menus now expose a separate cancel-first confirmation explaining sign-out,
page unload, private-group closure and download cancellation. Already exported
files and the regular saved-tab list remain untouched; reload is explicit.
Clearing refuses active system export pickers/copies. Navigation is gated across
app windows, engines/delegates are detached before the native storage API runs,
and new/recreated controllers stay gated until completion. Errors remain visible;
no certificate exceptions, broad filesystem deletion or session repair is used.

Gecko clears COOKIES | ALL_CACHES | DOM_STORAGES | AUTH_SESSIONS (55), not ALL.
WebKit removes all website data types and verifies records/session cookies after
completion. This does not promise secure erasure, removal of saved tab addresses,
OS-permission revocation, password deletion or erasure of exported documents.

New tests cover cancel-before-clear, engine teardown, regular-session preservation,
corrupt-session protection, pending-operation recreation/multiple controllers,
native API completion, failure/retry and WebKit cookie removal. Android's first
full run passed 14/16: both failures exposed routine blank-page progress replacing
the clearing result message. After the progress guard fix and an additional
positive-confirmation test, the native runner passed **17/17**. The host wrapper
still expected 16 and failed only its count assertion; the completed log was
revalidated for 17 success statuses, no failures and `OK (17 tests)`, recorded
in `android-native-summary.json`. Android's 9 unit tests passed, with 0 lint errors
and the existing OldTargetApi warning. Source suites passed 87 Python/56 JS tests.
iOS initially compiled with an actor-conversion warning; after retaining MainActor
isolation in the clearer closure, the Russian-language simulator run passed
**22/22**, with 0 failures and no runtime warnings (`ios-site-data.xcresult`,
`ios-summary.json`). This includes native cookie removal, multi-controller gating,
failure/retry and corruption protection. The network-dependent iOS download test
was excluded, not counted as passed. Physical-device and interrupted-process
completion checks remain unverified. Evidence is under the local build folder
`forge-site-data-20261101`. Nothing has been pushed, uploaded or distributed.

### Current local increment: foreground camera/microphone consent

Android now binds Gecko's permission delegate on each session, allows only camera
and RECORD_AUDIO runtime requests, and requires a secure non-exception origin.
An app-level explanation precedes missing OS authorization; media selection then
requires a separate site confirmation and a fresh OS-grant check. Unsupported
content permissions and screen/audio-capture sources are denied. iOS binds
WKUIDelegate and requests AVFoundation authorization only after site consent,
with English/Russian usage descriptions. No private API or OS-permission bypass
is used. Canonical HTTPS origins omit credentials, paths and query strings.

Requests are bound to a page/selection/navigation version, limited to foreground
same-origin contexts, and invalidated on navigation, tab/mode changes, background,
data clearing and teardown. Late OS responses cannot approve a replacement page.
Granted media pages are unloaded when left/backgrounded, so calls do not continue
in the background and future page navigation is explicit. OS access remains
application-wide, not private-group-scoped; there is no new persisted site-consent
database or OS revocation claim. Geolocation/general permissions remain separate.

Compilation is successful after fixing a Java callback-parameter shadow and
preserving MainActor isolation in the iOS foreground closure. The first Android
runtime run passed 19/22; failures exposed test timing assumptions about window
focus and asynchronous AlertDialog callbacks. After waiting for actual focus and
completion, the full Android rerun passed **22/22** (`android-final-native.log`,
`android-final-summary.json`); production foreground checks are unchanged.
Android unit tests passed **12/12**, lint has 0 errors/one known OldTargetApi warning,
and Python source/resource checks passed **88/88**. iOS's first full run passed
**29/29** with 0 failures/runtime warnings (`ios-media-permissions.xcresult`).
A final Russian-language rerun also passed **29/29**, with 0 failures/runtime
warnings (`ios-media-final.xcresult`, `ios-final-summary.json`), covering the
deny-only delegate for detached WebKit pages and stricter origin parsing.
The detached delegate avoids falling
back to WebKit's default prompt behavior during engine teardown.
The network-dependent iOS download test was excluded, not counted as passed.
Permission tests use injected OS outcomes, not live sensor access. Real-device
camera/microphone, native system prompts, WebRTC and privacy-indicator checks
remain unverified. Local evidence: `forge-media-permissions-20261101`. No push,
release, TestFlight upload, invitations or distribution has been performed.

### Local device-test packaging (2026-11-01)

The owner requested preparation for real-device validation. Local packaging is
authorized; a new TestFlight upload and physical-device installation are not.
ADB listed no devices and CoreDevice had no connected tunnels; no physical
device was selected. No device identifiers are included
in the distributable candidate directory.

- Frozen mobile source snapshot (58 files) plus hashes and MPL/upstream metadata.
- Android APKs for arm64-v8a, armeabi-v7a and x86_64, verified with apksigner,
  matching the previous local debug certificate. Version remains 0.1.0-prototype,
  code 1; exact SHA-256 identifies the candidate. Candidate runtime payloads match
  the previously tested APKs (dex, libraries, manifest and compiled resources).
- iOS 0.1.0 (4), archived and locally exported with Apple Distribution signing;
  codesign verification, provisioning compatibility, no debugger entitlement and
  en/ru usage descriptions were checked. The export is not directly installable,
  has not been uploaded and has no Apple-server validation receipt.
- Restored the pre-existing en/ru CFBundleDisplayName entries displaced when media
  permission descriptions were added; source checks now protect those names.
- Added a device checklist and no-upload local media fixture. The fixture must
  be served from a controlled trusted HTTPS origin under separate authorization;
  no website deployment accompanies packaging.
- Source checks passed 89/89; fixture JavaScript syntax passed without execution.
  Frozen Android unit tests passed 12/12; lint has 0 errors/OldTargetApi warning.
- Full iOS network-inclusive testing uses the restricted test-only CONNECT relay
  with TLS verification intact. First ru run passed 29/30; the keyboard test lost
  first-responder status after displaying the keyboard. That report is preserved.
  The same-snapshot focused control hit a 300-second timeout without a completed
  summary; full ru/en reruns were not started. The isolated simulator was shut
  down after the timeout. Root cause is unresolved, so candidate QA is **BLOCKED**
  and `readyForUpload=false`; no assertion was removed or treated as passed.
- Artifact integrity is recorded in MANIFEST.json, SOURCE-MANIFEST.json and
  SHA256SUMS, with a human-readable CANDIDATE_STATUS.md. Signature/checksum checks
  do not clear the runtime QA blocker. Earlier green mobile runs are historical
  evidence, not a substitute for this candidate's failed focus check.

Local staging folder: `forge-device-candidates-20261101-v4`. Physical capture,
system permission dialogs, hardware release, direct device networking, Files
export and WebRTC remain unverified. Existing releases/TestFlight build 3, live
website, tester groups and personal profiles are unchanged.

### Keyboard focus investigation and test-host hardening (2026-11-01)

Production `Sources/` files match the blocked build-4 snapshot; this investigation
does not contain a speculative browser focus patch or a new signed package.
Test-only forwarding/notification traces record responder classes, key-window and
scene state plus an end-editing stack, without input text, URLs or credentials.

- The original keyboard test passed all three fixed cold app-launch repetitions;
  traces kept the address field first responder and the test window key. The
  summary counts one unique test; three distinct trace attachments and execution
  logs establish the repetitions, not three distinct test cases.
- The diagnostic bundle took 351.8 seconds overall; actual test cases took about
  8.5 seconds total. The prior 300-second whole-xcodebuild deadline was too short
  for this cold build/runner startup. The 30-second keyboard expectation and
  original focus/position assertions are unchanged.
- A full network-inclusive ru run passed 30/30. A separate UI-testing scheme
  exercised real address/start-search taps and typed text in the normal SwiftUI
  app window: two tests, three fixed repetitions (six successful executions).
- The old keyboard fixture chose the first scene and created another key window.
  It now uses a foreground-active scene's existing normal key window, temporarily
  swaps/restores its root controller, and waits for intentional keyboard hide
  before restoring the host. This removes a potential host-window race; the exact
  original spontaneous failure has not been reproduced or conclusively attributed.
- Added `ForgeMobileKeyboardUI`, with explicit ru/en test-language input and
  localized address-label assertions. Fixed repetition runs retain all failures;
  no retry-until-green or assertion suppression is used.

Final validation passed in both languages: 30/30 full tests with three fixed app
relaunch repetitions per language (180 successful test executions total), plus
2/2 real-window UI tests with three repetitions per language (12 successful UI
executions). No failures, skipped keyboard assertion or retry-until-green loop.
All six final keyboard traces retained field focus/key-window ownership through
the layout assertion. The full runs include HTTPS downloads via the restricted
TLS-preserving relay; UI tests type fixture text without submitting navigation.
Python source checks passed 89/89; `git diff --check` is clean.

`focus-investigation-summary.json` records exact counts, test/project hashes and
the unchanged production-source comparison. The original spontaneous failure
remains unreproduced, not a conclusively fixed browser defect. Original candidate
artifacts, their BLOCKED manifest and previous failure evidence remain unchanged;
promotion/repackaging requires a separate decision using the new test evidence.
The isolated simulator was shut down. Evidence is local under
`forge-keyboard-focus-20261101`. No TestFlight upload, physical-device install,
push, public release or website update is involved.

### Build-5 fresh candidate failure and separate QA2 (2026-11-01)

The fresh frozen build-5 ru run FAILED: 29 passed, one failed, xcodebuild exit 65.
The keyboard test over-fulfilled `Software keyboard shown`; en and both UI phases
did not run. Earlier green 180+12 stress executions do not clear this candidate.
Its packages and failed evidence remain under `forge-device-candidates-20261101-v5`;
the gated finalizer has not run. Build 4 and its BLOCKED manifest are unchanged.

The exception stack shows keyboard-scene foreground tracking posting another
show notification while the global observer was still registered. No focus trace
was exported for the interrupted test; its focus state cannot be inferred.
Test-only one-shot observers now cancel before delivering the first matching
notification, and explicitly cancel on timeout/cleanup. Both show and hide use
this ownership rule. Two regression tests cover nonmatching, duplicate, reentrant
and cancelled notifications without disabling XCTest over-fulfillment checks.
Original keyboard focus/geometry assertions and 30-second waits remain intact.

Separate `forge-device-candidates-20261101-v5-qa2` freezes the corrected harness
and records its exact test-only hash delta from v5. Production source/packages
are unchanged; this is not a new iOS build or a silent replacement of failed QA.
Fresh full ru/en (32 tests each) and UI ru/en (two each) validation is pending.
No upload, physical install, push or live-site change is authorized here.

On 2026-11-05, the harness restart was confirmed to have interrupted QA2:
`BUILD INTERRUPTED`, an incomplete xcresult without Info.plist, and no completed
test summary. This is neither a passing run nor an observed assertion failure.
Its log and incomplete bundle are retained. A fresh run is staged separately in
`forge-device-candidates-20261105-v5-qa3`, with all frozen source hashes verified
against QA2 and no additional source changes. It repeats all four required
phases, not only the interrupted phase; finalization remains gated on results.

QA3 then failed before executing any test: xcodebuild exit 65, runner launch
`NSPOSIXErrorDomain 64 / Host is down`, with a possible simulator system-shell
failure. No browser assertion or regression-test result was obtained; remaining
phases did not run. Logs/results remain preserved. After rebooting only the
isolated Forge simulator, SpringBoard responded and a direct `simctl launch
--terminate-running-process` of Forge and its subsequent termination both passed
(exit 0). This preflight is not test coverage or proof of the original cause.
One fresh four-phase run, `forge-device-candidates-20261105-v5-qa4`, is pending
with identical hash-verified sources and no automatic retries. QA3 remains failed;
QA2 remains interrupted; earlier build-5 expectation failure remains retained.

QA4 FAILED full ru: 31/32 passed, one 30-second keyboard-show timeout (exit 65);
en and both UI phases did not run. Both new notification regression tests passed.
The retained trace shows focus-request return at 22.702 seconds and keyboard
did-show at 57.324 seconds: 34.623 seconds later, beyond the unchanged 30-second
wait. Field focus and key-window ownership remained true at did-show and layout;
no spontaneous focus loss was observed. This is a late notification, not evidence
that the matching predicate rejected every event. Intentional hide cleanup finished.

Post-run host load was high (initial sample 29.09/83.69/67.57); this was not sampled
during the test and cannot prove causality. Simulator/host slowdown is a hypothesis,
not a diagnosed browser fix. `qa4-failure-analysis.json` preserves exact timings and
regression execution lines locally. No timeout increase, assertion removal, automatic
rerun, finalization or upload followed. Candidate remains blocked; next validation
needs a controlled low-load environment with measurements during the run.

At the user's explicit request, one additional run is staged separately as
`forge-device-candidates-20261105-v5-qa5`. The pre-start one-minute host load fell
to 2.08 (5/15-minute averages still 30.91/47.55). Frozen source hashes match QA4;
keyboard timeout/assertions are unchanged. The runner now records timestamped
host-load samples every five seconds in `host-load.jsonl`, without changing the
test harness. All four full/UI ru/en phases are planned, stopping at the first
failure with no automatic retry. Prior failures remain retained.

QA5 FAILED full ru 31/32 on HTTPS preflight `NSURLErrorDomain -1001`; en/UI did
not run. Keyboard focus/geometry passed (7.199-second test, did-show 3.780 seconds
after focus-request return), as did both new notification regressions. This does
not erase QA4's keyboard timeout. Fifty-one in-run host-load samples ranged from
3.52 to 113.87 (one-minute average, eight logical CPUs).

A subsequent host curl probe also timed out before TCP connection at 25 seconds;
later explicit IPv4/IPv6 curl probes returned HTTP 200, and the same restricted
CONNECT relay returned HTTP 200 in 0.945 seconds with normal TLS validation.
The route is working at probe time, not proven stable; the original network
timeout cause is not established. A later host-load sample remained high
(67.59/50.96/22.34), so no further full validation was started. No unrelated
processes were terminated or system networking changed. Local QA5
`qa5-failure-analysis.json`, `host-load.jsonl` and `postrun-relay-network-probe.json`
retain the evidence. Candidate is still blocked; no finalization or upload.

After the user reported unloading the Mac, a recent host reboot was confirmed.
One-minute load was 5.70 on eight logical CPUs, with lagging 5/15-minute averages
27.70/18.35. Restricted-relay preflight returned HTTP 200 in 5.851 seconds with
normal TLS verification. One new run, `forge-device-candidates-20261105-v5-qa6`,
is pending on the identical hash-verified QA5 snapshot. It retains the 30-second
keyboard wait, all assertions, in-run load sampling and stop-on-first-failure.
Earlier failed/interrupted results remain unchanged; no automatic retry or upload.

### QA6 passed; separate local device kit finalized (2026-11-05)

All four QA6 phases passed: full ru 32/32, UI ru 2/2, full en 32/32, UI en 2/2 —
68 successful executions, zero failures or skips, no repetitions within this run.
The finalizer independently checked xcresult summaries, execution logs, every
frozen source hash and the single test-only delta from original build 5. iOS and
all three Android signatures were freshly verified; package SHA-256 values match
the previously prepared v5 packages. No new package build/upload was performed.
Workspace Python checks passed 89/89; these are separate from the iOS run.

New finalized kit: `forge-device-candidates-20261105-v5-qa6/artifacts`. Contains
three debug APKs, Apple Distribution iOS 0.1.0 (5) IPA, corrected QA6 source archive,
exact test-only delta, QA report, manifests, device checklist/fixture and SHA256SUMS.
Checksum verification passed 12/12; original blocked v4 kit passed 10/10 unchanged.
The source archive's README reflects its historical snapshot; CANDIDATE_STATUS.md
and QA-REPORT.json are the kit's authoritative current status. Android 12/12 unit,
22/22 native and lint evidence remains explicitly historical, not fresh QA6 runs.

QA6 is locally green, not proof of earlier failure causes or physical-device
stability. v5 and QA2–QA5 failures/interruption remain preserved and listed in the
report, as does the older 180+12 historical green stress evidence. Raw xcresults,
host-load logs and device identifiers stay in private staging, outside the kit.
TestFlight upload requires separate approval and App Store Connect build-number
availability check; neither happened. Real media capture/OS dialogs, hardware
release, privacy indicators, direct phone networking, WebRTC and Files export
remain device-test gates. No git push, live-site change or physical install.

### Build-5 TestFlight upload authorized (2026-11-05)

After QA6 finalization the user separately approved proceeding with TestFlight.
Read-only App Store Connect preflight found no build 5 for the expected app and
confirmed its bundle ID. All 12 frozen kit checksums passed again. A one-shot
pipeline is running Apple server validation, then upload of the exact existing
IPA (SHA-256 `eddb6b2584b80f2e031a3bb0f58f7b3d73b7f1559b87e04aa9b94d83fdd2509e`),
without rebuilding. Final upload/processing status is pending; do not infer success
from authorization or preflight. Private receipts are kept separately under
`forge-testflight-20261105-build5`; the finalized QA6 kit is not rewritten.

Existing internal testers may automatically gain access through their group once
Apple processes the upload. No external distribution/submission, invitation,
manual notification, physical install, git push or website change is requested.

### TestFlight 0.1.0 (5) processed VALID (2026-11-05)

Apple `altool --validate-app` and `--upload-app` both completed with exit 0 and
success receipts. The subsequent processing-state GET failed in transport; no
upload was repeated. A later read-only API check confirmed build
`0840e776-f73e-49ec-8e4e-6b6803c9b4cc` as VALID, not expired, with internal state
IN_BETA_TESTING and external state READY_FOR_BETA_SUBMISSION. The preReleaseVersion
relationship confirms marketing version 0.1.0; ASC build attribute `version` is 5.

`autoNotifyEnabled` is true in Apple's beta detail; automatic Apple notifications
may occur. No manual notification/invitation or external beta submission was sent.
Direct GET of build/betaGroups is unsupported (403 GET_RELATED); exact group
membership/access was not separately verified and no group changes were made.
Existing internal access remains subject to Apple/group configuration. Sanitized
receipts/status are saved in `forge-testflight-20261105-build5`. Frozen QA6 and
blocked v4 kits remain unchanged with their original creation-time statuses.

Next gate is real-device testing via DEVICE_TESTING.md: focus/keyboard, native
downloads and Files export, camera/microphone consent and release, privacy
indicators, direct networking and WebRTC. These remain unverified; VALID and
IN_BETA_TESTING are Apple processing/distribution states, not device QA results.

## First local increment

- Native Android/iOS tab creation, selection and closure, bounded to 32 tabs.
- Versioned, bounded local storage of tab IDs, safe URLs, titles and selection.
- Atomic writes; malformed or future session files are not overwritten after a
  failed load. The UI reports unavailable persistence instead of claiming success.
- Restored URLs do not start remote page navigation on cold launch. Reload or
  selecting a saved tab explicitly loads it. Normal in-memory tab switching keeps
  the engine instance and its history until a page is unloaded or the app exits.
- The persisted snapshot is **not** full history/form-state restoration. Private
  browsing, durable downloads, password storage and sync remain separate work.
- iOS session files are excluded from backups and use file protection. Android
  uses app-private no-backup storage, with application backup already disabled.

## Local validation (2026-10-29)

- iOS: `xcodebuild test` on an isolated iPhone 18 Pro / iOS 27.0 simulator,
  with `-testLanguage en -testRegion US` and `-testLanguage ru -testRegion RU`:
  **8 passed, 0 failed in each language**. Covers session persistence, invalid
  snapshots, tab limits, independent views and cold restore without navigation.
- Source checks: `python3.12 -m unittest discover -s tests -p 'test_*.py'`:
  **84 passed**; `node --test tests/*.test.mjs`: **56 passed, 0 failed**.
- Android: `gradle --no-daemon :app:testDebugUnitTest :app:lintDebug
  :app:assembleDebug :app:assembleDebugAndroidTest`: **BUILD SUCCESSFUL**;
  **5 unit tests passed, 0 failures/errors/skips**. Three debug APKs (ARM64,
  ARMv7, x86_64) and the instrumentation APK were produced. These are local
  debug-signed builds, not release-signed distribution packages.
- Android lint: **0 errors, 7 warnings**: target API 35, four available dependency
  updates, missing explicit Android 12+ data-extraction rules, and status-text
  concatenation. Backup policy still needs device-transfer validation; app-private
  no-backup session storage is not a claim about all Gecko profile data.
- Android native runtime: `gradle --no-daemon :app:connectedDebugAndroidTest`
  on an isolated Android 15 / API 35 ARM64 ATD emulator: **BUILD SUCCESSFUL,
  7 passed, 0 failures/errors/skips**. Covers independent Gecko sessions,
  Activity recreation, saved-address restoration across Activity relaunches,
  corrupt-file preservation during edits/recreation, inactive-tab memory-pressure
  unloading, native input rejection and actual local-document loading in Gecko.
  The successful AVD used a 720×1280 display and host graphics; software-rendered
  attempts timed out during emulator startup before any Forge tests ran.
  These tests do not prove actual OS process-death recovery or absence of all
  engine background traffic; cold restoration checks saved state and native UI,
  not packet capture. Physical Android devices remain untested.

## Android hardening follow-up (2026-10-30)

- Updated the JSON unit-test dependency and AndroidX test core/runner/JUnit
  integration to the versions reported by lint. No engine dependency changed.
- Added explicit all-domain exclusions for legacy full backup, Android 12+
  cloud backup and device transfer, retaining `allowBackup=false`. Physical
  OEM transfer behavior is not yet validated.
- Replaced status-text concatenation with a localized format resource.
- Repeated the full debug build/unit-test/lint/instrumentation-APK command:
  **BUILD SUCCESSFUL**, **5 unit tests passed**, lint **0 errors, 1 warning**.
  Only `OldTargetApi` remains: target API 35 is deliberately unchanged until
  newer Android behavior is tested. No lint checks were disabled or suppressed.
- Source suite: **85 passed**. Added a regression test for every backup/transfer
  storage-domain exclusion.
- Final-source native runtime regression on an isolated Android 15 / API 35
  ARM64 ATD emulator: **7 passed, 0 failures/errors/skips**.
- `mobile/android/tests/process_death.py`: **2 host checks passed**. A native
  UI-created third tab, all saved URLs/titles/IDs and selection survived
  `am force-stop` and relaunch with PID **2897 → 3248**. A separately selected
  saved remote address was displayed awaiting explicit Reload in PID **3517**.
  This verifies abrupt process restart and URL-only session restoration, not
  OS low-memory killing, history/forms/password restoration or packet capture.
- Local evidence: `android-runtime-448f3949d2/summary.json`, `gradle.log` and
  `process-death/summary.json` plus UI XML, under the maintainer's isolated
  `forge-mobile-tabs-20261029` build directory. No production profile was used.

## Mobile downloads increment (2026-10-30, local only)

- Android consumes GeckoView's existing `WebResponse` stream; iOS implements
  `WKDownloadDelegate`. Neither re-fetches the URL in a separate HTTP client,
  overrides TLS challenges, invokes another application or opens a file.
- Explicit confirmation, one pending file per controller, bounded sanitized
  names, private cache staging and an explicit system document-export step.
  256 MiB limit; iOS progress cancellation is asynchronous and may overshoot
  that threshold in native buffers, but oversized completed files cannot export.
- Android preserves the staged source after export failure for explicit retry;
  partial provider-document cleanup is best-effort. Duplicate staging names use
  independent files. Public destination collisions are handled by system pickers.
- Foreground transfers only: leaving the app cancels the network transfer.
  Android configuration recreation retains the job. No persistent download queue,
  automatic network retries, background service or resume after process death.
- Android full debug build/unit-test/lint/instrumentation-APK command passed.
  A first isolated Android 15 ARM64 runtime run passed **12 tests, 0 failures**,
  including an actual Gecko HTTPS download, cancellation, truncation, local export
  and export-error retry. Process-restart checks also passed. A subsequent run
  passed **11/12**: the public HTTPS download timed out. Navigation-error
  diagnostics and full emulator logs were added; this failure remains unresolved
  until a new run confirms the result. A later run against the direct public
  `razex.shop/forge/SHA256SUMS` fixture passed **12/12**, both process-restart
  checks, and native Android confirmation → system picker → export verification:
  **1266 bytes**, SHA-256
  `030afac07742330996331a1a352852370d20f5f304107d5190264a0c5a45c681`.
  Evidence: local `android-runtime-c9bf26c5b3` reports and UI XML.
- Android unit tests: **9 passed**; latest lint: **0 errors, 1 OldTargetApi warning**.
  Source checks: **86 Python tests and 56 JavaScript tests passed**.
- Initial iOS English runtime run: **11/13 passed**. The new WKDownload test failed
  before confirmation and the existing local WebKit rendering test timed out.
  Tests now attach their views to an actual simulator window scene and restore the
  previous key window; failure reasons are recorded without logging URLs/credentials.
  A focused rerun is in progress; bilingual download validation is not complete.
  Interactive Files-provider exports and physical devices are not yet validated.
  Previous iOS tab/session results are not download results.
- A subsequent iOS probe reported `NSURLErrorDomain -1003` before WKDownload:
  the simulator cannot resolve the fixture host although host DNS and HTTPS work.
  A test-only loopback CONNECT relay is being used to isolate simulator DNS from
  download behavior. It connects only to `razex.shop:443`, never decrypts traffic,
  and leaves WebKit/URLSession certificate verification intact. Proxy configuration
  exists only in the XCTest target, never in the shipped app. System DNS/settings
  were not changed. The focused proxy-backed rerun passed **2/2**, including
  native WKDownload confirmation/staging and local WebKit rendering. The complete
  English and Russian suites subsequently passed **13/13 each, 0 failures**.
  A harness restart interrupted orchestration, not the completed focused tests;
  their xcresult was reused rather than rerun. Direct simulator DNS and physical
  device/interactive iOS Files-provider validation remain separate limitations.

## Desktop matrix

Existing CI covers Windows, Linux and macOS on x64/ARM64. For the already notarized
Mac ZIPs, `forge-signed-macos.yml` adds a separate native runner workflow that
checks pinned hashes, architecture, Developer ID, Hardened Runtime, stapled
notarization and the complete browser suite. It does not export keys, upload apps
or change OS trust policy. It is a local workflow addition until push/CI approval;
it must not be reported as a successful native Intel test before it runs.

## Remaining gates

The owner explicitly approved acceptance of `android-sdk-arm-dbt-license` for
the ARM64 ATD system image. The Android 35 ATD image and emulator are now
installed locally. Runtime validation uses a separate disposable AVD, never an
existing personal device/profile. Compilation/unit tests are not a substitute
for that runtime run, physical-device checks or actual process-death recovery.

1. Run mobile runtime tests, including activity/process lifecycle, inactive-tab
   isolation, corrupt storage and explicit restore; test physical phones/tablets.
2. Implement mobile downloads, permission prompts, data clearing and private tabs.
   Do not add automatic certificate exceptions or unrestricted external schemes.
3. Test the actual signed Intel package on native Intel CI or hardware.
4. Configure stable Android release signing and Windows publisher signing with
   owner-approved key storage. They are not configured in the current source;
   absence of configuration is not proof that no keys exist on the maintainer's Mac.
5. Produce installers/package formats with install, uninstall and upgrade tests
   that preserve the browser profile on every supported target.
6. Choose and track a maintained Firefox stable/ESR security baseline rather than
   presenting the current Nightly artifact snapshot as a production security base.
   Design a supported security-update service before enabling it: Gecko security
   intake, signed metadata and packages, rollback protection, staged rollout,
   interruption recovery, expiry checks and an accountable maintenance process.
   Do not redirect MAR/update endpoints to an unimplemented server or replace
   Mozilla's signature checks with plain download checksums.
7. Repeat long-duration authenticated use, sleep/wake, printing, manual screen
   reader and packet-level testing; publish results without personal profile data.

No git push, public release, TestFlight upload/distribution or tester invitations
are part of this local increment without separate owner approval.

## TestFlight upload authorization (2026-10-30)

The owner subsequently requested a new TestFlight upload. Preparation targets
`0.1.0 (3)`; App Store Connect currently contains build 2. This authorizes the
upload, not new tester invitations, external review/distribution, manual
notifications or a git push. Existing internal group `Close test` has access to
all builds and may automatically gain access after Apple processes the upload;
that pre-existing group setting is preserved.

Build **0.1.0 (3)** was signed, Apple-validated and uploaded successfully. App Store
Connect reports **VALID**, not expired, build ID
`6f372f2a-0a07-4fda-85db-22d84bc74845`. The existing internal `Close test` group
lists builds 3 and 2. Internal beta state is `READY_FOR_BETA_TESTING`; external
state is `READY_FOR_BETA_SUBMISSION`, not submitted for external review.
No tester invitations, explicit group assignments or manual notifications were
sent. Apple's build-level `autoNotifyEnabled` default is true; no external
distribution/review action was taken to trigger it.

Archive/upload automation checked the actual xcresult counts, source timestamps
and hashes, archive/IPA version, signing/profile/entitlements and Apple validation
before upload. A local source snapshot and manifest are retained alongside the
archive at `forge-testflight-20261030-build3` in the maintainer's build directory.
IPA: **148550 bytes**, SHA-256
`5170e850e96cdd4ae74fdb2e15030d022e9f4e94c6837dbf14c6d6a2f2f9fcf5`.
No git push or public download/site update accompanied this upload.

## iPhone visual feedback follow-up (2026-10-31, local only)

The owner reported that build 3's iPhone UI looked unfinished. The earlier test
results established behavior, not visual quality. Current local iOS sources add:

- A native, dark Forge start page instead of the empty white WKWebView surface.
- A bottom address/navigation dock, explicit input/placeholder colors, a fixed
  44 pt Go control and usable address-field width instead of equal toolbar sizing.
- Safe-area-aware full-width page presentation and keyboard-layout-guide docking.
- A native explicit-load placeholder for restored remote tabs; no startup URL load.
- Hidden routine debug/status chatter, with visible errors and storage warnings.
- New layout/keyboard tests and snapshot attachments covering compact portrait,
  landscape and tablet widths. An initial run found the dock extending below a
  smaller viewport; clamping it to the safe-area bottom fixed that regression.
  The subsequent UI/runtime run passed **16/16** (the network download test was
  excluded from this layout-focused run). **87 source tests passed**.
- Actual iPhone simulator screenshots were visually inspected and shown to the
  owner: `forge-iphone-ui-20261031/iphone-final-ru.png` in the local build folder.
  A dark launch storyboard replaces the default white startup surface.
- Snapshot review also found that the large start-page hero crowded small/landscape
  viewports. Compact adaptive spacing/type/logo behavior and an above-fold action
  assertion were added; the focused rendered-layout rerun passed **4/4** across
  five viewport sizes. Assertions run after UIKit commits adaptive layout changes.
- Review of tablet snapshots exposed a stale hidden-keyboard guide leaving dead
  space below the dock in resized fixtures. The dock now defaults to the safe-area
  bottom and follows the keyboard only for docked keyboard-frame notifications.
  An intermediate run caught a keyboard-position regression (**15/16**). The final
  keyboard check passed **1/1**, followed by **16/16** layout/runtime checks with
  **0 failures** (`ios-keyboard-v7.xcresult`, `ios-ui-final-v7.xcresult`). Final
  snapshots were inspected at compact portrait, landscape and tablet widths;
  the dock stays at the bottom when the keyboard is hidden and input stays above
  the actual software keyboard when editing. The network download test was not
  rerun in this UI-specific pass. Physical-device and manual screen-reader checks
  remain separate work, not implied by these simulator results.

Website documents are not force-themed. Android sources, the signed build 3 IPA,
its source snapshot and published assets are unchanged by this UI follow-up.
No new TestFlight upload or git push is part of this visual-feedback request.
