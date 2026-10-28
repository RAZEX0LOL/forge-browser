/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */

export const DEFAULT_THEME = Object.freeze({
  accent: "#a4efce",
  radius: 12,
  density: "comfortable",
  appearance: "amoled",
  motion: "system",
  sidebarSide: "left",
  compactWidth: 80,
  iconSize: 18,
  tabHeight: 38,
  toolbarHeight: 50,
  contentGap: 8,
  controlRadius: 6,
  contrast: "balanced",
  glassOpacity: 72,
  blur: 24,
  startLayout: "center",
});

export function normalizeTheme(value) {
  const input = value && typeof value === "object" ? value : {};
  const number = (key, min, max) => Number.isFinite(input[key])
    ? Math.round(Math.min(max, Math.max(min, input[key]))) : DEFAULT_THEME[key];
  return {
    accent: /^#[\da-f]{6}$/i.test(input.accent) ? input.accent : DEFAULT_THEME.accent,
    radius: Number.isFinite(input.radius)
      ? Math.round(Math.min(24, Math.max(0, input.radius)))
      : DEFAULT_THEME.radius,
    density: ["compact", "comfortable"].includes(input.density)
      ? input.density : DEFAULT_THEME.density,
    appearance: ["amoled", "glass"].includes(input.appearance)
      ? input.appearance : DEFAULT_THEME.appearance,
    motion: ["system", "off"].includes(input.motion) ? input.motion : DEFAULT_THEME.motion,
    sidebarSide: ["left", "right"].includes(input.sidebarSide) ? input.sidebarSide : DEFAULT_THEME.sidebarSide,
    compactWidth: number("compactWidth", 72, 104),
    iconSize: number("iconSize", 16, 22),
    tabHeight: number("tabHeight", 32, 52),
    toolbarHeight: number("toolbarHeight", 40, 64),
    contentGap: number("contentGap", 0, 16),
    controlRadius: number("controlRadius", 0, 10),
    contrast: ["soft", "balanced", "strong"].includes(input.contrast) ? input.contrast : DEFAULT_THEME.contrast,
    glassOpacity: number("glassOpacity", 45, 95),
    blur: number("blur", 0, 40),
    startLayout: ["center", "top"].includes(input.startLayout) ? input.startLayout : DEFAULT_THEME.startLayout,
  };
}

export const THEME_PRESETS = Object.freeze({
  default: DEFAULT_THEME,
  amoled: { ...DEFAULT_THEME, radius: 8 },
  glass: { ...DEFAULT_THEME, appearance: "glass", radius: 14, glassOpacity: 65, blur: 28 },
  compact: { ...DEFAULT_THEME, density: "compact", radius: 6, tabHeight: 34, toolbarHeight: 42, contentGap: 4 },
  contrast: { ...DEFAULT_THEME, contrast: "strong", iconSize: 20, tabHeight: 44, controlRadius: 4 },
});

export const TOOL_IDS = Object.freeze(["inspect", "terminal", "network", "palette", "shield"]);
export class ValidationError extends Error {
  constructor(l10nId, args = {}) {
    super(l10nId);
    this.name = "ForgeValidationError";
    this.l10nId = l10nId;
    this.l10nArgs = Object.freeze({ ...args });
  }
}
export const SHORTCUT_COMMAND_IDS = Object.freeze(["inspector", "console", "network", "debugger", "downloads", "history", "restore", "split", "unsplit"]);
export function parseCommandBindings(text, paletteKey = "K") {
  let value;
  try { value = JSON.parse(text); } catch { throw new ValidationError("forge-error-shortcuts-json"); }
  if (!value || typeof value !== "object" || Array.isArray(value)) { throw new ValidationError("forge-error-shortcuts-object"); }
  const result = {}, used = new Set(["R", paletteKey.toUpperCase()]);
  for (const [id, raw] of Object.entries(value)) {
    if (!SHORTCUT_COMMAND_IDS.includes(id) || typeof raw !== "string" || !/^[A-Z]$/i.test(raw.trim())) { throw new ValidationError("forge-error-shortcuts-letter"); }
    const key = raw.trim().toUpperCase();
    if (used.has(key)) { throw new ValidationError("forge-error-shortcuts-conflict", { key }); }
    used.add(key); result[id] = key;
  }
  return result;
}
export const MAX_CUSTOM_CSS_LENGTH = 100_000;
export const MAX_SETTINGS_TRANSFER_LENGTH = 650_000;

