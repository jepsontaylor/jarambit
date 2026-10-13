"""Parametric hard-sheath generator (v1: planar knife -> 2D swept cavity -> 3D closed shell).

Cavity C = buffer( U_s [T(s) K  ∩  D], c_edge ) where D is the half-plane beyond the mouth line and T(s) the
draw path (rotation about a centre, or translation). The outline is buffer(C, rim). Panels close both faces.
The path is feasible when every swept knife point leaves D through the mouth segment (by construction here) and
the cavity does not intrude on the exposed grip keep-out. Clearances are explicit (plan §4.3).
"""
from dataclasses import dataclass, asdict, field
import math
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box
from shapely import affinity
from shapely.ops import unary_union


@dataclass
class SheathParams:
    material: str = "PA12_MJF"
    mouth_x: float = 76.0            # mouth line passes through (mouth_x, y_mid) of knife
    path: str = "rot"                # "rot" | "trans"
    centre: tuple = (120.0, 40.0)    # rotation centre (rot)
    direction_deg: float = 180.0     # translation direction (trans)
    sweep_max: float = 140.0         # deg (rot) or mm (trans)
    c_face: float = 0.25             # per-side face clearance (mm)
    c_edge: float = 0.8              # in-plane clearance around sharpened edges/tip (mm)
    rim: float = 3.0                 # in-plane wall outside cavity (edge protection band)
    wall: float = 1.6                # panel thickness
    detent_undercut: float = 0.6     # bump height into retention hole
    detent_a_in: float = 30.0
    detent_a_out: float = 40.0
    detent_hole: str = "guard"       # retention feature: closed guard hole (REVIEW REQUIRED)
    retention: str = "tab"           # "tab" = U-slot click-tab in each side panel | "panel" = bump on the solid panel
    tab_L: float = 9.0               # click-tab free length (mm)
    tab_b: float = 7.0               # click-tab width (mm)
    slot_w: float = 0.8              # U-slot kerf (mm) (MJF min slot ~0.5 mm: assumption)
    grip_keepout_x: float = 60.0     # no sheath material at x < this (ring + grip exposed)
    mount_mass_g: float = 4.0        # belt/strap clip allowance (not yet modelled)


def _T(p: SheathParams, s):
    def f(g):
        if p.path == "rot":
            return affinity.rotate(g, s, origin=p.centre, use_radians=False)
        a = math.radians(p.direction_deg)
        return affinity.translate(g, s * math.cos(a), s * math.sin(a))
    return f


def mouth_geom(K: Polygon, p: SheathParams):
    """Mouth point m and outward normal n (direction the mouth point moves at s=0); D = {(x-m).n < 0}."""
    x = p.mouth_x
    seg = K.intersection(LineString([(x, -200), (x, 200)]))
    ys = [c[1] for g in getattr(seg, "geoms", [seg]) for c in g.coords]
    m = np.array([x, 0.5 * (min(ys) + max(ys))])
    if p.path == "rot":
        r = m - np.array(p.centre)
        v = np.array([-r[1], r[0]]) * (1.0 if p.sweep_max > 0 else -1.0)  # velocity for the swept sense
    else:
        a = math.radians(p.direction_deg); v = np.array([math.cos(a), math.sin(a)])
    return m, v / np.linalg.norm(v), seg


def halfplane(m, n, L=600.0):
    """Region behind the mouth (where the blade sits): (x-m).n < 0."""
    t = np.array([-n[1], n[0]])
    a, b = m + t * L, m - t * L
    return Polygon([a, b, b - n * L, a - n * L])


def build2d(K: Polygon, p: SheathParams, ds=None):
    m, n, _ = mouth_geom(K, p)
    D = halfplane(m, n)
    ds = ds or (1.0 if p.path == "rot" else 1.5)
    parts, s, left = [], 0.0, None
    sign = 1.0 if p.sweep_max > 0 else -1.0
    while s <= abs(p.sweep_max):
        g = _T(p, sign * s)(K).intersection(D)
        if g.is_empty or g.area < 1e-3:
            left = s; break
        parts.append(g); s += ds
    feasible = left is not None
    Ksolid = Polygon(K.exterior)   # holes don't matter for the cavity
    swept = unary_union([_T(p, sign * k * ds)(Ksolid).intersection(D) for k in range(len(parts))])
    C = swept.buffer(p.c_edge, join_style=1).intersection(D)
    O = C.buffer(p.rim, join_style=1).intersection(D)
    keep = box(-500, -500, p.grip_keepout_x, 500)
    intrudes = O.intersection(keep).area > 1.0
    mouth_len = C.intersection(LineString([m - np.array([-n[1], n[0]]) * 300, m + np.array([-n[1], n[0]]) * 300]).buffer(0.25)).area / 0.5
    return {"cavity": C, "outline": O, "D": D, "m": m, "n": n, "swept": swept, "left_at": left,
            "path_feasible": bool(feasible and not intrudes), "grip_intrusion": bool(intrudes), "mouth_len_mm": mouth_len}


