# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
import base64
from marionette_driver.by import By
from marionette_driver.keys import Keys
from ui_wait import settle_ui


def run_native_checks(client, results, passed):
    def check(name, script, args=None):
        result = client.execute_script(script, script_args=args or [])
        if result is not True:
            raise AssertionError(f"{name}: {result!r}")
        passed.append(name)
        print(f"PASS {name}", flush=True)

    def frame():
        client.execute_async_script("const done=arguments[arguments.length-1]; requestAnimationFrame(() => requestAnimationFrame(() => done(true)));")

    def screenshot(name):
        settle_ui(client)
        (results / f"{name}.png").write_bytes(base64.b64decode(client.screenshot()))

    client.set_context("content")
    client.navigate("chrome://browser/content/forge/start.html")
    client.set_context("chrome")
    client.execute_script("window.__forgeNativeTheme = Services.prefs.getStringPref('forge.theme','{}');")
    check("Chrome controls are actual Firefox XUL widgets", """
        const controls = document.querySelectorAll('#forge-rail .forge-native-control, #forge-control-center .forge-native-control, #forge-editor .forge-dialog-button');
        return controls.length > 15 && Array.from(controls).every(node =>
            node.namespaceURI === 'http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul' &&
            ['toolbarbutton','button'].includes(node.localName));
    """)
    check("Native new-tab command fires exactly once", """
        const before = gBrowser.tabs.length;
        document.getElementById('forge-new-tab').doCommand();
        window.__forgeNativeNewTab = gBrowser.selectedTab;
        return gBrowser.tabs.length === before+1;
    """)
    frame()
    client.execute_script("window.__forgeNativeCount=gBrowser.tabs.length; document.getElementById('forge-new-tab').focus();")
    client.find_element(By.ID, "forge-new-tab").send_keys(Keys.SPACE)
    frame()
    check("Native toolbar control supports keyboard activation", """
        return gBrowser.tabs.length === __forgeNativeCount+1;
    """)
    client.execute_script("gBrowser.removeTab(gBrowser.selectedTab); gBrowser.removeTab(__forgeNativeNewTab); delete window.__forgeNativeNewTab; delete window.__forgeNativeCount;")
    frame(); settle_ui(client)
    client.find_element(By.ID, "forge-workspace").click()
    frame()
    check("Workspace chooser opens a native menu with management actions", """
        const popup=document.getElementById('forge-workspace-popup');
        return popup.state==='open' && popup.namespaceURI==='http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul' &&
            !!popup.querySelector('menuitem[checked="true"]') &&
            ['forge-workspace-add','forge-workspace-rename','forge-workspace-remove'].every(id=>!!document.getElementById(id));
    """)
    client.execute_script("document.getElementById('forge-workspace-popup').hidePopup(); Services.prefs.setBoolPref('forge.sidebar.collapsed',true);")
    for side in ("left", "right"):
        for width in (72, 104):
            client.execute_script("""
                const theme=JSON.parse(__forgeNativeTheme);
                Object.assign(theme,{sidebarSide:arguments[0],compactWidth:arguments[1],iconSize:22,tabHeight:44,toolbarHeight:58,contentGap:4});
                Services.prefs.setStringPref('forge.theme',JSON.stringify(theme));
            """, script_args=[side, width])
            frame(); settle_ui(client)
            check(f"Compact {side} rail at {width}px keeps native controls aligned", """
                const rail=document.getElementById('forge-rail').getBoundingClientRect();
                const controls=['forge-sidebar-toggle','forge-new-tab','forge-workspace'].map(id=>document.getElementById(id));
                controls.splice(1,0,document.querySelector('.forge-launcher'));
                const rects=controls.map(node=>node.getBoundingClientRect());
                const center=rects[0].left+rects[0].width/2;
                const valid=rects.every((rect,index)=>rect.width>=32 && rect.height>=32 && rect.left>=rail.left && rect.right<=rail.right &&
                    Math.abs(rect.left+rect.width/2-center)<1 && (!index || rect.top>=rects[index-1].bottom));
                const viewport=document.getElementById('tabbrowser-tabbox').getBoundingClientRect();
                const sideCorrect=arguments[0]==='right' ? rail.left>=viewport.right-1 : rail.right<=viewport.left+1;
                return (valid && Math.abs(rail.width-arguments[1])<1 && sideCorrect &&
                    getComputedStyle(document.querySelector('.forge-workspace-label')).display==='none') || {valid,railWidth:rail.width,sideCorrect};
            """, [side, width])
            screenshot(f"native-compact-{side}-{width}")
    check("Geometry settings reach real chrome without styling websites", """
        const icon=document.querySelector('.forge-launcher > svg');
        const style=getComputedStyle(document.getElementById('nav-bar'));
        return getComputedStyle(icon).width==='22px' && style.minHeight==='58px' &&
            getComputedStyle(document.getElementById('browser')).paddingBottom==='4px' &&
            getComputedStyle(document.getElementById('forge-new-tab')).boxShadow==='none';
    """)
    client.execute_script("""
        Services.prefs.clearUserPref('forge.sidebar.collapsed');
        Services.prefs.setStringPref('forge.theme',__forgeNativeTheme);
        document.querySelector('.forge-tool[aria-label="Оформление"]').doCommand();
        const preset=document.getElementById('forge-theme-preset');
        preset.value='glass'; preset.dispatchEvent(new Event('change',{bubbles:true}));
        document.querySelector('#forge-editor [data-setting="sidebarSide"]').value='right';
        document.querySelector('#forge-editor [data-setting="glassOpacity"]').value='55';
        document.querySelector('#forge-editor [data-setting="blur"]').value='12';
        document.getElementById('forge-theme-preview').doCommand();
    """)
    frame(); settle_ui(client)
    check("Preset and custom Glass controls preview with no CSS", """
        const theme=JSON.parse(Services.prefs.getStringPref('forge.theme'));
        const style=getComputedStyle(document.documentElement);
        return theme.appearance==='glass' && theme.sidebarSide==='right' && theme.glassOpacity===55 && theme.blur===12 &&
            style.getPropertyValue('--forge-surface').includes('0.55') && style.getPropertyValue('--forge-blur').includes('12px');
    """)
    client.execute_script("document.getElementById('forge-editor').close();")
    frame()
    check("Cancelling extended preview restores layout and opacity", "return Services.prefs.getStringPref('forge.theme')===__forgeNativeTheme;")
    client.execute_script("""
        document.querySelector('.forge-tool[aria-label="Оформление"]').doCommand();
        const preset=document.getElementById('forge-theme-preset');
        preset.value='contrast'; preset.dispatchEvent(new Event('change',{bubbles:true}));
        document.getElementById('forge-theme-save').doCommand();
    """)
    frame()
    check("Native save persists all new appearance settings", """
        const theme=JSON.parse(Services.prefs.getStringPref('forge.theme'));
        return theme.contrast==='strong' && theme.iconSize===20 && theme.tabHeight===44 && theme.controlRadius===4 &&
            getComputedStyle(document.documentElement).getPropertyValue('--forge-tab-height').trim()==='44px';
    """)
    client.execute_script("""
        document.querySelector('.forge-tool[aria-label="Оформление"]').doCommand();
        document.getElementById('forge-geometry-settings').open=true;
    """)
    screenshot("native-appearance-settings")
    client.execute_script("""
        document.getElementById('forge-editor').close();
        Services.prefs.setStringPref('forge.theme',__forgeNativeTheme);
        delete window.__forgeNativeTheme;
    """)
