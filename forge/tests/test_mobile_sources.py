from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

MOBILE=Path(__file__).resolve().parents[1]/'mobile'


class MobileResourceTests(unittest.TestCase):
    def test_android_picker_does_not_resolve_provider_paths_or_request_broad_grants(self):
        source=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserUploads.java').read_text()
        self.assertIn('Intent.ACTION_OPEN_DOCUMENT',source)
        self.assertIn('Intent.CATEGORY_OPENABLE',source)
        self.assertIn('Intent.FLAG_GRANT_READ_URI_PERMISSION',source)
        self.assertIn('new String[]{OpenableColumns.DISPLAY_NAME}',source)
        self.assertIn('openAssetFileDescriptor(uri, "r")',source)
        self.assertIn('Uri.fromFile(copy.file)',source)
        self.assertIn('host.current(request.session, request.document, request.version)',source)
        self.assertIn('pending.session == session',source)
        self.assertIn('requestCode != pickerCode',source)
        self.assertNotIn('takePersistableUriPermission',source)
        self.assertNotIn('FLAG_GRANT_WRITE_URI_PERMISSION',source)
        self.assertNotIn('FLAG_GRANT_PERSISTABLE_URI_PERMISSION',source)
        self.assertNotIn('ACTION_OPEN_DOCUMENT_TREE',source)
        self.assertNotIn('ACTION_IMAGE_CAPTURE',source)
        self.assertNotIn('"_data"',source)
        manifest=(MOBILE/'android/app/src/main/AndroidManifest.xml').read_text()
        self.assertNotIn('UploadFixtureProvider',manifest)

    def test_upload_staging_is_stream_bounded_private_and_independent_of_provider_paths(self):
        source=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserUploadStaging.java').read_text()
        self.assertIn('MAXIMUM_BYTES = 32L * 1024 * 1024',source)
        self.assertIn('received + count > MAXIMUM_BYTES',source)
        self.assertIn('try (InputStream input = selected)',source)
        self.assertIn('ownerOnly(partial, false)',source)
        self.assertIn('ownerOnly(directory, true)',source)
        self.assertIn('Files.deleteIfExists',source)
        self.assertIn('error.addSuppressed(cleanup)',source)
        self.assertNotIn('getContentResolver',source)
        self.assertNotIn('getColumnIndex',source)
        self.assertNotIn('takePersistableUriPermission',source)

    def test_android_os_link_entry_is_https_only_confirmed_and_not_restored_from_state(self):
        manifest=ET.parse(MOBILE/'android/app/src/main/AndroidManifest.xml').getroot()
        ns='{http://schemas.android.com/apk/res/android}'
        activity=manifest.find('application/activity')
        self.assertEqual(activity.get(ns+'launchMode'),'singleTop')
        view_filters=[f for f in activity.findall('intent-filter') if any(a.get(ns+'name')=='android.intent.action.VIEW' for a in f.findall('action'))]
        self.assertEqual(len(view_filters),1)
        self.assertEqual([d.get(ns+'scheme') for d in view_filters[0].findall('data')],['https'])
        source=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserActivity.java').read_text()
        self.assertIn('if (savedInstanceState == null) receiveExternalIntent(incoming)',source)
        self.assertIn('incoming.cloneFilter()',source)
        for cleanup in ('identity.replaceExtras((Bundle)null)', 'identity.setClipData(null)',
                        'identity.setSelector(null)', 'identity.setFlags(0)'):
            self.assertIn(cleanup,source)
        self.assertIn('BrowserExternalLinks.fromViewIntent',source)
        self.assertIn('if (externalLinkDialog != null) externalLinkDialog.dismiss()',source)
        self.assertIn('linkActionVersion != version || state.privateBrowsing != privateMode',source)
        self.assertNotIn('getParcelableExtra',source)
        self.assertNotIn('CFBundleURLTypes',(MOBILE/'ios/project.yml').read_text())

    def test_new_tab_links_require_native_confirmation_and_never_replay_forms(self):
        ios=(MOBILE/'ios/Sources/BrowserController.swift').read_text(encoding='utf-8')
        android=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserActivity.java').read_text(encoding='utf-8')
        self.assertIn('action.navigationType == .linkActivated && action.sourceFrame.isMainFrame',ios)
        self.assertIn('action.request.httpMethod == "GET"',ios)
        self.assertIn('makeNewTabConfirmation(url, from: source)',ios)
        self.assertIn('self.permissionVersion == version',ios)
        self.assertIn('pages[session.selectedID] === source',ios)
        self.assertIn('if (request.target == TARGET_WINDOW_NEW) return GeckoResult.fromValue(AllowOrDeny.DENY)',android)
        self.assertIn('onContextMenu',android)
        self.assertIn('BrowserLinkActions.shareURL(element.linkUri)',android)
        self.assertIn('linkActionVersion == actionVersion',android)
        self.assertIn('if (!addTab()) return false',android)

    def test_library_integration_records_regular_successes_and_keeps_clear_scopes_distinct(self):
        ios=(MOBILE/'ios/Sources/BrowserController.swift').read_text(encoding='utf-8')
        android=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserActivity.java').read_text(encoding='utf-8')
        self.assertIn('regularSession.tabs.contains(where: { $0.id == id })',ios)
        self.assertIn('libraryStore.recordVisit',ios)
        self.assertIn('!page.externalResponse',android)
        self.assertIn('!page.privatePage',android)
        self.assertIn('libraryStore.recordVisit',android)
        for language in ('en','ru'):
            catalog=(MOBILE/f'ios/Sources/Resources/{language}.lproj/Localizable.strings').read_text(encoding='utf-8')
            for key in ('Bookmarks','History','Clear history','Clear history warning','Add bookmark'):
                self.assertIn('"'+key+'" =',catalog)
        self.assertIn('FLAG_SECURE',(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserLibraryDialog.java').read_text())
        self.assertIn('forge-library-privacy-cover',(MOBILE/'ios/Sources/BrowserLibraryController.swift').read_text())

    def test_library_store_is_separate_bounded_atomic_and_rejects_private_writes(self):
        ios=(MOBILE/'ios/Sources/BrowserLibrary.swift').read_text(encoding='utf-8')
        android=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserLibraryStore.java').read_text(encoding='utf-8')
        model=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserLibrary.java').read_text(encoding='utf-8')
        for source in (ios,android):
            self.assertIn('library-v1.json',source)
            self.assertNotIn('session-v1.json',source)
        self.assertIn('maximumHistory = 500',ios)
        self.assertIn('maximumBookmarks = 200',ios)
        self.assertIn('MAXIMUM_HISTORY = 500',model)
        self.assertIn('MAXIMUM_BOOKMARKS = 200',model)
        self.assertIn('guard !isPrivate else { return false }',ios)
        self.assertIn('if (privateMode) return false;',android)
        self.assertIn('AtomicFile',android)
        self.assertIn('file.failWrite(output)',android)
        self.assertIn('.atomic, .completeFileProtectionUntilFirstUserAuthentication',ios)
        self.assertIn('isExcludedFromBackup = true',ios)

    def test_share_and_find_use_native_apis_without_sending_or_persisting_queries(self):
        ios=(MOBILE/'ios/Sources/BrowserController.swift').read_text(encoding='utf-8')
        android=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserActivity.java').read_text(encoding='utf-8')
        self.assertIn('UIActivityViewController(activityItems:',ios)
        self.assertIn('makePrivateShareConfirmation',ios)
        self.assertIn('presentFindNavigator',ios)
        self.assertIn('isFindInteractionEnabled = true',ios)
        self.assertIn('Intent.createChooser',android)
        self.assertIn('Intent.ACTION_SEND',android)
        self.assertIn('FINDER_DISPLAY_HIGHLIGHT_ALL',android)
        self.assertIn('version != findVersion',android)
        self.assertIn('findQuery.setText("")',android)
        self.assertNotIn('findQuery', (MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserSessionStore.java').read_text())

    def test_navigation_failure_messages_are_fixed_and_do_not_bypass_security(self):
        ios=(MOBILE/'ios/Sources/BrowserNavigationError.swift').read_text(encoding='utf-8')
        self.assertIn('NSURLErrorCancelled',ios)
        self.assertIn('NSURLErrorTimedOut',ios)
        self.assertIn('NSURLErrorServerCertificateUntrusted',ios)
        for forbidden in ('error.localizedDescription', 'error.userInfo', 'URLCredential(', 'URLSession('):
            self.assertNotIn(forbidden,ios)
        android=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserNavigationState.java').read_text(encoding='utf-8')
        self.assertIn('ERROR_CATEGORY_SAFEBROWSING',android)
        self.assertIn('ERROR_CATEGORY_SECURITY',android)
        self.assertIn('Phase.STOPPED',android)

    def test_tab_overviews_are_native_text_only_and_keep_private_protection(self):
        ios=(MOBILE/'ios/Sources/BrowserTabsController.swift').read_text(encoding='utf-8')
        android=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserTabsDialog.java').read_text(encoding='utf-8')
        self.assertIn('UISearchBar',ios)
        self.assertIn('UITableViewController',ios)
        self.assertIn('forge-tabs-privacy-cover',ios)
        self.assertIn('willResignActiveNotification',ios)
        self.assertIn('FLAG_SECURE',android)
        self.assertIn('ListView',android)
        self.assertIn('forge-tabs-search',android)
        for forbidden in ('WKWebView(', 'URLSession', 'takeSnapshot', 'fetch(', 'loadUri(', 'Bitmap', 'HttpURLConnection'):
            self.assertNotIn(forbidden,ios+android)
        ios_browser=(MOBILE/'ios/Sources/BrowserController.swift').read_text(encoding='utf-8')
        self.assertIn('closeTab($0, loadSavedPage: false)',ios_browser)
        self.assertIn('presentedViewController == nil',ios_browser)
        android_browser=(MOBILE/'android/app/src/main/java/org/forgebrowser/mobile/BrowserActivity.java').read_text(encoding='utf-8')
        self.assertIn('closeTab(id, false)',android_browser)

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
        source='\n'.join(path.read_text(encoding='utf-8') for path in root.glob('*.swift'))
        for key in re.findall(r'(?:text|button|showStatus)\("([^"]+)"',source):
            self.assertIn(key,catalogs[0])

    def test_mobile_manifests_keep_cleartext_disabled_and_scope_device_permissions(self):
        manifest=ET.parse(MOBILE/'android/app/src/main/AndroidManifest.xml').getroot()
        ns='{http://schemas.android.com/apk/res/android}'
        permissions={p.attrib[ns+'name'] for p in manifest.findall('uses-permission')}
        self.assertEqual(permissions,{'android.permission.INTERNET', 'android.permission.CAMERA', 'android.permission.RECORD_AUDIO'})
        features={p.attrib[ns+'name']:p.attrib[ns+'required'] for p in manifest.findall('uses-feature')}
        self.assertEqual(features,{'android.hardware.camera':'false', 'android.hardware.camera.autofocus':'false',
                                  'android.hardware.microphone':'false'})
        app=manifest.find('application')
        self.assertEqual(app.attrib[ns+'usesCleartextTraffic'],'false')
        self.assertEqual(app.attrib[ns+'allowBackup'],'false')
        self.assertNotIn('NSAllowsArbitraryLoads',(MOBILE/'ios/project.yml').read_text(encoding='utf-8'))

    def test_ios_media_usage_descriptions_are_localized_without_enabling_location(self):
        project=(MOBILE/'ios/project.yml').read_text(encoding='utf-8')
        for language,name in (('en','Forge Prototype'),('ru','Forge Прототип')):
            content=(MOBILE/f'ios/Sources/Resources/{language}.lproj/InfoPlist.strings').read_text(encoding='utf-8')
            self.assertIn('"CFBundleDisplayName" = "'+name+'";',content)
        for key in ('NSCameraUsageDescription','NSMicrophoneUsageDescription'):
            self.assertIn('INFOPLIST_KEY_'+key+':',project)
            for language in ('en','ru'):
                content=(MOBILE/f'ios/Sources/Resources/{language}.lproj/InfoPlist.strings').read_text(encoding='utf-8')
                self.assertRegex(content,r'"'+key+r'"\s*=\s*"[^"\n]+";')
        self.assertNotIn('NSLocationWhenInUseUsageDescription',project)

    def test_device_media_fixture_has_no_upload_recording_or_hidden_auto_stop(self):
        source=(MOBILE/'fixtures/media-permissions.html').read_text(encoding='utf-8')
        script=re.search(r'<script>(.*?)</script>',source,re.DOTALL).group(1)
        self.assertIn("connect-src 'none'",source)
        self.assertIn('getUserMedia',script)
        for forbidden in ('fetch(', 'XMLHttpRequest', 'sendBeacon', 'WebSocket', 'RTCPeerConnection', 'MediaRecorder',
                          'visibilitychange', 'pagehide', 'beforeunload'):
            self.assertNotIn(forbidden,script)

    def test_android_excludes_all_storage_domains_from_backup_and_transfer(self):
        root=MOBILE/'android/app/src/main'
        ns='{http://schemas.android.com/apk/res/android}'
        app=ET.parse(root/'AndroidManifest.xml').getroot().find('application')
        self.assertEqual(app.attrib[ns+'dataExtractionRules'],'@xml/data_extraction_rules')
        self.assertEqual(app.attrib[ns+'fullBackupContent'],'@xml/full_backup_rules')
        rules=ET.parse(root/'res/xml/data_extraction_rules.xml').getroot()
        self.assertEqual(rules.tag,'data-extraction-rules')
        self.assertEqual({section.tag for section in rules},{'cloud-backup','device-transfer'})
        domains={'root','file','database','sharedpref','external','device_root',
                 'device_file','device_database','device_sharedpref'}
        legacy=ET.parse(root/'res/xml/full_backup_rules.xml').getroot()
        self.assertEqual(legacy.tag,'full-backup-content')
        for section in [*rules,legacy]:
            self.assertEqual(len(section),len(domains))
            self.assertEqual({item.attrib['domain'] for item in section},domains)
            for item in section:
                self.assertEqual(item.tag,'exclude')
                self.assertEqual(item.attrib['path'],'.')

    def test_downloads_use_engine_responses_and_export_without_auto_open(self):
        android=MOBILE/'android/app/src/main/java/org/forgebrowser/mobile'
        activity=(android/'BrowserActivity.java').read_text(encoding='utf-8')
        downloads=(android/'BrowserDownloads.java').read_text(encoding='utf-8')
        self.assertIn('onExternalResponse',activity)
        self.assertIn('Intent.ACTION_CREATE_DOCUMENT',activity)
        self.assertNotIn('Intent.ACTION_VIEW',downloads)
        # Incoming VIEW validation is now supported; downloads still must not
        # construct an outgoing VIEW intent or auto-open an exported file.
        self.assertEqual(activity.count('Intent.ACTION_VIEW'),1)
        self.assertIn('!Intent.ACTION_VIEW.equals(intent.getAction())',activity)
        self.assertNotRegex(activity,r'new\s+Intent\s*\(\s*Intent\.ACTION_VIEW')
        self.assertNotRegex(activity,r'\.setAction\s*\(\s*Intent\.ACTION_VIEW')
        self.assertNotIn('skipConfirmation',downloads)
        self.assertNotIn('requestExternalApp',downloads)
        self.assertIn('!value.isSecure',downloads)
        ios=(MOBILE/'ios/Sources/BrowserDownloads.swift').read_text(encoding='utf-8')
        self.assertIn('WKDownloadDelegate',ios)
        self.assertIn('UIDocumentPickerViewController(forExporting:',ios)
        self.assertNotIn('URLSession',ios)
        self.assertNotIn('didReceiveAuthenticationChallenge',ios)
        self.assertNotIn('UIApplication.shared.open',ios)
        self.assertNotIn('proxyConfigurations',ios)

    def test_ios_launch_screen_uses_native_dark_background(self):
        project=(MOBILE/'ios/project.yml').read_text(encoding='utf-8')
        self.assertIn('INFOPLIST_KEY_UILaunchStoryboardName: LaunchScreen',project)
        self.assertIn('INFOPLIST_KEY_UIUserInterfaceStyle: Dark',project)
        storyboard=ET.parse(MOBILE/'ios/Sources/LaunchScreen.storyboard').getroot()
        self.assertEqual(storyboard.attrib['launchScreen'],'YES')
        colors=storyboard.findall('.//color[@key="backgroundColor"]')
        self.assertEqual(len(colors),1)
        for channel in ('red','green','blue'):
            self.assertLess(float(colors[0].attrib[channel]),0.05)
