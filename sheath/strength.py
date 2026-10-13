"""Containment + strength-test screens (analytic_proxy). These SCREEN designs for the physical test matrix (plan §8);
none of them proves puncture/cut-through resistance — an elastic or analytic model cannot (walls are unbreakable in it).

Cut-through screen (fracture-mechanics cutting, Atkins, "The Science and Engineering of Cutting", 2009): a sharp edge
advancing a cut of length L by depth d does work >= R*L*d (R = cutting/fracture toughness of the wall polymer).
R for PA12 is NOT known to us: ASSUMED range 5-30 kJ/m^2 (= 5-30 N/mm) until the M5 guarded blade-cut coupon test.
"""
import math
import numpy as np
from shapely.geometry import Point, LineString
from sheath import model as M

R_CUT_N_PER_MM = (5.0, 30.0)     # ASSUMPTION range
DROP_H_M = 1.5


def first_contact_screen(K, C, sharp_pts, land_pts, ndir=36, mouth=None, L=10.0, hole_land=None):
    """In-plane rigid shift of the seated knife in each direction: which boundary point touches the cavity WALL first?
    Returns per-direction gaps and the worst edge margin (gap_sharp - gap_land, >0 means a non-sharp land hits first).
    The mouth line is open (not a wall): it is removed from the boundary, and directions in which the sharp points meet
    no wall within L (they leave through the mouth = the draw direction) are reported as 'exit', not as a margin."""
    if hole_land is not None and hole_land.get("status") != "COMPLETE":
        return {"status": "INCOMPLETE", "reason": "directional bump land is not supported by exported CAD",
                "dirs": [], "worst": None, "n_exit": None, "frac_land_first": None}
    from sheath.generate import ray_dist
    from shapely.geometry import LineString as LS
    ring = C.exterior
    if mouth is not None:
        m, n = np.asarray(mouth[0], float), np.asarray(mouth[1], float)
        tdir = np.array([-n[1], n[0]])
        ring = ring.difference(LS([m - 400 * tdir, m + 400 * tdir]).buffer(0.05))
    S = np.asarray(sharp_pts)[::3]; Lp = np.asarray(land_pts) if len(land_pts) else np.empty((0, 2))
    out = []
    for k in range(ndir):
        a = 2 * math.pi * k / ndir; u = np.array([math.cos(a), math.sin(a)])
        gs = min(ray_dist(q, u, ring, L) for q in S)
        gl = min((ray_dist(q, u, ring, L) for q in Lp), default=L)
        if hole_land is not None:
            # bump (sheath) inside the closed guard hole (knife): non-camming flanks lock in-plane shifts that are
            # outside +-cam_half_deg of the draw axis at the bump/hole clearance; within +-45 deg of the axis the ramps cam (detent)
            off = abs(((math.degrees(a) - hole_land["draw_deg"]) + 180.0) % 360.0 - 180.0)
            if hole_land.get("cam_half_deg", 45.0) <= off <= 180.0 - hole_land.get("cam_half_deg", 45.0):
                gl = min(gl, hole_land["gap_mm"])
        if gs >= L - 1e-9:
            out.append({"dir_deg": math.degrees(a), "gap_sharp": None, "gap_land": gl, "margin": None, "exit": True}); continue
        out.append({"dir_deg": math.degrees(a), "gap_sharp": gs, "gap_land": gl, "margin": gs - gl, "exit": False})
    walls = [r for r in out if not r["exit"]]
    worst = min(walls, key=lambda r: r["margin"])
    return {"status": "COMPLETE", "dirs": out, "worst": worst, "n_exit": len(out) - len(walls),
            "frac_land_first": float(np.mean([r["margin"] > 0 for r in walls]))}


def drop_screen(m_knife_g, A_land_mm2, margin_mm, L_edge_mm, rim_mm, h=DROP_H_M, sigma=M.SIGMA_PA12_MPA):
    """Worst case: sheath stops instantly, knife arrives with full m g h relative KE (upper bound).
    Land/pad crush absorbs sigma*A per mm; if crush > margin the edge meets the rim with the residual energy, which must
    be < R*L*rim (no cut-through) — evaluated at both ends of the R range."""
    E = m_knife_g * 1e-3 * M.G0 * h * 1e3                      # N*mm
    crush = E / (sigma * max(A_land_mm2, 1e-6))
    resid = max(0.0, E - sigma * A_land_mm2 * max(margin_mm, 0.0))
    depth = [resid / (R * L_edge_mm) for R in R_CUT_N_PER_MM]   # lo-R (pessimistic) first
    return {"E_nmm": E, "land_crush_mm": crush, "edge_reached": crush > margin_mm, "residual_nmm": resid,
            "cut_depth_mm_pess_opt": depth, "rim_mm": rim_mm,
            "verdict": "SCREEN_PASS" if depth[0] < 0.5 * rim_mm else ("SCREEN_MARGINAL" if depth[1] < 0.5 * rim_mm else "SCREEN_FAIL")}


def crush_screen(panel_span_mm, wall_mm, c_face_mm, F_n=500.0, A_platen_mm2=4000.0, sigma=M.SIGMA_PA12_MPA):
    """500 N flat platen over the side face: clamped long-rectangle strip (Roark: sigma_edge = 0.5 q b^2 / t^2).
    If the panel deflection exceeds c_face the knife flats carry the load (contact on flats only — edges are in-plane)."""
    q = F_n / A_platen_mm2
    sig = 0.5 * q * panel_span_mm ** 2 / wall_mm ** 2
    E = M.MATERIALS["PA12_MJF"].E_mpa
    w = q * panel_span_mm ** 4 / (32 * E * wall_mm ** 3)          # clamped strip, unit width: q b^4 / (384 D) * 12 -> ~ /32Et^3
    return {"sigma_unsupported_mpa": sig, "w_unsupported_mm": w, "knife_supported": w > c_face_mm,
            "verdict": "SCREEN_PASS" if (sig < sigma / 1.5 or w > c_face_mm) else "SCREEN_FAIL"}


def overload_screen(F_n, A_land_mm2, sigma=M.SIGMA_PA12_MPA):
    s = F_n / max(A_land_mm2, 1e-6)
    return {"F_n": F_n, "bearing_mpa": s, "verdict": "SCREEN_PASS" if s < sigma / 1.5 else "SCREEN_FAIL"}
