import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == 'darwin', 'macOS relaunch adapter')
class RelauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix='forge-relauncher-test-')
        cls.root = Path(cls.workspace.name)
        directory = cls.root / 'Forge.app/Contents/MacOS/updater.app/Contents/MacOS'
        directory.mkdir(parents=True)
        cls.helper = directory / 'org.mozilla.updater'
        source = Path(__file__).parents[1] / 'scripts/macos_relauncher.mm'
        subprocess.run(['xcrun', 'clang++', '-Wall', '-Wextra', '-Werror', '-fobjc-arc', '-framework', 'AppKit',
                        str(source), '-o', str(cls.helper)], check=True)
        original = directory / 'org.mozilla.updater.real'
        original.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$FORGE_UPDATER_TEST"\nexit 19\n')
        original.chmod(0o700)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def forwarded(self, arguments):
        output = self.root / 'forwarded.args'
        result = subprocess.run([str(self.helper), *arguments], env=dict(os.environ, FORGE_UPDATER_TEST=str(output)))
        self.assertEqual(result.returncode, 19)
        self.assertEqual(output.read_text().splitlines(), arguments)

    def test_update_operations_and_exit_code_are_forwarded_unchanged(self):
        self.forwarded(['/test/staging', '/test/install', '/test/apply', '-1', 'argument with spaces'])

    def test_other_application_targets_stay_with_upstream_updater(self):
        self.forwarded(['--openAppBundle', '--wait-pid', str(os.getpid()), '/test/Other.app', '--headless'])

    def test_invalid_wait_pid_is_not_reinterpreted(self):
        self.forwarded(['--openAppBundle', '--wait-pid', 'not-a-pid', '/test/Other.app'])

    def test_ordinary_restart_adapter_does_not_modify_quarantine(self):
        source = (Path(__file__).parents[1] / 'scripts/macos_relauncher.mm').read_text()
        for forbidden in ('"/usr/bin/xattr"', 'removexattr(', 'setxattr(', 'system(', 'popen('):
            self.assertNotIn(forbidden, source)
