#!/usr/bin/env python3
"""Wrap an unchanged signed Forge.app in a drag-to-Applications disk image."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess
import sys


def run(*args):
    return subprocess.check_output(list(map(str, args)), stderr=subprocess.STDOUT)


def bundle_manifest(app):
    result = {}
    for path in sorted(app.rglob('*')):
        name = str(path.relative_to(app))
        if path.is_symlink():
            result[name] = {'symlink': str(path.readlink())}
        elif path.is_file():
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result[name] = {'sha256': digest, 'mode': path.stat().st_mode & 0o777}
    return result


def app_icon(app):
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier') != 'org.forgebrowser.development' or info.get('CFBundleExecutable') != 'forge':
        raise ValueError('Expected the Forge application bundle and launcher')
    if info.get('CFBundleIconName'):
        raise ValueError('Asset-catalog icon override must be removed before signing Forge')
    name = info.get('CFBundleIconFile', '')
    if not name or Path(name).name != name:
        raise ValueError('Bundle must reference its own icon basename')
    if not name.endswith('.icns'):
        name += '.icns'
    icon = app / 'Contents/Resources' / name
    if icon.is_symlink() or not icon.is_file() or icon.read_bytes()[:4] != b'icns':
        raise ValueError('Missing or invalid application ICNS icon')
    return icon


def background(path):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (720, 440), '#101713')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 22)
    small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 15)
    draw.text((360, 48), 'Forge', font=font, fill='#a4efce', anchor='mm')
    draw.text((360, 86), 'Drag Forge to Applications', font=small, fill='#e3eee7', anchor='mm')
    draw.line([(305, 210), (415, 210)], fill='#a4efce', width=4)
    draw.line([(400, 197), (415, 210), (400, 223)], fill='#a4efce', width=4)
    draw.text((360, 368), 'Quit Forge before replacing an existing installation.',
              font=small, fill='#aabbb0', anchor='mm')
    draw.text((360, 397), 'Перетащи Forge в «Программы»', font=small, fill='#aabbb0', anchor='mm')
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True, help='New private staging directory, retained as evidence')
    parser.add_argument('--identity', required=True, help='Developer ID identity for the disk image, never a private key')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('Requires macOS')
    app, output, work = args.app.absolute(), args.output.absolute(), args.work.absolute()
    if app.name != 'Forge.app' or app.is_symlink() or not app.is_dir():
        parser.error('Input must be a regular Forge.app directory')
    if output.suffix != '.dmg' or output.exists() or output.is_symlink() or work.exists():
        parser.error('Output DMG and work directory must be new; never overwrite release bytes')
    if app in output.parents or app in work.parents:
        parser.error('Never stage inside the signed application')
    from ds_store import DSStore
    from mac_alias import Alias
    icon = app_icon(app)
    run('codesign', '--verify', '--deep', '--strict', app)
    run('xcrun', 'stapler', 'validate', app)
    before = bundle_manifest(app)
    work.mkdir(mode=0o700, parents=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    source = work / 'source'
    source.mkdir()
    run('ditto', '--rsrc', '--extattr', app, source / 'Forge.app')
    (source / 'Applications').symlink_to('/Applications', target_is_directory=True)
    (source / '.background').mkdir()
    background(source / '.background/install.png')
    (source / '.VolumeIcon.icns').write_bytes(icon.read_bytes())
    writable, mount = work / 'layout.dmg', work / 'mount'
    mount.mkdir()
    run('hdiutil', 'create', '-volname', 'Forge', '-fs', 'HFS+', '-format', 'UDRW', '-srcfolder', source, writable)
    run('hdiutil', 'attach', '-nobrowse', '-noautoopen', '-mountpoint', mount, writable)
    try:
        run('xcrun', 'SetFile', '-a', 'C', mount)
        background_alias = Alias.for_file(str(mount / '.background/install.png'))
        # Finder resolves the volume identity/relative target; do not embed the
        # maintainer's private staging path as the mountpoint fallback.
        background_alias.volume.posix_path = '/Volumes/Forge'
        with DSStore.open(str(mount / '.DS_Store'), 'w+') as store:
            store['.']['bwsp'] = {'ShowStatusBar': False, 'ShowToolbar': False, 'ShowSidebar': False,
                                 'ShowPathbar': False, 'WindowBounds': '{{160, 120}, {720, 440}}'}
            store['.']['icvp'] = {'viewOptionsVersion': 1, 'backgroundType': 2,
                                 'backgroundImageAlias': background_alias.to_bytes(),
                                 'iconSize': 104.0, 'textSize': 14.0, 'gridSpacing': 100.0,
                                 'arrangeBy': 'none', 'labelOnBottom': True, 'showIconPreview': True}
            store['.']['vSrn'] = ('long', 1)
            store['.']['vstl'] = ('type', 'icnv')
            store['Forge.app']['Iloc'] = (190, 210)
            store['Applications']['Iloc'] = (530, 210)
        assert bundle_manifest(mount / 'Forge.app') == before, 'Mounted app bytes/modes differ'
        run('codesign', '--verify', '--deep', '--strict', mount / 'Forge.app')
        run('xcrun', 'stapler', 'validate', mount / 'Forge.app')
    finally:
        run('hdiutil', 'detach', mount)
    run('hdiutil', 'convert', writable, '-format', 'UDZO', '-imagekey', 'zlib-level=9', '-o', output)
    run('codesign', '--sign', args.identity, '--timestamp', '--identifier', 'org.forgebrowser.diskimage', output)
    run('codesign', '--verify', '--strict', output)
    assert bundle_manifest(app) == before, 'Source app changed'
    receipt = {'file': output.name, 'bytesBeforeStapling': output.stat().st_size,
               'sourceAppUnchanged': True, 'mountedAppMatchesSource': True,
               'applicationIcon': icon.name, 'volumeIcon': True, 'applicationsSymlink': '/Applications',
               'notarizedDMG': False, 'note': 'Submit DMG to Apple once, staple, then compute final release hash.'}
    (work / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (work / 'app-manifest.json').write_text(json.dumps(before, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
