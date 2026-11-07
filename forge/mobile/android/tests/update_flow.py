"""Real updater/OS installer UI acceptance on one explicitly owned emulator only."""
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
    def __init__(self, adb, output):
        self.command = [str(adb), '-s', 'emulator-5588']
        self.output = output
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.sequence = 0
        assert self.adb('emu', 'avd', 'name').decode().splitlines()[0] == 'ForgeUpdatesFlow20261107'

    def adb(self, *args, timeout=90):
        return subprocess.check_output(self.command + list(args), stderr=subprocess.STDOUT, timeout=timeout)

    def hierarchy(self, label):
        self.sequence += 1
        path = '/data/local/tmp/forge-update-ui.xml'
        self.adb('shell', 'uiautomator', 'dump', path)
        data = self.adb('shell', 'cat', path)
        (self.output / f'{self.sequence:04d}-{label}.xml').write_bytes(data)
        return ET.fromstring(data)

    def wait(self, label, predicate, timeout=30):
        deadline = time.monotonic() + timeout
        while True:
            for node in self.hierarchy(label).iter('node'):
                if predicate(node):
                    return node
            if time.monotonic() >= deadline:
                (self.output / f'{self.sequence:04d}-failed.png').write_bytes(self.adb('exec-out', 'screencap', '-p'))
                raise TimeoutError(label)
            time.sleep(1)

    def text(self, label, *values, timeout=30):
        expected = {value.casefold() for value in values}
        return self.wait(label, lambda node: node.get('text', '').casefold() in expected
                         or node.get('content-desc', '').casefold() in expected, timeout)

    def tap(self, node):
        bounds = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.get('bounds', ''))
        assert bounds
        left, top, right, bottom = map(int, bounds.groups())
        self.adb('shell', 'input', 'tap', str((left + right) // 2), str((top + bottom) // 2))

    def check(self):
        self.tap(self.text('menu', 'Menu', 'Меню'))
        self.tap(self.text('updates', 'Forge updates', 'Обновления Forge'))
        self.tap(self.text('consent', 'Check now', 'Проверить'))

    def version(self):
        text = self.adb('shell', 'dumpsys', 'package', PACKAGE).decode()
        return int(re.search(r'versionCode=(\d+)', text).group(1))

    def snapshot(self):
        result = {}
        for name in ('files/update-preservation-fixture.txt', 'no_backup/session-v1.json', 'no_backup/library-v1.json'):
            check = subprocess.run(self.command + ['shell', 'run-as', PACKAGE, 'test', '-f', name], capture_output=True)
            if check.returncode == 0:
                data = self.adb('exec-out', 'run-as', PACKAGE, 'cat', name)
                result[name] = hashlib.sha256(data).hexdigest()
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stage', required=True, choices=('bootstrap', 'prepare', 'install'))
    parser.add_argument('--seed-apk', type=Path)
    args = parser.parse_args()
    driver = Driver(args.adb, args.output)
    if args.stage in ('bootstrap', 'prepare'):
        assert args.seed_apk and args.seed_apk.is_file()
        driver.adb('install', '-r', str(args.seed_apk), timeout=180)
        assert driver.version() == 1
        driver.adb('shell', 'run-as', PACKAGE, 'mkdir', '-p', 'files')
        subprocess.run(driver.command + ['shell', 'run-as', PACKAGE, 'sh', '-c',
            '"cat > files/update-preservation-fixture.txt"'], input=b'Owned emulator update-preservation fixture\x00\xff\n', check=True)
        driver.adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/org.forgebrowser.mobile.BrowserActivity')
        if args.stage == 'bootstrap':
            # Run only before first publication, when the production endpoint is genuinely absent.
            driver.check()
            driver.wait('missing-feed-fails-closed', lambda node: node.get('text', '').startswith(
                ('Update could not be verified', 'Не удалось проверить')), timeout=60)
        assert driver.version() == 1
        summary = {'missingFeedRejected': args.stage == 'bootstrap', 'versionUnchanged': 1, 'snapshot': driver.snapshot()}
    else:
        assert driver.version() == 1
        # Use the real OS permission UI, not appops/root or an installer bypass.
        driver.adb('shell', 'am', 'start', '-W', '-a', 'android.settings.MANAGE_UNKNOWN_APP_SOURCES', '-d', 'package:' + PACKAGE)
        switch = driver.wait('os-install-source-setting', lambda node: node.get('class') == 'android.widget.Switch')
        assert switch.get('checked') == 'false', 'Permission must start denied'
        driver.tap(switch)
        driver.wait('os-install-source-enabled', lambda node: node.get('class') == 'android.widget.Switch' and node.get('checked') == 'true')
        driver.adb('shell', 'am', 'start', '-W', '-n', PACKAGE + '/org.forgebrowser.mobile.BrowserActivity')
        # Dismiss the preserved missing-feed message from bootstrap if present.
        tree = driver.hierarchy('initial-app')
        ok = next((n for n in tree.iter('node') if n.get('text', '').casefold() in ('ok', 'ок')), None)
        if ok is not None:
            driver.tap(ok)
        before = driver.snapshot()
        driver.check()
        driver.tap(driver.text('offer-download', 'Download', 'Скачать', timeout=60))
        driver.tap(driver.text('verified-install', 'Open installer', 'Открыть установщик', timeout=1200))
        install = driver.text('os-installer-consent', 'Update', 'Обновить', timeout=60)
        assert install.get('package') != PACKAGE, 'Must be the real OS installer'
        driver.tap(install)
        driver.text('os-install-complete', 'Done', 'Готово', timeout=120)
        assert driver.version() == 2
        after = driver.snapshot()
        assert before and before == after, (before, after)
        summary = {'systemInstallerConfirmed': True, 'versionBefore': 1, 'versionAfter': 2,
                   'dataHashesUnchanged': after, 'seedIsTestOnly': True, 'physicalDevice': False}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
