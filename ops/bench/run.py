#!/usr/bin/env python3
"""Run the frozen bench (bench/fixed_1k) for T1 search and T1c cert, REPS reps each; write one JSON record.

usage: run.py [--bin target/release/jarambit] [--search-n 200] [--cert-n 40] [--threads 8] [--reps 3] [--out FILE]
Checksums must be identical across reps (determinism); the run fails otherwise.
"""
import argparse, hashlib, json, platform, resource, socket, statistics, subprocess, sys, os

def one(b, tier, n, th):
    p = subprocess.run([b, "bench-fixed", "--tier", tier, "--n", str(n), "--threads", str(th)], capture_output=True, text=True)
    if p.returncode != 0: sys.exit(f"bench-fixed {tier} failed: {p.stderr[-500:]}")
    r = json.loads(p.stdout.strip().splitlines()[-1])
    r["peak_rss_kb_children"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    r["failures"] = r["n"] - r["fem_evaluated"]
    return r

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default="target/release/jarambit"); ap.add_argument("--search-n", type=int, default=200)
    ap.add_argument("--cert-n", type=int, default=40); ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--reps", type=int, default=3); ap.add_argument("--out")
    a = ap.parse_args(argv)
    sha = hashlib.sha256(open("bench/fixed_1k/genomes.csv", "rb").read()).hexdigest()
    want = open("bench/fixed_1k/SHA256SUMS").read().split()[0]
    if sha != want: sys.exit(f"workload sha mismatch {sha} != {want}")
    rec = {"workload": "bench/fixed_1k", "workload_sha256": sha, "host": socket.gethostname(), "cpu": platform.processor() or platform.machine(),
           "nproc": os.cpu_count(), "git": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(), "tiers": {}}
    for tier, n in (("search", a.search_n), ("cert", a.cert_n)):
        reps = [one(a.bin, tier, n, a.threads) for _ in range(a.reps)]
        if len({round(r["checksum"], 6) for r in reps}) != 1: sys.exit(f"{tier}: nondeterministic checksum")
        m = [r["core_s_per_design_mean"] for r in reps]
        rec["tiers"][tier] = {"n": n, "threads": a.threads, "reps": reps, "core_s_per_design_median": statistics.median(m),
                              "core_s_per_design_spread": max(m) - min(m)}
    s = json.dumps(rec, indent=1)
    if a.out: open(a.out, "w").write(s + "\n")
    print(s)

if __name__ == "__main__":
    main()
