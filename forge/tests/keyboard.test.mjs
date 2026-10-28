import test from "node:test";
import assert from "node:assert/strict";
import { plainKey, restoreDialogFocus, bindDialogTabCycle } from "../overlay/Keyboard.sys.mjs";

test("plain navigation excludes IME, consumed keys and all modifiers", () => {
  assert.equal(plainKey({ key: "ArrowDown" }), true);
  for (const key of ["defaultPrevented", "isComposing", "altKey", "ctrlKey", "metaKey", "shiftKey"]) {
    assert.equal(plainKey({ key: "ArrowDown", [key]: true }), false, key);
  }
});

function fixture() {
  const doc = { activeElement: null, querySelector: () => null };
  const dialog = { ownerDocument: doc, open: false };
  const node = overrides => ({ isConnected: true, disabled: false, closest: () => null,
    getClientRects: () => [{}], focus() { doc.activeElement = this; }, ...overrides });
  return { doc, dialog, node };
}

test("closing a dialog restores its actual opener", () => {
  const { doc, dialog, node } = fixture();
  const opener = node();
  assert.equal(restoreDialogFocus(dialog, opener), true);
  assert.equal(doc.activeElement, opener);
});

test("hidden, inert, detached or disabled openers use a visible fallback", () => {
  for (const overrides of [{ isConnected: false }, { disabled: true }, { closest: () => ({}) }, { getClientRects: () => [] }]) {
    const { doc, dialog, node } = fixture();
    const fallback = node();
    assert.equal(restoreDialogFocus(dialog, node(overrides), [null, fallback]), true);
    assert.equal(doc.activeElement, fallback);
  }
});

test("queued close events never steal focus from a newer modal dialog", () => {
  const { doc, dialog, node } = fixture();
  doc.querySelector = () => ({});
  assert.equal(restoreDialogFocus(dialog, node()), false);
  assert.equal(doc.activeElement, null);
  doc.querySelector = () => null;
  dialog.open = true;
  assert.equal(restoreDialogFocus(dialog, node()), false);
});

test("a node which rejects focus does not prevent fallback recovery", () => {
  const { doc, dialog, node } = fixture();
  const fallback = node();
  assert.equal(restoreDialogFocus(dialog, node({ focus() {} }), [fallback]), true);
  assert.equal(doc.activeElement, fallback);
  assert.equal(restoreDialogFocus(dialog, null), false);
});

test("native toolbar restoration uses Firefox's temporary focus mechanism", () => {
  const { doc, dialog, node } = fixture();
  let calls = 0;
  doc.defaultView = { ToolbarKeyboardNavigator: { _focusButton(button) { calls++; doc.activeElement = button; } } };
  const toolbarButton = node({ matches: () => true, closest: selector => selector === "toolbar" ? {} : null, focus() { throw new Error("Must use native toolbar navigation"); } });
  assert.equal(restoreDialogFocus(dialog, toolbarButton), true);
  assert.equal(calls, 1);
});

test("Tab boundaries skip hidden and disabled controls without a dead dialog stop", () => {
  const { doc, dialog, node } = fixture();
  const first = node({ tabIndex: 0 }), last = node({ tabIndex: 0 });
  dialog.querySelectorAll = () => [node({ tabIndex: 0, disabled: true }), first,
    node({ tabIndex: 0, getClientRects: () => [] }), last, node({ tabIndex: -1 })];
  let handler;
  bindDialogTabCycle(dialog, (_node, _type, callback) => { handler = callback; });
  const event = overrides => ({ key: "Tab", prevented: false, preventDefault() { this.prevented = true; }, ...overrides });
  doc.activeElement = last;
  const forward = event(); handler(forward);
  assert.equal(forward.prevented, true);
  assert.equal(doc.activeElement, first);
  const backward = event({ shiftKey: true }); handler(backward);
  assert.equal(backward.prevented, true);
  assert.equal(doc.activeElement, last);
});

test("interior Tab and modified or composing keys stay native", () => {
  const { doc, dialog, node } = fixture();
  const first = node({ tabIndex: 0 }), last = node({ tabIndex: 0 });
  dialog.querySelectorAll = () => [first, last];
  let handler;
  bindDialogTabCycle(dialog, (_node, _type, callback) => { handler = callback; });
  doc.activeElement = first;
  handler({ key: "Tab", preventDefault() { assert.fail("Interior Tab must stay native"); } });
  doc.activeElement = last;
  for (const modifier of ["isComposing", "ctrlKey", "metaKey", "altKey", "defaultPrevented"]) {
    handler({ key: "Tab", [modifier]: true, preventDefault() { assert.fail(modifier); } });
  }
});
