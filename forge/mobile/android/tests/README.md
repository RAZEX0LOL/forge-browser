# Host-driven Android checks

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
