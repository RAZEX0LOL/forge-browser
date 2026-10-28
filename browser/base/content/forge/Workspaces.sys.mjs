/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { SessionStore } from "moz-src:///browser/components/sessionstore/SessionStore.sys.mjs";
import { icon } from "./Icons.sys.mjs";
import { createStrings } from "./Localization.sys.mjs";

const KEY = "forge.workspace";
export function createWorkspaces(win, { el, on, cleanup }) {
  const browser = win.gBrowser;
  const t = createStrings(win);
  let state;
  try { state = JSON.parse(SessionStore.getCustomWindowValue(win, KEY)); } catch {}
  if (!state?.items?.length || !state.items.every(item => typeof item.id === "string" && typeof item.name === "string")) {
    state = { active: "main", items: [{ id: "main", name: t("forge-workspace-default") }] };
  }
  if (!state.items.some(item => item.id === state.active)) { state.active = state.items[0].id; }
  let hydrated = false;
  let restoring = false;
  let alive = true;
  cleanup(() => { alive = false; });
  const host = el("div", { class: "forge-workspaces" });
  const select = el("button", { id: "forge-workspace", type: "menu", "aria-label": t("forge-workspace-label"), "aria-haspopup": "menu" });
  const label = el("span", { class: "forge-workspace-label" });
  select.append(icon(win.document, "grid"), label);
  const popup = win.document.createXULElement("menupopup");
  popup.id = "forge-workspace-popup";
  select.append(popup);
  host.append(select);
  const item = (id, title, run) => {
    const node = win.document.createXULElement("menuitem");
    node.id = id;
    node.setAttribute("label", title);
    node.addEventListener("command", run);
    return node;
  };
  const add = item("forge-workspace-add", t("forge-workspace-add"), () => {
    const name = win.prompt(t("forge-workspace-new-name"))?.trim().slice(0, 40);
    if (!name || !hydrated || restoring) { return; }
    const id = Services.uuid.generateUUID().toString();
    state.items.push({ id, name });
    activate(id);
  });
  const remove = item("forge-workspace-remove", t("forge-workspace-remove"), () => {
    if (state.items.length < 2 || !win.confirm(t("forge-workspace-confirm"))) { return; }
    const target = state.items.find(space => space.id !== state.active).id;
    for (const tab of browser.tabs) { if (idFor(tab) === state.active) { assign(tab, target); } }
    state.items = state.items.filter(space => space.id !== state.active);
    activate(target);
  });
  const rename = item("forge-workspace-rename", t("forge-workspace-rename"), () => {
    const space = state.items.find(entry => entry.id === state.active);
    const name = win.prompt(t("forge-workspace-name"), space.name)?.trim().slice(0, 40);
    if (name) { space.name = name; notify(); }
  });
  const save = () => { if (hydrated && !restoring) { SessionStore.setCustomWindowValue(win, KEY, JSON.stringify(state)); } };
  const idFor = tab => SessionStore.getCustomTabValue(tab, KEY) || state.active;
  function assign(tab, id) {
    SessionStore.setCustomTabValue(tab, KEY, id);
    // Native groups and split siblings are indivisible workspace units.
    for (const sibling of tab.group?.tabs || tab.splitview?.tabs || []) { SessionStore.setCustomTabValue(sibling, KEY, id); }
  }
  function render() {
    const choices = state.items.map(space => {
      const node = item("", space.name, () => activate(space.id));
      node.setAttribute("type", "radio");
      node.setAttribute("name", "forge-workspaces");
      node.setAttribute("checked", String(space.id === state.active));
      node.setAttribute("data-workspace-id", space.id);
      return node;
    });
    popup.replaceChildren(...choices, win.document.createXULElement("menuseparator"), add, rename, remove);
    select.value = state.active;
    label.textContent = state.items.find(space => space.id === state.active).name;
    select.setAttribute("tooltiptext", t("forge-workspace-tooltip", { name: label.textContent }));
    select.setAttribute("aria-label", t("forge-workspace-current", { name: label.textContent }));
    remove.disabled = state.items.length < 2;
  }
  function notify() { render(); save(); win.dispatchEvent(new win.Event("forge-workspace-change")); }
  function activate(id) {
    if (!hydrated || restoring) { return; }
    if (!state.items.some(item => item.id === id)) { return; }
    state.active = id;
    const tab = Array.from(browser.tabs).find(item => !item.closing && !item.hidden && !item.pinned && idFor(item) === id);
    if (tab) { browser.selectedTab = tab; }
    else { win.BrowserCommands.openTab(); assign(browser.selectedTab, id); }
    notify();
  }
  function hydrate() {
    if (!alive) { return; }
    let stored;
    try { stored = JSON.parse(SessionStore.getCustomWindowValue(win, KEY)); } catch {}
    if (stored?.items?.length && stored.items.every(item => typeof item.id === "string" && typeof item.name === "string")) {
      state.items = stored.items;
      state.active = state.items.some(item => item.id === stored.active) ? stored.active : state.items[0].id;
    }
    for (const tab of browser.tabs) {
      const id = idFor(tab);
      assign(tab, state.items.some(item => item.id === id) ? id : state.active);
    }
    hydrated = true; restoring = false;
    notify();
  }
  on(win, "SSWindowStateBusy", () => { restoring = true; });
  on(win, "SSWindowStateReady", hydrate);
  SessionStore.promiseAllWindowsRestored.then(hydrate).catch(error => win.console.error("Forge workspace restore failed", error));
  on(browser.tabContainer, "TabOpen", event => { if (hydrated && !restoring) { assign(event.target, state.active); } });
  on(browser.tabContainer, "TabSelect", event => {
    if (!hydrated || restoring) { return; }
    const tab = event.target;
    if (!tab.pinned && idFor(tab) !== state.active) {
      const id = idFor(tab);
      if (state.items.some(item => item.id === id)) { state.active = id; notify(); }
      else { assign(tab, state.active); notify(); }
    }
  });
  on(browser.tabContainer, "SSTabRestored", () => {
    if (!hydrated || restoring) { return; }
    const id = idFor(browser.selectedTab);
    if (state.items.some(item => item.id === id)) { state.active = id; }
    else { assign(browser.selectedTab, state.active); }
    notify();
  });
  render();
  return { host, state, idFor, assign, activate,
    visible: tab => !tab.hidden && (tab.pinned || idFor(tab) === state.active),
    move(tab, id) {
      if (!state.items.some(item => item.id === id)) { return; }
      const affectsSelection = tab === browser.selectedTab || Array.from(tab.group?.tabs || tab.splitview?.tabs || []).includes(browser.selectedTab);
      assign(tab, id);
      if (affectsSelection) { activate(state.active); } else { notify(); }
    },
  };
}
