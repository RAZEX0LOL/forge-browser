"""Build a new macOS helper with an explicit minimum OS for every CGo object."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arch', choices=('arm64', 'amd64'), default='arm64')
    parser.add_argument('--build-number', required=True)
    args = parser.parse_args()
    if sys.platform != 'darwin' or not re.fullmatch(r'[1-9][0-9]{0,14}', args.build_number):
        parser.error('Requires macOS and a positive monotonic build number')
    if args.output.exists() or args.output.is_symlink():
        parser.error('Never overwrite an existing compiled helper')
    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = {**os.environ, 'CGO_ENABLED': '1', 'GOOS': 'darwin', 'GOARCH': args.arch,
           'MACOSX_DEPLOYMENT_TARGET': '13.0', 'GOTOOLCHAIN': 'local', 'GOMAXPROCS': '2',
           'CGO_CFLAGS': '-O2 -g -mmacosx-version-min=13.0',
           'CGO_CXXFLAGS': '-O2 -g -mmacosx-version-min=13.0',
           'CGO_LDFLAGS': '-mmacosx-version-min=13.0'}
    result = subprocess.run(['go', 'build', '-a', '-p', '1', '-trimpath', '-buildvcs=false',
                             '-ldflags', '-X=main.currentBuild=' + args.build_number,
                             '-o', str(args.output.resolve()), '.'], cwd=Path(__file__).resolve().parent,
                            env=env, capture_output=True, text=True, timeout=600)
    if result.returncode or "was built for newer" in result.stderr:
        # Preserve the candidate on disk for diagnosis rather than silently replacing it.
        sys.stderr.write(result.stdout + result.stderr)
        raise RuntimeError('Helper build failed or mixed newer-OS object files')
    arch = 'arm64' if args.arch == 'arm64' else 'x86_64'
    subprocess.run(['lipo', str(args.output), '-verify_arch', arch], check=True)
    deployment = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(args.output)], text=True)
    minimum = re.search(r'\bminos\s+(\d+)\.(\d+)', deployment)
    if not minimum or tuple(map(int, minimum.groups())) != (13, 0):
        raise RuntimeError('Unexpected helper minimum macOS version')
    print(deployment)


if __name__ == '__main__':
    main()