def edge_margins(g, sharp_pts, p: SheathParams):
    """Min in-plane distance from every swept sharp-edge sample to the cavity wall, and min rim behind seated edge."""
    C, O = g["cavity"], g["outline"]
    D = g["D"]
    mline = LineString([g["m"] - np.array([-g["n"][1], g["n"][0]]) * 300, g["m"] + np.array([-g["n"][1], g["n"][0]]) * 300])
    wall = C.exterior.difference(mline.buffer(0.6))   # the open mouth is not a wall
    min_clear, rim_min = math.inf, math.inf
    pts_all = []
    s = 0.0
    while g["left_at"] is not None and s <= g["left_at"]:
        sg = 1.0 if p.sweep_max > 0 else -1.0
        q = np.asarray(_T(p, sg * s)(LineString(sharp_pts)).coords) if len(sharp_pts) > 1 else np.empty((0, 2))
        for xy in q[::2]:
            P_ = Point(xy)
            if D.contains(P_):
                min_clear = min(min_clear, wall.distance(P_))
        s += 2.0
    for xy in sharp_pts[::2]:
        P_ = Point(xy)
        if D.contains(P_) and C.contains(P_):
            rim_min = min(rim_min, O.exterior.distance(P_))
    return min_clear, rim_min


def mass_g(g, p: SheathParams, t_knife, rho):
    O, C = g["outline"], g["cavity"]
    H = t_knife + 2 * p.c_face + 2 * p.wall
    vol = O.area * H - C.area * (t_knife + 2 * p.c_face)
    return vol * rho * 1e-3, vol


def solid3d(g, p: SheathParams, t_knife):
    """CadQuery solid: extruded outline minus extruded cavity (open at mouth), centred on z=0."""
    import cadquery as cq
    def wp_poly(poly, h, z0):
        ext = list(poly.exterior.coords)[:-1]
        w = cq.Workplane("XY", origin=(0, 0, z0)).polyline(ext).close()
        return w.extrude(h)
    H = t_knife + 2 * p.c_face + 2 * p.wall
    gap = t_knife + 2 * p.c_face
    O = g["outline"] if g["outline"].geom_type == "Polygon" else max(g["outline"].geoms, key=lambda x: x.area)
    C = g["cavity"] if g["cavity"].geom_type == "Polygon" else max(g["cavity"].geoms, key=lambda x: x.area)
    outer = wp_poly(O.simplify(0.05), H, -H / 2)
    # extend the cavity slightly past the mouth so it opens cleanly
    Cx = C.union(C.intersection(g["D"].buffer(-0.01)).buffer(0)).buffer(0)
    Cm = Cx.union(affinity.translate(C, *(g["n"] * 1.5))).buffer(0)
    cav = wp_poly((Cm if Cm.geom_type == "Polygon" else max(Cm.geoms, key=lambda x: x.area)).simplify(0.05), gap, -gap / 2)
    return outer.cut(cav)


def tab_slot_polys(g, p: SheathParams, bump_xy):
    """U-slot (3 sides) around a click-tab whose free end carries the bump and whose root lies deeper (along -n)."""
    n = np.asarray(g["n"]); t = np.array([-n[1], n[0]]); b = np.asarray(bump_xy)
    tip_end = b + n * 2.0                     # free end just mouth-side of the bump
    root = tip_end - n * p.tab_L
    hb, k = p.tab_b / 2, p.slot_w
    def quad(a0, a1, w0, w1):
        return Polygon([tip_end - n * a0 + t * w0, tip_end - n * a1 + t * w0, tip_end - n * a1 + t * w1, tip_end - n * a0 + t * w1])
    return [quad(-k, p.tab_L, hb, hb + k), quad(-k, p.tab_L, -hb - k, -hb), quad(-k, 0.0, -hb - k, hb + k)]


def solid3d_full(g, p: SheathParams, t_knife, bump_xy=None):
    import cadquery as cq
    sol = solid3d(g, p, t_knife)
    if bump_xy is None or p.retention != "tab":
        return sol
    H = t_knife + 2 * p.c_face + 2 * p.wall; gap = t_knife + 2 * p.c_face
    for side in (+1, -1):
        z0 = side * gap / 2 if side > 0 else -H / 2
        for q in tab_slot_polys(g, p, bump_xy):
            sol = sol.cut(cq.Workplane("XY", origin=(0, 0, z0)).polyline(list(q.exterior.coords)[:-1]).close().extrude(p.wall))
        h = p.detent_undercut; r0 = 1.6
        R = (r0 ** 2 + h ** 2) / (2 * h)
        zc = side * (gap / 2 + R - h)
        sph = cq.Workplane("XY").sphere(R).translate((bump_xy[0], bump_xy[1], zc))
        slab = cq.Workplane("XY", origin=(0, 0, side * gap / 2 if side < 0 else gap / 2 - h)).rect(400, 400).extrude(h) if side > 0 else \
            cq.Workplane("XY", origin=(0, 0, -gap / 2)).rect(400, 400).extrude(h)
        sol = sol.union(sph.intersect(slab))
    return sol
