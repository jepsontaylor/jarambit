#!/usr/bin/env python3
"""PR-0.31.1 accounting runner for bench/fixed_1k (wall, CPU-s, peak RSS, failures)."""
from __future__ import annotations
import argparse, csv, json, os, resource, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def peak_rss_kb() -> int:
    return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workload", default=str(ROOT / "bench/fixed_1k"))
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--bin", default=str(ROOT / "target/release/jarambit"))
    ap.add_argument("--mode", choices=["t1", "t1c"], default="t1")
    ap.add_argument("--out", default=str(ROOT / "bench/fixed_1k/results"))
    args = ap.parse_args()
    wl = Path(args.workload)
    genomes = wl / "genomes.csv"
    if not genomes.exists():
        print(f"missing {genomes}; generate/freeze genomes first", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for rep in range(1, args.reps + 1):
        env = os.environ.copy()
        env["JARAMBIT_BENCH_MODE"] = args.mode
        env["JARAMBIT_BENCH_GENOMES"] = str(genomes)
        t0 = time.perf_counter()
        # Placeholder until jarambit gains `bench-fixed` subcommand: time a no-op marker.
        cmd = [args.bin, "--help"]
        p = subprocess.run(cmd, env=env, capture_output=True, text=True)
        wall = time.perf_counter() - t0
        rss = peak_rss_kb()
        rows.append({
            "rep": rep,
            "mode": args.mode,
            "wall_s": round(wall, 4),
            "peak_rss_kb": rss,
            "returncode": p.returncode,
            "failures": 0 if p.returncode == 0 else 1,
            "note": "stub until jarambit bench-fixed lands",
        })
        print(json.dumps(rows[-1]))
    (out / f"{args.mode}_reps.json").write_text(json.dumps(rows, indent=2) + "\n")
    with (out / f"{args.mode}_reps.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
