"""End-to-end v1: knife STEP/STL -> interface -> path search -> sheath CAD -> draw-force (analytic + plate FEM) -> MC -> metrics.

usage: python -m sheath.run --step K.step --stl K.stl --out OUT [--workers N]  (default: safe_workers(); clamped by free memory)
Evidence level of every force here: analytic_proxy / uncalibrated_fea. NOT a measurement.
"""
import argparse, json, math, os, sys, time
from dataclasses import asdict, replace
from multiprocessing import Pool
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sheath import model as M
from sheath import generate as G
from sheath.ingest import thickness_at
from sheath.interface import from_step, validate
from sheath import strength as SS
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


PER_WORKER_GB = float(os.environ.get("SHEATH_PER_WORKER_GB", "3.0"))  # measured: 32 workers -> ~92 GB RSS (~2.6-2.9 GB each, fork COW of ~10 GB parent)


def _avail_gb():
    try:
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemAvailable:"):
                return int(ln.split()[1]) / 1048576.0
    except OSError:
        pass
    return None


def _cgroup_limit_gb():
    """Memory headroom left in our cgroup (e.g. memcap / systemd-run MemoryMax), if any."""
    try:
        cg = open("/proc/self/cgroup").read().strip().split("::")[-1]
        base = "/sys/fs/cgroup" + cg
        mx = open(base + "/memory.max").read().strip()
        if mx == "max":
            return None
        return (int(mx) - int(open(base + "/memory.current").read())) / 2**30
    except (OSError, ValueError):
        return None


