#!/usr/bin/env python3
"""PR-0.31.3: T1 (search) -> T2 (certification) factors with residual sigma, plus RS-karambit-v2 pass counts.
Input: docs/calibration/t1_t2.csv (from `jarambit calib-t1t2`). Output: docs/calibration/t1_t2.json (stdout with --check compares)."""
import csv, json, statistics as st, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
CASES = ["lat_rob", "ring_rob", "twist_joint", "pry20"]
SIGMA_MAX = 0.07

def build(rows):
    out = {"n_designs": len(rows), "sigma_max": SIGMA_MAX, "cases": {}}
    for c in CASES:
        q = [float(r["t2_" + c]) / float(r["t1_" + c]) for r in rows]
        f = st.median(q); res = [x / f - 1.0 for x in q]
        out["cases"][c] = {"factor_t2_over_t1": round(f, 5), "sigma": round(st.pstdev(res), 5), "max_abs_residual": round(max(map(abs, res)), 5),
                           "pass_sigma": st.pstdev(res) <= SIGMA_MAX}
    hm = {}
    for c in ["hm_twist_sf", "hm_tip_inplane_sf", "hm_spine_sf", "hm_ringback_sf", "fat_sf", "ring_bearing_w_mm", "ring_band_mm", "mass_g", "seq_ratio"]:
        v = [float(r[c]) for r in rows]; hm[c] = {"min": round(min(v), 4), "median": round(st.median(v), 4), "max": round(max(v), 4)}
    thr = {"hm_twist_sf": 1, "hm_tip_inplane_sf": 1, "hm_spine_sf": 1, "hm_ringback_sf": 1, "fat_sf": 1, "ring_bearing_w_mm": 10, "seq_ratio": 1.2}
    for c, t in thr.items(): hm[c]["n_pass"] = sum(float(r[c]) >= t for r in rows)
    hm["n_pass_human_max_all"] = sum(all(float(r[c]) >= thr[c] for c in ["hm_twist_sf", "hm_tip_inplane_sf", "hm_spine_sf", "hm_ringback_sf", "ring_bearing_w_mm"]) for r in rows)
    out["rs_v2"] = hm
    return out

def main():
    rows = list(csv.DictReader(open(ROOT / "docs/calibration/t1_t2.csv")))
    out = json.dumps(build(rows), indent=1) + "\n"
    p = ROOT / "docs/calibration/t1_t2.json"
    if "--check" in sys.argv:
        if p.read_text() != out: sys.exit("t1_t2.json stale: run python3 ops/calibration/t1_t2.py")
        return
    p.write_text(out); print(out)

if __name__ == "__main__":
    main()
