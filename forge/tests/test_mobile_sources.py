from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

MOBILE=Path(__file__).resolve().parents[1]/'mobile'


class MobileResourceTests(unittest.TestCase):
    def test_ios_distribution_metadata_supports_ipad_and_only_platform_crypto(self):
        source=(MOBILE/'ios/project.yml').read_text(encoding='utf-8')
        orientations=re.search(r"INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad: '([^']+)'",source)
        self.assertIsNotNone(orientations)
        self.assertEqual(set(orientations.group(1).split()), {
            'UIInterfaceOrientationPortrait', 'UIInterfaceOrientationPortraitUpsideDown',
            'UIInterfaceOrientationLandscapeLeft', 'UIInterfaceOrientationLandscapeRight'})
        self.assertIn('INFOPLIST_KEY_ITSAppUsesNonExemptEncryption: NO',source)
        self.assertNotIn('DEVELOPMENT_TEAM:',source)
        self.assertNotIn('PROVISIONING_PROFILE_SPECIFIER:',source)

    def test_android_russian_and_english_strings_have_matching_unique_keys(self):
        root=MOBILE/'android/app/src/main/res'
        catalogs=[]
        for folder in ('values','values-ru'):
            keys=[item.attrib['name'] for item in ET.parse(root/folder/'strings.xml').getroot()]
            self.assertEqual(len(keys),len(set(keys)))
            self.assertGreater(len(keys),5)
            catalogs.append(set(keys))
        self.assertEqual(*catalogs)

    def test_ios_russian_and_english_strings_cover_all_native_ui_keys(self):
        root=MOBILE/'ios/Sources'
        catalogs=[]
        for language in ('en','ru'):
            content=(root/f'Resources/{language}.lproj/Localizable.strings').read_text(encoding='utf-8')
            keys=re.findall(r'^"([^"]+)"\s*=\s*"[^"\n]*";',content,re.MULTILINE)
            self.assertEqual(len(keys),len(set(keys)))
            self.assertGreater(len(keys),5)
            catalogs.append(set(keys))
        self.assertEqual(*catalogs)
        source=(root/'BrowserController.swift').read_text(encoding='utf-8')
        for key in re.findall(r'(?:text|button)\("([^"]+)"',source):
            self.assertIn(key,catalogs[0])

    def test_mobile_manifests_do_not_enable_cleartext_or_sensitive_android_permissions(self):
        manifest=ET.parse(MOBILE/'android/app/src/main/AndroidManifest.xml').getroot()
        ns='{http://schemas.android.com/apk/res/android}'
        permissions={p.attrib[ns+'name'] for p in manifest.findall('uses-permission')}
        self.assertEqual(permissions,{'android.permission.INTERNET'})
        app=manifest.find('application')
        self.assertEqual(app.attrib[ns+'usesCleartextTraffic'],'false')
        self.assertEqual(app.attrib[ns+'allowBackup'],'false')
        self.assertNotIn('NSAllowsArbitraryLoads',(MOBILE/'ios/project.yml').read_text(encoding='utf-8'))
