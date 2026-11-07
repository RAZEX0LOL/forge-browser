# Mobile source checkpoint — 2026-11-07

This is a development-source checkpoint, not a binary release or daily-use
readiness claim. The owner authorized committing/pushing these sources to the
`forge` branch. That authorization does not include a new TestFlight upload,
release publication, website deployment or Apple capability request.

## Validation scope

| Scope | Latest completed evidence |
| --- | --- |
| Source checks | Node 56/56; Python 96/96; Python compilation and diff whitespace checks passed |
| iOS current production sources | Native 64/64 per language and UI 9/9 per language, 146 executions across separate ru/en native/UI runs |
| Android previous stage-4a snapshot | Native 41/41, unit 27/27; lint only OldTargetApi |
| Android current OS-link-entry delta | Native 49/49, unit 31/31, plus separate startup controls 2/2; lint only OldTargetApi. Earlier failures remain preserved |

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
