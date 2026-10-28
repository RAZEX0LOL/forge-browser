# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Gecko accessibility tree checks, not a substitute for VoiceOver testing."""
from marionette_driver import Wait
from pathlib import Path
import re


def run_accessibility_checks(client, results, passed):
    client.set_context('chrome')
    def check(name, script):
        result=client.execute_script(script)
        if result is not True: raise AssertionError(f'{name}: {result!r}')
        passed.append(name);print(f'PASS {name}',flush=True)
    resource=Path(__file__).resolve().parents[1]/'overlay/locales/ru/forge.ftl'
    ids=re.findall(r'^(forge-[\w-]+)\s*=',resource.read_text(encoding='utf-8'),re.MULTILINE)
    result=client.execute_script(r"""
        const {createStrings}=ChromeUtils.importESModule('chrome://browser/content/forge/Localization.sys.mjs');
        return ['ru','en-US'].every(locale=>{const t=createStrings(window,locale);
            return arguments[0].every(id=>{const value=t(id,{name:'Fixture <not markup>',count:2,key:'N',error:'Fixture error'});
                return typeof value==='string' && !/\{\s*\$/.test(value);});});
    """,script_args=[ids])
    if result is not True: raise AssertionError('Fluent catalogue did not resolve in both locales')
    passed.append('Every Forge Fluent message resolves with native Gecko in both locales')
    print('PASS Every Forge Fluent message resolves with native Gecko in both locales',flush=True)
    check('Native Fluent resolves Russian plural forms and English fallback', """
        const {createStrings}=ChromeUtils.importESModule('chrome://browser/content/forge/Localization.sys.mjs');
        const ru=createStrings(window),en=createStrings(window,'en-US'),fallback=createStrings(window,'unsupported');
        return ru('forge-group-count',{count:1}).includes('вкладка') && ru('forge-group-count',{count:2}).includes('вкладки') &&
            ru('forge-group-count',{count:5}).includes('вкладок') && en('forge-shortcuts-title')==='Keyboard shortcuts' && fallback('forge-save')==='Save';
    """)
    client.execute_script("""
        window.__forgeA11y=Cc['@mozilla.org/accessibilityService;1'].getService(Ci.nsIAccessibilityService);
        document.getElementById('forge-command-button').doCommand();
    """)
    Wait(client,timeout=10).until(lambda c:c.execute_script("return !!__forgeA11y.getAccessibleFor(document.querySelector('#forge-palette input'));"))
    check('Accessibility tree exposes a named palette dialog and editable search', """
        const dialog=__forgeA11y.getAccessibleFor(document.getElementById('forge-palette'));
        const input=__forgeA11y.getAccessibleFor(document.querySelector('#forge-palette input'));
        return (!!dialog && dialog.name==='Команды Forge' && !!input && input.name==='Поиск команд' &&
            __forgeA11y.getStringRole(dialog.role)==='dialog') || {dialogName:dialog?.name,role:dialog&&__forgeA11y.getStringRole(dialog.role),inputName:input?.name};
    """)
    check('Accessibility tree exposes named native palette actions', """
        const node=document.querySelector('.forge-result'),acc=__forgeA11y.getAccessibleFor(node);
        return !!acc && !!acc.name && __forgeA11y.getStringRole(acc.role)==='pushbutton';
    """)
    client.execute_script("document.getElementById('forge-palette').close();document.getElementById('forge-hub-button').doCommand();document.querySelector('.forge-hub-action[data-action=\"Сочетания клавиш\"]').doCommand();")
    Wait(client,timeout=10).until(lambda c:c.execute_script("return !!__forgeA11y.getAccessibleFor(document.querySelector('#forge-shortcuts input'));"))
    check('Shortcut editor has a named accessible dialog and labelled fields', """
        const acc=__forgeA11y.getAccessibleFor(document.getElementById('forge-shortcuts'));
        return acc?.name==='Сочетания клавиш' && Array.from(document.querySelectorAll('#forge-shortcuts input')).every(node=>!!__forgeA11y.getAccessibleFor(node)?.name);
    """)
    client.execute_script("document.getElementById('forge-shortcuts').close();window.__forgeA11yColors=browsingContext.forcedColorsOverride;browsingContext.forcedColorsOverride='active';")
    try:
        Wait(client,timeout=10).until(lambda c:c.execute_script("return matchMedia('(forced-colors: active)').matches;"))
        check('Forced-colors mode retains a visible selected-tab outline', """
            const node=document.querySelector('.forge-tab[selected]'),style=getComputedStyle(node);
            return node.getClientRects().length>0 && style.outlineStyle!=='none' && parseFloat(style.outlineWidth)>=2;
        """)
        Wait(client,timeout=10).until(lambda c:c.execute_script("""
            const node=document.querySelector('.forge-tab[selected] .forge-tab-close');
            return !!node?.getClientRects().length && !!__forgeA11y.getAccessibleFor(node)?.name;
        """))
        check('Forced-colors mode retains visible keyboard focus and close controls', """
            const node=document.querySelector('.forge-tab[selected] .forge-tab-close');
            node.focus();return (node.getClientRects().length>0 && document.activeElement===node && !!__forgeA11y.getAccessibleFor(node)?.name) ||
                {visible:!!node.getClientRects().length,focused:document.activeElement===node,name:__forgeA11y.getAccessibleFor(node)?.name};
        """)
    finally:
        client.execute_script("browsingContext.forcedColorsOverride=__forgeA11yColors;delete window.__forgeA11yColors;delete window.__forgeA11y;")
    return []
