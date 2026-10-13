"""Rebuild tiny CAD fixtures with the pinned CAD environment, from repo root.

The simplified STL is a smoke fixture only. Production ingest always uses the
original verified STL. Vertex clustering retains existing source positions.
"""
import json
from pathlib import Path
import struct

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

from ops.render.marketing.ingest import LEGACY_FIXTURE_SHA256, load_cad, sha256

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    shape = BRepPrimAPI_MakeBox(60, 40, 6).Shape()
    chamfer = BRepFilletAPI_MakeChamfer(shape)
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge = TopoDS.Edge_s(explorer.Current())
        # Box edges parallel to XY form the upper/lower perimeter; the vertical
        # corner edges are left alone. Every chosen edge gets a 1 mm chamfer.
        from OCP.TopAbs import TopAbs_VERTEX
        vex = TopExp_Explorer(edge, TopAbs_VERTEX)
        pts = []
        while vex.More():
            pts.append(BRep_Tool.Pnt_s(TopoDS.Vertex_s(vex.Current())))
            vex.Next()
        if abs(pts[0].Z() - pts[-1].Z()) < 1e-8:
            chamfer.Add(1.0, edge)
        explorer.Next()
    chamfer.Build()
    if not chamfer.IsDone():
        raise RuntimeError("fixture chamfer failed")
    writer = STEPControl_Writer()
    writer.Transfer(chamfer.Shape(), STEPControl_AsIs)
    step_path = HERE / "cube_bevel.step"
    if writer.Write(str(step_path)) != IFSelect_RetDone:
        raise RuntimeError("fixture STEP export failed")
    step_path.write_text("\n".join(line.rstrip() for line in step_path.read_text().splitlines()) + "\n")
    mesh = load_cad(step_path, validated_brep=True)
    # Independent geometric oracle: chamfer interiors have neither a box side
    # coordinate nor a top/bottom coordinate. Keep zero-based source face IDs.
    centers = mesh.V[mesh.F].mean(axis=1) * 1000
    box_plane = np.zeros(len(centers), dtype=bool)
    for axis, bounds in enumerate([(0, 60), (0, 40), (0, 6)]):
        box_plane |= np.isclose(centers[:, axis], bounds[0], atol=1e-6)
        box_plane |= np.isclose(centers[:, axis], bounds[1], atol=1e-6)
    expected = sorted(set(mesh.face_id[~box_plane].tolist()))
    (HERE / "cube_bevel.expected.json").write_text(json.dumps({"chamfer_face_ids": expected,
        "box_mm": [60, 40, 6], "chamfer_mm": 1, "oracle": "centroid lies on none of the six original box planes"}, indent=2) + "\n")
    source = ROOT / "evidence/wave27/g3_tip+00_t60_tt3.stl"
    original = load_cad(source, expected_sha256=LEGACY_FIXTURE_SHA256)
    cell = np.floor(original.V / 0.004).astype(np.int64)
    _, first, inverse = np.unique(cell, axis=0, return_index=True, return_inverse=True)
    V, F = original.V[first], inverse[original.F]
    good = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    F = F[good]
    cross = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    good = np.linalg.norm(cross, axis=1) > 1e-14
    F, cross = F[good], cross[good]
    # Remove duplicate triangles introduced by fixture-only clustering.
    _, first = np.unique(np.sort(F, axis=1), axis=0, return_index=True)
    F, cross = F[np.sort(first)], cross[np.sort(first)]
    normals = cross / np.linalg.norm(cross, axis=1)[:, None]
    dtype = np.dtype([("normal", "<f4", (3,)), ("V", "<f4", (3, 3)), ("attribute", "<u2")])
    data = np.zeros(len(F), dtype=dtype)
    data["normal"], data["V"] = normals, V[F] * 1000
    stl_path = HERE / "tiny_knife.stl"
    stl_path.write_bytes(b"jarambit source-position vertex-cluster smoke fixture".ljust(80, b"\0") + struct.pack("<I", len(F)) + data.tobytes())
    (HERE / "tiny.obj").write_text("# 20 x 10 x 2 mm; polygon triangulation fixture\n"
        "v 0 0 0\nv 20 0 0\nv 20 10 0\nv 0 10 0\nv 0 0 2\nv 20 0 2\nv 20 10 2\nv 0 10 2\n"
        "f 4 3 2 1\nf 5 6 7 8\nf 1 2 6 5\nf 2 3 7 6\nf 3 4 8 7\nf 4 1 5 8\n")
    (HERE / "provenance.json").write_text(json.dumps({"source": str(source.relative_to(ROOT)),
        "source_sha256": LEGACY_FIXTURE_SHA256, "role": "legacy smoke fixture only; not the C.9.2 hero",
        "tiny_knife": {"triangles": len(F), "cluster_mm": 4,
        "sha256": sha256(stl_path), "purpose": "smoke only; preserves selected source positions, loses detail"},
        "cube_bevel": {"sha256": sha256(step_path), "generator": "OCP box + upper/lower perimeter 1 mm chamfer"}}, indent=2) + "\n")


if __name__ == "__main__":
    main()
