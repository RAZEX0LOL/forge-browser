#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Create a separate locally ad-hoc-signed Forge.app; never modify the build."""
import argparse
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

package_ignore = shutil.ignore_patterns("moz.build", ".purgecaches")


def forge_metadata(data):
    result = dict(data)
    result.update(CFBundleName="Forge", CFBundleDisplayName="Forge",
                  CFBundleIdentifier="org.forgebrowser.development", CFBundleIconFile="forge.icns",
                  CFBundleExecutable="forge")
    # Preserve version, security and URL/document associations.
    return result


def create_icon(output):
    from PIL import Image, ImageDraw
    # Original geometry from overlay/forge.svg, rendered at 4x for antialiasing.
    size = 4096
    scale = size / 24
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(tuple(value * scale for value in (1, 1, 23, 23)),
                           radius=6 * scale, fill="#a4efce")
    points = [(6, 19), (6, 5), (19, 5), (16, 9), (10, 9), (10, 11),
              (16, 11), (13, 15), (10, 15), (10, 19)]
    draw.polygon([(x * scale, y * scale) for x, y in points], fill="#13291e")
    image.resize((1024, 1024), Image.Resampling.LANCZOS).save(output, format="ICNS")


def sign_bundle(output):
    # Artifact builds can omit the resource seals of helper bundles. Re-seal
    # each bundle inside-out, retaining its own entitlements and runtime flags.
    nested = [path for path in output.rglob("*") if path.is_dir() and path.suffix in (".app", ".framework")]
    # The runtime used to be the bundle's main executable. Once a launcher is
    # installed, seal it independently so its old Info.plist hash is replaced.
    runtime = output / "Contents/MacOS/firefox"
    updater_runtime = output / "Contents/MacOS/updater.app/Contents/MacOS/org.mozilla.updater.real"
    for bundle in [updater_runtime] + sorted(nested, key=lambda path: len(path.parts), reverse=True) + [runtime, output]:
        subprocess.run(["codesign", "--force", "--sign", "-", "--preserve-metadata=entitlements,requirements,flags,runtime", str(bundle)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(output)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "upstream/firefox")
    parser.add_argument("--output", type=Path, required=True, help="New path ending in Forge.app")
    parser.add_argument('--native-locale-stage',type=Path,help='Verified output of native_locale.py; built-in resources, not an extension')
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Packaging is supported on macOS only")
    source = args.source.resolve() / "obj-forge/dist/Nightly.app"
    output = args.output.absolute()
    if not (source / "Contents/Info.plist").is_file():
        parser.error("Build Nightly.app first")
    if output.name != "Forge.app" or output.exists() or output.is_symlink():
        parser.error("Output must be a new Forge.app; existing files are never overwritten")
    if source in output.parents:
        parser.error("Output cannot be inside the source app")
    if args.native_locale_stage:
        from native_locale import validate_stage
        validate_stage(args.native_locale_stage)
    # Check optional dependency before making a large copy.
    try:
        import PIL  # noqa: F401
    except ImportError:
        parser.error("Install requirements-package.txt in a virtual environment")
    # .purgecaches is consumed by Firefox at startup; sealing it would invalidate
    # the bundle's resource signature on its first launch.
    shutil.copytree(source, output, symlinks=False, ignore=package_ignore)
    if args.native_locale_stage:
        from native_locale import install
        install(args.native_locale_stage.resolve(),output)
    info = output / "Contents/Info.plist"
    info.write_bytes(plistlib.dumps(forge_metadata(plistlib.loads(info.read_bytes()))))
    create_icon(output / "Contents/Resources/forge.icns")
    subprocess.run(["xcrun", "clang", "-Wall", "-Wextra", "-Werror", "-O2",
                     str(Path(__file__).with_name("macos_launcher.c")), "-o", str(output / "Contents/MacOS/forge")], check=True)
    updater = output / "Contents/MacOS/updater.app/Contents/MacOS/org.mozilla.updater"
    updater.rename(updater.with_name(updater.name + '.real'))
    subprocess.run(["xcrun", "clang++", "-Wall", "-Wextra", "-Werror", "-O2", "-fobjc-arc", "-framework", "AppKit",
                    str(Path(__file__).with_name("macos_relauncher.mm")), "-o", str(updater)], check=True)
    sign_bundle(output)
    print(f"Created {output}\nLocal ad-hoc signature only. Not Developer ID signed or notarized; not a release.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
