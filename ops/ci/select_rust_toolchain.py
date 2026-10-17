#!/usr/bin/env python3
"""Select installed CI binaries without invoking or updating shared Rustup shims."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ('cargo', 'rustc', 'rustdoc', 'cargo-clippy', 'clippy-driver')


def select(manifest, install_home):
    channel = tomllib.loads(manifest.read_text())['toolchain']['channel']
    if not isinstance(channel, str) or not re.fullmatch(r'\d+\.\d+\.\d+', channel):
        raise ValueError('CI requires an exact Rust release in rust-toolchain.toml')
    # The required self-hosted jobs admit Linux x64 hosts only. This is also
    # the preinstalled home used by version-check's generic Rust bridge.
    binary_dir = install_home / 'toolchains' / f'{channel}-x86_64-unknown-linux-gnu' / 'bin'
    if any(character in str(binary_dir) for character in ('\n', '\r')):
        raise ValueError('invalid installed toolchain path')
    for name in TOOLS:
        binary = binary_dir / name
        if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError(f'required installed executable unavailable: {binary}')
    environment = {**os.environ, 'PATH': str(binary_dir) + os.pathsep + os.environ.get('PATH', ''),
                   'RUSTC': str(binary_dir / 'rustc'), 'RUSTDOC': str(binary_dir / 'rustdoc')}
    versions = {}
    for name in ('rustc', 'cargo'):
        version = subprocess.check_output([str(binary_dir / name), '--version'],
                                          env=environment, text=True, timeout=10).strip()
        if version.split()[:2] != [name, channel]:
            raise ValueError(f'installed {name} does not match Rust {channel}: {version}')
        versions[name] = version
    return binary_dir, versions


def export(binary_dir, path_file, env_file):
    # These are GitHub's per-job environment files, never runner .env files.
    with path_file.open('a') as paths, env_file.open('a') as environment:
        paths.write(str(binary_dir) + '\n')
        environment.write(f'RUSTC={binary_dir / "rustc"}\nRUSTDOC={binary_dir / "rustdoc"}\n')


def main():
    try:
        binary_dir, versions = select(ROOT / 'rust-toolchain.toml', Path.home() / '.rustup')
        export(binary_dir, Path(os.environ['GITHUB_PATH']), Path(os.environ['GITHUB_ENV']))
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'::error::Pinned CI toolchain unavailable: {error}. '
              'Provision the exact release and Clippy outside active CI, then retry this job. '
              'No shared toolchain installation or repair was attempted.', file=sys.stderr)
        return 1
    print('CI_RUST_TOOLCHAIN=' + json.dumps({'bin': str(binary_dir), **versions}), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
