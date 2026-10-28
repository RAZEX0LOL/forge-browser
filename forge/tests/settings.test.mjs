import test from "node:test";
import assert from "node:assert/strict";
import { parseSettingsTransfer, validateProject, readToolLayout, TOOL_IDS, presetForTheme, THEME_PRESETS, MAX_CUSTOM_CSS_LENGTH, parseCommandBindings } from "../overlay/core.sys.mjs";
test("settings export round-trips normalized theme and CSS", () => {
  const result = parseSettingsTransfer(JSON.stringify({ version: 1, theme: { appearance: "glass", radius: 100 }, css: "/* own CSS */" }));
  assert.equal(result.theme.appearance, "glass");
  assert.equal(result.theme.radius, 24);
  assert.equal(result.css, "/* own CSS */");
  assert.equal(result.enabled, undefined);
});
test("settings reject unknown schemas and oversized CSS", () => {
  assert.throws(() => parseSettingsTransfer('{"version":2}'));
  assert.throws(() => parseSettingsTransfer(JSON.stringify({version:1,theme:{},css:"x".repeat(100001)})));
  assert.throws(() => parseSettingsTransfer("not json"));
});
test("extra command shortcuts normalize letters and preserve disabled defaults", () => {
  assert.deepEqual(parseCommandBindings('{}'), {});
  assert.deepEqual(parseCommandBindings('{"network":" n ","console":"J"}'), {network:'N',console:'J'});
});
test("extra command shortcuts reject duplicate, reserved and unknown bindings", () => {
  for(const text of ['[]','broken','{"network":"R"}','{"network":"K"}','{"network":"N","console":"n"}','{"arbitrary-command":"Z"}']) {
    assert.throws(()=>parseCommandBindings(text));
  }
  assert.throws(()=>parseCommandBindings('{"network":"J"}','J'));
});
test("version 2 round-trips button order and shortcut without enabling CSS", () => {
  const toolOrder = [...TOOL_IDS].reverse();
  const result = parseSettingsTransfer(JSON.stringify({version:2,theme:{},css:"/* local */",enabled:true,
    layout:{paletteKey:"j",tools:["network","shield"],toolOrder}}));
  assert.equal(result.layout.paletteKey,"J");
  assert.deepEqual(result.layout.toolOrder,toolOrder);
  assert.deepEqual(result.layout.tools,["shield","network"]);
  assert.equal(result.enabled,undefined);
});
test("maximum-sized escaped CSS can be exported and imported", () => {
  const css="\u0001".repeat(MAX_CUSTOM_CSS_LENGTH);
  const text=JSON.stringify({version:1,theme:{},css});
  assert.ok(text.length>150000);
  assert.equal(parseSettingsTransfer(text).css,css);
});
test("malformed layout, array themes and reserved shortcuts are rejected", () => {
  for(const layout of [{paletteKey:"R",tools:[],toolOrder:TOOL_IDS},
    {paletteKey:"K",tools:["unknown"],toolOrder:TOOL_IDS},
    {paletteKey:"K",tools:[],toolOrder:["inspect","inspect"]}]) {
    assert.throws(()=>parseSettingsTransfer(JSON.stringify({version:2,theme:{},css:"",layout})));
  }
  assert.throws(()=>parseSettingsTransfer('{"version":1,"theme":[],"css":""}'));
});
test("tool preferences preserve empty selection and independent full order", () => {
  const order=[...TOOL_IDS].reverse();
  assert.deepEqual(readToolLayout('[]',JSON.stringify(order)),{tools:[],toolOrder:order});
  assert.deepEqual(readToolLayout('["palette","network"]'),{tools:["palette","network"],toolOrder:["palette","network","inspect","terminal","shield"]});
  assert.deepEqual(readToolLayout('broken').tools,TOOL_IDS);
});
test("preset detection follows manual edits and ignores hex letter case", () => {
  assert.equal(presetForTheme({...THEME_PRESETS.glass,accent:"#A4EFCE"}),"glass");
  assert.equal(presetForTheme({...THEME_PRESETS.glass,blur:1}),"");
});
test("localhost projects allow only local HTTP origins", () => {
  for (const host of ["localhost", "127.0.0.1", "[::1]"]) {
    const project = validateProject({name:" App ",url:`http://${host}:3000/path`,tool:"netmonitor"});
    assert.equal(project.name, "App");
  }
});
test("project presets cannot persist credentials, query secrets or remote URLs", () => {
  for (const url of ["https://example.com", "file:///etc/passwd", "javascript:alert(1)", "http://localhost:3000/?token=secret", "http://user:pass@localhost/", "http://localhost/#secret", "http://localhost.evil.test/"]) {
    assert.throws(() => validateProject({name:"App",url,tool:"netmonitor"}));
  }
});
test("project presets reject empty names and unsupported tools", () => {
  assert.throws(() => validateProject({name:"",url:"http://localhost/",tool:"inspector"}));
  assert.throws(() => validateProject({name:"App",url:"http://localhost/",tool:"shell"}));
});
