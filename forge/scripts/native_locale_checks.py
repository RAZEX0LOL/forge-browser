# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Real native locale/resource checks. Always called in disposable profiles."""
from marionette_driver import Wait, errors
import base64


def run_native_locale_checks(client, results, passed):
    client.set_context('chrome')
    def check(name,script,async_script=False):
        result=(client.execute_async_script if async_script else client.execute_script)(script)
        if result is not True: raise AssertionError(f'{name}: {result!r}')
        passed.append(name);print(f'PASS {name}',flush=True)
    check('Russian native locale is selected with en-US fallback and no preference lock', """
        const value={available:Services.locale.availableLocales,requested:Services.locale.requestedLocales,
            application:Services.locale.appLocalesAsBCP47,locked:Services.prefs.prefIsLocked('intl.locale.requested')};
        return (value.available.includes('ru') && value.available.includes('en-US') && value.application[0]==='ru' && !value.locked) || value;
    """)
    check('Native chrome registry resolves both browser and toolkit to Russian', """
        const registry=Cc['@mozilla.org/chrome/chrome-registry;1'].getService(Ci.nsIChromeRegistry);
        return ['chrome://browser/locale/browser.properties','chrome://global/locale/commonDialogs.properties'].every(
            url=>registry.convertChromeURL(Services.io.newURI(url)).spec.includes('/ru/'));
    """)
    check('Legacy native dialog strings are Russian and product branding stays Forge', """
        return Services.strings.createBundle('chrome://global/locale/commonDialogs.properties').GetStringFromName('Cancel')==='Отмена' &&
            Services.strings.createBundle('chrome://branding/locale/brand.properties').GetStringFromName('brandShortName')==='Forge';
    """)
    check('Native browser Fluent resolves actual application-menu labels in Russian', """
        const done=arguments[arguments.length-1];
        document.l10n.formatMessages(['appmenuitem-new-tab']).then(messages=>done(messages[0].attributes.some(attr=>attr.name==='label' && attr.value==='Новая вкладка'))).catch(error=>done(String(error)));
    """,True)
    check('Native locale does not install a language-pack extension or override signature policy', """
        const done=arguments[arguments.length-1];
        const {AddonManager}=ChromeUtils.importESModule('resource://gre/modules/AddonManager.sys.mjs');
        AddonManager.getAddonsByTypes(['locale']).then(addons=>done(addons.length===0 &&
            !Services.prefs.prefHasUserValue('xpinstall.signatures.required') &&
            !Services.prefs.prefHasUserValue('extensions.langpacks.signatures.required'))).catch(error=>done(String(error)));
    """,True)
    check('Packaged upstream translation coverage reports no missing entries', """
        const done=arguments[arguments.length-1];
        fetch('resource://gre/forge-native-l10n.json').then(response=>response.json()).then(data=>done(
            data.locale==='ru' && data.coverage.entries>=15000 && data.coverage.missingEntries===0 &&
            data.translationRevision.length===40 && data.geckoRevision.length===40)).catch(error=>done(String(error)));
    """,True)
    check('Native Hunspell loads Russian while retaining the English dictionary', """
        const engine=Cc['@mozilla.org/spellchecker/engine;1'].getService(Ci.mozISpellCheckingEngine);
        const available=engine.getDictionaryList(),previous=engine.dictionaries;
        if(!available.includes('ru') || !available.includes('en-US')){return available;}
        try{engine.dictionaries=['ru'];return engine.check('окно') && !engine.check('абвгдъьщ');}
        finally{engine.dictionaries=previous;}
    """)
    client.set_context('content');client.switch_to_window(client.window_handles[0])
    for url,title in [('about:preferences','Настройки'),('about:addons','Управление дополнениями'),('about:logins','Пароли')]:
        client.navigate(url)
        Wait(client,timeout=15,ignored_exceptions=(errors.JavascriptException,)).until(
            lambda c:c.execute_script('return document.readyState===\'complete\' && document.title===arguments[0];',script_args=[title]))
        name=f'Native {url} content process renders its Russian document title'
        passed.append(name);print(f'PASS {name}',flush=True)
        if url=='about:preferences': (results/'native-settings-russian.png').write_bytes(base64.b64decode(client.screenshot()))
    client.set_context('chrome')
    profile=client.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path;")
    original=client.execute_script("return Services.prefs.prefHasUserValue('intl.locale.requested')?Services.prefs.getStringPref('intl.locale.requested'):null;")
    def restart():
        client.restart(in_app=True);client.set_context('chrome')
        Wait(client,timeout=15).until(lambda c:c.execute_script("return document.documentElement.getAttribute('forge-ready')==='true';"))
        if client.execute_script("return Services.dirsvc.get('ProfD',Ci.nsIFile).path;")!=profile:
            raise AssertionError('Native locale restart switched profile')
    restart()
    check('Native Russian locale and Forge survive restart of the exact same disposable profile', """
        return Services.locale.appLocaleAsBCP47==='ru' && document.documentElement.getAttribute('forge-ready')==='true';
    """)
    client.execute_script("Services.locale.requestedLocales=['en-US'];")
    restart()
    check('Explicit English preference switches native Firefox and Forge panels after restart', """
        return Services.locale.appLocaleAsBCP47==='en-US' && document.getElementById('forge-palette-title').textContent==='Forge commands' &&
            document.getElementById('forge-editor-title').textContent==='Appearance' && document.getElementById('forge-palette').getAttribute('lang')==='en-US';
    """)
    client.set_context('content');client.switch_to_window(client.window_handles[0]);client.navigate('about:preferences')
    Wait(client,timeout=15,ignored_exceptions=(errors.JavascriptException,)).until(
        lambda c:c.execute_script("return document.title==='Settings' && document.documentElement.getAttribute('data-forge-localized')==='true';"))
    check('English native settings and Forge header use the same language', """
        const title=document.querySelector('[data-forge-l10n="forge-settings-title"]');
        return title.textContent==='Your browser, under your control.' && title.getAttribute('lang')==='en-US';
    """)
    (results/'native-settings-english.png').write_bytes(base64.b64decode(client.screenshot()))
    original_handle=client.current_window_handle
    handles=set(client.window_handles)
    client.set_context('chrome');client.execute_script('BrowserCommands.openTab();')
    client.set_context('content');client.switch_to_window(next(handle for handle in client.window_handles if handle not in handles))
    Wait(client,timeout=15,ignored_exceptions=(errors.JavascriptException,)).until(
        lambda c:c.execute_script("return document.documentElement.getAttribute('data-forge-localized')==='true';"))
    check('New-tab actor follows English application locale without author scripts', """
        return document.title==='Forge — New tab' && document.documentElement.lang==='en-US' &&
            document.getElementById('query').getAttribute('placeholder')==='Search the web' && document.scripts.length===0;
    """)
    client.set_context('chrome');client.execute_script('gBrowser.removeTab(gBrowser.selectedTab,{animate:false});')
    client.set_context('content');client.switch_to_window(original_handle)
    client.set_context('chrome')
    client.execute_script("if(arguments[0]===null){Services.prefs.clearUserPref('intl.locale.requested');}else{Services.prefs.setStringPref('intl.locale.requested',arguments[0]);}",script_args=[original])
    restart()
    check('Removing the explicit language override returns native Firefox and Forge to Russian', """
        return Services.locale.appLocaleAsBCP47==='ru' && document.getElementById('forge-palette-title').textContent==='Команды Forge' &&
            document.getElementById('forge-palette').getAttribute('lang')==='ru' && !Services.prefs.prefHasUserValue('intl.locale.requested');
    """)
    return []
