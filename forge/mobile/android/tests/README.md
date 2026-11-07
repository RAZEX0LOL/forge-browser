# Historical host-driven Android checks

`process_death.py` and `download_export.py` are retained from the earlier mobile
prototype validation. They require an explicitly selected isolated `forge-` AVD
and must never target a physical device or personal profile.

Their UI selectors and pinned download fixture describe the older prototype;
they have not been revalidated against the current tab overview/address-cancel
interface. Do not use a historical success from these scripts as current
acceptance. Current model/native regression tests are under `app/src/test` and
`app/src/androidTest`; checkpoint results and remaining real-device gates are in
`../../SOURCE_CHECKPOINT.md` and `../../../RELEASE_ROADMAP.md`.
