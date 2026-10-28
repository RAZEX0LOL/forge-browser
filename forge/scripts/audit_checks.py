# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Additional regression audit; all data belong to a disposable test profile."""
import base64
from marionette_driver.by import By
from marionette_driver.keys import Keys
from marionette_driver import errors
from marionette_driver.wait import Wait
from ui_wait import settle_ui


def run_audit_checks(client, results, passed):
    failures = []

    def check(name, script, asynchronous=False):
        try:
            method = client.execute_async_script if asynchronous else client.execute_script
            result = method(script)
        except Exception as error:
            result = str(error)
        if result is True:
            passed.append(name)
            print(f"PASS {name}", flush=True)
        else:
            failures.append({"name": name, "details": result})
            print(f"FAIL {name}: {result!r}", flush=True)

    def frame():
        client.execute_async_script("const done=arguments[arguments.length-1];requestAnimationFrame(()=>requestAnimationFrame(()=>done(true)));")

    def screenshot(name):
        settle_ui(client)
        (results / f"audit-{name}.png").write_bytes(base64.b64decode(client.screenshot()))

    client.set_context("chrome")
    client.execute_script("""
        window.__forgeAuditPrefs={};
        for(const name of ['forge.theme','forge.tools','forge.shortcuts.palette']) {
            __forgeAuditPrefs[name]=Services.prefs.prefHasUserValue(name)?Services.prefs.getStringPref(name):null;
        }
        window.__forgeAuditRestore=()=>{
            for(const [name,value] of Object.entries(__forgeAuditPrefs)) {
                if(value===null){Services.prefs.clearUserPref(name);}else{Services.prefs.setStringPref(name,value);}
            }
        };
        Services.prefs.setIntPref('ui.prefersReducedMotion',0);
    """)
    check("Keyboard context menu opens for a vertical tab", """
        const done=arguments[arguments.length-1];
        const popup=document.getElementById('forge-tab-menu');
        let timeout;
        const shown=()=>{clearTimeout(timeout);done(popup.state==='open');};
        popup.addEventListener('popupshown',shown,{once:true});
        timeout=setTimeout(()=>{popup.removeEventListener('popupshown',shown);done({state:popup.state});},5000);
        const button=document.querySelector('.forge-tab[selected] .forge-tab-select');
        button.focus();
        button.dispatchEvent(new KeyboardEvent('keydown',{key:'F10',shiftKey:true,bubbles:true}));
    """, True)
    client.execute_script("document.getElementById('forge-tab-menu').hidePopup(); window.__forgeAuditHidden=gBrowser.addTrustedTab('about:blank');")
    frame(); settle_ui(client)
    client.execute_script("window.__forgeAuditRows=document.querySelectorAll('.forge-tab:not([data-leaving])').length;gBrowser.hideTab(__forgeAuditHidden,'forge-audit');")
    frame(); settle_ui(client)
    check("Native hidden tabs disappear from the Forge view", "return __forgeAuditHidden.hidden && document.querySelectorAll('.forge-tab:not([data-leaving])').length===__forgeAuditRows-1;")
    client.execute_script("gBrowser.showTab(__forgeAuditHidden);")
    frame(); settle_ui(client)
    check("Native shown tabs return to the Forge view", "return !__forgeAuditHidden.hidden && document.querySelectorAll('.forge-tab:not([data-leaving])').length===__forgeAuditRows;")
    client.execute_script("gBrowser.removeTab(__forgeAuditHidden);delete window.__forgeAuditHidden;delete window.__forgeAuditRows;gBrowser.setIcon(gBrowser.selectedTab,'data:image/png;base64,AA==');")
    check("Broken favicon switches to a visible fallback", """
        const done=arguments[arguments.length-1];let attempts=0;
        const timer=setInterval(()=>{
            const row=document.querySelector('.forge-tab[selected]');
            const image=row?.querySelector('.forge-tab-favicon');
            if(image?.complete && image.naturalWidth===0) {
                clearInterval(timer);done(image.hidden && !row.querySelector('.forge-tab-marker > svg').hasAttribute('hidden'));
            } else if(++attempts>40){clearInterval(timer);done(false);}
        },25);
    """, True)
    client.execute_script("gBrowser.selectedTab.dispatchEvent(new CustomEvent('TabAttrModified',{bubbles:true,detail:{changed:['label']}}));")
    frame()
    check("Broken favicon fallback survives subsequent tab updates", """
        const row=document.querySelector('.forge-tab[selected]');
        return row.querySelector('.forge-tab-favicon').hidden && !row.querySelector('.forge-tab-marker > svg').hasAttribute('hidden');
    """)
    client.execute_script("gBrowser.setIcon(gBrowser.selectedTab,null); document.querySelector('.forge-tool[aria-label=" + '"Оформление"' + "]').doCommand();")
    check("Undo refreshes the editor fields as well as saved preferences", """
        const editor=document.getElementById('forge-editor');
        document.getElementById('forge-palette-shortcut').value='J';
        document.querySelector('#forge-dock-settings [data-tool="network"] input').checked=false;
        editor.querySelector('#forge-theme-save').doCommand();
        document.querySelector('.forge-tool[aria-label="Оформление"]').doCommand();
        document.getElementById('forge-theme-undo').doCommand();
        return document.getElementById('forge-palette-shortcut').value==='K' &&
            document.querySelector('#forge-dock-settings [data-tool="network"] input').checked &&
            document.getElementById('forge-command-key').getAttribute('key')==='K';
    """)
    check("Applying after undo does not reintroduce discarded layout", """
        document.getElementById('forge-theme-save').doCommand();
        return document.getElementById('forge-command-key').getAttribute('key')==='K' &&
            !document.querySelector('[data-forge-tool="network"]').hidden;
    """)
    client.execute_script("__forgeAuditRestore(); document.querySelector('.forge-tool[aria-label=" + '"Оформление"' + "]').doCommand();")
    client.execute_script("""
        document.querySelector('#forge-editor [data-setting="appearance"]').value='glass';
        document.getElementById('forge-theme-preview').doCommand();
        Services.prefs.setStringPref('forge.shortcuts.palette','J');
        document.getElementById('forge-editor').close();
    """)
    frame()
    check("Cancelling theme preview does not undo unrelated settings", "return Services.prefs.getStringPref('forge.shortcuts.palette')==='J';")
    client.execute_script("""
        __forgeAuditRestore();
        document.querySelector('.forge-tool[aria-label="Оформление"]').doCommand();
        document.querySelector('#forge-editor [data-setting="appearance"]').value='glass';
        document.getElementById('forge-theme-preview').doCommand();
        window.__forgeAuditConcurrentTheme=JSON.stringify({appearance:'amoled',accent:'#aaccff',contrast:'strong'});
        Services.prefs.setStringPref('forge.theme',__forgeAuditConcurrentTheme);
        document.getElementById('forge-editor').close();
    """)
    frame()
    check("Preview cancellation preserves a newer theme saved elsewhere", "return Services.prefs.getStringPref('forge.theme')===__forgeAuditConcurrentTheme;")
    client.execute_script("""
        __forgeAuditRestore();
        document.getElementById('forge-hub-button').doCommand();
        document.getElementById('forge-command-key').dispatchEvent(new Event('command',{bubbles:true}));
    """)
    check("Opening command palette never stacks Forge modal dialogs", "return document.querySelectorAll('#forge-control-center[open],#forge-editor[open],#forge-palette[open]').length===1 && document.getElementById('forge-palette').open;")
    client.execute_script("for(const id of ['forge-control-center','forge-editor','forge-palette']){document.getElementById(id).close();}")
    check("Arrow navigation skips inert tab-exit animation rows", """
        const done=arguments[arguments.length-1];
        const theme=JSON.parse(Services.prefs.getStringPref('forge.theme','{}'));theme.motion='system';Services.prefs.setStringPref('forge.theme',JSON.stringify(theme));
        const tabs=[gBrowser.addTrustedTab('about:blank'),gBrowser.addTrustedTab('about:blank'),gBrowser.addTrustedTab('about:blank')];
        requestAnimationFrame(()=>{
            gBrowser.removeTab(tabs[1]);
            requestAnimationFrame(()=>{
                const live=Array.from(document.querySelectorAll('.forge-tab:not([data-leaving]) .forge-tab-select'));
                const last=live.at(-1);last.focus();last.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));
                const valid=document.activeElement===live[0];
                gBrowser.removeTabs(tabs.filter(tab=>tab.isConnected && !tab.closing));
                done(valid);
            });
        });
    """, True)
    frame(); settle_ui(client)
    client.execute_script("""
        __forgeAuditRestore();
        document.querySelector('.forge-launcher').doCommand();
    """)
    check("Palette exposes Russian names and linked search results to accessibility APIs", """
        const palette=document.getElementById('forge-palette');
        const search=palette.querySelector('input');
        return palette.lang==='ru' && document.getElementById(palette.getAttribute('aria-labelledby')).textContent==='Команды Forge' &&
            search.getAttribute('aria-controls')==='forge-palette-results' &&
            document.getElementById(search.getAttribute('aria-describedby')).getAttribute('role')==='status' &&
            Array.from(palette.querySelectorAll('.forge-result')).every(node=>!!node.getAttribute('aria-label'));
    """)
    client.find_element(By.CSS_SELECTOR, "#forge-palette input").send_keys(Keys.ESCAPE)
    frame()
    check("Escape closes palette and restores keyboard focus", "return !document.getElementById('forge-palette').open && document.activeElement!==document.body;")
    client.set_window_rect(width=800, height=600)
    for scale in (1.25, 1.5, 2):
        client.execute_script("window.browsingContext.fullZoom=arguments[0];", script_args=[scale])
        frame()
        client.execute_script("document.querySelector('.forge-tool[aria-label=" + '"Оформление"' + "]').doCommand(); document.getElementById('forge-geometry-settings').open=true;")
        settle_ui(client)
        check(f"Editor remains usable at {round(scale*100)}% chrome zoom", """
            const editor=document.getElementById('forge-editor');const rect=editor.getBoundingClientRect();
            const valid=rect.left>=0 && rect.right<=innerWidth+1 && rect.top>=0 && rect.bottom<=innerHeight+1 && editor.scrollWidth<=editor.clientWidth+1;
            editor.querySelector('.forge-actions').scrollIntoView({block:'nearest',behavior:'instant'});
            return valid && editor.querySelector('.forge-actions').getBoundingClientRect().bottom<=rect.bottom+1;
        """)
        screenshot(f"editor-zoom-{round(scale*100)}")
        client.execute_script("document.getElementById('forge-editor').close();")
    client.execute_script("window.browsingContext.fullZoom=1;")
    client.set_window_rect(width=1366, height=768)
    client.execute_script("window.fullScreen=true;")
    frame()
    check("Native fullscreen hides the sidebar", "return window.fullScreen && getComputedStyle(document.getElementById('forge-rail')).display==='none';")
    client.execute_script("window.fullScreen=false;")
    frame()
    check("Leaving fullscreen restores the sidebar", "return !window.fullScreen && getComputedStyle(document.getElementById('forge-rail')).display!=='none';")
    # WebDriver deliberately interrupts script execution when a real alert opens.
    # Exercise its native alert API rather than treating that as a UI failure.
    client.execute_script("Services.prompt.asyncAlert(gBrowser.selectedBrowser.browsingContext,Ci.nsIPromptService.MODAL_TYPE_TAB,'Forge audit','Local test prompt; no user data');")
    try:
        text=Wait(client,timeout=5,interval=.05,ignored_exceptions=errors.NoAlertPresentException).until(lambda browser: browser.switch_to_alert().text)
        alert=client.switch_to_alert()
        alert.accept()
        if text == 'Local test prompt; no user data':
            passed.append('Native tab-modal alert opens and can be dismissed')
            print('PASS Native tab-modal alert opens and can be dismissed', flush=True)
        else:
            failures.append({'name':'Native tab-modal alert','details':text})
    except Exception as error:
        failures.append({'name':'Native tab-modal alert','details':str(error)})
    frame()
    check("Find-in-page bar opens with native input and actions", """
        const done=arguments[arguments.length-1];
        gBrowser.getFindBar().then(bar=>{bar.open();done(!bar.hidden && !!bar._findField);bar.close();}).catch(error=>done(String(error)));
    """, True)
    for url in ("about:preferences#privacy", "about:preferences#search", "about:preferences#home", "about:config", "about:support", "about:profiles", "about:debugging#/runtime/this-firefox"):
        client.set_context("content")
        client.navigate(url)
        frame()
        check(f"Internal surface {url} retains shared styling", "return getComputedStyle(document.documentElement).getPropertyValue('--forge-design-version').trim()==='2';")
        if url.startswith('about:preferences'):
            check(f"Settings {url.split('#')[1]} avoid horizontal overflow", """
                const main=document.querySelector('.main-content');
                return main.scrollWidth<=main.clientWidth+1 || {scroll:main.scrollWidth,available:main.clientWidth};
            """)
    client.navigate('about:preferences')
    frame()
    categories=client.execute_script("""
        return Array.from(document.querySelectorAll('#categories moz-page-nav-button[view]'))
            .filter(node=>!node.hidden && getComputedStyle(node).display!=='none' && node.getAttribute('view')!=='paneSearchResults')
            .map(node=>node.getAttribute('view'));
    """)
    for category in categories:
        check(f"Settings category {category} opens without horizontal clipping", """
            const done=arguments[arguments.length-1];let settled=false;
            const expected='CATEGORY';
            const finish=event=>{
                if(event.detail.category!==expected){return;}
                document.removeEventListener('paneshown',finish);settled=true;
                requestAnimationFrame(()=>requestAnimationFrame(()=>{
                    const main=document.querySelector('.main-content');
                    done((main.scrollWidth<=main.clientWidth+1)||{category:expected,scroll:main.scrollWidth,available:main.clientWidth});
                }));
            };
            document.addEventListener('paneshown',finish);
            document.querySelector('moz-page-nav-button[view="'+expected+'"]').shadowRoot.querySelector('button').click();
            setTimeout(()=>{if(!settled){document.removeEventListener('paneshown',finish);done('Category did not open: '+expected);}},5000);
        """.replace('CATEGORY',category), True)
    client.navigate('about:addons')
    check("Extension empty-state icon is bounded instead of filling the page", """
        const done=arguments[arguments.length-1];let attempts=0;
        const timer=setInterval(()=>{
            const icon=document.querySelector('#forge-extensions-empty .forge-icon');
            if(icon){const rect=icon.getBoundingClientRect();clearInterval(timer);done((rect.width>=16 && rect.width<=64 && rect.height<=64)||{width:rect.width,height:rect.height});}
            else if(++attempts>80){clearInterval(timer);done('Empty state not found');}
        },25);
    """, True)
    client.set_context('chrome')
    screenshot('extensions-empty')
    client.set_context('content')
    client.navigate("data:text/html,<title>Forge audit print</title><h1>Local print preview</h1><p>No printing will be submitted.</p>")
    client.set_context("chrome")
    check("Print preview opens and cancels without sending a print job", """
        const done=arguments[arguments.length-1];
        const browser=gBrowser.selectedBrowser;
        PrintUtils.startPrintWindow(browser.browsingContext);
        let attempts=0;
        const timer=setInterval(()=>{
            const dialogs=gBrowser.getTabDialogBox(browser).getTabDialogManager()._dialogs;
            const dialog=dialogs.find(item=>item._frame?.contentDocument?.documentURI.includes('print.html'));
            if(dialog){
                const doc=dialog._frame.contentDocument;
                const valid=doc.defaultView.getComputedStyle(doc.documentElement).getPropertyValue('--forge-design-version').trim()==='2';
                dialog.abort();clearInterval(timer);done(valid);
            }else if(++attempts>120){clearInterval(timer);done('Print preview not found');}
        },50);
    """, True)
    frame()
    # Exercise each additional DevTool against this local test document.
    for tool in ('inspector','webconsole','jsdebugger'):
        check(f"Actual DevTools panel {tool} opens and retains the shared theme", """
            const done=arguments[arguments.length-1];
            const {require}=ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
            const {gDevTools}=require('devtools/client/framework/devtools');
            gDevTools.showToolboxForTab(gBrowser.selectedTab,{toolId:'TOOL'}).then(toolbox=>{
                done(toolbox.currentToolId==='TOOL' && !!toolbox.getPanel('TOOL') &&
                    toolbox.win.getComputedStyle(toolbox.doc.documentElement).getPropertyValue('--forge-design-version').trim()==='2');
            }).catch(error=>done(String(error)));
        """.replace('TOOL',tool), True)
    client.execute_async_script("""
        const done=arguments[arguments.length-1];
        const {require}=ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
        const {gDevTools}=require('devtools/client/framework/devtools');
        const toolbox=gDevTools.getToolboxForTab(gBrowser.selectedTab);
        if(toolbox){toolbox.destroy().then(()=>done(true));}else{done(true);}
    """)
    client.set_context('content')
    client.navigate('about:downloads')
    client.set_context('chrome')
    check("A genuinely failed local download remains represented by the native backend", """
        const done=arguments[arguments.length-1];
        (async()=>{
            const {Downloads}=ChromeUtils.importESModule('resource://gre/modules/Downloads.sys.mjs');
            const directory=Services.dirsvc.get('ProfD',Ci.nsIFile);
            const source=directory.clone();source.append('nonexistent-forge-audit-source');
            const target=directory.clone();target.append('forge-audit-failed-download');
            const download=await Downloads.createDownload({source:Services.io.newFileURI(source).spec,target:target.path});
            window.__forgeAuditDownload=download;
            await (await Downloads.getList(Downloads.ALL)).add(download);
            try{await download.start();}catch{}
            done(!!download.error && !download.succeeded);
        })().catch(error=>done(String(error)));
    """, True)
    client.set_context('content')
    check("Failed download UI remains visible and does not show the empty state", """
        const done=arguments[arguments.length-1];let attempts=0;
        const timer=setInterval(()=>{
            const row=document.querySelector('#downloadsListBox richlistitem');
            if(row){clearInterval(timer);done(getComputedStyle(row).display!=='none' && getComputedStyle(document.getElementById('downloadsListEmptyDescription')).display==='none');}
            else if(++attempts>80){clearInterval(timer);done(false);}
        },25);
    """, True)
    client.set_context('chrome')
    client.execute_async_script("""
        const done=arguments[arguments.length-1];
        const {Downloads}=ChromeUtils.importESModule('resource://gre/modules/Downloads.sys.mjs');
        Downloads.getList(Downloads.ALL).then(list=>list.remove(__forgeAuditDownload))
            .then(()=>__forgeAuditDownload.finalize(true)).then(()=>{delete window.__forgeAuditDownload;done(true);});
    """)
    client.set_context('content')
    client.navigate('data:text/html,<title>Forge audit navigation A</title><h1>Page A</h1>')
    client.set_context('chrome')
    client.execute_script("window.__forgeAuditHistoryA=gBrowser.selectedBrowser.currentURI.spec;")
    client.set_context('content')
    client.navigate('data:text/html,<title>Forge audit navigation B</title><h1>Page B</h1>')
    client.set_context('chrome')
    client.execute_script("window.__forgeAuditHistoryB=gBrowser.selectedBrowser.currentURI.spec;")
    client.execute_script("document.getElementById('back-button').doCommand();")
    # Observe from browser chrome: a callback installed in page B is destroyed
    # when Back replaces its document, causing a false timeout on slower hosts.
    check("Native Back button navigates the actual page history", """
        const done=arguments[arguments.length-1];let attempts=0;
        const timer=setInterval(()=>{
            const browser=gBrowser.selectedBrowser;
            if(browser.contentTitle==='Forge audit navigation A' && browser.currentURI.spec===__forgeAuditHistoryA){clearInterval(timer);done(true);}
            else if(++attempts>200){clearInterval(timer);done({title:browser.contentTitle,uri:browser.currentURI.spec});}
        },25);
    """, True)
    client.set_context('chrome')
    client.execute_script("document.getElementById('forward-button').doCommand();")
    check("Native Forward button navigates the actual page history", """
        const done=arguments[arguments.length-1];let attempts=0;
        const timer=setInterval(()=>{
            const browser=gBrowser.selectedBrowser;
            if(browser.contentTitle==='Forge audit navigation B' && browser.currentURI.spec===__forgeAuditHistoryB){clearInterval(timer);done(true);}
            else if(++attempts>200){clearInterval(timer);done({title:browser.contentTitle,uri:browser.currentURI.spec});}
        },25);
    """, True)
    client.execute_script("delete window.__forgeAuditHistoryA;delete window.__forgeAuditHistoryB;")
    client.set_context('chrome')
    main_window=client.current_chrome_window_handle
    for private in (False,True):
        before=set(client.chrome_window_handles)
        client.execute_async_script("""
            const done=arguments[arguments.length-1];
            const win=OpenBrowserWindow({private:arguments[0]});let attempts=0;
            const timer=setInterval(()=>{
                if(win.document.documentElement.getAttribute('forge-ready')==='true'){clearInterval(timer);done(true);}
                else if(++attempts>200){clearInterval(timer);done(false);}
            },25);
        """, script_args=[private])
        other=next(handle for handle in client.chrome_window_handles if handle not in before)
        client.switch_to_window(other)
        client.execute_script("""
            const theme=JSON.parse(Services.prefs.getStringPref('forge.theme','{}'));
            Object.assign(theme,{appearance:'glass',sidebarSide:'right',iconSize:20});
            Services.prefs.setStringPref('forge.theme',JSON.stringify(theme));
        """)
        frame()
        label='Private' if private else 'Normal'
        check(f"{label} new window applies extended theme settings", """
            return document.documentElement.getAttribute('forge-sidebar-side')==='right' &&
                getComputedStyle(document.querySelector('.forge-launcher > svg')).width==='20px';
        """)
        client.switch_to_window(main_window)
        frame()
        check(f"Theme changes from a {label.lower()} window reach the original window", """
            return document.documentElement.getAttribute('forge-appearance')==='glass' &&
                document.documentElement.getAttribute('forge-sidebar-side')==='right';
        """)
        client.switch_to_window(other)
        client.close_chrome_window()
        client.switch_to_window(main_window)
        client.execute_script('__forgeAuditRestore();')
    frame()
    client.execute_script("""
        __forgeAuditRestore();Services.prefs.clearUserPref('ui.prefersReducedMotion');
        delete window.__forgeAuditPrefs;delete window.__forgeAuditRestore;delete window.__forgeAuditConcurrentTheme;
    """)
    return failures
