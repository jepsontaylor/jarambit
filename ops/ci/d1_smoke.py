#!/usr/bin/env python3
"""CI D1 smoke: check crescent-d1 output for the wave14_c03 reference against the OWNER-LOCK D1 gates.

Pins (1) the locked thresholds in the report header and (2) the known wave14_c03 verdict:
C.6 aesthetic PASS, hard gates ok, blade >= 3.375 in on all three, PASS @828 joint (cert ~280 N, strict ~270 N >= 260),
twist body PASS but tip submodel < 1 -> twist floor FAIL -> NOT promote-eligible.
It also recomputes promote-eligibility from the CSV columns with the locked thresholds and requires agreement.
Usage: d1_smoke.py <out_dir>
"""
import csv, sys, pathlib
out = pathlib.Path(sys.argv[1])
md = (out / "d1_rescreen.md").read_text()
errs = []
for s in ("828 MPa", "1.82 N*m", "hiker 180 / hunter 260 / ring 1500 N", "blade >= 3.375 in on all three", "C.6 aesthetic", "body AND tip submodel"):
    if s not in md: errs.append(f"report header missing locked gate text: {s!r}")
rows = {r["design"]: r for r in csv.DictReader(open(out / "d1_rescreen.csv"))}
r = rows.get("w14c03")
if r is None: sys.exit("FAIL: w14c03 row missing")
f = lambda k: float(r[k]); b = lambda k: r[k].strip().lower() == "true"
def want(cond, msg):
    if not cond: errs.append(msg)
want(b("aes_pass"), "w14c03 C.6 aesthetic should PASS")
want(b("gates_ok"), "w14c03 hard gates should be ok")
want(f("blade_min_in") >= 3.375, f"blade_min_in {f('blade_min_in')} < 3.375")
want(abs(f("joint_lat_cert") - 280.2) <= 5.0, f"joint_lat_cert drifted: {f('joint_lat_cert')} (ref 280.2 +/- 5)")
want(abs(f("strict_joint_lat_0p0625") - 269.8) <= 5.0, f"strict lat drifted: {f('strict_joint_lat_0p0625')} (ref 269.8 +/- 5)")
want(b("pass_828_joint"), "w14c03 should PASS @828 joint")
want(f("joint_lat_cert") >= 260 and f("strict_joint_lat_0p0625") >= 260 and f("joint_ring_cert") >= 1500, "floors 260/1500 not met")
want(f("twist_body_sf_1p82") >= 1.0, "twist body SF should be >= 1")
want(f("twist_tipzone_sf_strict") < 1.0, "twist tip submodel SF should be < 1 (known FAIL); a pass here means the gate moved")
want(not b("twist_floor_ok_body_and_tipsub"), "twist floor must FAIL (tip submodel < 1.82 N*m)")
want(not b("promote_eligible_pending_aesthetic_signoff"), "w14c03 must NOT be promote-eligible")
for name, row in rows.items():
    g = lambda k: float(row[k]); t = lambda k: row[k].strip().lower() == "true"
    recomputed = (t("aes_pass") and t("gates_ok") and t("pass_828_joint") and g("strict_joint_lat_0p0625") >= 260 and g("seq_ratio") >= 1.2
                  and g("twist_body_sf_1p82") >= 1.0 and g("twist_tipzone_sf_strict") >= 1.0 and 74.0 <= g("mass_g") <= 77.0 and g("blade_min_in") >= 3.375)
    if recomputed != t("promote_eligible_pending_aesthetic_signoff"):
        errs.append(f"{name}: promote_eligible {row['promote_eligible_pending_aesthetic_signoff']} != locked-gate recompute {recomputed}")
if errs:
    print("D1 SMOKE FAIL"); [print(" -", e) for e in errs]; sys.exit(1)
print(f"D1 SMOKE PASS: w14c03 cert {f('joint_lat_cert'):.1f} N strict {f('strict_joint_lat_0p0625'):.1f} N ring {f('joint_ring_cert'):.0f} N, "
      f"blade_min {f('blade_min_in'):.3f} in, twist body {f('twist_body_sf_1p82'):.2f} tip-sub {f('twist_tipzone_sf_strict'):.2f} -> promote=false (as locked)")
