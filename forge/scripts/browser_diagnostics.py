# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Capture native relaunch failures before Marionette removes its test profile."""
import json
import os
from pathlib import Path
import socket
import re
import signal
import subprocess
import sys

from marionette_driver.marionette import Marionette
from measurements import parse_processes, process_tree, write_report


def read_trace(path):
    records = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # The last append may have been interrupted.
    return records


class DiagnosticMarionette(Marionette):
    def __init__(self, *, diagnostic_directory, trace_directory, **kwargs):
        self.diagnostic_directory = Path(diagnostic_directory)
        self.diagnostic_directory.mkdir(parents=True, exist_ok=True)
        self.trace_path = Path(trace_directory) / 'native-launch.jsonl'
        self.test_binary = Path(kwargs['bin']).resolve()
        self.trace_supported = (sys.platform == 'darwin' and self.test_binary.name == 'forge' and
                                b'FORGE_LAUNCH_TRACE' in self.test_binary.read_bytes())
        self.verified_relaunches = []
        self.diagnostic_report = {'binary': str(self.test_binary), 'traceSupported': self.trace_supported,
                                  'verifiedRelaunches': self.verified_relaunches}
        previous = os.environ.get('FORGE_LAUNCH_TRACE')
        os.environ['FORGE_LAUNCH_TRACE'] = str(self.trace_path)
        try:
            super().__init__(**kwargs)
        finally:
            if previous is None:
                os.environ.pop('FORGE_LAUNCH_TRACE', None)
            else:
                os.environ['FORGE_LAUNCH_TRACE'] = previous

    def save_diagnostics(self):
        try:
            self.diagnostic_report['launches'] = read_trace(self.trace_path)
            write_report(self.diagnostic_directory / 'native-restarts.json', self.diagnostic_report)
        except OSError as error:
            self.diagnostic_report['diagnosticWriteError'] = str(error)

    def raise_for_port(self, *args, **kwargs):
        try:
            return super().raise_for_port(*args, **kwargs)
        except socket.timeout:
            # The driver's restart() calls cleanup before propagating this error.
            # Snapshot only PIDs from this run's private launcher trace, while alive.
            try:
                self.save_diagnostics()
                pids = sorted({int(record['pid']) for record in read_trace(self.trace_path)})
                candidates = []
                helpers = []
                if pids:
                    result = subprocess.run(['ps', '-axo', 'pid=,ppid=,rss=,comm='],
                                            capture_output=True, text=True, timeout=5, check=False)
                    rows = parse_processes(result.stdout)
                    allowed = {str(self.test_binary), str(self.test_binary.with_name('firefox'))}
                    candidates = [row for row in rows.values() if row['pid'] in pids and row['executable'] in allowed]
                    updater = str(self.test_binary.parent / 'updater.app/Contents/MacOS/org.mozilla.updater')
                    for process in rows.values():
                        if process['executable'] != updater:
                            continue
                        command = subprocess.check_output(['ps', '-p', str(process['pid']), '-o', 'args='], text=True, timeout=5)
                        wait_pid = re.search(r' --wait-pid (\d+)(?: |$)', command)
                        if wait_pid and int(wait_pid[1]) in pids:
                            helpers.extend(process_tree(rows, process['pid']))
                    candidates.extend(helpers)
                self.diagnostic_report['timeoutProcesses'] = candidates
                self.save_diagnostics()
                if sys.platform == 'darwin':
                    for process in candidates[-3:]:
                        sample = self.diagnostic_directory / f"native-timeout-{process['pid']}.sample"
                        subprocess.run(['sample', str(process['pid']), '1', '1', '-file', str(sample)],
                                       timeout=15, check=False, capture_output=True)
                # Only relaunch helpers tied to this private trace are ours to stop.
                # Prevent a timed-out helper later reopening a deleted test profile.
                for process in helpers:
                    try:
                        os.kill(process['pid'], signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                self.diagnostic_report['terminatedTestHelperPIDs'] = [process['pid'] for process in helpers]
                self.save_diagnostics()
            except Exception as error:
                self.diagnostic_report['diagnosticError'] = str(error)
                self.save_diagnostics()
            raise

    def restart(self, *args, **kwargs):
        result = super().restart(*args, **kwargs)
        if self.trace_supported and kwargs.get('in_app'):
            matching = [record for record in read_trace(self.trace_path)
                        if record.get('pid') == self.process_id and record.get('stage') == 'exec']
            if not matching or not matching[-1]['explicitProfile'] or not matching[-1]['restart']:
                self.save_diagnostics()
                raise AssertionError('Native restart did not pass through the expected isolated launcher')
            self.verified_relaunches.append(self.process_id)
            self.save_diagnostics()
        return result

    def cleanup(self):
        self.save_diagnostics()
        return super().cleanup()
