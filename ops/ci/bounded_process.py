"""Supervise one memcap scope; cancellation cleans only its attested unit/session."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time


def main(argv):
    cancelled = 0

    def cancel(signum, _frame):
        nonlocal cancelled
        cancelled = cancelled or signum

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, cancel)

    with tempfile.TemporaryDirectory(prefix='jarambit-ci-scope-') as temporary:
        report = Path(temporary) / 'scope.json'
        ack = Path(temporary) / 'admitted'
        env = {**os.environ, 'JARAMBIT_CI_SCOPE_REPORT': str(report),
               'JARAMBIT_CI_SCOPE_ACK': str(ack)}
        process = subprocess.Popen(argv, env=env, start_new_session=True)
        unit = None
        status = 1

        def unit_signal(name):
            if unit is not None:
                try:
                    subprocess.run(['systemctl', '--user', 'kill', '--kill-whom=all',
                                    '--signal=' + name, unit], capture_output=True, timeout=3)
                except (OSError, subprocess.TimeoutExpired) as error:
                    print('owned scope cleanup failed: ' + str(error), file=sys.stderr)

        def group_signal(signum):
            # Popen created this new session before exec. Before admission its
            # bootstrap children cannot execute the body or detach themselves.
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                pass

        try:
            deadline = time.monotonic() + 30
            while not cancelled and process.poll() is None and time.monotonic() < deadline:
                if report.exists():
                    info = json.loads(report.read_text())
                    pid = info['pid']
                    if type(pid) is not int or os.getsid(pid) != process.pid:
                        raise RuntimeError('scope reporter outside owned session')
                    actual = Path(f'/proc/{pid}/cgroup').read_text().strip().split('::', 1)[1]
                    candidate = Path(actual).name
                    if actual != info['cgroup'] or not re.fullmatch(r'run-[A-Za-z0-9_-]+\.scope', candidate):
                        raise RuntimeError('unattested memcap scope')
                    observed = subprocess.check_output(
                        ['systemctl', '--user', 'show', candidate, '-p', 'ControlGroup', '--value'],
                        text=True, timeout=3).strip()
                    if observed != actual:
                        raise RuntimeError('scope user-manager identity mismatch')
                    unit = candidate  # immutable after admission, before body runs
                    ack.write_text('admitted\n')
                    break
                time.sleep(0.02)
            if unit is None and not cancelled:
                status = process.poll()
                if status is None:
                    raise RuntimeError('bounded scope admission timed out')
                status = status or 1  # zero exit without admission is not a pass
            else:
                while not cancelled and process.poll() is None:
                    time.sleep(0.02)
                status = process.poll()
            if cancelled:
                status = 128 + cancelled
            elif status is not None and status < 0:
                status = 128 - status
        finally:
            # Unit cleanup includes detached grandchildren. The startup process
            # group closes the pre-admission cancellation window.
            try:
                unit_signal('SIGTERM')
            finally:
                group_signal(signal.SIGTERM)
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            try:
                unit_signal('SIGKILL')
            finally:
                group_signal(signal.SIGKILL)
                process.wait(timeout=3)
        return status if status is not None else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
