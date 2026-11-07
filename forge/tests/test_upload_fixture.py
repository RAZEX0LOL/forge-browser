import importlib.util
from pathlib import Path
import unittest
import tempfile
import threading
from types import SimpleNamespace


SPEC = importlib.util.spec_from_file_location('upload_fixture', Path(__file__).resolve().parents[1] / 'mobile/tests/upload_fixture.py')
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


class UploadFixtureTests(unittest.TestCase):
    def body(self, *, filename=FIXTURE.FILENAME, data=FIXTURE.PAYLOAD, case='regular', extra=b''):
        return (b'--fixture\r\nContent-Disposition: form-data; name="case"\r\n\r\n' + case.encode() + b'\r\n'
            + b'--fixture\r\nContent-Disposition: form-data; name="attachment"; filename="' + filename.encode()
            + b'"\r\nContent-Type: application/octet-stream\r\n\r\n' + data + b'\r\n' + extra + b'--fixture--\r\n')

    def inspect(self, **kwargs):
        return FIXTURE.inspect_multipart('multipart/form-data; boundary=fixture', self.body(**kwargs))

    def test_exact_binary_bytes_and_filename_are_required(self):
        receipt = self.inspect()
        self.assertEqual(receipt['bytes'], len(FIXTURE.PAYLOAD))
        self.assertEqual(receipt['filename'], FIXTURE.FILENAME)
        self.assertEqual(receipt['method'], 'POST')
        self.assertNotIn('body', receipt)

    def test_private_case_is_distinct(self):
        self.assertEqual(self.inspect(case='private')['case'], 'private')

    def test_wrong_or_truncated_bytes_are_rejected(self):
        for data in (b'', FIXTURE.PAYLOAD[:-1], FIXTURE.PAYLOAD + b'other'):
            with self.assertRaises(ValueError):
                self.inspect(data=data)

    def test_changed_filename_and_unknown_case_are_rejected(self):
        for kwargs in ({'filename': '../' + FIXTURE.FILENAME}, {'case': 'unknown'}):
            with self.assertRaises(ValueError):
                self.inspect(**kwargs)

    def test_duplicate_fields_and_nonmultipart_body_are_rejected(self):
        with self.assertRaises(ValueError):
            self.inspect(extra=b'--fixture\r\nContent-Disposition: form-data; name="case"\r\n\r\nregular\r\n')
        with self.assertRaises(ValueError):
            FIXTURE.inspect_multipart('application/octet-stream', b'fixture')

    def test_hard_size_limit_and_header_injection_are_rejected(self):
        with self.assertRaises(ValueError):
            FIXTURE.inspect_multipart('multipart/form-data; boundary=fixture', b'x' * (FIXTURE.MAXIMUM_BODY + 1))
        with self.assertRaises(ValueError):
            FIXTURE.inspect_multipart('multipart/form-data\r\nInjected: header', self.body())

    def test_form_uses_post_multipart_and_validated_case(self):
        self.assertIn(b'method="post"', FIXTURE.form('regular'))
        self.assertIn(b'enctype="multipart/form-data"', FIXTURE.form('private'))
        self.assertIn(b'type="file" required', FIXTURE.form('cancel'))
        with self.assertRaises(ValueError):
            FIXTURE.form('<script>')

    def test_rejected_post_attempt_is_recorded_even_without_an_accepted_receipt(self):
        with tempfile.TemporaryDirectory(prefix='forge-upload-fixture-') as directory:
            receipts = Path(directory) / 'receipts.jsonl'
            handler = FIXTURE.FixtureHandler.__new__(FIXTURE.FixtureHandler)
            handler.path = '/submit'
            handler.headers = {'Content-Length': '0'}
            handler.server = SimpleNamespace(receipts=receipts, receipt_lock=threading.Lock())
            statuses = []
            handler.respond = lambda status, body: statuses.append(status)
            handler.do_POST()
            self.assertEqual(statuses, [400])
            self.assertFalse(receipts.exists())
            self.assertEqual(receipts.with_name('requests.jsonl').read_text(), '{"method": "POST", "route": "/submit"}\n')


if __name__ == '__main__':
    unittest.main()
