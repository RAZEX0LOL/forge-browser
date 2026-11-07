# Full-package desktop updater

This is a separate, manually invoked updater, not a replacement for Mozilla MAR
signature verification. First target: macOS ARM64. Windows/Linux installation is
disabled, not implied by Go's ability to cross-compile a binary.

## Build

Requires Go 1.27.3, Xcode command-line tools and the matching macOS SDK:

```sh
python3.12 forge/updater/build_macos.py --arch arm64 \
  --build-number 2026110801 --output /private/staging/bin/forge-update
python3.12 forge/scripts/package_macos.py --source /private/firefox-worktree \
  --output /private/staging/adhoc/Forge.app \
  --native-locale-stage /private/staging/native-ru \
  --updater-helper /private/staging/bin/forge-update
```

The helper, launcher and relauncher target macOS 13.0 explicitly. The builder sets
**both** deployment environment and CGo compiler/linker flags, and rebuilds all
objects. A final `minos 13.0` is not enough if the linker reports newer-OS input
objects. Such mixed candidates are rejected. The packager also checks helper
architecture and deployment target. Older macOS runtime acceptance is separate
from declaring that deployment target; do not manufacture it from build success.

The resulting app is initially ad-hoc only. Developer ID sign every Mach-O file
and bundle inside-out using `scripts/sign_macos.py`, notarize, staple and validate
the ticket, then repeat native runtime checks before publishing a new immutable
ZIP. No signing key, profile, raw private log or compiled app belongs in Git.

The UI command is **Check for Forge updates**, in the control center and command
palette. `Updates.sys.mjs` starts only the sibling `forge-update` executable,
passing a bounded `--locale=ru|en` argument, never a profile, URL or shell command.
Missing bootstrap helpers and unsupported platforms produce localized errors.
There is no unattended install flag. `--version` is a non-network build probe.

## Trust and replacement

- Manual consent before checking; cookie-free HTTPS with fixed updater User-Agent.
  IP/path/User-Agent can appear in normal server logs. No browsing data is sent.
- Pinned RSA-3072 release key, exact signed payload bytes, desktop-only channel and
  bundle identifier, target selection, sequence rollback floor and maximum 14-day
  metadata lifetime. The shared release key cannot turn Android metadata into a
  desktop offer: both clients enforce their channel/package schema.
- Same-server immutable ZIP URLs only, no redirects, credentials or query data.
  Exact streaming SHA-256/length, 600-MiB package cap, bounded archive entries and
  4-GiB expanded cap; reject traversal, duplicate entries, escaping symlinks and
  special file entries before extraction.
- `codesign --verify --deep --strict`, expected TeamIdentifier/bundle identifier
  and normal `spctl --assess` on the current and replacement app. Verify the new
  signed helper's build number/architecture against metadata. No Gatekeeper,
  quarantine, TLS, Safe Browsing or MAR bypass. Internet quarantine is applied to
  the downloaded replacement, never removed.
- Stage beside the app on its filesystem. No root request or privileged daemon:
  an unwritable application folder fails with a manual-install instruction.
- Confirm again after verification and completely quit Forge. Use native libproc
  executable paths, not `ps comm` (macOS truncates it even with `-ww`). Do not read
  process arguments. For privacy-restricted live processes, compare the kernel
  executable basename against bundle executables and fail closed on a possible
  match. Inconclusive relevant inspection blocks installation.
- Rename old app to a fresh `.backup-<build>-<timestamp>` sibling, then activate
  the replacement. Roll back our rename on failure when the destination remains
  absent. Existing backup/foreign destinations must never be intentionally
  overwritten. Only newly created private staging directories are cleaned.
- No profile location is passed to the helper or touched by replacement. Keep
  application backups until the new version has been validated; rolling back an
  application does not guarantee backwards compatibility of its browser profile.

State lives in `~/Library/Application Support/ForgeUpdates`, outside Firefox's
profile. It contains the highest accepted sequence and a mutually exclusive lock.
A stale lock after a crash blocks another updater; inspect the owned updater
process before removing that specific lock. There is no automatic lock deletion.

## Feed operations

Endpoint: `/forge/updates/desktop-macos-arm64.json` (`macos-intel` is reserved, not
automatically enabled). The signed payload uses `schemaVersion`,
`channel: desktop-development`, `packageName: org.forgebrowser.development`,
`sequence`, `issued`, `expires`, monotonic `buildNumber`, `versionName` and
`artifacts[target]` with URL, SHA-256 and bytes. Only a strictly higher build is
offered. Each distributed helper must be compiled with that build number.

Sign offline using `scripts/sign_update_manifest.py`. Preserve old envelopes and
packages, renew before expiry using a higher sequence, and atomically replace
only channel metadata after full artifact verification. The key stays outside
the server/repository. This is not a maintained security-update SLA or an
automatic Mozilla patch integration service.

## Validation

```sh
go test -race -p 1 ./...
```

Tests cover signature/tamper/expiry/rollback/target/channel rejection, URL scope,
stream bounds/hash, ZIP traversal and framework symlinks, retained backups,
rollback, and a real owned process that must prevent replacement. Firefox chrome
QA retains the exact action count (now 14) and additionally requires the localized
updater action; it does not execute native installer consent dialogs as a side
effect of a generic UI test. Actual signed-package replacement acceptance is a
separate release gate, not established by unit tests or source CI alone.
