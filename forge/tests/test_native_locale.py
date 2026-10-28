import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import native_locale as native


class NativeLocaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.stage=self.root/'locale';self.stage.mkdir()
        self.files={
            'chrome.manifest':b'manifest chrome/ru.manifest\n',
            'chrome/ru.manifest':b'locale global ru ru/locale/ru/global/\n',
            'localization/ru/coverage.json':json.dumps({'fixture.ftl':{'missing':[],'total':3}}).encode(),
            'localization/ru/toolkit/fixture.ftl':'fixture = Русский\n'.encode(),
        }
        config=json.loads((native.PROJECT/'native-l10n.json').read_text())
        upstream=json.loads((native.PROJECT/'upstream.json').read_text())
        self.meta={'status':'passed','locale':'ru','translationRevision':config['revision'],'geckoRevision':upstream['revision']}
        self.write_stage()
        self.app=self.root/'Forge.app';self.resources=self.app/'Contents/Resources'
        (self.resources/'res').mkdir(parents=True)
        (self.resources/'res/multilocale.txt').write_text('en-US\n')
        (self.resources/'default.locale').write_text('en-US\n')
        (self.resources/'chrome.manifest').write_text('manifest components/security.manifest\nmanifest chrome/en-US.manifest\n')

    def write_stage(self):
        for name,data in self.files.items():
            path=self.stage/'staged'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        self.meta['files']={name:hashlib.sha256(data).hexdigest() for name,data in self.files.items()}
        (self.stage/'provenance.json').write_text(json.dumps(self.meta))

    def test_install_preserves_existing_manifests_fallback_and_unlocked_preferences(self):
        result=native.install(self.stage,self.app)
        self.assertEqual(result['coverage']['missingEntries'],0)
        manifest=(self.resources/'chrome.manifest').read_text()
        self.assertIn('manifest components/security.manifest',manifest)
        self.assertIn('manifest chrome/en-US.manifest',manifest)
        self.assertIn('manifest chrome/ru.manifest',manifest)
        self.assertEqual((self.resources/'res/multilocale.txt').read_text(),'en-US,ru\n')
        self.assertEqual((self.resources/'default.locale').read_text(),'en-US\n')
        prefs=(self.resources/'defaults/pref/forge-native-locale.js').read_text()
        self.assertIn('pref("intl.locale.requested", "ru,en-US")',prefs)
        self.assertIn('pref("forge.locale.followApp", true)',prefs)
        for prohibited in ['lockPref','xpinstall','langpacks.signatures','security.','safebrowsing']:
            self.assertNotIn(prohibited,prefs)

    def test_modified_resources_and_wrong_revisions_are_rejected(self):
        (self.stage/'staged/localization/ru/toolkit/fixture.ftl').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'resource changed'): native.validate_stage(self.stage)
        self.write_stage();self.meta['translationRevision']='0'*40
        (self.stage/'provenance.json').write_text(json.dumps(self.meta))
        with self.assertRaisesRegex(ValueError,'pinned inputs'): native.validate_stage(self.stage)

    def test_script_and_unknown_extra_files_are_rejected(self):
        self.files['localization/ru/evil.js']=b'execute()';self.write_stage()
        with self.assertRaisesRegex(ValueError,'locale-only'): native.validate_stage(self.stage)
        del self.files['localization/ru/evil.js'];(self.stage/'staged/localization/ru/evil.js').unlink();self.write_stage()
        (self.stage/'staged/unexpected').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError,'Unexpected'): native.validate_stage(self.stage)

    def test_symlinked_locale_resources_are_rejected(self):
        (self.stage/'staged/localization/ru/link.ftl').symlink_to(self.stage/'staged/localization/ru/toolkit/fixture.ftl')
        with self.assertRaisesRegex(ValueError,'symlinked'): native.validate_stage(self.stage)

    def test_new_non_locale_registration_and_unsafe_paths_are_rejected(self):
        for line in ['component evil ../evil.js','resource forged ../elsewhere/',
                     'locale browser ru ../../outside/','locale browser ru https://example.com/',
                     'manifest components/evil.manifest']:
            with self.subTest(line=line),self.assertRaises(ValueError): native.merge_manifest('',line)

    def test_existing_native_registrations_are_preserved_without_duplication(self):
        current='content browser browser/content/browser/ contentaccessible=yes\n'
        self.assertEqual(native.merge_manifest(current,current),current)

    def test_conflicting_locale_data_stops_before_any_writes(self):
        target=self.resources/'localization/ru/toolkit/fixture.ftl'
        target.parent.mkdir(parents=True);target.write_text('existing local work')
        before=(self.resources/'chrome.manifest').read_bytes()
        with self.assertRaisesRegex(ValueError,'overwrite'): native.install(self.stage,self.app)
        self.assertEqual((self.resources/'chrome.manifest').read_bytes(),before)
        self.assertEqual(target.read_text(),'existing local work')

    def test_coverage_counts_entries_and_explicit_fallbacks(self):
        self.assertEqual(native.coverage_summary({'a':{'missing':[],'total':3},'b':{'missing':['one','two'],'total':5}}),
                         {'resources':2,'entries':8,'missingEntries':2,'resourcesWithFallback':1})

    def test_russian_dictionary_uses_standard_registration_without_altering_builtin_addons(self):
        self.files.update({'dictionaries/ru.aff':b'SET UTF-8\n','dictionaries/ru.dic':'1\nокно\n'.encode(),
                           'dictionaries/ru-license.txt':b'upstream dictionary license'})
        self.write_stage()
        target=self.resources/'browser/chrome/browser/content/browser/built_in_addons.json'
        target.parent.mkdir(parents=True)
        original={'builtins':[{'addon_id':'existing@mozilla.org','res_url':'resource://existing/'}],
                  'dictionaries':{'en-US':'dictionaries/en-US.dic'},'other':'preserved'}
        target.write_text(json.dumps(original))
        native.install(self.stage,self.app)
        result=json.loads(target.read_text())
        self.assertEqual(result['builtins'],original['builtins'])
        self.assertEqual(result['other'],'preserved')
        self.assertEqual(result['dictionaries'],{'en-US':'dictionaries/en-US.dic','ru':'dictionaries/ru.dic'})
        self.assertEqual((self.resources/'dictionaries/ru-license.txt').read_bytes(),b'upstream dictionary license')

    def test_fetch_uses_pinned_sparse_snapshot_without_security_or_reset_flags(self):
        target=self.root/'new-translations'
        with patch('native_locale.subprocess.run') as run:
            native.fetch_translations(target)
        commands=[call.args[0] for call in run.call_args_list]
        config=json.loads((native.PROJECT/'native-l10n.json').read_text())
        self.assertTrue(any('fetch' in c and config['revision'] in c and '--filter=blob:none' in c for c in commands))
        self.assertTrue(any('sparse-checkout' in c and c[-1]=='ru' for c in commands))
        for command in commands:
            self.assertNotIn('reset',command);self.assertNotIn('--force',command)
            self.assertNotIn('http.sslVerify=false',command)

    def test_fetch_refuses_an_existing_directory_without_touching_it(self):
        marker=self.root/'user-work';marker.write_text('preserve')
        with patch('native_locale.subprocess.run') as run,self.assertRaises(FileExistsError):
            native.fetch_translations(self.root)
        run.assert_not_called();self.assertEqual(marker.read_text(),'preserve')
