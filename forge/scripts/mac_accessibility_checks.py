# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Gecko's native macOS AX bridge, not a manual VoiceOver/desktop-control test.

Uses the same nsIAccessibleMacInterface as Mozilla's in-process mac tests.
No AXUIElement desktop access, OS setting changes or external application control.
"""
from marionette_driver import Wait, errors


def run_mac_accessibility_checks(client, results, passed):
    client.set_context('chrome')
    if client.execute_script("return Services.appinfo.OS;")!='Darwin':
        raise RuntimeError('Native macOS AX checks require macOS')
    def check(name,script):
        result=client.execute_script(script)
        if result is not True: raise AssertionError(f'{name}: {result!r}')
        passed.append(name);print(f'PASS {name}',flush=True)
    client.execute_script("""
        window.__forgeMacOldPref=Services.prefs.prefHasUserValue('accessibility.force_disabled')?Services.prefs.getIntPref('accessibility.force_disabled'):null;
    """)
    try:
        client.execute_script("""
            Services.prefs.setIntPref('accessibility.force_disabled',-1);
            window.__forgeMacService=Cc['@mozilla.org/accessibilityService;1'].getService(Ci.nsIAccessibilityService);
            window.__forgeMacInterface=selector=>__forgeMacService.getAccessibleFor(document.querySelector(selector))?.nativeInterface?.QueryInterface(Ci.nsIAccessibleMacInterface);
            window.__forgeMacAttr=(iface,name)=>iface.attributeNames.includes(name)?iface.getAttributeValue(name):null;
            document.getElementById('forge-command-button').doCommand();
        """)
        Wait(client,timeout=10,ignored_exceptions=(errors.JavascriptException,)).until(
            lambda c:c.execute_script("return !!__forgeMacInterface('#forge-palette input');"))
        check('macOS AX bridge exposes named application dialog and search field', """
            const dialog=__forgeMacInterface('#forge-palette'),input=__forgeMacInterface('#forge-palette input');
            const state={dialogRole:__forgeMacAttr(dialog,'AXRole'),dialogSubrole:__forgeMacAttr(dialog,'AXSubrole'),
                dialogName:[__forgeMacAttr(dialog,'AXTitle'),__forgeMacAttr(dialog,'AXDescription')].filter(Boolean).join(' '),
                inputRole:__forgeMacAttr(input,'AXRole'),inputName:__forgeMacAttr(input,'AXDescription')};
            return (state.dialogRole==='AXGroup' && state.dialogSubrole==='AXApplicationDialog' && state.dialogName.includes('Команды Forge') &&
                state.inputRole==='AXTextField' && state.inputName==='Поиск команд') || state;
        """)
        check('macOS AX bridge exposes named actionable palette buttons', """
            const node=document.querySelector('.forge-result'),iface=__forgeMacInterface('.forge-result');
            const state={role:__forgeMacAttr(iface,'AXRole'),title:__forgeMacAttr(iface,'AXTitle'),description:__forgeMacAttr(iface,'AXDescription'),actions:iface.actionNames};
            return (state.role==='AXButton' && [state.title,state.description].includes(node.getAttribute('aria-label')) && state.actions.includes('AXPress')) || state;
        """)
        client.execute_script("document.querySelector('.forge-result').focus();")
        client.execute_script("document.querySelector('#forge-palette input').focus();")
        Wait(client,timeout=10).until(lambda c:c.execute_script("return !!__forgeMacAttr(__forgeMacInterface('#forge-palette input'),'AXFocused');"))
        check('macOS AX bridge reports actual search focus and focusability', """
            const iface=__forgeMacInterface('#forge-palette input');
            return document.activeElement===document.querySelector('#forge-palette input') &&
                !!__forgeMacAttr(iface,'AXFocused') && iface.isAttributeSettable('AXFocused');
        """)
        check('macOS AX bridge exposes polite atomic palette status', """
            const iface=__forgeMacInterface('#forge-palette-status');
            const state={live:__forgeMacAttr(iface,'AXARIALive'),atomic:__forgeMacAttr(iface,'AXARIAAtomic')};
            return (state.live==='polite' && !!state.atomic) || state;
        """)
        client.execute_script("document.getElementById('forge-palette').close();document.getElementById('forge-hub-button').doCommand();")
        def dialog_check(selector):
            Wait(client,timeout=10,ignored_exceptions=(errors.JavascriptException,)).until(
                lambda c:c.execute_script("return !!__forgeMacInterface(arguments[0]);",script_args=[selector]))
            state=client.execute_script("""
                const node=document.querySelector(arguments[0]),iface=__forgeMacInterface(arguments[0]);
                return {open:node.open,role:__forgeMacAttr(iface,'AXRole'),subrole:__forgeMacAttr(iface,'AXSubrole'),
                    name:[__forgeMacAttr(iface,'AXTitle'),__forgeMacAttr(iface,'AXDescription')].filter(Boolean).join(' '),
                    expectedName:document.getElementById(node.getAttribute('aria-labelledby')).textContent};
            """,script_args=[selector])
            if not (state['open'] and state['role']=='AXGroup' and state['subrole']=='AXApplicationDialog' and
                    state['expectedName'] and state['expectedName'] in state['name']):
                raise AssertionError(f'{selector}: {state!r}')
            name=f'macOS AX bridge exposes named application dialog {selector}'
            passed.append(name);print(f'PASS {name}',flush=True)
        dialog_check('#forge-control-center')
        client.execute_script("document.querySelector('.forge-hub-action[data-action=\"Оформление\"]').doCommand();")
        dialog_check('#forge-editor')
        client.execute_script("document.getElementById('forge-editor').close();document.getElementById('forge-hub-button').doCommand();document.querySelector('.forge-hub-action[data-action=\"Сочетания клавиш\"]').doCommand();")
        dialog_check('#forge-shortcuts')
        Wait(client,timeout=10,ignored_exceptions=(errors.JavascriptException,)).until(
            lambda c:c.execute_script("return !!__forgeMacInterface('#forge-shortcuts input');"))
        check('macOS AX bridge exposes shortcut fields with localized names', """
            const fields=Array.from(document.querySelectorAll('#forge-shortcuts input'));
            return fields.length===9 && fields.every(node=>{
                const iface=__forgeMacService.getAccessibleFor(node).nativeInterface.QueryInterface(Ci.nsIAccessibleMacInterface);
                return __forgeMacAttr(iface,'AXRole')==='AXTextField' &&
                    [__forgeMacAttr(iface,'AXTitle'),__forgeMacAttr(iface,'AXDescription')].includes(node.getAttribute('aria-label'));
            });
        """)
    finally:
        client.execute_script("""
            for(const dialog of document.querySelectorAll('dialog[id^="forge-"][open]')){dialog.close();}
            if(__forgeMacOldPref===null){Services.prefs.clearUserPref('accessibility.force_disabled');}
            else{Services.prefs.setIntPref('accessibility.force_disabled',__forgeMacOldPref);}
            for(const key of ['__forgeMacOldPref','__forgeMacService','__forgeMacInterface','__forgeMacAttr']){delete window[key];}
        """)
    return []
