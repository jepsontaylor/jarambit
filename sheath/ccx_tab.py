"""CalculiX (ccx) nonlinear finite-sliding contact benchmark of one click-tab releasing from the knife's guard hole.

Plane-strain slab (one C3D8I layer of thickness b, U3 = 0 everywhere; 2-D CPS elements diverged in ccx 2.21 contact
with out-of-plane residuals), NLGEOM, node-to-surface contact with Coulomb friction (large sliding),
history: seated (bump in hole, zero tab load) -> knife displaced along +x (draw) until the bump rides fully onto the
knife face. Knife = elastic Ti-6Al-4V (E 114 GPa) block driven on its far edges (compliance check vs rigid). Root of the
tab clamped (the sheath shell local stiffness is reported separately by the plate FEM). Units N-mm-s (density unused:
static). Output: axial reaction vs travel (draw curve), peak, work; 3-mesh convergence. Evidence: uncalibrated_fea.

Run inside the sheath container (ccx + python):  python -m sheath.ccx_tab --out DIR [--levels 4,6,9]
"""
import argparse, json, math, os, re, subprocess, sys
import numpy as np


def quad8_block(x_of, y_of, nu, nv, nodes, key):
    """Structured 8-node quads on a mapped block; (u,v) in [0,1]^2 -> (x,y). Node ids shared through `nodes` dict keyed
    by rounded coordinates so adjacent blocks merge."""
    ids = {}
    def nid(u, v):
        x, y = x_of(u, v), y_of(u, v)
        k = (round(x, 6), round(y, 6))
        if k not in nodes:
            nodes[k] = len(nodes) + 1
        return nodes[k]
    els = []
    for i in range(nu):
        for j in range(nv):
            u0, u1, v0, v1 = i / nu, (i + 1) / nu, j / nv, (j + 1) / nv
            um, vm = 0.5 * (u0 + u1), 0.5 * (v0 + v1)
            n = [nid(u0, v0), nid(u1, v0), nid(u1, v1), nid(u0, v1), nid(um, v0), nid(u1, vm), nid(um, v1), nid(u0, vm)]
            els.append((n, i, j))
    return els


def quad4_block(x_of, y_of, nu, nv, nodes):
    def nid(u, v):
        k = (round(x_of(u, v), 6), round(y_of(u, v), 6))
        if k not in nodes:
            nodes[k] = len(nodes) + 1
        return nodes[k]
    return [([nid(i / nu, j / nv), nid((i + 1) / nu, j / nv), nid((i + 1) / nu, (j + 1) / nv), nid(i / nu, (j + 1) / nv)], i, j)
            for i in range(nu) for j in range(nv)]


