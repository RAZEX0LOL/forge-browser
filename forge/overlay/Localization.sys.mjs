/* This Source Code Form is subject to the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { ValidationError } from "./core.sys.mjs";
// Private registry: never override upstream strings or extension translations.
// Forge's own UI has ru/en-US catalogues. Upstream Firefox language packs and
// the application's language-selection lifecycle remain separate concerns.
const windows = new WeakMap();
export function uiLocale() {
  if (!Services.prefs.getBoolPref("forge.locale.followApp", false)) { return "ru"; }
  return Services.locale.appLocaleAsBCP47.toLowerCase().startsWith("ru") ? "ru" : "en-US";
}
export function formatError(format, error) {
  return error instanceof ValidationError ? format(error.l10nId, error.l10nArgs) : format("forge-error-unexpected");
}
export function createStrings(win, locale = null) {
  let cached = windows.get(win);
  if (!cached) { cached = new Map(); windows.set(win, cached); }
  const selected = (locale ?? uiLocale()) === "ru" ? "ru" : "en-US";
  if (cached.has(selected)) { return cached.get(selected); }
  const registry = new win.L10nRegistry();
  registry.registerSources([new win.L10nFileSource("forge", "app", ["ru", "en-US"],
    "chrome://browser/content/forge/locales/{locale}/")]);
  const localization = new win.Localization(["forge.ftl"], true, registry, selected === "ru" ? ["ru", "en-US"] : ["en-US"]);
  const format = (id, args) => {
    const value = localization.formatValueSync(id, args);
    if (value == null) { throw new Error(`Missing Forge translation: ${id}`); }
    return value;
  };
  cached.set(selected, format);
  return format;
}
