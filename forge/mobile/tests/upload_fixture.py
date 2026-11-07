"""Loopback-only HTTPS multipart fixture. Never a production upload service."""
import argparse
from email import policy
from email.parser import BytesParser
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import ssl
import threading
from urllib.parse import parse_qs, urlsplit


FILENAME = 'forge-upload-fixture.txt'
PAYLOAD = b'Forge multipart fixture\x00\r\n\xff\n'
MAXIMUM_BODY = 256 * 1024
CASES = {'regular', 'private', 'cancel'}


def inspect_multipart(content_type, body):
    if len(body) > MAXIMUM_BODY or '\r' in content_type or '\n' in content_type:
        raise ValueError('Invalid fixture body')
    message = BytesParser(policy=policy.default).parsebytes(
        ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii') + body)
    if message.get_content_type() != 'multipart/form-data' or not message.is_multipart() or message.defects:
        raise ValueError('Expected multipart/form-data')
    parts = list(message.iter_parts())
    if len(parts) != 2:
        raise ValueError('Expected exactly two parts')
    fields = {}
    for part in parts:
        name = part.get_param('name', header='content-disposition')
        if part.is_multipart() or part.get_content_disposition() != 'form-data' or name not in ('case', 'attachment') or name in fields or part.defects:
            raise ValueError('Unexpected multipart field')
        fields[name] = part
    case = fields['case'].get_payload(decode=True).decode('ascii')
    attachment = fields['attachment']
    data = attachment.get_payload(decode=True)
    if case not in CASES or attachment.get_filename() != FILENAME or data != PAYLOAD:
        raise ValueError('Selected bytes/name/case do not match fixture')
    return {'case': case, 'filename': attachment.get_filename(), 'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(), 'method': 'POST', 'contentType': 'multipart/form-data'}


def form(case):
    if case not in CASES:
        raise ValueError('Unknown fixture case')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Forge upload fixture</title><style>
      body {{ font: 20px sans-serif; background: white; color: black; padding: 20px; }}
      input, button {{ font-size: 20px; margin: 24px 0; display: block; min-height: 56px; }}
      </style></head><body><h1>Forge upload fixture</h1>
      <form method="post" action="/submit" enctype="multipart/form-data">
      <input type="hidden" name="case" value="{case}">
      <label for="attachment">Choose fixture</label>
      <input id="attachment" name="attachment" type="file" required aria-label="Choose fixture">
      <p id="selected">No fixture selected</p><button type="submit">Submit fixture</button>
      </form><script>document.getElementById('attachment').addEventListener('change', function () {{
        document.getElementById('selected').textContent = this.files.length
          ? 'Selected fixture: ' + this.files[0].name + ' (' + this.files[0].size + ' bytes)'
          : 'No fixture selected';
      }});</script></body></html>'''.encode()


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, certificate, key, receipts):
        if address[0] != '127.0.0.1':
            raise ValueError('Fixture may bind only IPv4 loopback')
        self.receipts = Path(receipts)
        self.receipt_lock = threading.Lock()
        super().__init__(address, FixtureHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certificate, key)
        self.socket = context.wrap_socket(self.socket, server_side=True)


class FixtureHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass

    def record_request(self, method):
        route = urlsplit(self.path).path
        event = {'method': method, 'route': route if route in ('/form', '/submit') else 'other'}
        with self.server.receipt_lock:
            with self.server.receipts.with_name('requests.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event, sort_keys=True) + '\n')

    def respond(self, status, body):
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.record_request('GET')
        path = urlsplit(self.path)
        query = parse_qs(path.query)
        if path.path == '/form' and set(query) == {'case'} and len(query['case']) == 1 and query['case'][0] in CASES:
            self.respond(200, form(query['case'][0]))
        else:
            self.respond(404, b'Not a fixture route')

    def do_POST(self):
        self.record_request('POST')
        length = self.headers.get('Content-Length', '')
        if self.path != '/submit' or self.headers.get('Transfer-Encoding') or not length.isdecimal() or not 0 < int(length) <= MAXIMUM_BODY:
            self.close_connection = True
            self.respond(400, b'Invalid fixture request')
            return
        body = self.rfile.read(int(length))
        try:
            if len(body) != int(length):
                raise ValueError('Incomplete fixture request')
            receipt = inspect_multipart(self.headers.get('Content-Type', ''), body)
        except (ValueError, UnicodeError, KeyError):
            self.respond(400, b'Fixture mismatch')
            return
        with self.server.receipt_lock:
            with self.server.receipts.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(receipt, sort_keys=True) + '\n')
        self.respond(200, b'<!doctype html><meta name="viewport" content="width=device-width"><h1>Upload accepted</h1>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--certificate', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with FixtureServer(('127.0.0.1', args.port), args.certificate, args.key, args.output / 'receipts.jsonl') as server:
        (args.output / 'endpoint.json').write_text(json.dumps({'host': '127.0.0.1', 'port': server.server_port}) + '\n')
        print(json.dumps({'port': server.server_port}), flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
