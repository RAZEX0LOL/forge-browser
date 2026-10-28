/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { normalizeTheme, readTheme, searchCommands, parseSettingsTransfer, THEME_PRESETS,
  DEFAULT_THEME, readToolLayout, presetForTheme, MAX_CUSTOM_CSS_LENGTH, parseCommandBindings } from "./core.sys.mjs";
import { initShell } from "./Shell.sys.mjs";
import { initControlCenter } from "./ControlCenter.sys.mjs";
import { createMotion } from "./Motion.sys.mjs";
import { toolbarButton } from "./Toolbar.sys.mjs";
import { createCommands } from "./Commands.sys.mjs";
import { projectCommands } from "./Projects.sys.mjs";
import { plainKey, restoreDialogFocus, bindDialogTabCycle } from "./Keyboard.sys.mjs";
import { initShortcuts } from "./Shortcuts.sys.mjs";
import { createStrings, formatError, uiLocale } from "./Localization.sys.mjs";

// Services is a built-in privileged global in current Firefox ES modules.
const HTML = "http://www.w3.org/1999/xhtml";
const THEME_PREF = "forge.theme";
const CSS_PREF = "forge.customCSS";
const CSS_ENABLED_PREF = "forge.customCSS.enabled";
const instances = new WeakMap();

export function destroy(win) { instances.get(win)?.(); }

