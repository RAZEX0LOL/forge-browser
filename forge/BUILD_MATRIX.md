# Native build matrix

These are development artifact builds, not signed/notarized stable installers.
Desktop native Russian packaging is not yet included in the new CI matrix;
the Forge UI has its own ru/en catalogue while the upstream base locale is en-US.
The original locally built macOS arm64 prerelease separately includes native ru.

## Completed first native matrix

Workflow: https://github.com/RAZEX0LOL/forge-browser/actions/runs/40678188670

| Target | Build | Browser smoke |
| --- | --- | --- |
| Linux x64 (Ubuntu 24.04) | Portable tar.xz produced | **260 passed** |
| macOS Intel | Ad-hoc app / portable zip produced | **270 passed**, including eight macOS AX bridge checks |
| Windows x64 | Portable zip produced | Stopped after 156 checks at a Python FTL text-decoding error; UTF-8 fix under retest |

Failed-job packages are not uploaded as validated artifacts. The source retains
all checks; UTF-8 mode is explicitly enabled on CI, and the FTL resource reader
now declares its encoding. The Windows failure was in the Python test harness,
not evidence that the browser's Russian strings failed to render.

Native ARM64 Linux, Windows and macOS jobs are also defined. Each new package
checks its runtime's ELF/PE/Mach-O architecture before publication to CI artifacts;
an x64 package may not be relabeled as ARM64. Their results must be assessed
separately; defining a job is not successful platform validation.

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

GitHub workflow artifacts expire; a public release requires a separate explicit
upload with source commit, exact platform, checksums and limitations. Source and
engine signatures are not replaced with claims of publisher/notarization status.
