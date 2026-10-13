"""Frame farm.

Shards are contiguous ranges of 8 frames. One Blender process runs per GPU.
Dispatch is local on the coordinator and ssh+nohup on the other hosts.
A flock on /tmp/jarambit_render_gpu<uuid>.lock stops two jobs sharing a GPU.
Yield when another process holds more than half the VRAM or the GPU is over
half utilized while someone else is on it. Frames land via tmp+rename, with a
receipt. A later run skips a frame whose receipt hash still matches.
"""
import fcntl
import json
import os
import shlex
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import canon

SHARD_SIZE = 8
YIELD_UTIL = 50.0
YIELD_MEM = 0.50
SCRATCH_BUDGET_BYTES = 20 * 1024 ** 3
CPU_THREADS = 16
REQUEST_SCHEMA = "jarambit.render.request.v1"

# ssh Host xbabe2 is a different machine (the Mac alias). The coordinator is local.
DEFAULT_HOSTS = (
    {"name": "xbabe2", "ssh": None},
    {"name": "xbabe3", "ssh": "xbabe3"},
    {"name": "xbabe1", "ssh": "xbabe1"},
)


def shard_indices(count, size=SHARD_SIZE):
    count = int(count)
    if count < 0:
        raise ValueError("count must be >= 0")
    if size < 1:
        raise ValueError("shard size must be >= 1")
    return [list(range(start, min(start + size, count))) for start in range(0, count, size)]


def should_yield(gpu_util_percent, other_mem_bytes, mem_total_bytes, others_present):
    """True when some other process is over the yield line.

    Utilization is the whole GPU. It counts only when another compute process
    is present, so our own render does not trip the check. Memory is the sum
    of the other processes, not our own.
    """
    if not others_present:
        return False
    if gpu_util_percent is not None and float(gpu_util_percent) > YIELD_UTIL:
        return True
    total = float(mem_total_bytes or 0)
    if total <= 0:
        return False
    return float(other_mem_bytes or 0) / total > YIELD_MEM


def lock_path(gpu_uuid: str) -> str:
    safe = "".join(ch for ch in str(gpu_uuid) if ch.isalnum() or ch in "-_")
    if not safe:
        raise ValueError("gpu uuid is empty")
    return f"/tmp/jarambit_render_gpu{safe}.lock"


def acquire_gpu_lock(gpu_uuid: str, blocking=False):
    """Return an open file holding the lock, or None when the GPU is taken.

    The caller keeps the file object alive for as long as the lock should last.
    """
    path = lock_path(gpu_uuid)
    fh = open(path, "a+")
    flags = fcntl.LOCK_EX
    if not blocking:
        flags |= fcntl.LOCK_NB
    try:
        fcntl.flock(fh.fileno(), flags)
    except BlockingIOError:
        fh.close()
        return None
    return fh


def release_gpu_lock(fh):
    if fh is None:
        return
    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    fh.close()


def scratch_bytes(path) -> int:
    total = 0
    if not os.path.isdir(path):
        return 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def scratch_within_budget(path, budget=SCRATCH_BUDGET_BYTES) -> bool:
    return scratch_bytes(path) < budget


def frame_receipt_path(out_dir, index) -> str:
    return os.path.join(out_dir, f"frame_{int(index):04d}.receipt.json")


def write_receipt(out_dir, index, artifact_path, host, device_uuid, spp, seconds, plan_key):
    digest = canon.sha256_file(artifact_path)
    receipt = {
        "schema": "jarambit.render.receipt.v1",
        "frame_index": int(index),
        "host": host,
        "device_uuid": device_uuid,
        "spp": spp,
        "seconds": seconds,
        "sha256": digest,
        "path": os.path.abspath(artifact_path),
        "plan_key": plan_key,
    }
    canon.atomic_write_json(frame_receipt_path(out_dir, index), receipt)
    return receipt


def frame_done(out_dir, index) -> bool:
    path = frame_receipt_path(out_dir, index)
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as fh:
        receipt = json.load(fh)
    artifact = receipt.get("path")
    if not artifact or not os.path.isfile(artifact):
        return False
    return canon.sha256_file(artifact) == receipt.get("sha256")


