# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Opt-in, numeric socket metadata for only a disposable browser's process tree.

No elevated privileges, packet payloads, DNS lookups, or unrelated process sockets.
Polling necessarily misses short-lived connections; this is not a packet capture.
"""
import subprocess
from threading import Event, Thread
from measurements import snapshot_processes


def parse_sockets(text):
    result=[]
    protocol=None
    for line in text.splitlines():
        if line.startswith('f'): protocol=None
        elif line.startswith('P'): protocol=line[1:]
        elif line.startswith('n') and protocol in ('TCP','UDP'):
            result.append((protocol,line[1:]))
    return result


class SocketSampler:
    def __init__(self, browser):
        self.browser=browser
        self.stop_event=Event()
        self.thread=Thread(target=self._run,daemon=True)
        self.endpoints={}
        self.samples=0
        self.errors=0
        self.phase='startup'

    def start(self): self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            runner=getattr(getattr(self.browser,'instance',None),'runner',None)
            handler=getattr(runner,'process_handler',None)
            pid=getattr(handler,'pid',None)
            if pid:
                try:
                    phase=self.phase
                    tree=snapshot_processes(pid)['processes']
                    if tree:
                        command=['/usr/sbin/lsof','-nP','-a','-p',','.join(str(p['pid']) for p in tree),'-i','-F','fPn']
                        sample=subprocess.run(command,text=True,capture_output=True,timeout=3)
                        if sample.returncode not in (0,1): raise RuntimeError('Socket enumeration failed')
                        self.samples+=1
                        for protocol,endpoint in set(parse_sockets(sample.stdout)):
                            key=(phase,protocol,endpoint)
                            self.endpoints[key]=self.endpoints.get(key,0)+1
                except (OSError,subprocess.SubprocessError,RuntimeError): self.errors+=1
            self.stop_event.wait(.2)

    def stop(self):
        self.stop_event.set();self.thread.join(timeout=5)
        if self.thread.is_alive(): raise RuntimeError('Socket sampler did not stop')
        return {'samples':self.samples,'errors':self.errors,
                'endpoints':[{'phase':phase,'protocol':protocol,'numericEndpoint':endpoint,'observations':count}
                             for (phase,protocol,endpoint),count in sorted(self.endpoints.items())],
                'limitations':['Starts at first observable test process PID, not before process creation',
                               '200ms polling plus process/lsof latency misses short-lived sockets',
                               'No DNS query capture, packet payloads, attribution of encrypted traffic, or reparented children']}
