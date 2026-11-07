"""Sign exact update payload bytes offline; private keys never belong in Git/on webroot."""
import argparse
import base64
import json
from pathlib import Path
import stat
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--private-key', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    mode = args.private_key.stat().st_mode
    if not stat.S_ISREG(mode) or mode & 0o077 or args.private_key.suffix != '.env':
        parser.error('Private key must be an owner-only .env file outside the repository')
    repo = Path(__file__).resolve().parents[2]
    if args.private_key.resolve().is_relative_to(repo):
        parser.error('Signing key must stay outside the repository')
    # Validation/parsing here does not reserialize signed bytes on clients.
    payload = json.dumps(json.loads(args.payload.read_text()), separators=(',', ':'), sort_keys=True).encode()
    if len(payload) > 32000:
        parser.error('Payload too large')
    signature = subprocess.check_output(['openssl', 'dgst', '-sha256', '-sign', str(args.private_key)], input=payload)
    envelope = {name: base64.b64encode(value).decode() for name, value in [('payload', payload), ('signature', signature)]}
    with args.output.open('x') as output:
        output.write(json.dumps(envelope, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
