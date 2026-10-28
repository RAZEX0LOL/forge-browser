/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
export const MOTION_EASING = "cubic-bezier(.2,.8,.2,1)";

export function motionEnabled(win) {
  return !win.closed && !win.matchMedia("(prefers-reduced-motion: reduce)").matches &&
    win.document.documentElement.getAttribute("forge-motion") !== "off";
}

export function createMotion(win) {
  const active = new Set();
  const byElement = new WeakMap();
  const reduced = win.matchMedia("(prefers-reduced-motion: reduce)");
  function animate(element, frames, options = {}) {
    if (!motionEnabled(win) || !element.isConnected) { return null; }
    byElement.get(element)?.cancel();
    const animation = element.animate(frames, { duration: 180, easing: MOTION_EASING, ...options });
    animation.id = "forge-motion";
    active.add(animation);
    byElement.set(element, animation);
    const release = () => {
      active.delete(animation);
      if (byElement.get(element) === animation) { byElement.delete(element); }
    };
    animation.finished.then(release, release);
    return animation;
  }
  function cancelAll() { for (const animation of active) { animation.cancel(); } }
  const onReducedChange = () => { if (reduced.matches) { cancelAll(); } };
  reduced.addEventListener("change", onReducedChange);
  return {
    animate,
    cancelAll,
    remove(element) {
      if (!motionEnabled(win) || !element.isConnected) { element.remove(); return; }
      const current = win.getComputedStyle(element);
      const animation = animate(element, [
        { opacity: current.opacity, transform: current.transform },
        { opacity: 0, transform: "translateX(-8px) scale(.98)" },
      ], { duration: 120 });
      if (animation) { animation.finished.then(() => element.remove(), () => element.remove()); }
      else { element.remove(); }
    },
    bindDialog(dialog, on) {
      on(dialog, "toggle", event => {
        if (event.newState === "open" && dialog.open) {
          animate(dialog, [
            { opacity: 0, transform: "translateY(8px) scale(.985)" },
            { opacity: 1, transform: "translateY(0) scale(1)" },
          ], { duration: 200 });
        }
      });
    },
    destroy() { cancelAll(); reduced.removeEventListener("change", onReducedChange); },
  };
}
