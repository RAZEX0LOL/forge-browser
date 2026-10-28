#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Sample post-startup HTTP channel attempts in a disposable browser profile.

Not a packet capture: DNS, non-HTTP sockets and early startup are out of scope.
Only host counts are recorded, never paths, queries, headers or request bodies.
Run using .venv-test/bin/python. No user profile is accessed.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from marionette_driver.marionette import Marionette
from socket_audit import SocketSampler
from measurements import write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--warm", action="store_true", help="Also sample after a real restart of the same disposable profile")
    parser.add_argument('--sockets',action='store_true',help='Sample numeric TCP/UDP metadata from startup (macOS lsof, no packet capture)')
    parser.add_argument('--bootstrap',action='store_true',help='Opt-in Forge host/DNS counters from first browser chrome bootstrap')
    parser.add_argument("--output", type=Path, default=Path("test-results/network-sample.json"))
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error("Sampling duration must be 1–120 seconds")
    class ControlHandler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def do_GET(self):
            self.send_response(204)
            self.send_header('Content-Length','0')
            self.end_headers()
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), ControlHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="forge-network-") as workspace:
        for variable, name in [("MOZ_APP_DATA", "app-data"), ("MOZ_LOCAL_APP_DATA", "local-app-data")]:
            directory = Path(workspace) / name
            directory.mkdir()
            os.environ[variable] = str(directory)
        browser = Marionette(bin=str(args.binary.resolve()), port=0, headless=True, workspace=workspace,
                             prefs={'forge.audit.network':args.bootstrap,'network.dns.notifyResolution':args.bootstrap},
                             app_args=["--remote-allow-system-access", "--no-remote"],
                             gecko_log=str(Path(workspace) / "gecko.log"))
        sampler=SocketSampler(browser) if args.sockets else None
        phases=[];bootstrap=[]
        report={'status':'running','binary':str(args.binary.resolve()),'phases':phases,'bootstrapHostCounters':bootstrap}
        write_report(args.output,report)
        if sampler: sampler.start()
        try:
            browser.start_session()
            browser.set_context("chrome")
            browser.timeout.script = args.seconds + 30
            profile=browser.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path;")
            for phase in (('initial','warm-restart') if args.warm else ('initial',)):
                if phase=='warm-restart':
                    if sampler: sampler.phase='warm-restart-startup'
                    browser.restart(in_app=True)
                    browser.set_context('chrome')
                    if browser.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path;") != profile:
                        raise RuntimeError('Network audit restart switched profile')
                if sampler: sampler.phase=phase
                if args.bootstrap:
                    state=browser.execute_script("return ChromeUtils.importESModule('chrome://browser/content/forge/NetworkAudit.sys.mjs').takeSnapshot();")
                    if not state['active']: raise RuntimeError('Bootstrap audit did not activate; sample invalid')
                    bootstrap.append({'phase':phase+'-before-driver-observation',**state})
                sample = browser.execute_async_script("""
                const done = arguments[arguments.length-1];
                const hosts = new Map();
                const controlURL = arguments[1];
                const dnsControlURL = controlURL.replace('127.0.0.1','localhost');
                let controlObserved = false;
                const observer = {observe(channel) {
                    try {
                        const http = channel.QueryInterface(Ci.nsIHttpChannel);
                         if ([controlURL,dnsControlURL].includes(http.URI.spec)) { controlObserved = true; return; }
                        const host = http.URI.asciiHost;
                        hosts.set(host,(hosts.get(host)||0)+1);
                    } catch {}
                }};
                Services.obs.addObserver(observer,'http-on-modify-request');
                fetch(controlURL, {cache:'no-store',credentials:'omit'}).catch(() => {});
                if(arguments[2]){fetch(dnsControlURL,{cache:'no-store',credentials:'omit'}).catch(()=>{});}
                BrowserCommands.openTab();
                setTimeout(() => {
                    Services.obs.removeObserver(observer,'http-on-modify-request');
                    done({hosts:Object.fromEntries(hosts),controlObserved});
                },arguments[0]*1000);
                """, script_args=[args.seconds, f"http://127.0.0.1:{server.server_port}/observer-control",args.bootstrap])
                if not sample["controlObserved"]:
                    raise RuntimeError("HTTP observer did not see the local control request; sample is invalid")
                phases.append({'phase':phase,'seconds':args.seconds,'hosts':sample['hosts'],'observerControlRequestSeen':True})
                if args.bootstrap:
                    state=browser.execute_script("return ChromeUtils.importESModule('chrome://browser/content/forge/NetworkAudit.sys.mjs').takeSnapshot();")
                    state['dnsLocalhostControlSeen']=bool(state['dnsResolutionRequests'].get('localhost'))
                    state['httpLocalControlSeen']=bool(state['httpHosts'].get('127.0.0.1'))
                    if not state['dnsLocalhostControlSeen'] or not state['httpLocalControlSeen']:
                        raise RuntimeError('Bootstrap DNS/HTTP positive controls failed')
                    bootstrap.append({'phase':phase+'-driver-observation',**state})
            hosts={}
            for phase in phases:
                for host,count in phase['hosts'].items():
                    hosts[host]=hosts.get(host,0)+count
            report = {"status":"passed","scope": "post-startup HTTP channel attempts; not all traffic", "seconds": args.seconds,
                      "binary": str(args.binary.resolve()), "hosts": hosts, "phases":phases, "observerControlRequestSeen": True,
                      "limitations": ["No early-startup capture", "No DNS or non-HTTP sockets", "New disposable profile only", "Host observation does not identify payloads or prove zero telemetry"]}
            if sampler:
                report['socketMetadata']=sampler.stop()
                report['limitations']=['HTTP observer starts after startup; socket polling starts at first observable PID',
                    'No DNS query capture; no packet capture; short-lived sockets may be missed',
                    'Fresh and same-session reused disposable profile only; not an old real-world profile',
                    'Marionette automation defaults can suppress upstream background services',
                    'Endpoint/host observations do not identify payloads or prove zero telemetry']
                if not report['socketMetadata']['samples']: raise RuntimeError('No socket samples collected')
                report['socketMetadata']['localHTTPControlSeen']=any(
                    f'->127.0.0.1:{server.server_port}' in row['numericEndpoint']
                    for row in report['socketMetadata']['endpoints'])
                if not report['socketMetadata']['localHTTPControlSeen']: raise RuntimeError('Socket sampler missed the local HTTP positive control')
            args.output.parent.mkdir(parents=True, exist_ok=True)
            if args.bootstrap:
                report['bootstrapHostCounters']=bootstrap
                report['limitations'].append('DNS counters describe Gecko resolution requests, including cache; not DNS packets or system resolver traffic')
            write_report(args.output,report)
            print(json.dumps(report, indent=2))
        except Exception as error:
            report.update(status='failed',error=str(error))
            write_report(args.output,report)
            raise
        finally:
            if sampler: sampler.stop()
            browser.cleanup()
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
