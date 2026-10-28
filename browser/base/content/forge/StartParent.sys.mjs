/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
export class ForgeStartParent extends JSWindowActorParent {
  receiveMessage(message) {
    if (message.name !== "Forge:Navigate" || this.manager.documentURI?.spec !== "chrome://browser/content/forge/start.html") { return; }
    const browser = this.browsingContext.top.embedderElement;
    const win = browser?.ownerDocument.defaultView;
    const query = message.data?.query;
    if (!win?.gURLBar || browser !== win.gBrowser.selectedBrowser || typeof query !== "string" || !query.trim() || query.length > 8192) { return; }
    // Use the exact same fixup, search engine and navigation path as the URL bar.
    win.gURLBar.value = query;
    win.gURLBar.handleCommand();
  }
}
