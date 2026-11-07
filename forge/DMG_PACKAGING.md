# macOS drag-to-Applications images

`scripts/package_dmg.py` wraps an existing Developer ID signed, notarized and
stapled **unchanged** Forge.app. It does not build a new browser, change its icon,
re-sign its contents, move profiles or install into the maintainer's Applications.
ZIP remains the full-package updater format; a DMG is the manual installation UI.

```sh
python3.12 -m venv /private/staging/dmg-venv
/private/staging/dmg-venv/bin/pip install -r forge/requirements-dmg.txt
/private/staging/dmg-venv/bin/python forge/scripts/package_dmg.py \
  --app /private/staging/signed/Forge.app \
  --output /private/staging/Forge-development-YYYYMMDD-macos-arm64.dmg \
  --work /private/staging/new-dmg-work \
  --identity "$DEVELOPER_ID_IDENTITY"
```

Both output and work directory must be new. The HFS+ image contains Forge.app,
an `/Applications` symlink, a hidden background, Finder icon-view positions and
a volume icon copied from the application's `forge.icns`. The app's Info.plist
must reference its real ICNS icon. Byte hashes, executable modes and symlink
targets are compared before and after packaging; the mounted app's signature and
stapled ticket are checked. No Finder UI scripting or quarantine removal.

Firefox's `CFBundleIconName=AppIcon` selects its upstream asset-catalog icon and
can override `CFBundleIconFile`. `package_macos.py` removes that inherited key;
the DMG builder rejects bundles that still have an asset-icon override. Changing
the signed Info.plist requires signing and notarizing the app again, not patching
it inside a released image. Never infer icon acceptance merely from ICNS presence.

On systems that restyle application icons, raw ICNS pixels need not equal the
NSWorkspace output. Compare the installed application's NSWorkspace icon to an
independent minimal test bundle containing only the same Forge ICNS, with no
upstream asset catalog. Preserve both rendered images. This distinguishes the
real Forge mark from the inherited Nightly icon without disabling OS rendering.

The **disk image itself** is Developer ID signed, then must be submitted once to
Apple's notary service. Save the submission receipt; on a timeout inspect the
existing submission instead of automatically uploading again. Staple and validate
the DMG ticket, verify the image and signature, then calculate the final SHA-256
and size. Never publish a pre-stapling hash or overwrite an older filename.

Acceptance: mount read-only without opening Finder, inspect the Applications
symlink and Finder metadata, copy Forge.app into a new owned test directory,
unmount the image, and test that copy's launcher with a disposable browser/profile
registry. Check the system-resolved application icon and original resource seal.
This is a copy/install check, not a claim that actual Finder drag-and-drop or a
newer-version updater GUI has been automated.

If `spctl` reports `security disabled`, preserve that output and explicitly mark
enabled-Gatekeeper runtime acceptance as unverified. Do not change the host's
Gatekeeper configuration, strip quarantine or infer a protection pass from an
assessment override. Developer ID signature and stapled tickets are independent
checks that must still pass.