export function init(win) {
  const doc = win.document;
  const t = createStrings(win);
  if (instances.has(win) || !win.toolbar.visible) {
    return;
  }
  const abort = new win.AbortController();
  const motion = createMotion(win);
  const nodes = [];
  let initializing = true;
  const disposers = [];
  const cleanup = callback => disposers.push(callback);
  const dispose = () => {
    abort.abort(); motion.destroy();
    for (const callback of disposers.reverse()) { try { callback(); } catch (error) { win.console.error(error); } }
    for (const node of nodes.reverse()) { node.remove(); }
    for (const name of ["forge-shell", "forge-center", "forge-ready", "forge-sidebar-collapsed", "forge-native-menu-open", "forge-density", "forge-appearance", "forge-motion", "forge-sidebar-side"]) { doc.documentElement.removeAttribute(name); }
    for (const name of ["--forge-sidebar-width", "--forge-accent", "--forge-radius"]) { doc.documentElement.style.removeProperty(name); }
    instances.delete(win);
  };
  instances.set(win, dispose);
  try {
  const nativeEvent = (node, event) => event === "click" && node.namespaceURI === "http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul" && ["button", "toolbarbutton"].includes(node.localName) ? "command" : event;
  const on = (node, event, handler) => node.addEventListener(nativeEvent(node, event), handler, {
    signal: abort.signal,
  });
  function el(tag, attributes = {}, text = "") {
    const native = ["toolbarbutton", "native-button"].includes(tag);
    const node = native ? doc.createXULElement(tag === "native-button" ? "button" : tag) : doc.createElementNS(HTML, tag);
    if (initializing) { nodes.push(node); }
    for (const [key, value] of Object.entries(attributes)) {
      if (native && key === "type" && value === "button") { continue; }
      node.setAttribute(key, key === "lang" ? uiLocale() : value);
      if (native && key === "title") { node.setAttribute("tooltiptext", value); }
    }
    if (native) {
      node.classList.add(tag === "native-button" ? "forge-dialog-button" : "toolbarbutton-1", "forge-native-control");
      node.setAttribute("tabindex", "0");
      if (text) { node.setAttribute("label", text); }
    } else { node.textContent = text; }
    return node;
  }
  const style = el("link", {
    rel: "stylesheet", href: "chrome://browser/content/forge/forge.css",
  });
  doc.head.append(style);
  // This is a UI customization mechanism, not a sandbox for untrusted themes.
  const customStyle = el("style", { id: "forge-user-style" });
  doc.head.append(customStyle);
  let customURI = null;
  cleanup(() => { if (customURI) { win.windowUtils.removeSheetUsingURIString(customURI, win.windowUtils.USER_SHEET); } });
  let lastCSS = "";
  let editorPreferencesChanged = null;
  const applyPreferences = () => {
    const theme = readTheme(Services.prefs.getStringPref(THEME_PREF, "{}"));
    const root = doc.documentElement;
    root.style.setProperty("--forge-accent", theme.accent);
    root.style.setProperty("--forge-radius", `${theme.radius}px`);
    root.setAttribute("forge-density", theme.density);
    root.setAttribute("forge-appearance", theme.appearance);
    root.setAttribute("forge-motion", theme.motion);
    root.setAttribute("forge-sidebar-side", theme.sidebarSide);
    const paletteKey = Services.prefs.getStringPref("forge.shortcuts.palette", "K").toUpperCase();
    doc.getElementById("forge-command-key")?.setAttribute("key", /^[A-Z]$/.test(paletteKey) && paletteKey !== "R" ? paletteKey : "K");
    if (theme.motion === "off") { motion.cancelAll(); }
    const title = doc.getElementById("forge-window-title");
    if (title) { title.textContent = `FORGE / ${theme.appearance.toUpperCase()}`; }
    const cssText = Services.prefs.getBoolPref(CSS_ENABLED_PREF, false)
      ? Services.prefs.getStringPref(CSS_PREF, "") : "";
    // Keep the inspectable style node, but apply the editor as a window-local
    // USER sheet so trusted custom CSS can override the shared design system.
    customStyle.textContent = cssText;
    if (cssText !== lastCSS) {
      if (customURI) { win.windowUtils.removeSheetUsingURIString(customURI, win.windowUtils.USER_SHEET); }
      customURI = cssText ? `data:text/css;charset=utf-8,${encodeURIComponent(cssText)}` : null;
      if (customURI) { win.windowUtils.loadSheetUsingURIString(customURI, win.windowUtils.USER_SHEET); }
      lastCSS = cssText;
    }
  };
  const prefObserver = { observe(_subject, _topic, name) { applyPreferences(); editorPreferencesChanged?.(name); } };
  Services.prefs.addObserver("forge.", prefObserver);
  cleanup(() => Services.prefs.removeObserver("forge.", prefObserver));
  applyPreferences();

  const commandButton = toolbarButton(win, "forge-command-button", cleanup);
  commandButton?.setAttribute("aria-controls", "forge-palette");
  commandButton?.setAttribute("aria-haspopup", "dialog");
  commandButton?.setAttribute("aria-expanded", "false");

  const palette = el("dialog", { id: "forge-palette", role: "dialog", lang: "ru", "aria-label": t("forge-palette-name"), "aria-labelledby": "forge-palette-title" });
  let paletteOpener = null;
  let executingPaletteCommand = false;
  on(palette, "toggle", () => {
    for (const node of [commandButton, doc.querySelector(".forge-launcher")]) {
      node?.setAttribute("aria-expanded", String(palette.open));
    }
  });
  on(palette, "close", () => {
    if (!executingPaletteCommand) {
      restoreDialogFocus(palette, paletteOpener, [doc.querySelector(".forge-launcher"), doc.getElementById("forge-command-button"), win.gURLBar.inputField]);
    }
  });
  const heading = el("h2", { id: "forge-palette-title" }, t("forge-palette-name"));
  const search = el("input", {
    type: "search", placeholder: t("forge-palette-placeholder"),
    "aria-label": t("forge-palette-search"), "aria-controls": "forge-palette-results", "aria-describedby": "forge-palette-status", autocomplete: "off",
  });
  const results = el("div", { id: "forge-palette-results", class: "forge-results", role: "group", "aria-label": t("forge-palette-results") });
  const status = el("p", { id: "forge-palette-status", role: "status", "aria-live": "polite", "aria-atomic": "true", class: "forge-status" });
  const close = el("native-button", { type: "button", class: "forge-close" }, t("forge-palette-close"));
  palette.append(heading, search, results, status, close);
  doc.body.append(palette);

  const editor = el("dialog", { id: "forge-editor", role: "dialog", lang: "ru", "aria-label": t("forge-editor-name"), "aria-labelledby": "forge-editor-title", "aria-describedby": "forge-editor-description" });
  const editorHeader = el("header", { class: "forge-editor-header" });
  editorHeader.append(el("h2", { id: "forge-editor-title" }, t("forge-command-appearance")),
    el("p", { id: "forge-editor-description" }, t("forge-editor-description")));
  const editorBody = el("div", { class: "forge-editor-body" });
  const feedback = el("p", { id: "forge-editor-feedback", role: "status", "aria-live": "polite" });
  editor.append(editorHeader, editorBody);
  const prefNames = [THEME_PREF, CSS_PREF, CSS_ENABLED_PREF, "forge.shortcuts.palette", "forge.tools", "forge.tools.order"];
  const snapshot = () => Object.fromEntries(prefNames.map(name => [name,
    Services.prefs.prefHasUserValue(name) ? (name === CSS_ENABLED_PREF ? Services.prefs.getBoolPref(name) : Services.prefs.getStringPref(name)) : null]));
  const restore = data => {
    for (const name of prefNames) {
      if (data[name] === null) { Services.prefs.clearUserPref(name); }
      else if (name === CSS_ENABLED_PREF) { Services.prefs.setBoolPref(name, data[name]); }
      else { Services.prefs.setStringPref(name, data[name]); }
    }
  };
  let beforePreview = null;
  let previewValue = null;
  let lastSaved = null;
  let lastCommit = null;
  let editingBaseline = null;
  let committing = false;
  let returnFocus = null;
  const sameSnapshot = (left, right) => !!left && !!right && prefNames.every(name => left[name] === right[name]);
  const finishPreview = () => {
    // A preview only owns the theme it last wrote, not other windows' changes
    // or unrelated layout/CSS preferences changed while the editor is open.
    if (beforePreview && Services.prefs.getStringPref(THEME_PREF, "{}") === previewValue) {
      if (beforePreview[THEME_PREF] === null) { Services.prefs.clearUserPref(THEME_PREF); }
      else { Services.prefs.setStringPref(THEME_PREF, beforePreview[THEME_PREF]); }
    }
    beforePreview = null; previewValue = null;
  };
  const beforeCommit = () => {
    const current = snapshot();
    if (beforePreview && Services.prefs.getStringPref(THEME_PREF, "{}") === previewValue) { current[THEME_PREF] = beforePreview[THEME_PREF]; }
    return current;
  };
  cleanup(finishPreview);
  on(editor, "close", () => {
    if (editor.open) { return; }
    finishPreview();
    restoreDialogFocus(editor, returnFocus, [doc.querySelector('[data-forge-tool="palette"]'), doc.getElementById("forge-hub-button"), win.gURLBar.inputField]);
  });
  on(editor, "cancel", finishPreview);
  const appearance = el("select", { "data-setting": "appearance" });
  appearance.append(el("option", { value: "amoled" }, t("forge-editor-amoled")),
    el("option", { value: "glass" }, t("forge-editor-glass")));
  const accent = el("input", { type: "color", "aria-label": t("forge-editor-accent") });
  const accentHex = el("input", { id: "forge-accent-hex", type: "text", maxlength: "7", spellcheck: "false", autocomplete: "off", "aria-label": t("forge-editor-hex"), placeholder: "#A4EFCE" });
  const accentControls = el("div", { class: "forge-accent-controls" });
  accentControls.append(accent, accentHex);
  const radius = el("input", { type: "range", min: "0", max: "24", step: "1", "data-setting": "radius", "aria-label": t("forge-editor-radius") });
  const density = el("select", { "data-setting": "density" });
  density.append(el("option", { value: "comfortable" }, t("forge-editor-comfortable")),
    el("option", { value: "compact" }, t("forge-editor-compact")));
  const animations = el("select", { "data-setting": "motion" });
  animations.append(el("option", { value: "system" }, t("forge-editor-motion-system")),
    el("option", { value: "off" }, t("forge-editor-motion-off")));
  const enabled = el("input", { type: "checkbox" });
  const css = el("textarea", {
    rows: "10", spellcheck: "false", "aria-label": t("forge-editor-css"),
    placeholder: "/* #nav-bar { border-bottom: 2px solid var(--forge-accent); } */",
  });
  function field(title, input) {
    const label = el("label", { class: "forge-field" }, title);
    if (input.matches("input, select, textarea") && !input.hasAttribute("aria-label")) { input.setAttribute("aria-label", title); }
    label.append(input);
    editorBody.append(label);
  }
  const preset = el("select", { id: "forge-theme-preset", "aria-label": t("forge-editor-preset") });
  for (const value of ["", "default", "amoled", "glass", "compact", "contrast"]) {
    preset.append(el("option", { value }, t(`forge-preset-${value || "custom"}`)));
  }
  field(t("forge-editor-preset"), preset);
  on(preset, "change", () => { if (THEME_PRESETS[preset.value]) { populate(THEME_PRESETS[preset.value], css.value); updateEditorUI(); } });
  field(t("forge-editor-style"), appearance);
  field(t("forge-editor-accent"), accentControls);
  field(t("forge-editor-radius"), radius);
  const radiusOutput = el("output", { "aria-hidden": "true" });
  radius.parentElement.append(radiusOutput);
  const updateRadius = () => { radiusOutput.value = `${radius.value} px`; radius.setAttribute("aria-valuetext", radiusOutput.value); };
  on(radius, "input", updateRadius);
  field(t("forge-editor-density"), density);
  field(t("forge-editor-motion"), animations);
  const extraControls = new Map();
  function optionsField(parent, name, title, options) {
    const control = el("select", { "data-setting": name });
    for (const [value, label] of options) { control.append(el("option", { value }, label)); }
    field(title, control); parent.append(control.parentElement); extraControls.set(name, control);
  }
  function rangeField(parent, name, title, min, max, unit = "px") {
    const control = el("input", { type: "range", min, max, step: "1", "data-setting": name, "aria-label": title });
    field(title, control);
    const label = control.parentElement;
    const output = el("output", { "aria-hidden": "true" });
    label.append(output); parent.append(label); extraControls.set(name, control);
    const update = () => { output.value = `${control.value} ${unit}`; control.setAttribute("aria-valuetext", output.value); };
    on(control, "input", update);
    control.forgeUpdateOutput = update;
  }
  const geometry = el("details", { id: "forge-geometry-settings" });
  geometry.append(el("summary", {}, t("forge-editor-geometry")));
  optionsField(geometry, "sidebarSide", t("forge-editor-sidebarSide"), [["left", t("forge-option-left")], ["right", t("forge-option-right")]]);
  optionsField(geometry, "contrast", t("forge-editor-contrast"), [["soft", t("forge-option-soft")], ["balanced", t("forge-option-balanced")], ["strong", t("forge-option-strong")]]);
  optionsField(geometry, "startLayout", t("forge-command-new-tab"), [["center", t("forge-option-center")], ["top", t("forge-option-top")]]);
  for (const [name, min, max] of [
    ["compactWidth", 72, 104], ["iconSize", 16, 22], ["tabHeight", 32, 52],
    ["toolbarHeight", 40, 64], ["contentGap", 0, 16], ["controlRadius", 0, 10],
  ]) { rangeField(geometry, name, t(`forge-editor-${name}`), min, max); }
  editorBody.append(geometry);
  const glassSettings = el("details", { id: "forge-glass-settings" });
  glassSettings.append(el("summary", {}, t("forge-editor-glass-section")));
  glassSettings.append(el("p", { class: "forge-editor-help" }, t("forge-editor-glass-help")));
  rangeField(glassSettings, "glassOpacity", t("forge-editor-glassOpacity"), 45, 95, "%");
  rangeField(glassSettings, "blur", t("forge-editor-blur"), 0, 40);
  editorBody.append(glassSettings);
  const layout = el("details", { id: "forge-layout-settings" });
  layout.append(el("summary", {}, t("forge-editor-layout")));
  const shortcut = el("input", { id: "forge-palette-shortcut", type: "text", maxlength: "1", "aria-label": t("forge-editor-shortcut") });
  const shortcutLabel = el("label", { class: "forge-field" }, t("forge-editor-shortcut-help"));
  shortcutLabel.append(shortcut); layout.append(shortcutLabel);
  const dock = el("div", { id: "forge-dock-settings" });
  const toolNames = [["inspect", t("forge-tool-inspect")], ["terminal", t("forge-tool-console")], ["network", t("forge-command-network")], ["palette", t("forge-command-appearance")], ["shield", t("forge-command-privacy")]];
  for (const [id, title] of toolNames) {
    const row = el("div", { class: "forge-dock-setting", "data-tool": id });
    const check = el("input", { type: "checkbox", "aria-label": title });
    const label = el("label", {}, title); label.prepend(check);
    const up = el("native-button", { type: "button", "aria-label": t("forge-editor-up", { name: title }) }, "↑");
    const down = el("native-button", { type: "button", "aria-label": t("forge-editor-down", { name: title }) }, "↓");
    up.setAttribute("data-move", "up"); down.setAttribute("data-move", "down");
    on(up, "click", () => { if (row.previousElementSibling) { dock.insertBefore(row, row.previousElementSibling); updateEditorUI(); (up.disabled ? check : up).focus(); } });
    on(down, "click", () => { if (row.nextElementSibling) { dock.insertBefore(row.nextElementSibling, row); updateEditorUI(); (down.disabled ? check : down).focus(); } });
    row.append(label, up, down); dock.append(row);
  }
  layout.append(dock); editorBody.append(layout);
  const advanced = el("details", { id: "forge-editor-advanced" });
  advanced.append(el("summary", {}, t("forge-editor-advanced")));
  const warning = el("p", { id: "forge-css-warning", class: "forge-warning" },
    t("forge-editor-css-warning"));
  field(t("forge-editor-css-enable"), enabled);
  enabled.setAttribute("aria-describedby", "forge-css-warning");
  css.setAttribute("aria-describedby", "forge-css-warning forge-editor-feedback");
  accentHex.setAttribute("aria-describedby", "forge-editor-feedback");
  shortcut.setAttribute("aria-describedby", "forge-editor-feedback");
  advanced.append(warning, enabled.parentElement, css);
  const cssDisable = el("native-button", { id: "forge-css-disable", type: "button" }, t("forge-editor-css-disable"));
  const cssClear = el("native-button", { id: "forge-css-clear", type: "button" }, t("forge-editor-css-clear"));
  const cssActions = el("div", { class: "forge-editor-inline-actions" });
  cssActions.append(cssDisable, cssClear);
  advanced.append(cssActions, el("p", { class: "forge-editor-help" }, t("forge-editor-css-help")));
  editorBody.append(advanced);
  const transfer = el("details", { id: "forge-settings-transfer" });
  transfer.append(el("summary", {}, t("forge-editor-transfer")));
  const transferText = el("textarea", { rows: "5", "aria-label": t("forge-editor-json"), placeholder: t("forge-editor-json-placeholder") });
  const exportButton = el("native-button", { type: "button" }, t("forge-editor-export"));
  const importButton = el("native-button", { type: "button" }, t("forge-editor-import"));
  const copyButton = el("native-button", { id: "forge-settings-copy", type: "button" }, t("forge-editor-copy"));
  const transferStatus = el("p", { role: "status" });
  transfer.append(el("p", { class: "forge-editor-help" }, t("forge-editor-transfer-help")), transferText, exportButton, importButton, copyButton, transferStatus);
  editorBody.append(transfer);
  function populate(theme, text) {
    appearance.value = theme.appearance; accent.value = theme.accent; radius.value = theme.radius;
    density.value = theme.density; animations.value = theme.motion; css.value = text;
    accentHex.value = theme.accent.toUpperCase(); updateRadius();
    for (const [name, control] of extraControls) { control.value = theme[name]; control.forgeUpdateOutput?.(); }
    preset.value = presetForTheme(theme);
  }
  const draftTheme = () => normalizeTheme({ appearance: appearance.value, motion: animations.value, accent: accent.value, radius: Number(radius.value), density: density.value,
    ...Object.fromEntries(Array.from(extraControls, ([name, control]) => [name, control.type === "range" ? Number(control.value) : control.value])),
  });
  on(exportButton, "click", () => {
    if (!validateEditor()) { return; }
    transferText.value = JSON.stringify({ version: 2, theme: draftTheme(), css: css.value, layout: draftLayout() }, null, 2);
    transferText.focus(); transferText.select();
    transferStatus.textContent = t("forge-editor-json-ready");
    updateEditorUI();
  });
  on(importButton, "click", () => {
    try {
      const data = parseSettingsTransfer(transferText.value);
      finishPreview();
      populate(data.theme, data.css); enabled.checked = false;
      if (data.layout) { populateLayout(data.layout); }
      transferStatus.setAttribute("role", "status");
      transferStatus.textContent = t("forge-editor-imported");
      updateEditorUI();
    } catch (error) { transferStatus.setAttribute("role", "alert"); transferStatus.textContent = t("forge-editor-import-error", { error: formatError(t, error) }); }
  });
  on(copyButton, "click", async () => {
    if (!transferText.value.trim()) { return; }
    try {
      await win.navigator.clipboard.writeText(transferText.value);
      transferStatus.setAttribute("role", "status"); transferStatus.textContent = t("forge-editor-copied");
    } catch {
      transferText.focus(); transferText.select(); transferStatus.setAttribute("role", "alert");
      transferStatus.textContent = t("forge-editor-copy-failed");
    }
  });
  const actions = el("div", { class: "forge-actions" });
  const save = el("native-button", { type: "button", default: "true", id: "forge-theme-save" }, t("forge-save"));
  const reset = el("native-button", { type: "button", id: "forge-theme-reset", title: t("forge-editor-reset-help") }, t("forge-editor-reset"));
  const cancel = el("native-button", { type: "button", id: "forge-theme-cancel" }, t("forge-cancel"));
  const preview = el("native-button", { type: "button", id: "forge-theme-preview", title: t("forge-editor-preview-help") }, t("forge-editor-preview"));
  const undo = el("native-button", { type: "button", id: "forge-theme-undo", title: t("forge-editor-undo-help") }, t("forge-editor-undo"));
  const revertPreview = el("native-button", { type: "button", id: "forge-theme-revert", title: t("forge-editor-revert-help") }, t("forge-editor-revert"));
  const reload = el("native-button", { type: "button", id: "forge-editor-reload", title: t("forge-editor-reload-help") }, t("forge-shortcuts-reload"));
  reload.hidden = true; editorHeader.append(reload);
  const secondaryActions = el("div", { class: "forge-editor-secondary-actions" });
  secondaryActions.append(revertPreview, undo, reset);
  const primaryActions = el("div", { class: "forge-editor-primary-actions" });
  primaryActions.append(preview, cancel, save);
  actions.append(secondaryActions, primaryActions);
  const footer = el("footer", { class: "forge-editor-footer" });
  footer.append(feedback, actions); editor.append(footer);
  function draftLayout() {
    const toolOrder = Array.from(dock.children, row => row.getAttribute("data-tool"));
    return { paletteKey: shortcut.value.trim().toUpperCase(),
      tools: Array.from(dock.children).filter(row => row.querySelector("input").checked).map(row => row.getAttribute("data-tool")), toolOrder };
  }
  function populateLayout(value) {
    shortcut.value = value.paletteKey;
    const rows = Array.from(dock.children);
    for (const id of value.toolOrder) {
      const row = rows.find(item => item.getAttribute("data-tool") === id);
      if (row) { row.querySelector("input").checked = value.tools.includes(id); dock.append(row); }
    }
  }
  function stateFromSnapshot(data) {
    const key = data["forge.shortcuts.palette"] || "K";
    const theme = readTheme(data[THEME_PREF] || "{}"); theme.accent = theme.accent.toLowerCase();
    return { theme, css: data[CSS_PREF] || "", enabled: data[CSS_ENABLED_PREF] ?? false,
      layout: { paletteKey: /^[A-QS-Z]$/i.test(key) ? key.toUpperCase() : "K", ...readToolLayout(data["forge.tools"] || "null", data["forge.tools.order"] || "null") } };
  }
  const draftState = () => ({ theme: draftTheme(), css: css.value, enabled: enabled.checked, layout: draftLayout() });
  const conflict = () => !!editingBaseline && !sameSnapshot(editingBaseline, beforeCommit());
  function updateEditorUI(message = null, kind = "status") {
    const activePreview = !!beforePreview && Services.prefs.getStringPref(THEME_PREF, "{}") === previewValue;
    revertPreview.disabled = !activePreview;
    undo.disabled = !lastSaved || !sameSnapshot(beforeCommit(), lastCommit);
    reload.hidden = !conflict();
    cssDisable.disabled = !Services.prefs.getBoolPref(CSS_ENABLED_PREF, false);
    cssClear.disabled = !css.value && !enabled.checked;
    copyButton.disabled = !transferText.value.trim();
    for (const [index, row] of Array.from(dock.children).entries()) {
      row.querySelector('[data-move="up"]').disabled = index === 0;
      row.querySelector('[data-move="down"]').disabled = index === dock.children.length - 1;
    }
    for (const key of ["glassOpacity", "blur"]) { extraControls.get(key).disabled = appearance.value !== "glass"; }
    const validAccent = /^#?[\da-f]{6}$/i.test(accentHex.value.trim());
    accentHex.setAttribute("aria-invalid", String(!validAccent));
    shortcut.setAttribute("aria-invalid", String(!/^[A-QS-Z]$/i.test(shortcut.value.trim())));
    css.setAttribute("aria-invalid", String(css.value.length > MAX_CUSTOM_CSS_LENGTH));
    preset.value = validAccent ? presetForTheme(draftTheme()) : "";
    if (!message) {
      if (conflict()) { message = t("forge-editor-stale"); kind = "warning"; }
      else if (activePreview) { message = t("forge-editor-preview-active"); }
      else if (!editingBaseline || JSON.stringify(draftState()) !== JSON.stringify(stateFromSnapshot(editingBaseline))) { message = t("forge-editor-dirty"); }
      else { message = t("forge-editor-clean"); }
    }
    feedback.textContent = message;
    feedback.dataset.kind = kind; feedback.setAttribute("role", kind === "error" ? "alert" : "status");
  }
  function validateEditor(themeOnly = false) {
    const value = accentHex.value.trim();
    if (!/^#?[\da-f]{6}$/i.test(value)) { updateEditorUI(t("forge-editor-invalid-hex"), "error"); accentHex.focus(); return false; }
    accent.value = `#${value.replace(/^#/, "").toLowerCase()}`;
    if (!themeOnly && !/^[A-QS-Z]$/i.test(shortcut.value.trim())) {
      layout.open = true; updateEditorUI(t("forge-editor-invalid-key"), "error"); shortcut.focus(); return false;
    }
    if (!themeOnly && css.value.length > MAX_CUSTOM_CSS_LENGTH) { advanced.open = true; updateEditorUI(t("forge-editor-large-css"), "error"); css.focus(); return false; }
    if (!themeOnly && shortcut.value.trim().toUpperCase() !== Services.prefs.getStringPref("forge.shortcuts.palette", "K").toUpperCase()) {
      try { parseCommandBindings(Services.prefs.getStringPref("forge.shortcuts.commands", "{}"), shortcut.value.trim().toUpperCase()); }
      catch { layout.open = true; updateEditorUI(t("forge-editor-key-conflict"), "error"); shortcut.focus(); return false; }
    }
    return true;
  }
  on(accent, "input", () => { accentHex.value = accent.value.toUpperCase(); });
  on(accentHex, "input", () => { if (/^#?[\da-f]{6}$/i.test(accentHex.value.trim())) { accent.value = `#${accentHex.value.trim().replace(/^#/, "")}`; } });
  function updateLivePreview() {
    if (!beforePreview || Services.prefs.getStringPref(THEME_PREF, "{}") !== previewValue || !/^#?[\da-f]{6}$/i.test(accentHex.value.trim())) { return; }
    const value = JSON.stringify(draftTheme());
    if (value !== previewValue) { previewValue = value; Services.prefs.setStringPref(THEME_PREF, value); }
  }
  on(editorBody, "input", () => { updateLivePreview(); updateEditorUI(); });
  on(editorBody, "change", () => { updateLivePreview(); updateEditorUI(); });
  on(revertPreview, "click", () => { finishPreview(); updateEditorUI(t("forge-editor-preview-ended")); });
  on(reload, "click", () => { finishPreview(); populateSavedPreferences(); updateEditorUI(t("forge-editor-reloaded")); });
  on(cssClear, "click", () => { css.value = ""; enabled.checked = false; updateEditorUI(t("forge-editor-css-cleared")); });
  on(cssDisable, "click", () => {
    committing = true;
    try { Services.prefs.setBoolPref(CSS_ENABLED_PREF, false); } finally { committing = false; }
    enabled.checked = false; editingBaseline[CSS_ENABLED_PREF] = false;
    lastSaved = null; lastCommit = null;
    updateEditorUI(t("forge-editor-css-disabled"));
  });
  on(preview, "click", () => {
    if (!validateEditor(true)) { return; }
    if (!beforePreview || Services.prefs.getStringPref(THEME_PREF, "{}") !== previewValue) { beforePreview = snapshot(); }
    previewValue = JSON.stringify(draftTheme());
    Services.prefs.setStringPref(THEME_PREF, previewValue);
    updateEditorUI();
  });
  on(undo, "click", () => {
    finishPreview();
    if (!lastSaved || !sameSnapshot(snapshot(), lastCommit)) { updateEditorUI(t("forge-editor-undo-blocked"), "warning"); return; }
    committing = true;
    try { restore(lastSaved); } finally { committing = false; }
    lastSaved = null; lastCommit = null; populateSavedPreferences(); updateEditorUI(t("forge-editor-undone"));
  });
  doc.body.append(editor);
  on(save, "click", () => {
    if (!validateEditor()) { return; }
    if (conflict()) { updateEditorUI(t("forge-editor-save-blocked"), "error"); reload.focus(); return; }
    const previous = beforeCommit();
    if (JSON.stringify(draftState()) === JSON.stringify(stateFromSnapshot(previous))) { finishPreview(); editor.close(); return; }
    lastSaved = previous; beforePreview = null; previewValue = null;
    committing = true;
    try {
      const draft = draftState();
      Services.prefs.setStringPref(THEME_PREF, JSON.stringify(draft.theme));
      Services.prefs.setStringPref(CSS_PREF, draft.css);
      Services.prefs.setBoolPref(CSS_ENABLED_PREF, draft.enabled);
      Services.prefs.setStringPref("forge.shortcuts.palette", draft.layout.paletteKey);
      Services.prefs.setStringPref("forge.tools.order", JSON.stringify(draft.layout.toolOrder));
      Services.prefs.setStringPref("forge.tools", JSON.stringify(draft.layout.tools));
    } finally { committing = false; }
    lastCommit = snapshot();
    editor.close();
  });
  on(reset, "click", () => {
    finishPreview(); populate(DEFAULT_THEME, css.value);
    updateEditorUI(t("forge-editor-reset-staged"));
  });
  on(cancel, "click", () => { finishPreview(); editor.close(); });
  function populateSavedPreferences() {
    editingBaseline = snapshot();
    const state = stateFromSnapshot(editingBaseline);
    populate(state.theme, state.css); populateLayout(state.layout); enabled.checked = state.enabled;
    updateEditorUI();
  }
  function openEditor() {
    if (editor.open) { return; }
    finishPreview();
    transferText.value = ""; transferStatus.textContent = "";
    populateSavedPreferences();
    returnFocus = doc.activeElement;
    if (!returnFocus || returnFocus === doc.body || returnFocus.closest?.("#forge-palette, #forge-control-center, #forge-editor")) {
      returnFocus = doc.querySelector('[data-forge-tool="palette"]:not([hidden])') || doc.getElementById("forge-hub-button") || win.gURLBar.inputField;
    }
    editorBody.scrollTop = 0;
    for (const other of doc.querySelectorAll('dialog[id^="forge-"][open]')) { if (other !== editor) { other.close(); } }
    editor.showModal();
    preset.focus();
  }
  editorPreferencesChanged = name => {
    if (!editor.open || committing) { return; }
    if (name === CSS_ENABLED_PREF && !Services.prefs.getBoolPref(CSS_ENABLED_PREF, false)) { enabled.checked = false; }
    updateEditorUI();
  };
  on(editor, "keydown", event => {
    if (event.isComposing || event.key !== "Enter") { return; }
    if (event.ctrlKey || event.metaKey || event.target === accentHex || event.target === shortcut) { event.preventDefault(); save.doCommand(); }
  });
  const open = url => win.openTrustedLinkIn(url, "tab");
  const toolbox = async toolId => {
    const { require } = ChromeUtils.importESModule("resource://devtools/shared/loader/Loader.sys.mjs");
    const { gDevTools } = require("devtools/client/framework/devtools");
    await gDevTools.showToolboxForTab(win.gBrowser.selectedTab, { toolId });
  };
  const catalog = createCommands(win, { open, openEditor, showPalette, toolbox, workspace: () => shell.workspaces });
  const shortcuts = initShortcuts(win, { el, on, cleanup, commands: catalog });
  catalog.push({ id: "shortcuts", icon: "settings", title: t("forge-shortcuts-title"), keywords: "keyboard shortcuts горячие клавиши", group: t("forge-section-browser"), run: shortcuts.open });
  const recency = new Map();
  on(win.gBrowser.tabContainer, "TabClose", event => recency.delete(event.target));
  function commands() {
    return [
      ...catalog,
      ...projectCommands(win, toolbox),
      ...Array.from(win.gBrowser.tabs).filter(tab => !tab.closing && !tab.hidden).sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0)).map(tab => ({
         id: tab,
          title: t("forge-palette-tab", { name: tab.label }), keywords: `tab вкладки ${tab.linkedBrowser.currentURI.displaySpec}`,
        run: () => { if (tab.isConnected) { win.gBrowser.selectedTab = tab; } },
      })),
    ];
  }
  async function execute(command) {
    executingPaletteCommand = true;
    palette.close();
    try {
      await command.run();
      recency.set(command.id, Date.now());
    } catch (error) {
      console.error("Forge command failed", error);
      win.alert(formatError(t, error));
    }
  }
  function render() {
    results.replaceChildren();
    const matches = searchCommands(commands(), search.value).sort((a, b) => (recency.get(b.id) || 0) - (recency.get(a.id) || 0));
    const fragment = doc.createDocumentFragment();
    for (const command of matches) {
      const row = el("toolbarbutton", { class: "forge-result", "aria-label": command.title });
      row.append(el("span", {}, command.title));
      // Nodes are replaced on search; don't retain them via the window abort signal.
      row.addEventListener("command", () => execute(command));
      fragment.append(row);
    }
    results.append(fragment);
    status.textContent = matches.length ? t("forge-palette-count", { count: matches.length }) : t("forge-palette-empty");
  }
  function showPalette() {
    if (palette.open) { palette.close(); return; }
    paletteOpener = doc.activeElement;
    executingPaletteCommand = false;
    for (const other of doc.querySelectorAll('dialog[id^="forge-"][open]')) { if (other !== palette) { other.close(); } }
    search.value = "";
    render();
    palette.showModal();
    search.focus();
  }
  on(search, "input", render);
  on(palette, "keydown", event => {
    // A native search field otherwise consumes Escape just to clear its text.
    if (event.key === "Escape" && plainKey(event)) { event.preventDefault(); palette.close(); }
  });
  on(search, "keydown", event => {
    if (!plainKey(event)) { return; }
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      (event.key === "ArrowDown" ? results.firstElementChild : results.lastElementChild)?.focus();
    } else if (event.key === "Enter") {
      event.preventDefault();
      results.firstElementChild?.doCommand();
    }
  });
  on(results, "keydown", event => {
    if (!plainKey(event) || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) { return; }
    event.preventDefault();
    if (event.key === "Home" || event.key === "End") {
      (event.key === "Home" ? results.firstElementChild : results.lastElementChild)?.focus(); return;
    }
    const next = event.key === "ArrowDown" ? doc.activeElement.nextElementSibling : doc.activeElement.previousElementSibling;
    (next || search).focus();
  });
  on(close, "click", () => palette.close());
  on(win, "forge-show-palette", showPalette);
  // A XUL key binding also works while a remote web page has keyboard focus.
  const key = doc.createXULElement("key");
  nodes.push(key);
  key.id = "forge-command-key";
  const savedKey = Services.prefs.getStringPref("forge.shortcuts.palette", "K").toUpperCase();
  key.setAttribute("key", /^[A-Z]$/.test(savedKey) && savedKey !== "R" ? savedKey : "K");
  // Preserve Firefox's accel+shift+K Web Console shortcut.
  key.setAttribute("modifiers", "accel,shift,alt");
  on(key, "command", showPalette);
  doc.getElementById("mainKeyset").append(key);
  const recovery = doc.createXULElement("key");
  nodes.push(recovery);
  recovery.id = "forge-css-recovery-key";
  recovery.setAttribute("key", "R"); recovery.setAttribute("modifiers", "accel,shift,alt");
  on(recovery, "command", () => { finishPreview(); Services.prefs.setBoolPref(CSS_ENABLED_PREF, false); });
  doc.getElementById("mainKeyset").append(recovery);

  const shell = initShell(win, { el, on, showPalette, openEditor, toolbox, open, motion, cleanup });
  const hub = initControlCenter(win, { el, on, cleanup, commands: catalog });
  for (const dialog of [palette, editor, hub, shortcuts.dialog]) { motion.bindDialog(dialog, on); bindDialogTabCycle(dialog, on); }

  doc.documentElement.setAttribute("forge-ready", "true");
  initializing = false;
  const owned = new Set(nodes);
  for (let index = nodes.length - 1; index >= 0; index--) {
    if (owned.has(nodes[index].parentElement)) { nodes.splice(index, 1); }
  }
  doc.getElementById("forge-startup-error")?.remove();
  on(win, "unload", dispose);
  return shell;
  } catch (error) { dispose(); throw error; }
}
