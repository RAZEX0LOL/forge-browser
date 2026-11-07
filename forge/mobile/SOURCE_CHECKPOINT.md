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
| Android current OS-link-entry delta | Under validation: expected 49 native +31 unit; do not substitute the stage-4a results |

iOS accepted evidence: `forge-mobile-new-tab-links-20261107-ios-v3` (native) and
`forge-mobile-new-tab-links-20261107-ios-v4` (UI-only test delta). Android stage-4a:
`forge-mobile-new-tab-links-20261107-android-v7`. The current Android OS-link work
is recorded separately in `forge-mobile-external-links-20261107-android-v2`.
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

- Current Android external-link integration acceptance; actual OS chooser/default
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
