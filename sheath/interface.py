"""KnifeInterfaceV1 contract + two adapters (exact STEP, crescent Pheno direct).

Rules: units mm; frame = part XY plane, thickness Z. Every safety-relevant field is either evidence or null; a null
or unapproved field makes the dependent verdict INCOMPLETE — never PASS. All declared sharp boundaries (edge_in, edge_sp,
tip zone, auto-detected) are hazards; the spine is never assumed safe. Retention/seating may ONLY use lands listed in a
human-approved annotation file bound to the source hash.
"""
import hashlib, json, math
import numpy as np

SCHEMA = "jarambit.sheath.knife_interface.v1"
REQUIRED = ["schema", "source", "units", "frame", "planform", "holes", "ring", "tip", "sharp_regions",
            "retention_lands", "seating_lands", "keepouts", "tessellation_error_mm", "mass_g"]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_annotations(path, source_sha):
    """Annotation file must name the same source sha; approval requires reviewer + date. Returns (lands, status)."""
    if path is None:
        return None, "INCOMPLETE: no annotation file"
    with open(path) as f:
        a = json.load(f)
    if a.get("source_sha256") != source_sha:
        return None, "INCOMPLETE: annotation bound to a different source hash"
    st = a.get("review", {})
    approved = st.get("approved") is True and bool(st.get("reviewer")) and bool(st.get("date"))
    if not approved:
        return None, "INCOMPLETE: annotation PROPOSED, awaiting human approval"
    return a, "APPROVED"


def from_step(step_path, stl_path, annotation_path=None):
    from sheath.ingest import ingest
    raw, mesh, P = ingest(step_path, stl_path)
    sha = raw["source"]["step_sha256"]
    ann, status = load_annotations(annotation_path, sha)
    tess = tessellation_error(step_path, mesh)
    # declared-sharp boundary arcs from the annotation (geometry that is modelled with an edge flat but is a cutting edge:
    # rule — every cutting edge is sharp with ~0 edge width, so only explicitly non-cutting geometry can be a land)
    extra = []
    if ann:
        ring = P.exterior
        bnd = np.array([ring.interpolate(t).coords[0] for t in np.arange(0, ring.length, 0.5)])
        for d in ann.get("declared_sharp") or []:
            (x0, x1), (y0, y1) = d["x_range"], d["y_range"]
            sel = bnd[(bnd[:, 0] >= x0) & (bnd[:, 0] <= x1) & (bnd[:, 1] >= y0) & (bnd[:, 1] <= y1)]
            if len(sel):
                extra.append({"name": d["name"], "origin": "annotation.declared_sharp: " + d.get("why", ""), "pts": sel.tolist()})
    iface = {
        "schema": SCHEMA, "source": {"kind": "step", **raw["source"]}, "units": "mm", "frame": raw["frame"],
        "planform": raw["planform"], "holes": raw["holes"], "ring": raw["ring"], "tip": raw["tip"], "t_max_mm": raw["t_max_mm"],
        "sharp_regions": [{"name": "auto_%d" % i, "origin": "thickness_probe<1.0mm@0.6mm + 6mm tip zone", "pts": r["pts"]}
                          for i, r in enumerate(raw["sharp_runs"])] + extra,
        "retention_lands": ann.get("retention_lands") if ann else None,
        "seating_lands": ann.get("seating_lands") if ann else None,
        "keepouts": (ann.get("keepouts") if ann else None) or [{"name": "grip+ring", "x_max": 60.0, "origin": "default"}],
        "annotation_status": status, "approved_annotations": ann,
        "tessellation_error_mm": tess, "mass_g": raw["brep"].get("mass_g_ti64"),
        "brep": raw["brep"],
    }
    return iface, mesh, P


def tessellation_error(step_path, mesh, n=400, seed=0):
    """Max distance of sampled STL vertices to the B-rep (OCC). null if OCC unavailable."""
    try:
        import cadquery as cq
        s = cq.importers.importStep(step_path).val()
        idx = np.random.default_rng(seed).choice(len(mesh.vertices), size=min(n, len(mesh.vertices)), replace=False)
        d = [s.distance(cq.Vertex.makeVertex(*map(float, mesh.vertices[i]))) for i in idx]
        return {"max": float(max(d)), "p95": float(np.percentile(d, 95)), "n": len(d), "method": "STL vertex -> B-rep distance"}
    except Exception as e:
        return None


def from_pheno(ph: dict):
    """Crescent Pheno (crates/crescent) direct adapter. Uses the FULL `outline` (with scallops/jimping), never
    `macro_outline`. edge_in AND edge_sp are both declared sharp. Thickness is uniform t (plate)."""
    from shapely.geometry import Polygon
    P = Polygon(ph["outline"], [h for h in ph.get("holes", [])])
    holes = []
    for k, h in enumerate(ph.get("holes", [])):
        hp = Polygon(h); c = hp.centroid
        holes.append({"name": (ph.get("hole_names") or [None] * 99)[k], "centroid": [c.x, c.y], "area_mm2": hp.area,
                      "eq_radius_mm": math.sqrt(hp.area / math.pi)})
    ring = max(holes, key=lambda h: h["area_mm2"]) if holes else None
    sharp = [{"name": "edge_in", "origin": "Pheno.edge_in", "pts": ph["edge_in"]},
             {"name": "edge_sp", "origin": "Pheno.edge_sp (sharpened spine portion)", "pts": ph["edge_sp"]}]
    tip = ph["tip"]
    sharp.append({"name": "tip_zone", "origin": "Pheno.tip + 6 mm", "pts": [tip]})
    src = _sha(json.dumps(ph, sort_keys=True).encode())
    return {
        "schema": SCHEMA, "source": {"kind": "crescent_pheno", "pheno_sha256": src}, "units": "mm",
        "frame": "Pheno XY, thickness Z", "planform": {"exterior": list(map(list, P.exterior.coords)),
                                                       "interiors": [list(map(list, r.coords)) for r in P.interiors], "area_mm2": P.area},
        "holes": holes, "ring": ring, "tip": tip, "t_max_mm": ph["t"], "sharp_regions": sharp,
        "retention_lands": None, "seating_lands": None, "keepouts": [{"name": "grip+ring", "x_max": None, "origin": "TBD from Pheno.field"}],
        "annotation_status": "INCOMPLETE: no annotation for this genome", "tessellation_error_mm": 0.0, "mass_g": ph.get("mass_g"),
    }


def validate(iface: dict):
    """Return (ok, verdict dict). Missing evidence -> INCOMPLETE with the missing keys."""
    missing = [k for k in REQUIRED if k not in iface]
    nulls = [k for k in REQUIRED if k in iface and iface[k] is None]
    if missing:
        return False, {"outcome": "fail", "reasons": ["missing keys: %s" % missing]}
    if iface["schema"] != SCHEMA:
        return False, {"outcome": "fail", "reasons": ["schema"]}
    if not iface["sharp_regions"]:
        return False, {"outcome": "fail", "reasons": ["no sharp regions declared — refuse (a knife always has some)"]}
    ann = iface.get("approved_annotations")
    approved = (isinstance(ann, dict) and bool(ann.get("source_sha256")) and ann.get("source_sha256") == iface.get("source", {}).get("step_sha256")
                and ann.get("review", {}).get("approved") is True
                and bool(ann.get("review", {}).get("reviewer")) and bool(ann.get("review", {}).get("date")))
    if nulls or iface.get("annotation_status") != "APPROVED" or not approved:
        return True, {"outcome": "incomplete", "missing": nulls + ([] if approved else ["approved_annotations"])}
    return True, {"outcome": "pass"}
