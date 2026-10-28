#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Exercise the actual Firefox chrome in a disposable, headless profile."""

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess

from browser_diagnostics import DiagnosticMarionette
from surface_checks import run_surface_checks
from window_checks import run_window_checks
from appearance_checks import run_appearance_checks
from ui_wait import settle_ui
from motion_checks import run_motion_checks
from feature_checks import run_feature_checks
from native_checks import run_native_checks
from audit_checks import run_audit_checks
from editor_checks import run_editor_checks
from devtools_checks import run_devtools_checks
from keyboard_checks import run_keyboard_checks
from transfer_checks import run_transfer_checks
from workflow_checks import run_workflow_checks
from accessibility_checks import run_accessibility_checks
from native_locale_checks import run_native_locale_checks
from mac_accessibility_checks import run_mac_accessibility_checks

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        parser.error(f"Browser executable not found: {binary}")
    results = PROJECT / "test-results"
    results.mkdir(exist_ok=True)
    checks = []
    client = None
    # No installed Firefox profile is read or modified.
    with tempfile.TemporaryDirectory(prefix="forge-smoke-") as workspace:
        try:
            # Isolate Firefox's profile registry as well as the profile itself.
            # This also avoids the macOS FSFindFolder dependency in headless runs.
            for variable, name in [("MOZ_APP_DATA", "app-data"),
                                   ("MOZ_LOCAL_APP_DATA", "local-app-data")]:
                folder = Path(workspace) / name
                folder.mkdir()
                os.environ[variable] = str(folder)
            client = DiagnosticMarionette(
                diagnostic_directory=results/'smoke-native',
                trace_directory=workspace,
                bin=str(binary), port=0, headless=True, workspace=workspace,
                app_args=["--remote-allow-system-access", "--no-remote"],
                gecko_log=str(results / "gecko.log"),
                prefs={"browser.shell.checkDefaultBrowser": False,
                       "browser.startup.homepage": "about:blank",
                       "browser.startup.page": 0},
            )
            client.start_session()
            client.set_context("chrome")
            client.timeout.script = 90
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const win = Services.wm.getMostRecentWindow('navigator:browser');
                if (win.gBrowserInit.delayedStartupFinished) { done(true); }
                else { win.delayedStartupPromise.then(() => done(true)); }
            """)

            def check(name, script):
                result = client.execute_script(script)
                if result is not True:
                    raise AssertionError(f"{name}: {result!r}")
                checks.append(name)
                print(f"PASS {name}", flush=True)

            check("Forge chrome initialized", """
                return !!document.getElementById('forge-command-button') &&
                    !!document.getElementById('forge-palette') &&
                    !!document.getElementById('forge-editor');
            """)
            check('Network instrumentation is inactive in a normal disposable profile', """
                const state=ChromeUtils.importESModule('chrome://browser/content/forge/NetworkAudit.sys.mjs').takeSnapshot();
                return !state.active && Object.keys(state.httpHosts).length===0 && Object.keys(state.dnsResolutionRequests).length===0;
            """)
            locked_prefs = json.loads((PROJECT / "privacy.json").read_text())["locked"]
            privacy_result = client.execute_script("""
                const expected = arguments[0];
                const branch = Services.prefs.getDefaultBranch('');
                const failures = [];
                for (const [name, value] of Object.entries(expected)) {
                    const method = typeof value === 'boolean' ? 'getBoolPref' :
                        typeof value === 'number' ? 'getIntPref' : 'getStringPref';
                    if (branch[method](name) !== value || Services.prefs[method](name) !== value ||
                        !Services.prefs.prefIsLocked(name)) { failures.push(name); }
                }
                return failures;
            """, script_args=[locked_prefs])
            if privacy_result:
                raise AssertionError(f"Privacy defaults/locks failed: {privacy_result}")
            checks.append(f"All {len(locked_prefs)} privacy defaults and locks active")
            print(f"PASS All {len(locked_prefs)} privacy defaults and locks active", flush=True)
            check("Packaged anti-promotion policies active", """
                const policies = Services.policies.getActivePolicies();
                return policies.DisableTelemetry === true && policies.DisableFirefoxStudies === true &&
                    policies.UserMessaging?.ExtensionRecommendations === false &&
                    policies.FirefoxHome?.SponsoredTopSites === false;
            """)
            check("User preference cannot re-enable telemetry upload", """
                const name = 'datareporting.healthreport.uploadEnabled';
                try { Services.prefs.setBoolPref(name, true); } catch {}
                return Services.prefs.getBoolPref(name) === false && Services.prefs.prefIsLocked(name);
            """)
            check("Native security controls preserved", """
                return !!document.getElementById('identity-box') &&
                    Services.prefs.getBoolPref('browser.safebrowsing.phishing.enabled') &&
                    Services.prefs.getBoolPref('browser.safebrowsing.malware.enabled');
            """)
            check("Redesigned shell and vertical tab view mounted", """
                return document.documentElement.getAttribute('forge-shell') === 'true' &&
                    !!document.getElementById('forge-rail') &&
                    document.querySelectorAll('.forge-tab').length === gBrowser.tabs.length;
            """)
            initial_handles = set(client.window_handles)
            client.execute_script("document.getElementById('forge-new-tab').click();")
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const target = gBrowser.selectedBrowser;
                function ready() {
                    return target.currentURI.spec === 'chrome://browser/content/forge/start.html' &&
                        document.querySelectorAll('.forge-tab').length === gBrowser.tabs.length;
                }
                if (ready()) { done(true); }
                else {
                    const timer = setInterval(() => { if (ready()) { clearInterval(timer); done(true); } }, 50);
                }
            """)
            check("New tab opens local Forge dashboard", """
                return gBrowser.selectedBrowser.currentURI.spec === 'chrome://browser/content/forge/start.html' &&
                    document.querySelectorAll('.forge-tab').length === gBrowser.tabs.length;
            """)
            client.set_context("content")
            new_handle = next(handle for handle in client.window_handles if handle not in initial_handles)
            client.switch_to_window(new_handle)
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const settle = () => requestAnimationFrame(() => requestAnimationFrame(() => done(true)));
                if (document.readyState === 'complete') { settle(); }
                else { addEventListener('load', settle, { once: true }); }
            """)
            dashboard_state = client.execute_script("""
                return { title: document.title, scripts: document.scripts.length,
                    remoteResources: performance.getEntriesByType('resource')
                        .filter(item => /^https?:/.test(item.name)).map(item => item.name) };
            """)
            if dashboard_state != {"title": "Forge — Новая вкладка", "scripts": 0, "remoteResources": []}:
                raise AssertionError(f"Dashboard passive resources: {dashboard_state}")
            checks.append("Dashboard has no scripts or remote passive resources")
            print("PASS Dashboard has no scripts or remote passive resources", flush=True)
            check('Start page actor applies Fluent without author scripts or replacing SVG controls', """
                return document.documentElement.getAttribute('data-forge-localized')==='true' &&
                    document.querySelector('h1').textContent==='С чего начнём?' &&
                    document.querySelector('button[type="submit"] svg')!==null &&
                    document.querySelector('#query').getAttribute('placeholder')==='Поиск в интернете';
            """)
            client.set_context("chrome")
            settle_ui(client)
            (results / "shell.png").write_bytes(base64.b64decode(client.screenshot()))
            check("Vertical tabs select native tabs", """
                document.querySelector('.forge-tab-select').click();
                return gBrowser.selectedTab === gBrowser.tabs[0];
            """)
            client.execute_script("document.querySelectorAll('.forge-tab-close')[1].click();")
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const timer = setInterval(() => {
                    if (gBrowser.tabs.length === 1 && document.querySelectorAll('.forge-tab').length === 1) {
                        clearInterval(timer); done(true);
                    }
                }, 50);
            """)
            check("Vertical tab close updates native tab store", """
                return gBrowser.tabs.length === 1 && document.querySelectorAll('.forge-tab').length === 1;
            """)
            check("Sidebar search opens command palette", """
                document.querySelector('.forge-launcher').click();
                return document.getElementById('forge-palette').open;
            """)
            check("Search filters commands", """
                const input = document.querySelector('#forge-palette input');
                input.value = 'network';
                input.dispatchEvent(new Event('input', { bubbles: true }));
                const rows = document.querySelectorAll('.forge-result');
                return rows.length === 1 && rows[0].textContent === 'Сетевые запросы';
            """)
            check("Customization editor opens", """
                const input = document.querySelector('#forge-palette input');
                input.value = 'theme';
                input.dispatchEvent(new Event('input', { bubbles: true }));
                document.querySelector('.forge-result').click();
                return document.getElementById('forge-editor').open &&
                    !document.getElementById('forge-palette').open;
            """)
            check("Theme persists to prefs and applies", """
                const editor = document.getElementById('forge-editor');
                editor.querySelector('input[type=color]').value = '#33aaff';
                editor.querySelector('input[type=color]').dispatchEvent(new Event('input',{bubbles:true}));
                editor.querySelector('input[type=range]').value = '18';
                editor.querySelector('[data-setting="density"]').value = 'compact';
                editor.querySelector('#forge-theme-save').click();
                const theme = JSON.parse(Services.prefs.getStringPref('forge.theme'));
                return theme.accent === '#33aaff' && theme.radius === 18 &&
                    theme.density === 'compact' &&
                    document.documentElement.style.getPropertyValue('--forge-accent') === '#33aaff';
            """)
            check("Custom CSS requires explicit enable", """
                Services.prefs.setStringPref('forge.customCSS', '#nav-bar { --forge-smoke: 1; background-color: rgb(1, 2, 3) !important; }');
                return document.getElementById('forge-user-style').textContent === '';
            """)
            check("Custom CSS enable and disable", """
                Services.prefs.setBoolPref('forge.customCSS.enabled', true);
                const applied = document.getElementById('forge-user-style').textContent.includes('--forge-smoke') &&
                    getComputedStyle(document.getElementById('nav-bar')).backgroundColor === 'rgb(1, 2, 3)';
                Services.prefs.setBoolPref('forge.customCSS.enabled', false);
                return applied && document.getElementById('forge-user-style').textContent === '';
            """)
            check("Palette keyboard command registered", """
                const key = document.getElementById('forge-command-key');
                key.dispatchEvent(new Event('command', { bubbles: true }));
                return key.getAttribute('modifiers') === 'accel,shift,alt' &&
                    document.getElementById('forge-palette').open;
            """)
            settle_ui(client)
            (results / "palette.png").write_bytes(base64.b64decode(client.screenshot()))
            # Drive an actual DevTools command, not just check its label.
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const input = document.querySelector('#forge-palette input');
                input.value = 'network';
                input.dispatchEvent(new Event('input', { bubbles: true }));
                const { require } = ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
                const { gDevTools } = require('devtools/client/framework/devtools');
                gDevTools.once('toolbox-ready', () => done(true));
                document.querySelector('.forge-result').click();
            """)
            check("Network Monitor opened for selected tab", """
                const { require } = ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
                const { gDevTools } = require('devtools/client/framework/devtools');
                const toolbox = gDevTools.getToolboxForTab(gBrowser.selectedTab);
                return toolbox?.currentToolId === 'netmonitor';
            """)
            run_surface_checks(client, results, checks)
            run_window_checks(client, results, checks)
            run_appearance_checks(client, results, checks)
            run_motion_checks(client, results, checks)
            run_feature_checks(client, results, checks)
            run_native_checks(client, results, checks)
            run_devtools_checks(client, results, checks)
            run_keyboard_checks(client, results, checks)
            run_transfer_checks(client, results, checks)
            run_workflow_checks(client, results, checks)
            run_accessibility_checks(client, results, checks)
            if sys.platform=='darwin':
                run_mac_accessibility_checks(client,results,checks)
            audit_failures=run_audit_checks(client,results,checks)
            if audit_failures:
                raise AssertionError(f"Extended UI audit failed: {audit_failures}")
            editor_failures=run_editor_checks(client,results,checks)
            if editor_failures:
                raise AssertionError(f"Appearance editor audit failed: {editor_failures}")
            client.set_context('chrome')
            native_locale=client.execute_script("return Services.prefs.getDefaultBranch('').getBoolPref('forge.locale.followApp',false);")
            if native_locale:
                run_native_locale_checks(client,results,checks)
            if client.trace_supported:
                if len(client.verified_relaunches) != (5 if native_locale else 2):
                    raise AssertionError('Unexpected verified native launcher restart count')
                checks.append('All native restarts pass through the expected isolated launcher')
            client.cleanup()
            client=None
            if sys.platform == 'darwin' and binary.name == 'forge':
                subprocess.run(['codesign','--verify','--deep','--strict',str(binary.parents[2])],check=True)
                checks.append('macOS app resource signature stays valid after launch and shutdown')
            report = {"passed": checks, "binary": str(binary), "status": "passed"}
            (results / "smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            print(f"Passed {len(checks)} browser integration checks.")
            return 0
        except Exception as error:
            if client and client.session:
                try:
                    client.set_context("chrome")
                    (results / "failure.png").write_bytes(base64.b64decode(client.screenshot()))
                except Exception:
                    pass
            (results / "smoke.json").write_text(json.dumps({
                "status": "failed", "passed": checks, "error": str(error),
                "binary": str(binary),
            }, ensure_ascii=False, indent=2) + "\n")
            print(f"FAIL {error}", file=sys.stderr)
            return 1
        finally:
            if client:
                client.cleanup()


if __name__ == "__main__":
    sys.exit(main())
