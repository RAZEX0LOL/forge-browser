#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Prepare a pinned Firefox checkout without modifying an installed browser."""

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
from scripts.palette import compile_palette
STATE = ".forge-overlay-state.json"
HOOK = '  <script src="chrome://browser/content/forge/forge.js"></script>'
ANCHOR = '  <script src="chrome://browser/content/browser-main.js"></script>'
FILES = ("forge.js", "Forge.sys.mjs", "core.sys.mjs", "forge.css", "forge.svg",
         "Shell.sys.mjs", "Keyboard.sys.mjs", "TabTransfer.sys.mjs", "Shortcuts.sys.mjs", "NetworkAudit.sys.mjs", "Localization.sys.mjs", "localize.js", "locales/ru/forge.ftl", "locales/en-US/forge.ftl", "start.html", "start.css", "DesignSystem.sys.mjs",
         "design-tokens.sys.mjs", "design-system.css", "ControlCenter.sys.mjs", "hub.svg", "vault.svg", "Lifecycle.sys.mjs", "Icons.sys.mjs", "Motion.sys.mjs", "Workspaces.sys.mjs", "StartChild.sys.mjs", "StartParent.sys.mjs", "Toolbar.sys.mjs", "Commands.sys.mjs", "Projects.sys.mjs")


def localize_addon_strings(text):
    pairs = [('"Расширений пока нет."', 'forge-extensions-empty'),
             ('"Добавляй только те, которым доверяешь. Управление и установка из файла — в меню справа."', 'forge-extensions-help')]
    for literal, key in pairs:
        text = text.replace(literal, f'ChromeUtils.importESModule("chrome://browser/content/forge/Localization.sys.mjs").createStrings(window)("{key}")')
    return text


def localize_page_markup(text, header_id, messages):
    for literal, key in messages.items():
        pattern = r'(<(?:html:)?[\w-]+)([^<>]*)(>)' + re.escape(literal) + r'(?=</)'
        def insert(match):
            attrs = match[2]
            if 'data-forge-l10n=' not in attrs:
                attrs += f' data-forge-l10n="{key}"'
            return match[1] + attrs + match[3] + literal
        text = re.sub(pattern, insert, text)
    url = 'chrome://browser/content/forge/localize.js'
    if url not in text:
        pattern = rf'(<(?:html:)?header id="{re.escape(header_id)}"[^>]*>[\s\S]*?</(?:html:)?header>)'
        text, count = re.subn(pattern, lambda match: match[1] + f'\n<script src="{url}"></script>', text)
        if count != 1:
            raise ValueError(f'Forge localization header changed: {header_id}')
    return text


def integrate_addon_list(text):
    anchor = "  createEmptyListMessage() {"
    if 'id = "forge-extensions-empty"' in text:
        text = text.replace('icon.textContent = "⊞";', 'icon.append(forgeIcon(document, "extension"));')
        if "import { icon as forgeIcon }" not in text:
            text = 'import { icon as forgeIcon } from "chrome://browser/content/forge/Icons.sys.mjs";\n' + text
        return localize_addon_strings(text)
    if text.count(anchor) != 1:
        raise ValueError("Firefox extension empty state changed; manual review required")
    block = '''
    // Forge: an empty installed list is not an advertising surface.
    if (this.type === "extension") {
      const section = document.createElement("section");
      section.id = "forge-extensions-empty";
      const icon = document.createElement("div");
      icon.className = "forge-empty-icon";
      icon.append(forgeIcon(document, "extension"));
      icon.setAttribute("aria-hidden", "true");
      const title = document.createElement("h2");
      title.textContent = "Расширений пока нет.";
      const description = document.createElement("p");
      description.textContent = "Добавляй только те, которым доверяешь. Управление и установка из файла — в меню справа.";
      section.append(icon, title, description);
      return section;
    }
'''
    return localize_addon_strings('import { icon as forgeIcon } from "chrome://browser/content/forge/Icons.sys.mjs";\n' + text.replace(anchor, anchor + block))


