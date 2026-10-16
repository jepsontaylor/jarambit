# Capability contracts for the required Linux self-hosted CI shell wrapper.
import json
import os
from pathlib import Path
import subprocess
import signal
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
WRAPPER = ROOT / 'ops/ci/run_bounded.sh'


class BoundedCITests(unittest.TestCase):
    def test_pid_cancellation_stops_body_and_detached_child_preserves_other_job(self):
        def alive(pid):
            try:
                text = Path(f'/proc/{pid}/stat').read_text()
                return text[text.rfind(')') + 2:].split()[0] != 'Z'
            except FileNotFoundError:
                return False

        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                pidfile = folder / 'owned-pids.json'
                payload = folder / 'body.py'
                payload.write_text('import json,os,subprocess,time\n'
                                   'from pathlib import Path\n'
                                   'p=subprocess.Popen(["sleep","30"],start_new_session=True)\n'
                                   f'target=Path({str(pidfile)!r})\n'
                                   'tmp=target.with_suffix(".tmp")\n'
                                   'tmp.write_text(json.dumps([os.getpid(),p.pid]))\n'
                                   'tmp.replace(target)\n'
                                   'time.sleep(30)\n')
                body = folder / 'body.sh'
                body.write_text('exec python3 "' + str(payload) + '"\n')
                sentinel = subprocess.Popen(['sleep', '30'])
                process = subprocess.Popen(['bash', str(WRAPPER), 'version', str(body)],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                owned = []
                try:
                    deadline = time.monotonic() + 15
                    raw_pids = ''
                    while process.poll() is None and time.monotonic() < deadline:
                        if pidfile.is_file():
                            raw_pids = pidfile.read_text().strip()
                            if raw_pids:
                                break
                        time.sleep(0.02)
                    if not raw_pids and pidfile.is_file():
                        raw_pids = pidfile.read_text().strip()
                    self.assertTrue(bool(raw_pids), 'bounded body did not write non-empty pidfile')
                    owned = json.loads(raw_pids)
                    process.send_signal(signum)
                    stdout, stderr = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 128 + signum, stdout + stderr)
                    deadline = time.monotonic() + 3
                    while any(alive(pid) for pid in owned) and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertFalse(any(alive(pid) for pid in owned), 'owned work survived cancellation')
                    self.assertIsNone(sentinel.poll(), 'unrelated sentinel was stopped')
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.communicate(timeout=10)
                    for pid in owned:
                        if alive(pid):
                            os.kill(pid, signal.SIGKILL)  # only this fixture's recorded children
                    sentinel.terminate()
                    sentinel.wait(timeout=5)

    def test_invalid_profile_never_executes_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            body = folder / 'body.sh'
            marker = folder / 'executed'
            body.write_text('touch "' + str(marker) + '"\n')
            result = subprocess.run(['bash', str(WRAPPER), 'unknown', str(body)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(marker.exists())

    def test_missing_script_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(['bash', str(WRAPPER), 'version', temporary + '/absent'], capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_real_version_profile_and_quoted_script_path(self):
        # This is required on admitted CI/Linux hosts. Missing capability is an error.
        self.assertTrue(Path('/home/ubuntu/bin/memcap').is_file(), 'required CI memcap unavailable')
        with tempfile.TemporaryDirectory(prefix='bounded ci ') as temporary:
            body = Path(temporary) / 'script with spaces.sh'
            body.write_text('printf "BOUNDED_BODY_EXECUTED\\n"\n')
            result = subprocess.run(['bash', str(WRAPPER), 'version', str(body)], capture_output=True,
                                    text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            probes = [line.split('=', 1)[1] for line in result.stdout.splitlines()
                      if line.startswith('CI_RESOURCE_PROBE=')]
            self.assertEqual(len(probes), 1)
            probe = json.loads(probes[0])
            self.assertLessEqual(probe['memory_max'], 2147483648)
            self.assertEqual(probe['swap_max'], 0)
            self.assertEqual(len(probe['affinity']), 1)
            self.assertEqual(probe['native_pools'], 1)
            self.assertIn('BOUNDED_BODY_EXECUTED', result.stdout)

    def test_body_failure_status_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            body = Path(temporary) / 'failure.sh'
            body.write_text('exit 37\n')
            result = subprocess.run(['bash', str(WRAPPER), 'version', str(body)],
                                    capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 37, result.stdout + result.stderr)

    def test_inside_marker_cannot_bypass_probe_under_optimized_python(self):
        with tempfile.TemporaryDirectory() as temporary:
            body = Path(temporary) / 'body.sh'
            marker = Path(temporary) / 'executed'
            body.write_text('touch "' + str(marker) + '"\n')
            env = {**os.environ, 'PYTHONOPTIMIZE': '1', 'JARAMBIT_CI_BOUNDED': '1',
                   'OMP_NUM_THREADS': '9', 'OPENBLAS_NUM_THREADS': '1',
                   'MKL_NUM_THREADS': '1', 'CARGO_BUILD_JOBS': '1', 'RUST_TEST_THREADS': '1'}
            result = subprocess.run(['bash', str(WRAPPER), '--inside', 'version', str(body)],
                                    capture_output=True, env=env, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
