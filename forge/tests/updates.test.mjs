import test from "node:test";
import assert from "node:assert/strict";
import { launchDesktopUpdater } from "../overlay/Updates.sys.mjs";

function environment({ platform = "macosx", exists = true, symlink = false, locale = "ru-RU" } = {}) {
  const calls = [];
  let observer;
  const file = { append(name) { calls.push(["append", name]); }, exists: () => exists,
    isSymlink: () => symlink, isFile: () => true, isExecutable: () => true };
  const process = { isRunning: true, init(value) { assert.equal(value, file); },
    runAsync(args, count, value, weak) { calls.push(["runAsync", args, count, weak]); observer = value; } };
  globalThis.ChromeUtils = { importESModule(url) {
    assert.equal(url, "resource://gre/modules/AppConstants.sys.mjs"); return { AppConstants: { platform } };
  } };
  globalThis.Ci = { nsIFile: {}, nsIProcess: {} };
  globalThis.Cc = { "@mozilla.org/process/util;1": { createInstance: () => process } };
  globalThis.Services = { dirsvc: { get(key) { assert.equal(key, "XREExeF"); return { parent: file }; } },
    locale: { appLocalesAsBCP47: [locale] } };
  return { calls, finish() { process.isRunning = false; observer?.observe(); } };
}

test("desktop updater only launches the sibling helper with a bounded locale, never a URL/profile/shell", () => {
  for (const [locale, expected] of [["ru-RU", "ru"], ["en-US", "en"], ["fr", "en"]]) {
    const env = environment({ locale });
    launchDesktopUpdater();
    assert.deepEqual(env.calls, [["append", "forge-update"], ["runAsync", [`--locale=${expected}`], 1, false]]);
    assert.throws(launchDesktopUpdater, error => error.l10nId === "forge-update-running");
    env.finish();
  }
});

test("unavailable platforms, missing helper and symlink helper fail without starting a process", () => {
  for (const options of [{ platform: "win" }, { platform: "linux" }, { exists: false }, { symlink: true }]) {
    const env = environment(options);
    assert.throws(launchDesktopUpdater, error => ["forge-update-unavailable", "forge-update-bootstrap"].includes(error.l10nId));
    assert.equal(env.calls.some(call => call[0] === "runAsync"), false);
    env.finish();
  }
});
