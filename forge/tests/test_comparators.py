import sys
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fetch_comparators import normalize_finder_metadata, verify_bundle


class ComparatorMetadataTests(unittest.TestCase):
    def test_only_finderinfo_is_removed_and_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Path(folder)/'Test.app';app.mkdir()
            binary=app/'binary';binary.write_bytes(b'unchanged executable fixture')
            (app/'link').symlink_to(binary)
            with patch('fetch_comparators.subprocess.check_output',return_value='com.apple.FinderInfo\ncom.apple.quarantine\n'), \
                    patch('fetch_comparators.subprocess.run') as run:
                result=normalize_finder_metadata(app)
            self.assertEqual(result,['.','binary'])
            self.assertEqual(run.call_count,2)
            for call in run.call_args_list:
                self.assertEqual(call.args[0][:3],['xattr','-d','com.apple.FinderInfo'])
            self.assertEqual(binary.read_bytes(),b'unchanged executable fixture')

    def test_quarantine_only_is_never_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('fetch_comparators.subprocess.check_output',return_value='com.apple.quarantine\n'), \
                    patch('fetch_comparators.subprocess.run') as run:
                self.assertEqual(normalize_finder_metadata(Path(folder)),[])
                run.assert_not_called()

    def test_bad_signature_stops_before_gatekeeper_or_execution(self):
        with patch('fetch_comparators.normalize_finder_metadata',return_value=[]), \
                patch('fetch_comparators.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','bad signature')) as run:
            with self.assertRaisesRegex(RuntimeError,'signature verification failed'):
                verify_bundle(Path('Private.app'))
            self.assertEqual(run.call_count,1)
            self.assertEqual(run.call_args.args[0][:4],['codesign','--verify','--deep','--strict'])

    def test_gatekeeper_rejection_is_not_bypassed(self):
        responses=[subprocess.CompletedProcess([],0,'',''),
                   subprocess.CompletedProcess([],0,'','valid signature'),
                   subprocess.CompletedProcess([],1,'','rejected')]
        with patch('fetch_comparators.normalize_finder_metadata',return_value=[]), \
                patch('fetch_comparators.subprocess.run',side_effect=responses) as run:
            with self.assertRaisesRegex(RuntimeError,'Gatekeeper assessment failed; not bypassing'):
                verify_bundle(Path('Private.app'))
            self.assertEqual(run.call_count,3)
