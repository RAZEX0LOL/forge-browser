# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Regress process-actor teardown, without suppressing console diagnostics."""
from ui_wait import settle_ui


def run_devtools_checks(client, results, passed):
    client.set_context('chrome')
    client.execute_script("""
        window.__forgeActorErrors=[];
        window.__forgeActorListener={observe(message){
            if(message.message.includes("No such JSProcessActor")){
                __forgeActorErrors.push(message.message);
            }
        }};
        Services.console.registerListener(__forgeActorListener);
    """)
    try:
        for tool in ('inspector','webconsole','netmonitor','jsdebugger'):
            result=client.execute_async_script("""
                const done=arguments[arguments.length-1],toolId=arguments[0];
                (async()=>{
                    const {require}=ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
                    const {gDevTools}=require('devtools/client/framework/devtools');
                    for(let cycle=0;cycle<2;cycle++){
                        const tab=gBrowser.addTrustedTab('about:blank');
                        try{
                            gBrowser.selectedTab=tab;
                            const toolbox=await gDevTools.showToolboxForTab(tab,{toolId});
                            if(toolbox.currentToolId!==toolId){throw new Error('Wrong DevTools panel');}
                            await gDevTools.closeToolboxForTab(tab);
                        }finally{
                            await gDevTools.closeToolboxForTab(tab);
                            gBrowser.removeTab(tab,{animate:false});
                        }
                    }
                    done(true);
                })().catch(error=>done(String(error)));
            """,script_args=[tool])
            if result is not True:
                raise AssertionError(f'{tool} teardown: {result!r}')
            settle_ui(client)
            errors=client.execute_script('return __forgeActorErrors;')
            if errors:
                raise AssertionError(f'{tool} generated process actor errors: {errors}')
            name=f'DevTools {tool} reopens and closes twice without missing process actors'
            passed.append(name)
            print(f'PASS {name}',flush=True)
        result=client.execute_async_script("""
            const done=arguments[arguments.length-1];
            (async()=>{
                const {require}=ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
                const {gDevTools}=require('devtools/client/framework/devtools');
                const tabs=[gBrowser.addTrustedTab('about:blank'),gBrowser.addTrustedTab('about:blank')];
                try{
                    for(const tab of tabs){await gDevTools.showToolboxForTab(tab,{toolId:'webconsole'});}
                    await gDevTools.closeToolboxForTab(tabs[0]);
                    const remaining=gDevTools.getToolboxForTab(tabs[1]);
                    await remaining.selectTool('inspector');
                    if(remaining.currentToolId!=='inspector'){throw new Error('Other toolbox stopped working');}
                    await Promise.all(tabs.map(tab=>gDevTools.closeToolboxForTab(tab)));
                    done(true);
                }finally{
                    await Promise.all(tabs.map(tab=>gDevTools.closeToolboxForTab(tab)));
                    gBrowser.removeTabs(tabs,{animate:false});
                }
            })().catch(error=>done(String(error)));
        """)
        if result is not True:
            raise AssertionError(f'Concurrent toolbox teardown: {result!r}')
        settle_ui(client)
        if client.execute_script('return __forgeActorErrors.length;'):
            raise AssertionError('Concurrent toolbox teardown generated missing actor errors')
        name='Closing one toolbox keeps another toolbox operational without actor errors'
        passed.append(name)
        print(f'PASS {name}',flush=True)
        result=client.execute_async_script("""
            const done=arguments[arguments.length-1];
            const {require}=ChromeUtils.importESModule('resource://devtools/shared/loader/Loader.sys.mjs');
            const {gDevTools}=require('devtools/client/framework/devtools');
            if(gDevTools.getToolboxes().length){done('Unexpected leftover toolbox');return;}
            let attempts=0;
            const timer=setInterval(()=>{
                try{ChromeUtils.getAllDOMProcesses()[0].getActor('DevToolsProcess');}
                catch(error){clearInterval(timer);done(error.name==='NotFoundError');return;}
                if(++attempts>=100){clearInterval(timer);done('Process actor remained registered');}
            },50);
        """)
        if result is not True:
            raise AssertionError(f'Actor cleanup: {result!r}')
        name='Last toolbox closure unregisters the process actor after cleanup'
        passed.append(name)
        print(f'PASS {name}',flush=True)
    finally:
        client.execute_script("""
            Services.console.unregisterListener(__forgeActorListener);
            delete window.__forgeActorListener;delete window.__forgeActorErrors;
        """)
