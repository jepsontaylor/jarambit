"""End-to-end v1: knife STEP/STL -> interface -> path search -> sheath CAD -> draw-force (analytic + plate FEM) -> MC -> metrics.

usage: python -m sheath.run --step K.step --stl K.stl --out OUT [--workers 32]
Evidence level of every force here: analytic_proxy / uncalibrated_fea. NOT a measurement.
"""
import argparse, json, math, os, sys, time
from dataclasses import asdict, replace
from multiprocessing import Pool
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sheath import model as M
from sheath import generate as G
from sheath.ingest import ingest, thickness_at
from shapely.geometry import Polygon, Point, LineString

_K = None
_S = None


def _init(Kc, S):
    global _K, _S
    _K = Polygon(Kc); _S = np.asarray(S)


def _try(p):
    try:
        g = G.build2d(_K, p, ds=2.0)
        if not g["path_feasible"]:
            return (p, False, math.inf, None)
        D = g["D"]
        ins = [q for q in _S if D.contains(Point(q))]
        depth = min(-(np.asarray(q) - g["m"]) @ g["n"] for q in ins) if ins else -1.0
        ok = len(ins) == len(_S) and depth >= 6.0
        return (p, ok, g["outline"].area, float(depth))
    except Exception as e:
        return (p, False, math.inf, None)


def search_path(K, base, workers, S):
    cands = []
    for cx in np.arange(60, 181, 10.0):
        for cy in np.arange(-10, 121, 10.0):
            for sg in (1, -1):
                cands.append(replace(base, path="rot", centre=(float(cx), float(cy)), sweep_max=150.0 * sg))
    for d in np.arange(120, 241, 10.0):
        cands.append(replace(base, path="trans", direction_deg=float(d), sweep_max=200.0))
    with Pool(workers, initializer=_init, initargs=(list(K.exterior.coords), S[::4])) as pool:
        res = pool.map(_try, cands, chunksize=4)
    ok = sorted([r for r in res if r[1]], key=lambda r: r[2])
    return ok, len(cands)


def track_profile(mesh, p, g, bump_xy, t_gap_knife, ds=0.5):
    """Knife points that pass under the bump during draw: q(s) = T(s)^-1(bump). Returns s, arc(mm at grip ref), t(s)."""
    sg = 1.0 if p.sweep_max > 0 else -1.0
    S = np.arange(0, (g["left_at"] or 0) + ds, ds)
    pts = []
    for s in S:
        if p.path == "rot":
            c = np.array(p.centre); a = -math.radians(sg * s)
            r = np.array(bump_xy) - c
            pts.append(c + [r[0] * math.cos(a) - r[1] * math.sin(a), r[0] * math.sin(a) + r[1] * math.cos(a)])
        else:
            a = math.radians(p.direction_deg)
            pts.append(np.array(bump_xy) - sg * s * np.array([math.cos(a), math.sin(a)]))
    pts = np.array(pts)
    t = thickness_at(mesh, pts)
    # displacement of the grip reference (ring centre) per unit s
    if p.path == "rot":
        R = np.linalg.norm(np.array([0.0, 0.0]) - np.array(p.centre))
        arc = S * math.radians(1) * R
    else:
        arc = S
    return S, arc, pts, t


