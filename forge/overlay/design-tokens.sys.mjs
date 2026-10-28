/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { normalizeTheme } from "./core.sys.mjs";

// Never include http(s), file, extension documents, arbitrary about: pages, or
// TLS/malware error pages. Website and extension UI belong to their authors.
export const SURFACE_PREFIXES = Object.freeze([
  "chrome://browser/content/browser.xhtml", "chrome://browser/content/preferences/",
  "chrome://browser/content/downloads/", "chrome://browser/content/places/",
  "chrome://browser/content/pageinfo/", "chrome://browser/content/forge/",
  "chrome://browser/content/aboutDialog.xhtml", "chrome://browser/content/sanitize",
  "chrome://mozapps/content/extensions/",
  "chrome://mozapps/content/downloads/", "chrome://devtools/content/",
  "chrome://global/content/commonDialog.xhtml", "chrome://global/content/selectDialog.xhtml",
  "chrome://global/content/print.html",
]);
export const SURFACE_ABOUT_PAGES = Object.freeze([
  "preferences", "addons", "downloads", "processes", "debugging", "logins",
  "policies", "config", "support", "profiles", "privatebrowsing", "devtools-toolbox",
]);
export function isForgeSurface(uri) {
  if (SURFACE_PREFIXES.some(prefix => uri.startsWith(prefix))) { return true; }
  return SURFACE_ABOUT_PAGES.some(page => new RegExp(`^about:${page}(?:[?#]|$)`).test(uri));
}
export const SURFACE_SCOPE = [
  ...SURFACE_PREFIXES.map(uri => `url-prefix("${uri}")`),
  ...SURFACE_ABOUT_PAGES.flatMap(page => [
    `url("about:${page}")`, `url-prefix("about:${page}#")`, `url-prefix("about:${page}?")`,
  ]),
].join(",\n");

export function createThemeSheet(value) {
  const theme = normalizeTheme(value);
  const space = theme.density === "compact" ? 6 : 10;
  const glass = theme.appearance === "glass";
  const alpha = (theme.glassOpacity / 100).toFixed(2);
  const colors = glass ? {
    canvas: "#0b0d17", surface: `rgba(23, 30, 49, ${alpha})`, raised: `rgba(42, 52, 78, ${alpha})`,
    hover: "rgba(60, 75, 108, .72)", field: "rgba(6, 12, 25, .66)",
    line: "rgba(195, 212, 255, .23)", strong: "rgba(210, 224, 255, .43)",
    ink: "#f3f6ff", muted: "#bdc9e1", dim: "#9baac7",
    selected: "color-mix(in srgb, var(--forge-accent) 20%, #18233a)",
  } : {
    canvas: "#000000", surface: "#080808", raised: "#141414", hover: "#202020", field: "#050505",
    line: "#303030", strong: "#595959", ink: "#f0f0f0", muted: "#b8b8b8", dim: "#909090",
    selected: "color-mix(in srgb, var(--forge-accent) 15%, #050505)",
  };
  if (theme.contrast === "strong") {
    colors.line = glass ? "rgba(210, 224, 255, .48)" : "#606060";
    colors.muted = glass ? "#d8e2ff" : "#d8d8d8";
  } else if (theme.contrast === "soft") {
    colors.line = glass ? "rgba(195, 212, 255, .15)" : "#242424";
  }
  const declarations = Object.entries(colors).map(([key, color]) => `--forge-${key}: ${color} !important;`).join("\n");
  return `@-moz-document ${SURFACE_SCOPE} {
    :root {
      --forge-design-version: 2 !important;
      --forge-appearance: ${theme.appearance} !important;
      --forge-accent: ${theme.accent} !important;
      --forge-radius: ${theme.radius}px !important;
      --forge-control-radius: ${theme.controlRadius}px !important;
      --forge-icon-size: ${theme.iconSize}px !important;
      --forge-tab-height: ${theme.tabHeight}px !important;
      --forge-compact-width: ${theme.compactWidth}px !important;
      --forge-navigation-height: ${theme.toolbarHeight}px !important;
      --forge-content-gap: ${theme.contentGap}px !important;
      --forge-control-padding: ${space}px !important;
      --forge-motion-fast: ${theme.motion === "off" ? "0ms" : "140ms"} !important;
      --forge-motion-normal: ${theme.motion === "off" ? "0ms" : "220ms"} !important;
      --forge-stagger-step: ${theme.motion === "off" ? "0ms" : "10ms"} !important;
      --forge-ease: cubic-bezier(.2,.8,.2,1) !important;
      --forge-blur: ${glass ? `blur(${theme.blur}px) saturate(1.25)` : "none"} !important;
      --forge-wallpaper: ${glass ? "radial-gradient(ellipse at 8% 8%, #7588c84d, transparent 55%), radial-gradient(ellipse at 85% 80%, #4e9c9c38, transparent 55%)" : "none"} !important;
      --forge-scrim: ${glass ? "rgba(2, 5, 15, .42)" : "rgba(0, 0, 0, .78)"} !important;
      ${declarations}
    }
    :root, body { background-image: var(--forge-wallpaper) !important; }
    body:has(#forge-search) > main { margin-block: ${theme.startLayout === "top" ? "8vh auto" : "auto"} !important; }
    #navigator-toolbox, #browser, .main-content { background-color: ${glass ? "transparent" : "var(--forge-canvas)"} !important; }
    #forge-rail, #nav-bar { background-color: ${glass ? "var(--forge-surface)" : "var(--forge-canvas)"} !important; }
    #forge-rail, #nav-bar, #forge-control-center, #forge-editor, #forge-palette,
    #sidebar-box, setting-group, groupbox, addon-card, .card, .panel-subview-body {
      backdrop-filter: var(--forge-blur) !important;
    }
    #forge-control-center::backdrop, #forge-editor::backdrop, #forge-palette::backdrop {
      background: var(--forge-scrim) !important;
      backdrop-filter: var(--forge-blur) !important;
    }
    @media (prefers-reduced-motion: reduce) {
      :root { --forge-motion-fast: 0ms !important; --forge-motion-normal: 0ms !important; --forge-stagger-step: 0ms !important; }
    }
  }`;
}
