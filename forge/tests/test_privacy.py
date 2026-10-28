import importlib.util
import json
import re
from pathlib import Path
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forge", PROJECT / "scripts/forge.py")
forge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forge)


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PROJECT / "privacy.json").read_text())
        self.prefs, raw = forge.privacy_outputs(PROJECT)
        self.policies = json.loads(raw)["policies"]

    def test_every_privacy_pref_is_locked(self):
        for name, value in self.config["locked"].items():
            self.assertIn(f"pref({json.dumps(name)}, {json.dumps(value)}, locked);", self.prefs)

    def test_reporting_is_disabled_in_defaults(self):
        for name in ["datareporting.healthreport.uploadEnabled", "datareporting.usage.uploadEnabled",
                     "datareporting.policy.dataSubmissionEnabled", "toolkit.telemetry.enabled",
                     "browser.newtabpage.activity-stream.telemetry", "app.normandy.enabled"]:
            self.assertIs(self.config["locked"][name], False)
        self.assertTrue(self.policies["DisableTelemetry"])
        self.assertTrue(self.policies["DisableFirefoxStudies"])

    def test_safety_and_updates_not_disabled(self):
        for name in self.config["locked"]:
            self.assertFalse(name.startswith(("browser.safebrowsing.", "app.update.",
                                              "security.", "services.settings.")), name)
        for name in ["DisableAppUpdate", "DisableSecurityBypass", "DisableSystemAddonUpdate"]:
            self.assertNotIn(name, self.policies)

    def test_newtab_is_offline_and_has_no_scripts(self):
        page = (PROJECT / "overlay/start.html").read_text()
        self.assertNotIn("<script", page.lower())
        self.assertNotIn('src="https:', page)
        self.assertNotIn('href="https:', page)
        self.assertIn("default-src 'none'", page)
        css = (PROJECT / "overlay/start.css").read_text()
        self.assertNotIn("@import", css)
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        self.assertNotIn("https://", css)

    def test_no_remote_search_suggestions(self):
        self.assertIs(self.config["locked"]["browser.search.suggest.enabled"], False)
        self.assertIs(self.config["locked"]["browser.urlbar.suggest.searches"], False)


if __name__ == "__main__":
    unittest.main()