def force_curve(t_track, arc, k, p, mat, t_gap_knife, mu=None):
    """Quasi-static axial force at grip reference along the draw (both panels have a bump)."""
    mu = mat.mu_steel if mu is None else mu
    i = p.detent_undercut - p.c_face - (t_gap_knife - t_track) / 2.0
    i = np.where(t_track <= 1e-6, -1.0, i)         # over the hole: bump free
    P = k * np.clip(i, 0, None)                      # per side
    di = np.gradient(i, arc)                         # interference slope seen by the bump
    F = np.zeros_like(arc)
    for j in range(len(arc)):
        if P[j] <= 0: continue
        ang = math.degrees(math.atan(max(di[j], 0.0)))  # climbing (resisting) ramp
        F[j] = 2 * (M.snap_axial(P[j], mu, min(ang, p.detent_a_out)) if di[j] > 1e-6 else mu * P[j])
    return F, i, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True); ap.add_argument("--stl", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=32); ap.add_argument("--mc", type=int, default=20000)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    iface, mesh, Kp = ingest(a.step, a.stl)
    json.dump(iface, open(os.path.join(a.out, "knife_interface.json"), "w"), indent=1)
    K = Polygon(Kp.exterior)
    base = G.SheathParams()
    mat = M.MATERIALS[base.material]
    sharp_pts = np.vstack([np.array(r["pts"]) for r in iface["sharp_runs"]])
    ranked, ncand = search_path(K, base, a.workers, sharp_pts)
    if not ranked:
        json.dump({"status": "path_infeasible", "n_candidates": ncand}, open(os.path.join(a.out, "metrics.json"), "w")); return
    p = ranked[0][0]
    g = G.build2d(K, p, ds=1.0)
    sharp_pts = np.vstack([np.array(r["pts"]) for r in iface["sharp_runs"]])
    min_clear, rim_min = G.edge_margins(g, sharp_pts, p)
    nvec, mvec = g["n"], g["m"]
    seated_sharp = [q for q in sharp_pts if g["D"].contains(Point(q))]
    edge_mouth_depth = float(min(-(np.asarray(q) - mvec) @ nvec for q in seated_sharp)) if seated_sharp else -1.0
    uncovered_sharp_mm = 0.5 * (len(sharp_pts) - len(seated_sharp))
    # covered-region knife thickness (gap sizing)
    C = g["cavity"]
    xs = np.random.default_rng(0).uniform(np.array(C.bounds)[:2], np.array(C.bounds)[2:], size=(6000, 2))
    seated = Polygon(Kp.exterior).intersection(g["D"])
    pin = np.array([seated.contains(Point(q)) for q in xs])
    tcov = thickness_at(mesh, xs[pin])
    t_gap_knife = float(np.max(tcov))
    m_g, vol = G.mass_g(g, p, t_gap_knife, mat.rho_g_cm3)
    # retention feature: smallest closed hole inside the covered region
    holes = [h for h in iface["holes"] if seated.contains(Point(h["centroid"])) and h is not iface["ring"]]
    holes = [h for h in holes if h["eq_radius_mm"] < 6]
    det = min(holes, key=lambda h: h["area_mm2"]) if holes else None
    res = {"schema": "jarambit.sheath.metrics.v1", "evidence_level": "analytic_proxy+uncalibrated_fea",
           "knife": iface["source"], "knife_mass_g_brep": iface["brep"].get("mass_g_ti64"),
           "params": asdict(p), "material": asdict(mat), "n_path_candidates": ncand, "n_feasible": len(ranked),
           "top_paths": [{"path": r[0].path, "centre": r[0].centre, "dir": r[0].direction_deg, "sweep": r[0].sweep_max,
                          "outline_mm2": r[2], "edge_mouth_depth_mm": r[3]} for r in ranked[:8]],
           "path_feasible": g["path_feasible"], "left_at": g["left_at"], "mouth_len_mm": g["mouth_len_mm"], "mouth_note": "length of cavity edge on the mouth line",
           "outline_mm2": g["outline"].area, "cavity_mm2": C.area, "t_gap_knife_mm": t_gap_knife,
           "min_edge_clearance_mm": min_clear, "rim_min_mm": rim_min,
           "edge_mouth_depth_mm": edge_mouth_depth, "uncovered_sharp_mm": uncovered_sharp_mm,
           "shell_mass_g": m_g, "mass_g": m_g + p.mount_mass_g, "eps_allow": mat.eps_allow}
    if det is None:
        res["retention"] = "NOT_EVALUATED: no admissible closed hole in covered region"
    else:
        from sheath.fem_plate import plate_stiffness
        from shapely.geometry import box as sbox
        bump = tuple(det["centroid"])
        r0 = min(2.0, 0.6 * det["eq_radius_mm"])
        n = g["n"]; mpt = g["m"]
        panel = C if C.geom_type == "Polygon" else max(C.geoms, key=lambda x: x.area)
        hr = det["eq_radius_mm"]
        ring_pts = np.array([[bump[0] + (hr + 1.0) * math.cos(t), bump[1] + (hr + 1.0) * math.sin(t)] for t in np.linspace(0, 2 * math.pi, 24, endpoint=False)])
        t_local = float(np.median(thickness_at(mesh, ring_pts)))
        a_eq = panel.exterior.distance(Point(bump))
        # --- solid-panel stiffness (FEM ladder) — reported for the record (too stiff for a tunable click)
        ladder = []
        for ma in (2.0, 1.0, 0.5):
            kp, w, nd, _ = plate_stiffness(panel, bump, mat.E_mpa, p.wall, r0=r0, free_line=(mpt, n), max_area=ma)
            ladder.append({"max_area": ma, "k_n_mm": kp, "ndof": int(nd)})
        res["solid_panel"] = {"k_ladder": ladder, "k_analytic_clamped_circle_n_mm": M.clamped_circ_plate_k(mat.E_mpa, p.wall, a_eq), "a_eq_mm": a_eq}

        def tab_k_fem(q, ma=0.15):
            rect = sbox(0, 0, q.tab_L, q.tab_b)
            kf, _, nd, _ = plate_stiffness(rect, (q.tab_L - min(2.0, q.tab_b / 3), q.tab_b / 2), mat.E_mpa, q.wall,
                                           r0=min(1.5, q.tab_b / 4), max_area=ma, clamp_fn=lambda x, y: x < 1e-6)
            return kf, nd

        rng = np.random.default_rng(42); N = a.mc; W = M.WINDOW
        Tf = rng.choice([mat.E_temp[0], 1.0, mat.E_temp[1]], size=N, p=[0.2, 0.6, 0.2])
        dw = rng.normal(0, 0.1, N); du = rng.normal(0, 0.05, N); dc = rng.normal(0, 0.05, N)
        tk = rng.normal(0, 0.03, N); mu_s = rng.uniform(0.20, 0.45, N); wear = rng.uniform(0.0, 0.10, N)
        dL = rng.normal(0, 0.1, N)
        new = (Tf == 1.0) & (wear < 0.02)

        def evaluate(q, k=None):
            if k is None:
                k = M.tab_k(mat.E_mpa, q.tab_b, q.wall, q.tab_L - 2.0) if q.retention == "tab" else ladder[-1]["k_n_mm"]
            i_face = q.detent_undercut - q.c_face - (t_gap_knife - t_local) / 2
            d = M.detent_forces(k, max(i_face, 0), mat.mu_steel, q.detent_a_in, q.detent_a_out)
            eps = M.tab_strain(q.wall, q.tab_L - 2.0, max(i_face, 0)) if q.retention == "tab" else math.nan
            kk = k * Tf * ((q.wall + dw) / q.wall) ** 3 * ((q.tab_L / (q.tab_L + dL)) ** 3 if q.retention == "tab" else 1)
            ii = np.clip(q.detent_undercut + du - (q.c_face + dc) - (t_gap_knife - t_local) / 2 + tk / 2 - wear, 0, None)
            ta = math.tan(math.radians(q.detent_a_out))
            Fmc = 2 * kk * ii * (mu_s + ta) / np.clip(1 - mu_s * ta, 1e-6, None)
            return {"k": k, "i_face": i_face, "P": d.P_n, "draw": 2 * d.draw_n, "insert": 2 * d.insert_n, "eps": eps,
                    "p05": float(np.percentile(Fmc, 5)), "p50": float(np.median(Fmc)), "p95": float(np.percentile(Fmc, 95)),
                    "p_life": float(np.mean((Fmc > W.lo_life) & (Fmc < W.hi_life))),
                    "p_new": float(np.mean((Fmc[new] > W.lo_new) & (Fmc[new] < W.hi_new)))}

        # --- retention design search (cheap, analytic k): tab length, undercut, return angle, wall
        best = None; nsearch = 0
        import itertools
        for wall, L, und, aout, tb in itertools.product((1.0, 1.2, 1.4, 1.6, 1.8, 2.0), np.arange(6.0, 22.01, 1.0),
                                                        np.arange(0.30, 1.301, 0.05), (20.0, 25.0, 30.0, 35.0, 40.0, 45.0), (5.0, 7.0, 9.0)):
                        q = replace(p, wall=wall, tab_L=float(L), detent_undercut=float(und), detent_a_out=aout, tab_b=tb)
                        e = evaluate(q); nsearch += 1
                        mg = G.mass_g(g, q, t_gap_knife, mat.rho_g_cm3)[0] + q.mount_mass_g
                        f = M.fitness({"edge_mouth_depth_mm": edge_mouth_depth, "uncovered_sharp_mm": uncovered_sharp_mm, "path_feasible": g["path_feasible"], "min_edge_clearance_mm": min_clear, "insert_n": e["insert"],
                                       "strain_est": e["eps"], "eps_allow": mat.eps_allow, "rim_min_mm": rim_min,
                                       "p_in_life_window": e["p_life"], "draw_n": e["draw"], "mass_g": mg, "p_in_new_window": e["p_new"]})
                        key = (f["score"], f["raw"])
                        if best is None or key > best[0]: best = (key, q, e, mg)
        p = best[1]
        kf, ndf = tab_k_fem(p); kf2, ndf2 = tab_k_fem(p, 0.05)
        e = evaluate(p)
        m_g = best[3] - p.mount_mass_g
        res.update({"params": asdict(p), "shell_mass_g": m_g, "mass_g": best[3], "retention_search_n": nsearch})
        S, arc, pts, tt = track_profile(mesh, p, g, bump, t_gap_knife)
        F, inter, P = force_curve(tt + (t_gap_knife - t_local) * 0, arc, e["k"], p, mat, t_gap_knife)
        sh = LineString(sharp_pts) if len(sharp_pts) > 1 else None
        sharp_hit = any(ii > 0 and sh.distance(Point(q)) < r0 for q, ii in zip(pts, inter)) if sh is not None else False
        res.update({
            "retention_feature": {"type": "twin U-slot click-tabs, bumps into closed guard hole (both faces)", "hole": det,
                                  "review_required": True, "bump_r0_mm": r0, "t_local_mm": t_local},
            "k_tab_analytic_n_mm": e["k"], "k_tab_fem_n_mm": [kf, kf2], "k_tab_fem_ndof": [int(ndf), int(ndf2)],
            "k_tab_fem_vs_analytic": kf2 / e["k"] - 1,
            "interference_per_side_mm": e["i_face"], "P_per_side_n": e["P"], "insert_n": e["insert"], "draw_n": e["draw"],
            "draw_n_fem_k": e["draw"] * kf2 / e["k"],
            "curve_peak_n": float(F.max()) if len(F) else 0.0, "draw_work_j": float(np.trapezoid(F, arc) / 1000.0),
            "strain_est": e["eps"], "sharp_edge_over_detent": bool(sharp_hit),
            "retention_sf": {kn: M.inertial_sf(e["draw"], iface["brep"].get("mass_g_ti64", 66.8), acc) for kn, acc in M.RETENTION_CASES.items()},
            "retention_sf_p05": {kn: M.inertial_sf(e["p05"], iface["brep"].get("mass_g_ti64", 66.8), acc) for kn, acc in M.RETENTION_CASES.items()},
            "mc": {"n": N, "p05": e["p05"], "p50": e["p50"], "p95": e["p95"], "p_in_life_window": e["p_life"], "p_in_new_window": e["p_new"],
                   "assumptions": "wall sd0.1, undercut sd0.05, c_face sd0.05, knife t sd0.03, tab L sd0.1, mu U(0.20,0.45), wear U(0,0.10)mm, E x{1.25@-20C,1,0.70@+60C} p{.2,.6,.2}"},
        })
        res["p_in_life_window"] = e["p_life"]; res["p_in_new_window"] = e["p_new"]
        np.savetxt(os.path.join(a.out, "draw_curve.csv"), np.c_[arc, F, inter, tt], delimiter=",",
                   header="grip_disp_mm,axial_force_n,interference_per_side_mm,knife_t_under_bump_mm", comments="")
    res["fitness"] = M.fitness(res)
    res["verdicts"] = {"geometry": "PASS" if g["path_feasible"] else "FAIL",
                       "withdrawal_clearance": "PASS" if min_clear >= 0.3 else "FAIL",
                       "retention_force": "PREDICTED (analytic_proxy+uncalibrated_fea) — not a measurement",
                       "puncture": "NOT_EVALUATED", "mount": "NOT_EVALUATED", "physical_validation": "NOT_EVALUATED"}
    # CAD export
    try:
        import cadquery as cq
        sol = G.solid3d_full(g, p, t_gap_knife, tuple(det['centroid']) if det else None)
        cq.exporters.export(sol, os.path.join(a.out, "sheath_v1.step"))
        cq.exporters.export(sol, os.path.join(a.out, "sheath_v1.stl"), tolerance=0.05)
        res["cad_volume_mm3"] = sol.val().Volume(); res["cad_mass_g"] = sol.val().Volume() * mat.rho_g_cm3 * 1e-3
    except Exception as e:
        res["cad_export"] = "failed: %r" % e
    res["elapsed_s"] = time.time() - t0
    json.dump(res, open(os.path.join(a.out, "metrics.json"), "w"), indent=1, default=float)
    # figure
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(15, 6))
        for geom, kw in ((g["outline"], dict(fc="#3a6", alpha=.35)), (C, dict(fc="w", alpha=1))):
            for gg in getattr(geom, "geoms", [geom]):
                ax[0].fill(*gg.exterior.xy, ec="k", **kw)
        ax[0].plot(*Kp.exterior.xy, "k", lw=.8)
        for r in Kp.interiors: ax[0].plot(*r.xy, "k", lw=.6)
        ax[0].plot(sharp_pts[:, 0], sharp_pts[:, 1], "r.", ms=1.5, label="sharpened edge (auto)")
        if det:
            ax[0].plot(*det["centroid"], "b*", ms=12, label="detent")
            for q in G.tab_slot_polys(g, p, det["centroid"]): ax[0].fill(*q.exterior.xy, fc="k")
        if p.path == "rot": ax[0].plot(*p.centre, "m+", ms=12, label="draw-rotation centre")
        ax[0].set_aspect("equal"); ax[0].legend(loc="lower left"); ax[0].set_title("SHEATH v1 planform (green) / cavity (white) / knife")
        if det:
            ax[1].plot(arc, F); ax[1].axhspan(W.lo_new, W.hi_new, color="g", alpha=.15, label="new window")
            ax[1].set_xlabel("grip-reference displacement (mm)"); ax[1].set_ylabel("axial draw force (N)")
            ax[1].set_title("quasi-static draw curve (analytic_proxy + plate FEA)"); ax[1].legend()
        fig.tight_layout(); fig.savefig(os.path.join(a.out, "sheath_v1.png"), dpi=120)
    except Exception as e:
        print("plot failed", e)
    print(json.dumps({k: res.get(k) for k in ("path_feasible", "mass_g", "draw_n", "insert_n", "k_panel_n_mm", "mc", "fitness")}, indent=1, default=float))


if __name__ == "__main__":
    main()
