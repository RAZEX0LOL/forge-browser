#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. https://mozilla.org/MPL/2.0/
"""Run Mozilla's development commands with the project's isolated build cache."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap", "build", "run", "package", "smoke"))
    parser.add_argument("--source", type=Path, default=PROJECT / "upstream/firefox")
    parser.add_argument("--diagnostics", action="store_true", help="Write local startup status only (no browsing data)")
    args = parser.parse_args()
    source = args.source.resolve()
    state = (PROJECT / ".mozbuild").resolve()
    if any(char.isspace() for char in str(source) + str(state)):
        parser.error("Mozilla requires source and build cache paths without spaces. "
                     "Move the checkout/cache and leave directory symlinks in the project.")
    if not (source / "mach").is_file():
        parser.error("Firefox checkout not found; run scripts/forge.py clone first")
    env = {**os.environ, "MOZBUILD_STATE_PATH": str(state), "MACH_TELEMETRY_NO_SUBMIT": "1"}
    command = [sys.executable, str(source / "mach")]
    if args.command == "bootstrap":
        command += ["--no-interactive", "bootstrap", "--application-choice",
                    "browser_artifact_mode", "--no-system-changes", "--no-agentic-tools"]
    elif args.command == "run":
        profile = source / "obj-forge/test-profile"
        profile.mkdir(parents=True, exist_ok=True)
        for variable, name in [("MOZ_APP_DATA", "test-app-data"),
                               ("MOZ_LOCAL_APP_DATA", "test-local-app-data")]:
            folder = source / "obj-forge" / name
            folder.mkdir(parents=True, exist_ok=True)
            env[variable] = str(folder)
        if args.diagnostics:
            folder = source / "obj-forge/diagnostics"
            folder.mkdir(parents=True, exist_ok=True)
            log = folder / "startup.jsonl"
            log.touch(exist_ok=True)  # IOUtils append mode expects an existing file.
            env["FORGE_DIAGNOSTICS_PATH"] = str(log)
        # Frontend-only artifact rebuilds can keep the same compiled BuildID.
        # Never reuse stale XUL/JS bytecode from an older Forge development build.
        command += ["run", "--purgecaches", "--no-remote", "--profile", str(profile)]
    elif args.command == "smoke":
        command = [str(PROJECT / ".venv-test/bin/python"), str(PROJECT / "scripts/smoke.py"),
                   "--binary", str(source / "obj-forge/dist/Nightly.app/Contents/MacOS/firefox")]
    else:
        command += [args.command]
    return subprocess.run(command, cwd=source, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