def integrate_downloads(text):
    messages = {"FORGE / ЗАГРУЗКИ": "forge-downloads-eyebrow", "Твои загрузки.": "forge-downloads-title",
                "Файлы, прогресс и действия — в одном месте.": "forge-downloads-description",
                "Здесь будут твои файлы.": "forge-downloads-empty",
                "Завершённые и текущие загрузки появятся в этом списке.": "forge-downloads-empty-help"}
    glyph = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="64" height="64" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></svg>'
    old_empty = '''  <description id="downloadsListEmptyDescription"
               data-l10n-id="downloads-list-empty"/>'''
    new_empty = f'''  <html:section id="downloadsListEmptyDescription">
    <html:div class="forge-empty-icon" aria-hidden="true">{glyph}</html:div>
    <html:h2>Здесь будут твои файлы.</html:h2>
    <html:p>Завершённые и текущие загрузки появятся в этом списке.</html:p>
  </html:section>'''
    text = text.replace(old_empty, new_empty)
    text = text.replace('class="forge-empty-icon" aria-hidden="true">↓', f'class="forge-empty-icon" aria-hidden="true">{glyph}')
    if 'id="forge-downloads-header"' in text:
        return localize_page_markup(text.replace("FORGE / LOCAL FILES", "FORGE / ЗАГРУЗКИ"), 'forge-downloads-header', messages)
    anchor = '  <richlistbox flex="1"'
    if text.count(anchor) != 1:
        raise ValueError("Firefox downloads structure changed; manual review required")
    header = '''  <html:header id="forge-downloads-header">
    <html:div>FORGE / ЗАГРУЗКИ</html:div>
    <html:h1>Твои загрузки.</html:h1>
    <html:p>Файлы, прогресс и действия — в одном месте.</html:p>
  </html:header>
'''
    return localize_page_markup(text.replace(anchor, header + anchor), 'forge-downloads-header', messages)


def integrate_branding(text, fluent=False):
    names = ("brand-shorter-name", "brand-short-name", "brand-shortcut-name", "brand-full-name",
             "brand-product-name", "vendor-short-name") if fluent else ("brandShorterName", "brandShortName", "brandFullName")
    for name in names:
        pattern = rf"^({'-' if fluent else ''}{name}\s*=\s*).*$"
        if len(re.findall(pattern, text, flags=re.MULTILINE)) != 1:
            raise ValueError(f"Branding key changed: {name}")
        text = re.sub(pattern, r"\g<1>Forge", text, flags=re.MULTILINE)
    return text


def integrate_devtools_teardown(text, kind):
    """Keep process actors alive until their final cleanup IPC is acknowledged."""
    marker = "// Forge: ignore detached documents in page lifecycle notifications." if kind == "lifecycle" else "// Forge: drain watcher teardown before unregistering process actors."
    if marker in text:
        return text
    changes = {
        "lifecycle": [
            ('subject.defaultView.addEventListener("pageshow", handleEvent, {', 'subject.defaultView?.addEventListener("pageshow", handleEvent, {'),
            ('subject.defaultView.addEventListener("pagehide", handleEvent, {', 'subject.defaultView?.addEventListener("pagehide", handleEvent, {')],
        "parent": [('return this.sendAsyncMessage("DevToolsProcessParent:destroyWatcher", {',
                    'return this.sendQuery("DevToolsProcessParent:destroyWatcher", {')],
        "watcher": [
            ('      const domProcesses = ChromeUtils.getAllDOMProcesses();\n      for (const domProcess of domProcesses) {\n        domProcess.getActor(this._jsActorName).destroyWatcher({\n          watcherActorID: this.actorID,\n        });\n      }',
             '''      const domProcesses = ChromeUtils.getAllDOMProcesses();
      const pending = [];
      for (const domProcess of domProcesses) {
        try {
          pending.push(domProcess.getActor(this._jsActorName).destroyWatcher({
            watcherActorID: this.actorID,
          }));
        } catch (error) {
          // A content process may have already exited during tab/window closure.
          if (error.name !== "InvalidStateError" && error.name !== "AbortError") {
            throw error;
          }
        }
      }
      ParentProcessWatcherRegistry.deferUnregisterUntil(Promise.allSettled(pending));''')],
        "registry": [
            ('  maybeUnregisterJSActors() {\n    if (sessionDataByWatcherActor.size == 0) {',
             '''  deferUnregisterUntil(promise) {
    pendingTeardowns.add(promise);
    promise.finally(() => {
      pendingTeardowns.delete(promise);
      this.maybeUnregisterJSActors();
    });
  },

  maybeUnregisterJSActors() {
    if (sessionDataByWatcherActor.size == 0 && pendingTeardowns.size === 0) {'''),
            ('let isJSProcessActorRegistered = false;',
             'const pendingTeardowns = new Set();\nlet isJSProcessActorRegistered = false;')],
    }
    for before, after in changes[kind]:
        if text.count(before) != 1:
            raise ValueError(f"Firefox DevTools {kind} teardown changed; manual review required")
        text = text.replace(before, after)
    return marker + "\n" + text


