# Host-driven Android checks

## Server update acceptance

`update_flow.py` targets only `emulator-5588`, AVD `ForgeUpdatesFlow20261107`.
Use a fresh full API35 Google APIs ARM64 image: Google ATD omits the unknown-app
source settings activity and cannot establish installer acceptance. Do not grant
installation via appops/root to turn this missing UI into a pass.

The seed is an explicitly test-only versionCode-1 build of the updater sources,
with only versionCode/versionName changed. It is not the original public v1 and
must never be distributed. `bootstrap` checks the genuinely absent public feed
before first deployment; `prepare` seeds a new full-system AVD after that negative
control has already been recorded. `install` enables the source permission in
real Settings UI, downloads the signed public artifact through the app, verifies
the app's separate confirmation and the real Android installer Update button,
then asserts installed versionCode 2 and byte-identical synthetic/regular data.
Never apply this driver to a physical device or personal AVD.

Failed selectors, ATD settings resolution, UI hierarchies and initial runtime
startup evidence remain in private staging. Compose Settings exports a checkable
`android.view.View`, not necessarily `android.widget.Switch`; the driver checks
OS title, checkability and before/after checked state instead of guessing a class.

The HTTPS download regression uses an immutable November `.bin` checksum fixture,
checking both 1375 bytes and its exact SHA-256. It must not depend on the mutable
current `SHA256SUMS`, whose bytes necessarily change when a new APK is published.

## Current upload-form driver

`upload_form.py` drives real native UI on the separately owned
`ForgeUpload20261107` AVD at `emulator-5584`. It never uses ActivityMonitor,
synthetic FilePrompt objects or manually delivered picker results. It opens the
loopback HTTPS form through confirmed ACTION_VIEW, taps the HTML file control,
confirms Forge's warning and selects a fixed file in the actual DocumentsUI.

The server is `../../tests/upload_fixture.py`: IPv4 loopback only, TLS 1.2+,
bounded request body, fixed fixture bytes and exact multipart filename checks.
Its `requests.jsonl` counts **all** POST attempts, including rejected bodies;
`receipts.jsonl` contains only accepted filename/size/SHA-256 receipts. Cancellation
must add zero POST attempts, not merely zero successful receipts. Private mode
also preserves regular-session/library bytes, inode and nanosecond mtime.

Prerequisites are deliberate, not automatic bypasses:

- Create a fresh upload-only AVD; never use personal or baseline acceptance data.
- Generate a one-day CA and server certificate with an IP SAN for `10.0.2.2`.
  Keep private keys outside the repository in owner-only `*.env` files.
- First prove the browser rejects the untrusted certificate with
  `--expect-untrusted`. Stop the isolated Forge package before NSS DB operations.
- Import that CA only into the isolated Gecko profile using NSS `certutil` on
  private copies of its databases. Transfer both modified `cert9.db` **and**
  `key4.db` back while the package is stopped; trust metadata depends on both.
  Do not change production runtime settings or disable certificate validation.
- Push the fixed `PAYLOAD` from the fixture module as
  `/sdcard/Download/forge-upload-fixture.txt` and scan it into MediaStore so the
  real system picker can select it. This is selected test data, not a browser
  broad-storage permission.
- Pass `--exercise-upload --case regular|cancel|private --receipts <server-log>`
  with a matching `--url https://10.0.2.2:<port>/form?case=<case>` and a fresh
  `--output` directory. Every UI dump is retained with a unique sequence number.
- Also prove rejection of a same-CA certificate missing the address in its SAN.
  No certificate exceptions, public deployment or physical device are required.

This fixture does not establish arbitrary provider, camera, folder, multiple-file
or physical-device compatibility. Earlier failed evidence must remain retained.

## Historical drivers

`process_death.py` and `download_export.py` are retained from the earlier mobile
prototype validation. They require an explicitly selected isolated `forge-` AVD
and must never target a physical device or personal profile.

Their UI selectors and pinned download fixture describe the older prototype;
they have not been revalidated against the current tab overview/address-cancel
interface. Do not use a historical success from these scripts as current
acceptance. Current model/native regression tests are under `app/src/test` and
`app/src/androidTest`; checkpoint results and remaining real-device gates are in
`../../SOURCE_CHECKPOINT.md` and `../../../RELEASE_ROADMAP.md`.
