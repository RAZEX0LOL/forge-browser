# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Real keyboard input and modifier/IME regressions in disposable profiles."""
from marionette_driver.by import By
from marionette_driver.keys import Keys
from ui_wait import settle_ui


def run_keyboard_checks(client, results, passed):
    def check(name, script):
        result=client.execute_script(script)
        if result is not True:
            raise AssertionError(f'{name}: {result!r}')
        passed.append(name)
        print(f'PASS {name}',flush=True)

    def frame():
        client.execute_async_script('const done=arguments[arguments.length-1];requestAnimationFrame(()=>requestAnimationFrame(()=>done(true)));')

    def key(selector, value):
        client.find_element(By.CSS_SELECTOR, selector).send_keys(value)
        frame()

    def palette():
        client.execute_script("document.querySelector('.forge-launcher').focus();document.querySelector('.forge-launcher').doCommand();")
        settle_ui(client)

    def press(value, shift=False):
        sequence=client.actions.sequence('key','forge-keyboard-audit')
        if shift:
            sequence.key_down(Keys.SHIFT)
        sequence.key_down(value).key_up(value)
        if shift:
            sequence.key_up(Keys.SHIFT)
        sequence.perform()
        frame()

    client.set_context('chrome')
    palette()
    check('Palette starts with keyboard focus in search', "return document.activeElement===document.querySelector('#forge-palette input');")
    check('Palette entry points expose their open dialog state', """
        return [document.querySelector('.forge-launcher'),document.getElementById('forge-command-button')].every(node=>
            node.getAttribute('aria-controls')==='forge-palette' && node.getAttribute('aria-haspopup')==='dialog' && node.getAttribute('aria-expanded')==='true');
    """)
    key('#forge-palette input',Keys.ARROW_DOWN)
    check('Palette ArrowDown enters the first result', "return document.activeElement===document.querySelector('.forge-results').firstElementChild;")
    key('.forge-result',Keys.END)
    check('Palette End moves to the final result', "return document.activeElement===document.querySelector('.forge-results').lastElementChild;")
    client.execute_script("document.querySelector('.forge-results').lastElementChild.focus();")
    key('.forge-result:last-child',Keys.HOME)
    check('Palette Home returns to the first result', "return document.activeElement===document.querySelector('.forge-results').firstElementChild;")
    key('.forge-result',Keys.ARROW_UP)
    check('Palette ArrowUp from the first result returns to search', "return document.activeElement===document.querySelector('#forge-palette input');")
    key('#forge-palette input',Keys.ARROW_UP)
    check('Palette ArrowUp from search enters the final result', "return document.activeElement===document.querySelector('.forge-results').lastElementChild;")
    key('.forge-result:last-child',Keys.ESCAPE)
    check('Palette Escape restores the exact sidebar opener', "return !document.getElementById('forge-palette').open && document.activeElement===document.querySelector('.forge-launcher');")
    check('Closing palette updates expanded state for both entry points', """
        return [document.querySelector('.forge-launcher'),document.getElementById('forge-command-button')].every(node=>node.getAttribute('aria-expanded')==='false');
    """)
    palette()
    check('Palette IME Enter never executes a command', """
        const input=document.querySelector('#forge-palette input'),count=gBrowser.tabs.length;
        const event=new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true});
        input.dispatchEvent(event);
        return !event.defaultPrevented && document.getElementById('forge-palette').open && gBrowser.tabs.length===count;
    """)
    check('Palette modified arrows preserve native text-selection shortcuts', """
        const input=document.querySelector('#forge-palette input');input.focus();
        return ['ctrlKey','metaKey','shiftKey','altKey'].every(modifier=>{
            const event=new KeyboardEvent('keydown',{key:'ArrowDown',[modifier]:true,bubbles:true,cancelable:true});
            input.dispatchEvent(event);return !event.defaultPrevented && document.activeElement===input;
        });
    """)
    client.execute_script("const input=document.querySelector('#forge-palette input');input.value='no-such-forge-command-987';input.dispatchEvent(new Event('input',{bubbles:true}));")
    key('#forge-palette input',Keys.RETURN)
    check('Enter with no palette results is a safe no-op', "return document.getElementById('forge-palette').open && document.activeElement===document.querySelector('#forge-palette input');")
    key('#forge-palette input',Keys.ESCAPE)
    check('Escape closes a nonempty palette search in a single keypress', "return !document.getElementById('forge-palette').open && document.activeElement===document.querySelector('.forge-launcher');")
    palette()
    client.execute_script("const input=document.querySelector('#forge-palette input');input.value='Новая вкладка';input.dispatchEvent(new Event('input',{bubbles:true}));window.__forgeKeyboardCount=gBrowser.tabs.length;")
    key('#forge-palette input',Keys.RETURN)
    check('Palette Enter executes the first native command exactly once', "return !document.getElementById('forge-palette').open && gBrowser.tabs.length===__forgeKeyboardCount+1;")
    client.execute_script('gBrowser.removeTab(gBrowser.selectedTab,{animate:false});delete window.__forgeKeyboardCount;')
    frame();settle_ui(client)
    palette()
    client.execute_script("const input=document.querySelector('#forge-palette input');input.value='Новая вкладка';input.dispatchEvent(new Event('input',{bubbles:true}));window.__forgeKeyboardCount=gBrowser.tabs.length;")
    key('#forge-palette input',Keys.ARROW_DOWN)
    key('.forge-result',Keys.SPACE)
    check('Space activates a palette result once without restoring focus over navigation', "return gBrowser.tabs.length===__forgeKeyboardCount+1 && !document.getElementById('forge-palette').open && document.activeElement!==document.querySelector('.forge-launcher');")
    client.execute_script('gBrowser.removeTab(gBrowser.selectedTab,{animate:false});delete window.__forgeKeyboardCount;')
    frame();settle_ui(client)
    client.execute_script("ToolbarKeyboardNavigator._focusButton(document.getElementById('forge-hub-button'));document.getElementById('forge-hub-button').doCommand();")
    settle_ui(client)
    key('.forge-hub-close',Keys.ESCAPE)
    check('Control center Escape restores the exact toolbar opener', """
        const button=document.getElementById('forge-hub-button');
        return (!document.getElementById('forge-control-center').open && document.activeElement===button) ||
            {open:document.getElementById('forge-control-center').open,active:document.activeElement?.outerHTML,
             opener:button.outerHTML,rects:button.getClientRects().length,hiddenAncestor:button.closest('[hidden],[inert]')?.outerHTML};
    """)
    client.execute_script("document.getElementById('forge-hub-button').doCommand();document.querySelector('.forge-hub-close').focus();window.__forgeKeyboardVisited=new Set([document.activeElement]);")
    settle_ui(client)
    steps=client.execute_script("return document.querySelectorAll('#forge-control-center toolbarbutton').length;")
    for _ in range(steps):
        press(Keys.TAB)
        client.execute_script('window.__forgeKeyboardVisited.add(document.activeElement);')
    check('Control center Tab reaches every action and wraps inside the dialog', """
        const hub=document.getElementById('forge-control-center');
        return (document.activeElement===hub.querySelector('.forge-hub-close') &&
            Array.from(hub.querySelectorAll('toolbarbutton')).every(node=>__forgeKeyboardVisited.has(node))) ||
            {active:document.activeElement?.outerHTML,visited:Array.from(__forgeKeyboardVisited,node=>node.getAttribute('aria-label')||node.localName),
             missing:Array.from(hub.querySelectorAll('toolbarbutton')).filter(node=>!__forgeKeyboardVisited.has(node)).map(node=>node.getAttribute('aria-label'))};
    """)
    press(Keys.TAB,shift=True)
    check('Control center Shift-Tab wraps to the final native-menu action', "return document.activeElement===document.getElementById('forge-native-menu');")
    press(Keys.ESCAPE)
    client.execute_script('delete window.__forgeKeyboardVisited;')
    palette()
    client.execute_script("const input=document.querySelector('#forge-palette input');input.value='Оформление';input.dispatchEvent(new Event('input',{bubbles:true}));")
    key('#forge-palette input',Keys.RETURN)
    check('Opening Appearance from palette does not steal its initial focus', "return document.getElementById('forge-editor').open && document.activeElement===document.getElementById('forge-theme-preset');")
    press(Keys.TAB,shift=True)
    check('Appearance Shift-Tab wraps from the first field to Save', "return document.activeElement===document.getElementById('forge-theme-save');")
    press(Keys.TAB)
    check('Appearance Tab wraps from Save to the first field', "return document.activeElement===document.getElementById('forge-theme-preset');")
    key('#forge-theme-preset',Keys.ESCAPE)
    check('Closing Appearance opened from palette returns to a visible control', "return !document.querySelector('dialog[open]') && document.activeElement!==document.body && document.activeElement.getClientRects().length>0 && !document.activeElement.closest('dialog:not([open])');")
    check('Sidebar ignores modified navigation but keeps ordinary arrow navigation', """
        const node=document.querySelector('.forge-tab:not([data-leaving]) .forge-tab-select');node.focus();
        return ['ctrlKey','metaKey','shiftKey'].every(modifier=>{
            const event=new KeyboardEvent('keydown',{key:'ArrowDown',[modifier]:true,bubbles:true,cancelable:true});
            node.dispatchEvent(event);return !event.defaultPrevented && document.activeElement===node;
        });
    """)
    check('Sidebar controls carry Russian language and localized workspace guidance', """
        return document.getElementById('forge-rail').lang==='ru' &&
            document.getElementById('forge-hub-button').getAttribute('lang')==='ru' &&
            document.getElementById('forge-workspace').getAttribute('tooltiptext').includes('файлов cookie');
    """)
    client.execute_script("""
        window.__keyboardOriginalBindings=Services.prefs.prefHasUserValue('forge.shortcuts.commands')?Services.prefs.getStringPref('forge.shortcuts.commands'):null;
        document.getElementById('forge-hub-button').doCommand();
        document.querySelector('.forge-hub-action[data-action="Сочетания клавиш"]').doCommand();
        document.querySelector('#forge-shortcuts [data-shortcut="network"]').value='R';
        document.getElementById('forge-shortcuts-save').doCommand();
    """)
    frame()
    check('Extra shortcut editor rejects the reserved CSS recovery key', "return document.getElementById('forge-shortcuts').open && document.getElementById('forge-shortcuts-status').getAttribute('role')==='alert';")
    client.execute_script("document.querySelector('#forge-shortcuts [data-shortcut="+'"network"'+"]').value='N';document.getElementById('forge-shortcuts-save').doCommand();")
    frame()
    check('Extra shortcuts create real native key bindings after explicit Save', "return !document.getElementById('forge-shortcuts').open && document.getElementById('forge-extra-key-network')?.getAttribute('key')==='N' && document.getElementById('forge-extra-key-network').getAttribute('modifiers')==='accel,shift,alt';")
    client.execute_script("""
        document.getElementById('forge-hub-button').doCommand();document.querySelector('.forge-hub-action[data-action="Сочетания клавиш"]').doCommand();
        document.getElementById('forge-shortcuts-reset').doCommand();document.getElementById('forge-shortcuts-cancel').doCommand();
    """)
    frame()
    check('Cancelling shortcut reset preserves saved native bindings', "return document.getElementById('forge-extra-key-network')?.getAttribute('key')==='N';")
    client.execute_script("""
        document.getElementById('forge-hub-button').doCommand();document.querySelector('.forge-hub-action[data-action="Сочетания клавиш"]').doCommand();
        Services.prefs.setStringPref('forge.shortcuts.commands','{"network":"M"}');
        document.getElementById('forge-shortcuts-save').doCommand();
    """)
    frame()
    check('Shortcut editor blocks stale saves after external preference changes', "return document.getElementById('forge-shortcuts').open && !document.getElementById('forge-shortcuts-reload').hidden && document.getElementById('forge-extra-key-network').getAttribute('key')==='M';")
    client.execute_script("document.getElementById('forge-shortcuts-reload').doCommand();")
    check('Shortcut reload replaces the stale draft with actual bindings', "return document.querySelector('#forge-shortcuts [data-shortcut=\"network\"]').value==='M';")
    client.execute_script("document.getElementById('forge-command-button').doCommand();")
    frame()
    check('Opening palette from shortcuts never stacks Forge modal dialogs', "return document.querySelectorAll('dialog[id^=\"forge-\"][open]').length===1 && document.getElementById('forge-palette').open;")
    client.execute_script("""
        document.getElementById('forge-palette').close();document.getElementById('forge-hub-button').doCommand();
        document.querySelector('.forge-hub-action[data-action="Оформление"]').doCommand();
        document.getElementById('forge-palette-shortcut').value='M';document.getElementById('forge-theme-save').doCommand();
    """)
    frame()
    check('Palette shortcut cannot overwrite an extra command binding', "return document.getElementById('forge-editor').open && document.getElementById('forge-editor-feedback').getAttribute('role')==='alert' && document.getElementById('forge-extra-key-network').getAttribute('key')==='M';")
    client.execute_script("document.getElementById('forge-theme-cancel').doCommand();")
    client.execute_script("""
        if(__keyboardOriginalBindings===null){Services.prefs.clearUserPref('forge.shortcuts.commands');}
        else{Services.prefs.setStringPref('forge.shortcuts.commands',__keyboardOriginalBindings);}
        delete window.__keyboardOriginalBindings;
    """)
    return []
