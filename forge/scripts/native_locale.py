#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Stage pinned upstream Russian resources with Mozilla's own merge/stage actions.

All outputs are new, isolated directories. No profile, installed app, signature
preference, or Gecko executable is modified. Packaging installs data before signing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import subprocess
import shutil
import sys
from measurements import write_report

PROJECT=Path(__file__).resolve().parents[1]


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_translations(target):
    """Fetch just the pinned snapshot into a new sparse checkout; never reset one."""
    config=json.loads((PROJECT/'native-l10n.json').read_text())
    target=target.resolve();target.mkdir(parents=True,exist_ok=False)
    commands=[['git','init','--quiet',str(target)],
              ['git','-C',str(target),'remote','add','origin',config['repository']],
              ['git','-C',str(target),'config','remote.origin.promisor','true'],
              ['git','-C',str(target),'config','remote.origin.partialclonefilter','blob:none'],
              ['git','-C',str(target),'fetch','--filter=blob:none','--depth','1','origin',config['revision']],
              ['git','-C',str(target),'sparse-checkout','set',config['locale']],
              ['git','-C',str(target),'checkout','--quiet','--detach','FETCH_HEAD']]
    for command in commands: subprocess.run(command,check=True)


def coverage_summary(coverage):
    return {'resources':len(coverage),'entries':sum(item['total'] for item in coverage.values()),
            'missingEntries':sum(len(item['missing']) for item in coverage.values()),
            'resourcesWithFallback':sum(bool(item['missing']) for item in coverage.values())}


MANIFESTS={'chrome.manifest','browser/chrome.manifest','chrome/ru.manifest',
           'browser/chrome/ru.manifest','browser/chrome/browser.manifest'}
PREFIXES=('localization/ru/','browser/localization/ru/','chrome/ru/',
          'browser/chrome/ru/','browser/chrome/browser/locale/ru/')
SUFFIXES={'.ftl','.properties','.png','.svg','.css','.json'}
DICTIONARIES={'dictionaries/ru.aff','dictionaries/ru.dic','dictionaries/ru-license.txt'}


def validate_stage(folder):
    folder=folder.resolve()
    metadata=json.loads((folder/'provenance.json').read_text())
    config=json.loads((PROJECT/'native-l10n.json').read_text())
    upstream=json.loads((PROJECT/'upstream.json').read_text())
    if (metadata.get('status')!='passed' or metadata.get('locale')!='ru' or
        metadata.get('translationRevision')!=config['revision'] or
        metadata.get('geckoRevision')!=upstream['revision'] or not metadata.get('files')):
        raise ValueError('Locale stage is incomplete or does not match pinned inputs')
    staged=folder/'staged'
    actual={str(path.relative_to(staged)) for path in staged.rglob('*') if path.is_file()}
    if any(path.is_symlink() for path in staged.rglob('*')) or actual!=set(metadata['files']):
        raise ValueError('Unexpected, missing or symlinked locale files')
    for name,expected in metadata['files'].items():
        relative=PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name:
            raise ValueError('Unsafe locale resource path')
        if name not in MANIFESTS and name not in DICTIONARIES and not (name.startswith(PREFIXES) and relative.suffix in SUFFIXES):
            raise ValueError(f'Not a locale-only resource: {name}')
        if sha256(staged/name)!=expected:
            raise ValueError(f'Locale resource changed: {name}')
    return metadata


def merge_manifest(current, addition):
    lines=current.splitlines()
    for line in addition.splitlines():
        line=line.strip()
        if not line or line.startswith('#') or line in lines: continue
        parts=line.split()
        if parts[0]=='locale' and len(parts)>=4 and parts[2]=='ru':
            target=PurePosixPath(parts[3])
            if target.is_absolute() or '..' in target.parts or ':' in parts[3]:
                raise ValueError('Unsafe chrome locale mapping')
        elif parts[0]=='manifest' and len(parts)==2 and parts[1] in ('chrome/ru.manifest','chrome/browser.manifest'):
            pass
        else:
            raise ValueError(f'Refusing new non-locale chrome registration: {line}')
        lines.append(line)
    return '\n'.join(lines)+'\n'


