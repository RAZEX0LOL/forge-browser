#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Developer ID sign a new copy of an existing Forge app, inside out."""
import argparse
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

MAIN_ENTITLEMENTS = {
    'com.apple.security.cs.allow-jit': True,
    'com.apple.security.cs.disable-library-validation': True,
    'com.apple.security.device.audio-input': True,
    'com.apple.security.device.camera': True,
    'com.apple.security.personal-information.location': True,
    'com.apple.security.smartcard': True,
}
HELPER_ENTITLEMENTS = {
    'plugin-container.app': {'com.apple.security.cs.allow-jit': True},
    'media-plugin-helper.app': {'com.apple.security.cs.disable-library-validation': True},
    'security-module-helper.app': {
        'com.apple.security.cs.disable-library-validation': True,
        'com.apple.security.smartcard': True,
    },
}
MACHO_MAGICS = {
    b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',
    b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe',
    b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
    b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca',
}


def entitlements_for(path, app):
    if path == app or path == app / 'Contents/MacOS/firefox':
        return MAIN_ENTITLEMENTS.copy()
    return HELPER_ENTITLEMENTS.get(path.name, {}).copy()


def is_macho(path):
    if path.is_symlink() or not path.is_file():
        return False
    with path.open('rb') as file:
        return file.read(4) in MACHO_MAGICS


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-app', type=Path, required=True)
    parser.add_argument('--output-app', type=Path, required=True)
    parser.add_argument('--identity', required=True, help='Installed Developer ID certificate SHA-1')
    parser.add_argument('--team', required=True)
    args = parser.parse_args()
    source, output = args.source_app.resolve(), args.output_app.absolute()
    if sys.platform != 'darwin' or not re.fullmatch(r'[A-Fa-f0-9]{40}', args.identity):
        parser.error('Requires macOS and an explicit certificate SHA-1')
    if output.name != 'Forge.app' or output.exists() or output.is_symlink() or source in output.parents:
        parser.error('Output must be a new Forge.app outside the source app')
    info = plistlib.loads((source / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier') != 'org.forgebrowser.development':
        parser.error('Expected the separately packaged Forge development app')
    identities = subprocess.check_output(['security', 'find-identity', '-v', '-p', 'codesigning'], text=True)
    if not any(args.identity.upper() in line and 'Developer ID Application:' in line
               and f'({args.team})' in line for line in identities.splitlines()):
        parser.error('Identity is not an installed Developer ID Application for this team')
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, output, symlinks=True)
    bundles = sorted((p for p in output.rglob('*') if p.is_dir() and not p.is_symlink()
                      and p.suffix in ('.app', '.framework', '.xpc')),
                     key=lambda p: len(p.parts), reverse=True)
    executables = set()
    for bundle in [output, *bundles]:
        for relative in ('Contents/Info.plist', 'Resources/Info.plist'):
            plist = bundle / relative
            if plist.is_file():
                data = plistlib.loads(plist.read_bytes())
                name = data.get('CFBundleExecutable')
                if name:
                    for candidate in (bundle / 'Contents/MacOS' / name, bundle / name):
                        if candidate.exists():
                            executables.add(candidate.resolve())
                break
    files = sorted((p for p in output.rglob('*') if is_macho(p) and p.resolve() not in executables),
                   key=lambda p: len(p.parts), reverse=True)
    signed = []
    with tempfile.TemporaryDirectory(prefix='forge-entitlements-') as temporary:
        for index, path in enumerate([*files, *bundles, output]):
            command = ['codesign', '--force', '--sign', args.identity, '--options', 'runtime', '--timestamp']
            entitlements = entitlements_for(path, output)
            if entitlements:
                plist = Path(temporary) / f'{index}.plist'
                plist.write_bytes(plistlib.dumps(entitlements))
                command += ['--entitlements', str(plist), '--generate-entitlement-der']
            run(*command, path)
            signed.append({'path': str(path.relative_to(output)), 'entitlements': entitlements})
    run('codesign', '--verify', '--deep', '--strict', '--verbose=2', output)
    for path in [*files, *bundles, output]:
        details = subprocess.run(['codesign', '-dv', '--verbose=4', str(path)], capture_output=True, text=True, check=True)
        if f'TeamIdentifier={args.team}' not in details.stderr or 'runtime' not in details.stderr:
            raise RuntimeError(f'Unexpected signing team/runtime: {path.name}')
    report = {'app': str(output), 'team': args.team, 'identity': args.identity,
              'hardenedRuntime': True, 'timestamped': True, 'notarized': False,
              'restrictedMozillaEntitlementsIncluded': False, 'signed': signed}
    output.with_suffix('.signing.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Signed {output}; notarization and runtime validation still required.')


if __name__ == '__main__':
    main()
