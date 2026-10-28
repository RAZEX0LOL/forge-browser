# Apple signing

`scripts/sign_macos.py` creates a separate Developer ID signed copy of a packaged
Forge development app. It never overwrites the source app and never exports a
Keychain private key. Pass the installed certificate SHA-1 and team explicitly:

```sh
python3 scripts/sign_macos.py --source-app /path/to/original/Forge.app \
  --output-app /path/to/new/Forge.app --identity CERTIFICATE_SHA1 --team TEAM_ID
```

All Mach-O files and nested bundles are signed inside-out, with secure timestamps
and Hardened Runtime. Signing does not use `--deep`; verification does. Each
signed component is checked for the expected team and Hardened Runtime flag.

Entitlements follow the upstream production policy in
`security/mac/hardenedruntime/production/`: JIT is allowed for the browser and
content process, and library-validation exceptions are scoped to the browser,
media helper and security-module helper for third-party CDM/PKCS#11 modules.
Other utilities/libraries do not receive those exceptions. Debugger and DYLD
environment entitlements are not enabled. OS trust settings are never changed.

Mozilla-only application identifiers, profile groups and restricted passkey
entitlements are deliberately excluded. This is not full Mozilla production
signing equivalence; platform passkeys require separate Apple eligibility and
provisioning for Forge and are not claimed to work.

After signing, run isolated browser smoke tests again, submit a ZIP of the app to
Apple's notary service, require `Accepted`, staple and validate the ticket, and
assess the app with Gatekeeper. A signing report alone is **not** notarization.
Repackage only after stapling, then generate new SHA-256 checksums. Existing
development release assets and their provenance must not be silently replaced.

## iOS

The mobile project remains a WebKit prototype. Register its exact Bundle ID in
the correct developer team and use a dedicated App Store distribution profile.
Apple Distribution certificates/private keys and provisioning profiles belong
outside this repository. Team/profile selection can be passed as local Xcode
build settings without committing personal signing configuration.

Export an archive using `method=app-store-connect` and `destination=export` to
produce a local IPA without uploading it. Such an IPA is for TestFlight/App Store
processing, not unrestricted direct installation. Device testing needs a suitable
development/ad-hoc profile or a processed TestFlight build.

App Store Connect API keys can register Bundle IDs and manage certificates and
profiles. A new app record must be created on the App Store Connect website;
the public apps API does not create it. Uploading builds, distributing TestFlight
builds, submitting for review and releasing publicly are separate actions.

Never commit `.p8`, PEM/private-key files, PKCS#12 exports, API environment files,
JWTs, device identifiers or provisioning profiles. Notarization does not imply
App Store approval, browser privacy certification or automatic security updates.
