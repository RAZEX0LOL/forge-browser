# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Integration checks for real browser UI beyond the new-tab page."""
import base64
from ui_wait import settle_ui


def run_surface_checks(client, results, passed):
    failures = []

    def check(name, script):
        try:
            value = client.execute_script(script)
        except Exception as error:
            value = str(error)
        if value is not True:
            failures.append(f"{name}: {value!r}")
            print(f"FAIL {name}: {value!r}", flush=True)
            return
        passed.append(name)
        print(f"PASS {name}", flush=True)

    def screenshot(name):
        client.set_context("chrome")
        settle_ui(client)
        (results / f"{name}.png").write_bytes(base64.b64decode(client.screenshot()))

    def settle():
        client.execute_async_script("""
            const done = arguments[arguments.length - 1];
            requestAnimationFrame(() => requestAnimationFrame(() => done(true)));
        """)

    client.set_context("chrome")
    check("Native omnibox uses Forge geometry", """
        const radius = getComputedStyle(document.querySelector('#urlbar .urlbar-background')).borderRadius;
        const version = getComputedStyle(document.documentElement).getPropertyValue('--forge-design-version').trim();
        return (radius === '18px' && version === '2') || {radius, version};
    """)
    check("DevTools uses shared Forge palette", """
        const { require } = ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
        const { gDevTools } = require('devtools/client/framework/devtools');
        const toolbox = gDevTools.getToolboxForTab(gBrowser.selectedTab);
        const background = toolbox?.win.getComputedStyle(toolbox.doc.documentElement)
            .getPropertyValue('--theme-body-background').trim();
        return background === '#000000' || {background, uri: toolbox?.doc.documentURI};
    """)
    check("Native browser product labels use Forge branding", """
        const bundle = Services.strings.createBundle('chrome://branding/locale/brand.properties');
        return bundle.GetStringFromName('brandShortName') === 'Forge';
    """)
    screenshot("devtools")
    client.execute_async_script("""
        const done = arguments[arguments.length - 1];
        const { require } = ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
        const { gDevTools } = require('devtools/client/framework/devtools');
        gDevTools.getToolboxForTab(gBrowser.selectedTab).destroy().then(() => done(true));
    """)
    check("Custom control center opens with real actions", """
        document.getElementById('forge-hub-button').doCommand();
        return document.getElementById('forge-control-center').open &&
            document.querySelectorAll('.forge-hub-action').length === 13;
    """)
    screenshot("control-center")
    client.execute_script("document.getElementById('forge-control-center').close();")

    client.set_context("content")
    client.switch_to_window(client.window_handles[0])
    client.navigate("about:preferences")
    settle()
    check("Real settings page has Forge layout and native search", """
        return !!document.getElementById('forge-settings-header') && !!document.getElementById('searchInput') &&
            getComputedStyle(document.documentElement).getPropertyValue('--forge-design-version').trim() === '2';
    """)
    check('Forge settings header is translated through Fluent without replacing native settings', """
        return document.documentElement.getAttribute('data-forge-localized')==='true' &&
            document.querySelector('[data-forge-l10n="forge-settings-title"]').textContent==='Браузер под твоим контролем.' &&
            document.querySelector('#forge-settings-header nav').getAttribute('aria-label')==='Разделы Forge';
    """)
    check("Theme accent reaches settings in the content process", """
        return getComputedStyle(document.documentElement).getPropertyValue('--forge-accent').trim() === '#33aaff';
    """)
    client.set_context("chrome")
    client.execute_script("Services.prefs.clearUserPref('forge.theme');")
    client.set_context("content")
    client.execute_async_script("""
        const done = arguments[arguments.length - 1];
        const timer = setInterval(() => {
            if (getComputedStyle(document.documentElement).getPropertyValue('--forge-accent').trim() === '#a4efce') {
                clearInterval(timer); done(true);
            }
        }, 50);
    """)
    check("Theme reset updates already-open native settings", """
        return getComputedStyle(document.documentElement).getPropertyValue('--forge-accent').trim() === '#a4efce';
    """)
    screenshot("settings")

    surfaces = [
        ("about:addons", "extensions", "Extensions manager receives design tokens"),
        ("about:downloads", "downloads", "Downloads page receives design tokens"),
        ("about:logins", "passwords", "Password manager receives design tokens"),
        ("about:processes", "processes", "Process manager receives design tokens"),
        ("about:policies", "policies", "Privacy policy page receives design tokens"),
    ]
    for url, filename, label in surfaces:
        client.set_context("content")
        client.navigate(url)
        settle()
        check(label, """
            return getComputedStyle(document.documentElement).getPropertyValue('--forge-design-version').trim() === '2' &&
                getComputedStyle(document.documentElement).getPropertyValue('--forge-accent').trim() === '#a4efce';
        """)
        if url == "about:addons":
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const timer = setInterval(() => {
                    if (document.querySelector('addon-list')) { clearInterval(timer); done(true); }
                }, 50);
            """)
            check("Extension recommendations landing page is removed", """
                return !!document.querySelector('addon-list') && !document.querySelector('discovery-pane') &&
                    !document.querySelector('addons-promo') && !!document.getElementById('forge-extensions-empty');
            """)
            check('Forge extension empty-state uses the Fluent catalogue', "return document.querySelector('#forge-extensions-empty h2')?.textContent==='Расширений пока нет.';")
        if url == "about:downloads":
            check("Downloads has a native Forge page layout", """
                return !!document.getElementById('forge-downloads-header') && !!document.getElementById('downloadsListBox');
            """)
            check('Forge downloads headings use Fluent while retaining the native download backend', """
                return document.documentElement.getAttribute('data-forge-localized')==='true' &&
                    document.querySelector('[data-forge-l10n="forge-downloads-title"]').textContent==='Твои загрузки.' &&
                    !!document.getElementById('downloadsListBox');
            """)
        if url == "about:logins":
            check("Password empty state uses Forge artwork", """
                const image = document.querySelector('login-intro')?.shadowRoot.querySelector('.illustration');
                return image?.src === 'chrome://browser/content/forge/vault.svg';
            """)
        screenshot(filename)
        if url == "about:downloads":
            client.set_context("chrome")
            client.execute_async_script("""
                const target = arguments[0];
                const done = arguments[arguments.length - 1];
                (async () => {
                    const { Downloads } = ChromeUtils.importESModule('resource://gre/modules/Downloads.sys.mjs');
                    const list = await Downloads.getList(Downloads.ALL);
                    const download = await Downloads.createDownload({source: 'data:text/plain,Forge%20download%20test', target});
                    window.forgeTestDownload = download;
                    await list.add(download);
                    await download.start();
                    done(true);
                })().catch(error => done(String(error)));
            """, script_args=[client.profile_path + "/forge-download-test.txt"])
            client.set_context("content")
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const timer = setInterval(() => {
                    if (document.querySelector('#downloadsListBox richlistitem')) { clearInterval(timer); done(true); }
                }, 50);
            """)
            check("Real completed download uses the redesigned list", """
                const row = document.querySelector('#downloadsListBox richlistitem');
                return !!row && getComputedStyle(row).borderRadius === '12px' &&
                    getComputedStyle(document.getElementById('downloadsListEmptyDescription')).display === 'none';
            """)
            screenshot("downloads-active")
            client.execute_async_script("""
                const done = arguments[arguments.length - 1];
                const { Downloads } = ChromeUtils.importESModule('resource://gre/modules/Downloads.sys.mjs');
                Downloads.getList(Downloads.ALL).then(list => list.remove(window.forgeTestDownload))
                    .then(() => { delete window.forgeTestDownload; done(true); });
            """)

    client.set_context("chrome")
    original_window = client.current_chrome_window_handle
    before = set(client.chrome_window_handles)
    client.execute_async_script("""
        const done = arguments[arguments.length - 1];
        PlacesCommandHook.showPlacesOrganizer('History');
        const timer = setInterval(() => {
            const organizer = Services.wm.getMostRecentWindow('Places:Organizer');
            if (organizer?.document.readyState === 'complete') { clearInterval(timer); done(true); }
        }, 50);
    """)
    organizer_handle = next(handle for handle in client.chrome_window_handles if handle not in before)
    client.switch_to_window(organizer_handle)
    check("History and bookmarks library uses Forge design", """
        return document.documentURI.includes('/places/places.xhtml') &&
            getComputedStyle(document.documentElement).getPropertyValue('--forge-design-version').trim() === '2' &&
            !!document.getElementById('placesView');
    """)
    screenshot("history")
    client.close_chrome_window()
    client.switch_to_window(original_window)

    client.execute_async_script("""
        const done = arguments[arguments.length - 1];
        document.getElementById('forge-hub-button').doCommand();
        document.getElementById('forge-native-menu').click();
        const timer = setInterval(() => {
            if (PanelUI.panel.state === 'open') { clearInterval(timer); done(true); }
        }, 50);
    """)
    check("Fallback native menu is available and redesigned", """
        return PanelUI.panel.state === 'open' &&
            getComputedStyle(PanelUI.panel).getPropertyValue('--arrowpanel-background').trim() ===
                getComputedStyle(document.documentElement).getPropertyValue('--forge-surface').trim();
    """)
    screenshot("native-menu")
    client.execute_script("PanelUI.hide();")
    client.set_context("content")
    client.switch_to_window(client.window_handles[0])
    client.navigate("data:text/html,<title>Unthemed site</title><body style='background:white;color:black'><h1>Site content stays untouched</h1><input placeholder='Native site input'></body>")
    check("Website content is not themed by Forge", """
        return getComputedStyle(document.documentElement).getPropertyValue('--forge-design-version').trim() === '' &&
            getComputedStyle(document.body).backgroundColor === 'rgb(255, 255, 255)';
    """)
    client.set_context("chrome")
    if failures:
        raise AssertionError("Surface checks failed: " + "; ".join(failures))
