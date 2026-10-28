/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { CustomizableUI } from "moz-src:///browser/components/customizableui/CustomizableUI.sys.mjs";
import { createStrings, uiLocale } from "./Localization.sys.mjs";
let registered = false;
export function toolbarButton(win, id, cleanup) {
  if (!registered) {
    const t = createStrings(win);
    for (const [widgetId, label, event] of [
      ["forge-command-button", t("forge-palette-name"), "forge-show-palette"],
      ["forge-hub-button", t("forge-hub-name"), "forge-show-center"],
    ]) {
      CustomizableUI.createWidget({ id: widgetId, type: "button", label, tooltiptext: label,
        defaultArea: CustomizableUI.AREA_NAVBAR,
         onCreated(node) { node.setAttribute("lang", uiLocale()); node.hidden = node.ownerDocument.documentElement.getAttribute("forge-ready") !== "true"; },
        onCommand(command) {
          const target = command.view || command.target.ownerDocument?.defaultView || command.target.defaultView;
          if (target.document.documentElement.getAttribute("forge-ready") === "true") {
            target.dispatchEvent(new target.Event(event));
          }
        },
      });
    }
    registered = true;
  }
  const node = CustomizableUI.getWidget(id).forWindow(win).node;
  if (node) {
    node.hidden = false;
    cleanup(() => { node.hidden = true; });
  }
  return node;
}