def build_deck(L=13.0, b=9.0, t=2.0, h=1.3, c_face=0.25, a_in=30.0, a_out=25.0, wb=0.6, mu=0.30, E=1800.0, nu=0.38,
               level=6, travel=None, chamfer=0.3, K_pen=None, ctype="S2S", inc=(0.002, 0.005), fillet_n=3):
    nodes = {}
    xb = min(L - 2.0, L - wb / 2 - h / math.tan(math.radians(a_in)) - 0.2)   # bump must sit on the tab
    xl_top = xb - wb / 2 - h / math.tan(math.radians(a_out))
    xr_top = xb + wb / 2 + h / math.tan(math.radians(a_in))
    ny = level; hx = t / ny
    def nseg(a, b_): return max(1, int(round((b_ - a) / hx)))
    els = []; faces_m = []   # (index in els, face label) for the master (tab/bump) surface
    for (x0, x1) in ((0.0, xl_top), (xl_top, xr_top), (xr_top, L)):
        if x1 - x0 > 1e-6:
            blk = quad4_block(lambda u, v, x0=x0, x1=x1: x0 + u * (x1 - x0), lambda u, v: v * t, nseg(x0, x1), ny, nodes)
            if x0 > 0 and abs(x0 - xl_top) > 1e-9 or x0 == 0.0:
                faces_m += [(len(els) + k, "S3") for k, (n, i, j) in enumerate(blk) if j == 0 and not (abs(x0 - xl_top) < 1e-9)]
            els += blk
    nb_u = nseg(xl_top, xr_top); nb_v = max(2, int(round(h / hx)))
    def bx(u, v):
        y = -h * (1 - v)
        xl = xb - wb / 2 - (y + h) / math.tan(math.radians(a_out))
        xr = xb + wb / 2 + (y + h) / math.tan(math.radians(a_in))
        return xl + u * (xr - xl)
    blk = quad4_block(bx, lambda u, v: -h * (1 - v), nb_u, nb_v, nodes)
    for k, (n, i, j) in enumerate(blk):
        if j == 0: faces_m.append((len(els) + k, "S3"))
        if i == 0: faces_m.append((len(els) + k, "S6"))
        if i == nb_u - 1: faces_m.append((len(els) + k, "S4"))
    els += blk
    yk = -c_face
    xc = xb - wb / 2 - (h - c_face) / math.tan(math.radians(a_out)) - 0.03
    kx0 = xc - 14.0; kd = 2.0
    nkx = max(8, int(14.0 / (hx * 1.5))); nky = max(3, int(kd / (hx * 1.5)))
    kn = {}
    kel = quad4_block(lambda u, v: kx0 + u * (xc - kx0), lambda u, v: yk - kd + v * kd, nkx, nky, kn)
    off = len(nodes)
    inv = {v: k for k, v in nodes.items()}; kinv = {v + off: k for k, v in kn.items()}
    # round the knife's hole-wall corner (radius `chamfer`): nodes within the radius on the top face / wall are projected
    # onto the fillet arc so the contact sees a smooth convex slave (a sharp corner chatters between master facets)
    rc = chamfer; cx, cy = xc - rc, yk - rc
    for i_, (x, y) in list(kinv.items()):
        if x > cx - 1e-9 and y > cy - 1e-9 and (abs(y - yk) < 1e-9 or abs(x - xc) < 1e-9):
            ang = math.atan2(y - cy, x - cx); kinv[i_] = (cx + rc * math.cos(ang), cy + rc * math.sin(ang))
    allxy = dict(inv); allxy.update(kinv)
    NN = max(allxy)
    lines = ["*HEADING", "jarambit sheath click-tab release (uncalibrated_fea)", "*NODE"]
    for i_ in sorted(allxy):
        x, y = allxy[i_]
        lines.append("%d, %.6f, %.6f, 0" % (i_, x, y)); lines.append("%d, %.6f, %.6f, %.6f" % (i_ + NN, x, y, b))
    def hexa(n): return n + [x + NN for x in n]
    eid = 1; ek = []
    lines.append("*ELEMENT, TYPE=C3D8I, ELSET=TAB")
    for n, _, _ in els:
        lines.append("%d, %s" % (eid, ", ".join(map(str, hexa(n))))); eid += 1
    lines.append("*ELEMENT, TYPE=C3D8I, ELSET=KNIFE")
    for n, i, j in kel:
        nn = [x + off for x in n]
        lines.append("%d, %s" % (eid, ", ".join(map(str, hexa(nn))))); ek.append((eid, i, j)); eid += 1
    both = lambda ids: ids + [x + NN for x in ids]
    root = both([i_ for i_, (x, y) in inv.items() if abs(x) < 1e-9])
    drv = both([i_ for i_, (x, y) in kinv.items() if abs(y - (yk - kd)) < 1e-9 or abs(x - kx0) < 1e-9])
    slave = both([i_ for i_, (x, y) in kinv.items() if abs(y - yk) < 1e-9 or abs(x - xc) < 1e-6 or (abs(x - (xc - chamfer)) < 1e-6 and abs(y - yk) < 1e-9)])
    alln = both(sorted(allxy))
    def nset(name, ids): return ["*NSET, NSET=%s" % name] + [", ".join(map(str, ids[k:k + 12])) for k in range(0, len(ids), 12)]
    lines += nset("ROOT", root) + nset("KDRV", drv) + nset("SLV", slave) + nset("ALLN", alln)
    # slave = knife top + hole-wall nodes (incl. the chamfered corner); master = smooth tab/bump faces (N2S: the convex
    # corner must be the slave, else it pokes through the slave face between nodes)
    lines.append("*SURFACE, NAME=MASTER, TYPE=ELEMENT")
    for k, lab in faces_m:
        lines.append("%d, %s" % (k + 1, lab))
    K_pen = K_pen or 5.0 * E
    if ctype == "S2S":
        lines.append("*SURFACE, NAME=SLAVE, TYPE=ELEMENT")
        for e, i, j in ek:
            if j == nky - 1: lines.append("%d, S5" % e)
            if i == nkx - 1: lines.append("%d, S4" % e)
    else:
        lines += ["*SURFACE, NAME=SLAVE, TYPE=NODE", "SLV"]
    lines += [
              "*MATERIAL, NAME=PA12", "*ELASTIC", "%g, %g" % (E, nu),
              "*MATERIAL, NAME=TI", "*ELASTIC", "114000, 0.34",
              "*SOLID SECTION, ELSET=TAB, MATERIAL=PA12", "*SOLID SECTION, ELSET=KNIFE, MATERIAL=TI",
              "*SURFACE INTERACTION, NAME=SI", "*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=LINEAR", "%g" % K_pen] + \
             (["*FRICTION", "%g, %g" % (mu, K_pen)] if mu > 0 else []) + \
             ["*CONTACT PAIR, INTERACTION=SI, TYPE=%s" % ("SURFACE TO SURFACE" if ctype == "S2S" else "NODE TO SURFACE"), "SLAVE, MASTER"]
    travel = travel or (h / math.tan(math.radians(a_out)) + wb + 1.5)
    lines += ["*STEP, NLGEOM, INC=4000", "*STATIC", "%g, 1.0, 1e-8, %g" % inc,
              "*BOUNDARY", "ALLN, 3, 3, 0", "ROOT, 1, 2, 0", "KDRV, 1, 1, %g" % travel, "KDRV, 2, 2, 0",
              "*NODE PRINT, NSET=KDRV, TOTALS=ONLY", "RF", "*END STEP"]
    meta = {"L": L, "b": b, "t": t, "h": h, "c_face": c_face, "a_in": a_in, "a_out": a_out, "wb": wb, "mu": mu, "E": E, "nu": nu,
            "level": level, "travel": travel, "n_nodes": 2 * len(allxy), "n_el": eid - 1, "xb": xb, "K_pen": K_pen,
            "element": "C3D8I plane-strain slab", "ctype": ctype, "fillet_r": chamfer}
    return "\n".join(lines) + "\n", meta


