/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { parseCommandBindings, SHORTCUT_COMMAND_IDS } from "./core.sys.mjs";
import { restoreDialogFocus } from "./Keyboard.sys.mjs";
import { createStrings, formatError } from "./Localization.sys.mjs";
const PREF = "forge.shortcuts.commands";

export function initShortcuts(win, { el, on, cleanup, commands }) {
  const doc = win.document, controls = new Map(), keys = [];
  const text = createStrings(win);
  const dialog = el("dialog", { id: "forge-shortcuts", role: "dialog", lang: "ru", "aria-labelledby": "forge-shortcuts-title" });
  dialog.append(el("h2", { id: "forge-shortcuts-title" }, text("forge-shortcuts-title")),
    el("p", {}, text("forge-shortcuts-description")));
  let baseline = null, baselinePalette = null, opener = null;
  const paletteKey = () => Services.prefs.getStringPref("forge.shortcuts.palette", "K").toUpperCase();
  const snapshot = () => Services.prefs.prefHasUserValue(PREF) ? Services.prefs.getStringPref(PREF) : null;
  const status = el("p", { id: "forge-shortcuts-status", role: "status", "aria-live": "polite" });
  for (const id of SHORTCUT_COMMAND_IDS) {
    const command = commands.find(command => command.id === id);
    const label = el("label", { class: "forge-field" }, command.title);
    const input = el("input", { type: "text", maxlength: "1", autocomplete: "off", spellcheck: "false", "data-shortcut": id, "aria-label": command.title, "aria-describedby": status.id });
    label.append(input); dialog.append(label); controls.set(id, input);
  }
  const footer = el("div", { class: "forge-shortcut-actions" });
  const reload = el("native-button", { id: "forge-shortcuts-reload", type: "button" }, text("forge-shortcuts-reload"));
  const reset = el("native-button", { id: "forge-shortcuts-reset", type: "button" }, text("forge-shortcuts-reset"));
  const cancel = el("native-button", { id: "forge-shortcuts-cancel", type: "button" }, text("forge-cancel"));
  const save = el("native-button", { id: "forge-shortcuts-save", type: "button", default: "true" }, text("forge-save"));
  footer.append(reset, reload, cancel, save); dialog.append(status, footer); doc.body.append(dialog);
  const feedback = (text, error = false) => { status.textContent = text; status.setAttribute("role", error ? "alert" : "status"); };
  function populate() {
    baseline = snapshot(); baselinePalette = paletteKey();
    let bindings = {};
    try { bindings = parseCommandBindings(baseline || "{}", baselinePalette); feedback(text("forge-shortcuts-help")); }
    catch (error) { feedback(`${formatError(text, error)} ${text("forge-shortcuts-repair")}`, true); }
    for (const [id, control] of controls) { control.value = bindings[id] || ""; control.removeAttribute("aria-invalid"); }
    reload.hidden = true;
  }
  function apply() {
    for (const key of keys.splice(0)) { key.remove(); }
    let bindings;
    try { bindings = parseCommandBindings(snapshot() || "{}", paletteKey()); }
    catch { bindings = {}; }
    for (const [id, letter] of Object.entries(bindings)) {
      const key = doc.createXULElement("key"); key.id = `forge-extra-key-${id}`;
      key.setAttribute("key", letter); key.setAttribute("modifiers", "accel,shift,alt");
      key.addEventListener("command", async () => {
        if (doc.querySelector('dialog[id^="forge-"][open]')) { return; }
        try { await commands.find(command => command.id === id).run(); }
        catch (error) { win.console.error("Forge shortcut failed", error); win.alert(text("forge-shortcuts-failed")); }
      });
      doc.getElementById("mainKeyset").append(key); keys.push(key);
    }
    if (dialog.open && (snapshot() !== baseline || paletteKey() !== baselinePalette)) {
      reload.hidden = false; feedback(text("forge-shortcuts-stale"), true);
    }
  }
  const observer = { observe: apply };
  Services.prefs.addObserver("forge.shortcuts.", observer);
  cleanup(() => { Services.prefs.removeObserver("forge.shortcuts.", observer); for (const key of keys) { key.remove(); } });
  apply();
  on(reload, "click", populate);
  on(reset, "click", () => { for (const control of controls.values()) { control.value = ""; } feedback(text("forge-shortcuts-cleared")); });
  on(cancel, "click", () => dialog.close());
  on(save, "click", () => {
    if (snapshot() !== baseline || paletteKey() !== baselinePalette) { reload.hidden = false; feedback(text("forge-shortcuts-blocked"), true); return; }
    const draft = Object.fromEntries(Array.from(controls).filter(([, control]) => control.value.trim()).map(([id, control]) => [id, control.value]));
    try {
      const value = JSON.stringify(parseCommandBindings(JSON.stringify(draft), paletteKey()));
      if (value !== (baseline || "{}")) { Services.prefs.setStringPref(PREF, value); }
      dialog.close();
    } catch (error) { feedback(formatError(text, error), true); }
  });
  on(dialog, "close", () => restoreDialogFocus(dialog, opener, [doc.getElementById("forge-hub-button"), win.gURLBar.inputField]));
  return { dialog, open() {
    opener = doc.activeElement;
    for (const other of doc.querySelectorAll('dialog[id^="forge-"][open]')) { other.close(); }
    populate(); dialog.showModal(); controls.values().next().value.focus();
  } };
}
