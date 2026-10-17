#!/usr/bin/env python3
"""Record source-file byte identities without interpreting their contents.

Default mode reads Git blobs from one resolved commit. --runtime-root reads
local files instead; those hashes do not establish committed source availability.
Neither mode validates results or supplies scientific admission/certification.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ops.ci.publication_inventory import Snapshot, repository_path, sha256


def collect_sources(root, paths, revision):
    """Hash exactly the bytes read; revision=None explicitly selects local mode."""
    root = root.resolve()
    names = [repository_path(path) for path in paths]
    if not names or len(set(names)) != len(names):
        raise ValueError('Expected a nonempty list of distinct source paths')
    snapshot = Snapshot(root, revision) if revision is not None else None
    sources = []
    for name in sorted(names):
        if snapshot is not None:
            raw = snapshot.read(name)
        else:
            path = (root / name).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError('Expected a source file inside the local root: ' + name)
            raw = path.read_bytes()
        sources.append({'path': name, 'size_bytes': len(raw), 'sha256': sha256(raw)})
    return {
        'schema': 'source-file-ledger.v1',
        'source_mode': 'committed_git_blobs' if snapshot else 'local_files_unchecked_against_git',
        'source_commit': snapshot.commit if snapshot else None,
        'scope': 'File identities only; no result validation, scientific admission or certification.',
        'sources': sources,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--ref', help='Git revision, resolved once; default: origin/main')
    mode.add_argument('--runtime-root', type=Path, help='Read local files; no Git availability check')
    parser.add_argument('sources', nargs='+', help='Source paths relative to the selected root')
    args = parser.parse_args(argv)
    try:
        report = collect_sources(args.runtime_root or ROOT, args.sources,
                                 None if args.runtime_root else args.ref or 'origin/main')
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'source_ledger: {error}\n')
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
