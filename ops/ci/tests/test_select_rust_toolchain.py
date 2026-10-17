"""Neutral tool fixtures: no project build, solver or shared installation writes."""
import concurrent.futures
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ops.ci import select_rust_toolchain as toolchain


class SelectRustToolchainTests(unittest.TestCase):
    def fixture(self, missing=(), versions=None, channel='1.85.1'):
        # Keep fixtures in this lane's target, including when diagnosing failures.
        parent = toolchain.ROOT / 'target/ci-toolchain-tests'
        parent.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='installed toolchain ', dir=parent))
        manifest = root / 'rust-toolchain.toml'
        manifest.write_text('[toolchain]\nchannel = ' + json.dumps(channel) + '\n')
        home = root / 'install'
        binary_dir = home / 'toolchains/1.85.1-x86_64-unknown-linux-gnu/bin'
        binary_dir.mkdir(parents=True)
        for name in toolchain.TOOLS:
            if name in missing:
                continue
            version = (versions or {}).get(name, '1.85.1')
            binary = binary_dir / name
            binary.write_text(
                f'#!{sys.executable}\n'
                'import os, sys\n'
                'from pathlib import Path\n'
                f'name={name!r}\n'
                'if name == "cargo" and sys.argv[1:2] == ["clippy"]:\n'
                '    os.execvp("cargo-clippy", ["cargo-clippy", *sys.argv[2:]])\n'
                f'print(name + " {version} (neutral fixture)")\n')
            binary.chmod(0o755)
        return root, manifest, home, binary_dir

    def test_missing_shared_shims_do_not_break_subsequent_steps(self):
        root, manifest, home, expected = self.fixture()
        broken_shims = root / 'shared cargo home/bin'
        broken_shims.mkdir(parents=True)
        (broken_shims / 'cargo').symlink_to('absent-rustup')
        marker = root / 'rustup-invoked'
        rustup = broken_shims / 'rustup'
        rustup.write_text(f'#!{sys.executable}\nfrom pathlib import Path\n'
                          f'Path({str(marker)!r}).write_text("invoked")\nraise SystemExit(99)\n')
        rustup.chmod(0o755)
        env = {**os.environ, 'PATH': str(broken_shims),
               'CARGO_HOME': str(broken_shims.parent), 'RUSTUP_HOME': str(root / 'shared rustup')}
        before = subprocess.run(['/bin/bash', '-c', 'cargo --version'], env=env,
                                capture_output=True, text=True)
        self.assertEqual(before.returncode, 127)
        with patch.dict(os.environ, env, clear=True):
            selected, _ = toolchain.select(manifest, home)
        self.assertEqual(selected, expected)
        path_file, env_file = root / 'job-path', root / 'job-env'
        path_file.touch()
        env_file.touch()
        toolchain.export(selected, path_file, env_file)
        # Model how GitHub loads GITHUB_PATH/GITHUB_ENV for the next step.
        env['PATH'] = path_file.read_text().strip() + os.pathsep + env['PATH']
        env.update(line.split('=', 1) for line in env_file.read_text().splitlines())
        for arguments in (['cargo', '--version'], ['rustc', '--version'],
                          ['cargo', 'clippy', '--version']):
            result = subprocess.run(arguments, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('1.85.1', result.stdout)
        self.assertEqual(env['RUSTC'], str(expected / 'rustc'))
        self.assertEqual(env['RUSTDOC'], str(expected / 'rustdoc'))
        self.assertFalse(marker.exists(), 'shared rustup was invoked')

    def test_missing_required_component_fails_closed(self):
        for missing in toolchain.TOOLS:
            with self.subTest(missing=missing):
                _, manifest, home, _ = self.fixture(missing=(missing,))
                with self.assertRaisesRegex(ValueError, 'executable unavailable'):
                    toolchain.select(manifest, home)

    def test_wrong_compiler_or_cargo_release_fails_closed(self):
        for name in ('rustc', 'cargo'):
            with self.subTest(name=name):
                _, manifest, home, _ = self.fixture(versions={name: '1.86.0'})
                with self.assertRaisesRegex(ValueError, 'does not match Rust 1.85.1'):
                    toolchain.select(manifest, home)

    def test_shim_cannot_substitute_for_installed_binary(self):
        root, manifest, home, binaries = self.fixture(missing=('cargo',))
        shim = root / 'shim'
        shim.write_text('#!/bin/sh\nexit 99\n')
        shim.chmod(0o755)
        (binaries / 'cargo').symlink_to(shim)
        with self.assertRaisesRegex(ValueError, 'executable unavailable'):
            toolchain.select(manifest, home)

    def test_floating_channel_is_not_accepted(self):
        for channel in ('stable', '1.85', '1.85.1\nRUSTC=injected'):
            with self.subTest(channel=channel):
                _, manifest, home, _ = self.fixture(channel=channel)
                with self.assertRaisesRegex(ValueError, 'exact Rust release'):
                    toolchain.select(manifest, home)

    def test_concurrent_jobs_export_separately_without_install_writes(self):
        root, manifest, home, binaries = self.fixture()
        before = {p.relative_to(home): (p.stat().st_mtime_ns, p.read_bytes())
                  for p in home.rglob('*') if p.is_file()}

        def job(number):
            path_file, env_file = root / f'job-{number}-path', root / f'job-{number}-env'
            path_file.touch()
            env_file.touch()
            selected, _ = toolchain.select(manifest, home)
            toolchain.export(selected, path_file, env_file)
            return path_file.read_text(), env_file.read_text()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(job, (1, 2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], str(binaries) + '\n')
        after = {p.relative_to(home): (p.stat().st_mtime_ns, p.read_bytes())
                 for p in home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_setup_failure_does_not_export_environment(self):
        root, manifest, _, _ = self.fixture()
        path_file, env_file = root / 'job-path', root / 'job-env'
        path_file.write_text('unchanged-path\n')
        env_file.write_text('UNCHANGED=value\n')
        errors = io.StringIO()
        with patch.object(toolchain, 'ROOT', manifest.parent), \
                patch.object(toolchain.Path, 'home', return_value=root / 'missing-home'), \
                patch.dict(os.environ, {'GITHUB_PATH': str(path_file), 'GITHUB_ENV': str(env_file)}), \
                contextlib.redirect_stderr(errors):
            self.assertEqual(toolchain.main(), 1)
        self.assertIn('Provision the exact release and Clippy', errors.getvalue())
        self.assertIn('No shared toolchain installation or repair', errors.getvalue())
        self.assertEqual(path_file.read_text(), 'unchanged-path\n')
        self.assertEqual(env_file.read_text(), 'UNCHANGED=value\n')


if __name__ == '__main__':
    unittest.main()
