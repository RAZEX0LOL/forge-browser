import importlib.util
from pathlib import Path
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("forge", PROJECT / "scripts/forge.py")
forge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forge)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "browser/base/content").mkdir(parents=True)
        (self.root / "browser/base/content/browser.xhtml").write_text(
            "<head>\n" + forge.ANCHOR + "\n</head>\n")
        (self.root / "browser/base/jar.mn").write_text(
            "browser.jar:\n% content browser %content/browser/\n#ifdef XP_MACOSX\n#endif\n")
        (self.root / "browser/app/profile").mkdir(parents=True)
        (self.root / "browser/app/profile/firefox.js").write_text('pref("existing.pref", true);\n')
        (self.root / "browser/app/distribution").mkdir()
        (self.root / "browser/app/distribution/moz.build").write_text('DIST_SUBDIR = ""\n')
        (self.root / "browser/components/preferences").mkdir(parents=True)
        (self.root / "browser/components/preferences/preferences.xhtml").write_text(
            '<html><body>\n        <html:div id="search-container">\n</html:div></body></html>\n')
        (self.root / "browser/components/preferences/main.js").write_text('const icon = "chrome://global/skin/illustrations/kit-happy.svg";\n')
        branding = self.root / "browser/branding/unofficial/locales/en-US"
        branding.mkdir(parents=True)
        branding.joinpath("brand.ftl").write_text("\n".join(
            f"-{key} = Nightly" for key in ["brand-shorter-name", "brand-short-name", "brand-shortcut-name",
                                           "brand-full-name", "brand-product-name", "vendor-short-name"]))
        branding.joinpath("brand.properties").write_text("brandShorterName=Nightly\nbrandShortName=Nightly\nbrandFullName=Nightly\n")
        fixtures = {
            "devtools/server/connectors/js-process-actor/target-watchers/window-global.sys.mjs":
                'subject.defaultView.addEventListener("pageshow", handleEvent, {\nsubject.defaultView.addEventListener("pagehide", handleEvent, {',
            "devtools/server/connectors/js-process-actor/DevToolsProcessParent.sys.mjs":
                'return this.sendAsyncMessage("DevToolsProcessParent:destroyWatcher", {',
            "devtools/server/actors/watcher.js": '''      const domProcesses = ChromeUtils.getAllDOMProcesses();
      for (const domProcess of domProcesses) {
        domProcess.getActor(this._jsActorName).destroyWatcher({
          watcherActorID: this.actorID,
        });
      }''',
            "devtools/server/actors/watcher/ParentProcessWatcherRegistry.sys.mjs":
                'let isJSProcessActorRegistered = false;\n  maybeUnregisterJSActors() {\n    if (sessionDataByWatcherActor.size == 0) {',
            "toolkit/mozapps/extensions/content/components/addon-list.mjs": "class List {\n  createEmptyListMessage() {\n  }\n}\n",
            "browser/components/downloads/content/contentAreaDownloadsView.xhtml": '<window>\n  <richlistbox flex="1" id="downloadsListBox"/>\n</window>\n',
            "browser/components/aboutlogins/content/aboutLogins.html": '<img src="chrome://global/content/megalist/icons/cpm-fox-illustration.svg">',
        }
        for name, content in fixtures.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

    def prepare(self):
        return forge.prepare(self.root, verify_revision=False)

    def test_prepare_is_idempotent(self):
        self.assertEqual(self.prepare(), 17 + len(forge.FILES))
        state = (self.root / forge.STATE).read_bytes()
        self.prepare()
        self.assertEqual(state, (self.root / forge.STATE).read_bytes())
        xhtml = (self.root / "browser/base/content/browser.xhtml").read_text()
        self.assertEqual(xhtml.count(forge.HOOK), 1)

    def test_jar_entries_outside_platform_conditionals(self):
        self.prepare()
        jar = (self.root / "browser/base/jar.mn").read_text()
        self.assertLess(jar.index("content/browser/forge/"), jar.index("#ifdef"))
        for name in forge.FILES:
            self.assertIn(f"content/browser/forge/{name}", jar)

    def test_preserves_local_edits(self):
        self.prepare()
        target = self.root / "browser/base/content/forge/forge.css"
        target.write_text("user changes")
        with self.assertRaisesRegex(ValueError, "Local changes"):
            self.prepare()
        self.assertEqual(target.read_text(), "user changes")

    def test_preserves_existing_mozconfig(self):
        (self.root / ".mozconfig").write_text("user configuration")
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            self.prepare()
        self.assertFalse((self.root / forge.STATE).exists())
        self.assertNotIn(forge.HOOK, (self.root / "browser/base/content/browser.xhtml").read_text())

    def test_upstream_hook_drift_fails_before_writes(self):
        (self.root / "browser/base/content/browser.xhtml").write_text("different upstream")
        with self.assertRaisesRegex(ValueError, "hook changed"):
            self.prepare()
        self.assertFalse((self.root / ".mozconfig").exists())

    def test_duplicate_hook_rejected(self):
        with self.assertRaises(ValueError):
            forge.integrate_xhtml(forge.ANCHOR + "\n" + forge.ANCHOR)

    def test_revision_mismatch_rejected(self):
        original = forge.git
        forge.git = lambda *args: "wrong-revision"
        try:
            with self.assertRaisesRegex(ValueError, "revision differs"):
                forge.prepare(self.root)
        finally:
            forge.git = original

    def test_resource_manifest_can_grow(self):
        old = "browser.jar:\n# Forge overlay\n        content/browser/forge/forge.js (content/forge/forge.js)\n% content browser %content/browser/\n"
        updated = forge.integrate_jar(old)
        self.assertIn("content/browser/forge/start.html", updated)
        self.assertEqual(updated.count("content/browser/forge/forge.js"), 1)
        self.assertEqual(updated, forge.integrate_jar(updated))

    def test_privacy_defaults_and_policy_packaged(self):
        self.prepare()
        prefs = (self.root / "browser/app/profile/firefox.js").read_text()
        self.assertIn('pref("existing.pref", true)', prefs)
        self.assertIn('pref("datareporting.healthreport.uploadEnabled", false, locked)', prefs)
        policy_file = self.root / "browser/app/distribution/policies.json"
        self.assertTrue(policy_file.is_file())
        self.assertIn('FINAL_TARGET_FILES.distribution += ["policies.json"]',
                      (self.root / "browser/app/distribution/moz.build").read_text())

    def test_settings_header_integrated_without_replacing_controls(self):
        self.prepare()
        page = (self.root / "browser/components/preferences/preferences.xhtml").read_text()
        self.assertEqual(page.count('id="forge-settings-header"'), 1)
        self.assertEqual(forge.integrate_preferences(page), page)
        self.assertIn('id="search-container"', page)

    def test_settings_structure_drift_rejected(self):
        with self.assertRaisesRegex(ValueError, "settings structure changed"):
            forge.integrate_preferences("different upstream")

    def test_native_ui_branding_is_forge(self):
        self.prepare()
        ftl = (self.root / "browser/branding/unofficial/locales/en-US/brand.ftl").read_text()
        self.assertNotIn("Nightly", ftl)
        self.assertIn("-brand-short-name = Forge", ftl)
        jar = (self.root / "browser/base/jar.mn").read_text()
        self.assertIn("override chrome://branding/content/icon32.png", jar)

    def test_devtools_teardown_waits_for_cleanup_acknowledgement(self):
        self.prepare()
        parent = (self.root / "devtools/server/connectors/js-process-actor/DevToolsProcessParent.sys.mjs").read_text()
        registry = (self.root / "devtools/server/actors/watcher/ParentProcessWatcherRegistry.sys.mjs").read_text()
        watcher = (self.root / "devtools/server/actors/watcher.js").read_text()
        self.assertIn('sendQuery("DevToolsProcessParent:destroyWatcher"', parent)
        self.assertIn('pendingTeardowns.size === 0', registry)
        self.assertIn('deferUnregisterUntil(Promise.allSettled(pending))', watcher)

    def test_devtools_teardown_structure_drift_fails_closed(self):
        for kind in ("parent", "registry", "watcher", "lifecycle"):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "teardown changed"):
                forge.integrate_devtools_teardown("unexpected upstream", kind)

    def test_detached_devtools_documents_do_not_register_lifecycle_listeners(self):
        self.prepare()
        text = (self.root / 'devtools/server/connectors/js-process-actor/target-watchers/window-global.sys.mjs').read_text()
        self.assertIn('subject.defaultView?.addEventListener("pagehide"', text)
        self.assertIn('subject.defaultView?.addEventListener("pageshow"', text)
        self.assertEqual(text, forge.integrate_devtools_teardown(text, 'lifecycle'))

    def test_devtools_drift_does_not_partially_prepare_checkout(self):
        target = self.root / "devtools/server/actors/watcher.js"
        target.write_text("changed upstream teardown")
        with self.assertRaisesRegex(ValueError, "teardown changed"):
            self.prepare()
        self.assertNotIn(forge.HOOK, (self.root / "browser/base/content/browser.xhtml").read_text())
        self.assertFalse((self.root / forge.STATE).exists())

    def test_existing_forge_headers_migrate_to_russian_idempotently(self):
        settings = '<header id="forge-settings-header">FORGE / CONTROL ROOM</header>'
        downloads = '<header id="forge-downloads-header">FORGE / LOCAL FILES</header>'
        settings = forge.integrate_preferences(settings)
        downloads = forge.integrate_downloads(downloads)
        self.assertIn("FORGE / НАСТРОЙКИ", settings)
        self.assertIn("FORGE / ЗАГРУЗКИ", downloads)
        self.assertEqual(settings, forge.integrate_preferences(settings))
        self.assertEqual(downloads, forge.integrate_downloads(downloads))

    def test_fluent_markup_is_stable_and_only_known_headers_receive_the_script(self):
        text='<html:header id="forge-settings-header"><html:h2>Heading</html:h2></html:header>'
        result=forge.localize_page_markup(text,'forge-settings-header',{'Heading':'forge-settings-title'})
        self.assertEqual(result.count('data-forge-l10n="forge-settings-title"'),1)
        self.assertEqual(result.count('chrome://browser/content/forge/localize.js'),1)
        self.assertEqual(result,forge.localize_page_markup(result,'forge-settings-header',{'Heading':'forge-settings-title'}))
        with self.assertRaisesRegex(ValueError,'localization header changed'):
            forge.localize_page_markup('<h2>Unrelated native page</h2>','forge-settings-header',{})

    def test_addon_empty_state_uses_native_fluent_not_hardcoded_prose(self):
        text=forge.integrate_addon_list('  createEmptyListMessage() {\n  }')
        self.assertIn('createStrings(window)("forge-extensions-empty")',text)
        self.assertNotIn('title.textContent = "Расширений пока нет."',text)
        self.assertEqual(text,forge.integrate_addon_list(text))


if __name__ == "__main__":
    unittest.main()
