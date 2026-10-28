# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Appearance editor button-by-button regressions, only in disposable profiles."""
import base64
from marionette_driver.by import By
from marionette_driver.keys import Keys
from ui_wait import settle_ui


def run_editor_checks(client, results, passed):
    failures=[]
    def check(name, script, asynchronous=False):
        try:
            result=(client.execute_async_script if asynchronous else client.execute_script)(script)
        except Exception as error:
            result=str(error)
        if result is True:
            passed.append(name);print(f"PASS {name}",flush=True)
        else:
            failures.append({'name':name,'details':result});print(f"FAIL {name}: {result!r}",flush=True)
    def frame():
        client.execute_async_script("const done=arguments[arguments.length-1];requestAnimationFrame(()=>requestAnimationFrame(()=>done(true)));")
    def open_editor():
        client.execute_script("if(!document.getElementById('forge-editor').open){document.getElementById('forge-hub-button').doCommand();document.querySelector('.forge-hub-action[data-action=\"Оформление\"]').doCommand();}")
        settle_ui(client)
    def click(id):
        client.find_element(By.ID,id).click();frame()
    def screenshot(name):
        settle_ui(client)
        (results/f'editor-{name}.png').write_bytes(base64.b64decode(client.screenshot()))
    client.set_context('chrome')
    client.execute_script("""
        window.__editorPrefs=['forge.theme','forge.customCSS','forge.customCSS.enabled','forge.shortcuts.palette','forge.tools','forge.tools.order'];
        window.__editorSnapshot=()=>Object.fromEntries(__editorPrefs.map(name=>[name,Services.prefs.prefHasUserValue(name)?
            (name==='forge.customCSS.enabled'?Services.prefs.getBoolPref(name):Services.prefs.getStringPref(name)):null]));
        window.__editorOriginal=__editorSnapshot();
        window.__editorRestore=()=>{for(const [name,value] of Object.entries(__editorOriginal)){
            if(value===null){Services.prefs.clearUserPref(name);}else if(typeof value==='boolean'){Services.prefs.setBoolPref(name,value);}else{Services.prefs.setStringPref(name,value);}
        }};
        window.__editorInput=(selector,value)=>{const node=document.querySelector(selector);node.value=value;node.dispatchEvent(new Event('input',{bubbles:true}));};
    """)
    open_editor()
    screenshot('main')
    check("Appearance actions use explicit labels and native buttons", """
        const editor=document.getElementById('forge-editor');
        return editor.getAttribute('aria-labelledby')==='forge-editor-title' &&
            Array.from(editor.querySelectorAll('button')).every(button=>button.namespaceURI==='http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul' &&
                !!(button.getAttribute('label')||button.getAttribute('aria-label'))) &&
            document.getElementById('forge-theme-reset').getAttribute('label')==='Сбросить тему';
    """)
    check("Appearance fields expose names and CSS safety guidance to accessibility APIs", """
        const editor=document.getElementById('forge-editor');
        return editor.lang==='ru' && Array.from(editor.querySelectorAll('input,select,textarea')).every(node=>!!node.getAttribute('aria-label')) &&
            document.querySelector('#forge-editor-advanced input[type="checkbox"]').getAttribute('aria-describedby')==='forge-css-warning' &&
            document.querySelector('#forge-editor-advanced textarea').getAttribute('aria-describedby').includes('forge-css-warning');
    """)
    client.execute_script("window.__editorBeforeNoop=JSON.stringify(__editorSnapshot());")
    click('forge-theme-save')
    check("Saving an unchanged editor does not rewrite preferences", "return !document.getElementById('forge-editor').open && JSON.stringify(__editorSnapshot())===__editorBeforeNoop;")
    open_editor()
    for preset in ('default','amoled','glass','compact','contrast'):
        check(f"Preset {preset} fills all theme fields", """
            const {THEME_PRESETS}=ChromeUtils.importESModule('chrome://browser/content/forge/core.sys.mjs');
            const select=document.getElementById('forge-theme-preset');select.value='__PRESET__';select.dispatchEvent(new Event('change',{bubbles:true}));
            const expected=THEME_PRESETS['__PRESET__'];
            return select.value==='__PRESET__' && Array.from(document.querySelectorAll('#forge-editor [data-setting]')).every(node=>
                String(node.value)===String(expected[node.getAttribute('data-setting')]));
        """.replace('__PRESET__',preset))
    check("Manual changes clear the selected preset and update numeric labels", """
        __editorInput('#forge-editor [data-setting="radius"]','7');
        const range=document.querySelector('#forge-editor [data-setting="radius"]');
        return document.getElementById('forge-theme-preset').value==='' && range.getAttribute('aria-valuetext')==='7 px' &&
            range.parentElement.querySelector('output').value==='7 px';
    """)
    check("AMOLED disables Glass-only fields with an explanation", """
        const appearance=document.querySelector('#forge-editor [data-setting="appearance"]');appearance.value='amoled';appearance.dispatchEvent(new Event('change',{bubbles:true}));
        return ['glassOpacity','blur'].every(key=>document.querySelector('#forge-editor [data-setting="'+key+'"]').disabled) &&
            document.querySelector('#forge-glass-settings .forge-editor-help').textContent.includes('Glass');
    """)
    click('forge-theme-cancel');open_editor()
    client.execute_script("window.__editorBeforeInvalid=JSON.stringify(__editorSnapshot());__editorInput('#forge-accent-hex','oops');")
    click('forge-theme-save')
    check("Invalid HEX reports inline error without saving or opening an alert", """
        return document.getElementById('forge-editor').open && document.getElementById('forge-editor-feedback').getAttribute('role')==='alert' &&
            document.activeElement.id==='forge-accent-hex' && JSON.stringify(__editorSnapshot())===__editorBeforeInvalid;
    """)
    client.execute_script("__editorInput('#forge-accent-hex','ABCDEF');")
    client.find_element(By.ID,'forge-accent-hex').send_keys(Keys.RETURN)
    frame()
    check("HEX input accepts six digits and Enter saves once", "return !document.getElementById('forge-editor').open && JSON.parse(Services.prefs.getStringPref('forge.theme')).accent==='#abcdef';")
    open_editor();click('forge-theme-undo')
    check("Undo restores the exact saved snapshot and disables itself", "return JSON.stringify(__editorSnapshot())===__editorBeforeInvalid && document.getElementById('forge-theme-undo').disabled;")
    client.execute_script("document.getElementById('forge-layout-settings').open=true;__editorInput('#forge-palette-shortcut','R');")
    click('forge-theme-save')
    check("Reserved shortcut validation focuses its field without committing", "return document.getElementById('forge-editor').open && document.activeElement.id==='forge-palette-shortcut' && document.getElementById('forge-editor-feedback').textContent.includes('кроме R');")
    client.execute_script("__editorInput('#forge-palette-shortcut','K');document.getElementById('forge-editor-advanced').open=true;__editorInput('#forge-editor-advanced textarea','x'.repeat(100001));")
    click('forge-theme-save')
    check("Oversized CSS is rejected without changing saved data", "return document.getElementById('forge-editor').open && document.getElementById('forge-editor-feedback').textContent.includes('100 000') && JSON.stringify(__editorSnapshot())===__editorBeforeInvalid;")
    click('forge-theme-cancel');open_editor()
    client.execute_script("""
        window.__editorBeforePreview=JSON.stringify(__editorSnapshot());
        __editorInput('#forge-accent-hex','#112233');
        const side=document.querySelector('#forge-editor [data-setting="sidebarSide"]');side.value='right';side.dispatchEvent(new Event('change',{bubbles:true}));
    """)
    click('forge-theme-preview')
    check("Preview visibly applies theme and activates its return action", "return document.documentElement.getAttribute('forge-sidebar-side')==='right' && !document.getElementById('forge-theme-revert').disabled && document.getElementById('forge-editor-feedback').textContent.includes('Предпросмотр');")
    check("Active preview follows live slider edits without saving the draft", """
        __editorInput('#forge-editor [data-setting="radius"]','5');
        return JSON.parse(Services.prefs.getStringPref('forge.theme')).radius===5 && !document.getElementById('forge-theme-revert').disabled;
    """)
    click('forge-theme-revert')
    check("Return theme ends preview but keeps the edited draft", "return JSON.stringify(__editorSnapshot())===__editorBeforePreview && document.getElementById('forge-accent-hex').value.toLowerCase()==='#112233' && document.getElementById('forge-theme-revert').disabled;")
    click('forge-theme-reset')
    check("Reset is staged and does not erase CSS, buttons or current settings", "return document.getElementById('forge-editor').open && JSON.stringify(__editorSnapshot())===__editorBeforePreview && document.getElementById('forge-theme-preset').value==='default';")
    click('forge-theme-preview')
    client.find_element(By.ID,'forge-accent-hex').send_keys(Keys.ESCAPE)
    frame()
    check("Escape cancels preview and closes without writing the draft", "return !document.getElementById('forge-editor').open && JSON.stringify(__editorSnapshot())===__editorBeforePreview;")
    open_editor()
    click('forge-theme-cancel');open_editor()
    client.execute_script("""
        document.getElementById('forge-editor').close();
        Services.prefs.setStringPref('forge.theme',JSON.stringify({appearance:'glass',accent:'#123456'}));
        Services.prefs.setStringPref('forge.customCSS','/* preserved CSS */');
        Services.prefs.setStringPref('forge.shortcuts.palette','J');
        window.__editorResetFixture=JSON.stringify(__editorSnapshot());
    """)
    frame();open_editor();click('forge-theme-reset');click('forge-theme-save')
    check("Saving a reset applies defaults while preserving CSS and keyboard layout", """
        const theme=JSON.parse(Services.prefs.getStringPref('forge.theme'));
        return theme.accent==='#a4efce' && theme.radius===12 && theme.appearance==='amoled' &&
            Services.prefs.getStringPref('forge.customCSS')==='/* preserved CSS */' && Services.prefs.getStringPref('forge.shortcuts.palette')==='J';
    """)
    open_editor();click('forge-theme-undo')
    check("A saved theme reset can be undone exactly", "return JSON.stringify(__editorSnapshot())===__editorResetFixture;")
    click('forge-theme-cancel');client.execute_script('__editorRestore();');open_editor()
    client.execute_script("""
        __editorInput('#forge-accent-hex','#223344');
        window.__editorExternal=JSON.stringify({appearance:'glass',accent:'#aabbcc'});
        Services.prefs.setStringPref('forge.theme',__editorExternal);
    """)
    click('forge-theme-save')
    check("External edits block stale saves rather than overwriting another window", "return document.getElementById('forge-editor').open && !document.getElementById('forge-editor-reload').hidden && Services.prefs.getStringPref('forge.theme')===__editorExternal;")
    click('forge-editor-reload')
    check("Reload current settings replaces the stale draft", "return document.getElementById('forge-accent-hex').value.toLowerCase()==='#aabbcc' && document.getElementById('forge-editor-reload').hidden;")
    client.execute_script("__editorInput('#forge-accent-hex','#556677');")
    click('forge-theme-save')
    client.execute_script("window.__editorOtherCommit=JSON.stringify({appearance:'amoled',accent:'#ccaabb'});Services.prefs.setStringPref('forge.theme',__editorOtherCommit);")
    open_editor()
    check("Undo cannot overwrite changes committed after this window saved", """
        const button=document.getElementById('forge-theme-undo');
        const disabled=button.disabled;button.doCommand();
        return disabled && Services.prefs.getStringPref('forge.theme')===__editorOtherCommit;
    """)
    click('forge-theme-cancel')
    client.execute_script('__editorRestore();');open_editor()
    client.execute_script("document.getElementById('forge-layout-settings').open=true;")
    check("Every dock row can move up and down without losing keyboard focus", """
        const dock=document.getElementById('forge-dock-settings');
        const original=Array.from(dock.children);
        for(const row of original){
            const index=Array.from(dock.children).indexOf(row);
            const first=index===0?'down':'up',second=index===0?'up':'down';
            row.querySelector('[data-move="'+first+'"]').doCommand();
            if(Array.from(dock.children).indexOf(row)!==index+(index===0?1:-1)){return false;}
            row.querySelector('[data-move="'+second+'"]').doCommand();
            if(Array.from(dock.children).indexOf(row)!==index || !row.contains(document.activeElement)){return false;}
        }
        return true;
    """)
    client.execute_script("""
        const row=document.querySelector('#forge-dock-settings [data-tool="network"]');
        row.querySelector('[data-move="up"]').doCommand();row.querySelector('[data-move="up"]').doCommand();
        document.querySelector('#forge-dock-settings [data-tool="terminal"] input').checked=false;
    """)
    check("Dock move controls disable impossible boundary moves", """return document.querySelector('#forge-dock-settings').firstElementChild.getAttribute('data-tool')==='network' && document.querySelector('#forge-dock-settings').firstElementChild.querySelector('[data-move="up"]').disabled && document.querySelector('#forge-dock-settings').lastElementChild.querySelector('[data-move="down"]').disabled;""")
    click('forge-theme-save');open_editor()
    check("Disabled dock items retain their full saved order on reopening", """
        const order=JSON.parse(Services.prefs.getStringPref('forge.tools.order'));
        return order[0]==='network' && JSON.stringify(Array.from(document.querySelector('#forge-dock-settings').children,row=>row.getAttribute('data-tool')))===JSON.stringify(order) &&
            !document.querySelector('#forge-dock-settings [data-tool="terminal"] input').checked;
    """)
    client.execute_script("document.getElementById('forge-settings-transfer').open=true;")
    client.execute_script("document.querySelectorAll('#forge-settings-transfer button')[0].doCommand();")
    check("Export version 2 includes theme, CSS, dock order and keyboard shortcut", """
        const data=JSON.parse(document.querySelector('#forge-settings-transfer textarea').value);
        return data.version===2 && data.layout.toolOrder[0]==='network' && !data.layout.tools.includes('terminal') && !('enabled' in data);
    """)
    check("Copy JSON uses the generated text (clipboard mocked)", """
        const done=arguments[arguments.length-1], clipboard=navigator.clipboard;
        const descriptor=Object.getOwnPropertyDescriptor(clipboard,'writeText');let copied;
        Object.defineProperty(clipboard,'writeText',{configurable:true,value:async text=>{copied=text;}});
        document.getElementById('forge-settings-copy').doCommand();
        Promise.resolve().then(()=>{
            if(descriptor){Object.defineProperty(clipboard,'writeText',descriptor);}else{delete clipboard.writeText;}
            done(copied===document.querySelector('#forge-settings-transfer textarea').value);
        });
    """,True)
    check("Clipboard failure offers manual selection instead of losing export", """
        const done=arguments[arguments.length-1], clipboard=navigator.clipboard;
        const descriptor=Object.getOwnPropertyDescriptor(clipboard,'writeText');
        Object.defineProperty(clipboard,'writeText',{configurable:true,value:async()=>{throw new Error('mock clipboard denial');}});
        document.getElementById('forge-settings-copy').doCommand();
        Promise.resolve().then(()=>{
            if(descriptor){Object.defineProperty(clipboard,'writeText',descriptor);}else{delete clipboard.writeText;}
            const field=document.querySelector('#forge-settings-transfer textarea');
            done(field.selectionStart===0 && field.selectionEnd===field.value.length);
        });
    """,True)
    check("Malformed import leaves every draft field intact", """
        const before=document.getElementById('forge-accent-hex').value;
        document.querySelector('#forge-settings-transfer textarea').value='{broken';document.querySelectorAll('#forge-settings-transfer button')[1].doCommand();
        return document.getElementById('forge-accent-hex').value===before && document.querySelector('#forge-settings-transfer [role="alert"]').textContent.includes('JSON');
    """)
    check("Version 1 import remains supported and never enables CSS", """
        document.querySelector('#forge-settings-transfer textarea').value=JSON.stringify({version:1,theme:{appearance:'glass'},css:'/* imported test */',enabled:true});
        document.querySelectorAll('#forge-settings-transfer button')[1].doCommand();
        return document.querySelector('#forge-editor [data-setting="appearance"]').value==='glass' && !document.querySelector('#forge-editor-advanced input[type="checkbox"]').checked;
    """)
    check("Version 2 import restores full dock layout and shortcut into the draft", """
        const {TOOL_IDS}=ChromeUtils.importESModule('chrome://browser/content/forge/core.sys.mjs');
        const order=[...TOOL_IDS].reverse();
        document.querySelector('#forge-settings-transfer textarea').value=JSON.stringify({version:2,theme:{appearance:'glass'},css:'/* imported v2 */',
            layout:{paletteKey:'L',tools:['palette'],toolOrder:order}});
        document.querySelectorAll('#forge-settings-transfer button')[1].doCommand();
        return document.getElementById('forge-palette-shortcut').value==='L' &&
            JSON.stringify(Array.from(document.querySelector('#forge-dock-settings').children,row=>row.getAttribute('data-tool')))===JSON.stringify(order) &&
            Array.from(document.querySelectorAll('#forge-dock-settings input')).filter(input=>input.checked).length===1;
    """)
    click('forge-theme-cancel')
    client.execute_script('__editorRestore();');open_editor()
    client.execute_script("for(const input of document.querySelectorAll('#forge-dock-settings input')){input.checked=false;}")
    click('forge-theme-save')
    check("Hiding the whole dock does not remove the native settings entry point", "return document.querySelectorAll('.forge-dev-tools toolbarbutton:not([hidden])').length===0 && !!document.getElementById('forge-hub-button');")
    open_editor()
    client.execute_script("for(const input of document.querySelectorAll('#forge-dock-settings input')){input.checked=true;}")
    click('forge-theme-save')
    check("All dock buttons can be restored through the control center", "return document.querySelectorAll('.forge-dev-tools toolbarbutton:not([hidden])').length===5;")
    client.execute_script("__editorRestore();Services.prefs.setStringPref('forge.customCSS','/* saved test CSS */');Services.prefs.setBoolPref('forge.customCSS.enabled',true);")
    open_editor();client.execute_script("document.getElementById('forge-editor-advanced').open=true;")
    click('forge-css-clear')
    check("Clear CSS edits only the draft until saved", "return document.querySelector('#forge-editor-advanced textarea').value==='' && Services.prefs.getStringPref('forge.customCSS')==='/* saved test CSS */' && Services.prefs.getBoolPref('forge.customCSS.enabled');")
    click('forge-theme-cancel');open_editor();client.execute_script("document.getElementById('forge-editor-advanced').open=true;")
    click('forge-css-disable')
    check("Disable CSS now is immediate, preserves code and disables itself", "return !Services.prefs.getBoolPref('forge.customCSS.enabled') && Services.prefs.getStringPref('forge.customCSS')==='/* saved test CSS */' && document.getElementById('forge-css-disable').disabled;")
    client.find_element(By.CSS_SELECTOR,'#forge-editor-advanced textarea').send_keys(Keys.RETURN)
    frame()
    check("Enter in CSS inserts a newline instead of saving the dialog", "return document.getElementById('forge-editor').open && document.querySelector('#forge-editor-advanced textarea').value.includes('\\n');")
    for width,height,scale in ((800,600,1),(800,600,2)):
        client.set_window_rect(width=width,height=height)
        client.execute_script("window.browsingContext.fullZoom=arguments[0];document.querySelector('.forge-editor-body').scrollTop=100000;",script_args=[scale])
        frame();settle_ui(client)
        check(f"Appearance footer buttons stay visible at {round(scale*100)}% zoom", """
            const rect=document.getElementById('forge-editor').getBoundingClientRect();
            const buttons=Array.from(document.querySelectorAll('#forge-editor .forge-actions button'));
            return buttons.every(button=>{const r=button.getBoundingClientRect();return r.width>0 && r.left>=rect.left && r.right<=rect.right+1 && r.top>=rect.top && r.bottom<=rect.bottom+1;}) &&
                document.querySelector('.forge-editor-body').clientHeight>20;
        """)
        screenshot(f'footer-{round(scale*100)}')
    client.execute_script("window.browsingContext.fullZoom=1;")
    client.set_window_rect(width=1366,height=768)
    click('forge-theme-cancel')
    client.execute_script("__editorRestore();for(const key of ['__editorPrefs','__editorSnapshot','__editorOriginal','__editorRestore','__editorInput','__editorBeforeNoop','__editorBeforeInvalid','__editorBeforePreview','__editorExternal','__editorResetFixture','__editorOtherCommit']){delete window[key];}")
    return failures
