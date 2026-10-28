# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
from ui_wait import settle_ui


def run_transfer_checks(client, results, passed):
    def check(name, script):
        result=client.execute_script(script)
        if result is not True:
            raise AssertionError(f'{name}: {result!r}')
        passed.append(name);print(f'PASS {name}',flush=True)
    def frame():
        client.execute_async_script('const done=arguments[arguments.length-1];requestAnimationFrame(()=>requestAnimationFrame(()=>done(true)));')
    client.set_context('chrome')
    client.execute_async_script("""
        const done=arguments[arguments.length-1];
        window.__transferOriginal=gBrowser.selectedTab;
        let created;
        const observer={observe(win){if(win!==created){return;}Services.obs.removeObserver(observer,'browser-delayed-startup-finished');
            win.requestAnimationFrame(()=>win.requestAnimationFrame(()=>done(true)));}};
        Services.obs.addObserver(observer,'browser-delayed-startup-finished');
        window.__transferDestination=created=OpenBrowserWindow();
    """)
    client.execute_script("""
        window.__transferCreated=[];
        const {SessionStore}=ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        window.__transferMake=(token,container=0)=>{
            const tab=gBrowser.addTrustedTab('about:blank',{userContextId:container});
            SessionStore.setCustomTabValue(tab,'forge.test.transfer',token);__transferCreated.push(tab);return tab;
        };
        window.__transferDrop=(node)=>{
            const data=new DataTransfer();node.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:data}));
            __transferDestination.document.querySelector('.forge-tab[selected]').dispatchEvent(new __transferDestination.DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:data}));
        };
        window.__transferTab=__transferMake('ordinary',2);gBrowser.selectedTab=__transferTab;
    """)
    frame();settle_ui(client)
    check('Cross-window drops reject external fake payloads', """
        const before=__transferDestination.gBrowser.tabs.length,data=new DataTransfer();data.setData('application/x-forge-tab','fake');
        __transferDestination.document.querySelector('.forge-tab[selected]').dispatchEvent(new __transferDestination.DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:data}));
        return __transferDestination.gBrowser.tabs.length===before && __transferTab.isConnected;
    """)
    client.execute_script("__transferDrop(document.querySelector('.forge-tab[selected]'));")
    frame();settle_ui(client)
    check('Native cross-window tab adoption preserves container and SessionStore data', """
        const {SessionStore}=ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        const moved=Array.from(__transferDestination.gBrowser.tabs).find(tab=>SessionStore.getCustomTabValue(tab,'forge.test.transfer')==='ordinary');
        return (!!moved && !__transferTab.isConnected && moved.getAttribute('usercontextid')==='2' && moved.linkedBrowser.currentURI.spec==='about:blank') ||
            {oldConnected:__transferTab.isConnected,destination:Array.from(__transferDestination.gBrowser.tabs,tab=>({token:SessionStore.getCustomTabValue(tab,'forge.test.transfer'),container:tab.getAttribute('usercontextid'),url:tab.linkedBrowser.currentURI.spec}))};
    """)
    client.execute_script("""
        const first=__transferMake('group-first'),second=__transferMake('group-second');
        window.__transferGroup=gBrowser.addTabGroup([first,second],{label:'Рабочая группа',insertBefore:first});gBrowser.selectedTab=first;
    """)
    frame();settle_ui(client)
    check('Native groups get accessible sidebar controls', """
        const header=document.querySelector('[data-forge-group="'+__transferGroup.id+'"]');
        return !!header && header.getAttribute('aria-expanded')==='true' && header.getAttribute('aria-label').includes('Рабочая группа');
    """)
    client.execute_script('''document.querySelector('[data-forge-group="'+__transferGroup.id+'"]').doCommand();''')
    frame();settle_ui(client)
    check('Group collapse changes native state and keeps the group entry available', """
        const header=document.querySelector('[data-forge-group="'+__transferGroup.id+'"]');
        return __transferGroup.collapsed && header.getAttribute('aria-expanded')==='false' && header.getClientRects().length>0;
    """)
    client.execute_script("__transferGroup.collapsed=false;")
    frame();settle_ui(client)
    client.execute_script('''__transferDrop(document.querySelector('[data-forge-group="'+__transferGroup.id+'"]'));''')
    frame();settle_ui(client)
    check('Native group adoption preserves group name, member order and destination workspace', """
        const {SessionStore}=ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        const dest=__transferDestination,group=dest.gBrowser.tabGroups.find(group=>group.label==='Рабочая группа');
        const active=JSON.parse(SessionStore.getCustomWindowValue(dest,'forge.workspace')).active;
        return !!group && JSON.stringify(group.tabs.map(tab=>SessionStore.getCustomTabValue(tab,'forge.test.transfer')))===JSON.stringify(['group-first','group-second']) &&
            group.tabs.every(tab=>SessionStore.getCustomTabValue(tab,'forge.workspace')===active);
    """)
    client.execute_script("const first=__transferMake('split-first'),second=__transferMake('split-second');gBrowser.addTabSplitView([first,second]);gBrowser.selectedTab=second;")
    frame();settle_ui(client)
    client.execute_script("__transferDrop(document.querySelector('.forge-tab[selected]'));")
    frame();settle_ui(client)
    check('Cross-window split adoption preserves both native page panels', """
        const {SessionStore}=ChromeUtils.importESModule('moz-src:///browser/components/sessionstore/SessionStore.sys.mjs');
        const moved=Array.from(__transferDestination.gBrowser.tabs).filter(tab=>SessionStore.getCustomTabValue(tab,'forge.test.transfer').startsWith('split-'));
        return moved.length===2 && !!moved[0].splitview && moved[0].splitview===moved[1].splitview && !moved[0].group;
    """)
    client.execute_async_script("""
        const done=arguments[arguments.length-1];let created;
        const observer={observe(win){if(win!==created){return;}Services.obs.removeObserver(observer,'browser-delayed-startup-finished');done(true);}};
        Services.obs.addObserver(observer,'browser-delayed-startup-finished');
        window.__transferPrivate=created=OpenBrowserWindow({private:true});
    """)
    check('Native transfers never cross normal/private browsing boundaries', """
        const {canTransfer}=ChromeUtils.importESModule('chrome://browser/content/forge/TabTransfer.sys.mjs');
        return !canTransfer(gBrowser.selectedTab,__transferPrivate);
    """)
    client.execute_script("""
        __transferPrivate.close();__transferDestination.close();
        gBrowser.removeTabs(__transferCreated.filter(tab=>tab.isConnected),{animate:false});
        gBrowser.selectedTab=__transferOriginal;
        for(const key of ['__transferOriginal','__transferDestination','__transferPrivate','__transferCreated','__transferMake','__transferDrop','__transferTab','__transferGroup']){delete window[key];}
    """)
    frame();settle_ui(client)
    return []
