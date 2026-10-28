import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("package_macos", Path(__file__).parents[1] / "scripts/package_macos.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageTests(unittest.TestCase):
    def test_packaging_excludes_consumed_startup_markers(self):
        self.assertEqual(package.package_ignore("Contents/Resources/browser", [".purgecaches", "omni.ja", "moz.build"]), {".purgecaches", "moz.build"})

    def test_branding_preserves_security_and_version_metadata(self):
        original = {"CFBundleName": "Nightly", "CFBundleExecutable": "firefox",
                    "CFBundleVersion": "161.0a1", "NSAppTransportSecurity": {"test": True}}
        result = package.forge_metadata(original)
        self.assertEqual(result["CFBundleName"], "Forge")
        self.assertEqual(result["CFBundleExecutable"], "forge")
        self.assertEqual(result["NSAppTransportSecurity"], original["NSAppTransportSecurity"])
        self.assertEqual(result["CFBundleVersion"], original["CFBundleVersion"])
        self.assertEqual(original["CFBundleName"], "Nightly")
