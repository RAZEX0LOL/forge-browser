from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from publish_artifacts import resource_name, validate_native


class ArtifactPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.archive=self.root/'Forge.zip';self.archive.write_bytes(b'fixture archive')
        self.meta={'sourceCommit':'a'*40,'target':'win32-arm64','archive':self.archive.name,
                   'sha256':hashlib.sha256(self.archive.read_bytes()).hexdigest()}
        self.report={'status':'passed','passed':[f'check {i}' for i in range(260)]}
        self.write()

    def write(self): (self.root/'SOURCE.json').write_text(json.dumps(self.meta),encoding='utf-8')

    def test_source_target_checksum_and_actual_runtime_report_must_match(self):
        archive,_=validate_native(self.root,self.report,'a'*40,'win32-arm64')
        self.assertEqual(archive,self.archive)
        for head,target in [('b'*40,'win32-arm64'),('a'*40,'win32-amd64')]:
            with self.assertRaises(ValueError):validate_native(self.root,self.report,head,target)
        self.archive.write_bytes(b'tampered')
        with self.assertRaises(ValueError):validate_native(self.root,self.report,'a'*40,'win32-arm64')

    def test_failed_empty_and_non_list_runtime_reports_cannot_publish(self):
        for report in [{'status':'failed','passed':self.report['passed']},{'status':'passed','passed':[]},
                       {'status':'passed','passed':'x'*260},{'status':'passed','passed':[None]*260}]:
            with self.assertRaises(ValueError):validate_native(self.root,report,'a'*40,'win32-arm64')

    def test_artifact_paths_and_symlinks_are_rejected(self):
        for name in ('../private','/absolute','C:\\secret','--bad/name','.','..'):
            with self.assertRaises(ValueError):resource_name(name)
        link=self.root/'link.zip';link.symlink_to(self.archive)
        self.meta['archive']=link.name;self.write()
        with self.assertRaises(ValueError):validate_native(self.root,self.report,'a'*40,'win32-arm64')
