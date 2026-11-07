"""Native UI driver for a dedicated Forge emulator and loopback HTTPS fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET


PACKAGE = 'org.forgebrowser.mobile.development'


class Driver:
    def __init__(self, adb, serial, output):
        if serial != 'emulator-5584':
            raise ValueError('Only the separately owned upload-fixture emulator is allowed')
        self.command = [str(adb), '-s', serial]
        self.output = Path(output)
        self.output.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.sequence = 0
        if self.adb('emu', 'avd', 'name').decode().splitlines()[0] != 'ForgeUpload20261107':
            raise ValueError('Wrong AVD; never use a personal profile')

    def adb(self, *args, timeout=60):
        return subprocess.check_output(self.command + list(args), stderr=subprocess.STDOUT, timeout=timeout)

    def hierarchy(self, label):
        self.sequence += 1
        remote = '/data/local/tmp/forge-upload-fixture-ui.xml'
        self.adb('shell', 'uiautomator', 'dump', remote)
        data = self.adb('shell', 'cat', remote)
        (self.output / f'{self.sequence:04d}-{label}.xml').write_bytes(data)
        return ET.fromstring(data)

    def wait(self, label, predicate, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            root = self.hierarchy(label)
            for node in root.iter('node'):
                if predicate(node):
                    return node
            if time.monotonic() >= deadline:
                (self.output / f'{self.sequence:04d}-{label}-failure.png').write_bytes(self.adb('exec-out', 'screencap', '-p'))
                raise TimeoutError('UI condition not reached: ' + label)
            time.sleep(0.5)

    def text(self, label, *values):
        expected = {value.casefold() for value in values}
        return self.wait(label, lambda node: node.get('text', '').casefold() in expected
            or node.get('content-desc', '').casefold() in expected)

    def tap(self, node):
        bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
        if bounds is None:
            raise ValueError('No native screen bounds')
        left, top, right, bottom = map(int, bounds.groups())
        self.adb('shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))

    def open(self, url):
        if not re.fullmatch(r'https://10\.0\.2\.2:[0-9]+/form\?case=(regular|private|cancel)', url):
            raise ValueError('Only the isolated loopback fixture is allowed')
        self.adb('shell', 'am', 'start', '-W', '-a', 'android.intent.action.VIEW', '-d', url,
            '-n', PACKAGE + '/org.forgebrowser.mobile.BrowserActivity')
        self.tap(self.text('confirm-external', 'Open link in new tab', 'Открыть ссылку в новой вкладке'))

    def regular_storage(self):
        result = {}
        for name in ('session-v1.json', 'library-v1.json'):
            path = 'no_backup/' + name
            exists = subprocess.run(self.command + ['shell', 'run-as', PACKAGE, 'test', '-f', path], capture_output=True).returncode == 0
            if not exists:
                result[name] = {'exists': False}
                continue
            data = self.adb('exec-out', 'run-as', PACKAGE, 'cat', path)
            result[name] = {'exists': True, 'sha256': hashlib.sha256(data).hexdigest(),
                'stat': self.adb('shell', 'run-as', PACKAGE, 'stat', '-c', '%i:%y:%s', path).decode().strip()}
        return result

    def private_mode(self):
        self.tap(self.wait('tabs-button', lambda node: node.get('content-desc', '').startswith(('Tabs (', 'Вкладки ('))))
        self.tap(self.text('private-group', 'Private tabs', 'Приватные вкладки'))
        self.tap(self.text('overview-done', 'Done', 'Готово'))

    def attach(self, cancel=False):
        self.tap(self.text('choose-file', 'Choose fixture'))
        self.tap(self.text('native-file-confirmation', 'Choose file', 'Выбрать файл'))
        # The system document picker must actually be foreground; no test
        # ActivityMonitor or synthetic result is accepted by this driver.
        self.wait('system-picker', lambda node: node.get('package') == 'com.google.android.documentsui')
        if cancel:
            self.adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
            self.text('cancelled-input', 'No fixture selected')
        else:
            self.tap(self.text('selected-system-file', 'forge-upload-fixture.txt'))
            self.text('file-input-change', 'Selected fixture: forge-upload-fixture.txt (28 bytes)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--expect-untrusted', action='store_true')
    parser.add_argument('--exercise-upload', action='store_true')
    parser.add_argument('--case', choices=('regular', 'private', 'cancel'), default='regular')
    parser.add_argument('--receipts', type=Path)
    args = parser.parse_args()
    if args.expect_untrusted and args.exercise_upload:
        parser.error('TLS rejection and upload acceptance must be separate runs')
    driver = Driver(args.adb, args.serial, args.output)
    if args.case == 'private':
        driver.private_mode()
    before = driver.regular_storage()
    receipts_before = args.receipts.read_text().splitlines() if args.receipts and args.receipts.exists() else []
    requests = args.receipts.with_name('requests.jsonl') if args.receipts else None
    posts_before = [json.loads(line) for line in requests.read_text().splitlines() if json.loads(line)['method'] == 'POST'] if requests and requests.exists() else []
    driver.open(args.url)
    if args.expect_untrusted:
        driver.text('tls-rejected', 'Secure connection failed. No certificate exception was added.',
            'Не удалось установить защищённое соединение. Исключение для сертификата не добавлено.')
        result = {'untrustedCertificateRejected': True}
    else:
        driver.text('fixture-loaded', 'Forge upload fixture')
        result = {'httpsFormLoaded': True, 'uploadTestComplete': False}
        if args.exercise_upload:
            if args.receipts is None or not args.url.endswith('case=' + args.case):
                raise ValueError('Upload acceptance requires matching case and local server receipts')
            driver.attach(cancel=args.case == 'cancel')
            if args.case != 'cancel':
                driver.tap(driver.text('submit-form', 'Submit fixture'))
                driver.text('server-accepted', 'Upload accepted')
            receipts_after = args.receipts.read_text().splitlines() if args.receipts.exists() else []
            posts_after = [json.loads(line) for line in requests.read_text().splitlines() if json.loads(line)['method'] == 'POST']
            expected = 0 if args.case == 'cancel' else 1
            after = driver.regular_storage()
            result.update({'case': args.case, 'receiptsBefore': len(receipts_before), 'receiptsAfter': len(receipts_after),
                'regularStorageBefore': before, 'regularStorageAfter': after, 'privateStorageUnchanged': before == after if args.case == 'private' else None})
            result.update({'postRequestsBefore': len(posts_before), 'postRequestsAfter': len(posts_after)})
            (args.output / 'observations.json').write_text(json.dumps(result, indent=2) + '\n')
            assert receipts_after[:len(receipts_before)] == receipts_before, 'Server evidence was overwritten'
            assert len(receipts_after) == len(receipts_before) + expected, 'Unexpected POST count'
            assert len(posts_after) == len(posts_before) + expected, 'Unexpected POST attempt, including rejected requests'
            if expected:
                receipt = json.loads(receipts_after[-1])
                assert receipt['case'] == args.case and receipt['method'] == 'POST'
                assert receipt['filename'] == 'forge-upload-fixture.txt' and receipt['bytes'] == 28
                assert receipt['sha256'] == 'd0c46ce52201c5fec50c206c491c1e46dc52c459582a50855aaba667aa586ca3'
            if args.case == 'private':
                assert before == after, 'Private upload changed regular file bytes/inode/mtime'
            result['uploadTestComplete'] = True
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
