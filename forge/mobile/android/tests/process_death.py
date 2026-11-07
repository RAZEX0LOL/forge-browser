import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET


PACKAGE = 'org.forgebrowser.mobile.development'
SESSION = 'no_backup/session-v1.json'


def main():
    parser = argparse.ArgumentParser(description='Test Forge process restart on an isolated Forge AVD.')
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'emulator-\d+', args.serial):
        parser.error('Only an explicitly selected emulator is supported, never a physical device.')

    def adb(*command, check=True, data=None):
        result = subprocess.run([args.adb, '-s', args.serial, *command], input=data,
                                capture_output=True, timeout=60)
        if check and result.returncode:
            raise RuntimeError('ADB command failed: ' + result.stderr.decode('utf-8', errors='replace'))
        return result.stdout.decode('utf-8')

    name = adb('emu', 'avd', 'name').splitlines()[0]
    if not name.startswith('forge-'):
        parser.error('Use a dedicated AVD whose name starts with forge-.')
    args.output.mkdir(parents=True, exist_ok=False)
    adb('shell', 'run-as', PACKAGE, 'id')
    adb('shell', 'run-as', PACKAGE, 'mkdir', '-p', 'no_backup')
    for suffix in ('.bak', '.new'):
        result = adb('shell', 'run-as', PACKAGE, 'sh', '-c',
                     f'"if test -e {SESSION}{suffix}; then echo exists; fi"')
        if result.strip():
            raise RuntimeError('Unfinished session write exists; refusing to alter it.')

    def read_session():
        return adb('shell', 'run-as', PACKAGE, 'cat', SESSION)

    def write_session(value):
        adb('shell', 'run-as', PACKAGE, 'sh', '-c', f'"cat > {SESSION}"', data=value.encode())

    def pid():
        return adb('shell', 'pidof', PACKAGE, check=False).strip()

    def stop():
        adb('shell', 'am', 'force-stop', PACKAGE)
        if pid():
            raise AssertionError('Application process survived force-stop.')

    def launch():
        adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/org.forgebrowser.mobile.BrowserActivity')
        current = pid()
        if not current:
            raise AssertionError('Application process did not start.')
        return current

    remote_xml = '/data/local/tmp/forge-process-test-' + uuid.uuid4().hex + '.xml'

    def hierarchy(label):
        adb('shell', 'uiautomator', 'dump', remote_xml)
        content = adb('shell', 'cat', remote_xml)
        (args.output / (label + '.xml')).write_text(content, encoding='utf-8')
        return ET.fromstring(content)

    def tap(node):
        bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
        if bounds is None:
            raise AssertionError('Missing native control bounds.')
        left, top, right, bottom = map(int, bounds.groups())
        adb('shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))

    def tabs_node(root, count):
        return next(node for node in root.iter('node')
                    if node.get('content-desc') in (f'Tabs ({count})', f'Вкладки ({count})'))

    stop()
    exists = adb('shell', 'run-as', PACKAGE, 'sh', '-c',
                 f'"if test -f {SESSION}; then echo exists; fi"').strip() == 'exists'
    original = read_session() if exists else None
    first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
    fixture = {'schemaVersion': 1, 'selectedID': second_id, 'tabs': [
        {'id': first_id, 'url': 'https://example.invalid/process-restore', 'title': 'Saved remote tab'},
        {'id': second_id, 'url': 'about:blank', 'title': ''}]}
    checks = []
    try:
        write_session(json.dumps(fixture))
        before_pid = launch()
        tap(tabs_node(hierarchy('before-add'), 2))
        dialog = hierarchy('tab-dialog')
        tap(next(node for node in dialog.iter('node')
                 if node.get('resource-id') == 'android:id/button1'
                 and node.get('text', '').casefold() in ('new tab', 'новая вкладка')))
        deadline = time.monotonic() + 30
        while True:
            saved = json.loads(read_session())
            if len(saved['tabs']) == 3 and saved['selectedID'] not in (first_id, second_id):
                break
            if time.monotonic() >= deadline:
                raise AssertionError('Native tab addition was not persisted.')
            time.sleep(0.5)
        tabs_node(hierarchy('after-add'), 3)
        stop()
        after_pid = launch()
        if before_pid == after_pid:
            raise AssertionError('Expected a different application process after restart.')
        tabs_node(hierarchy('after-process-restart'), 3)
        if json.loads(read_session()) != saved:
            raise AssertionError('URLs, titles, IDs or selection changed after process restart.')
        checks.append({'check': 'native-tab-edit-survives-force-stop', 'passed': True,
                       'beforePID': before_pid, 'afterPID': after_pid, 'tabs': 3})
        stop()
        saved['selectedID'] = first_id
        write_session(json.dumps(saved))
        remote_pid = launch()
        root = hierarchy('restored-remote-address')
        texts = [node.get('text', '') for node in root.iter('node')]
        if fixture['tabs'][0]['url'] not in texts:
            raise AssertionError('Saved remote address was not shown.')
        if not any('Tap Reload' in value or 'Нажмите «Обновить»' in value for value in texts):
            raise AssertionError('Remote tab did not remain in explicit-reload state.')
        if json.loads(read_session()) != saved:
            raise AssertionError('Cold restore changed the saved snapshot.')
        checks.append({'check': 'remote-address-awaits-explicit-reload', 'passed': True, 'pid': remote_pid})
        result = {'status': 'passed', 'checks': checks,
                  'scope': 'Force-stop/relaunch and native UI, not OS low-memory killing or packet capture.'}
        (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    finally:
        stop()
        if original is None:
            adb('shell', 'run-as', PACKAGE, 'rm', '-f', SESSION)
        else:
            write_session(original)
        adb('shell', 'rm', '-f', remote_xml)


if __name__ == '__main__':
    main()
