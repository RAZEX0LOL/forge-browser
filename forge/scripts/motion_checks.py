# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
import base64
from ui_wait import settle_ui


def run_motion_checks(client, results, passed):
    def check(name, script):
        value = client.execute_script(script)
        if value is not True:
            raise AssertionError(f"{name}: {value!r}")
        passed.append(name)
        print(f"PASS {name}", flush=True)

    def frame():
        client.execute_async_script("""
            const done = arguments[arguments.length - 1];
            requestAnimationFrame(() => requestAnimationFrame(() => done(true)));
        """)

    def async_check(name, script):
        value = client.execute_async_script(script)
        if value is not True:
            raise AssertionError(f"{name}: {value!r}")
        passed.append(name)
        print(f"PASS {name}", flush=True)

    client.set_context("chrome")
    client.execute_script("""
        Services.prefs.setIntPref('ui.prefersReducedMotion', 0);
        const theme = JSON.parse(Services.prefs.getStringPref('forge.theme', '{}'));
        theme.motion = 'system';
        Services.prefs.setStringPref('forge.theme', JSON.stringify(theme));
    """)
    frame()
    check("Tab close controls are visible without hover", """
        document.getElementById('forge-new-tab').focus();
        return Array.from(document.querySelectorAll('.forge-tab-close')).every(button => {
            const style = getComputedStyle(button);
            return style.display !== 'none' && style.opacity === '1' && style.pointerEvents === 'auto' &&
                button.getBoundingClientRect().height >= 24;
        });
    """)
    check("Minimal tool dock keeps accessible names without persistent labels", """
        const tools = Array.from(document.querySelectorAll('.forge-dev-tools toolbarbutton'));
        return tools.length === 5 && tools.every(button => button.getAttribute('aria-label') &&
            getComputedStyle(button.querySelector('span')).display === 'none');
    """)
    client.execute_script("document.getElementById('forge-sidebar-toggle').click();")
    settle_ui(client)
    check("Sidebar collapses to a usable icon rail", """
        return document.documentElement.hasAttribute('forge-sidebar-collapsed') &&
            document.getElementById('forge-rail').getBoundingClientRect().width <= 82 &&
            document.getElementById('forge-sidebar-toggle').getAttribute('aria-expanded') === 'false' &&
            document.getElementById('forge-new-tab').getAttribute('aria-label') === 'Новая вкладка';
    """)
    (results / "sidebar-collapsed.png").write_bytes(base64.b64decode(client.screenshot()))
    check("Collapsed sidebar buttons remain visible and inside the rail", """
        const rail = document.getElementById('forge-rail').getBoundingClientRect();
        const buttons = document.querySelectorAll('#forge-sidebar-toggle, .forge-launcher, .forge-new-tab, .forge-dev-tools toolbarbutton, .forge-tab-close');
        return Array.from(buttons).every(button => {
            const rect = button.getBoundingClientRect();
            const style = getComputedStyle(button);
            return rect.width >= 24 && rect.height >= 24 && rect.left >= rail.left && rect.right <= rail.right &&
                style.display !== 'none' && style.opacity === '1' && style.pointerEvents === 'auto';
        });
    """)
    client.execute_script("document.getElementById('forge-new-tab').click();")
    frame()
    settle_ui(client)
    check("Collapsed tab close hits the visible control and closes the native tab", """
        const tab = gBrowser.selectedTab;
        const close = document.querySelector('.forge-tab[selected] .forge-tab-close');
        const rect = close.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        if (hit !== close && !close.contains(hit)) { return false; }
        close.click();
        return tab.closing || !tab.isConnected;
    """)
    frame()
    settle_ui(client)
    client.execute_script("document.getElementById('forge-sidebar-toggle').click();")
    settle_ui(client)
    check("Sidebar expansion preserves the tab view and keyboard-close access", """
        const close = document.querySelector('.forge-tab[selected] .forge-tab-close');
        close.focus();
        return !document.documentElement.hasAttribute('forge-sidebar-collapsed') &&
            document.getElementById('forge-rail').getBoundingClientRect().width >= 200 &&
            close.getAttribute('aria-label')?.startsWith('Закрыть:') &&
            getComputedStyle(close).pointerEvents === 'auto';
    """)
    async_check("Control center opens with a real finite animation", """
        const done = arguments[arguments.length - 1];
        document.getElementById('forge-hub-button').doCommand();
        const deadline = performance.now() + 1000;
        const inspect = () => {
            const animations = document.getElementById('forge-control-center').getAnimations({subtree: true});
            if (animations.some(animation => animation.id === 'forge-motion' && animation.playState === 'running')) { done(true); }
            else if (performance.now() < deadline) { requestAnimationFrame(inspect); }
            else { done(false); }
        };
        requestAnimationFrame(inspect);
    """)
    settle_ui(client)
    (results / "minimal-control-center.png").write_bytes(base64.b64decode(client.screenshot()))
    client.execute_script("document.getElementById('forge-control-center').close();")
    async_check("New tab enters with a composited animation", """
        const done = arguments[arguments.length - 1];
        document.getElementById('forge-new-tab').click();
        requestAnimationFrame(() => {
            const row = document.querySelector('.forge-tab[selected]');
            done(!!row && row.getAnimations().some(animation => animation.id === 'forge-motion' && animation.playState === 'running'));
        });
    """)
    async_check("Closed tab exits visually without delaying its native close", """
        const done = arguments[arguments.length - 1];
        const tab = gBrowser.selectedTab;
        const close = document.querySelector('.forge-tab[selected] .forge-tab-close');
        close.focus();
        close.click();
        requestAnimationFrame(() => {
            const leaving = document.querySelector('.forge-tab[data-leaving]');
            done(!!leaving && leaving.inert && (tab.closing || !tab.isConnected) &&
                leaving.getAnimations().some(animation => animation.id === 'forge-motion'));
        });
    """)
    settle_ui(client)
    client.execute_script("Services.prefs.setIntPref('ui.prefersReducedMotion', 1);")
    frame()
    client.execute_script("document.getElementById('forge-hub-button').doCommand();")
    frame()
    check("System reduced-motion disables JS and CSS movement", """
        const hub = document.getElementById('forge-control-center');
        return matchMedia('(prefers-reduced-motion: reduce)').matches &&
            !hub.getAnimations({subtree:true}).some(animation => animation.playState === 'running') &&
            getComputedStyle(document.getElementById('forge-rail')).transitionDuration.split(',').every(value => parseFloat(value) === 0);
    """)
    client.execute_script("""
        document.getElementById('forge-control-center').close();
        Services.prefs.setIntPref('ui.prefersReducedMotion', 0);
    """)
    frame()
    client.execute_script("""
        document.getElementById('forge-hub-button').doCommand();
        document.querySelector('.forge-hub-action[data-action="Оформление"]').click();
        const editor = document.getElementById('forge-editor');
        editor.querySelector('[data-setting="motion"]').value = 'off';
        editor.querySelector('#forge-theme-save').click();
        document.getElementById('forge-hub-button').doCommand();
    """)
    frame()
    check("Explicit animation-off setting persists and takes effect", """
        return JSON.parse(Services.prefs.getStringPref('forge.theme')).motion === 'off' &&
            document.documentElement.getAttribute('forge-motion') === 'off' &&
            !document.getElementById('forge-control-center').getAnimations({subtree:true})
                .some(animation => animation.playState === 'running');
    """)
    client.execute_script("""
        document.getElementById('forge-control-center').close();
        Services.prefs.clearUserPref('ui.prefersReducedMotion');
        Services.prefs.clearUserPref('forge.sidebar.collapsed');
        const theme = JSON.parse(Services.prefs.getStringPref('forge.theme'));
        theme.motion = 'system';
        Services.prefs.setStringPref('forge.theme', JSON.stringify(theme));
    """)
