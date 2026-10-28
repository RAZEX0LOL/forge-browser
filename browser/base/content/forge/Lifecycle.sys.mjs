/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { init } from "./Forge.sys.mjs";
import { installDesignSystem } from "./DesignSystem.sys.mjs";
import { createStrings, uiLocale } from "./Localization.sys.mjs";

const START_PAGE = "chrome://browser/content/forge/start.html";
let registered = false;
let diagnosticsQueue = Promise.resolve();
let actorRegistered = false;

function enabled() {
  return !Services.appinfo.inSafeMode && Services.prefs.getBoolPref("forge.enabled", true);
}

function ensureNewTab() {
  if (!actorRegistered) {
    ChromeUtils.registerWindowActor("ForgeStart", {
      parent: { esModuleURI: "chrome://browser/content/forge/StartParent.sys.mjs" },
      child: { esModuleURI: "chrome://browser/content/forge/StartChild.sys.mjs", events: { submit: { capture: true }, DOMContentLoaded: { capture: true } } },
      matches: [START_PAGE], includeChrome: true,
    });
    actorRegistered = true;
  }
  const { AboutNewTab } = ChromeUtils.importESModule("resource:///modules/AboutNewTab.sys.mjs");
  if (AboutNewTab.newTabURL !== START_PAGE) { AboutNewTab.newTabURL = START_PAGE; }
}

function diagnose(win, phase, error = null) {
  // Optional local developer diagnostics. Never include URLs, titles, history,
  // user CSS, search text or credentials. No file is written in normal runs.
  const path = Services.env.get("FORGE_DIAGNOSTICS_PATH");
  if (!path) { return; }
  const doc = win.document;
  const state = {
    phase,
    shell: doc.documentElement.getAttribute("forge-shell") === "true",
    rail: !!doc.getElementById("forge-rail"),
    palette: !!doc.getElementById("forge-palette"),
    center: !!doc.getElementById("forge-control-center"),
    toolbarVisible: win.toolbar.visible,
    safeMode: Services.appinfo.inSafeMode,
    enabled: Services.prefs.getBoolPref("forge.enabled", true),
    error: error ? String(error.message).slice(0, 200) : null,
  };
  diagnosticsQueue = diagnosticsQueue.then(() => IOUtils.writeUTF8(path, JSON.stringify(state) + "\n", { mode: "append" }))
    .catch(failure => console.error("Forge local diagnostic write failed", failure));
}

function initializeWindow(win) {
  if (!enabled() || win.closed || win.document.documentElement.getAttribute("windowtype") !== "navigator:browser") { return; }
  try {
    installDesignSystem();
    ensureNewTab();
    init(win);
    diagnose(win, "ready");
  } catch (error) {
    console.error("Forge browser shell failed to initialize", error);
    diagnose(win, "failed", error);
    if (!win.document.getElementById("forge-startup-error")) {
      const notice = win.document.createElementNS("http://www.w3.org/1999/xhtml", "div");
      notice.id = "forge-startup-error";
      notice.setAttribute("role", "alert");
       try { notice.setAttribute('lang',uiLocale()); notice.textContent = createStrings(win)("forge-startup-failed"); }
       catch { notice.setAttribute('lang','en-US'); notice.textContent = "Forge could not start. Native browser controls remain available. Restart the development build with --purgecaches."; }
      win.document.body.prepend(notice);
    }
  }
}

const windowObserver = {
  observe(win) { initializeWindow(win); },
};

export function registerWindow(win) {
  if (!enabled()) { return; }
  installDesignSystem();
  ensureNewTab();
  if (!registered) {
    // One process-wide observer covers all normal/private browser windows,
    // rather than relying exclusively on each window's individual script.
    Services.obs.addObserver(windowObserver, "browser-delayed-startup-finished");
    registered = true;
  }
  if (win.gBrowserInit?.delayedStartupFinished) { initializeWindow(win); }
}
