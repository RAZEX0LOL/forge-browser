import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET


PACKAGE = 'org.forgebrowser.mobile.development'
URL = 'https://razex.shop/forge/SHA256SUMS'
EXPECTED_SHA256 = '030afac07742330996331a1a352852370d20f5f304107d5190264a0c5a45c681'


def main():
    parser = argparse.ArgumentParser(description='Exercise the native download confirmation and Android file picker.')
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'emulator-\d+', args.serial):
        parser.error('An explicitly selected emulator is required.')

    def adb(*command):
        result = subprocess.run([args.adb, '-s', args.serial, *command], capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
        return result.stdout

    if not adb('emu', 'avd', 'name').decode().splitlines()[0].startswith('forge-'):
        parser.error('Use a dedicated Forge AVD, never a personal profile.')
    args.output.mkdir(parents=True, exist_ok=False)
    remote = '/data/local/tmp/forge-download-ui-' + uuid.uuid4().hex + '.xml'
    export_name = 'forge-download-test-' + uuid.uuid4().hex + '.txt'
    original = None
    exists = adb('shell', 'run-as', PACKAGE, 'sh', '-c',
                 '"if test -f no_backup/session-v1.json; then echo exists; fi"').strip() == b'exists'
    if exists:
        original = adb('shell', 'run-as', PACKAGE, 'cat', 'no_backup/session-v1.json')

    def hierarchy(label):
        adb('shell', 'uiautomator', 'dump', remote)
        data = adb('shell', 'cat', remote)
        (args.output / (label + '.xml')).write_bytes(data)
        return ET.fromstring(data)

    def wait_for(label, match, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            root = hierarchy(label)
            for node in root.iter('node'):
                if match(node):
                    return node
            time.sleep(1)
        raise TimeoutError('Native UI control not found: ' + label)

    def tap(node):
        bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
        if bounds is None:
            raise AssertionError('Control has no screen bounds.')
        left, top, right, bottom = map(int, bounds.groups())
        adb('shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))

    try:
        adb('shell', 'am', 'force-stop', PACKAGE)
        adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/org.forgebrowser.mobile.BrowserActivity')
        field = wait_for('address', lambda n: n.get('class') == 'android.widget.EditText')
        tap(field)
        adb('shell', 'input', 'keycombination', '113', '29')
        adb('shell', 'input', 'keyevent', 'KEYCODE_DEL')
        adb('shell', 'input', 'text', URL)
        tap(wait_for('go', lambda n: n.get('text', '').casefold() in ('go', 'перейти')))
        confirm = wait_for('confirm', lambda n: n.get('content-desc') in ('Download', 'Скачать'))
        tap(confirm)
        ready = wait_for('ready', lambda n: n.get('content-desc') in ('Save file', 'Сохранить файл'))
        tap(ready)
        filename = wait_for('picker', lambda n: n.get('class') == 'android.widget.EditText'
                            and n.get('package') != PACKAGE)
        tap(filename)
        adb('shell', 'input', 'keycombination', '113', '29')
        adb('shell', 'input', 'keyevent', 'KEYCODE_DEL')
        adb('shell', 'input', 'text', export_name)
        tap(wait_for('picker-save', lambda n: n.get('package') != PACKAGE
                     and n.get('text', '').casefold() in ('save', 'сохранить')))
        wait_for('saved', lambda n: 'File saved. It was not opened.' in n.get('text', '')
                 or 'Файл сохранён. Автоматическое открытие не выполнялось.' in n.get('text', ''))
        data = adb('exec-out', 'cat', '/sdcard/Download/' + export_name)
        if len(data) != 1266 or hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
            raise AssertionError('Exported file does not match the pinned public fixture.')
        result = {'status': 'passed', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                  'checks': ['native-confirmation', 'engine-response-stream', 'system-create-document', 'exported-bytes']}
        (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    finally:
        adb('shell', 'am', 'force-stop', PACKAGE)
        if original is not None:
            subprocess.run([args.adb, '-s', args.serial, 'shell', 'run-as', PACKAGE, 'sh', '-c',
                            '"cat > no_backup/session-v1.json"'], input=original, check=True)
        else:
            adb('shell', 'run-as', PACKAGE, 'rm', '-f', 'no_backup/session-v1.json')
        adb('shell', 'rm', '-f', remote, '/sdcard/Download/' + export_name)


if __name__ == '__main__':
    main()
