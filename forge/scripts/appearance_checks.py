# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
import base64
from ui_wait import settle_ui


def run_appearance_checks(client, results, passed):
    def check(name, script):
        value = client.execute_script(script)
        if value is not True:
            raise AssertionError(f"{name}: {value!r}")
        passed.append(name)
        print(f"PASS {name}", flush=True)

    client.set_context("chrome")
    check("Custom icons are valid, consistently sized SVG paths", """
        const icons = Array.from(document.querySelectorAll('[data-forge-icon]'));
        const bad = icons.filter(svg => {
            const path = svg.querySelector('path');
            const bounds = path?.getBBox();
            return svg.getAttribute('viewBox') !== '0 0 24 24' || !path ||
                !Number.isFinite(path.getTotalLength()) || path.getTotalLength() <= 0 ||
                !bounds || bounds.x < 0 || bounds.y < 0 || bounds.x + bounds.width > 24.01 || bounds.y + bounds.height > 24.01 ||
                svg.getAttribute('aria-hidden') !== 'true';
        });
        return (icons.length >= 19 && bad.length === 0) || {count: icons.length, bad: bad.map(svg => svg.dataset.forgeIcon)};
    """)
    check("Brand icon loads rather than falling back to a broken image", """
        const image = document.querySelector('.forge-brand-mark');
        return image.complete && image.naturalWidth > 0;
    """)
    for mode in ("glass", "amoled"):
        client.execute_script("""
            document.getElementById('forge-hub-button').doCommand();
            document.querySelector('.forge-hub-action[data-action="Оформление"]').click();
            const editor = document.getElementById('forge-editor');
            editor.querySelector('[data-setting="appearance"]').value = arguments[0];
            editor.querySelector('#forge-theme-save').click();
        """, script_args=[mode])
        client.execute_async_script("""
            const done = arguments[arguments.length - 1];
            requestAnimationFrame(() => requestAnimationFrame(() => done(true)));
        """)
        if mode == "glass":
            check("Glass persists and uses real translucent layers with blur", """
                const style = getComputedStyle(document.getElementById('forge-rail'));
                return JSON.parse(Services.prefs.getStringPref('forge.theme')).appearance === 'glass' &&
                    style.backdropFilter.includes('blur(24px)') && style.backgroundColor.startsWith('rgba(');
            """)
        else:
            check("AMOLED persists and uses a true black shell without blur", """
                const style = getComputedStyle(document.getElementById('forge-rail'));
                return JSON.parse(Services.prefs.getStringPref('forge.theme')).appearance === 'amoled' &&
                    style.backgroundColor === 'rgb(0, 0, 0)' && style.backdropFilter === 'none';
            """)
        client.set_context("content")
        client.switch_to_window(client.window_handles[-1])
        client.execute_async_script("""
            const wanted = arguments[0];
            const done = arguments[arguments.length - 1];
            const timer = setInterval(() => {
                if (getComputedStyle(document.documentElement).getPropertyValue('--forge-appearance').trim() === wanted) {
                    clearInterval(timer); done(true);
                }
            }, 50);
        """, script_args=[mode])
        check(f"{mode.upper()} also reaches the local start page", """
            return ['glass', 'amoled'].includes(getComputedStyle(document.documentElement).getPropertyValue('--forge-appearance').trim());
        """)
        client.set_context("chrome")
        settle_ui(client)
        (results / f"appearance-{mode}.png").write_bytes(base64.b64decode(client.screenshot()))
