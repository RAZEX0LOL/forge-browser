import base64
import json
import re
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/sign_update_manifest.py'


class UpdateSigningTests(unittest.TestCase):
    def test_published_android_manifest_matches_pinned_key_and_limits(self):
        forge = SCRIPT.parents[1]
        envelope = json.loads((forge / 'site/updates/android-development.json').read_text())
        payload = base64.b64decode(envelope['payload'], validate=True)
        data = json.loads(payload)
        java = (forge / 'mobile/android/app/src/main/java/org/forgebrowser/mobile/UpdatePolicy.java').read_text()
        public = base64.b64decode(re.search(r'PUBLIC_KEY = "([^"]+)"', java).group(1), validate=True)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pem = subprocess.check_output(['openssl', 'pkey', '-pubin', '-inform', 'DER', '-outform', 'PEM'], input=public)
            (root / 'public.pem').write_bytes(pem)
            (root / 'signature.bin').write_bytes(base64.b64decode(envelope['signature'], validate=True))
            verify = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(root / 'public.pem'),
                                     '-signature', str(root / 'signature.bin')], input=payload, capture_output=True)
            self.assertEqual(verify.returncode, 0)
        self.assertEqual(data['channel'], 'android-development')
        self.assertEqual(data['packageName'], 'org.forgebrowser.mobile.development')
        self.assertEqual(data['versionCode'], 2)
        self.assertLessEqual(data['expires'] - data['issued'], 14 * 86400)
        self.assertGreater(data['expires'], data['issued'])
        self.assertEqual(data['certificateSha256'], '4faadf5155d5d72c0b48b19139da9b4c9a2dabc4111374cf3c6acdee3cbf942d')
        self.assertEqual(set(data['artifacts']), {'arm64-v8a'})

    def test_offline_envelope_verifies_exact_payload_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            key = root / 'key.env'
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048',
                            '-out', str(key)], check=True, capture_output=True)
            key.chmod(0o600)
            payload = root / 'payload.json'
            payload.write_text('{"sequence":1,"channel":"test fixture"}')
            output = root / 'envelope.json'
            command = ['python3', str(SCRIPT), '--payload', str(payload), '--private-key', str(key), '--output', str(output)]
            subprocess.run(command, check=True, capture_output=True)
            envelope = json.loads(output.read_text())
            self.assertEqual(set(envelope), {'payload', 'signature'})
            decoded = base64.b64decode(envelope['payload'])
            self.assertEqual(json.loads(decoded), json.loads(payload.read_text()))
            signature = root / 'signature.bin'
            signature.write_bytes(base64.b64decode(envelope['signature']))
            public = root / 'public.pem'
            subprocess.run(['openssl', 'pkey', '-in', str(key), '-pubout', '-out', str(public)], check=True, capture_output=True)
            verify = ['openssl', 'dgst', '-sha256', '-verify', str(public), '-signature', str(signature)]
            self.assertEqual(subprocess.run(verify, input=decoded, capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(verify, input=decoded + b' ', capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            key.chmod(0o644)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_production_updater_does_not_disable_platform_checks(self):
        source = SCRIPT.parents[1] / 'mobile/android/app/src/main/java/org/forgebrowser/mobile'
        runtime = (source / 'BrowserUpdates.java').read_text()
        for required in ('setInstanceFollowRedirects(false)', 'UpdatePolicy.verify(', 'UpdatePolicy.copy(',
                         'getPackageArchiveInfo(', 'canRequestPackageInstalls()', 'Intent.ACTION_VIEW'):
            self.assertIn(required, runtime)
        for forbidden in ('setSSLSocketFactory', 'setHostnameVerifier', 'Runtime.exec', 'ProcessBuilder', 'setDefault('):
            self.assertNotIn(forbidden, runtime)
        activity = (source / 'BrowserActivity.java').read_text()
        self.assertEqual(activity.count('new BrowserUpdates(this)'), 1)
        self.assertIn('if (updates != null) { updates.dispose(); updates = null; }', activity)


if __name__ == '__main__':
    unittest.main()
