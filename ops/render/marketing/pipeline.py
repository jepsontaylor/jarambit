#!/usr/bin/env python3
"""Marketing render CLI.

  pipeline.py doctor [--require ffmpeg,zscale,blender] [--write-lock] [--hosts]
  pipeline.py plan --bundle bundle.json --out plan.json [--regions regions.json]
  pipeline.py render --plan plan.json --dest DIR [--bundle B] [--regions R] [--execute]
  pipeline.py finish --in DIR --out DIR
  pipeline.py encode --frames DIR --out DIR
  pipeline.py qa --measurements measurements.json --out qa.json [--stills a.png]
  pipeline.py package --root DIR [--cad C.9.3.step] [--cad-sha 3a818183...] --bundle-sha SHA --plan-key KEY --file SRC=NAME:ROLE
  pipeline.py all ...   runs the stages that have their inputs; a missing peer tool fails the stage

ingest and finish delegate to the Codex and Claude modules when those files exist.
This process never imports bpy. It does not upload a release.
"""
import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import canon
import encode as encode_mod
import farm as farm_mod
import package as package_mod
import plan as plan_mod
import qa as qa_mod
import toolchain as toolchain_mod

LOCK_PATH = os.path.join(_HERE, "toolchain.lock.json")


def _load_peer(name):
    path = os.path.join(_HERE, name + ".py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location(f"marketing_{name}", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _die(message, code=2):
    print(message, file=sys.stderr)
    raise SystemExit(code)


def cmd_doctor(args):
    report = toolchain_mod.collect(include_hosts=args.hosts)
    require = [part.strip() for part in (args.require or "").split(",") if part.strip()]
    gone = toolchain_mod.missing(report, require)
    if args.write_lock:
        toolchain_mod.write_lock(args.lock or LOCK_PATH, report)
        print(f"wrote {args.lock or LOCK_PATH}")
    print(json.dumps({
        "ffmpeg": report["ffmpeg"]["version_line"],
        "zscale": report["ffmpeg"]["zscale"],
        "libx264": report["ffmpeg"]["libx264"],
        "libx265": report["ffmpeg"]["libx265"],
        "libwebp": report["ffmpeg"]["libwebp"],
        "gifski": report["gifski"],
        "blender": report["blender"]["version_line"] or report["blender"]["path"],
        "hosts": report.get("hosts"),
        "missing": gone,
    }, indent=2))
    if gone:
        _die("required tool missing: " + ", ".join(gone) + " (fail, not skip)", 2)


def cmd_ingest(args):
    peer = _load_peer("ingest")
    if peer is None or not hasattr(peer, "main"):
        _die("ingest.py is not in this worktree yet (Codex lane). Refusing to invent a mesh.")
    raise SystemExit(peer.main(args.rest))


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_plan(args):
    bundle = _load_json(args.bundle)
    regions_sha = None
    if args.regions:
        regions_sha = canon.sha256_file(args.regions)
    profiles = tuple(part.strip() for part in args.profiles.split(",") if part.strip())
    resolved = plan_mod.resolve(
        bundle,
        regions_sha256=regions_sha,
        finish_preset=args.finish,
        accents=[part for part in (args.accents or "").split(",") if part],
        profiles=profiles,
        include_dark_turntable=args.dark_turntable,
    )
    canon.atomic_write_bytes(args.out, plan_mod.dumps(resolved))
    print(resolved["plan_key"])


def bundle_mismatch(resolved, bundle_path, regions_path):
    """Return why the supplied bundle/regions do not match the resolved plan, or None.

    The worker consumes the bundle that is passed in, not the plan's record of it, so the
    supplied files themselves must hash to what the plan was resolved from."""
    if not bundle_path or not os.path.isfile(bundle_path):
        return f"bundle not found: {bundle_path!r}"
    try:
        digest = plan_mod._bundle_digest(_load_json(bundle_path))
    except (OSError, ValueError, plan_mod.PlanError) as exc:
        return f"bundle unreadable: {exc}"
    want = resolved.get("bundle") or {}
    if not want.get("npz_sha256") or not digest.get("npz_sha256"):
        return "plan and bundle must both pin a non-empty npz_sha256"
    # the worker always loads mesh.npz next to the bundle, so that exact file is what gets verified
    npz_path = os.path.join(os.path.dirname(os.path.abspath(bundle_path)), "mesh.npz")
    if not os.path.isfile(npz_path):
        return f"mesh npz missing: {npz_path}"
    actual = canon.sha256_file(npz_path)
    if actual != want["npz_sha256"]:
        return f"mesh npz sha256 {actual} != plan {want['npz_sha256']}"
    for key in ("source_sha256", "npz_sha256"):
        if digest.get(key) != want.get(key):
            return f"bundle {key} {digest.get(key)} != plan {want.get(key)}"
    if plan_mod.retired_g3(digest.get("source_sha256")):
        return "bundle names the retired g3 STL"
    want_regions = resolved.get("regions_sha256")
    if want_regions and want_regions != "missing":
        if not regions_path or not os.path.isfile(regions_path):
            return "plan pins regions but no regions file was supplied"
        got = canon.sha256_file(regions_path)
        if got != want_regions:
            return f"regions sha256 {got} != plan {want_regions}"
    return None


def cmd_render(args):
    resolved = _load_json(args.plan)
    if args.execute:
        sha = (resolved.get("bundle") or {}).get("source_sha256")
        try:
            plan_mod.assert_hero_source(sha)
        except plan_mod.PlanError as exc:
            _die(str(exc))
        problem = bundle_mismatch(resolved, args.bundle, args.regions)
        if problem:
            _die("refusing to dispatch: " + problem)
    blender = args.blender or toolchain_mod.find_blender() or ""
    worker = args.worker or os.path.join(_HERE, "blender", "worker.py")
    summary = farm_mod.render_jobs(
        resolved,
        args.dest,
        args.bundle or "",
        args.regions or "",
        blender,
        worker,
        execute=args.execute,
    )
    print(json.dumps({key: summary[key] for key in ("plan_key", "jobs", "pending", "skip", "launched", "queued", "yield")}))
    if args.execute and summary["launched"] == 0 and summary["pending"]:
        _die("execute was set but no shard launched")


def cmd_finish(args):
    peer = _load_peer("finish")
    if peer is None:
        _die("finish.py is not in this worktree yet (Claude lane). Refusing to invent a display transform.")
    fn = getattr(peer, "main", None)
    if fn is None:
        _die("finish.py has no main()")
    raise SystemExit(fn(args.rest))


def cmd_encode(args):
    os.makedirs(args.out, exist_ok=True)
    if args.ramp:
        png = os.path.join(args.out, "gray_ramp.png")
        encode_mod.write_gray_ramp(png)
        encode_mod.encode_h264(
            png, os.path.join(args.out, "gray_ramp.mp4"),
            width=64, height=48, fps=1, preset=args.preset, sequence=False,
        )
        print(os.path.join(args.out, "gray_ramp.mp4"))
        return
    if not args.frames:
        _die("encode needs --frames DIR or --ramp")
    pattern = os.path.join(args.frames, args.pattern)
    encode_mod.encode_h264(
        pattern, os.path.join(args.out, "turntable_1080p_h264.mp4"),
        width=1920, height=1080, fps=30, preset=args.preset, sequence=True,
    )
    encode_mod.encode_h264(
        pattern, os.path.join(args.out, "turntable_2160p_h264.mp4"),
        width=3840, height=2160, fps=30, crf=18, preset=args.preset, sequence=True,
    )
    encode_mod.encode_h265(
        pattern, os.path.join(args.out, "turntable_2160p_h265.mp4"),
        preset=args.preset, sequence=True,
    )
    encode_mod.encode_webp(
        pattern, os.path.join(args.out, "turntable_720p.webp"), sequence=True,
    )
    encode_mod.encode_gif(args.frames, os.path.join(args.out, "turntable_640.gif"))
    print(args.out)


def cmd_qa(args):
    measurements = _load_json(args.measurements) if args.measurements else {}
    report = qa_mod.evaluate(measurements)
    if args.stills:
        sheet = qa_mod.contact_sheet(args.stills, os.path.join(os.path.dirname(args.out) or ".", "contact_sheet.png"))
        report["contact_sheet"] = sheet
    qa_mod.write_qa(args.out, report)
    print(args.out)
    if report["release_blocked"] and args.strict:
        _die("QA release_blocked: " + ",".join(report["release_blocked_reasons"]))


def _parse_file(item):
    # SRC=NAME:ROLE
    src, rest = item.split("=", 1)
    name, role = rest.split(":", 1)
    return {"src": src, "dest_name": name, "role": role}


def cmd_package(args):
    files = [_parse_file(item) for item in args.file]
    git_sha = args.git_sha
    if not git_sha:
        proc = __import__("subprocess").run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=_HERE)
        git_sha = proc.stdout.strip() or "unknown"
    toolchain = {}
    if os.path.isfile(LOCK_PATH):
        toolchain = _load_json(LOCK_PATH)
    try:
        result = package_mod.stage(
            args.root,
            cad_path=args.cad,
            expected_cad_sha256=args.cad_sha,
            mesh_bundle_sha256=args.bundle_sha,
            toolchain=toolchain,
            git_sha=git_sha,
            plan_key=args.plan_key,
            files=files,
            normal_policy=args.normal_policy,
            raw_paths=args.raw or [],
            keep_raw=args.keep_raw,
        )
    except package_mod.PackageError as exc:
        _die(str(exc))
    print(result["manifest"])