def integrate_preferences(text):
    messages = {"FORGE / НАСТРОЙКИ": "forge-settings-eyebrow", "Браузер под твоим контролем.": "forge-settings-title",
                "Все настройки — без рекламных предложений.": "forge-settings-description",
                "Политики приватности": "forge-sidebar-policies", "Расширения": "forge-command-addons", "Загрузки": "forge-command-downloads"}
    anchor = '        <html:div id="search-container">'
    header = '''          <!-- BEGIN FORGE SETTINGS -->
          <html:header id="forge-settings-header">
            <html:div class="forge-settings-eyebrow">FORGE / НАСТРОЙКИ</html:div>
            <html:h2>Браузер под твоим контролем.</html:h2>
            <html:p>Все настройки — без рекламных предложений.</html:p>
            <html:nav aria-label="Разделы Forge">
              <html:a href="about:policies">Политики приватности</html:a>
              <html:a href="about:addons">Расширения</html:a>
              <html:a href="about:downloads">Загрузки</html:a>
            </html:nav>
          </html:header>
          <!-- END FORGE SETTINGS -->'''
    if 'id="forge-settings-header"' in text:
        text = text.replace("FORGE / CONTROL ROOM", "FORGE / НАСТРОЙКИ")
    else:
        if text.count(anchor) != 1:
            raise ValueError("Firefox settings structure changed; manual review required")
        text = text.replace(anchor, anchor + "\n" + header)
    text = text.replace('aria-label="Разделы Forge"', 'aria-label="Разделы Forge" data-forge-l10n="forge-settings-navigation" data-forge-l10n-attr="aria-label"') if 'data-forge-l10n="forge-settings-navigation"' not in text else text
    return localize_page_markup(text, 'forge-settings-header', messages)


def replace_block(text, name, content, prefix="//"):
    start, end = f"{prefix} BEGIN FORGE {name}", f"{prefix} END FORGE {name}"
    block = f"{start}\n{content}\n{end}"
    if start in text or end in text:
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError(f"Invalid managed {name} block")
        before, rest = text.split(start)
        _, after = rest.split(end)
        return before + block + after
    return text.rstrip() + "\n\n" + block + "\n"


