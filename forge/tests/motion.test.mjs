import test from "node:test";
import assert from "node:assert/strict";
import { createMotion, motionEnabled } from "../overlay/Motion.sys.mjs";

function windowStub({ reduced = false, motion = "system", closed = false } = {}) {
  return { closed, document: { documentElement: { getAttribute: () => motion } },
    matchMedia: () => ({ matches: reduced, addEventListener() {}, removeEventListener() {} }) };
}
test("motion respects both OS preference and the explicit off setting", () => {
  assert.equal(motionEnabled(windowStub()), true);
  assert.equal(motionEnabled(windowStub({ reduced: true })), false);
  assert.equal(motionEnabled(windowStub({ motion: "off" })), false);
  assert.equal(motionEnabled(windowStub({ closed: true })), false);
});
test("reduced motion removes closed rows immediately without scheduling animation", () => {
  const controller = createMotion(windowStub({ reduced: true }));
  let removed = false;
  const element = { isConnected: true, animate() { throw new Error("Should not animate"); }, remove() { removed = true; } };
  controller.remove(element);
  assert.equal(removed, true);
  controller.destroy();
});
test("disconnected elements never receive an animation", () => {
  const controller = createMotion(windowStub());
  assert.equal(controller.animate({ isConnected: false }, []), null);
  controller.destroy();
});
test("enabled animations are finite and tagged for cleanup and test synchronization", async () => {
  const controller = createMotion(windowStub());
  let settings;
  const animation = { finished: Promise.resolve(), cancel() {} };
  const element = { isConnected: true, animate(_frames, options) { settings = options; return animation; } };
  assert.equal(controller.animate(element, [{ opacity: 0 }, { opacity: 1 }]), animation);
  assert.equal(settings.duration, 180);
  assert.equal(animation.id, "forge-motion");
  assert.equal(settings.iterations, undefined);
  await animation.finished;
  controller.destroy();
});
