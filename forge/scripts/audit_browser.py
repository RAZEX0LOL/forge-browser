#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Run edge-case UI regressions in an isolated, disposable Firefox profile."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from marionette_driver.marionette import Marionette
from audit_checks import run_audit_checks
from editor_checks import run_editor_checks
from keyboard_checks import run_keyboard_checks
from transfer_checks import run_transfer_checks
from workflow_checks import run_workflow_checks
from accessibility_checks import run_accessibility_checks
from public_site_checks import run_public_site_checks
from native_locale_checks import run_native_locale_checks
from mac_accessibility_checks import run_mac_accessibility_checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',required=True,type=Path)
    suite=parser.add_mutually_exclusive_group()
    suite.add_argument('--appearance',action='store_true',help='Run appearance-editor checks only')
    suite.add_argument('--keyboard',action='store_true',help='Run keyboard-navigation checks only')
    suite.add_argument('--transfers',action='store_true',help='Run native tab/group/split transfer checks only')
    suite.add_argument('--workflow',action='store_true',help='Run interactive page and DevTools checks only')
    suite.add_argument('--accessibility',action='store_true',help='Run Gecko accessibility-tree and forced-colors checks')
    suite.add_argument('--public-sites',action='store_true',help='Read-only MDN/GitHub/Wikipedia checks; uses public network')
    suite.add_argument('--native-locale',action='store_true',help='Validate a package with built-in native Russian resources')
    suite.add_argument('--mac-accessibility',action='store_true',help='Native Gecko macOS AX bridge (not manual VoiceOver)')
    args=parser.parse_args()
    results=Path(__file__).resolve().parents[1]/'test-results'
    results.mkdir(exist_ok=True)
    passed=[]
    output='mac-accessibility-audit.json' if args.mac_accessibility else 'native-locale-audit.json' if args.native_locale else 'public-sites-audit.json' if args.public_sites else 'accessibility-audit.json' if args.accessibility else 'workflow-audit.json' if args.workflow else 'transfer-audit.json' if args.transfers else 'keyboard-audit.json' if args.keyboard else 'appearance-audit.json' if args.appearance else 'audit.json'
    with tempfile.TemporaryDirectory(prefix='forge-audit-') as workspace:
        for variable,name in [('MOZ_APP_DATA','app-data'),('MOZ_LOCAL_APP_DATA','local-app-data')]:
            path=Path(workspace)/name;path.mkdir();os.environ[variable]=str(path)
        client=Marionette(bin=str(args.binary.resolve()),port=0,headless=True,workspace=workspace,
                          app_args=['--remote-allow-system-access','--no-remote'],
                          gecko_log=str(results/'audit-gecko.log'),
                          prefs={'browser.shell.checkDefaultBrowser':False,'browser.startup.homepage':'about:blank','browser.startup.page':0})
        report={'binary':str(args.binary.resolve()),'status':'failed','passed':passed,'failures':[]}
        try:
            client.start_session();client.set_context('chrome');client.timeout.script=30
            client.execute_async_script("const done=arguments[arguments.length-1];if(document.documentElement.hasAttribute('forge-ready')){done(true);}else{window.delayedStartupPromise.then(()=>requestAnimationFrame(()=>done(true)));}")
            failures=(run_mac_accessibility_checks if args.mac_accessibility else run_native_locale_checks if args.native_locale else run_public_site_checks if args.public_sites else run_accessibility_checks if args.accessibility else run_workflow_checks if args.workflow else run_transfer_checks if args.transfers else run_keyboard_checks if args.keyboard else run_editor_checks if args.appearance else run_audit_checks)(client,results,passed)
            report={'binary':str(args.binary.resolve()),'status':'failed' if failures else 'passed','passed':passed,'failures':failures}
            if args.mac_accessibility:
                report.update(scope='Gecko in-process nsIAccessibleMacInterface; disposable profile',
                    limitations=['Not manual VoiceOver, speech, rotor or external OS AX transport'])
            (results/output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(f'Audit: {len(passed)} passed, {len(failures)} failed.')
            return bool(failures)
        except Exception as error:
            report['error']=str(error)
            (results/output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            raise
        finally:
            client.cleanup()


if __name__=='__main__':
    raise SystemExit(main())
