# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
import base64


def run_window_checks(client, results, passed):
    def check(name, script):
        value = client.execute_script(script)
        if value is not True:
            raise AssertionError(f"{name}: {value!r}")
        passed.append(name)
        print(f"PASS {name}", flush=True)

    client.set_context("chrome")
    main = client.current_chrome_window_handle
    for private in (False, True):
        before = set(client.chrome_window_handles)
        client.execute_async_script("""
            const done = arguments[arguments.length - 1];
            let created;
            const observer = { observe(subject) {
                if (subject !== created) { return; }
                Services.obs.removeObserver(observer, 'browser-delayed-startup-finished');
                subject.requestAnimationFrame(() => done(true));
            }};
            Services.obs.addObserver(observer, 'browser-delayed-startup-finished');
            created = OpenBrowserWindow({ private: arguments[0] });
        """, script_args=[private])
        handle = next(value for value in client.chrome_window_handles if value not in before)
        client.switch_to_window(handle)
        label = "Private" if private else "Normal"
        check(f"{label} new window keeps the Forge shell", """
            return document.documentElement.getAttribute('forge-shell') === 'true' &&
                !!document.getElementById('forge-rail') && !!document.getElementById('forge-hub-button');
        """)
        client.execute_script("document.getElementById('forge-new-tab').click();")
        client.execute_async_script("""
            const done = arguments[arguments.length - 1];
            const timer = setInterval(() => {
                if (gBrowser.selectedBrowser.currentURI.spec === 'chrome://browser/content/forge/start.html') {
                    clearInterval(timer); done(true);
                }
            }, 50);
        """)
        check(f"{label} window new tab does not revert to Firefox", """
            return document.documentElement.getAttribute('forge-shell') === 'true' &&
                !!document.getElementById('forge-rail') &&
                gBrowser.selectedBrowser.currentURI.spec === 'chrome://browser/content/forge/start.html';
        """)
        client.close_chrome_window()
        client.switch_to_window(main)

    # Exercise an actual warm restart of the same disposable profile; do not
    # mistake a clean-profile-only pass for coverage of normal user restarts.
    expected_profile=client.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path;")
    client.restart(in_app=True)
    client.set_context("chrome")
    client.execute_async_script("""
        const done = arguments[arguments.length - 1];
        const timer = setInterval(() => {
            if (gBrowserInit.delayedStartupFinished && document.getElementById('forge-rail')) {
                clearInterval(timer); done(true);
            }
        }, 50);
    """)
    check("Warm restart preserves the Forge shell", """
        return document.documentElement.getAttribute('forge-shell') === 'true' &&
            !!document.getElementById('forge-control-center');
    """)
    profile_matches=client.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path===arguments[0];",script_args=[expected_profile])
    if not profile_matches:
        raise AssertionError("Warm restart switched to a different profile")
    passed.append("Warm restart keeps the exact same explicit profile")
    print("PASS Warm restart keeps the exact same explicit profile",flush=True)
    client.execute_script("document.getElementById('forge-new-tab').click();")
    client.execute_async_script("""
        const done = arguments[arguments.length - 1];
        const timer = setInterval(() => {
            if (gBrowser.selectedBrowser.currentURI.spec === 'chrome://browser/content/forge/start.html') {
                clearInterval(timer); done(true);
            }
        }, 50);
    """)
    check("New tab after warm restart keeps the shell", """
        return document.documentElement.getAttribute('forge-shell') === 'true' &&
            gBrowser.selectedBrowser.currentURI.spec === 'chrome://browser/content/forge/start.html';
    """)
    (results / "warm-restart.png").write_bytes(base64.b64decode(client.screenshot()))
