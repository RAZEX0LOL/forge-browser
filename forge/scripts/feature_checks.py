# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from ui_wait import settle_ui


def run_feature_checks(client, results, passed):
    def check(name, script):
        result = client.execute_script(script)
        if result is not True:
            raise AssertionError(f"{name}: {result!r}")
        passed.append(name)
        print(f"PASS {name}", flush=True)

    def frame():
        client.execute_async_script("const done = arguments[arguments.length-1]; requestAnimationFrame(() => requestAnimationFrame(() => done(true)));")

    client.set_context("chrome")
    check("Partial initialization rolls back and can be retried", """
        const module = ChromeUtils.importESModule('chrome://browser/content/forge/Forge.sys.mjs');
        module.destroy(window);
        const original = document.createElementNS;
        let dialogs = 0, failed = false;
        document.createElementNS = function(ns, name, ...args) {
            if (name === 'dialog' && ++dialogs === 3) { throw new Error('intentional rollback test'); }
            return original.call(this, ns, name, ...args);
        };
        try { module.init(window); } catch { failed = true; }
        finally { document.createElementNS = original; }
        const rolledBack = failed && !document.getElementById('forge-rail') &&
            !document.getElementById('forge-palette') && !document.documentElement.hasAttribute('forge-shell');
        window.__forgeFeatureShell = module.init(window);
        return rolledBack && document.documentElement.getAttribute('forge-ready') === 'true' &&
            document.querySelectorAll('#forge-rail').length === 1;
    """)
    check("Toolbar widgets use native customization", """
        const { CustomizableUI } = ChromeUtils.importESModule('moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs');
        return ['forge-command-button','forge-hub-button'].every(id => CustomizableUI.getWidget(id)?.provider === 'api');
    """)
    client.execute_script("""
        const handle = document.getElementById('forge-rail-resize');
        handle.dispatchEvent(new KeyboardEvent('keydown', {key:'ArrowRight', bubbles:true}));
    """)
    settle_ui(client)
    check("Sidebar resizing is keyboard accessible and persisted", """
        return Services.prefs.getIntPref('forge.sidebar.width') === 232 &&
            document.getElementById('forge-rail-resize').getAttribute('aria-valuenow') === '232' &&
            document.getElementById('forge-rail').getBoundingClientRect().width >= 231;
    """)
    client.execute_script("Services.prefs.clearUserPref('forge.sidebar.width');")
    check("Workspaces create real native tabs without closing old tabs", """
        window.__forgeOldTab = gBrowser.selectedTab;
        window.__forgeOldCount = gBrowser.tabs.length;
        const original = window.prompt;
        window.prompt = () => 'Тестовый проект';
        try { document.getElementById('forge-workspace-add').doCommand(); } finally { window.prompt = original; }
        return __forgeFeatureShell.workspaces.state.items.length === 2 &&
            gBrowser.tabs.length === __forgeOldCount + 1 && __forgeOldTab.isConnected;
    """)
    frame(); settle_ui(client)
    check("Workspace filters the view and native selection switches back", """
        const controller = __forgeFeatureShell.workspaces;
        const oldId = controller.idFor(__forgeOldTab);
        const filtered = !controller.visible(__forgeOldTab) && document.querySelectorAll('.forge-tab:not([data-leaving])').length ===
            Array.from(gBrowser.tabs).filter(tab => !tab.closing && controller.visible(tab)).length;
        gBrowser.selectedTab = __forgeOldTab;
        return filtered && controller.state.active === oldId;
    """)
    frame()
    check("Workspace membership is stored in native session data", """
        const { SessionStore } = ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        return JSON.parse(SessionStore.getCustomWindowValue(window,'forge.workspace')).items.length === 2 &&
            !!SessionStore.getCustomTabValue(__forgeOldTab,'forge.workspace');
    """)
    client.execute_script("""
        window.__forgeSplitOther = gBrowser.addTrustedTab('about:blank');
        document.querySelector('.forge-launcher').click();
        const input = document.querySelector('#forge-palette input');
        input.value = 'Разделить просмотр'; input.dispatchEvent(new Event('input', {bubbles:true}));
        document.querySelector('.forge-result').click();
    """)
    frame()
    check("Split view uses actual native page panels", """
        return gBrowser.selectedTab.splitview?.tabs.length === 2 && gBrowser.splitViewBrowsers.length === 2;
    """)
    settle_ui(client)
    (results / "split-view.png").write_bytes(base64.b64decode(client.screenshot()))
    client.execute_script("gBrowser.selectedTab.splitview.unsplitTabs();")
    frame()
    check("Split view separates without losing tabs", "return !gBrowser.selectedTab.splitview && __forgeSplitOther.isConnected;")
    check("Favicon fallback and tab states are available", """
        const tab = gBrowser.selectedTab;
        tab.setAttribute('busy','true'); tab.setAttribute('pending','true'); tab.setAttribute('muted','true');
        tab.dispatchEvent(new CustomEvent('TabAttrModified',{bubbles:true,detail:{changed:['busy','pending','muted']}}));
        return !!document.querySelector('.forge-tab-favicon') && !!document.querySelector('[data-forge-icon="globe"]');
    """)
    frame()
    check("Busy, unloaded and muted states reach the sidebar", """
        const row = document.querySelector('.forge-tab[selected]');
        const valid = row.hasAttribute('busy') && row.hasAttribute('pending') && row.hasAttribute('muted') &&
            !row.querySelector('.forge-tab-audio').hidden;
        for (const name of ['busy','pending','muted']) { gBrowser.selectedTab.removeAttribute(name); }
        gBrowser.selectedTab.dispatchEvent(new CustomEvent('TabAttrModified',{bubbles:true,detail:{changed:['busy','pending','muted']}}));
        return valid;
    """)
    client.execute_script("""
        document.querySelector('.forge-tab[selected]').dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,screenX:180,screenY:180}));
    """)
    frame()
    check("Tab menu exposes native actions and workspace moves", """
        const menu = document.getElementById('forge-tab-menu');
        return menu.state === 'open' && Array.from(menu.children).some(item => item.getAttribute('label') === 'Закрепить') &&
            Array.from(menu.children).some(item => item.getAttribute('label').startsWith('Перенести в'));
    """)
    client.execute_script("document.getElementById('forge-tab-menu').hidePopup(); document.querySelector('.forge-tool[aria-label=" + '"Оформление"' + "]').click();")
    check("Theme preview can be cancelled without saving", """
        window.__forgeBeforeTheme = Services.prefs.getStringPref('forge.theme','{}');
        const editor = document.getElementById('forge-editor');
        editor.querySelector('[data-setting="appearance"]').value = 'glass';
        document.getElementById('forge-theme-preview').click();
        const applied = document.documentElement.getAttribute('forge-appearance') === 'glass';
        editor.close();
        return applied;
    """)
    frame()
    check("Closing preview restores the previous saved preferences", "return Services.prefs.getStringPref('forge.theme','{}') === __forgeBeforeTheme;")
    check("Emergency shortcut disables custom CSS", """
        Services.prefs.setBoolPref('forge.customCSS.enabled',true);
        document.getElementById('forge-css-recovery-key').dispatchEvent(new Event('command',{bubbles:true}));
        return !Services.prefs.getBoolPref('forge.customCSS.enabled');
    """)
    check("Settings import stays opt-in and can be exported", """
        document.querySelector('.forge-tool[aria-label="Оформление"]').click();
        const transfer = document.querySelector('#forge-settings-transfer textarea');
        transfer.value = JSON.stringify({version:1,theme:{appearance:'glass'},css:'/* imported */'});
        document.querySelectorAll('#forge-settings-transfer button')[1].click();
        const editor = document.getElementById('forge-editor');
        const imported = editor.querySelector('[data-setting="appearance"]').value === 'glass' &&
            editor.querySelector('#forge-editor-advanced textarea').value === '/* imported */' &&
            !editor.querySelector('#forge-editor-advanced input[type="checkbox"]').checked;
        document.querySelectorAll('#forge-settings-transfer button')[0].click();
        const exported = JSON.parse(transfer.value);
        editor.close();
        return imported && exported.version === 2 && exported.theme.appearance === 'glass';
    """)
    frame()
    check("Keyboard and dock preferences apply and can be undone", """
        document.querySelector('.forge-tool[aria-label="Оформление"]').click();
        const editor = document.getElementById('forge-editor');
        document.getElementById('forge-palette-shortcut').value = 'J';
        document.querySelector('#forge-dock-settings [data-tool="network"] input').checked = false;
        editor.querySelector('#forge-theme-save').click();
        const applied = document.getElementById('forge-command-key').getAttribute('key') === 'J' &&
            document.querySelector('[data-forge-tool="network"]').hidden;
        document.querySelector('.forge-tool[aria-label="Оформление"]').click();
        document.getElementById('forge-theme-undo').click();
        editor.close();
        return applied && document.getElementById('forge-command-key').getAttribute('key') === 'K' &&
            !document.querySelector('[data-forge-tool="network"]').hidden;
    """)
    frame()
    check("Drag-and-drop handlers reorder native tabs", """
        const controller = __forgeFeatureShell.workspaces;
        const native = Array.from(gBrowser.tabs).filter(tab => !tab.closing && controller.visible(tab));
        const rows = Array.from(document.querySelectorAll('.forge-tab:not([data-leaving])'));
        if (native.length < 2) { return false; }
        const moved = native[0], before = moved.index;
        const transfer = new DataTransfer();
        rows[0].dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:transfer}));
        rows[1].dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
        const valid = moved.index !== before;
        gBrowser.moveTabTo(moved,{tabIndex:before});
        return valid;
    """)
    frame(); settle_ui(client)
    client.set_window_rect(width=800, height=600)
    client.execute_script("document.querySelector('.forge-tool[aria-label=" + '"Оформление"' + "]').click();")
    settle_ui(client)
    check("Appearance editor fits a small window and scrolls to its actions", """
        const editor = document.getElementById('forge-editor');
        const rect = editor.getBoundingClientRect();
        const valid = rect.top >= 0 && rect.bottom <= innerHeight+1 && rect.right <= innerWidth+1 &&
            editor.scrollWidth <= editor.clientWidth+1;
        editor.querySelector('.forge-actions').scrollIntoView({block:'nearest',behavior:'instant'});
        return valid && editor.querySelector('.forge-actions').getBoundingClientRect().bottom <= rect.bottom;
    """)
    (results / "editor-small-window.png").write_bytes(base64.b64decode(client.screenshot()))
    client.execute_script("document.getElementById('forge-editor').close();")
    client.set_window_rect(width=1366, height=768)
    frame()
    check("Developer project presets persist validated local addresses", """
        const { projectCommands } = ChromeUtils.importESModule('chrome://browser/content/forge/Projects.sys.mjs');
        const original = window.prompt;
        const answers = ['Test localhost', 'http://localhost:3000/', 'netmonitor'];
        window.prompt = () => answers.shift();
        try { projectCommands(window, () => {}).find(item => item.id === 'project-add').run(); }
        finally { window.prompt = original; }
        return JSON.parse(Services.prefs.getStringPref('forge.developer.projects'))[0].tool === 'netmonitor' &&
            projectCommands(window, () => {}).some(item => item.title === 'Проект: Test localhost');
    """)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = b'<!doctype html><title>Forge local navigation test</title><p>Local only</p>'
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers(); self.wfile.write(data)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/forge-start'
        client.set_context('content')
        client.navigate('chrome://browser/content/forge/start.html')
        client.execute_script("document.getElementById('query').value=arguments[0]; document.getElementById('forge-search').requestSubmit();", script_args=[url])
        client.set_context('chrome')
        result = client.execute_async_script("""
            const expected = arguments[0], done = arguments[arguments.length-1];
            let attempts = 0;
            const timer = setInterval(() => {
                if (gBrowser.selectedBrowser.currentURI.spec === expected) { clearInterval(timer); done(true); }
                else if (++attempts > 100) { clearInterval(timer); done(gBrowser.selectedBrowser.currentURI.spec); }
            }, 50);
        """, script_args=[url])
        if result is not True:
            raise AssertionError(f'Start page native navigation: {result!r}')
        passed.append('Start page delegates URL navigation to the native address bar')
        print('PASS Start page delegates URL navigation to the native address bar', flush=True)
        client.execute_async_script("""
            const done = arguments[arguments.length-1];
            const { SearchService } = ChromeUtils.importESModule('moz-src:///toolkit/components/search/SearchService.sys.mjs');
            (async () => {
                window.__forgeOldEngine = await SearchService.getDefault();
                const engine = await SearchService.addUserEngine({name:'Forge local test',url:arguments[0]+'?q={searchTerms}'});
                await SearchService.setDefault(engine,SearchService.CHANGE_REASON.USER);
                done(true);
            })().catch(error => done(String(error)));
        """, script_args=[url])
        client.set_context('content')
        client.navigate('chrome://browser/content/forge/start.html')
        client.execute_script("document.getElementById('query').value='forge engine test'; document.getElementById('forge-search').requestSubmit();")
        client.set_context('chrome')
        result = client.execute_async_script("""
            const expected = arguments[0], done = arguments[arguments.length-1];
            let attempts = 0;
            const timer = setInterval(() => {
                const uri = gBrowser.selectedBrowser.currentURI.spec;
                if (uri.startsWith(expected+'?q=') && decodeURIComponent(uri.replaceAll('+',' ')).includes('forge engine test')) { clearInterval(timer); done(true); }
                else if (++attempts > 100) { clearInterval(timer); done(uri); }
            },50);
        """, script_args=[url])
        if result is not True:
            raise AssertionError(f'Start page selected engine: {result!r}')
        passed.append('Start page search follows the selected native search engine')
        print('PASS Start page search follows the selected native search engine', flush=True)
        client.execute_async_script("""
            const done = arguments[arguments.length-1];
            const { SearchService } = ChromeUtils.importESModule('moz-src:///toolkit/components/search/SearchService.sys.mjs');
            SearchService.setDefault(__forgeOldEngine,SearchService.CHANGE_REASON.USER).then(() => {delete window.__forgeOldEngine;done(true);});
        """)
    finally:
        server.shutdown(); server.server_close()
    client.set_context('chrome')
    metrics = []
    for count in (100, 200):
        client.execute_script("""
            window.__forgeLoadStarted = performance.now();
            window.__forgeLoadTabs = Array.from({length:arguments[0]}, () => gBrowser.addTrustedTab('about:blank'));
            gBrowser.selectedTab = __forgeLoadTabs.at(-1);
        """, script_args=[count])
        frame(); settle_ui(client)
        metrics.append(client.execute_script("""
            const panel = document.getElementById('forge-tabs').getBoundingClientRect();
            const active = document.querySelector('.forge-tab[selected]').getBoundingClientRect();
            return {tabs:arguments[0], createAndRenderMs:performance.now()-__forgeLoadStarted,
                activeVisible:active.top >= panel.top && active.bottom <= panel.bottom+1,
                rendered:document.querySelectorAll('.forge-tab:not([data-leaving])').length};
        """, script_args=[count]))
        check(f"{count} tabs render and keep the active row visible", """
            const panel = document.getElementById('forge-tabs').getBoundingClientRect();
            const active = document.querySelector('.forge-tab[selected]').getBoundingClientRect();
            return active.top >= panel.top && active.bottom <= panel.bottom+1 &&
                document.querySelectorAll('.forge-tab:not([data-leaving])').length >= arguments[0];
        """.replace('arguments[0]', str(count)))
        client.execute_script("gBrowser.removeTabs(__forgeLoadTabs, {animate:false}); delete window.__forgeLoadTabs;")
        frame(); settle_ui(client)
    (results / 'tab-load.json').write_text(json.dumps({'note':'Synthetic local about:blank load; not a cross-browser benchmark', 'runs':metrics}, indent=2)+'\n')
    check("Workspace session snapshot is ready for restart", """
        const { SessionStore } = ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        Services.prefs.setStringPref('forge.test.expectedWorkspace',SessionStore.getCustomWindowValue(window,'forge.workspace'));
        return true;
    """)
    client.execute_script("delete window.__forgeFeatureShell; delete window.__forgeOldTab; delete window.__forgeOldCount; delete window.__forgeSplitOther; delete window.__forgeBeforeTheme;")
    expected_profile=client.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path;")
    (results / 'workspace-restart-state.json').write_text(json.dumps(client.execute_script("""
        return {pid:Services.appinfo.processID,profile:Services.dirsvc.get('ProfD',Ci.nsIFile).path,
            windows:Array.from(Services.wm.getEnumerator('navigator:browser'),win=>({closed:win.closed,tabs:win.gBrowser.tabs.length})),
            environment:Object.fromEntries(['XRE_PROFILE_PATH','XRE_BINARY_PATH','MOZ_APP_RESTART','MOZ_APP_LAUNCHER','MOZ_APP_SILENT_START'].map(key=>[key,Services.env.get(key)]))};
    """),indent=2)+'\n')
    client.restart(in_app=True)
    client.set_context('chrome')
    client.execute_async_script("""
        const done = arguments[arguments.length-1];
        let attempts = 0;
        const timer=setInterval(() => {
            if(document.documentElement.getAttribute('forge-ready')==='true') {clearInterval(timer);done(true);}
            else if(++attempts>200){clearInterval(timer);done(false);}
        },50);
    """)
    check("Workspace names and active selection survive a real restart", """
        const expected = JSON.parse(Services.prefs.getStringPref('forge.test.expectedWorkspace'));
        const { SessionStore } = ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        const actual = JSON.parse(SessionStore.getCustomWindowValue(window,'forge.workspace'));
        return (JSON.stringify(actual.items)===JSON.stringify(expected.items) && actual.active===expected.active &&
            document.getElementById('forge-workspace').value===expected.active) || {expected,actual,selected:document.getElementById('forge-workspace').value};
    """)
    if not client.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path===arguments[0];",script_args=[expected_profile]):
        raise AssertionError("Workspace restart changed the explicit profile")
    passed.append("Workspace restart keeps the exact same explicit profile")
    print("PASS Workspace restart keeps the exact same explicit profile",flush=True)
    client.execute_script("Services.prefs.clearUserPref('forge.test.expectedWorkspace'); Services.prefs.clearUserPref('forge.developer.projects');")
    settle_ui(client)
    (results / 'workspaces.png').write_bytes(base64.b64decode(client.screenshot()))
