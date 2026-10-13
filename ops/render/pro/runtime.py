"""Memory admission and the host's hard 32G scope for every pro command."""
import os
from pathlib import Path
import shutil

GIB = 1024 ** 3
MEMCAP = 32 * GIB
MAX_THREADS = 16


def available_memory():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('MemAvailable is required for render admission')


def scope_limits():
    """Read actual cgroup limits; an environment flag is not proof of containment."""
    rel = next((s.split(':', 2)[2] for s in Path('/proc/self/cgroup').read_text().splitlines()
                if s.startswith('0::')), None)
    if rel is None:
        raise RuntimeError('cgroup v2 is required for memcap')
    base = Path('/sys/fs/cgroup')
    node = base / rel.lstrip('/')
    limits = []
    while node != base:
        maximum = (node / 'memory.max').read_text().strip()
        if maximum != 'max':
            limit = int(maximum)
            used = int((node / 'memory.current').read_text())
            swap = (node / 'memory.swap.max').read_text().strip()
            limits.append((limit, max(0, limit - used), swap))
        node = node.parent
    return limits


def safe_workers(requested=MAX_THREADS, *, fixed_bytes=2 * GIB, per_worker_bytes=GIB // 2,
                 free_bytes=None):
    """Bound worker threads by free memory, CPU count and the 32G shared command budget."""
    free = available_memory() if free_bytes is None else free_bytes
    # Leave 20% of free host memory for other workloads, even when the scope allows more.
    budget = min(MEMCAP, int(free * 0.8)) - fixed_bytes
    cpus = len(os.sched_getaffinity(0))
    count = min(int(requested), MAX_THREADS, cpus, budget // per_worker_bytes)
    if count < 1:
        raise RuntimeError('insufficient free memory for one render worker')
    return int(count)


def blender_command(command, workers):
    """Native flags must run before -P; conflicting flags cannot restore unbounded pools."""
    split = command.index('--') if '--' in command else len(command)
    native, script_args = command[:split], command[split:]
    cleaned = [native[0]]; threads = exit_code = None; script_started = late_flags = False
    i = 1
    while i < len(native):
        token = native[i]
        if token in ('-P', '--python', '--python-expr', '--python-console'):
            script_started = True
        if token in ('-t', '--threads', '--python-exit-code'):
            value = int(native[i+1])
            if not script_started:
                if token == '--python-exit-code': exit_code = value
                else: threads = value
            else:
                late_flags = True
            i += 2
            continue
        cleaned.append(token); i += 1
    applied = threads is not None and 0 < threads <= workers and exit_code is not None and exit_code > 0 and not late_flags
    chosen = min(workers, threads) if threads is not None and threads > 0 else workers
    bounded = [cleaned[0], '--threads', str(chosen), '--python-exit-code', '1', *cleaned[1:], *script_args]
    return bounded, applied, chosen


def ensure_memcap(*, fixed_bytes=2 * GIB, blender=False):
    """Re-exec uncapped entry points in memcap 32G; never launch if the wrapper is absent."""
    limits = scope_limits()
    free = min([available_memory(), *[remaining for _, remaining, _ in limits]])
    workers = safe_workers(fixed_bytes=fixed_bytes, free_bytes=free)
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    os.nice(max(0, 19 - os.getpriority(os.PRIO_PROCESS, 0)))
    capped = any(limit <= MEMCAP and swap == '0' for limit, _, swap in limits)
    command = [os.fsdecode(x) for x in Path('/proc/self/cmdline').read_bytes().split(b'\0') if x]
    if blender:
        command, applied, workers = blender_command(command, workers)
        if capped and not applied:
            os.execv(command[0], command)
            raise RuntimeError('Blender exec unexpectedly returned')
    if capped:
        return workers
    wrapper = shutil.which('memcap')
    if wrapper is None:
        fallback = Path.home() / 'bin/memcap'
        if fallback.is_file() and os.access(fallback, os.X_OK):
            wrapper = str(fallback)
    if wrapper is None:
        raise RuntimeError('memcap is required; refusing an uncapped pro command')
    os.execv(wrapper, [wrapper, '32G', '--', *command])
    raise RuntimeError('memcap exec unexpectedly returned')