def install(folder, app):
    """Only call on the packager's new private copy, BEFORE ad-hoc signing."""
    metadata=validate_stage(folder)
    resources=app/'Contents/Resources'
    staged=folder/'staged'
    writes={}
    for name in metadata['files']:
        target=resources/name;data=(staged/name).read_bytes()
        if name in MANIFESTS:
            data=merge_manifest(target.read_text() if target.exists() else '',data.decode()).encode()
        elif target.exists() and target.read_bytes()!=data:
            raise ValueError(f'Refusing to overwrite existing locale data: {name}')
        writes[target]=data
    multilocale=resources/'res/multilocale.txt'
    locales=multilocale.read_text().strip().split(',')
    if 'en-US' not in locales: raise ValueError('The base app must retain en-US fallback')
    if 'ru' not in locales: locales.append('ru')
    writes[multilocale]=(','.join(locales)+'\n').encode()
    pref=resources/'defaults/pref/forge-native-locale.js'
    if pref.exists(): raise ValueError('Native locale preference file already exists')
    # A default, not a lock. Explicit user language preferences retain priority.
    writes[pref]=b'// Built-in Forge development locale; keep en-US fallback.\npref("intl.locale.requested", "ru,en-US");\npref("forge.locale.followApp", true);\n'
    if 'dictionaries/ru.dic' in metadata['files']:
        builtin=resources/'browser/chrome/browser/content/browser/built_in_addons.json'
        registration=json.loads(builtin.read_text())
        dictionaries=registration.get('dictionaries')
        if not isinstance(dictionaries,dict) or 'en-US' not in dictionaries:
            raise ValueError('Base built-in dictionary registration is missing')
        if 'ru' in dictionaries and dictionaries['ru']!='dictionaries/ru.dic':
            raise ValueError('Conflicting Russian dictionary registration')
        registration={**registration,'dictionaries':{**dictionaries,'ru':'dictionaries/ru.dic'}}
        writes[builtin]=(json.dumps(registration,indent=2)+'\n').encode()
    coverage=json.loads((staged/'localization/ru/coverage.json').read_text())
    metadata={**metadata,'coverage':coverage_summary(coverage),'signaturePolicy':'unchanged; built-in resources, no addon install'}
    writes[resources/'forge-native-l10n.json']=(json.dumps(metadata,indent=2)+'\n').encode()
    for target,data in writes.items():
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return metadata


def prepare(source, translations, output):
    config=json.loads((PROJECT/'native-l10n.json').read_text())
    upstream=json.loads((PROJECT/'upstream.json').read_text())
    source=source.resolve();translations=translations.resolve();output=output.resolve()
    if git(source,'rev-parse','HEAD')!=upstream['revision']:
        raise ValueError('Gecko source differs from upstream.json')
    if git(translations,'rev-parse','HEAD')!=config['revision'] or git(translations,'status','--porcelain'):
        raise ValueError('Translations must be the clean, pinned native-l10n.json revision')
    if any(path.is_symlink() for path in (translations/config['locale']).rglob('*')):
        raise ValueError('Symlinked translation inputs are not allowed')
    if not (source/'obj-forge/l10n-manifest.json').is_file():
        raise ValueError('Build the pinned Firefox source before staging localization')
    output.mkdir(parents=True,exist_ok=False)
    report={'status':'running','locale':config['locale'],'geckoRevision':upstream['revision'],
            'translationRepository':config['repository'],'translationRevision':config['revision'],
            'mode':'built-in locale; Mozilla merge and chrome staging; en-US fallback preserved'}
    report_path=output/'provenance.json';write_report(report_path,report)
    env={**os.environ,'MOZBUILD_STATE_PATH':str((PROJECT/'.mozbuild').resolve()),'MACH_TELEMETRY_NO_SUBMIT':'1'}
    command=[sys.executable,str(source/'mach'),'python','--virtualenv','build','-m']
    try:
        subprocess.run(command+['mozbuild.action.l10n_merge','--locale',config['locale'],
            '--config',str(source/'browser/locales/l10n.toml'),'--l10n-base',str(translations),
            '--target',str(output/'merge')],cwd=source,env=env,check=True)
        subprocess.run(command+['mozbuild.action.l10n_stage','--locale',config['locale'],
            '--manifest',str(source/'obj-forge/l10n-manifest.json'),'--merge-tree',str(output/'merge'/config['locale']),
            '--dest',str(output/'staged'),'--topsrcdir',str(source),'--topobjdir',str(source/'obj-forge'),
            '--mode','chrome'],cwd=source,env=env,check=True)
        dictionaries=output/'staged/dictionaries';dictionaries.mkdir()
        hunspell=output/'merge'/config['locale']/'extensions/spellcheck/hunspell'
        for original,destination in [('ru.aff','ru.aff'),('ru.dic','ru.dic'),('license.txt','ru-license.txt')]:
            shutil.copyfile(hunspell/original,dictionaries/destination)
        report['files']={str(path.relative_to(output/'staged')):sha256(path)
                         for path in sorted((output/'staged').rglob('*')) if path.is_file()}
        report['coverage']=coverage_summary(json.loads((output/'merge'/config['locale']/'coverage.json').read_text()))
        report['status']='passed'
    except Exception as error:
        report.update(status='failed',error=str(error));raise
    finally: write_report(report_path,report)
    print(f"Staged {len(report['files'])} locale resources in {output}")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--translations',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New output directory')
    parser.add_argument('--fetch-translations',action='store_true',help='First fetch the pinned ru snapshot into a NEW --translations directory')
    args=parser.parse_args()
    if args.fetch_translations: fetch_translations(args.translations)
    prepare(args.source,args.translations,args.output)


if __name__=='__main__': main()
