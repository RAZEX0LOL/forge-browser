/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
(() => {
  try {
    ChromeUtils.importESModule("chrome://browser/content/forge/NetworkAudit.sys.mjs").start();
    ChromeUtils.importESModule("chrome://browser/content/forge/Lifecycle.sys.mjs")
      .registerWindow(window);
  } catch (error) {
    console.error("Forge bootstrap failed", error);
  }
})();
