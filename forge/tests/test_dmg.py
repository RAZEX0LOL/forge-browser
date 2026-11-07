import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/package_dmg.py'
spec = importlib.util.spec_from_file_location('package_dmg', SCRIPT)
dmg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dmg)


class DMGTests(unittest.TestCase):
    def test_packaged_metadata_removes_firefox_asset_icon_override(self):
        spec = importlib.util.spec_from_file_location('package_macos', SCRIPT.with_name('package_macos.py'))
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        original = {'CFBundleIconName': 'AppIcon', 'CFBundleIconFile': 'firefox.icns', 'CFBundleVersion': '161.0'}
        metadata = package.forge_metadata(original)
        self.assertNotIn('CFBundleIconName', metadata)
        self.assertEqual(metadata['CFBundleIconFile'], 'forge.icns')
        self.assertEqual(metadata['CFBundleVersion'], '161.0')
        self.assertEqual(original['CFBundleIconName'], 'AppIcon')

    def test_icon_requires_forge_bundle_and_real_icns(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Path(folder) / 'Forge.app'
            resources = app / 'Contents/Resources'
            resources.mkdir(parents=True)
            info = app / 'Contents/Info.plist'
            metadata = {'CFBundleIdentifier': 'org.forgebrowser.development',
                        'CFBundleExecutable': 'forge', 'CFBundleIconFile': 'forge.icns'}
            info.write_bytes(plistlib.dumps(metadata))
            icon = resources / 'forge.icns'
            icon.write_bytes(b'icns fixture')
            self.assertEqual(dmg.app_icon(app), icon)
            metadata['CFBundleIconName'] = 'AppIcon'
            info.write_bytes(plistlib.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'Asset-catalog'):
                dmg.app_icon(app)
            metadata.pop('CFBundleIconName')
            for bad in ('../forge.icns', '', '/tmp/forge.icns'):
                metadata['CFBundleIconFile'] = bad
                info.write_bytes(plistlib.dumps(metadata))
                with self.assertRaises(ValueError):
                    dmg.app_icon(app)
            metadata['CFBundleIconFile'] = 'forge.icns'
            info.write_bytes(plistlib.dumps(metadata))
            icon.write_bytes(b'not an icon')
            with self.assertRaises(ValueError):
                dmg.app_icon(app)

    def test_manifest_checks_bytes_modes_and_symlink_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / 'launcher'
            file.write_bytes(b'original')
            file.chmod(0o755)
            (root / 'link').symlink_to('launcher')
            original = dmg.bundle_manifest(root)
            self.assertEqual(original['link'], {'symlink': 'launcher'})
            file.write_bytes(b'changed')
            self.assertNotEqual(dmg.bundle_manifest(root), original)
            file.write_bytes(b'original')
            file.chmod(0o644)
            self.assertNotEqual(dmg.bundle_manifest(root), original)
