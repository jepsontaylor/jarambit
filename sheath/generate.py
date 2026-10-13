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
    wobble_dir_deg: float = 2.0      # ± draw-direction perturbation swept into the cavity (R3)
    wobble_rot_deg: float = 2.0      # ± rotation about the mouth point, ramped in over the first `wobble_ramp` mm (R3)
    wobble_ramp: float = 20.0
    tip_reserve: float = 1.5         # tip-to-pocket reserve along the insertion direction once seated on the stop
    collar_frame: float = 2.0        # collar module: frame width around the tab window (mm)
    collar_flange: float = 0.8       # collar module: outer flange thickness (mm)
    c_land: float = 0.3              # in-plane clearance at approved bumper lands (non-sharp) -> lands hit before edges


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


def _poses(p: SheathParams, s, m):
    """Nominal + perturbed rigid poses at path parameter s (translation family gets ±dir and ±rot wobble)."""
    out = []
    sg = 1.0 if p.sweep_max > 0 else -1.0
    rmp = min(1.0, s / max(p.wobble_ramp, 1e-6))
    dirs = (0.0, -p.wobble_dir_deg, p.wobble_dir_deg) if p.wobble_dir_deg > 0 else (0.0,)
    rots = (0.0, -p.wobble_rot_deg, p.wobble_rot_deg) if p.wobble_rot_deg > 0 else (0.0,)
    for dd in dirs:
        for rr in rots:
            def f(g, dd=dd, rr=rr):
                if p.path == "rot":
                    g2 = affinity.rotate(g, sg * s, origin=p.centre)
                else:
                    a = math.radians(p.direction_deg + dd)
                    g2 = affinity.translate(g, sg * s * math.cos(a), sg * s * math.sin(a))
                return affinity.rotate(g2, rr * rmp, origin=tuple(m)) if rr else g2
            out.append(f)
    return out


def ray_dist(q, d, ring_geom, L=40.0):
    q = np.asarray(q, float)
    seg = LineString([q, q + d * L])
    x = seg.intersection(ring_geom)
    if x.is_empty:
        return L
    pts = [c for g in getattr(x, "geoms", [x]) for c in g.coords]
    return float(min(np.hypot(*(np.asarray(c) - q)) for c in pts))