def profile_for_request(profile, seed):
    return {
        "res": list(profile["res"]),
        "spp_max": profile["spp_max"],
        "spp_min": profile["spp_min"],
        "adaptive_threshold": profile["adaptive_threshold"],
        "denoise": bool(profile["denoise"]),
        "device": profile["device"],
        "seed": int(seed),
    }


def build_request(plan, shot, frames, profile_name, out_dir, bundle_path, regions_path):
    if profile_name not in plan["profiles"]:
        raise KeyError(profile_name)
    frozen_frames = []
    for frame in frames:
        frozen_frames.append({
            "index": int(frame["index"]),
            "az": frame["az"],
            "el": frame["el"],
            "distance_m": frame["distance_m"],
            "target": list(frame["target"]),
        })
    return {
        "schema": REQUEST_SCHEMA,
        "plan_key": plan["plan_key"],
        "bundle_path": bundle_path,
        "regions_path": regions_path,
        "finish_preset": plan["finish_preset"],
        "rig_preset": shot["rig_preset"],
        "accents": list(plan.get("accents") or []),
        "shot": {
            "id": shot["id"],
            "camera": shot["camera"],
            "frames": frozen_frames,
        },
        "profile": profile_for_request(plan["profiles"][profile_name], frames[0]["seed"]),
        "out_dir": out_dir,
    }


def iter_shards(plan):
    for shot in plan["shots"]:
        for profile_name in shot["profiles"]:
            frames = shot["frames"]
            for shard_i, idxs in enumerate(shard_indices(len(frames))):
                yield shot, profile_name, shard_i, [frames[i] for i in idxs]


def blender_argv(blender, worker, request_path, threads=CPU_THREADS):
    return [
        "nice", "-n", "10",
        "env", f"OMP_NUM_THREADS={threads}", f"OPENBLAS_NUM_THREADS={threads}",
        blender, "-b", "--factory-startup", "--disable-autoexec",
        "--python-exit-code", "11", "--threads", str(threads),
        "-P", worker, "--", "--request", request_path,
    ]


def shell_join(argv) -> str:
    return " ".join(shlex.quote(str(part)) for part in argv)


def prepare_jobs(plan, dest, bundle_path, regions_path, hosts=None):
    """Write one request JSON per shard. Skip shards whose receipts still verify."""
    hosts = list(hosts or DEFAULT_HOSTS)
    os.makedirs(dest, exist_ok=True)
    if not scratch_within_budget(dest):
        raise RuntimeError(f"scratch {dest} is at or over {SCRATCH_BUDGET_BYTES} bytes")
    jobs = []
    for shot, profile_name, shard_i, frames in iter_shards(plan):
        out_dir = os.path.join(dest, "shots", shot["id"], profile_name)
        os.makedirs(out_dir, exist_ok=True)
        done = all(frame_done(out_dir, frame["index"]) for frame in frames)
        request = build_request(plan, shot, frames, profile_name, out_dir, bundle_path, regions_path)
        request_path = os.path.join(dest, "requests", f"{shot['id']}_{profile_name}_{shard_i:03d}.json")
        canon.atomic_write_json(request_path, request)
        jobs.append({
            "shot_id": shot["id"],
            "profile": profile_name,
            "shard": shard_i,
            "frames": [frame["index"] for frame in frames],
            "request_path": request_path,
            "out_dir": out_dir,
            "status": "skip" if done else "pending",
            "host": None,
        })
    return jobs


def assign_hosts(jobs, host_states):
    """Round-robin pending shards onto hosts that are not yielding."""
    usable = [state for state in host_states if state.get("reachable") and not state.get("yield")]
    cursor = 0
    for job in jobs:
        if job["status"] != "pending":
            continue
        if not usable:
            job["status"] = "yield"
            continue
        job["host"] = usable[cursor % len(usable)]["name"]
        cursor += 1
    return jobs


def launch_shell(argv, log_path, ssh_host=None):
    """Detach with nohup. Return the remote or local pid string. Never kills the child."""
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    inner = f"nohup {shell_join(argv)} > {shlex.quote(log_path)} 2>&1 & echo $!"
    if ssh_host:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", ssh_host, inner]
    else:
        cmd = ["bash", "-c", inner]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return proc.stdout.strip().splitlines()[-1].strip()


