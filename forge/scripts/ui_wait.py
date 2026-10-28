# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/


def settle_ui(client):
    """Wait for finite Forge animations, never a website's own animations."""
    client.execute_async_script("""
        const done = arguments[arguments.length - 1];
        const animations = document.getAnimations({ subtree: true }).filter(animation => {
            const target = animation.effect?.target;
            const owned = animation.id === 'forge-motion' || animation.animationName?.startsWith('forge-') ||
                !!target?.closest?.('#forge-rail, #forge-control-center, #forge-palette, #forge-editor');
            return owned && Number.isFinite(animation.effect?.getTiming().iterations);
        });
        Promise.allSettled(animations.map(animation => animation.finished))
            .then(() => requestAnimationFrame(() => done(true)));
    """)
