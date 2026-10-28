import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from socket_audit import parse_sockets


class SocketAuditTests(unittest.TestCase):
    def test_only_protocol_and_numeric_endpoints_are_retained(self):
        sample='p123\ncFirefox\nf18\nPTCP\nn127.0.0.1:123->127.0.0.1:80\nf19\nPUDP\nn[::1]:5353\n'
        self.assertEqual(parse_sockets(sample),[('TCP','127.0.0.1:123->127.0.0.1:80'),('UDP','[::1]:5353')])

    def test_protocol_does_not_leak_across_files(self):
        self.assertEqual(parse_sockets('f1\nPTCP\nn*:80\nf2\nnignored\n'),[('TCP','*:80')])
