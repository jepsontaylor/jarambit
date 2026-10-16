import contextlib
import io
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from ops.ci import ensure_cargo_cache as cache


class CargoCacheTests(unittest.TestCase):
    def run_preflight(self, results):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(cache.subprocess, 'run', side_effect=results) as run:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                code = cache.ensure('/toolchain with spaces/cargo', Path('Cargo.toml'))
        return code, run.call_args_list, output.getvalue() + errors.getvalue()

    def result(self, code=0, error=''):
        return subprocess.CompletedProcess([], code, '', error)

    def test_ready_cache_never_uses_network(self):
        code, calls, output = self.run_preflight([self.result()])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertIn('--offline', calls[0].args[0])
        self.assertIn('ready', output)

    def test_missing_index_is_rehydrated_then_verified_offline(self):
        with patch.dict(os.environ, {'CARGO_HOME': '/runner/cache', 'CARGO_NET_OFFLINE': 'true'}):
            code, calls, output = self.run_preflight([
                self.result(101, 'config.json not found in registry\n'), self.result(), self.result()])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 3)
        self.assertIn('--offline', calls[0].args[0])
        self.assertNotIn('--offline', calls[1].args[0])
        self.assertEqual(calls[1].kwargs['env']['CARGO_NET_OFFLINE'], 'false')
        self.assertEqual(calls[1].kwargs['env']['CARGO_HOME'], '/runner/cache')
        self.assertIn('--offline', calls[2].args[0])
        self.assertTrue(all('--locked' in call.args[0] for call in calls))
        self.assertIn('repaired', output)

    def test_network_failure_is_a_clear_retry_failure(self):
        code, calls, output = self.run_preflight([
            self.result(101, 'config.json missing\n'), self.result(101, 'network unavailable\n')])
        self.assertEqual(code, 75)
        self.assertEqual(len(calls), 2)
        self.assertIn('retry this job', output)
        self.assertIn('offline build was not run', output)

    def test_recovery_timeout_fails_closed(self):
        code, calls, output = self.run_preflight([
            self.result(101), subprocess.TimeoutExpired(['cargo', 'fetch'], 90)])
        self.assertEqual(code, 75)
        self.assertEqual(calls[1].kwargs['timeout'], 90)
        self.assertIn('retry this job', output)

    def test_online_success_alone_does_not_certify_cache(self):
        code, calls, output = self.run_preflight([
            self.result(101), self.result(), self.result(101, 'archive missing\n')])
        self.assertEqual(code, 75)
        self.assertEqual(len(calls), 3)
        self.assertIn('archive missing', output)


if __name__ == '__main__':
    unittest.main()