def parse_dat(path):
    txt = open(path).read()
    t = [float(x) for x in re.findall(r"total force \(fx,fy,fz\) for set KDRV and time\s+([0-9.Ee+-]+)", txt)]
    blocks = re.findall(r"total force \(fx,fy,fz\) for set KDRV and time\s+[0-9.Ee+-]+\s*\n\s*([-0-9.Ee+ ]+)\n", txt)
    F = [list(map(float, b.split()))[:2] for b in blocks]
    return np.array(t), np.array(F)


def analytic(meta):
    a = meta["xb"]; E = meta["E"]; b = meta["b"]; t = meta["t"]
    k = 3 * E / (1 - meta["nu"] ** 2) * (b * t ** 3 / 12) / a ** 3       # plane-strain beam at the bump (matches the slab)
    i = meta["h"] - meta["c_face"]
    ta = math.tan(math.radians(meta["a_out"])); mu = meta["mu"]
    P = k * i
    # Bayer formula assumes the ramp keeps its as-moulded angle; the tab tip rotates by theta = 1.5 i / a (cantilever end
    # slope) while it is lifted, so the effective release angle at peak deflection is alpha - theta (Bayer/Covestro snap-fit
    # guide notes the angle change of long beams; quantified here, checked against ccx)
    th = 1.5 * i / a; tr = math.tan(math.radians(meta["a_out"]) - th)
    return {"k_beam": k, "P": P, "W_bayer": P * (mu + ta) / (1 - mu * ta), "theta_tip_deg": math.degrees(th),
            "W_bayer_rot": P * (mu + tr) / (1 - mu * tr)}


def run(out, levels=(3, 4, 6, 8), ccx="ccx", **kw):
    os.makedirs(out, exist_ok=True)
    res = {"evidence_level": "uncalibrated_fea", "solver": None, "levels": []}
    try:
        res["solver"] = subprocess.run([ccx, "-v"], capture_output=True, text=True).stdout.strip()[:200]
    except Exception as e:
        res["solver"] = "unavailable: %r" % e
    for lv in levels:
        deck, meta = build_deck(level=lv, **kw)
        job = os.path.join(out, "tab_l%d" % lv)
        open(job + ".inp", "w").write(deck)
        r = subprocess.run([ccx, "-i", os.path.basename(job)], cwd=out, capture_output=True, text=True)
        ok = os.path.exists(job + ".dat")
        rec = {"level": lv, "meta": meta, "ccx_rc": r.returncode, "log_tail": r.stdout[-600:]}
        if ok:
            tt, F = parse_dat(job + ".dat")
            if len(tt):
                x = tt * meta["travel"]; fx = -F[:, 0]
                rec.update({"peak_n_per_tab": float(np.max(np.abs(fx))), "work_nmm": float(np.trapezoid(np.abs(fx), x)),
                            "completed": bool(abs(tt[-1] - 1.0) < 1e-6), "n_inc": int(len(tt))})
                np.savetxt(job + "_curve.csv", np.c_[x, fx, -F[:, 1]], delimiter=",", header="travel_mm,Fx_n,Fy_n", comments="")
        res["levels"].append(rec)
    an = analytic(res["levels"][-1]["meta"])
    res["analytic"] = an
    pk = [l.get("peak_n_per_tab") for l in res["levels"] if l.get("peak_n_per_tab")]
    if len(pk) >= 2:
        res["conv_rel_last2"] = abs(pk[-1] / pk[-2] - 1)
        res["ccx_over_bayer"] = pk[-1] / an["W_bayer"]
        res["ccx_over_bayer_rot"] = pk[-1] / an["W_bayer_rot"]
    json.dump(res, open(os.path.join(out, "ccx_tab.json"), "w"), indent=1, default=float)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--levels", default="3,4,6,8")
    ap.add_argument("--params", default=None, help="json of build_deck kwargs (e.g. from metrics.json params)")
    a = ap.parse_args()
    kw = json.loads(a.params) if a.params else {}
    r = run(a.out, tuple(int(x) for x in a.levels.split(",")), **kw)
    print(json.dumps({k: r.get(k) for k in ("solver", "analytic", "conv_rel_last2", "ccx_over_bayer", "ccx_over_bayer_rot")}, indent=1, default=float))
    for l in r["levels"]: print(l["level"], l.get("peak_n_per_tab"), l.get("completed"), l.get("n_inc"), l["ccx_rc"])
