import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createThemeSheet, isForgeSurface, SURFACE_PREFIXES } from "../overlay/design-tokens.sys.mjs";

test("native browser surfaces are recognized", () => {
  for (const uri of ["about:preferences", "about:preferences#privacy", "about:addons", "about:downloads",
    "about:logins", "chrome://browser/content/places/places.xhtml", "chrome://devtools/content/framework/toolbox.xhtml"]) {
    assert.equal(isForgeSurface(uri), true, uri);
  }
});
test("websites, extension documents and security error pages are excluded", () => {
  for (const uri of ["https://example.com", "http://localhost:3000", "file:///hello.html",
    "moz-extension://id/options.html", "about:certerror?e=nssBadCert", "about:neterror",
    "about:blocked", "about:preferences-untrusted", "chrome://browser/content/blockedSite.xhtml"]) {
    assert.equal(isForgeSurface(uri), false, uri);
  }
});
test("theme injection cannot escape CSS declarations", () => {
  const css = createThemeSheet({ accent: "red; } body { display:none; }", radius: -100, density: "compact" });
  assert.ok(!css.includes("display:none"));
  assert.ok(css.includes("--forge-accent: #a4efce"));
  assert.ok(css.includes("--forge-radius: 0px"));
  assert.ok(css.includes("--forge-control-padding: 6px"));
});
test("static and dynamic sheets cover the same chrome surfaces", () => {
  const css = readFileSync(new URL("../overlay/design-system.css", import.meta.url), "utf8");
  for (const uri of SURFACE_PREFIXES) {
    assert.ok(css.includes(`url-prefix("${uri}")`), uri);
  }
  assert.ok(!css.includes('url-prefix("http'));
  assert.ok(!css.includes('url-prefix("moz-extension:'));
});
test("AMOLED has a true black canvas and no blur", () => {
  const css = createThemeSheet({ appearance: "amoled" });
  assert.ok(css.includes("--forge-canvas: #000000 !important"));
  assert.ok(css.includes("--forge-blur: none !important"));
});
test("Glass has translucent surfaces and blur without changing website scope", () => {
  const css = createThemeSheet({ appearance: "glass" });
  assert.ok(css.includes("--forge-surface: rgba("));
  assert.ok(css.includes("--forge-blur: blur(24px) saturate(1.25)"));
  assert.ok(!css.includes('url-prefix("https:'));
});
test("appearance sheet applies custom geometry and Glass strength", () => {
  const css = createThemeSheet({appearance:"glass",glassOpacity:55,blur:12,iconSize:22,tabHeight:46,toolbarHeight:58,compactWidth:96,contentGap:2,controlRadius:3,contrast:"strong"});
  for (const text of ["rgba(23, 30, 49, 0.55)","blur(12px)","--forge-icon-size: 22px",
    "--forge-tab-height: 46px","--forge-navigation-height: 58px","--forge-compact-width: 96px",
    "--forge-content-gap: 2px","--forge-control-radius: 3px"]) { assert.ok(css.includes(text),text); }
});
