import test from "node:test";
import assert from "node:assert/strict";

test("network host instrumentation is off by default and requires both opt-ins", async () => {
  const registered = [];
  const prefs = new Map();
  globalThis.Services = { prefs: { getBoolPref: (name, fallback) => prefs.get(name) ?? fallback },
    obs: { addObserver: (...args) => registered.push(args) } };
  const audit = await import("../overlay/NetworkAudit.sys.mjs?off");
  audit.start();
  assert.equal(audit.takeSnapshot().active, false);
  prefs.set("forge.audit.network", true);
  audit.start();
  assert.equal(registered.length, 0);
  prefs.set("network.dns.notifyResolution", true);
  audit.start(); audit.start();
  assert.equal(registered.length, 2);
});

test("audit records only bounded host counts and drains each snapshot", async () => {
  const listeners = new Map();
  globalThis.Services = { prefs: { getBoolPref: () => true },
    obs: { addObserver: (observer, topic) => listeners.set(topic, observer) } };
  globalThis.Ci = { nsIHttpChannel: {} };
  const audit = await import("../overlay/NetworkAudit.sys.mjs?hosts");
  audit.start();
  const http = listeners.get("http-on-modify-request");
  http.observe({ QueryInterface: () => ({ URI: { asciiHost: "example.test",
    get spec() { throw new Error("Full URLs must never be accessed"); } } }) }, "http-on-modify-request");
  const dns = listeners.get("dns-resolution-request");
  dns.observe(null, "dns-resolution-request", "localhost");
  dns.observe(null, "dns-resolution-request", "localhost");
  const state = audit.takeSnapshot();
  assert.deepEqual(state.httpHosts, { "example.test": 1 });
  assert.deepEqual(state.dnsResolutionRequests, { localhost: 2 });
  assert.deepEqual(audit.takeSnapshot().httpHosts, {});
  for (let i = 0; i < 4100; i++) { dns.observe(null, "dns-resolution-request", `host${i}.test`); }
  const bounded = audit.takeSnapshot();
  assert.equal(Object.keys(bounded.dnsResolutionRequests).length, 4096);
  assert.equal(bounded.truncated, true);
});
