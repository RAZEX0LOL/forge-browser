/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */

import { icon } from "./Icons.sys.mjs";
import { toolbarButton } from "./Toolbar.sys.mjs";
import { restoreDialogFocus } from "./Keyboard.sys.mjs";
import { createStrings } from "./Localization.sys.mjs";

export function initControlCenter(win, { el: createElement, on, cleanup, commands }) {
  const el = (tag, ...args) => createElement(tag === "button" ? "toolbarbutton" : tag, ...args);
  const doc = win.document;
  const t = createStrings(win);
  const hub = el("dialog", { id: "forge-control-center", role: "dialog", lang: "ru", "aria-label": t("forge-hub-name"), "aria-labelledby": "forge-hub-title" });
  let opener = null;
  let runningAction = false;
  on(hub, "close", () => {
    if (!runningAction) { restoreDialogFocus(hub, opener, [doc.getElementById("forge-hub-button"), win.gURLBar.inputField]); }
  });
  const header = el("header", { class: "forge-hub-header" });
  const intro = el("div");
  intro.append(el("p", { class: "forge-hub-eyebrow" }, t("forge-hub-eyebrow")),
    el("h2", { id: "forge-hub-title" }, t("forge-hub-title")), el("p", {}, t("forge-hub-description")));
  const close = el("button", { type: "button", class: "forge-hub-close", "aria-label": t("forge-hub-close") });
  close.append(icon(doc, "close"));
  on(close, "click", () => hub.close());
  header.append(intro, close);
  hub.append(header);
  const groups = Array.from(new Set(commands.map(command => command.group).filter(Boolean)), group => [group, commands.filter(command => command.group === group)]);
  let itemIndex = 0;
  for (const [title, items] of groups) {
    const section = el("section", { class: "forge-hub-section" });
    section.append(el("h3", {}, title));
    const grid = el("div", { class: "forge-hub-grid" });
    for (const { icon: iconName, title: label, run } of items) {
      const description = label;
      const action = el("button", { type: "button", class: "forge-hub-action", "data-action": label, "aria-label": label });
      action.title = description;
      action.style.setProperty("--forge-item-index", Math.min(itemIndex++, 6));
      const text = el("span");
      text.append(el("strong", {}, label), el("small", {}, description));
      const badge = el("span", { class: "forge-hub-icon", "aria-hidden": "true" });
      badge.append(icon(doc, iconName));
      action.append(badge, text);
      on(action, "click", async () => {
        runningAction = true;
        hub.close();
        try { await run(); } catch (error) { win.console.error("Forge control action failed", error); }
      });
      grid.append(action);
    }
    section.append(grid);
    hub.append(section);
  }
  const footer = el("footer", { class: "forge-hub-footer" });
  const nativeMenu = el("button", { type: "button", id: "forge-native-menu", "aria-label": t("forge-hub-more"), "aria-haspopup": "true" });
  nativeMenu.append(el("span", {}, t("forge-hub-more")), icon(doc, "arrow"));
  on(nativeMenu, "click", () => {
    runningAction = true;
    hub.close();
    doc.documentElement.setAttribute("forge-native-menu-open", "true");
    win.PanelUI.show();
  });
  on(doc, "popuphidden", event => {
    if (event.target.id === "appMenu-popup") {
      doc.documentElement.removeAttribute("forge-native-menu-open");
    }
  });
  footer.append(el("span", {}, t("forge-hub-privacy")), nativeMenu);
  hub.append(footer);
  doc.body.append(hub);
  const hubButton = toolbarButton(win, "forge-hub-button", cleanup);
  hubButton?.setAttribute("aria-controls", hub.id);
  hubButton?.setAttribute("aria-haspopup", "dialog");
  hubButton?.setAttribute("aria-expanded", "false");
  on(hub, "toggle", () => hubButton?.setAttribute("aria-expanded", String(hub.open)));
  on(win, "forge-show-center", () => {
    if (hub.open) { hub.close(); return; }
    opener = doc.activeElement;
    runningAction = false;
    for (const id of ["forge-palette", "forge-editor", "forge-shortcuts"]) {
      const dialog = doc.getElementById(id);
      if (dialog?.open) { dialog.close(); }
    }
    hub.showModal();
  });
  doc.documentElement.setAttribute("forge-center", "true");
  return hub;
}
