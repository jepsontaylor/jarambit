"""Maker's-mark tests: asset integrity, automatic placement on two different CADs + a synthetic
plate, determinism, readability, margin, and the Q15 QA gate."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ops.render.marketing import qa, signature
from ops.render.marketing.ingest import canonical_pose, load_cad

ROOT = Path(__file__).resolve().parents[4]
BRAND = ROOT / "ops" / "render" / "brand" / "signature"
G3_STL = ROOT / "evidence" / "wave27" / "g3_tip+00_t60_tt3.stl"
C93_STL = Path(os.path.expanduser("~/jarambit_render/inputs/switchback_C9.3/switchback_revC9_3_ground.stl"))


def posed(path):
    mesh = load_cad(path)
    R, t = canonical_pose(mesh.V, mesh.F)
    return mesh.V @ R.T + t, mesh.F


def plate_with_hole(L=0.12, H=0.03, T=0.004, hole=(0.0, 0.0, 0.008), n=96):
    """Flat plate (blade plane XZ, thickness Y) with a square hole; side walls make it closed."""
    xs = np.linspace(-L / 2, L / 2, n + 1)
    zs = np.linspace(-H / 2, H / 2, n // 4 + 1)
    V, F = [], []
    hx, hz, hr = hole
    for y, flip in ((-T / 2, True), (T / 2, False)):
        base = len(V)
        for z in zs:
            for x in xs:
                V.append((x, y, z))
        W = len(xs)
        for j in range(len(zs) - 1):
            for i in range(n):
                cx, cz = (xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
                if abs(cx - hx) < hr and abs(cz - hz) < hr:
                    continue
                a, b, c, d = base + j * W + i, base + j * W + i + 1, base + (j + 1) * W + i + 1, base + (j + 1) * W + i
                tris = [(a, b, c), (a, c, d)]
                F += [(t[0], t[2], t[1]) for t in tris] if flip else tris
    return np.array(V), np.array(F)


def _inside_flat(V, F, pl, pts):
    n = np.array(pl["normal"])
    fn, _ = signature._face_normals(V, F)
    sel = F[(fn @ n > 0.9994) & (np.abs(V[F].mean(1) @ n - pl["plane_offset_m"]) < 5e-5)]
    r, u = signature.plane_basis(n)
    P = np.stack([V @ r, V @ u], -1)
    A, B, C = P[sel[:, 0]], P[sel[:, 1]], P[sel[:, 2]]
    out = []
    for p in pts:
        q = np.array([p @ r, p @ u])
        d = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1])
        l1 = ((B[:, 1] - C[:, 1]) * (q[0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (q[1] - C[:, 1])) / d
        l2 = ((C[:, 1] - A[:, 1]) * (q[0] - C[:, 0]) + (A[:, 0] - C[:, 0]) * (q[1] - C[:, 1])) / d
        out.append(bool(np.any((l1 >= -1e-6) & (l2 >= -1e-6) & (l1 + l2 <= 1 + 1e-6))))
    return np.array(out)


def check_placement(V, F, pl, margin_mm=1.5):
    assert pl["ok"], pl
    u, v, n = (np.array(pl[k]) for k in ("u_axis", "v_axis", "normal"))
    assert abs(np.dot(u, v)) < 1e-6 and abs(np.dot(u, n)) < 1e-6
    assert v[2] >= 0, "text must read upright from the camera on that side"
    assert np.allclose(np.cross(n, u), v, atol=1e-6)
    assert pl["width_m"] / pl["height_m"] == pytest.approx(signature.ASPECT, rel=1e-4)
    # the rectangle grown by (margin - one raster cell) must still lie on the flat face
    c = np.array(pl["center_m"])
    m = (margin_mm - 0.15) * 1e-3
    pts = [c + a * u * (pl["width_m"] / 2 + m) + b * v * (pl["height_m"] / 2 + m)
           for a in np.linspace(-1, 1, 9) for b in np.linspace(-1, 1, 5)]
    inside = _inside_flat(V, F, pl, pts)
    assert inside.mean() > 0.97, f"{(~inside).sum()} of {len(pts)} margin probes off the flat face"


def test_asset_manifest_and_constants():
    sums = (BRAND / "SHA256SUMS").read_text().split("\n")
    for line in filter(None, sums):
        sha, name = line.split(None, 1)
        assert hashlib.sha256((BRAND / name.strip()).read_bytes()).hexdigest() == sha, name
    m = np.asarray(Image.open(BRAND / "jepson_t_mask_4096.png").convert("L"), float) / 255
    assert m.shape[1] / m.shape[0] == pytest.approx(signature.ASPECT, rel=1e-9)
    assert m.mean() == pytest.approx(signature.INK_FRACTION, abs=5e-4)
    svg = (BRAND / "jepson_t.svg").read_text()
    assert 'fill="#000000"' in svg and "<rect" not in svg  # single fill, no background
    assert (BRAND / "source" / "jepson_signature_v2_bold.png").is_file()


def test_plate_avoids_hole_and_is_deterministic():
    V, F = plate_with_hole()
    a = signature.place(V, F, {"sides": ["hero", "back"]})
    b = signature.place(V, F, {"sides": ["hero", "back"]})
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    hero, back = a["placements"]
    assert hero["normal"] == [0.0, -1.0, 0.0] and back["normal"] == [0.0, 1.0, 0.0]
    for pl in (hero, back):
        check_placement(V, F, pl)
        assert abs(pl["center_m"][0]) > 0.008 + pl["width_m"] / 2 - 1e-4  # beside the hole, not over it
    assert hero["u_axis"][0] > 0 and back["u_axis"][0] < 0  # left-to-right as seen from each side


@pytest.mark.parametrize("name,path", [("switchback_C9.3", C93_STL), ("g3_tip+00_t60_tt3", G3_STL)])
def test_placement_on_real_cads(name, path):
    if not path.is_file():
        pytest.skip(f"{path} not on this host")
    V, F = posed(path)
    res = signature.place(V, F, {"sides": ["hero", "back"]})
    for pl in res["placements"]:
        check_placement(V, F, pl)
        assert pl["width_m"] >= 0.010, f"{name}: mark under 10 mm wide"
    print(name, json.dumps(res["placements"], sort_keys=True))


def _row(**kw):
    base = {"shot": "hero_3q", "frame": 0, "hero": True, "applied": True, "facing": True,
            "in_frame": True, "expected_px": 400.0, "visible_px": 380.0, "visible_ratio": 0.95}
    base.update(kw)
    return base


def test_q15_gate():
    assert qa.check_q15([_row()])["status"] == "PASS"
    assert qa.check_q15([])["status"] == "FAIL"
    assert qa.check_q15([_row(visible_px=40.0, visible_ratio=0.1)])["status"] == "FAIL"  # occluded
    assert qa.check_q15([_row(facing=False)])["status"] == "FAIL"
    assert qa.check_q15([_row(applied=False, hero=False)])["status"] == "FAIL"  # every shot needs it
    # turntable frames may face away; only hero stills are held to visibility
    assert qa.check_q15([_row(), _row(shot="turntable", hero=False, facing=False, visible_px=0)])["status"] == "PASS"
    res = {"shot_id": "hero_3q", "signature": {"enabled": True, "material": {"applied": True}},
           "frames": [{"index": 0, "signature": {"facing": True, "in_frame": True, "expected_px": 100.0,
                                                 "visible_px": 90.0, "visible_ratio": 0.9}}]}
    assert qa.check_q15(qa.signature_rows([res]))["status"] == "PASS"