def _vertices(bundle_path, npz_path):
    import numpy as np
    path = npz_path or os.path.join(os.path.dirname(os.path.abspath(bundle_path)), "mesh.npz")
    if not os.path.isfile(path):
        return None, path
    return np.load(path)["V"], path


def _start_delivery(dest, png_dir, pipeline_path, *, pattern="turntable_%04d.png", label="deliver"):
    """Encode, then QA and package. Does not upload. Q14 stays pending."""
    script = os.path.join(dest, label + ".sh")
    out = os.path.join(dest, label)
    package_root = os.path.join(dest, label + "_package")
    plan_path = os.path.join(dest, "render_plan.resolved.json")
    text = "\n".join([
        "#!/bin/bash",
        "set -euo pipefail",
        f"mkdir -p {json.dumps(out)} {json.dumps(package_root)}",
        " ".join([
            "nice", "-n", "10", sys.executable, json.dumps(pipeline_path), "encode",
            "--frames", json.dumps(png_dir), "--pattern", pattern,
            "--out", json.dumps(out),
        ]),
        "echo DELIVERY_ENCODE_OK",
        " ".join([
            "nice", "-n", "10", sys.executable, json.dumps(pipeline_path), "post",
            "--dest", json.dumps(dest),
            "--delivery", json.dumps(out),
            "--package", json.dumps(package_root),
            "--plan", json.dumps(plan_path),
            "--png-dir", json.dumps(png_dir),
        ]),
        "echo DELIVERY_POST_OK",
    ]) + "\n"
    canon.atomic_write_text(script, text)
    os.chmod(script, 0o755)
    log = os.path.join(dest, "logs", label + ".log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    subprocess.Popen(
        ["bash", script],
        stdout=open(log, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"delivery started {script}", flush=True)


def _decode_probe(path):
    """Full decode of one video. Returns (probe, decoded) for Q10."""
    proc = subprocess.run(
        [
            encode_mod.FFPROBE, "-v", "error", "-count_frames",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=nb_read_frames,r_frame_rate,avg_frame_rate,color_space,"
            "color_transfer,color_primaries,color_range",
            "-of", "json", path,
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None, False
    data = json.loads(proc.stdout)
    stream = (data.get("streams") or [{}])[0]
    try:
        count = int(stream.get("nb_read_frames") or 0)
    except (TypeError, ValueError):
        count = 0
    return {"video": stream, "frames_decoded": count}, count > 0


def cmd_post(args):
    """Package the encoded turntable and write QA. Release stays blocked on Q14."""
    plan = _load_json(args.plan)
    receipts = []
    if os.path.isdir(args.png_dir):
        for name in sorted(os.listdir(args.png_dir)):
            if name.startswith("turntable_") and name.endswith(".receipt.json"):
                receipts.append(_load_json(os.path.join(args.png_dir, name)))
    seconds = qa_mod.seconds_from_receipts(receipts)
    results = []
    if os.path.isdir(args.png_dir):
        for name in sorted(os.listdir(args.png_dir)):
            if name.endswith(".result.json"):
                results.append(_load_json(os.path.join(args.png_dir, name)))
    signature_log = [{"shot": r.get("shot_id"), **{k: (r.get("signature") or {}).get(k) for k in
                      ("enabled", "asset", "placements_canonical")}} for r in results]
    wall = None
    stamp = os.path.join(args.dest, "started_at.txt")
    if os.path.isfile(stamp):
        try:
            wall = time.time() - float(open(stamp, encoding="utf-8").read().strip())
        except ValueError:
            wall = None
    sizes = {}
    if os.path.isdir(args.delivery):
        for name in os.listdir(args.delivery):
            path = os.path.join(args.delivery, name)
            if os.path.isfile(path):
                sizes[name] = os.path.getsize(path)
    video = os.path.join(args.delivery, "turntable_1080p_h264.mp4")
    probe, decoded = (None, False)
    faststart = None
    if os.path.isfile(video):
        probe, decoded = _decode_probe(video)
        faststart = encode_mod.moov_before_mdat(video)
    files = []
    for name, role in (
        ("turntable_1080p_h264.mp4", "turntable"),
        ("turntable_2160p_h264.mp4", "turntable"),
        ("turntable_2160p_h265.mp4", "turntable"),
        ("turntable_720p.webp", "turntable"),
        ("turntable_640.gif", "turntable"),
    ):
        src = os.path.join(args.delivery, name)
        if os.path.isfile(src):
            files.append({"src": src, "dest_name": name, "role": role})
    if not files:
        _die("post needs at least one encoded turntable file")
    bundle = plan.get("bundle") or {}
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=_HERE)
    toolchain = _load_json(LOCK_PATH) if os.path.isfile(LOCK_PATH) else {}
    try:
        staged = package_mod.stage(
            args.package,
            mesh_bundle_sha256=bundle.get("npz_sha256"),
            toolchain=toolchain,
            git_sha=(git.stdout or "").strip() or "unknown",
            plan_key=plan.get("plan_key"),
            files=files,
            normal_policy=bundle.get("normal_policy"),
            signature=signature_log or None,
        )
    except package_mod.PackageError as exc:
        _die(str(exc))
    manifest = _load_json(staged["manifest"])
    measurements = {
        "seconds": seconds,
        "wall_seconds": wall,
        "framing": qa_mod.framing_rows(plan),
        "sizes": sizes,
        "probe": probe,
        "decoded": decoded,
        "faststart": faststart,
        "frame_count": 240,
        "manifest": manifest,
        "sums_ok": package_mod.verify_sums(args.package),
        "source_sha256": (manifest.get("source_cad") or {}).get("sha256"),
        "signature": qa_mod.signature_rows(results),
    }
    report = qa_mod.evaluate(measurements)
    qa_path = os.path.join(args.dest, "qa.json")
    qa_mod.write_qa(qa_path, report)
    print(json.dumps({
        "qa": qa_path,
        "manifest": staged["manifest"],
        "release_blocked": report["release_blocked"],
        "failed": report["failed"],
        "art_review": report["art_review"],
    }), flush=True)


def cmd_dispatch(args):
    """One shard per free GPU. xbabe1 first, then xbabe3, then xbabe2 if it is under the yield line."""
    bundle = _load_json(args.bundle)
    source_sha = (bundle.get("source") or {}).get("sha256")
    plan_mod.assert_hero_source(source_sha)
    npz_sha = bundle.get("npz_sha256")
    if npz_sha != "062be78fe0828a5f0fc5f2e20e2f4ed07f2d9ffa07741b0645fbb053aa232228":
        _die(f"refusing to dispatch: bundle npz sha is {npz_sha}")
    vertices, npz_path = _vertices(args.bundle, args.npz)
    if vertices is None:
        _die(f"mesh npz is missing: {npz_path}")
    if canon.sha256_file(npz_path) != npz_sha:
        _die("mesh.npz sha256 does not match bundle.json")
    regions_sha = canon.sha256_file(args.regions) if args.regions else None
    resolved = plan_mod.resolve(
        bundle,
        regions_sha256=regions_sha,
        finish_preset=args.finish,
        profiles=("final_4k",),
        include_dark_turntable=True,
        vertices=vertices,
    )
    dest = os.path.abspath(args.dest or farm_mod.scratch_root(resolved["plan_key"]))
    os.makedirs(dest, exist_ok=True)
    canon.atomic_write_bytes(os.path.join(dest, "render_plan.resolved.json"), plan_mod.dumps(resolved))
    stamp = os.path.join(dest, "started_at.txt")
    if not os.path.isfile(stamp):
        canon.atomic_write_text(stamp, f"{time.time():.3f}\n")
    hosts = (
        {"name": "xbabe1", "ssh": "xbabe1"},
        {"name": "xbabe3", "ssh": "xbabe3"},
        {"name": "xbabe2", "ssh": None},
    )
    deadline = datetime.datetime(2026, 10, 13, 16, 0, tzinfo=datetime.timezone.utc).timestamp()
    png_dir = os.path.join(dest, "shots", "turntable", "final_4k")

    def deliver(_dest):
        _start_delivery(_dest, png_dir, os.path.abspath(__file__))

    print(json.dumps({
        "plan_key": resolved["plan_key"],
        "dest": dest,
        "frames": 240,
        "spp_max": resolved["profiles"]["final_4k"]["spp_max"],
        "adaptive_threshold": resolved["profiles"]["final_4k"]["adaptive_threshold"],
        "auto_tile": resolved["profiles"]["final_4k"]["auto_tile"],
        "deadline_utc": "2026-10-13T16:00:00Z",
    }), flush=True)
    farm_mod.supervise(
        resolved,
        dest,
        os.path.abspath(args.bundle),
        os.path.abspath(args.regions) if args.regions else "",
        npz_path,
        args.blender or toolchain_mod.find_blender(),
        args.worker or os.path.join(_HERE, "blender", "worker.py"),
        hosts,
        _HERE,
        os.path.expanduser("~/jarambit_render_scratch/hdri/studio_small_09_4k.hdr"),
        os.path.join(_HERE, "finish.py"),
        shots=("turntable",),
        later_shots=("turntable_dark",),
        deadline_utc=deadline,
        on_primary_done=deliver,
    )
    dark_dir = os.path.join(dest, "shots", "turntable_dark", "final_4k")
    dark_pngs = [
        os.path.join(dark_dir, f"turntable_dark_{index:04d}.png") for index in range(240)
    ]
    if dark_pngs and all(os.path.isfile(path) and os.path.getsize(path) > 32 for path in dark_pngs):
        _start_delivery(
            dest, dark_dir, os.path.abspath(__file__),
            pattern="turntable_dark_%04d.png", label="deliver_dark",
        )


def cmd_all(args):
    """Run the stages whose inputs were passed. Peer gaps fail instead of being skipped."""
    if args.cad and not args.bundle:
        cmd_ingest(argparse.Namespace(rest=["--help"]))
    if not args.bundle or not args.out:
        _die("all needs --bundle and --out")
    plan_path = os.path.join(args.out, "render_plan.resolved.json")
    cmd_plan(argparse.Namespace(
        bundle=args.bundle, regions=args.regions, out=plan_path, finish=args.finish,
        accents=args.accents, profiles=args.profiles, dark_turntable=args.dark_turntable,
    ))
    cmd_render(argparse.Namespace(
        plan=plan_path, dest=os.path.join(args.out, "farm"), bundle=args.bundle,
        regions=args.regions or "", blender=args.blender, worker=args.worker, execute=args.execute,
    ))


def build_parser():
    parser = argparse.ArgumentParser(prog="pipeline.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--require", default="", help="comma list; missing names fail the process")
    doctor.add_argument("--write-lock", action="store_true")
    doctor.add_argument("--lock", default=LOCK_PATH)
    doctor.add_argument("--hosts", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("rest", nargs=argparse.REMAINDER)
    ingest.set_defaults(func=cmd_ingest)

    plan = sub.add_parser("plan")
    plan.add_argument("--bundle", required=True)
    plan.add_argument("--regions")
    plan.add_argument("--out", required=True)
    plan.add_argument("--finish", default="finish_ti64")
    plan.add_argument("--accents", default="")
    plan.add_argument("--profiles", default="final_4k,native_1080")
    plan.add_argument("--dark-turntable", action="store_true")
    plan.set_defaults(func=cmd_plan)

    render = sub.add_parser("render")
    render.add_argument("--plan", required=True)
    render.add_argument("--dest", required=True)
    render.add_argument("--bundle", default="")
    render.add_argument("--regions", default="")
    render.add_argument("--blender")
    render.add_argument("--worker")
    render.add_argument("--execute", action="store_true")
    render.set_defaults(func=cmd_render)

    dispatch = sub.add_parser("dispatch")
    dispatch.add_argument("--bundle", required=True)
    dispatch.add_argument("--regions", required=True)
    dispatch.add_argument("--npz")
    dispatch.add_argument("--dest")
    dispatch.add_argument("--finish", default="finish_ti64")
    dispatch.add_argument("--blender")
    dispatch.add_argument("--worker")
    dispatch.set_defaults(func=cmd_dispatch)

    finish = sub.add_parser("finish")
    finish.add_argument("rest", nargs=argparse.REMAINDER)
    finish.set_defaults(func=cmd_finish)

    enc = sub.add_parser("encode")
    enc.add_argument("--frames")
    enc.add_argument("--pattern", default="frame_%04d.png")
    enc.add_argument("--out", required=True)
    enc.add_argument("--preset", default="slow")
    enc.add_argument("--ramp", action="store_true")
    enc.set_defaults(func=cmd_encode)

    qa = sub.add_parser("qa")
    qa.add_argument("--measurements")
    qa.add_argument("--out", required=True)
    qa.add_argument("--stills", nargs="*")
    qa.add_argument("--strict", action="store_true")
    qa.set_defaults(func=cmd_qa)

    pkg = sub.add_parser("package")
    pkg.add_argument("--root", required=True)
    pkg.add_argument("--cad", default=plan_mod.HERO_STEP_PATH,
                     help="defaults to the SWITCHBACK Rev C.9.3 STEP")
    pkg.add_argument("--cad-sha", default=plan_mod.HERO_STEP_SHA256,
                     help="defaults to the C.9.3 STEP sha256")
    pkg.add_argument("--bundle-sha", required=True)
    pkg.add_argument("--plan-key", required=True)
    pkg.add_argument("--file", action="append", required=True)
    pkg.add_argument("--git-sha")
    pkg.add_argument("--normal-policy")
    pkg.add_argument("--raw", action="append")
    pkg.add_argument("--keep-raw", action="store_true")
    pkg.set_defaults(func=cmd_package)

    post = sub.add_parser("post")
    post.add_argument("--dest", required=True)
    post.add_argument("--delivery", required=True)
    post.add_argument("--package", required=True)
    post.add_argument("--plan", required=True)
    post.add_argument("--png-dir", required=True)
    post.set_defaults(func=cmd_post)

    entire = sub.add_parser("all")
    entire.add_argument("--bundle")
    entire.add_argument("--regions")
    entire.add_argument("--cad")
    entire.add_argument("--out")
    entire.add_argument("--finish", default="finish_ti64")
    entire.add_argument("--accents", default="")
    entire.add_argument("--profiles", default="final_4k,native_1080")
    entire.add_argument("--dark-turntable", action="store_true")
    entire.add_argument("--execute", action="store_true")
    entire.add_argument("--blender")
    entire.add_argument("--worker")
    entire.set_defaults(func=cmd_all)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