def parse_nvidia_query(gpu_csv: str, apps_csv: str, our_pids):
    """Parse nvidia-smi CSV. gpu_csv is one line: util, mem.used, mem.total (MiB).

    apps_csv lines are: pid, process_name, used_memory MiB.
    """
    our = {int(pid) for pid in our_pids}
    line = gpu_csv.strip().splitlines()[0]
    parts = [part.strip().split()[0] for part in line.split(",")]
    util = float(parts[0])
    mem_total = float(parts[2]) * 1024 ** 2
    other_mem = 0.0
    others = 0
    for raw in apps_csv.splitlines():
        raw = raw.strip()
        if not raw or raw.lower().startswith("pid"):
            continue
        cols = [col.strip() for col in raw.split(",")]
        pid = int(cols[0])
        mem = float(cols[2].split()[0]) * 1024 ** 2
        if pid in our:
            continue
        others += 1
        other_mem += mem
    return {
        "util": util,
        "mem_total": mem_total,
        "other_mem": other_mem,
        "others_present": others > 0,
        "yield": should_yield(util, other_mem, mem_total, others > 0),
    }


def probe_host_gpu(host):
    """Reachability plus the yield rule. Unreachable hosts are not scheduled."""
    gpu_cmd = (
        "nvidia-smi --query-gpu=uuid,utilization.gpu,memory.used,memory.total "
        "--format=csv,noheader,nounits && echo '---' && "
        "nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader"
    )
    try:
        if host["ssh"] is None:
            proc = subprocess.run(["bash", "-c", gpu_cmd], capture_output=True, text=True, timeout=20)
        else:
            proc = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host["ssh"], gpu_cmd],
                capture_output=True, text=True, timeout=25,
            )
    except subprocess.TimeoutExpired:
        return {"name": host["name"], "reachable": False, "yield": True, "ssh": host["ssh"], "detail": "timeout"}
    if proc.returncode != 0:
        return {"name": host["name"], "reachable": False, "yield": True, "ssh": host["ssh"],
                "detail": (proc.stderr or "")[-300:]}
    gpu_text, _, apps = proc.stdout.partition("---")
    first = gpu_text.strip().splitlines()[0]
    uuid, util, used, total = [part.strip() for part in first.split(",")]
    parsed = parse_nvidia_query(f"{util}, {used}, {total}", apps, our_pids=())
    return {
        "name": host["name"],
        "reachable": True,
        "yield": parsed["yield"],
        "ssh": host["ssh"],
        "gpu_uuid": uuid,
        "gpu": parsed,
    }


def scratch_root(plan_key):
    return os.path.join(os.path.expanduser("~/jarambit_render_scratch"), plan_key)


def rewrite_request(request, root, bundle_path, regions_path):
    """Point a request at a host scratch directory. The schema fields stay the same."""
    updated = json.loads(json.dumps(request))
    inputs = os.path.join(root, "inputs")
    if bundle_path:
        updated["bundle_path"] = os.path.join(inputs, os.path.basename(bundle_path))
    if regions_path:
        updated["regions_path"] = os.path.join(inputs, os.path.basename(regions_path))
    shot = updated["shot"]["id"]
    updated["out_dir"] = os.path.join(root, "shots", shot, os.path.basename(request["out_dir"]))
    return updated


def _ssh(host, script, check=False):
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, script],
        capture_output=True, text=True, check=check,
    )


def push_files(ssh_host, files, dest_dir):
    files = [path for path in files if path and os.path.isfile(path)]
    if ssh_host is None:
        os.makedirs(dest_dir, exist_ok=True)
        for path in files:
            target = os.path.join(dest_dir, os.path.basename(path))
            if os.path.abspath(path) != os.path.abspath(target):
                shutil.copy2(path, target)
        return
    _ssh(ssh_host, f"mkdir -p {shlex.quote(dest_dir)}", check=True)
    if files:
        subprocess.run(["rsync", "-a", *files, f"{ssh_host}:{dest_dir}/"], check=True)


def pull_dir(ssh_host, remote_dir, local_dir):
    if not ssh_host:
        return
    os.makedirs(local_dir, exist_ok=True)
    subprocess.run(["rsync", "-a", f"{ssh_host}:{remote_dir}/", local_dir + "/"], check=False)


def remote_disk_ok(ssh_host, path):
    if ssh_host is None:
        return scratch_within_budget(path)
    proc = _ssh(ssh_host, f"du -sb {shlex.quote(path)} 2>/dev/null || echo 0")
    token = (proc.stdout or "0").split()
    try:
        return int(token[0]) < SCRATCH_BUDGET_BYTES
    except (ValueError, IndexError):
        return True


