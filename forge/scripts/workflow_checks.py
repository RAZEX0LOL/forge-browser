# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
from workload_server import WorkloadServer
from marionette_driver import Wait, errors


def run_workflow_checks(client, results, passed):
    def check(name,script,asynchronous=False):
        result=(client.execute_async_script if asynchronous else client.execute_script)(script)
        if result is not True:
            raise AssertionError(f'{name}: {result!r}')
        passed.append(name);print(f'PASS {name}',flush=True)
    with WorkloadServer() as server:
        client.set_context('content')
        original_handle=client.current_window_handle
        handles=set(client.window_handles)
        client.set_context('chrome')
        client.execute_script("window.__workflowOriginal=gBrowser.selectedTab;window.__workflowTab=gBrowser.addTrustedTab('about:blank');gBrowser.selectedTab=__workflowTab;")
        client.set_context('content')
        client.switch_to_window(next(handle for handle in client.window_handles if handle not in handles))
        client.navigate(server.url)
        Wait(client,timeout=15,ignored_exceptions=(errors.JavascriptException,)).until(
            lambda c:c.execute_script("return !!window.wrappedJSObject.workloadReady;"))
        check('Interactive page loads real API data and renders 1000 records', "const done=arguments[arguments.length-1];window.wrappedJSObject.workloadReady.then(()=>done(document.querySelectorAll('#items li').length===1000));",True)
        check('DOM/filter/canvas/history workload preserves local state', "const done=arguments[arguments.length-1];window.wrappedJSObject.runWorkload().then(result=>done(result.rows===1000 && result.persistent && location.hash==='#updated'));",True)
        client.set_context('chrome')
        check('Network resource observer attaches to the real toolbox', """
            const done=arguments[arguments.length-1];
            window.__workflowErrors=[];window.__workflowListener={observe(message){
                if(message.message.includes('No such JSProcessActor') || (message.message.includes('defaultView') && message.message.includes('null'))){__workflowErrors.push(message.message);}
            }};Services.console.registerListener(__workflowListener);
            const {require}=ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
            const {gDevTools}=require('devtools/client/framework/devtools');
            gDevTools.showToolboxForTab(gBrowser.selectedTab,{toolId:'netmonitor'}).then(async toolbox=>{
                window.__workflowToolbox=toolbox;window.__workflowNetworkSeen=false;window.__workflowResources=[];
                window.__workflowNetworkCallback=resources=>{window.__workflowResources.push(...resources.map(resource=>({url:resource.url,keys:Object.keys(resource)})));if(resources.some(resource=>resource.url?.endsWith('/api/items'))){window.__workflowNetworkSeen=true;}};
                const command=toolbox.commands.resourceCommand;
                await command.watchResources([command.TYPES.NETWORK_EVENT],{onAvailable:__workflowNetworkCallback,ignoreExistingResources:true});
                done(true);
            }).catch(error=>done(String(error)));
        """,True)
        client.set_context('content')
        check('Real page API refresh remains functional with Network Monitor open', "const done=arguments[arguments.length-1];window.wrappedJSObject.fetch('/api/items').then(r=>r.json()).then(rows=>done(rows.length===1000));",True)
        client.execute_script("document.getElementById('frames').click();")
        client.set_context('chrome')
        check('DevTools backend receives actual network resources from the page', """
            const done=arguments[arguments.length-1];let attempts=0;
            const timer=setInterval(()=>{if(__workflowNetworkSeen){clearInterval(timer);done(true);}
                else if(++attempts>100){clearInterval(timer);done({resources:__workflowResources,tool:__workflowToolbox.currentToolId,url:gBrowser.selectedBrowser.currentURI.spec});}},50);
        """,True)
        check('Detached document lifecycle notifications do not crash DevTools', """
            const detached=document.implementation.createHTMLDocument('Detached fixture');
            Services.obs.notifyObservers(detached,'chrome-page-shown');Services.obs.notifyObservers(detached,'chrome-page-hidden');
            return __workflowErrors.length===0 && __workflowToolbox.currentToolId==='netmonitor';
        """)
        client.execute_async_script("""
            const done=arguments[arguments.length-1];(async()=>{
                for(const tool of ['inspector','webconsole','jsdebugger','netmonitor']){await __workflowToolbox.selectTool(tool);}
                const command=__workflowToolbox.commands.resourceCommand;
                command.unwatchResources([command.TYPES.NETWORK_EVENT],{onAvailable:__workflowNetworkCallback});
                await __workflowToolbox.destroy();done(true);
            })().catch(error=>done(String(error)));
        """)
        client.set_context('content');client.refresh()
        check('Reload restores the interactive page and its localStorage state', "const done=arguments[arguments.length-1];window.wrappedJSObject.workloadReady.then(()=>done(localStorage.getItem('forge-fixture')==='persistent' && document.querySelectorAll('#items li').length===1000));",True)
        client.set_context('chrome')
        check('Page/frame teardown leaves no targeted DevTools actor or detached-view errors', "return __workflowErrors.length===0;")
        client.execute_script("""
            Services.console.unregisterListener(__workflowListener);gBrowser.removeTab(__workflowTab,{animate:false});gBrowser.selectedTab=__workflowOriginal;
            for(const key of ['__workflowOriginal','__workflowTab','__workflowErrors','__workflowListener','__workflowToolbox','__workflowNetworkSeen','__workflowNetworkCallback']){delete window[key];}
        """)
        client.switch_to_window(original_handle)
    return []
