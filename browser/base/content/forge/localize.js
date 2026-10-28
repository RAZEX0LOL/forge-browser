/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
(() => {
  function translate() {
    try {
      const { createStrings, uiLocale } = ChromeUtils.importESModule("chrome://browser/content/forge/Localization.sys.mjs");
      const text = createStrings(window);
      for (const node of document.querySelectorAll('[data-forge-l10n]')) {
        node.setAttribute('lang', uiLocale());
        const value = text(node.getAttribute('data-forge-l10n'));
        const attr = node.getAttribute('data-forge-l10n-attr');
        if (attr && ["aria-label", "placeholder", "title"].includes(attr)) { node.setAttribute(attr, value); }
        else if (!attr) { node.textContent = value; }
      }
      document.documentElement.setAttribute('data-forge-localized', 'true');
    } catch (error) { console.error("Forge page localization failed", error); }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', translate, { once: true }); }
  else { translate(); }
})();
