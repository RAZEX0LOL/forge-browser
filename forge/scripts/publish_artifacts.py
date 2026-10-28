#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Upload verified CI artifacts to an OWNER-CREATED DRAFT prerelease only."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile

NATIVE={
    'linux-x64':('desktop','linux-x86_64','Forge-development-linux-x86_64.tar.xz'),
    'macos-intel':('desktop','darwin-x86_64','Forge-development-macos-x86_64.zip'),
    'linux-arm64':('arm','linux-aarch64','Forge-development-linux-arm64.tar.xz'),
    'windows-arm64':('arm','win32-arm64','Forge-development-windows-arm64.zip'),
    'windows-x64':('windows','win32-amd64','Forge-development-windows-x86_64.zip'),
}
MAC_IMAGE='Forge-development-20261028-macos-arm64.dmg'
MAC_SHA='eec183d157ef64fdbc30d06133007fe2ddf64fd9cee2562cf2009bfb91971046'
GECKOVIEW_SOURCE='https://hg.mozilla.org/releases/mozilla-release/rev/5add844c26613d7e4d84c799d6e23cf987b1240d'


def gh(*args):
    return subprocess.check_output(['gh',*map(str,args)],text=True)


def api(path): return json.loads(gh('api',path))


def sha(path):
    with path.open('rb') as file:return hashlib.file_digest(file,'sha256').hexdigest()


