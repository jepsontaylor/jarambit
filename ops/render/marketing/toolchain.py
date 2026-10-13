"""Local tool probes and the toolchain lock.

doctor reports what is installed. A missing required tool is a failure, never
a skip. OptiX verification is a separate step and refuses to start while
another process is over the yield line.
"""
import glob
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import canon

SCHEMA = "jarambit.render.toolchain.v1"
BLENDER_VERSION = "4.2.23"
BLENDER_URL = "https://download.blender.org/release/Blender4.2/blender-4.2.23-linux-x64.tar.xz"
COORDINATOR = "xbabe2"
REMOTE_HOSTS = ("xbabe3", "xbabe1")


def _run(argv, timeout=20):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def find_blender():
    env = os.environ.get("JARAMBIT_BLENDER")
    if env:
        return env
    pattern = os.path.expanduser(f"~/opt/blender-{BLENDER_VERSION}*-linux-x64/blender")
    found = sorted(glob.glob(pattern))
    return found[-1] if found else None


def find_gifski():
    env = os.environ.get("JARAMBIT_GIFSKI")
    if env:
        return env
    home = os.path.expanduser("~/opt/gifski/bin/gifski")
    if os.path.isfile(home):
        return home
    from shutil import which
    return which("gifski")


def probe_ffmpeg(binary="ffmpeg"):
    version = _run([binary, "-version"])
    encoders = _run([binary, "-hide_banner", "-encoders"])
    filters = _run([binary, "-hide_banner", "-filters"])
    text_v = version.stdout or ""
    text_e = encoders.stdout or ""
    text_f = filters.stdout or ""
    first = text_v.splitlines()[0] if text_v else ""
    zscale = any(line.split()[1:2] == ["zscale"] for line in text_f.splitlines())
    return {
        "path": binary,
        "ok": version.returncode == 0,
        "version_line": first,
        "libx264": "libx264" in text_e,
        "libx265": "libx265" in text_e,
        "libwebp": "libwebp" in text_e,
        "zscale": zscale,
    }


def probe_gifski():
    path = find_gifski()
    if not path or not os.path.isfile(path):
        return {"path": path, "ok": False, "version_line": ""}
    proc = _run([path, "--version"])
    line = (proc.stdout or proc.stderr or "").splitlines()
    return {"path": path, "ok": proc.returncode == 0, "version_line": line[0] if line else ""}


def probe_blender():
    path = find_blender()
    if not path or not os.path.isfile(path):
        return {"path": path, "ok": False, "version_line": "", "sha256": None}
    proc = _run([path, "--version"], timeout=60)
    line = (proc.stdout or "").splitlines()
    return {
        "path": path,
        "ok": proc.returncode == 0 and "Blender" in (proc.stdout or ""),
        "version_line": line[0] if line else "",
        "sha256": canon.sha256_file(path),
    }


def probe_host(name, timeout=6):
    if name == COORDINATOR:
        return {"name": name, "reachable": True, "hostname": _hostname(), "ssh": None}
    try:
        proc = _run(
            ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout}", name, "hostname"],
            timeout=timeout + 3,
        )
    except subprocess.TimeoutExpired:
        return {"name": name, "reachable": False, "hostname": "", "detail": "timeout"}
    return {
        "name": name,
        "reachable": proc.returncode == 0,
        "hostname": (proc.stdout or "").strip(),
        "detail": (proc.stderr or "").strip()[:200],
        "ssh": name,
    }


def _hostname():
    proc = _run(["hostname"])
    return (proc.stdout or "").strip()


def tarball_sha256(path=None):
    path = path or os.path.expanduser("~/opt/src/blender-4.2.23-linux-x64.tar.xz")
    if not os.path.isfile(path):
        return {"path": path, "sha256": None}
    return {"path": path, "sha256": canon.sha256_file(path)}


