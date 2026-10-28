# Native build matrix

These are development artifact builds, not signed/notarized stable installers.
Desktop native Russian packaging is not yet included in the new CI matrix;
the Forge UI has its own ru/en catalogue while the upstream base locale is en-US.
The original locally built macOS arm64 prerelease separately includes native ru.

## Completed native builds

[Public multiplatform prerelease](https://github.com/RAZEX0LOL/forge-browser/releases/tag/v0.1.0-dev.20261028-multiplatform).
All 13 uploaded asset digests were checked against the published manifest and
checksums. Exact per-asset source commits remain in `MANIFEST.json`; subsequent
documentation commits do not change those build origins.

| Target | Build | Browser smoke |
| --- | --- | --- |
| Linux x64 (Ubuntu 24.04) | Portable tar.xz produced | **260 passed** |
| macOS Intel | Ad-hoc app / portable zip produced | **270 passed**, including eight macOS AX bridge checks |
| Windows x64 | Published portable ZIP | **260 passed** |
| Linux ARM64 | Published portable tar.xz | **260 passed** on native ARM64 CI |
| Windows ARM64 | Published portable ZIP | **260 passed** on native ARM64 CI |
| macOS Apple Silicon | Published native-Russian DMG; separate CI ZIP built | **285 local checks** for the DMG; **270 passed** for the separate CI build |

Successful artifact/test origins:

- [Linux x64 and Intel macOS](https://github.com/RAZEX0LOL/forge-browser/actions/runs/40678188670)
- [Linux and Windows ARM64](https://github.com/RAZEX0LOL/forge-browser/actions/runs/40681319721)
- [Final Windows x64](https://github.com/RAZEX0LOL/forge-browser/actions/runs/40682181631)
- [Final macOS ARM64 CI](https://github.com/RAZEX0LOL/forge-browser/actions/runs/40683919981)
- [Android and iOS prototypes](https://github.com/RAZEX0LOL/forge-browser/actions/runs/40683736410)

The first two overall workflows included failed jobs later fixed and retested;
only their successful target artifacts were published. Windows UTF-8 and history
callback test-harness issues and macOS `lipo` argument ordering were fixed without
removing checks. ELF/PE/Mach-O architecture was verified; x64 packages were not
relabeled as ARM64.

Android unit tests, lint and two native UI/Gecko tests passed on an x86_64 emulator.
Three ABI-specific debug APKs are published; physical ARM devices remain untested.
iOS passed four XCTest cases in each of English and Russian on Simulator and built
an unsigned device archive. Neither iOS archive is an installable signed IPA.

## Manual dispatch

`Forge native desktop builds` supports `all`, individual targets, and `arm-desktops`.
It installs build tools only on disposable hosted runners, builds the integrated
source, runs the real browser integration suite in isolated profiles and uploads
archives only after that suite passes. No user profiles or signing keys are read.
Windows uses a pinned official MozillaBuild 4.2.1 installer with a required SHA-256,
corroborated against its Chocolatey verification record. Antivirus exclusions and
trust-policy changes are not configured.

`Forge mobile prototypes` builds separate GeckoView Android and WebKit iOS apps;
see [mobile/README.md](mobile/README.md). Simulator archives are not installable
iPhone IPAs. Mobile checks do not inherit the desktop check counts.

GitHub workflow artifacts expire; the public prerelease preserves the selected
downloads with source commits, checksums and limitations. The [manual publisher
run](https://github.com/RAZEX0LOL/forge-browser/actions/runs/40687274486) succeeded.
This is not an automatic update service or publisher/notarization certification.
