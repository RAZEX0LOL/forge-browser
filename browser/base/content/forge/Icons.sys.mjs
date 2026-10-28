/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */

// A single original 24px outline family. No icon fonts, emoji or network assets.
export const ICON_PATHS = Object.freeze({
  plus: "M12 5v14M5 12h14",
  close: "m6 6 12 12M18 6 6 18",
  search: "M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Zm5 12 4.5 4.5",
  window: "M4 4h16v16H4ZM4 9h16M8 6.5h.01M11 6.5h.01",
  private: "M12 3 4 6v6c0 4 4 7 8 9 4-2 8-5 8-9V6ZM8.5 12h7M9 11v2m6-2v2",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  history: "M4 9a8 8 0 1 1 0 6M4 4v5h5M12 7v5l3 2",
  bookmark: "M6 3h12v18l-6-4-6 4Z",
  palette: "M12 3a9 9 0 1 0 0 18h2a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h4a4 4 0 0 0 4-4c0-3-5-6-9-6ZM7 9h.01M10 6h.01M15 7h.01M6 13h.01",
  settings: "M4 6h16M4 12h16M4 18h16M9 3v6m6 0v6m-7 0v6",
  extension: "M4 4h5V3a3 3 0 0 1 6 0v1h5v5h-1a3 3 0 0 0 0 6h1v5h-5v-1a3 3 0 0 0-6 0v1H4v-5h1a3 3 0 0 0 0-6H4Z",
  lock: "M7 10V8a5 5 0 0 1 10 0v2M5 10h14v11H5ZM12 14v3",
  shield: "M12 3 4 6v6c0 4 4 7 8 9 4-2 8-5 8-9V6ZM8 12l3 3 5-6",
  terminal: "m5 6 5 6-5 6m8 0h6",
  inspect: "M4 4h16v16H4ZM8 8l3 10 2-5 5-2Z",
  network: "M6 8V4h12v4M6 16v4h12v-4M3 8h6v8H3ZM15 8h6v8h-6ZM9 12h6",
  pin: "m8 3 8 0-1 6 4 4H5l4-4ZM12 13v8",
  arrow: "M5 19 19 5M7 5h12v12",
  grid: "M4 4h6v6H4ZM14 4h6v6h-6ZM4 14h6v6H4ZM14 14h6v6h-6Z",
  sidebar: "M4 4h16v16H4ZM9 4v16M6 8h.01M6 12h.01M6 16h.01",
  globe: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM3 12h18M12 3c-5 5-5 13 0 18 5-5 5-13 0-18Z",
  sound: "M4 9h4l5-5v16l-5-5H4ZM16 8c3 2 3 6 0 8m3-11c5 4 5 10 0 14",
  muted: "M4 9h4l5-5v16l-5-5H4ZM17 9l5 6m0-6-5 6",
  split: "M3 4h18v16H3ZM12 4v16",
});

export function icon(doc, name, className = "forge-icon") {
  if (!Object.hasOwn(ICON_PATHS, name)) { throw new Error(`Unknown Forge icon: ${name}`); }
  const svg = doc.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  // A safe intrinsic size is needed in internal documents without forge.css.
  // Presentation attributes remain overridable by scoped theme CSS.
  svg.setAttribute("width", "24");
  svg.setAttribute("height", "24");
  svg.setAttribute("class", className);
  svg.setAttribute("data-forge-icon", name);
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  const path = doc.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICON_PATHS[name]);
  svg.append(path);
  return svg;
}