export function readToolLayout(toolsText = "null", orderText = "null") {
  let tools, order;
  try { tools = JSON.parse(toolsText); } catch {}
  try { order = JSON.parse(orderText); } catch {}
  const valid = value => Array.isArray(value) && value.every(id => TOOL_IDS.includes(id)) && new Set(value).size === value.length;
  if (!valid(tools)) { tools = [...TOOL_IDS]; }
  if (!valid(order)) { order = tools; }
  const toolOrder = [...order, ...TOOL_IDS.filter(id => !order.includes(id))];
  return { tools: toolOrder.filter(id => tools.includes(id)), toolOrder };
}

export function presetForTheme(theme) {
  const normalized = normalizeTheme(theme);
  return Object.entries(THEME_PRESETS).find(([, preset]) =>
    Object.keys(normalized).every(key => key === "accent"
      ? normalized[key].toLowerCase() === preset[key].toLowerCase() : normalized[key] === preset[key]))?.[0] || "";
}

export function readTheme(serialized) {
  try {
    return normalizeTheme(JSON.parse(serialized));
  } catch {
    return { ...DEFAULT_THEME };
  }
}

export function searchCommands(commands, query) {
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return commands.filter(command => {
    const text = `${command.title} ${command.keywords || ""}`.toLocaleLowerCase();
    return terms.every(term => text.includes(term));
  });
}

export function parseSettingsTransfer(text) {
  if (text.length > MAX_SETTINGS_TRANSFER_LENGTH) { throw new ValidationError("forge-error-large-json"); }
  let data;
  try { data = JSON.parse(text); } catch { throw new ValidationError("forge-error-invalid-json"); }
  if (![1, 2].includes(data?.version) || !data.theme || typeof data.theme !== "object" || Array.isArray(data.theme) ||
      typeof data.css !== "string" || data.css.length > MAX_CUSTOM_CSS_LENGTH) {
    throw new ValidationError("forge-error-export-schema");
  }
  const result = { theme: normalizeTheme(data.theme), css: data.css };
  if (data.version === 2) {
    const layout = data.layout;
    const validIds = ids => Array.isArray(ids) && ids.every(id => TOOL_IDS.includes(id)) && new Set(ids).size === ids.length;
    if (!layout || typeof layout.paletteKey !== "string" || !/^[A-QS-Z]$/i.test(layout.paletteKey) ||
        !validIds(layout.tools) || !validIds(layout.toolOrder) || layout.toolOrder.length !== TOOL_IDS.length) {
      throw new ValidationError("forge-error-export-layout");
    }
    result.layout = { paletteKey: layout.paletteKey.toUpperCase(),
      ...readToolLayout(JSON.stringify(layout.tools), JSON.stringify(layout.toolOrder)) };
  }
  return result;
}

export function validateProject(value) {
  if (!value || typeof value.name !== "string" || !value.name.trim() || value.name.length > 80) {
    throw new ValidationError("forge-error-project-name");
  }
  let url;
  try { url = new URL(value.url); } catch { throw new ValidationError("forge-error-project-url"); }
  if (!["http:", "https:"].includes(url.protocol) ||
      !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) ||
      url.username || url.password || url.search || url.hash) {
    throw new ValidationError("forge-error-project-url");
  }
  if (!["inspector", "webconsole", "netmonitor", "jsdebugger"].includes(value.tool)) {
    throw new ValidationError("forge-error-project-tool");
  }
  return { name: value.name.trim(), url: url.href, tool: value.tool };
}
