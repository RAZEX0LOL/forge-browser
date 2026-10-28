import test from "node:test";
import assert from "node:assert/strict";
import { canTransfer, unitFor, unitTabs, beginDrag, draggedTab, endDrag } from "../overlay/TabTransfer.sys.mjs";

globalThis.ChromeUtils = { importESModule: () => ({ PrivateBrowsingUtils: { isWindowPrivate: win => !!win.private } }) };
function fixture() {
  const source = { gBrowser: { tabs: [] }, crypto: { randomUUID: () => "unguessable-test-token" } };
  const destination = { gBrowser: { tabs: [] } };
  const tab = { ownerGlobal: source, isConnected: true, pinned: false };
  source.gBrowser.tabs.push(tab);
  return { source, destination, tab };
}
test("transfer rejects forged, hidden and closed tabs and private boundaries", () => {
  const { tab, source, destination } = fixture();
  assert.equal(canTransfer(tab, destination), true);
  assert.equal(canTransfer({ ...tab }, destination), false);
  for (const key of ["hidden", "closing"]) { tab[key] = true; assert.equal(canTransfer(tab, destination), false); tab[key] = false; }
  destination.private = true;
  assert.equal(canTransfer(tab, destination), false);
  source.private = true;
  assert.equal(canTransfer(tab, destination), true);
});
test("groups and split views transfer as native units", () => {
  const { tab } = fixture();
  const other = { ...tab };
  tab.splitview = { tabs: [tab, other] };
  assert.equal(unitFor(tab), tab.splitview);
  assert.deepEqual(unitTabs(tab), [tab, other]);
  tab.group = { tabs: [tab, other] };
  assert.equal(unitFor(tab), tab.group);
});
test("external payloads cannot manufacture a native drag", () => {
  const { tab, destination } = fixture();
  const payload = new Map();
  const data = { setData: (key, value) => payload.set(key, value), getData: key => payload.get(key), get types() { return [...payload.keys()]; } };
  assert.equal(draggedTab(data, destination), null);
  beginDrag(tab, data);
  assert.equal(draggedTab(data, destination), tab);
  const protectedData = { types: data.types, getData: () => "" };
  assert.equal(draggedTab(protectedData, destination, null, true), tab);
  assert.equal(draggedTab(protectedData, destination), null);
  payload.set('application/x-forge-tab', 'forged');
  assert.equal(draggedTab(data, destination), null);
  endDrag();
  assert.equal(draggedTab(data, destination), null);
});