def safe_workers(requested=None, per_worker_gb=PER_WORKER_GB):
    """min(requested, cores/4, free_GB*0.5/per_worker_GB), >= 1. Warns on stderr when clamped."""
    cores = os.cpu_count() or 4
    caps = {"cores/4": max(1, cores // 4)}
    free = _avail_gb()
    if free is not None:
        caps["mem_available"] = max(1, int(free * 0.5 / per_worker_gb))
    cg = _cgroup_limit_gb()
    if cg is not None:
        caps["cgroup_headroom"] = max(1, int(cg * 0.8 / per_worker_gb))
    n = min(caps.values())
    if requested is not None and requested < n:
        return requested
    if requested is not None and requested > n:
        print(f"[sheath.run] WARNING: --workers {requested} clamped to {n} ({caps}, free={free and round(free,1)} GB, "
              f"{per_worker_gb} GB/worker)", file=sys.stderr, flush=True)
    return n


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


def _stage(name):
    import resource
    print("[stage] %s t=%.0fs maxrss=%.1fGB" % (name, time.time() - _T0, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6), file=sys.stderr, flush=True)


_T0 = time.time()


def _ladder_child(q, args):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (8 << 30, 8 << 30))
    from sheath.fem_plate import plate_stiffness
    panel, bump, E, wall, r0, fl = args
    out = []
    for ma in (2.0, 1.0, 0.5):
        kp, w, nd, _ = plate_stiffness(panel, bump, E, wall, r0=r0, free_line=fl, max_area=ma)
        out.append({"max_area": ma, "k_n_mm": kp, "ndof": int(nd)})
    q.put(out)


def _guarded_ladder(*args, timeout=240):
    """Solid-panel plate ladder (record only) in a child with an 8 GB address-space cap and a timeout: Triangle quality
    refinement ran away on the C.9.3 c_edge-1.3 cavity (>90 GB). On failure -> null + INCOMPLETE, never a number."""
    import multiprocessing as mp
    q = mp.Queue(); pr = mp.Process(target=_ladder_child, args=(q, args)); pr.start(); pr.join(timeout)
    if pr.is_alive():
        pr.kill(); pr.join(); return None
    try:
        return q.get(timeout=1)
    except Exception:
        return None


def main():
    if os.environ.get("SHEATH_TB_AFTER"):
        import faulthandler; faulthandler.dump_traceback_later(float(os.environ["SHEATH_TB_AFTER"]), repeat=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True); ap.add_argument("--stl", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=None, help="pool size; default and upper bound = safe_workers()"); ap.add_argument("--mc", type=int, default=20000)
    ap.add_argument("--annotations", default=None); ap.add_argument("--ccx", default=None, help="ccx_tab results json (axial-force correction)")
    ap.add_argument("--no-rot-corr", action="store_true", help="disable the tab-end rotation correction of the Bayer release angle")
    a = ap.parse_args()
    a.workers = safe_workers(a.workers)
    print(f"[sheath.run] workers={a.workers}", file=sys.stderr, flush=True)
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    iface, mesh, Kp = from_step(a.step, a.stl, a.annotations)
    iface_ok, iface_verdict = validate(iface)
    json.dump(iface, open(os.path.join(a.out, "knife_interface.json"), "w"), indent=1)
    ann = json.load(open(a.annotations)) if a.annotations else {}
    K = Polygon(Kp.exterior)
    base = G.SheathParams()
    mat = M.MATERIALS[base.material]
    sharp_pts = np.vstack([np.array(r["pts"]) for r in iface["sharp_regions"]])
    tip_xy = np.asarray(iface["tip"])
    _stage("path_search")
    ranked, ncand = search_path(K, base, a.workers, sharp_pts)
    if not ranked:
        json.dump({"status": "path_infeasible", "n_candidates": ncand}, open(os.path.join(a.out, "metrics.json"), "w")); return
    p = ranked[0][0]
    seat = (ann.get("seating_lands") or [None])[0]
    ring_ = K.exterior
    bnd = np.array([ring_.interpolate(t).coords[0] for t in np.arange(0, ring_.length, 0.5)])
    from shapely.geometry import MultiPoint
    sharpL = LineString(sharp_pts)
    def land_pts(spec):
        x0, x1 = spec["x_range"]; y0, y1 = spec.get("y_range", [-1e9, spec.get("y_max", 1e9)])
        sel = [q for q in bnd if x0 <= q[0] <= x1 and y0 <= q[1] <= y1 and sharpL.distance(Point(q)) > 1.0
               and np.hypot(*(q - tip_xy)) > 6.0]
        return np.array(sel)
    bumper = [land_pts(b) for b in (ann.get("bumper_lands") or [])]
    bumper = [b for b in bumper if len(b) > 1]
    g = G.build2d(K, p, ds=1.0, seating_land=seat, tip_xy=tip_xy, bumper_pts=None)
    if bumper:
        gs = [G.build2d(K, p, ds=1.0, seating_land=seat, tip_xy=tip_xy, bumper_pts=b) for b in bumper[:1]]
        # apply all bumper pads sequentially on the cavity
        C0 = g["cavity"]
        for b in bumper:
            gb = G.build2d(K, p, ds=1.0, seating_land=seat, tip_xy=tip_xy, bumper_pts=b)
            if gb["pads"] is not None and not gb["pads"].is_empty:
                C0 = C0.difference(gb["pads"]).buffer(0)
                C0 = C0 if C0.geom_type == "Polygon" else max(C0.geoms, key=lambda x: x.area)
        g["cavity"] = C0; g["outline"] = C0.buffer(p.rim, join_style=1).intersection(g["D"])
    _stage("edge_margins")
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
    det = None
    for rl in (ann.get("retention_lands") or []):
        c = rl["hole_centroid"]
        hs = [h for h in iface["holes"] if np.hypot(h["centroid"][0] - c[0], h["centroid"][1] - c[1]) < 1.0]
        if hs and seated.contains(Point(hs[0]["centroid"])):
            det = hs[0]
    res = {"schema": "jarambit.sheath.metrics.v1", "evidence_level": "analytic_proxy+uncalibrated_fea",
           "knife": iface["source"], "knife_mass_g_brep": iface["brep"].get("mass_g_ti64"),
           "params": asdict(p), "material": asdict(mat), "n_path_candidates": ncand, "n_feasible": len(ranked),
           "top_paths": [{"path": r[0].path, "centre": r[0].centre, "dir": r[0].direction_deg, "sweep": r[0].sweep_max,
                          "outline_mm2": r[2], "edge_mouth_depth_mm": r[3]} for r in ranked[:8]],
           "path_feasible": g["path_feasible"], "left_at": g["left_at"], "mouth_len_mm": g["mouth_len_mm"], "mouth_note": "length of cavity edge on the mouth line",
           "outline_mm2": g["outline"].area, "cavity_mm2": C.area, "t_gap_knife_mm": t_gap_knife,
           "min_edge_clearance_mm": min_clear, "rim_min_mm": rim_min,
           "edge_mouth_depth_mm": edge_mouth_depth, "uncovered_sharp_mm": uncovered_sharp_mm,
           "shell_mass_g": m_g, "mass_g": m_g + p.mount_mass_g, "eps_allow": mat.eps_allow,
           "interface_verdict": iface_verdict, "annotation_status": iface.get("annotation_status"),
           "tessellation_error_mm": iface.get("tessellation_error_mm"), "min_clear_nominal_mm": g.get("min_clear_nominal"),
           "wobble": {"dir_deg": p.wobble_dir_deg, "rot_deg": p.wobble_rot_deg, "ramp_mm": p.wobble_ramp}, "motion_bound_mm": g["motion_bound_mm"]}
    # --- containment: positive stop, tip reserve, first-contact screen, strength screens
    _stage("containment")
    tr = G.tip_reserve(g, sharp_pts, tip_xy)
    land_all = np.vstack(bumper + ([np.array(g["stop_land_pts"])] if g["stop_land_pts"] else [])) if (bumper or g["stop_land_pts"]) else np.empty((0, 2))
    det0 = None
    for rl in (ann.get("retention_lands") or []):
        hs = [h for h in iface["holes"] if np.hypot(h["centroid"][0] - rl["hole_centroid"][0], h["centroid"][1] - rl["hole_centroid"][1]) < 1.0]
        det0 = hs[0] if hs else det0
    hole_land = None; A_flank = 0.0
    if det0 is not None:
        r_b = det0["eq_radius_mm"] - p.c_land
        # flank bearing: 2 bumps (both faces) x engaged height (undercut - c_face, nominal 1.0 mm before the search) x chord
        A_flank = 2 * max(p.detent_undercut - p.c_face, 1.0) * 2 * r_b * math.sin(math.radians(45))
        hole_land = {"draw_deg": p.direction_deg, "gap_mm": p.c_land, "cam_half_deg": p.bump_cam_half_deg, "r_bump_mm": r_b, "flank_bearing_mm2": A_flank,
                     "requirement": "bump lateral flanks >= 75 deg (non-camming); ramps only on the draw/insert axis +-%g deg" % p.bump_cam_half_deg}
    fc = SS.first_contact_screen(K, g["cavity"], sharp_pts, land_all, mouth=(g["m"], g["n"]), hole_land=hole_land)
    A_stop = 0.5 * len(g["stop_land_pts"]) * 3.6 if g["stop_land_pts"] else 0.0
    A_bump = [0.5 * len(b) * 3.0 for b in bumper]
    from shapely.geometry import Polygon as Pg
    span = 2 * max(0.5, max(g["cavity"].buffer(-r).area > 0 and r or 0 for r in np.arange(0.5, 30, 0.5)))
    margin_worst = fc["worst"]["margin"]
    res.update({"tip_reserve_mm": tr, "stop_land_n": len(g["stop_land_pts"]), "stop_bearing_area_mm2": A_stop,
                "first_contact": {"frac_land_first": fc["frac_land_first"], "worst": fc["worst"], "n_exit": fc["n_exit"], "hole_land": hole_land},
                "strength_screens": {
                    "drop_1.5m_edge": SS.drop_screen(iface["mass_g"], min(A_bump + ([A_flank] if A_flank else [])) if (A_bump or A_flank) else A_stop, margin_worst, 10.0, p.rim),
                    "drop_1.5m_tip_on_stop": SS.drop_screen(iface["mass_g"], A_stop, tr, 2.0, p.rim),
                    "crush_500N_platen": SS.crush_screen(span, p.wall, p.c_face),
                    "seated_overload_150N": SS.overload_screen(150.0, A_stop),
                    "mount_proof_240N": "NOT_EVALUATED (mount geometry PR-S4)",
                    "sustained_25N_60s": "NOT_EVALUATED (creep data; seated tabs carry 0 deflection by design)",
                    "puncture_cut_through": "SCREEN ONLY — physical guarded test mandatory (plan §8.4)"},
                "rattle_free_play_mm": p.c_land if bumper else p.c_edge + 0.5 * g["motion_bound_mm"]})
    res["strength_fail"] = [k for k, v in res["strength_screens"].items() if isinstance(v, dict) and v.get("verdict") == "SCREEN_FAIL"]
    if det is None:
        res["retention"] = "NOT_EVALUATED: no human-annotated retention land (INCOMPLETE)"
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
        ladder = _guarded_ladder(panel, bump, mat.E_mpa, p.wall, r0, (mpt, n))
        res["solid_panel"] = {"k_ladder": ladder, "k_analytic_clamped_circle_n_mm": M.clamped_circ_plate_k(mat.E_mpa, p.wall, a_eq), "a_eq_mm": a_eq}

        def tab_k_fem(q, ma=0.15):
            rect = sbox(0, 0, q.tab_L, q.tab_b)
            kf, _, nd, _ = plate_stiffness(rect, (q.tab_L - min(2.0, q.tab_b / 3), q.tab_b / 2), mat.E_mpa, q.wall,
                                           r0=min(1.5, q.tab_b / 4), max_area=ma, clamp_fn=lambda x, y: x < 1e-6)
            return kf, nd

        rng = np.random.default_rng(42); N = a.mc; W = M.WINDOW
        ROT = 0.0 if a.no_rot_corr else 1.0
        # residual FEA calibration: ccx large-sliding S2S peak / rotation-corrected Bayer at the benchmark geometry
        CCXF = 1.0; ccx_info = None
        if a.ccx:
            cj = json.load(open(a.ccx)); CCXF = float(cj.get("ccx_over_bayer_rot") or 1.0) if not a.no_rot_corr else 1.0
            ccx_info = {k: cj.get(k) for k in ("solver", "conv_rel_last2", "ccx_over_bayer", "ccx_over_bayer_rot", "analytic")}
        def draws(N, seed):
            r = np.random.default_rng(seed)
            Tf = r.choice([1.15, 1.0, 0.80], size=N, p=[0.2, 0.6, 0.2])   # E(-10C), E(23C), E(+50C): ASSUMPTION pending ISO 178 at T
            return dict(Tf=Tf, dw=r.normal(0, 0.1, N), du=r.normal(0, 0.05, N), dc=r.normal(0, 0.05, N), tk=r.normal(0, 0.03, N),
                        mu=r.uniform(0.20, 0.45, N), wear=r.uniform(0.0, 0.15, N), dL=r.normal(0, 0.1, N),
                        # NEW condition population (same tolerance draws): 23 C, no wear, clean dry Ti/PA12 mu U(0.20,0.32)
                        # ASSUMPTION pending ASTM D1894 coupons; conditioned/life population keeps dry/wet/grit U(0.20,0.45)
                        mu_new=r.uniform(0.20, 0.32, N))
        MCs = draws(2000, 7); MCf = draws(N, 42)

        def evaluate(q, k=None, mc=None):
            mc = mc or MCs
            Tf, dw, du, dc, tk, mu_s, wear, dL = (mc[x] for x in ("Tf", "dw", "du", "dc", "tk", "mu", "wear", "dL"))
            if k is None:
                k = M.tab_k(mat.E_mpa, q.tab_b, q.wall, q.tab_L - 2.0)
            i_face = q.detent_undercut - q.c_face - (t_gap_knife - t_local) / 2
            d = M.detent_forces(k, max(i_face, 0), mat.mu_steel, q.detent_a_in, q.detent_a_out)
            eps = M.tab_strain(q.wall, q.tab_L - 2.0, max(i_face, 0))
            a_tab = q.tab_L - 2.0
            def F_of(Tf_, wear_, mu_):
                kk = k * Tf_ * ((q.wall + dw) / q.wall) ** 3 * (a_tab / (a_tab + dL)) ** 3
                ii = np.clip(q.detent_undercut + du - (q.c_face + dc) - (t_gap_knife - t_local) / 2 + tk / 2 - wear_, 0, None)
                ta = np.tan(np.radians(q.detent_a_out) - ROT * 1.5 * ii / a_tab)   # tab-end rotation (ccx-verified, ccx_tab.py)
                return CCXF * 2 * kk * ii * (mu_ + ta) / np.clip(1 - mu_ * ta, 1e-6, None)
            Fmc = F_of(Tf, wear, mu_s); Fnew = F_of(1.0, 0.0, mc["mu_new"])
            i0 = max(i_face, 0); tr0 = math.tan(math.radians(q.detent_a_out) - ROT * 1.5 * i0 / a_tab); mu0 = mat.mu_steel
            draw0 = CCXF * 2 * k * i0 * (mu0 + tr0) / (1 - mu0 * tr0)
            ti0 = math.tan(math.radians(q.detent_a_in) - ROT * 1.5 * i0 / a_tab)
            ins0 = CCXF * 2 * k * i0 * (mu0 + ti0) / (1 - mu0 * ti0)
            return {"k": k, "i_face": i_face, "P": d.P_n, "draw": draw0, "draw_no_rot": 2 * d.draw_n, "insert": ins0, "insert_no_rot": 2 * d.insert_n, "eps": eps,
                    "new_p05": float(np.percentile(Fnew, 5)), "new_p95": float(np.percentile(Fnew, 95)),
                    "p05": float(np.percentile(Fmc, 5)), "p50": float(np.median(Fmc)), "p95": float(np.percentile(Fmc, 95)),
                    "p_life": float(np.mean((Fmc > W.lo_life) & (Fmc < W.hi_life))),
                    "p_new": float(np.mean((Fnew > W.lo_new) & (Fnew < W.hi_new))), "Fmc": Fmc}

        # --- retention design search (cheap, analytic k): tab length, undercut, return angle, wall
        _stage("retention_search")
        best = None; nsearch = 0
        import itertools
        SEARCH = {"wall": (1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8), "tab_L": tuple(np.arange(6.0, 26.01, 1.0)),
                  "undercut": tuple(np.round(np.arange(0.30, 2.001, 0.05), 3)), "a_out": (20.0, 25.0, 30.0, 35.0, 40.0, 45.0),
                  "tab_b": (5.0, 7.0, 9.0), "retention": ("tab", "collar")}
        for wall, L, und, aout, tb, rmode in itertools.product(*SEARCH.values()):
                        if 2.0 * (und - p.c_face) > (L - 2.0) * 0.25: continue      # geometric sanity: bump << tab
                        q = replace(p, wall=wall, tab_L=float(L), detent_undercut=float(und), detent_a_out=aout, tab_b=tb, retention=rmode)
                        e = evaluate(q); nsearch += 1
                        mg = G.mass_g(g, q, t_gap_knife, mat.rho_g_cm3)[0] + q.mount_mass_g + G.collar_mass_delta_g(g, q, bump, mat.rho_g_cm3)
                        f = M.fitness({"tip_reserve_mm": tr, "strength_fail": res["strength_fail"], "cost_proxy": 0.05 if rmode == "collar" else 0.0, "edge_mouth_depth_mm": edge_mouth_depth, "uncovered_sharp_mm": uncovered_sharp_mm, "path_feasible": g["path_feasible"], "min_edge_clearance_mm": min_clear, "insert_n": e["insert"],
                                       "strain_est": e["eps"], "eps_allow": mat.eps_allow, "rim_min_mm": rim_min,
                                       "p_in_life_window": e["p_life"], "draw_n": e["draw"], "mass_g": mg, "p_in_new_window": e["p_new"]})
                        key = (f["score"], e["p_life"], e["p_new"], -mg)
                        if best is None or key > best[0]: best = (key, q, e, mg)
        p = best[1]
        _stage("tab_fem")
        kf, ndf = tab_k_fem(p); kf2, ndf2 = tab_k_fem(p, 0.05)
        e = evaluate(p, mc=MCf)
        m_g = best[3] - p.mount_mass_g
        at_bound = {k: (getattr(p, {"undercut": "detent_undercut", "a_out": "detent_a_out"}.get(k, k)) in (v[0], v[-1]))
                    for k, v in SEARCH.items() if k != "retention"}
        np.savetxt(os.path.join(a.out, "draw_mc.csv"), e["Fmc"], delimiter=",", header="draw_peak_n", comments="", fmt="%.3f")
        # integral vs collar comparison at the same compliant geometry
        alt = replace(p, retention="collar" if p.retention == "tab" else "tab")
        res["integral_vs_collar"] = {p.retention: best[3], alt.retention: m_g + p.mount_mass_g + G.collar_mass_delta_g(g, alt, bump, mat.rho_g_cm3)
                                     - G.collar_mass_delta_g(g, p, bump, mat.rho_g_cm3)}
        res["search_bound_hit"] = at_bound
        res.update({"params": asdict(p), "shell_mass_g": m_g, "mass_g": best[3], "retention_search_n": nsearch})
        _stage("track_profile")
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
            "draw_n_no_rot_corr": e["draw_no_rot"], "ccx_factor": CCXF, "ccx": ccx_info, "mc_new": {"p05": e["new_p05"], "p95": e["new_p95"], "mu": "U(0.20,0.32) ASSUMED", "wear": 0, "T": "23C"},
            "mc": {"n": N, "p05": e["p05"], "p50": e["p50"], "p95": e["p95"], "p_in_life_window": e["p_life"], "p_in_new_window": e["p_new"],
                   "p01": float(np.percentile(e["Fmc"], 1)), "p99": float(np.percentile(e["Fmc"], 99)),
                   "assumptions": "wall sd0.1, undercut sd0.05, c_face sd0.05, knife t sd0.03, tab L sd0.1, life mu U(0.20,0.45) / new mu U(0.20,0.32), tab-end rotation correction %s, wear U(0,0.15)mm (5000 cyc), E x{1.15@-10C,1,0.80@+50C} p{.2,.6,.2}" % ("on" if ROT else "off")},
        })
        res["p_in_life_window"] = e["p_life"]; res["p_in_new_window"] = e["p_new"]
        np.savetxt(os.path.join(a.out, "draw_curve.csv"), np.c_[arc, F, inter, tt], delimiter=",",
                   header="grip_disp_mm,axial_force_n,interference_per_side_mm,knife_t_under_bump_mm", comments="")
    _stage("fitness")
    res["fitness"] = M.fitness(res)
    res["verdicts"] = {"geometry": "PASS" if g["path_feasible"] else "FAIL",
                       "withdrawal_clearance": "PASS" if min_clear >= 0.3 else "FAIL",
                       "retention_force": "PREDICTED (analytic_proxy+uncalibrated_fea) — not a measurement",
                       "puncture": "NOT_EVALUATED", "mount": "NOT_EVALUATED", "physical_validation": "NOT_EVALUATED"}
    # CAD export
    try:
        import cadquery as cq
        sol = G.solid3d_full(g, p, t_gap_knife, tuple(det['centroid']) if det else None)
        parts = sol if isinstance(sol, dict) else {"shell": sol}
        res["cad_parts"] = {}
        for nm, so in parts.items():
            cq.exporters.export(so, os.path.join(a.out, "sheath_v1_%s.step" % nm))
            cq.exporters.export(so, os.path.join(a.out, "sheath_v1_%s.stl" % nm), tolerance=0.05)
            res["cad_parts"][nm] = {"volume_mm3": so.val().Volume(), "mass_g": so.val().Volume() * mat.rho_g_cm3 * 1e-3}
        res["cad_mass_g"] = sum(v["mass_g"] for v in res["cad_parts"].values())
    except Exception as e:
        res["cad_export"] = "failed: %r" % e
    res["elapsed_s"] = time.time() - t0
    json.dump(res, open(os.path.join(a.out, "metrics.json"), "w"), indent=1, default=float)
    # figure
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(15, 6))
        C = g["cavity"]
        for geom, kw in ((g["outline"], dict(fc="#3a6", alpha=.35)), (C, dict(fc="w", alpha=1))):
            for gg in getattr(geom, "geoms", [geom]):
                ax[0].fill(*gg.exterior.xy, ec="k", **kw)
        ax[0].plot(*Kp.exterior.xy, "k", lw=.8)
        for r in Kp.interiors: ax[0].plot(*r.xy, "k", lw=.6)
        ax[0].plot(sharp_pts[:, 0], sharp_pts[:, 1], "r.", ms=1.5, label="sharpened edge (auto)")
        for extra, col in ((g.get("stop"), "#c60"),):
            if extra is not None and not extra.is_empty:
                for gg in getattr(extra, "geoms", [extra]): ax[0].fill(*gg.exterior.xy, fc=col)
        if len(land_all): ax[0].plot(land_all[:, 0], land_all[:, 1], "c.", ms=2, label="approved(proposed) lands")
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
