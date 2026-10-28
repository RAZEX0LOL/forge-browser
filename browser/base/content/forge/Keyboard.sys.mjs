/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */

export function plainKey(event) {
  return !event.defaultPrevented && !event.isComposing &&
    !event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey;
}

export function restoreDialogFocus(dialog, opener, fallbacks = []) {
  const doc = dialog.ownerDocument;
  // Close events are queued: a command may already have opened another dialog.
  if (dialog.open || doc.querySelector("dialog[open]")) { return false; }
  for (const node of [opener, ...fallbacks]) {
    if (!node?.isConnected || node.disabled ||
        node.closest?.("[hidden], [inert], dialog:not([open])") || !node.getClientRects().length) { continue; }
    const toolbarNavigation = doc.defaultView?.ToolbarKeyboardNavigator;
    if (node.matches?.("toolbarbutton") && node.closest?.("toolbar") && toolbarNavigation?._focusButton) {
      // Firefox toolbar buttons deliberately have no permanent tab stop.
      toolbarNavigation._focusButton(node);
    } else { node.focus(); }
    if (doc.activeElement === node || node.contains?.(doc.activeElement)) { return true; }
  }
  return false;
}

export function bindDialogTabCycle(dialog, on) {
  on(dialog, "keydown", event => {
    if (event.key !== "Tab" || event.defaultPrevented || event.isComposing || event.altKey || event.ctrlKey || event.metaKey) { return; }
    const stops = Array.from(dialog.querySelectorAll("button, toolbarbutton, input, select, textarea, summary, [tabindex]"))
      .filter(node => !node.disabled && node.tabIndex >= 0 && !node.closest("[hidden], [inert]") && node.getClientRects().length);
    if (!stops.length) { return; }
    const active = dialog.ownerDocument.activeElement;
    // Gecko chrome otherwise adds the dialog itself as a non-actionable tab stop.
    // Leave all interior traversal, popup handling and modifier combinations native.
    if (active === dialog || active === (event.shiftKey ? stops[0] : stops.at(-1))) {
      event.preventDefault();
      (event.shiftKey ? stops.at(-1) : stops[0]).focus();
    }
  });
}
