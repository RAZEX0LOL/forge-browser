#!/usr/bin/env python3
"""Fetch official macOS comparators into a NEW isolated directory, never /Applications.

TLS checks stay enabled. Verify upstream checksum and Apple code signature before
using a copied bundle. Do not remove quarantine, alter signatures or launch GUI.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
from measurements import write_report


def fetch(url, target):
    subprocess.run(['curl','--fail','--location','--silent','--show-error','--proto','=https',
                    '--proto-redir','=https','--output',str(target),url],check=True)


def digest(path, kind):
    h=hashlib.new(kind)
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def normalize_finder_metadata(app):
    # Some upstream DMGs contain FinderInfo on signed executable resources.
    # Remove ONLY that decorative metadata on our private copy. Never touch
    # quarantine, signatures, resource contents or any installed application.
    changed=[]
    for path in [app,*app.rglob('*')]:
        if path.is_symlink(): continue
        attributes=subprocess.check_output(['xattr',str(path)],text=True).splitlines()
        if 'com.apple.FinderInfo' in attributes:
            subprocess.run(['xattr','-d','com.apple.FinderInfo',str(path)],check=True)
            changed.append(str(path.relative_to(app)))
    return changed


def verify_bundle(target):
    normalized=normalize_finder_metadata(target)
    verification=subprocess.run(['codesign','--verify','--deep','--strict',str(target)],capture_output=True,text=True)
    if verification.returncode: raise RuntimeError('Official bundle signature verification failed: '+verification.stderr)
    identity=subprocess.run(['codesign','--display','--verbose=2',str(target)],capture_output=True,text=True,check=True).stderr
    assessment=subprocess.run(['spctl','--assess','--type','execute','--verbose=2',str(target)],capture_output=True,text=True)
    if assessment.returncode: raise RuntimeError('Gatekeeper assessment failed; not bypassing it: '+assessment.stderr)
    return {'app':str(target.resolve()),'signature':identity,'gatekeeper':assessment.stderr,
            'removedDecorativeFinderInfoOnly':normalized,'quarantineUntouched':True}


def unpack(dmg, folder):
    result=subprocess.run(['hdiutil','attach','-readonly','-nobrowse','-plist',str(dmg)],capture_output=True,check=True)
    mounted=plistlib.loads(result.stdout)
    volume=next(entry['mount-point'] for entry in mounted['system-entities'] if 'mount-point' in entry)
    try:
        apps=list(Path(volume).glob('*.app'))
        if len(apps)!=1: raise RuntimeError('Expected exactly one app on the official image')
        target=folder/apps[0].name
        subprocess.run(['ditto',str(apps[0]),str(target)],check=True)
    finally:
        subprocess.run(['hdiutil','detach',volume],check=True)
    return verify_bundle(target)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='New directory; existing paths are refused')
    args=parser.parse_args()
    folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=False)
    report={'status':'running','products':[]}
    try:
        fetch('https://product-details.mozilla.org/1.0/firefox_versions.json',folder/'firefox-versions.json')
        version=json.loads((folder/'firefox-versions.json').read_text())['LATEST_FIREFOX_VERSION']
        base=f'https://archive.mozilla.org/pub/firefox/releases/{version}/'
        relative=f'mac/en-US/Firefox {version}.dmg'
        fetch(base+'SHA512SUMS',folder/'firefox-SHA512SUMS')
        expected=next(line.split(None,1)[0] for line in (folder/'firefox-SHA512SUMS').read_text().splitlines()
                      if line.split(None,1)[-1].strip()==relative)
        target=folder/'firefox.dmg';url=base+relative.replace(' ','%20');fetch(url,target)
        actual=digest(target,'sha512')
        if actual!=expected: raise RuntimeError('Firefox checksum mismatch')
        report['products'].append({'product':'Firefox','version':version,'url':url,'sha512':actual,**unpack(target,folder)})
        write_report(folder/'provenance.json',report)
        fetch('https://api.github.com/repos/zen-browser/desktop/releases/latest',folder/'zen-release.json')
        release=json.loads((folder/'zen-release.json').read_text())
        asset=next(a for a in release['assets'] if a['name']=='zen.macos-universal.dmg')
        target=folder/'zen.dmg';fetch(asset['browser_download_url'],target)
        actual=digest(target,'sha256')
        if asset.get('digest')!='sha256:'+actual: raise RuntimeError('Zen checksum mismatch or no published checksum')
        report['products'].append({'product':'Zen','version':release['tag_name'],'url':asset['browser_download_url'],
            'sha256':actual,**unpack(target,folder)})
        report['status']='passed'
    except Exception as error:
        report.update(status='failed',error=str(error));raise
    finally: write_report(folder/'provenance.json',report)


if __name__=='__main__': main()