def privacy_outputs(project):
    config = json.loads((project / "privacy.json").read_text())
    locked, defaults = config["locked"], config["defaults"]
    if locked.keys() & defaults.keys():
        raise ValueError("Privacy defaults and locks must not overlap")
    # The Gecko default-pref parser supports native `locked` attributes. Unlike
    # Preferences enterprise policy, it does not reject toolkit/app/nimbus names
    # and is applied before profile startup. No AutoConfig JavaScript is needed.
    prefs = "\n".join(f"pref({json.dumps(key)}, {json.dumps(value)}{', locked' if key in locked else ''});"
                      for key, value in sorted({**defaults, **locked}.items()))
    policies = {"policies": {
        "DisableTelemetry": True,
        "DisableFirefoxStudies": True,
        "UserMessaging": {"ExtensionRecommendations": False, "FeatureRecommendations": False,
                          "UrlbarInterventions": False, "SkipOnboarding": True,
                          "MoreFromMozilla": False, "FirefoxLabs": False, "Locked": True},
        "FirefoxHome": {"SponsoredTopSites": False, "Stories": False,
                        "SponsoredStories": False, "Weather": False,
                        "Highlights": False, "Widgets": {"Enabled": False}, "Locked": True},
    }}
    return prefs, (json.dumps(policies, ensure_ascii=False, indent=2) + "\n").encode()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def integrate_xhtml(text):
    if text.count(ANCHOR) != 1:
        raise ValueError("Firefox browser-main.js hook changed; manual review required")
    if HOOK in text:
        if text.count(HOOK) != 1 or ANCHOR + "\n" + HOOK not in text:
            raise ValueError("Unexpected existing Forge hook")
        return text
    return text.replace(ANCHOR, ANCHOR + "\n" + HOOK)


def integrate_jar(text):
    if text.count("browser.jar:") != 1:
        raise ValueError("Unexpected browser jar manifest")
    lines = [f"        content/browser/forge/{name} (content/forge/{name})" for name in FILES]
    for name in ["icon16.png", "icon32.png", "icon48.png", "icon64.png", "icon128.png",
                 "about.png", "about-logo.png", "about-logo@2x.png", "about-logo.svg"]:
        lines.append(f"% override chrome://branding/content/{name} chrome://browser/content/forge/forge.svg")
    # Migrate the original manifest block when adding overlay files.
    if "# Forge overlay\n" in text:
        before, after = text.split("# Forge overlay\n", 1)
        existing = after.splitlines(keepends=True)
        while existing and existing[0].lstrip().startswith("content/browser/forge/"):
            existing.pop(0)
        text = before + "".join(existing)
    if "# BEGIN FORGE RESOURCES" in text:
        return replace_block(text, "RESOURCES", "\n".join(lines), "#")
    if "content/browser/forge/" in text:
        raise ValueError("Unexpected existing Forge jar entries")
    # Insert before any conditional preprocessor directives in the manifest.
    block = "# BEGIN FORGE RESOURCES\n" + "\n".join(lines) + "\n# END FORGE RESOURCES\n"
    return text.replace("browser.jar:\n", "browser.jar:\n" + block, 1)


