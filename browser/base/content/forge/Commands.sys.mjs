/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { createStrings } from "./Localization.sys.mjs";
import { ValidationError } from "./core.sys.mjs";
export function createCommands(win, { open, openEditor, showPalette, toolbox, workspace }) {
  const t = createStrings(win);
  const invoke = id => win.document.getElementById(id).dispatchEvent(new win.Event("command", { bubbles: true }));
  const entries = [
    ["new-tab", "plus", "new tab", "space", () => win.BrowserCommands.openTab()],
    ["new-window", "window", "new window", "space", () => invoke("cmd_newNavigator")],
    ["private", "private", "private window", "space", () => win.OpenBrowserWindow({ private: true })],
    ["downloads", "download", "downloads files", "library", () => open("about:downloads")],
    ["history", "history", "history", "library", () => win.PlacesCommandHook.showPlacesOrganizer("History")],
    ["bookmarks", "bookmark", "bookmarks", "library", () => win.PlacesCommandHook.showPlacesOrganizer("AllBookmarks")],
    ["appearance", "palette", "theme custom css дизайн тема", "browser", openEditor],
    ["settings", "settings", "settings preferences", "browser", () => open("about:preferences")],
    ["addons", "extension", "addons extensions", "browser", () => open("about:addons")],
    ["passwords", "lock", "passwords", "browser", () => open("about:logins")],
    ["privacy", "shield", "privacy policies", "browser", () => open("about:policies")],
    ["commands", "terminal", "commands search", "browser", showPalette],
    ["inspector", "inspect", "inspect devtools html css", null, () => toolbox("inspector")],
    ["console", "terminal", "console javascript devtools", null, () => toolbox("webconsole")],
    ["network", "network", "network api requests devtools", null, () => toolbox("netmonitor")],
    ["debugger", "terminal", "debugger breakpoints devtools", null, () => toolbox("jsdebugger")],
    ["processes", "grid", "memory cpu performance", null, () => open("about:processes")],
    ["debugging", "extension", "debug extensions", null, () => open("about:debugging#/runtime/this-firefox")],
    ["restore", "history", "undo restore reopen", null, () => win.undoCloseTab()],
    ["split", "split", "split view два окна", null, () => {
      const browser = win.gBrowser, active = browser.selectedTab;
      if (active.splitview) { active.splitview.unsplitTabs(); return; }
      const other = Array.from(browser.tabs).find(tab => tab !== active && !tab.pinned && !tab.splitview && !tab.closing && workspace().visible(tab));
      if (active.pinned || !other) { throw new ValidationError("forge-split-needs-tabs"); }
      browser.addTabSplitView([active, other], { insertBefore: active });
      browser.selectedTab = active;
    }],
    ["unsplit", "split", "unsplit view", null, () => win.gBrowser.selectedTab.splitview?.unsplitTabs()],
    ["toolbar", "settings", "toolbar customize buttons", null, () => win.gCustomizeMode.enter()],
  ];
  return entries.map(([id, icon, keywords, group, run]) => ({ id, icon,
    title: t(`forge-command-${id}`), keywords, group: group ? t(`forge-section-${group}`) : null, run }));
}
