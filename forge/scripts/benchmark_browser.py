#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Synthetic headless baseline: same Gecko binary, Forge shell on/off, fresh profiles.

Does not flush OS caches, load real websites, measure energy, or compare with Zen.
Summed RSS double-counts shared pages; it is not unique physical memory usage.
"""
import argparse
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import traceback

from marionette_driver.marionette import Marionette
from measurements import snapshot_processes, summarize, write_report
from ui_wait import settle_ui
from workload_server import WorkloadServer
from marionette_driver import Wait, errors

PROJECT = Path(__file__).resolve().parents[1]


def wait_ready(client, shell):
    client.set_context('chrome')
    result = client.execute_async_script("""
        const shell=arguments[0],done=arguments[arguments.length-1];
        const ready=()=>gBrowserInit.delayedStartupFinished &&
            (!window.gZenStartup || window.gZenStartup.isReady) &&
            (!shell || document.documentElement.getAttribute('forge-ready')==='true');
        if(ready()){done(true);return;}
        let attempts=0;
        const timer=setInterval(()=>{
            if(ready()){clearInterval(timer);done(true);}
            else if(++attempts>=400){clearInterval(timer);done(false);}
        },50);
    """, script_args=[shell])
    if result is not True:
        raise AssertionError('Browser did not become ready within 20 seconds')
    active = client.execute_script("return document.documentElement.getAttribute('forge-ready')==='true';")
    if active != shell:
        raise AssertionError('Unexpected Forge shell state; comparison is invalid')


def run_sample(binary, shell, run, folder, entry, workload=False, normalize_tabs=False):
    client = None
    try:
        started = time.monotonic()
        client = Marionette(bin=str(binary), port=0, headless=True, workspace=str(folder),
            app_args=['--remote-allow-system-access', '--no-remote'],
            gecko_log=str(folder / 'gecko.log'),
            prefs={'forge.enabled': shell, 'browser.shell.checkDefaultBrowser': False,
                   'browser.startup.page': 0, 'browser.startup.homepage': 'about:blank'})
        client.start_session()
        client.timeout.script = 90
        wait_ready(client, shell)
        entry['automationLaunchToReadyMs'] = round((time.monotonic() - started) * 1000, 2)
        entry['browser'] = client.execute_script("""
            const info=Services.startup.getStartupInfo();
            return {version:Services.appinfo.version,buildID:Services.appinfo.appBuildID,
                pid:Services.appinfo.processID,
                startupFromProcessMs:Object.fromEntries(Object.entries(info)
                    .filter(([,value])=>value instanceof Date)
                    .map(([key,value])=>[key,value-info.process]))};
        """)
        if normalize_tabs:
            entry['initialTabCount']=client.execute_script('return gBrowser.tabs.length;')
            client.set_context('content')
            previous_handles=set(client.window_handles)
            client.set_context('chrome')
            client.execute_script("""
                const keep=gBrowser.addTrustedTab('about:blank');gBrowser.selectedTab=keep;
                gBrowser.removeTabs(Array.from(gBrowser.tabs).filter(tab=>tab!==keep && !tab.hasAttribute('zen-empty-tab')),{animate:false});
            """)
            settle_ui(client)
            client.set_context('content')
            client.switch_to_window(next(handle for handle in client.window_handles if handle not in previous_handles))
            client.set_context('chrome')
        if workload:
            with WorkloadServer() as server:
                client.set_context('content')
                client.navigate(server.url)
                Wait(client,timeout=15,ignored_exceptions=(errors.JavascriptException,)).until(
                    lambda c:c.execute_script('return !!window.wrappedJSObject.workloadReady;'))
                times=[]
                for iteration in range(6):
                    result=client.execute_async_script("""
                        const done=arguments[arguments.length-1];window.wrappedJSObject.runWorkload().then(done,error=>done({error:String(error)}));
                    """)
                    if result.get('rows')!=1000 or not result.get('persistent'): raise AssertionError(f'Invalid workload result: {result}')
                    if iteration: times.append(result['elapsedMs'])
                entry['interactiveWorkload']={'iterationsAfterWarmup':5,'elapsedMs':summarize(times),
                    'processSnapshot':snapshot_processes(entry['browser']['pid'])}
                client.navigate('about:blank')
                client.set_context('chrome')
        entry['tabSamples'] = []
        for count in (1, 10, 50, 200):
            client.execute_script("""
                window.__forgeBenchmarkStart=performance.now();
                const target=arguments[0];
                const counted=()=>Array.from(gBrowser.tabs).filter(tab=>!tab.hasAttribute('zen-empty-tab'));
                while(counted().length<target){gBrowser.addTrustedTab('about:blank');}
                gBrowser.selectedTab=gBrowser.tabs[gBrowser.tabs.length-1];
            """, script_args=[count])
            settle_ui(client)
            elapsed = client.execute_script('return performance.now()-__forgeBenchmarkStart;')
            actual = client.execute_script("return Array.from(gBrowser.tabs).filter(tab=>!tab.hasAttribute('zen-empty-tab')).length;")
            if actual != count:
                diagnostic=client.execute_script("return Array.from(gBrowser.tabs,tab=>({url:tab.linkedBrowser.currentURI.spec,attributes:Array.from(tab.attributes,attr=>[attr.name,attr.value])}));")
                raise AssertionError(f'Expected {count} tabs, got {actual}: {diagnostic}')
            # Defined settling period, then three RSS samples; no forced GC or cache eviction.
            time.sleep(1)
            snapshots = []
            for index in range(3):
                if index:
                    time.sleep(.25)
                snapshot = snapshot_processes(entry['browser']['pid'])
                if not snapshot['rootPresent']:
                    raise AssertionError('Test browser exited during memory sampling')
                snapshots.append(snapshot)
            sample = {'tabs': count, 'createAndSettleMs': round(elapsed, 2),
                      'nativeTabCount':client.execute_script('return gBrowser.tabs.length;'),
                      'medianSumRSSMiB': round(statistics.median(s['sumRSSKiB'] for s in snapshots) / 1024, 2),
                      'rssSamples': snapshots}
            entry['tabSamples'].append(sample)
            print(f"SAMPLE shell={'on' if shell else 'off'} run={run} tabs={count}: "
                  f"{sample['medianSumRSSMiB']} MiB summed RSS", flush=True)
        entry['status'] = 'passed'
    except Exception:
        entry['status'] = 'failed'
        log = folder / 'gecko.log'
        if log.exists():
            entry['geckoLogTail'] = log.read_text(errors='replace')[-16000:]
        raise
    finally:
        if client:
            client.cleanup()


def aggregate(runs):
    summary = {}
    for mode in ('on', 'off'):
        selected = [entry for entry in runs if entry['shell'] == mode and entry.get('status') == 'passed']
        if not selected:
            continue
        summary[mode] = {
            'automationLaunchToReadyMs': summarize([entry['automationLaunchToReadyMs'] for entry in selected]),
            'tabs': {str(count): {
                'medianSumRSSMiB': summarize([sample['medianSumRSSMiB'] for entry in selected for sample in entry['tabSamples'] if sample['tabs'] == count]),
                'createAndSettleMs': summarize([sample['createAndSettleMs'] for entry in selected for sample in entry['tabSamples'] if sample['tabs'] == count]),
            } for count in (1, 10, 50, 200)},
        }
        workloads=[entry['interactiveWorkload']['elapsedMs']['median'] for entry in selected if 'interactiveWorkload' in entry]
        if workloads: summary[mode]['interactiveWorkloadMedianMs']=summarize(workloads)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--shell', choices=('on', 'off', 'both'), default='both')
    parser.add_argument('--workload',action='store_true',help='Also measure a local 1000-row DOM/filter/canvas/history workload')
    parser.add_argument('--output', type=Path, default=PROJECT / 'test-results/performance.json')
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file() or not 1 <= args.runs <= 10:
        parser.error('Need an existing binary and 1–10 runs per mode')
    report = {'status': 'running', 'binary': str(binary),
              'host': {'os': platform.platform(), 'machine': platform.machine(), 'logicalCPUs': os.cpu_count()},
              'method': 'Interleaved modes, fresh disposable profiles, headless, local about:blank tabs, no forced GC',
              'limitations': ['Not OS-cache-cold startup; automation timing includes driver/session setup',
                              'Summed process RSS double-counts shared pages and excludes reparented processes',
                               'Controlled local workload and blank tabs; not public-site performance or energy measurement',
                              'Same binary with shell toggled, not Firefox release or Zen comparison',
                              'Other running applications and OS memory pressure are uncontrolled'],
              'runs': []}
    write_report(args.output, report)
    keys = ('MOZ_APP_DATA', 'MOZ_LOCAL_APP_DATA')
    saved = {key: os.environ.get(key) for key in keys}
    try:
        for run in range(1, args.runs + 1):
            modes = ('on', 'off') if args.shell == 'both' else (args.shell,)
            if run % 2 == 0:
                modes = tuple(reversed(modes))
            for mode in modes:
                entry = {'run': run, 'shell': mode, 'status': 'running'}
                report['runs'].append(entry)
                write_report(args.output, report)
                with tempfile.TemporaryDirectory(prefix='forge-benchmark-') as workspace:
                    folder = Path(workspace)
                    for key in keys:
                        location = folder / key
                        location.mkdir()
                        os.environ[key] = str(location)
                    run_sample(binary, mode == 'on', run, folder, entry, args.workload)
                write_report(args.output, report)
        if sys.platform == 'darwin' and binary.name == 'forge':
            subprocess.run(['codesign', '--verify', '--deep', '--strict', str(binary.parents[2])], check=True)
        builds = {(entry['browser']['version'], entry['browser']['buildID']) for entry in report['runs']}
        if len(builds) != 1:
            raise AssertionError('Browser build changed between samples; comparison is invalid')
        report['summary'] = aggregate(report['runs'])
        report['status'] = 'passed'
    except Exception:
        report.update(status='failed', error=traceback.format_exc())
        print(report['error'], file=sys.stderr)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        write_report(args.output, report)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
