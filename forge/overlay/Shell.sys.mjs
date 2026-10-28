/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */

import { icon } from "./Icons.sys.mjs";
import { createWorkspaces } from "./Workspaces.sys.mjs";
import { readToolLayout } from "./core.sys.mjs";
import { plainKey } from "./Keyboard.sys.mjs";
import { beginDrag, draggedTab, endDrag, transferTab, canTransfer, unitFor } from "./TabTransfer.sys.mjs";
import { createStrings, uiLocale } from "./Localization.sys.mjs";

export function initShell(win, { el: createElement, on, showPalette, openEditor, toolbox, open, motion, cleanup }) {
  const text = createStrings(win);
  const el = (tag, ...args) => createElement(tag === "button" ? "toolbarbutton" : tag, ...args);
  const doc = win.document;
  const browser = win.gBrowser;
  const rail = el("aside", { id: "forge-rail", lang: "ru", "aria-label": text("forge-sidebar-name") });
  const brand = el("div", { class: "forge-brand" });
  brand.append(el("img", { class: "forge-brand-mark", "aria-hidden": "true", src: "chrome://browser/content/forge/forge.svg" }),
    el("span", { class: "forge-brand-name" }, "forge"));
  const collapse = el("button", { id: "forge-sidebar-toggle", type: "button", "aria-controls": "forge-rail" });
  collapse.append(icon(doc, "sidebar"));
  brand.append(collapse);
  const applyCollapse = () => {
    const collapsed = Services.prefs.getBoolPref("forge.sidebar.collapsed", false);
    doc.documentElement.toggleAttribute("forge-sidebar-collapsed", collapsed);
    collapse.setAttribute("aria-expanded", String(!collapsed));
    collapse.setAttribute("aria-label", text(collapsed ? "forge-sidebar-expand" : "forge-sidebar-collapse"));
    collapse.setAttribute("tooltiptext", collapse.getAttribute("aria-label"));
  };
  const collapseObserver = { observe: applyCollapse };
  Services.prefs.addObserver("forge.sidebar.collapsed", collapseObserver);
  cleanup(() => Services.prefs.removeObserver("forge.sidebar.collapsed", collapseObserver));
  applyCollapse();
  on(collapse, "click", () => Services.prefs.setBoolPref("forge.sidebar.collapsed", collapse.getAttribute("aria-expanded") === "true"));
  const launcher = el("button", { class: "forge-launcher", type: "button", "aria-label": text("forge-sidebar-search-name"), "aria-controls": "forge-palette", "aria-haspopup": "dialog", "aria-expanded": "false" });
  launcher.append(icon(doc, "search"), el("span", {}, text("forge-sidebar-search")), el("kbd", {}, "⌘⌥⇧K"));
  on(launcher, "click", showPalette);
  const section = el("div", { class: "forge-section-label" }, text("forge-sidebar-tabs"));
  const count = el("span", { id: "forge-tab-count" });
  section.append(count);
  const newTab = el("button", { id: "forge-new-tab", type: "button", class: "forge-new-tab", "aria-label": text("forge-command-new-tab") });
  newTab.append(icon(doc, "plus"), el("span", {}, text("forge-command-new-tab")));
  on(newTab, "click", () => win.BrowserCommands.openTab());
  const tabs = el("div", { id: "forge-tabs", "aria-label": text("forge-sidebar-open-tabs") });
  const tools = el("div", { class: "forge-dev-tools", role: "group", "aria-label": text("forge-sidebar-tools") });
  const toolActions = [
    ["inspect", text("forge-tool-inspect"), () => toolbox("inspector")],
    ["terminal", text("forge-tool-console"), () => toolbox("webconsole")],
    ["network", text("forge-command-network"), () => toolbox("netmonitor")],
    ["palette", text("forge-command-appearance"), openEditor],
  ];
  for (const [iconName, title, run] of toolActions) {
    const button = el("button", { type: "button", class: "forge-tool", "aria-label": title, title });
    button.setAttribute("data-forge-tool", iconName);
    button.append(icon(doc, iconName), el("span", {}, title));
    on(button, "click", async () => {
      try { await run(); } catch (error) { win.console.error("Forge tool failed", error); }
    });
    tools.append(button);
  }
  const privacy = el("button", { type: "button", class: "forge-privacy-link", "aria-label": text("forge-sidebar-policies") });
  privacy.setAttribute("data-forge-tool", "shield");
  privacy.append(icon(doc, "shield"), el("span", {}, text("forge-sidebar-privacy")));
  privacy.title = text("forge-sidebar-policies-help");
  on(privacy, "click", () => open("about:policies"));
  tools.append(privacy);
  const toolButtons = Array.from(tools.children);
  const applyTools = () => {
    const { tools: ids } = readToolLayout(Services.prefs.getStringPref("forge.tools", "null"), Services.prefs.getStringPref("forge.tools.order", "null"));
    for (const button of toolButtons) { button.hidden = !ids.includes(button.getAttribute("data-forge-tool")); }
    for (const id of new Set(ids)) { const button = toolButtons.find(item => item.getAttribute("data-forge-tool") === id); if (button) { tools.append(button); } }
    const stored = Services.prefs.getStringPref("forge.shortcuts.palette", "K").toUpperCase();
    const key = /^[A-Z]$/.test(stored) && stored !== "R" ? stored : "K";
    launcher.querySelector("kbd").textContent = Services.appinfo.OS === "Darwin" ? `⌘⌥⇧${key}` : `Ctrl+Alt+Shift+${key}`;
    launcher.setAttribute("tooltiptext", text("forge-sidebar-palette-key", { key }));
  };
  const toolsObserver = { observe: applyTools };
  Services.prefs.addObserver("forge.tools", toolsObserver);
  Services.prefs.addObserver("forge.shortcuts.palette", toolsObserver);
  cleanup(() => Services.prefs.removeObserver("forge.tools", toolsObserver));
  cleanup(() => Services.prefs.removeObserver("forge.shortcuts.palette", toolsObserver));
  applyTools();
  const workspaces = createWorkspaces(win, { el, on, cleanup });
  rail.append(brand, launcher, workspaces.host, section, newTab, tabs, tools);
  doc.getElementById("browser").prepend(rail);
  const resize = el("div", { id: "forge-rail-resize", role: "separator", tabindex: "0", "aria-label": text("forge-sidebar-width"), "aria-orientation": "vertical", "aria-valuemin": "180", "aria-valuemax": "400" });
  rail.append(resize);
  const updateWidth = () => {
    const width = Math.min(400, Math.max(180, Services.prefs.getIntPref("forge.sidebar.width", 224)));
    doc.documentElement.style.setProperty("--forge-sidebar-width", `${width}px`);
    resize.setAttribute("aria-valuenow", String(width));
  };
  const widthObserver = { observe: updateWidth };
  Services.prefs.addObserver("forge.sidebar.width", widthObserver);
  cleanup(() => Services.prefs.removeObserver("forge.sidebar.width", widthObserver));
  updateWidth();
  on(resize, "pointerdown", event => { resize.setPointerCapture(event.pointerId); });
  on(resize, "pointermove", event => {
    if (resize.hasPointerCapture(event.pointerId)) {
      const rect = rail.getBoundingClientRect();
      const right = doc.documentElement.getAttribute("forge-sidebar-side") === "right";
      Services.prefs.setIntPref("forge.sidebar.width", Math.round(Math.min(400, Math.max(180, right ? rect.right - event.clientX : event.clientX - rect.left))));
    }
  });
  on(resize, "pointerup", event => { if (resize.hasPointerCapture(event.pointerId)) { resize.releasePointerCapture(event.pointerId); } });
  on(resize, "keydown", event => {
    if (!plainKey(event) || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) { return; }
    event.preventDefault();
    const current = Number(resize.getAttribute("aria-valuenow"));
    const right = doc.documentElement.getAttribute("forge-sidebar-side") === "right";
    const delta = (event.key === "ArrowRight" ? 8 : -8) * (right ? -1 : 1);
    const width = event.key === "Home" ? 180 : event.key === "End" ? 400 : current + delta;
    Services.prefs.setIntPref("forge.sidebar.width", Math.min(400, Math.max(180, width)));
  });
  const title = el("div", { id: "forge-window-title", "aria-hidden": "true" },
    `FORGE / ${(doc.documentElement.getAttribute("forge-appearance") || "amoled").toUpperCase()}`);
  doc.getElementById("TabsToolbar").prepend(title);

  // Keep native tab objects/session restore. This is a view, never a second tab store.
  const rows = new Map();
  const groupHeaders = new Map();
  function attachDrag(node, tabForNode) {
    node.draggable = true;
    node.addEventListener("dragstart", event => { const tab = tabForNode(); if (!tab?.isConnected || !event.dataTransfer) { event.preventDefault(); return; } beginDrag(tab, event.dataTransfer); });
    node.addEventListener("dragover", event => {
      if (draggedTab(event.dataTransfer, win, tabForNode(), true)) { event.preventDefault(); event.dataTransfer.dropEffect = "move"; node.setAttribute("data-drop", "true"); }
    });
    node.addEventListener("dragleave", () => node.removeAttribute("data-drop"));
    node.addEventListener("drop", event => {
      const source = draggedTab(event.dataTransfer, win, tabForNode());
      if (source) {
        event.preventDefault(); event.stopPropagation();
        try { transferTab(source, win, workspaces, tabForNode()); } catch (error) { win.console.error("Forge tab transfer failed", error); }
      }
      node.removeAttribute("data-drop"); endDrag();
    });
    node.addEventListener("dragend", () => { endDrag(); for (const item of tabs.querySelectorAll('[data-drop]')) { item.removeAttribute("data-drop"); } });
  }
  on(tabs, "dragover", event => {
    if (event.target === tabs && draggedTab(event.dataTransfer, win, null, true)) { event.preventDefault(); }
  });
  on(tabs, "drop", event => {
    if (event.target !== tabs) { return; }
    const source = draggedTab(event.dataTransfer, win);
    if (source) { event.preventDefault(); try { transferTab(source, win, workspaces); } catch (error) { win.console.error(error); } }
    endDrag();
  });
  const menu = doc.createXULElement("menupopup");
  menu.id = "forge-tab-menu";
  menu.setAttribute("lang", uiLocale());
  doc.getElementById("mainPopupSet").append(menu);
  cleanup(() => menu.remove());
  function openMenu(tab, event, position = null) {
    menu.replaceChildren();
    const action = (label, run, disabled = false, id = "") => {
      const item = doc.createXULElement("menuitem");
      item.setAttribute("label", label);
      if (id) { item.setAttribute("data-forge-action", id); }
      item.disabled = disabled;
      item.addEventListener("command", () => { try { run(); } catch (error) { win.console.error(error); } }, { once: true });
      menu.append(item);
    };
    action(text(tab.pinned ? "forge-tab-unpin" : "forge-tab-pin"), () => tab.pinned ? browser.unpinTab(tab) : browser.pinTab(tab));
    action(text("forge-tab-duplicate"), () => { const copy = browser.duplicateTab(tab); workspaces.assign(copy, workspaces.idFor(tab)); });
    action(text("forge-tab-new-window"), () => browser.replaceTabWithWindow(tab));
    for (const destination of Services.wm.getEnumerator("navigator:browser")) {
      if (destination === win || !canTransfer(tab, destination)) { continue; }
      action(text("forge-tab-move-window", { name: (destination.document.title || "Forge").slice(0, 80) }), () => {
        const targetShell = destination.document.getElementById("forge-rail");
        if (targetShell) { destination.dispatchEvent(new destination.CustomEvent("forge-adopt-tab", { detail: tab })); }
      }, false, "move-window");
    }
    if (!tab.pinned) {
      if (!tab.group) {
        action(text("forge-group-create"), () => {
          const name = win.prompt(text("forge-group-new-name"))?.trim().slice(0, 60);
          if (!name) { return; }
          const group = browser.addTabGroup([tab.splitview || tab], { label: name, insertBefore: tab.splitview || tab });
          if (group) { workspaces.assign(group.tabs[0], workspaces.state.active); }
        }, false, "group-create");
      } else {
        action(text("forge-group-rename"), () => { const name = win.prompt(text("forge-group-name"), tab.group.label)?.trim().slice(0, 60); if (name) { tab.group.label = name; } }, false, "group-rename");
        action(text(tab.group.collapsed ? "forge-group-expand" : "forge-group-collapse"), () => { tab.group.collapsed = !tab.group.collapsed; }, false, "group-collapse");
        action(text("forge-group-remove"), () => browser.ungroupTab(tab), false, "group-remove");
      }
      for (const group of browser.tabGroups) {
        if (group !== tab.group && group.tabs.every(member => workspaces.visible(member))) {
          action(text("forge-group-join", { name: group.label || text("forge-group-untitled") }), () => { group.addTabs([tab.splitview || tab]); workspaces.assign(tab, workspaces.state.active); }, false, "group-join");
        }
      }
    }
    action(text("forge-tab-reload"), () => browser.reloadTab(tab));
    action(text(tab.muted ? "forge-tab-unmute" : "forge-tab-mute"), () => tab.toggleMuteAudio());
    action(text("forge-tab-split"), () => {
      browser.addTabSplitView([browser.selectedTab, tab]);
      browser.selectedTab = tab;
    }, tab.selected || tab.pinned || browser.selectedTab.pinned || !!tab.splitview || !!browser.selectedTab.splitview);
    for (const space of workspaces.state.items) {
      if (space.id !== workspaces.idFor(tab)) {
        action(text("forge-tab-move-space", { name: space.name }), () => workspaces.move(tab, space.id), tab.pinned);
      }
    }
    action(text("forge-command-restore"), () => win.undoCloseTab());
    action(text("forge-tab-close-others"), () => {
      const others = Array.from(browser.tabs).filter(item => item !== tab && !item.pinned && workspaces.visible(item));
      if (others.length && win.confirm(text("forge-tab-confirm-close", { count: others.length }))) {
        browser.selectedTab = tab;
        browser.removeTabs(others);
      }
    });
    action(text("forge-tab-close"), () => browser.removeTab(tab));
    menu.openPopupAtScreen(position?.x ?? event.screenX, position?.y ?? event.screenY, true, event);
  }
  let mounted = false;
  let previousSelected = null;
  function renderTabs() {
    const before = new Map(Array.from(rows, ([tab, row]) => [tab, row.getBoundingClientRect()]));
    const added = new Set();
    const workspaceTabs = Array.from(browser.tabs).filter(tab => !tab.closing && workspaces.visible(tab));
    const currentTabs = workspaceTabs.filter(tab => !tab.group?.collapsed || tab.selected);
    const groups = new Set(workspaceTabs.map(tab => tab.group).filter(Boolean));
    for (const [group, header] of groupHeaders) { if (!groups.has(group)) { header.remove(); groupHeaders.delete(group); } }
    for (const group of groups) {
      let header = groupHeaders.get(group);
      if (!header) {
        header = el("button", { class: "forge-group-toggle", "data-forge-group": group.id, "aria-label": text("forge-group-label") });
        header.append(icon(doc, "grid"), el("span"));
        header.addEventListener("command", () => { group.collapsed = !group.collapsed; });
        header.addEventListener("contextmenu", event => { event.preventDefault(); openMenu(group.tabs[0], event); });
        attachDrag(header, () => group.tabs[0]);
        groupHeaders.set(group, header);
      }
      const name = group.label || text("forge-group-untitled");
      header.querySelector("span").textContent = `${name} · ${group.tabs.length}`;
      header.setAttribute("aria-label", text("forge-group-accessible", { name, count: group.tabs.length }));
      header.setAttribute("aria-expanded", String(!group.collapsed));
      header.setAttribute("tooltiptext", text("forge-group-help", { name }));
    }
    const currentSet = new Set(currentTabs);
    count.textContent = String(currentTabs.length);
    for (const [tab, row] of rows) {
      if (!currentSet.has(tab)) {
        const needsFocus = row.contains(doc.activeElement);
        row.inert = true;
        row.setAttribute("data-leaving", "true");
        const top = row.offsetTop;
        const width = row.getBoundingClientRect().width;
        row.style.position = "absolute";
        row.style.top = `${top}px`;
        row.style.width = `${width}px`;
        rows.delete(tab);
        motion.remove(row);
        if (needsFocus) {
          win.requestAnimationFrame(() => rows.get(browser.selectedTab)?.querySelector(".forge-tab-select").focus());
        }
      }
    }
    currentTabs.forEach((tab, index) => {
      let row = rows.get(tab);
      if (!row) {
        row = el("div", { class: "forge-tab" });
        const select = el("button", { type: "button", class: "forge-tab-select" });
        const marker = el("span", { class: "forge-tab-marker", "aria-hidden": "true" });
        const favicon = el("img", { class: "forge-tab-favicon", "aria-hidden": "true" });
        const fallback = icon(doc, "globe");
        marker.append(favicon, fallback);
        favicon.addEventListener("error", () => {
          favicon.dataset.failedSource = favicon.getAttribute("src") || "";
          favicon.hidden = true; fallback.removeAttribute("hidden");
        });
        const label = el("span", { class: "forge-tab-label" });
        select.append(marker, label);
        const close = el("button", { type: "button", class: "forge-tab-close" });
        close.append(icon(doc, "close"));
        // Removed tab rows release these listeners with their native tab references.
        select.addEventListener("command", () => { browser.selectedTab = tab; });
        close.addEventListener("command", () => browser.removeTab(tab, { animate: true }));
        row.addEventListener("auxclick", event => {
          if (event.button === 1) { event.preventDefault(); browser.removeTab(tab); }
        });
        const audio = el("button", { type: "button", class: "forge-tab-audio" });
        audio.addEventListener("command", () => tab.toggleMuteAudio());
        row.append(select, audio, close);
        attachDrag(row, () => tab);
        row.addEventListener("contextmenu", event => { event.preventDefault(); openMenu(tab, event); });
        row.addEventListener("keydown", event => {
          if (event.defaultPrevented || event.isComposing) { return; }
          if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
            event.preventDefault();
            const rect = row.getBoundingClientRect();
            openMenu(tab, event, { x: win.mozInnerScreenX + rect.left, y: win.mozInnerScreenY + rect.bottom });
          }
        });
        rows.set(tab, row);
        added.add(tab);
      }
      const favicon = row.querySelector(".forge-tab-favicon");
      const image = browser.getIcon(tab);
      if (image && favicon.getAttribute("src") !== image) { delete favicon.dataset.failedSource; favicon.src = image; }
      const validIcon = !!image && favicon.dataset.failedSource !== image;
      favicon.hidden = !validIcon;
      row.querySelector('.forge-tab-marker > svg').toggleAttribute("hidden", validIcon);
      for (const attr of ["busy", "pending", "pinned", "soundplaying", "muted"]) { row.toggleAttribute(attr, tab.hasAttribute(attr)); }
      row.style.setProperty("--forge-container", "transparent");
      const contextId = tab.getAttribute("usercontextid");
      if (contextId && contextId !== "0") {
        const { ContextualIdentityService } = ChromeUtils.importESModule("moz-src:///toolkit/components/contextualidentity/ContextualIdentityService.sys.mjs");
        const identity = ContextualIdentityService.getPublicIdentityFromId(Number(contextId));
        if (identity) { row.style.setProperty("--forge-container", ContextualIdentityService.getContainerColorCode(identity.color)); }
      }
      const audio = row.querySelector(".forge-tab-audio");
      audio.hidden = !tab.hasAttribute("soundplaying") && !tab.hasAttribute("muted");
      const audioName = text(tab.hasAttribute("muted") ? "forge-tab-unmute" : "forge-tab-mute");
      audio.setAttribute("aria-label", audioName); audio.setAttribute("tooltiptext", audioName);
      const audioIcon = tab.hasAttribute("muted") ? "muted" : "sound";
      if (audio.firstElementChild?.getAttribute("data-forge-icon") !== audioIcon) { audio.replaceChildren(icon(doc, audioIcon)); }
      row.querySelector(".forge-tab-label").textContent = tab.label || text("forge-command-new-tab");
      row.querySelector(".forge-tab-select").setAttribute("tooltiptext", [tab.label, tab.linkedBrowser.currentURI.displaySpec, tab.pinned && text("forge-tab-pinned"), tab.hasAttribute("pending") && text("forge-tab-unloaded")].filter(Boolean).join("\n"));
      row.querySelector(".forge-tab-select").setAttribute("aria-label", tab.label || text("forge-command-new-tab"));
      row.querySelector(".forge-tab-select").setAttribute("aria-current", tab.selected ? "page" : "false");
      row.querySelector(".forge-tab-close").setAttribute("aria-label", text("forge-tab-close-named", { name: tab.label }));
      row.querySelector(".forge-tab-close").setAttribute("tooltiptext", text("forge-tab-close-named", { name: tab.label }));
      row.toggleAttribute("selected", tab.selected);
      // Move only when order changed, preserving keyboard focus for existing rows.
      const previous = index ? rows.get(currentTabs[index - 1]) : null;
      const anchor = previous ? previous.nextElementSibling : tabs.firstElementChild;
      if (anchor !== row) { tabs.insertBefore(row, anchor); }
    });
    const ordered = [], seen = new Set();
    for (const tab of workspaceTabs) {
      if (tab.group && !seen.has(tab.group)) { ordered.push(groupHeaders.get(tab.group)); seen.add(tab.group); }
      if (rows.has(tab)) { ordered.push(rows.get(tab)); }
    }
    let cursor = tabs.firstElementChild;
    for (const node of ordered) { if (node !== cursor) { tabs.insertBefore(node, cursor); } cursor = node.nextElementSibling; }
    const after = new Map(Array.from(rows, ([tab, row]) => [tab, row.getBoundingClientRect()]));
    if (mounted) {
      for (const [tab, row] of rows) {
        if (added.has(tab)) {
          motion.animate(row, [{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "translateY(0)" }]);
        } else if (before.has(tab)) {
          const delta = before.get(tab).top - after.get(tab).top;
          if (Math.abs(delta) > .5) {
            motion.animate(row, [{ transform: `translateY(${delta}px)` }, { transform: "translateY(0)" }], { duration: 160 });
          }
        }
      }
    }
    if (previousSelected !== browser.selectedTab) {
      rows.get(browser.selectedTab)?.scrollIntoView({ block: "nearest", behavior: "instant" });
      previousSelected = browser.selectedTab;
    }
  }
  let frame = null;
  const schedule = () => {
    if (frame !== null) { return; }
    frame = win.requestAnimationFrame(() => { frame = null; renderTabs(); });
  };
  for (const event of ["TabOpen", "TabClose", "TabSelect", "TabAttrModified", "TabMove", "TabPinned", "TabUnpinned", "TabHide", "TabShow", "TabGroupCreate", "TabGroupRemoved", "TabGroupCollapse", "TabGroupExpand", "TabGroupUpdate", "TabGrouped", "TabUngrouped"]) {
    on(browser.tabContainer, event, schedule);
  }
  on(win, "forge-workspace-change", schedule);
  on(win, "forge-adopt-tab", event => { if (event.detail?.ownerDocument?.defaultView?.gBrowser) { transferTab(event.detail, win, workspaces); } });
  on(tabs, "keydown", event => {
    if (event.defaultPrevented || event.isComposing) { return; }
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key) || !doc.activeElement.classList.contains("forge-tab-select")) { return; }
    const reorder = event.altKey && event.shiftKey && !event.ctrlKey && !event.metaKey && ["ArrowUp", "ArrowDown"].includes(event.key);
    if (!plainKey(event) && !reorder) { return; }
    event.preventDefault();
    const buttons = Array.from(tabs.querySelectorAll(".forge-tab:not([data-leaving]) .forge-tab-select"));
    const index = buttons.indexOf(doc.activeElement);
    if (reorder) {
      const focused = Array.from(rows).find(([, row]) => row.contains(doc.activeElement))?.[0];
      if (focused) { browser.moveTabTo(unitFor(focused), { tabIndex: focused.index + (event.key === "ArrowDown" ? 1 : -1) }); }
      return;
    }
    if (event.key === "Home" || event.key === "End") { buttons[event.key === "Home" ? 0 : buttons.length - 1]?.focus(); return; }
    buttons[(index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
  });
  cleanup(() => {
    if (frame !== null) { win.cancelAnimationFrame(frame); }
    rows.clear();
    groupHeaders.clear(); endDrag(win);
  });
  renderTabs();
  mounted = true;
  // Don't hide native chrome until the alternative view has mounted successfully.
  doc.documentElement.setAttribute("forge-shell", "true");
  return { workspaces };
}
