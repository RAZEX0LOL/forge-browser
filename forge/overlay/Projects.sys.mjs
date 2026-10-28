/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. https://mozilla.org/MPL/2.0/ */
import { validateProject, ValidationError } from "./core.sys.mjs";
import { createStrings } from "./Localization.sys.mjs";
const PREF = "forge.developer.projects";
export function projectCommands(win, toolbox) {
  const t = createStrings(win);
  const { PrivateBrowsingUtils } = ChromeUtils.importESModule("resource://gre/modules/PrivateBrowsingUtils.sys.mjs");
  const privateWindow = PrivateBrowsingUtils.isWindowPrivate(win);
  let projects;
  try {
    const stored = JSON.parse(Services.prefs.getStringPref(PREF, "[]"));
    projects = Array.isArray(stored) ? stored.slice(0, 20).map(validateProject) : [];
  } catch { projects = []; }
  return [
    { id: "project-add", title: t("forge-project-add"), keywords: "developer project localhost devtools", run: () => {
      if (privateWindow) { win.alert(t("forge-project-private")); return; }
      if (projects.length >= 20) { throw new ValidationError("forge-project-limit"); }
      const name = win.prompt(t("forge-project-name")); if (!name) { return; }
      const url = win.prompt(t("forge-project-url"), "http://localhost:3000/"); if (!url) { return; }
      const tool = win.prompt(t("forge-project-tool"), "netmonitor"); if (!tool) { return; }
      projects.push(validateProject({ name, url, tool }));
      Services.prefs.setStringPref(PREF, JSON.stringify(projects));
    } },
    ...projects.flatMap((project, index) => [
      { id: `project-open-${index}`, title: t("forge-project-open", { name: project.name }), keywords: `localhost developer ${project.url} ${project.tool}`, run: async () => {
        const tab = win.gBrowser.addTrustedTab(project.url);
        win.gBrowser.selectedTab = tab;
        await toolbox(project.tool);
      } },
      { id: `project-delete-${index}`, title: t("forge-project-delete", { name: project.name }), keywords: "developer project remove", run: () => {
        if (privateWindow || !win.confirm(t("forge-project-confirm", { name: project.name }))) { return; }
        projects.splice(index, 1); Services.prefs.setStringPref(PREF, JSON.stringify(projects));
      } },
    ]),
  ];
}
