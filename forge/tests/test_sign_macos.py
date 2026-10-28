from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sign_macos import entitlements_for, is_macho


class MacSigningTests(unittest.TestCase):
    def test_entitlements_are_scoped_and_exclude_restricted_mozilla_and_debug_rights(self):
        app = Path('/fixture/Forge.app')
        main = entitlements_for(app, app)
        self.assertEqual(main, entitlements_for(app / 'Contents/MacOS/firefox', app))
        self.assertTrue(main['com.apple.security.cs.allow-jit'])
        for key in main:
            self.assertNotIn('get-task-allow', key)
            self.assertNotIn('application-identifier', key)
            self.assertNotIn('application-groups', key)
            self.assertNotIn('public-key-credential', key)
        self.assertEqual(entitlements_for(app / 'Contents/MacOS/gpu-helper.app', app), {})
        self.assertEqual(entitlements_for(app / 'Contents/MacOS/plugin-container.app', app),
                         {'com.apple.security.cs.allow-jit': True})
        self.assertEqual(entitlements_for(app / 'Contents/MacOS/XUL', app), {})

    def test_macho_detection_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / 'binary'
            binary.write_bytes(b'\xcf\xfa\xed\xfe' + b'\0' * 16)
            link = Path(temporary) / 'link'
            link.symlink_to(binary)
            self.assertTrue(is_macho(binary))
            self.assertFalse(is_macho(link))
            self.assertFalse(is_macho(Path(temporary)))
            binary.write_bytes(b'not executable')
            self.assertFalse(is_macho(binary))
