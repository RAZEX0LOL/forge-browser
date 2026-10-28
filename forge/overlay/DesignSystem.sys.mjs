/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { readTheme } from "./core.sys.mjs";
import { createThemeSheet } from "./design-tokens.sys.mjs";

let installed = false;
let themeURI = null;
let sheets = null;
const themeObserver = { observe: refreshTheme };

function refreshTheme() {
  const value = readTheme(Services.prefs.getStringPref("forge.theme", "{}"));
  const next = Services.io.newURI(`data:text/css;charset=utf-8,${encodeURIComponent(createThemeSheet(value))}`);
  if (themeURI?.equals(next)) { return; }
  // Register the new sheet first so there is no unthemed frame between updates.
  sheets.loadAndRegisterSheet(next, sheets.USER_SHEET);
  if (themeURI) { sheets.unregisterSheet(themeURI, sheets.USER_SHEET); }
  themeURI = next;
}

export function installDesignSystem() {
  if (installed || Services.appinfo.inSafeMode || !Services.prefs.getBoolPref("forge.enabled", true)) { return; }
  sheets = Cc["@mozilla.org/content/style-sheet-service;1"].getService(Ci.nsIStyleSheetService);
  const uri = Services.io.newURI("chrome://browser/content/forge/design-system.css");
  // @-moz-document is intentionally restricted in author sheets. Register as a
  // user sheet to keep URL scoping effective without weakening Gecko's prefs.
  if (!sheets.sheetRegistered(uri, sheets.USER_SHEET)) {
    sheets.loadAndRegisterSheet(uri, sheets.USER_SHEET);
  }
  refreshTheme();
  Services.prefs.addObserver("forge.theme", themeObserver);
  installed = true;
}
