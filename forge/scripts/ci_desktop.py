#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Build the already-integrated fork on a native CI host, then package it.

Artifact development builds only. No signing-policy changes, profile import,
release upload, installer registration or automatic updates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import struct
import sys

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT.parent


def run(*command,env=None):
    subprocess.run([str(item) for item in command],cwd=ROOT,env=env,check=True)


def verify_architecture(binary,system,machine):
    arm=machine.lower() in ('arm64','aarch64')
    if system=='darwin':
        run('lipo','-verify_arch','arm64' if arm else 'x86_64',binary)
        return
    with binary.open('rb') as file:
        header=file.read(64)
        if system=='linux':
            if header[:5]!=b'\x7fELF\x02' or header[5]!=1: raise ValueError('Expected little-endian ELF64 runtime')
            actual=struct.unpack_from('<H',header,18)[0]
            expected=183 if arm else 62
        elif system=='win32':
            if header[:2]!=b'MZ': raise ValueError('Expected PE runtime')
            file.seek(struct.unpack_from('<I',header,0x3c)[0])
            coff=file.read(6)
            if coff[:4]!=b'PE\0\0': raise ValueError('Invalid PE signature')
            actual=struct.unpack_from('<H',coff,4)[0]
            expected=0xaa64 if arm else 0x8664
        else: raise ValueError('Unsupported runtime format')
    if actual!=expected: raise ValueError(f'Runtime architecture mismatch: {actual:#x} != {expected:#x}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='New directory')
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists(): parser.error('Output directory must be new')
    if sys.platform not in ('linux','win32','darwin'): parser.error('Unsupported host')
    env={**os.environ,'MOZCONFIG':str(PROJECT/'mozconfig'),'MACH_TELEMETRY_NO_SUBMIT':'1'}
    env['MOZBUILD_STATE_PATH']=str(Path(os.environ.get('RUNNER_TEMP',str(PROJECT)))/'forge-mozbuild')
    run(sys.executable,ROOT/'mach','--no-interactive','bootstrap','--application-choice',
        'browser_artifact_mode','--no-system-changes','--no-agentic-tools',env=env)
    run(sys.executable,ROOT/'mach','build',env=env)
    output.mkdir(parents=True,exist_ok=False)
    target=f'{sys.platform}-{platform.machine().lower()}'
    if sys.platform=='darwin':
        app=output/'Forge.app'
        run(sys.executable,PROJECT/'scripts/package_macos.py','--source',ROOT,'--output',app,env=env)
        binary=app/'Contents/MacOS/forge'
        verify_architecture(app/'Contents/MacOS/firefox',sys.platform,platform.machine())
        archive=output/f'Forge-development-{target}.zip'
        run('ditto','-c','-k','--sequesterRsrc','--keepParent',app,archive)
    else:
        # Resolve build-tree symlinks into a self-contained portable development
        # directory. Do not rewrite upstream executable signatures or trust prefs.
        bundle=output/'Forge'
        shutil.copytree(ROOT/'obj-forge/dist/bin',bundle,symlinks=False,
                        ignore=shutil.ignore_patterns('.purgecaches'))
        if sys.platform=='win32':
            binary=bundle/'firefox.exe'
            (bundle/'Forge.cmd').write_text('@echo off\r\nsetlocal\r\n'
                'set "MOZ_APP_DATA=%LOCALAPPDATA%\\ForgeDevelopment\\app-data"\r\n'
                'set "MOZ_LOCAL_APP_DATA=%LOCALAPPDATA%\\ForgeDevelopment\\local-app-data"\r\n'
                'if not exist "%LOCALAPPDATA%\\ForgeDevelopment\\profile" mkdir "%LOCALAPPDATA%\\ForgeDevelopment\\profile"\r\n'
                '"%~dp0firefox.exe" --no-remote --profile "%LOCALAPPDATA%\\ForgeDevelopment\\profile" %*\r\n')
        else:
            binary=bundle/'firefox'
            launcher=bundle/'forge'
            launcher.write_text('#!/bin/sh\nset -eu\numask 077\n'
                'root="${XDG_DATA_HOME:-$HOME/.local/share}/forge-development"\n'
                'mkdir -p "$root/profile" "$root/app-data" "$root/local-app-data"\n'
                'export MOZ_APP_DATA="$root/app-data" MOZ_LOCAL_APP_DATA="$root/local-app-data"\n'
                'exec "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/firefox" --no-remote --profile "$root/profile" "$@"\n')
            launcher.chmod(0o755)
        if not binary.is_file(): raise RuntimeError(f'Missing built runtime: {binary.name}')
        verify_architecture(binary,sys.platform,platform.machine())
        archive=Path(shutil.make_archive(str(output/f'Forge-development-{target}'),
                    'zip' if sys.platform=='win32' else 'xztar',root_dir=output,base_dir='Forge'))
    with archive.open('rb') as file: digest=hashlib.file_digest(file,'sha256').hexdigest()
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    (output/'SOURCE.json').write_text(json.dumps({'sourceCommit':source,'target':target,
        'runtime':'Mozilla artifact development build','signature':'ad-hoc on macOS; no Forge signing on other hosts',
        'archive':archive.name,'sha256':digest,'nativeRussianLocalePackaged':False,
        'runtimeChecks':'Not yet run; see separate CI smoke step'},indent=2)+'\n')
    (output/'SHA256SUMS').write_text(f'{digest}  {archive.name}\n')
    github_output=os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output,'a') as file:file.write(f'binary={binary}\narchive={archive}\n')
    print(archive)


if __name__=='__main__': main()
