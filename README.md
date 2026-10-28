# Forge Browser

A development fork of [Mozilla Firefox](https://github.com/mozilla-firefox/firefox),
maintained by [RAZEX0LOL](https://github.com/RAZEX0LOL). Mozilla's history, license
notices and third-party attribution are retained. Forge is not a Mozilla product
or an official Firefox release.

Forge adds native vertical tabs, workspaces, split-view integration, a command
palette, appearance customization, AMOLED/Glass themes, privacy defaults, and
built-in Russian localization alongside English fallback.

**Development software, not a production-ready browser.** There is no supported
automatic security-update service. Do not treat this snapshot as a maintained,
secure replacement for an up-to-date browser.

**[Forge website and downloads](https://razex.shop/forge/)** — platform selection,
notarized macOS ZIPs, checksums and explicit development/mobile limitations.

## Platform status

[Download the multiplatform development prerelease](https://github.com/RAZEX0LOL/forge-browser/releases/tag/v0.1.0-dev.20261028-multiplatform).
Its 13 assets include the packages below, `MANIFEST.json` with exact per-package
source commits, and `SHA256SUMS`.

| Platform | Actual status |
| --- | --- |
| macOS Apple Silicon | Published native-Russian DMG: 285 local browser checks; separate CI build: 270 passed; ad-hoc signed, not notarized |
| macOS Intel | Native development app built; 270 browser checks passed on Intel CI |
| Windows x64 | Published portable ZIP; 260 browser checks passed on native CI |
| Linux x64 | Native portable development build produced; 260 browser checks passed on Linux CI |
| Linux ARM64 / Windows ARM64 | Published portable packages; 260 browser checks passed on each native ARM64 runner |
| Android | Published GeckoView debug APKs for arm64-v8a, armeabi-v7a and x86_64; unit tests, lint and two x86_64 emulator tests passed; physical ARM devices untested |
| iOS / iPadOS | Published WebKit Simulator ZIP and unsigned device XCArchive; four native tests passed in English and Russian on Simulator; no installable signed IPA |

No placeholder images or upstream Firefox binaries are presented as Forge builds.
Android and iOS are separate prototypes, not ports of this desktop interface.
See [`forge/mobile/README.md`](forge/mobile/README.md) for their limited scope.

## Source layout and builds

This branch starts at Firefox commit
`efd2d1e6f77570ae6bc5294731a68101e45c81a3`. The native desktop integration is
committed in the upstream tree. [`forge/`](forge/) contains the editable overlay,
preparation scripts, pinned inputs, documentation and tests.

The tested packaging path is currently an **artifact development build**: it
reuses Mozilla's compiled Gecko; it is not a full independent Gecko toolchain.
See [`forge/README.md`](forge/README.md) and
[`forge/RELEASE_STATUS.md`](forge/RELEASE_STATUS.md) before building or distributing.
For the pinned preparation scripts, place a clean upstream checkout **outside**
the Forge project directory; do not run the overlay preparation script against
this already-patched fork. The script intentionally rejects that layout.

Source checks (these do not build a browser):

```sh
cd forge
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -p 'test_*.py'
```

## License and attribution

Original Mozilla and third-party code retains its existing licenses: see
[`LICENSE`](LICENSE), the [license template](toolkit/content/license.html.mako)
and [license texts](toolkit/content/licenses/).
Forge additions are available under MPL-2.0; see [`forge/LICENSE`](forge/LICENSE).
No rights to Mozilla's trademarks are granted. The name Forge is provisional;
trademark clearance has not been completed.

Machine-local profiles, browsing data, build caches, credentials and audit logs
are not published. Local test counts in historical documentation are maintainer
observations, not independent certification or results for unbuilt platforms.