def prepare(root, project=PROJECT, verify_revision=True):
    root = root.resolve()
    if root == project.resolve() or project.resolve().is_relative_to(root):
        raise ValueError("Firefox checkout must not contain the Forge project")
    config = json.loads((project / "upstream.json").read_text())
    if verify_revision and git(root, "rev-parse", "HEAD") != config["revision"]:
        raise ValueError("Checkout revision differs from upstream.json; refusing to patch")
    state_path = root / STATE
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    # Protect all files previously written by us, including upstream hook files.
    for name, expected in previous.items():
        target = root / name
        if not target.is_file() or digest(target.read_bytes()) != expected:
            raise ValueError(f"Local changes in {name}; preserve/review them before preparing")
    xhtml = "browser/base/content/browser.xhtml"
    jar = "browser/base/jar.mn"
    prefs, policies = privacy_outputs(project)
    profile = "browser/app/profile/firefox.js"
    distribution = "browser/app/distribution/moz.build"
    preferences = "browser/components/preferences/preferences.xhtml"
    brand_ftl = "browser/branding/unofficial/locales/en-US/brand.ftl"
    brand_properties = "browser/branding/unofficial/locales/en-US/brand.properties"
    main_settings = "browser/components/preferences/main.js"
    addon_list = "toolkit/mozapps/extensions/content/components/addon-list.mjs"
    downloads = "browser/components/downloads/content/contentAreaDownloadsView.xhtml"
    logins = "browser/components/aboutlogins/content/aboutLogins.html"
    devtools = {
        "lifecycle": "devtools/server/connectors/js-process-actor/target-watchers/window-global.sys.mjs",
        "parent": "devtools/server/connectors/js-process-actor/DevToolsProcessParent.sys.mjs",
        "watcher": "devtools/server/actors/watcher.js",
        "registry": "devtools/server/actors/watcher/ParentProcessWatcherRegistry.sys.mjs",
    }
    settings_script = (root / main_settings).read_text()
    for image in ("kit-happy.svg", "kit-concerned.svg"):
        settings_script = settings_script.replace(f"chrome://global/skin/illustrations/{image}",
                                                   "chrome://browser/content/forge/forge.svg")
    writes = {
        xhtml: integrate_xhtml((root / xhtml).read_text()).encode(),
        jar: integrate_jar((root / jar).read_text()).encode(),
        ".mozconfig": (project / "mozconfig").read_bytes(),
        profile: replace_block((root / profile).read_text(), "PRIVACY", prefs).encode(),
        distribution: replace_block((root / distribution).read_text(), "POLICIES",
                                    'FINAL_TARGET_FILES.distribution += ["policies.json"]', "#").encode(),
        "browser/app/distribution/policies.json": policies,
        preferences: integrate_preferences((root / preferences).read_text()).encode(),
        brand_ftl: integrate_branding((root / brand_ftl).read_text(), fluent=True).encode(),
        brand_properties: integrate_branding((root / brand_properties).read_text()).encode(),
        main_settings: settings_script.encode(),
        addon_list: integrate_addon_list((root / addon_list).read_text()).encode(),
        downloads: integrate_downloads((root / downloads).read_text()).encode(),
        logins: (root / logins).read_text().replace(
            "chrome://global/content/megalist/icons/cpm-fox-illustration.svg",
            "chrome://browser/content/forge/vault.svg").encode(),
    }
    for name in FILES:
        data = (project / "overlay" / name).read_bytes()
        if name.endswith(".css"):
            data = compile_palette(data.decode()).encode()
        writes[f"browser/base/content/forge/{name}"] = data
    for kind, name in devtools.items():
        writes[name] = integrate_devtools_teardown((root / name).read_text(), kind).encode()
    # Preflight everything before writing anything. Never overwrite unknown files.
    for name, data in writes.items():
        target = root / name
        if name not in (xhtml, jar, profile, distribution, preferences, brand_ftl, brand_properties,
                        main_settings, addon_list, downloads, logins, *devtools.values()) and target.exists() and name not in previous:
            if target.read_bytes() != data:
                raise ValueError(f"Refusing to overwrite existing {name}")
    for name, data in writes.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    state_path.write_text(json.dumps({name: digest(data) for name, data in writes.items()}, indent=2) + "\n")
    return len(writes)


def clone(root):
    config = json.loads((PROJECT / "upstream.json").read_text())
    if root.exists():
        raise ValueError("Destination already exists; clone only accepts a new directory")
    if not shutil.which("git"):
        raise ValueError("git is required")
    root.parent.mkdir(parents=True, exist_ok=True)
    # Failures leave a partial checkout intact for diagnosis; nothing is deleted.
    subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", "--depth=1",
                    config["repository"], str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "fetch", "--depth=1", "origin", config["revision"]], check=True)
    subprocess.run(["git", "-C", str(root), "checkout", "--detach", config["revision"]], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("clone", "prepare"))
    parser.add_argument("--source", type=Path, default=PROJECT / "upstream" / "firefox")
    args = parser.parse_args()
    try:
        if args.command == "clone":
            clone(args.source.resolve())
        else:
            print(f"Prepared {prepare(args.source)} files in {args.source.resolve()}")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Forge: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
