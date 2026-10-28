import test from "node:test";
import assert from "node:assert/strict";
import { ICON_PATHS, icon } from "../overlay/Icons.sys.mjs";

function node(tag) {
  return { tag, attributes: {}, children: [], setAttribute(name, value) { this.attributes[name] = value; },
    append(child) { this.children.push(child); } };
}
const doc = { createElementNS(_namespace, tag) { return node(tag); } };

test("all Forge icons use the same accessible 24px SVG geometry", () => {
  for (const name of Object.keys(ICON_PATHS)) {
    const svg = icon(doc, name);
    assert.equal(svg.tag, "svg");
    assert.equal(svg.attributes.viewBox, "0 0 24 24");
    assert.equal(svg.attributes.width, "24");
    assert.equal(svg.attributes.height, "24");
    assert.equal(svg.attributes["aria-hidden"], "true");
    assert.equal(svg.attributes.focusable, "false");
    assert.equal(svg.attributes.stroke, "currentColor");
    assert.equal(svg.attributes["stroke-width"], "1.7");
    assert.ok(svg.children[0].attributes.d.length > 10, name);
    assert.match(svg.children[0].attributes.d, /^[MmLlHhVvCcSsQqTtAaZz\d\s.,+-]+$/);
  }
});
test("unknown icon names fail explicitly rather than rendering missing glyphs", () => {
  assert.throws(() => icon(doc, "missing-icon"), /Unknown Forge icon/);
});
