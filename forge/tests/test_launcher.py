import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == "darwin", "macOS launcher")
class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="forge-launcher-test-")
        cls.directory = Path(cls.workspace.name)
        cls.launcher = cls.directory / "forge"
        source = Path(__file__).parents[1] / "scripts/macos_launcher.c"
        subprocess.run(["xcrun", "clang", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(cls.launcher)], check=True)
        runtime = cls.directory / "firefox"
        runtime.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$FORGE_LAUNCH_TEST"\nprintf "%s\\n" "$XRE_PROFILE_PATH" > "$FORGE_LAUNCH_TEST.profile"\n')
        runtime.chmod(0o700)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def run_launcher(self, name, arguments, restart_profile=None, trace=None):
        home = self.directory / name
        capture = self.directory / f"{name}.args"
        env = dict(os.environ, HOME=str(home), FORGE_LAUNCH_TEST=str(capture))
        env.pop("XRE_PROFILE_PATH", None)
        env.pop("XRE_PROFILE_LOCAL_PATH", None)
        env.pop("FORGE_LAUNCH_TRACE", None)
        if trace is not None:
            env['FORGE_LAUNCH_TRACE'] = str(trace)
        if restart_profile:
            env["XRE_PROFILE_PATH"] = restart_profile
        subprocess.run([str(self.launcher), *arguments], env=env, check=True)
        return home, capture.read_text().splitlines()

    def test_default_launch_uses_dedicated_profile(self):
        home, arguments = self.run_launcher("default-home", ["--headless"])
        profile = home / "Library/Application Support/Forge Development/profile"
        self.assertEqual(arguments, ["--no-remote", "--purgecaches", "--profile", str(profile), "--headless"])
        self.assertTrue(profile.is_dir())
        self.assertEqual(profile.stat().st_mode & 0o777, 0o700)

    def test_explicit_test_profile_is_forwarded_without_creating_default(self):
        home, arguments = self.run_launcher("explicit-home", ["--profile", "/test/disposable-profile", "--headless"])
        self.assertEqual(arguments.count("--profile"), 1)
        self.assertIn("/test/disposable-profile", arguments)
        self.assertFalse(home.exists())

    def test_restart_profile_from_gecko_environment_is_not_replaced(self):
        home, arguments = self.run_launcher("restart-home", ["--headless"], restart_profile="/test/original-restart-profile")
        self.assertNotIn("--profile", arguments)
        self.assertFalse(home.exists())
        self.assertEqual((self.directory / "restart-home.args.profile").read_text().strip(), "/test/original-restart-profile")

    def test_trace_is_opt_in_private_and_excludes_argument_values(self):
        trace = self.directory / 'launch-trace.jsonl'
        self.run_launcher('trace-home', ['--profile', '/test/profile', 'PRIVATE-ARGUMENT'], trace=trace)
        record = json.loads(trace.read_text())
        self.assertEqual(record['stage'], 'exec')
        self.assertTrue(record['explicitProfile'])
        self.assertNotIn('PRIVATE-ARGUMENT', trace.read_text())
        self.assertNotIn('/test/profile', trace.read_text())
        self.assertEqual(trace.stat().st_mode & 0o777, 0o600)

    def test_trace_does_not_follow_symlinks_or_append_to_public_files(self):
        target = self.directory / 'trace-unchanged'
        target.write_text('unchanged')
        target.chmod(0o600)
        link = self.directory / 'trace-link'
        link.symlink_to(target)
        self.run_launcher('trace-link-home', ['--profile', '/test/profile'], trace=link)
        self.assertEqual(target.read_text(), 'unchanged')
        target.chmod(0o644)
        self.run_launcher('trace-public-home', ['--profile', '/test/profile'], trace=target)
        self.assertEqual(target.read_text(), 'unchanged')

    def test_trace_rejects_relative_paths_and_parent_traversal(self):
        target = self.directory / 'trace-traversal'
        target.write_text('unchanged')
        target.chmod(0o600)
        subdir = self.directory / 'trace-subdir'
        subdir.mkdir()
        self.run_launcher('trace-relative-home', ['--profile', '/test/profile'], trace='relative-trace.jsonl')
        self.run_launcher('trace-traversal-home', ['--profile', '/test/profile'], trace=str(subdir)+'/../trace-traversal')
        self.assertEqual(target.read_text(), 'unchanged')