def collect(include_hosts=False):
    ffmpeg = probe_ffmpeg()
    report = {
        "schema": SCHEMA,
        "blender_pin": {
            "version": BLENDER_VERSION,
            "channel": "lts",
            "url": BLENDER_URL,
        },
        "ffmpeg": ffmpeg,
        "gifski": probe_gifski(),
        "blender": probe_blender(),
        "tarball": tarball_sha256(),
    }
    if include_hosts:
        report["hosts"] = [probe_host(COORDINATOR)] + [probe_host(name) for name in REMOTE_HOSTS]
    return report


def missing(report, require):
    """require is a set of names: ffmpeg, zscale, libx264, libx265, libwebp, gifski, blender."""
    gone = []
    ffmpeg = report.get("ffmpeg") or {}
    for name in require:
        if name == "ffmpeg":
            if not ffmpeg.get("ok"):
                gone.append(name)
        elif name in ("zscale", "libx264", "libx265", "libwebp"):
            if not ffmpeg.get(name):
                gone.append(name)
        elif name == "gifski":
            if not (report.get("gifski") or {}).get("ok"):
                gone.append(name)
        elif name == "blender":
            if not (report.get("blender") or {}).get("ok"):
                gone.append(name)
        else:
            gone.append(name)
    return gone


def lock_document(report, extra=None):
    doc = {
        "schema": SCHEMA,
        "blender": {
            "version": BLENDER_VERSION,
            "channel": "lts",
            "url": BLENDER_URL,
            "tarball_sha256": (report.get("tarball") or {}).get("sha256"),
            "tarball_path": (report.get("tarball") or {}).get("path"),
            "binary": report.get("blender"),
        },
        "ffmpeg": report.get("ffmpeg"),
        "gifski": report.get("gifski"),
        "hosts": report.get("hosts") or [],
    }
    if extra:
        doc.update(extra)
    return doc


def write_lock(path, report, extra=None):
    canon.atomic_write_json(path, lock_document(report, extra))
    return path


def gpu_yield_local():
    """Read the local GPU. Returns yield=True when another process is over the line."""
    import farm
    gpu = _run([
        "nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ])
    apps = _run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory", "--format=csv,noheader"])
    if gpu.returncode != 0:
        return {"yield": True, "detail": "nvidia-smi failed"}
    return farm.parse_nvidia_query(gpu.stdout, apps.stdout, our_pids=())


OPTIX_PY = """\
import bpy
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for dev in prefs.devices:
    if dev.type in ('OPTIX', 'CUDA'):
        dev.use = True
    print('DEVICE\\t%s\\t%s\\t%d' % (dev.type, dev.name, int(bool(dev.use))))
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.render.resolution_x = 16
scene.render.resolution_y = 16
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.filepath = {out!r}
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print('OPTIX_RENDER_OK')
"""


def optix_probe(out_png, script_path):
    """Render 16x16 / 1 spp on OptiX. Refuses when the yield rule says the GPU is taken."""
    state = gpu_yield_local()
    if state.get("yield"):
        return {"ok": False, "status": "yield", "gpu": state}
    blender = find_blender()
    if not blender:
        return {"ok": False, "status": "no-blender"}
    code = OPTIX_PY.format(out=out_png)
    with open(script_path, "w", encoding="utf-8") as fh:
        fh.write(code)
    proc = _run([
        blender, "-b", "--factory-startup", "--disable-autoexec",
        "--python-exit-code", "11", "-P", script_path,
    ], timeout=180)
    text = (proc.stdout or "") + (proc.stderr or "")
    devices = []
    for line in text.splitlines():
        if line.startswith("DEVICE\t"):
            _tag, kind, name, used = line.split("\t", 3)
            devices.append({"type": kind, "name": name, "use": used == "1"})
    return {
        "ok": proc.returncode == 0 and "OPTIX_RENDER_OK" in text and os.path.isfile(out_png),
        "status": "rendered" if proc.returncode == 0 else "error",
        "devices": devices,
        "returncode": proc.returncode,
        "tail": text[-1500:],
    }
