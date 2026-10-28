#!/usr/bin/env python3
"""Interleaved Forge/official Firefox/Zen local headless comparison, fresh profiles.

Not an equal-engine experiment: versions, product defaults and security policies
differ. No energy, GPU, cold-cache, long-duration or real-site speed claims.
"""
import argparse
import os
from pathlib import Path
import platform
import plistlib
import tempfile
import traceback
from benchmark_browser import run_sample
from measurements import write_report, summarize


def app_binary(app):
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    binary=app/'Contents/MacOS'/info['CFBundleExecutable']
    if not binary.is_file(): raise ValueError(f'Missing binary: {binary}')
    return binary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forge',type=Path,required=True)
    parser.add_argument('--firefox',type=Path,required=True)
    parser.add_argument('--zen',type=Path,required=True)
    parser.add_argument('--runs',type=int,default=3)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.runs<=10: parser.error('Use 1–10 runs')
    binaries={name:app_binary(getattr(args,name).resolve()) for name in ('forge','firefox','zen')}
    report={'status':'running','binaries':{name:str(path) for name,path in binaries.items()},
        'host':{'os':platform.platform(),'machine':platform.machine(),'logicalCPUs':os.cpu_count()},
        'method':'Rotate product order; fresh profile per run; normalize to one tab; one workload warmup + five iterations; then 1/10/50/200 blank tabs',
        'limitations':['Different Gecko versions and product defaults; not isolated shell overhead',
            'Headless; automation defaults may suppress background product services',
            'Launch timing includes automation; OS caches and other application load uncontrolled',
            'Tab memory is after the interactive workload, not a clean blank-tab baseline',
            'Zen structural zen-empty-tab is excluded from workload tab count but retained in process memory/nativeTabCount',
            'Summed RSS double-counts shared pages; not unique physical memory',
            'No energy/GPU/public-site or long-duration performance measurement'],
        'runs':[]}
    saved={key:os.environ.get(key) for key in ('MOZ_APP_DATA','MOZ_LOCAL_APP_DATA')}
    names=list(binaries)
    try:
        for run in range(args.runs):
            order=names[run%3:]+names[:run%3]
            for name in order:
                entry={'product':name,'run':run+1,'status':'running'};report['runs'].append(entry)
                write_report(args.output,report)
                with tempfile.TemporaryDirectory(prefix=f'forge-compare-{name}-') as workspace:
                    folder=Path(workspace)
                    for key in saved:
                        location=folder/key;location.mkdir();os.environ[key]=str(location)
                    run_sample(binaries[name],name=='forge',run+1,folder,entry,workload=True,normalize_tabs=True)
                write_report(args.output,report)
        report['summary']={}
        for name in names:
            entries=[entry for entry in report['runs'] if entry['product']==name]
            if len({(e['browser']['version'],e['browser']['buildID']) for e in entries})!=1:
                raise AssertionError(f'{name} build changed during comparison')
            report['summary'][name]={
                'version':entries[0]['browser']['version'],'buildID':entries[0]['browser']['buildID'],
                'automationLaunchToReadyMs':summarize([e['automationLaunchToReadyMs'] for e in entries]),
                'interactiveMedianMs':summarize([e['interactiveWorkload']['elapsedMs']['median'] for e in entries]),
                'tabs':{str(count):{'sumRSSMiB':summarize([s['medianSumRSSMiB'] for e in entries for s in e['tabSamples'] if s['tabs']==count]),
                    'createAndSettleMs':summarize([s['createAndSettleMs'] for e in entries for s in e['tabSamples'] if s['tabs']==count])}
                    for count in (1,10,50,200)}}
        report['status']='passed'
    except Exception:
        report.update(status='failed',error=traceback.format_exc());print(report['error'],flush=True)
    finally:
        for key,value in saved.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
        write_report(args.output,report)
    return 0 if report['status']=='passed' else 1


if __name__=='__main__': raise SystemExit(main())
