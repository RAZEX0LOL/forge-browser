from pathlib import Path
import json
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from isolated_profile import prepare


class IsolatedProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.binary=self.root/"package with 'quotes'/Forge.app/Contents/MacOS/forge"
        self.binary.parent.mkdir(parents=True);self.binary.write_text('#!/bin/sh\nexit 0\n');self.binary.chmod(0o700)
        self.output=self.root/"manual 'profile'"

    def test_prepares_private_empty_profile_without_launch_or_preferences(self):
        with patch('isolated_profile.subprocess.run') as run:
            launcher=prepare(self.binary,self.output)
        run.assert_called_once_with(['codesign','--verify','--deep','--strict',str(self.binary.resolve().parents[2])],check=True)
        self.assertEqual(list((self.output/'profile').iterdir()),[])
        for name in ('profile','app-data','local-app-data','Launch.command'):
            self.assertEqual(stat.S_IMODE((self.output/name).stat().st_mode),0o700)
        lines=launcher.read_text().splitlines()
        self.assertEqual(shlex.split(lines[-1]),['exec',str(self.binary.resolve()),'--no-remote','--profile',str(self.output.resolve()/'profile')])
        for name in ('MOZ_APP_DATA','MOZ_LOCAL_APP_DATA'):
            self.assertTrue(any(line.startswith(f'export {name}=') for line in lines))
        self.assertNotIn('--remote-allow-system-access',launcher.read_text())
        self.assertFalse(json.loads((self.output/'isolation.json').read_text())['launched'])

    def test_existing_directory_is_not_touched(self):
        self.output.mkdir();marker=self.output/'prefs.js';marker.write_text('user work')
        with patch('isolated_profile.subprocess.run') as run,self.assertRaises(FileExistsError):
            prepare(self.binary,self.output)
        run.assert_not_called();self.assertEqual(marker.read_text(),'user work')

    def test_dangling_output_symlink_is_not_followed(self):
        target=self.root/'not-created';self.output.symlink_to(target)
        with self.assertRaises(FileExistsError): prepare(self.binary,self.output)
        self.assertFalse(target.exists())

    def test_profile_inside_package_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'signed app'):
            prepare(self.binary,self.binary.parents[2]/'manual-profile')

    def test_signature_failure_creates_nothing(self):
        with patch('isolated_profile.subprocess.run',side_effect=subprocess.CalledProcessError(1,'codesign')):
            with self.assertRaises(subprocess.CalledProcessError): prepare(self.binary,self.output)
        self.assertFalse(self.output.exists())
