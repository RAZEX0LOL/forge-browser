# Manual standard WebKit upload UI check

Use the separate `ForgeMobileUploadUI` scheme, not the ordinary keyboard suite.
It requires `FORGE_UPLOAD_FIXTURE_URL=https://127.0.0.1:<port>/form?case=cancel`
from `../../tests/upload_fixture.py` and an explicitly owned isolated simulator
whose keychain trusts that fixture's one-day CA. Never install test trust into
the Mac or a personal simulator/device, and never bypass WebKit TLS challenges.

The UI test uses the app's unmodified default WKUIDelegate upload behavior:
real HTML input, Safari-style menu, Choose File, system Files panel and Cancel.
The host runner must additionally assert that the server's `requests.jsonl`
contains no new POST attempt (including rejected requests). UI evidence alone
does not prove that nothing reached the server.

On iOS27 the Files panel exports `Browse View (Picker)` and navigation identifier
`FullDocumentManagerViewControllerNavigationBar`, even when Recents is selected.
Do not identify it by a guessed Browse navigation title. Preserve failed logs,
screenshots, recordings and source snapshots; never extend deadlines or remove
the panel/cancellation assertions to manufacture a pass.

This does not validate successful file submission, an iOS custom upload guard,
physical providers or exact iOS17/18.4 behavior. Those runtimes were unavailable
in the current local environment. Deployment target remains iOS17.