def render_jobs(plan, dest, bundle_path, regions_path, blender, worker, hosts=None, execute=False):
    """Prepare requests and, when execute is set, nohup one Blender per pending shard.

    execute probes each host first. A host over the yield line is left idle.
    This function does not kill, renice, or wait out a busy GPU.
    """
    if execute and not os.path.isfile(worker):
        raise RuntimeError(f"blender worker is not present: {worker}")
    if execute and not os.path.isfile(blender):
        raise RuntimeError(f"blender is not present: {blender}")
    host_list = list(hosts or DEFAULT_HOSTS)
    root = scratch_root(plan["plan_key"])
    if execute:
        for host in host_list:
            if host["ssh"]:
                pull_dir(host["ssh"], os.path.join(root, "shots"), os.path.join(dest, "shots"))
    jobs = prepare_jobs(plan, dest, bundle_path, regions_path, host_list)
    if execute:
        host_states = [probe_host_gpu(host) for host in host_list]
    else:
        host_states = [{"name": host["name"], "reachable": True, "yield": False, "ssh": host["ssh"]}
                       for host in host_list]
    assign_hosts(jobs, host_states)
    by_name = {state["name"]: state for state in host_states}
    if execute:
        for job in jobs:
            if job["status"] != "pending" or not job.get("host"):
                continue
            state = by_name[job["host"]]
            ssh_host = state.get("ssh")
            if not remote_disk_ok(ssh_host, root if ssh_host else dest):
                job["status"] = "disk"
                continue
            with open(job["request_path"], encoding="utf-8") as fh:
                request = json.load(fh)
            if ssh_host:
                updated = rewrite_request(request, root, bundle_path, regions_path)
                remote_request = os.path.join(root, "requests", os.path.basename(job["request_path"]))
                remote_worker_dir = os.path.join(root, "blender")
                remote_worker = os.path.join(remote_worker_dir, os.path.basename(worker))
                staged = os.path.join(dest, "remote_requests", state["name"], os.path.basename(job["request_path"]))
                canon.atomic_write_json(staged, updated)
                push_files(ssh_host, [bundle_path, regions_path], os.path.join(root, "inputs"))
                siblings = []
                worker_dir = os.path.dirname(os.path.abspath(worker))
                if os.path.isdir(worker_dir):
                    siblings = [os.path.join(worker_dir, name) for name in os.listdir(worker_dir) if name.endswith(".py")]
                push_files(ssh_host, siblings or [worker], remote_worker_dir)
                push_files(ssh_host, [staged], os.path.join(root, "requests"))
                launch_blender = blender
                launch_worker = remote_worker
                launch_request = remote_request
                log_path = os.path.join(root, "logs", f"{job['shot_id']}_{job['profile']}_{job['shard']:03d}.log")
                _ssh(ssh_host, f"mkdir -p {shlex.quote(os.path.dirname(log_path))}", check=True)
            else:
                launch_blender = blender
                launch_worker = worker
                launch_request = job["request_path"]
                log_path = os.path.join(dest, "logs", f"{job['shot_id']}_{job['profile']}_{job['shard']:03d}.log")
            argv = blender_argv(launch_blender, launch_worker, launch_request)
            if state.get("gpu_uuid"):
                lock = lock_path(state["gpu_uuid"])
                inner = (
                    f"exec 9>{shlex.quote(lock)}; "
                    f"flock -n 9 || {{ echo GPU_LOCK_BUSY; exit 75; }}; "
                    f"{shell_join(argv)}"
                )
                argv = ["bash", "-c", inner]
            job["pid"] = launch_shell(argv, log_path, ssh_host=ssh_host)
            job["status"] = "launched"
    summary = {
        "plan_key": plan["plan_key"],
        "jobs": len(jobs),
        "pending": sum(1 for job in jobs if job["status"] == "pending"),
        "skip": sum(1 for job in jobs if job["status"] == "skip"),
        "launched": sum(1 for job in jobs if job["status"] == "launched"),
        "yield": sum(1 for job in jobs if job["status"] == "yield"),
        "items": jobs,
    }
    canon.atomic_write_json(os.path.join(dest, "farm_jobs.json"), summary)
    return summary


