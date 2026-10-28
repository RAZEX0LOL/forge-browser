/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
// Process-local native objects, never a tab identifier supplied by web content.
const TYPE = "application/x-forge-tab";
let drag = null;
function windowFor(tab) { return tab?.ownerDocument?.defaultView || tab?.ownerGlobal; }

export function unitFor(tab) { return tab.group || tab.splitview || tab; }
export function unitTabs(tab) { const unit = unitFor(tab); return unit.tabs ? Array.from(unit.tabs) : [tab]; }

function privateWindow(win) {
  const { PrivateBrowsingUtils } = ChromeUtils.importESModule("resource://gre/modules/PrivateBrowsingUtils.sys.mjs");
  return PrivateBrowsingUtils.isWindowPrivate(win);
}

export function canTransfer(tab, win, target = null) {
  const source = windowFor(tab);
  if (!tab?.isConnected || tab.closing || tab.hidden || !source?.gBrowser || source.closed || !win?.gBrowser || win.closed || !Array.from(source.gBrowser.tabs).includes(tab)) { return false; }
  if (privateWindow(source) !== privateWindow(win)) { return false; }
  if (target && (!target.isConnected || target.closing || target.hidden || windowFor(target) !== win || tab.pinned !== target.pinned)) { return false; }
  if (target && unitTabs(tab).includes(target)) { return false; }
  return unitTabs(tab).every(member => member.isConnected && !member.closing && !member.hidden);
}

export function transferTab(tab, win, workspaces, target = null) {
  if (!canTransfer(tab, win, target)) { return []; }
  const browser = win.gBrowser, source = windowFor(tab), unit = unitFor(tab);
  const members = unitTabs(tab), selectedIndex = members.indexOf(tab);
  const targetUnit = target && unitFor(target);
  const index = target ? (targetUnit.tabs?.[0] || target).index : (tab.pinned ? browser.pinnedTabCount : browser.tabs.length);
  const adoptionIndex = tab.pinned ? browser.pinnedTabCount : browser.tabs.length;
  let moved;
  if (source === win) {
    browser.moveTabTo(unit, { tabIndex: index, forceUngrouped: !tab.group });
    moved = members;
  } else if (tab.group) {
    const collapsed = unit.collapsed;
    const group = browser.adoptTabGroup(unit, { tabIndex: adoptionIndex, selectTab: true });
    group.collapsed = collapsed;
    moved = Array.from(group.tabs);
  } else if (tab.splitview) {
    moved = Array.from(browser.adoptSplitView(unit, { tabIndex: adoptionIndex, selectTab: true }).tabs);
  } else {
    const adopted = browser.adoptTab(tab, { tabIndex: adoptionIndex, selectTab: true });
    if (!adopted) { return []; }
    if (adopted.group) { browser.ungroupTab(adopted); }
    moved = [adopted];
  }
  if (source !== win && target) { browser.moveTabTo(unitFor(moved[0]), { tabIndex: index, forceUngrouped: !moved[0].group }); }
  for (const adopted of moved) { workspaces.assign(adopted, workspaces.state.active); }
  browser.selectedTab = moved[selectedIndex] || moved[0];
  return moved;
}

export function beginDrag(tab, data) {
  const source = windowFor(tab), token = source.crypto.randomUUID();
  drag = { tab, token, source };
  data.setData(TYPE, token);
  data.effectAllowed = "move";
}

export function draggedTab(data, win, target = null, preview = false) {
  if (!drag || !data || !(preview ? Array.from(data.types).includes(TYPE) : data.getData(TYPE) === drag.token) || !canTransfer(drag.tab, win, target)) { return null; }
  return drag.tab;
}

export function endDrag(source = null) { if (!source || drag?.source === source) { drag = null; } }
