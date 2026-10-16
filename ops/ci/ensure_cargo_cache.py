#!/usr/bin/env python3
"""Rehydrate incomplete runner registry caches before a locked offline build."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def fetch(cargo, manifest, offline, timeout):
    command = [cargo, 'fetch', '--locked', '--manifest-path', str(manifest)]
    env = dict(os.environ)
    if offline:
        command.append('--offline')
    else:
        env.update(CARGO_NET_OFFLINE='false', CARGO_NET_RETRY='2', CARGO_HTTP_TIMEOUT='20')
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f'Cargo cache preflight: {error}', file=sys.stderr)
        return False
    if result.returncode:
        print(result.stderr, file=sys.stderr, end='')
        return False
    return True


def ensure(cargo, manifest):
    if fetch(cargo, manifest, offline=True, timeout=30):
        print('Cargo cache ready: locked offline fetch passed.')
        return 0
    home = os.environ.get('CARGO_HOME', str(Path.home() / '.cargo'))
    print(f'Cargo cache incomplete under {home}; rehydrating with a bounded locked fetch.', flush=True)
    if (fetch(cargo, manifest, offline=False, timeout=90)
            and fetch(cargo, manifest, offline=True, timeout=30)):
        print('Cargo cache repaired: locked offline fetch passed.')
        return 0
    print(f'::error::Cargo registry cache recovery failed under {home}. '
          'Check runner disk/network access, then retry this job; the offline build was not run.',
          file=sys.stderr)
    return 75


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cargo', required=True)
    parser.add_argument('--manifest-path', type=Path, default=Path('Cargo.toml'))
    args = parser.parse_args()
    return ensure(args.cargo, args.manifest_path)


if __name__ == '__main__':
    sys.exit(main())
