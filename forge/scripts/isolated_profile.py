#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Prepare a NEW persistent manual-test profile and launcher; never launch it.

No existing profile is read, copied or registered. No automation/accessibility
preferences are enabled. The generated launcher is an explicit user action.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess


def prepare(binary, output):
    binary=binary.resolve(strict=True)
    app=binary.parents[2]
    if binary.name!='forge' or binary.parent.name!='MacOS' or binary.parent.parent.name!='Contents' or app.name!='Forge.app':
        raise ValueError('Expected Forge.app/Contents/MacOS/forge')
    if not binary.is_file() or not os.access(binary,os.X_OK):
        raise ValueError('Forge launcher must be executable')
    output=output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError('Manual-test output must be a new directory')
    if app in output.resolve().parents:
        raise ValueError('Do not create a profile inside the signed app')
    # Verify the package before creating anything. Do not re-sign or strip xattrs.
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    output.mkdir(parents=True,mode=0o700,exist_ok=False)
    output=output.resolve()
    for name in ('profile','app-data','local-app-data'):
        (output/name).mkdir(mode=0o700)
    lines=['#!/bin/zsh','set -eu','umask 077',
           'unset XRE_PROFILE_PATH XRE_PROFILE_LOCAL_PATH XRE_BINARY_PATH MOZ_APP_RESTART MOZ_MARIONETTE MOZ_HEADLESS FORGE_DIAGNOSTICS_PATH FORGE_LAUNCH_TRACE']
    for variable,name in [('MOZ_APP_DATA','app-data'),('MOZ_LOCAL_APP_DATA','local-app-data')]:
        lines.append(f'export {variable}={shlex.quote(str(output/name))}')
    lines.append(f'exec {shlex.quote(str(binary))} --no-remote --profile {shlex.quote(str(output/"profile"))}')
    launcher=output/'Launch.command'
    launcher.write_text('\n'.join(lines)+'\n');launcher.chmod(0o700)
    metadata={'binary':str(binary),'profile':str(output/'profile'),'launched':False,
              'purpose':'Persistent isolated manual testing; no real-profile import',
              'automationEnabled':False,'signatureVerification':'codesign --verify --deep --strict'}
    marker=output/'isolation.json'
    marker.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n');marker.chmod(0o600)
    return launcher


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New directory; never reuse a real profile')
    args=parser.parse_args()
    print(f'Prepared, not launched: {prepare(args.binary,args.output)}')


if __name__=='__main__': main()
