#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Stress real in-app restarts in a disposable profile; never retry a failure."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

from browser_diagnostics import DiagnosticMarionette
from ui_wait import settle_ui
from measurements import snapshot_processes, write_report

PROJECT = Path(__file__).resolve().parents[1]


def state(client):
    flushed=client.execute_async_script("""
        const done=arguments[arguments.length-1];
        const {TabStateFlusher}=ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/TabStateFlusher.sys.mjs');
        TabStateFlusher.flushWindow(window).then(()=>done(true),error=>done(String(error)));
    """)
    if flushed is not True:
        raise AssertionError(f'SessionStore flush failed: {flushed}')
    return client.execute_script("""
        const {SessionStore}=ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        return {pid:Services.appinfo.processID,profile:Services.dirsvc.get('ProfD',Ci.nsIFile).path,
            binary:Services.dirsvc.get('XREExeF',Ci.nsIFile).path,
            theme:Services.prefs.getStringPref('forge.theme','{}'),
            workspace:SessionStore.getCustomWindowValue(window,'forge.workspace'),
            tabs:Array.from(gBrowser.tabs,tab=>{
                const saved=JSON.parse(SessionStore.getTabState(tab));
                return {token:SessionStore.getCustomTabValue(tab,'forge.test.restartTab'),
                    workspace:SessionStore.getCustomTabValue(tab,'forge.workspace'),
                    url:saved.entries?.[(saved.index || saved.entries.length)-1]?.url || tab.linkedBrowser.currentURI.spec};
            }),
            selectedTab:SessionStore.getCustomTabValue(gBrowser.selectedTab,'forge.test.restartTab'),
            token:Services.prefs.getIntPref('forge.test.restartToken',0),
            ready:document.documentElement.getAttribute('forge-ready')==='true'};
    """)


def wait_ready(client):
    client.set_context('chrome')
    ready = client.execute_async_script("""
        const done=arguments[arguments.length-1];
        const ready=()=>gBrowserInit.delayedStartupFinished &&
            document.documentElement.getAttribute('forge-ready')==='true';
        if(ready()){done(true);return;}
        let attempts=0;
        const timer=setInterval(()=>{
            if(ready()){clearInterval(timer);done(true);}
            else if(++attempts>=400){clearInterval(timer);done(false);}
        },50);
    """)
    if ready is not True:
        raise AssertionError('Browser startup did not finish within 20 seconds')
    settle_ui(client)
    if not state(client)['ready']:
        raise AssertionError('Forge did not initialize after restart')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',required=True,type=Path)
    parser.add_argument('--cycles',type=int,default=10)
    parser.add_argument('--tabs',type=int,default=200)
    parser.add_argument('--output',type=Path,default=PROJECT/'test-results/restart-audit.json')
    args=parser.parse_args()
    binary=args.binary.resolve()
    if not binary.is_file() or not 1 <= args.cycles <= 100 or not 0 <= args.tabs <= 500:
        parser.error('Need an existing binary, 1–100 cycles and 0–500 tabs')
    results=PROJECT/'test-results'
    results.mkdir(exist_ok=True)
    report={'status':'running','binary':str(binary),'cycles':[]}
    write_report(args.output,report)
    client=None
    saved_env={key:os.environ.get(key) for key in ('MOZ_APP_DATA','MOZ_LOCAL_APP_DATA')}
    with tempfile.TemporaryDirectory(prefix='forge-restarts-') as workspace:
        try:
            for key in saved_env:
                folder=Path(workspace)/key
                folder.mkdir()
                os.environ[key]=str(folder)
            client=DiagnosticMarionette(diagnostic_directory=args.output.parent/(args.output.stem+'-native'),trace_directory=workspace,
                bin=str(binary),port=0,headless=True,workspace=workspace,
                app_args=['--remote-allow-system-access','--no-remote'],
                gecko_log=str(results/'restart-gecko.log'),
                prefs={'browser.shell.checkDefaultBrowser':False,'browser.startup.page':0})
            client.start_session()
            client.timeout.script=90
            wait_ready(client)
            client.execute_script("""
                const original=window.prompt;window.prompt=()=>'Restart regression';
                try{document.getElementById('forge-workspace-add').doCommand();}
                finally{window.prompt=original;}
                const {SessionStore}=ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
                Array.from(gBrowser.tabs).forEach((tab,index)=>SessionStore.setCustomTabValue(tab,'forge.test.restartTab',`test-tab-${index}`));
            """)
            for cycle in range(1,args.cycles+1):
                client.execute_script("""
                    Services.prefs.setIntPref('forge.test.restartToken',arguments[0]);
                    Services.prefs.setStringPref('forge.theme',JSON.stringify({appearance:arguments[0]%2?'glass':'amoled'}));
                    const tabs=Array.from({length:arguments[1]},()=>gBrowser.addTrustedTab('about:blank'));
                    if(tabs.length){gBrowser.selectedTab=tabs.at(-1);gBrowser.removeTabs(tabs,{animate:false});}
                """,script_args=[cycle,args.tabs])
                settle_ui(client)
                before=state(client)
                entry={'cycle':cycle,'before':before,'status':'restarting',
                       'processesBefore':snapshot_processes(before['pid'])}
                report['cycles'].append(entry)
                write_report(args.output,report)
                started=time.monotonic()
                client.restart(in_app=True)
                wait_ready(client)
                after=state(client)
                entry.update(after=after,seconds=round(time.monotonic()-started,3))
                for key in ('profile','binary','theme','workspace','token','tabs','selectedTab'):
                    if after[key] != before[key]:
                        raise AssertionError(f'Restart {cycle} changed {key}: {before[key]!r} -> {after[key]!r}')
                if before['pid']==after['pid']:
                    raise AssertionError('Expected a real macOS process restart, not reused UI')
                entry['status']='passed'
                write_report(args.output,report)
                print(f'PASS restart {cycle}: same binary/profile/theme/workspace, new PID',flush=True)
            client.cleanup()
            client=None
            if sys.platform=='darwin' and binary.name=='forge':
                subprocess.run(['codesign','--verify','--deep','--strict',str(binary.parents[2])],check=True)
            report['status']='passed'
        except Exception:
            report.update(status='failed',error=traceback.format_exc())
            if report['cycles']:
                failed=report['cycles'][-1]
                if failed['status']!='passed':
                    failed['status']='failed'
                try:
                    failed['processesAfterFailure']=snapshot_processes(failed['before']['pid'])
                    runner=getattr(getattr(client,'instance',None),'runner',None)
                    failed['runnerReturnCode']=getattr(runner,'returncode',None)
                except Exception as error:
                    failed['diagnosticError']=str(error)
            write_report(args.output,report)
            print(report['error'],file=sys.stderr)
        finally:
            if client:
                try:
                    client.cleanup()
                except Exception:
                    report['cleanupError']=traceback.format_exc()
            for key,value in saved_env.items():
                if value is None:
                    os.environ.pop(key,None)
                else:
                    os.environ[key]=value
            write_report(args.output,report)
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    sys.exit(main())
