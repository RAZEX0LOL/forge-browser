/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { ValidationError } from "./core.sys.mjs";

let running = null;

// Native helper owns consent, signature verification and installation. No shell,
// profile path, browsing URL, cookies or command-line install override is passed.
export function launchDesktopUpdater() {
  const { AppConstants } = ChromeUtils.importESModule("resource://gre/modules/AppConstants.sys.mjs");
  if (AppConstants.platform !== "macosx") throw new ValidationError("forge-update-unavailable");
  if (running?.isRunning) throw new ValidationError("forge-update-running");
  const helper = Services.dirsvc.get("XREExeF", Ci.nsIFile).parent;
  helper.append("forge-update");
  if (!helper.exists() || helper.isSymlink() || !helper.isFile() || !helper.isExecutable()) {
    throw new ValidationError("forge-update-bootstrap");
  }
  const process = Cc["@mozilla.org/process/util;1"].createInstance(Ci.nsIProcess);
  process.init(helper);
  running = process;
  try {
    const locale = Services.locale.appLocalesAsBCP47[0]?.startsWith("ru") ? "ru" : "en";
    process.runAsync([`--locale=${locale}`], 1, { observe() { if (running === process) running = null; } }, false);
  } catch (error) {
    running = null;
    throw new ValidationError("forge-update-bootstrap");
  }
}
