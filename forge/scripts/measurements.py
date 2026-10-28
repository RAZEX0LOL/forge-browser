# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Small dependency-free helpers for disposable-browser diagnostics."""
import json
import os
from pathlib import Path
import statistics
import subprocess


def write_report(path, data):
    """Replace a report atomically, including before a potentially fatal restart."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)


def parse_processes(text):
    processes = {}
    for line in text.splitlines():
        fields = line.split(None, 3)
        if len(fields) != 4:
            continue
        try:
            pid, parent, rss = map(int, fields[:3])
        except ValueError:
            continue
        if pid <= 0 or parent < 0 or rss < 0:
            continue
        processes[pid] = {'pid': pid, 'parent': parent, 'rssKiB': rss, 'executable': fields[3]}
    return processes


def process_tree(processes, root):
    """Only return the selected test process and its descendants, never other apps."""
    if root not in processes:
        return []
    selected = {root}
    while True:
        children = {pid for pid, value in processes.items() if value['parent'] in selected}
        if children <= selected:
            break
        selected.update(children)
    return [processes[pid] for pid in sorted(selected)]


def snapshot_processes(root):
    text = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,rss=,comm='], text=True)
    tree = process_tree(parse_processes(text), root)
    return {'rootPID': root, 'rootPresent': any(p['pid'] == root for p in tree),
            'processes': tree, 'sumRSSKiB': sum(p['rssKiB'] for p in tree)}


def summarize(values):
    if not values:
        raise ValueError('Cannot summarize an empty sample')
    return {'samples': len(values), 'min': min(values),
            'median': statistics.median(values), 'max': max(values)}
