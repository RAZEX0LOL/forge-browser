/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { createStrings, uiLocale } from "./Localization.sys.mjs";
export class ForgeStartChild extends JSWindowActorChild {
  handleEvent(event) {
    if (event.type === "DOMContentLoaded") {
      const doc = this.document, text = createStrings(this.contentWindow);
      doc.documentElement.setAttribute('lang', uiLocale());
      for (const node of doc.querySelectorAll('[data-forge-l10n]')) {
        const value = text(node.getAttribute('data-forge-l10n'));
        const attr = node.getAttribute('data-forge-l10n-attr');
        if (attr && ["aria-label", "placeholder", "title"].includes(attr)) { node.setAttribute(attr, value); }
        else if (!attr) { node.textContent = value; }
      }
      doc.documentElement.setAttribute('data-forge-localized', 'true');
      return;
    }
    if (event.type !== "submit" || event.target.id !== "forge-search") { return; }
    event.preventDefault();
    const query = this.document.getElementById("query").value.trim();
    if (query && query.length <= 8192) { this.sendAsyncMessage("Forge:Navigate", { query }); }
  }
}
