import test from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_THEME, normalizeTheme, readTheme, searchCommands, THEME_PRESETS } from "../overlay/core.sys.mjs";

test("invalid theme data falls back without crashing", () => {
  for (const value of ["broken", "null", "[]", "42", "{}"] ) {
    assert.deepEqual(readTheme(value), DEFAULT_THEME);
  }
});
test("CSS values cannot be injected through theme settings", () => {
  assert.equal(normalizeTheme({ accent: "red; display:none" }).accent, DEFAULT_THEME.accent);
  assert.equal(normalizeTheme({ accent: "#ABCDEF" }).accent, "#ABCDEF");
});
test("radius is bounded and rounded", () => {
  assert.equal(normalizeTheme({ radius: -1 }).radius, 0);
  assert.equal(normalizeTheme({ radius: 100 }).radius, 24);
  assert.equal(normalizeTheme({ radius: 4.6 }).radius, 5);
  assert.equal(normalizeTheme({ radius: Infinity }).radius, 12);
  assert.equal(normalizeTheme({ radius: "8" }).radius, 12);
});
test("only known densities are accepted", () => {
  assert.equal(normalizeTheme({ density: "compact" }).density, "compact");
  assert.equal(normalizeTheme({ density: "unknown" }).density, "comfortable");
});
test("AMOLED is the default; only AMOLED and Glass are accepted", () => {
  assert.equal(normalizeTheme({}).appearance, "amoled");
  assert.equal(normalizeTheme({ appearance: "glass" }).appearance, "glass");
  assert.equal(normalizeTheme({ appearance: "transparent; color:red" }).appearance, "amoled");
  assert.equal(readTheme('{"accent":"#ABCDEF","density":"compact"}').appearance, "amoled");
});
test("motion defaults to system preference and rejects unknown modes", () => {
  assert.equal(normalizeTheme({}).motion, "system");
  assert.equal(normalizeTheme({ motion: "off" }).motion, "off");
  assert.equal(normalizeTheme({ motion: "always-ignore-os" }).motion, "system");
});
test("new appearance dimensions are bounded and reject CSS values", () => {
  const result = normalizeTheme({compactWidth:500,iconSize:-1,tabHeight:100,toolbarHeight:NaN,
    glassOpacity:0,blur:100,contentGap:"8;display:none",controlRadius:100});
  assert.equal(result.compactWidth,104);
  assert.equal(result.iconSize,16);
  assert.equal(result.tabHeight,52);
  assert.equal(result.toolbarHeight,50);
  assert.equal(result.glassOpacity,45);
  assert.equal(result.blur,40);
  assert.equal(result.contentGap,8);
  assert.equal(result.controlRadius,10);
});
test("layout and contrast use only known choices", () => {
  assert.equal(normalizeTheme({sidebarSide:"right"}).sidebarSide,"right");
  assert.equal(normalizeTheme({sidebarSide:"right;display:none"}).sidebarSide,"left");
  assert.equal(normalizeTheme({contrast:"strong"}).contrast,"strong");
  assert.equal(normalizeTheme({contrast:"custom"}).contrast,"balanced");
  assert.equal(normalizeTheme({startLayout:"top"}).startLayout,"top");
});
test("all presets round-trip the normalized theme schema", () => {
  for (const preset of Object.values(THEME_PRESETS)) { assert.deepEqual(normalizeTheme(preset),preset); }
});
test("command search matches all words, ignores case and supports Cyrillic", () => {
  const commands = [
    { title: "Сетевые запросы", keywords: "network API" },
    { title: "Консоль", keywords: "console" },
  ];
  assert.equal(searchCommands(commands, " API network ").length, 1);
  assert.equal(searchCommands(commands, "СЕТЕВЫЕ").length, 1);
  assert.equal(searchCommands(commands, "api console").length, 0);
  assert.equal(searchCommands(commands, "   ").length, 2);
});