def build2d(K: Polygon, p: SheathParams, ds=None, seating_land=None, tip_xy=None, bumper_pts=None):
    """Cavity C = H ∩ ⋃_s ⋃_wobble T(s)K ⊕ (c_edge + motion bound), minus the positive stop, plus tip reserve."""
    m, n, _ = mouth_geom(K, p)
    D = halfplane(m, n)
    ds = ds or (1.0 if p.path == "rot" else 1.5)
    Ksolid = Polygon(K.exterior)
    parts, s, left = [], 0.0, None
    while s <= abs(p.sweep_max):
        g = _T(p, (1 if p.sweep_max > 0 else -1) * s)(K).intersection(D)
        if g.is_empty or g.area < 1e-3:
            left = s; break
        s += ds
    feasible = left is not None
    S = np.arange(0.0, (left if left is not None else abs(p.sweep_max)) + ds, ds)
    pieces, moving = [], []
    for sv in S:
        for f in _poses(p, sv, m):
            g_ = f(Ksolid).intersection(D)
            pieces.append(g_)
            if sv >= ds - 1e-9:
                moving.append(g_)
    swept = unary_union(pieces)
    # continuous-motion bound: between samples no point moves more than ds (+ wobble-ramp rotation increment)
    Rmax = max(np.hypot(*(np.asarray(Ksolid.exterior.coords) - m).T))
    motion = ds + Rmax * math.radians(p.wobble_rot_deg) * ds / max(p.wobble_ramp, 1e-6)
    C = swept.buffer(p.c_edge + 0.5 * motion, join_style=1).intersection(D)
    dvec = -np.array([math.cos(math.radians(p.direction_deg)), math.sin(math.radians(p.direction_deg))]) if p.path == "trans" else -n
    stop_poly, land_used = None, []
    if seating_land:
        x0, x1 = seating_land["x_range"]; ymax = seating_land["y_max"]
        ring = Ksolid.exterior
        cand = [ring.interpolate(t).coords[0] for t in np.arange(0, ring.length, 0.5)]
        cand = [q for q in cand if x0 <= q[0] <= x1 and q[1] <= ymax and D.contains(Point(q))]
        # leading points only: the -d ray must not re-enter the knife
        lead = [q for q in cand if not LineString([np.add(q, dvec * 0.3), np.add(q, dvec * 15)]).intersects(Ksolid)]
        if lead:
            proj = np.array([np.dot(q, dvec) for q in lead])
            lead = [q for q, pr in zip(lead, proj) if pr >= proj.max() - 0.6]
            land_used = lead
            fill = unary_union([LineString([q, np.add(q, dvec * (p.c_edge + motion + 3.0))]).buffer(0.6, cap_style=2) for q in lead])
            stop_poly = fill.difference(Ksolid.buffer(0.02)).intersection(C)
            C = C.difference(stop_poly).buffer(0)
            if C.geom_type != "Polygon":
                C = max(C.geoms, key=lambda x: x.area)
    if tip_xy is not None:
        tz = Point(tip_xy).buffer(6.0).intersection(Ksolid)
        ext = unary_union([affinity.translate(tz, *(dvec * k)) for k in np.linspace(0, p.tip_reserve + 0.5, 6)])
        C = unary_union([C, ext.buffer(p.c_edge, join_style=1).intersection(D)]).buffer(0)
        if C.geom_type != "Polygon":
            C = max(C.geoms, key=lambda x: x.area)
    pads = None
    if bumper_pts is not None and len(bumper_pts) > 1:
        mov = unary_union(moving).buffer(p.c_land) if moving else Polygon()
        band = LineString(bumper_pts).buffer(p.c_edge + 0.5 * motion + 0.05, cap_style=2)
        pads = band.intersection(C).difference(Ksolid.buffer(p.c_land)).difference(mov).buffer(0)
        if not pads.is_empty:
            C = C.difference(pads).buffer(0)
            if C.geom_type != "Polygon":
                C = max(C.geoms, key=lambda x: x.area)
    O = C.buffer(p.rim, join_style=1).intersection(D)
    keep = box(-500, -500, p.grip_keepout_x, 500)
    intrudes = O.intersection(keep).area > 1.0
    mline = LineString([m - np.array([-n[1], n[0]]) * 300, m + np.array([-n[1], n[0]]) * 300])
    mouth_len = C.intersection(mline.buffer(0.25)).area / 0.5
    return {"cavity": C, "outline": O, "D": D, "m": m, "n": n, "swept": swept, "left_at": left, "dvec": dvec,
            "stop": stop_poly, "pads": pads, "stop_land_pts": land_used, "motion_bound_mm": motion,
            "path_feasible": bool(feasible and not intrudes), "grip_intrusion": bool(intrudes), "mouth_len_mm": mouth_len}


def tip_reserve(g, sharp_pts, tip_xy):
    """Min distance along the insertion direction from tip-zone/sharp points to the pocket wall (seated on the stop)."""
    C = g["cavity"]; d = g["dvec"]; mline_ok = []
    pts = [q for q in sharp_pts if np.hypot(*(np.asarray(q) - tip_xy)) < 8.0] + [tip_xy]
    return float(min(ray_dist(q, d, C.exterior) for q in pts))


