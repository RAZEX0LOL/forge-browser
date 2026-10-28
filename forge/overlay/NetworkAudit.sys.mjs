/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
// Explicit disposable-automation instrumentation, off in normal profiles.
// Memory-only host counts; never URLs, headers, payloads, files or socket hooks.
let active = false;
let hosts = new Map(), dns = new Map(), truncated = false;
const record = (map, host) => {
  if (!host || host.length > 253) { return; }
  if (!map.has(host) && map.size >= 4096) { truncated = true; return; }
  map.set(host, (map.get(host) || 0) + 1);
};
const observer = { observe(subject, topic, data) {
  if (topic === "dns-resolution-request") { record(dns, data); return; }
  try { record(hosts, subject.QueryInterface(Ci.nsIHttpChannel).URI.asciiHost); } catch {}
} };

export function start() {
  if (active || !Services.prefs.getBoolPref("forge.audit.network", false) ||
      !Services.prefs.getBoolPref("network.dns.notifyResolution", false)) { return; }
  Services.obs.addObserver(observer, "http-on-modify-request");
  Services.obs.addObserver(observer, "dns-resolution-request");
  active = true;
}

export function takeSnapshot() {
  const state = { active, startBoundary: "first browser chrome bootstrap (not process creation)",
    httpHosts: Object.fromEntries(hosts), dnsResolutionRequests: Object.fromEntries(dns), truncated };
  hosts = new Map(); dns = new Map(); truncated = false;
  return state;
}