def resource_name(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or name in ('.','..'):
        raise ValueError('Unsafe artifact resource name')
    return name


def validate_native(folder,report,head,target):
    metadata=json.loads((folder/'SOURCE.json').read_text(encoding='utf-8'))
    if metadata.get('sourceCommit')!=head or metadata.get('target')!=target:
        raise ValueError('Artifact source or target mismatch')
    checks=report.get('passed')
    if report.get('status')!='passed' or not isinstance(checks,list) or len(checks)<200 or not all(isinstance(item,str) for item in checks):
        raise ValueError('Native runtime suite did not pass')
    archive=folder/resource_name(metadata['archive'])
    if archive.is_symlink() or not archive.is_file() or sha(archive)!=metadata.get('sha256'):
        raise ValueError('Artifact checksum mismatch')
    return archive,metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True)
    parser.add_argument('--tag',required=True)
    for group in ('desktop','arm','windows','mobile'):
        parser.add_argument(f'--{group}-run',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repo):parser.error('Invalid repository')
    if not re.fullmatch(r'v[A-Za-z0-9_.-]+',args.tag):parser.error('Invalid prerelease tag')
    ids={group:getattr(args,f'{group}_run') for group in ('desktop','arm','windows','mobile')}
    if not all(value.isdecimal() for value in ids.values()):parser.error('Run IDs must be decimal')
    releases=api(f'repos/{args.repo}/releases?per_page=100')
    release=next(item for item in releases if item['tag_name']==args.tag)
    if not release['draft'] or not release['prerelease'] or release['author']['login'].lower()!=args.repo.split('/')[0].lower():
        raise RuntimeError('Expected an owner-created draft prerelease')
    if release['assets']:raise RuntimeError('Draft already has assets; refusing to overwrite them')
    with tempfile.TemporaryDirectory(prefix='forge-publish-') as temp:
        root=Path(temp);output=root/'release';output.mkdir()
        runs={};builds=[]
        for group,run_id in ids.items():
            run=api(f'repos/{args.repo}/actions/runs/{run_id}')
            if run['head_repository']['full_name'].lower()!=args.repo.lower() or run['event']!='workflow_dispatch':
                raise ValueError('Unexpected artifact source repository/event')
            expected='Forge mobile prototypes' if group=='mobile' else 'Forge native desktop builds'
            if run['name']!=expected:raise ValueError('Unexpected artifact workflow')
            runs[group]=run
            gh('run','download',run_id,'--repo',args.repo,'--pattern','Forge-*','--dir',root/group)
        def include(path,name,metadata):
            name=resource_name(name)
            target=output/name
            if target.exists():raise ValueError('Duplicate release asset')
            shutil.copyfile(path,target)
            builds.append({'file':name,'sha256':sha(target),**metadata})
        for target,(group,machine,name) in NATIVE.items():
            report=json.loads((root/group/f'Forge-smoke-{target}'/'smoke.json').read_text(encoding='utf-8'))
            archive,metadata=validate_native(root/group/f'Forge-development-{target}',report,runs[group]['head_sha'],machine)
            include(archive,name,{'target':target,'sourceCommit':metadata['sourceCommit'],
                'ciRun':runs[group]['html_url'],'browserChecks':len(report['passed']),
                'runtime':metadata['runtime'],'nativeRussianLocalePackaged':False})
        original=root/'original';original.mkdir()
        for name in (MAC_IMAGE,'SOURCE.json'):
            gh('release','download','v0.1.0-dev.20261028','--repo',args.repo,'--pattern',name,'--dir',original)
        if sha(original/MAC_IMAGE)!=MAC_SHA:raise ValueError('Original macOS image checksum mismatch')
        mac=json.loads((original/'SOURCE.json').read_text(encoding='utf-8'))
        include(original/MAC_IMAGE,MAC_IMAGE,{'target':'macos-arm64','sourceCommit':mac['sourceCommit'],
            'browserChecks':285,'validationOrigin':'maintainer local isolated checks; not a CI result',
            'runtime':mac['runtime'],'nativeRussianLocalePackaged':True,'signature':mac['signing']})
        mobile=root/'mobile';mobile_source=runs['mobile']['head_sha'];mobile_url=runs['mobile']['html_url']
        for abi in ('arm64-v8a','armeabi-v7a','x86_64'):
            apk=mobile/'Forge-android-prototype-debug'/f'app-{abi}-debug.apk'
            with zipfile.ZipFile(apk) as package:
                actual={name.split('/')[1] for name in package.namelist() if name.startswith('lib/') and name.count('/')>=2}
                if actual!={abi} or package.testzip() is not None:raise ValueError('APK architecture/integrity mismatch')
            include(apk,f'Forge-android-prototype-{abi}-debug.apk',{'target':f'android-{abi}',
                'sourceCommit':mobile_source,'ciRun':mobile_url,'engine':'GeckoView 159.0.20261022150525',
                'engineSource':GECKOVIEW_SOURCE,'signing':'ephemeral debug identity, not a production publisher key',
                'runtimeValidation':'two native tests on Android x86_64 emulator; physical ARM devices untested'})
        for name,device in [('Forge-ios-simulator-prototype.zip',False),('Forge-ios-device-unsigned.xcarchive.zip',True)]:
            archive=mobile/'Forge-ios-simulator-prototype'/name
            with zipfile.ZipFile(archive) as package:
                names=package.namelist()
                if any(n.endswith('embedded.mobileprovision') for n in names):raise ValueError('Do not publish provisioning data')
                info_name=next(n for n in names if n.endswith('ForgeMobile.app/Info.plist'))
                info=plistlib.loads(package.read(info_name))
                expected='iPhoneOS' if device else 'iPhoneSimulator'
                if info.get('CFBundleSupportedPlatforms')!=[expected]:raise ValueError('iOS platform mismatch')
                if package.testzip() is not None:raise ValueError('Corrupt iOS archive')
            include(archive,name,{'target':'ios-device-unsigned' if device else 'ios-simulator',
                'sourceCommit':mobile_source,'ciRun':mobile_url,'engine':'system WebKit, not Gecko',
                'runtimeValidation':'four native XCTest cases, English and Russian, on iOS Simulator',
                'installableIPhoneIPA':False,'deviceRuntimeTested':False})
        manifest={'schemaVersion':1,'repository':f'https://github.com/{args.repo}',
            'status':'development / mobile prototypes; no supported automatic security-update service',
            'geckoSourceBase':'efd2d1e6f77570ae6bc5294731a68101e45c81a3','builds':builds}
        (output/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        files=sorted(output.iterdir())
        (output/'SHA256SUMS').write_text(''.join(f'{sha(file)}  {file.name}\n' for file in files),encoding='utf-8')
        gh('release','upload',args.tag,'--repo',args.repo,*sorted(output.iterdir()))
        gh('release','edit',args.tag,'--repo',args.repo,'--draft=false','--prerelease')
        print(json.dumps({'published':args.tag,'assets':len(list(output.iterdir())),'builds':len(builds)}))


if __name__=='__main__':main()
