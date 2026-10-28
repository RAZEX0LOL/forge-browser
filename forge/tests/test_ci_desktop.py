from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ci_desktop import verify_architecture


class DesktopArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.binary=Path(self.temp.name)/'runtime'

    def test_elf_x64_and_arm64_are_not_interchangeable(self):
        for machine,number in [('x86_64',62),('aarch64',183)]:
            header=bytearray(64);header[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',header,18,number)
            self.binary.write_bytes(header)
            verify_architecture(self.binary,'linux',machine)
            with self.assertRaisesRegex(ValueError,'mismatch'):
                verify_architecture(self.binary,'linux','aarch64' if machine=='x86_64' else 'x86_64')

    def test_pe_x64_and_arm64_are_not_interchangeable(self):
        for machine,number in [('AMD64',0x8664),('ARM64',0xaa64)]:
            header=bytearray(128);header[:2]=b'MZ';struct.pack_into('<I',header,0x3c,64)
            header[64:68]=b'PE\0\0';struct.pack_into('<H',header,68,number)
            self.binary.write_bytes(header)
            verify_architecture(self.binary,'win32',machine)
            with self.assertRaisesRegex(ValueError,'mismatch'):
                verify_architecture(self.binary,'win32','ARM64' if machine=='AMD64' else 'AMD64')

    def test_invalid_formats_are_rejected(self):
        self.binary.write_bytes(b'not an executable'.ljust(64,b'\0'))
        for system in ('linux','win32'):
            with self.assertRaises(ValueError):verify_architecture(self.binary,system,'x86_64')