def edge_margins(g, sharp_pts, p: SheathParams):
    """Min in-plane distance from every swept sharp-edge sample (nominal AND wobble poses) to the cavity wall
    (mouth excluded), and min solid rim outboard of each seated sharp point."""
    C, O, D = g["cavity"], g["outline"], g["D"]
    mline = LineString([g["m"] - np.array([-g["n"][1], g["n"][0]]) * 300, g["m"] + np.array([-g["n"][1], g["n"][0]]) * 300])
    wall = C.exterior.difference(mline.buffer(0.6))
    min_clear, rim_min, min_nom = math.inf, math.inf, math.inf
    L = LineString(sharp_pts[::2])
    s = 0.0
    while g["left_at"] is not None and s <= g["left_at"]:
        for k, f in enumerate(_poses(p, s, g["m"])):
            q = np.asarray(f(L).coords)
            for xy in q[::2]:
                P_ = Point(xy)
                if D.contains(P_):
                    d = wall.distance(P_)
                    min_clear = min(min_clear, d)
                    if k == 0: min_nom = min(min_nom, d)
        s += 2.0
    for xy in sharp_pts[::2]:
        P_ = Point(xy)
        if D.contains(P_) and C.contains(P_):
            rim_min = min(rim_min, O.exterior.distance(P_))
    g["min_clear_nominal"] = min_nom
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


def collar_window(g, p: SheathParams, bump_xy):
    n = np.asarray(g["n"]); t = np.array([-n[1], n[0]]); b = np.asarray(bump_xy)
    tip_end = b + n * 2.0
    hb = p.tab_b / 2 + p.slot_w + p.collar_frame
    a0, a1 = -p.slot_w - p.collar_frame, p.tab_L + p.collar_frame
    return Polygon([tip_end - n * a0 + t * hb, tip_end - n * a1 + t * hb, tip_end - n * a1 - t * hb, tip_end - n * a0 - t * hb])


def collar_mass_delta_g(g, p: SheathParams, bump_xy, rho):
    """Collar module vs integral tab: same compliant geometry, plus a flange ring (window + 2 mm) x flange t, per side."""
    if p.retention != "collar":
        return 0.0
    W = collar_window(g, p, bump_xy)
    flange = W.buffer(2.0, join_style=2).area * p.collar_flange
    return 2 * flange * rho * 1e-3


def solid3d_full(g, p: SheathParams, t_knife, bump_xy=None):
    import cadquery as cq
    sol = solid3d(g, p, t_knife)
    if bump_xy is None:
        return sol
    if p.retention == "collar":
        return collar_assembly(g, p, t_knife, bump_xy, sol)
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


def collar_assembly(g, p: SheathParams, t_knife, bump_xy, shell):
    """Swappable collar module: rectangular window through each panel; collar = window-0.1 mm plate (same wall) carrying
    the U-slot tab + bump, with an outer flange (window + 2 mm) that seats on the panel outside face. Returns
    {"shell": ..., "collar_pos": ..., "collar_neg": ...} (separate solids, separate STEP files)."""
    import cadquery as cq
    H = t_knife + 2 * p.c_face + 2 * p.wall; gap = t_knife + 2 * p.c_face
    W = collar_window(g, p, bump_xy)
    def ext(poly, z0, h):
        return cq.Workplane("XY", origin=(0, 0, z0)).polyline(list(poly.exterior.coords)[:-1]).close().extrude(h)
    out = {}
    for side, name in ((+1, "collar_pos"), (-1, "collar_neg")):
        zin = gap / 2 if side > 0 else -H / 2
        shell = shell.cut(ext(W, zin, p.wall))
        plate = ext(W.buffer(-0.1, join_style=2), zin, p.wall)
        zfl = H / 2 if side > 0 else -H / 2 - p.collar_flange
        plate = plate.union(ext(W.buffer(2.0, join_style=2), zfl, p.collar_flange))
        for q in tab_slot_polys(g, p, bump_xy):
            plate = plate.cut(ext(q, min(zin, zfl) - 0.1, p.wall + p.collar_flange + 0.2))
        h = p.detent_undercut; r0 = 1.6; R = (r0 ** 2 + h ** 2) / (2 * h)
        zc = side * (gap / 2 + R - h)
        sph = cq.Workplane("XY").sphere(R).translate((bump_xy[0], bump_xy[1], zc))
        slab = cq.Workplane("XY", origin=(0, 0, gap / 2 - h if side > 0 else -gap / 2)).rect(400, 400).extrude(h)
        out[name] = plate.union(sph.intersect(slab))
    out["shell"] = shell
    return out
