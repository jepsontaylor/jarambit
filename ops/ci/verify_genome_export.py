"""Read STEP topology and fit the separate mesh's meridians; construction metadata is not an oracle."""
from __future__ import annotations
import json
import math
from pathlib import Path

TAU = 2 * math.pi
CAD_TOL = 1e-7  # Coordinate fitting tolerance, never a requirement waiver.


def mesh_bore_profiles(surface: dict) -> list[dict]:
    import numpy as np
    verts = surface['verts']
    inner = min(math.hypot(x, y) for x, y, _ in verts)
    rows = {}
    for x, y, z in verts:
        theta = math.atan2(y, x) % TAU
        rows.setdefault(round(theta * 1e8), []).append((math.hypot(x, y), z))
    fitted = []
    sectors = {1: set(), -1: set()}
    for theta, points in rows.items():
        if min(r for r, _ in points) > inner + CAD_TOL:
            continue
        for side in [1, -1]:
            arc = sorted(set((r, abs(z)) for r, z in points if z * side > 0))[:17]
            if len(arc) < 17 or abs(arc[0][0] - inner) > CAD_TOL:
                raise ValueError('mesh lacks a complete bore roll on both faces')
            a = np.array(arc)
            cx, cz, k = np.linalg.lstsq(np.column_stack([2*a[:, 0], 2*a[:, 1], np.ones(17)]),
                                       (a*a).sum(axis=1), rcond=None)[0]
            radius = math.sqrt(max(0., k + cx*cx + cz*cz))
            if (radius <= 0 or np.max(np.abs(np.hypot(a[:, 0]-cx, a[:, 1]-cz)-radius)) > CAD_TOL
                    or abs(cx-inner-radius) > CAD_TOL or abs(cz-arc[0][1]) > CAD_TOL
                    or abs(arc[-1][0]-cx) > CAD_TOL or abs(arc[-1][1]-cz-radius) > CAD_TOL):
                raise ValueError('mesh meridian is not a complete circular quarter roll')
            angle = theta / 1e8
            sectors[side].add(min(71, int(angle / TAU * 72)))
            fitted.append(dict(theta=angle, side=side, major_radius_mm=float(cx),
                               minor_radius_mm=radius, center_z_mm=float(side*cz)))
    if any(len(x) != 72 for x in sectors.values()):
        raise ValueError('mesh bore does not cover the full circle on both faces')
    return fitted


def covered(intervals: list[tuple[float, float]]) -> bool:
    parts = []
    for start, width in intervals:
        start %= TAU
        if width < 0 or width > TAU + CAD_TOL:
            return False
        end = start + width
        parts.append((start, min(end, TAU)))
        if end > TAU:
            parts.append((0., end-TAU))
    end = 0.
    for a, b in sorted(parts):
        if a > end + CAD_TOL:
            return False
        end = max(end, b)
    return end >= TAU - CAD_TOL


def compare_bore(faces: list[dict], profiles: list[dict]) -> dict:
    intervals = {1: [], -1: []}
    matches = bool(faces and profiles)
    for face in faces:
        side = 1 if face['center_z_mm'] > 0 else -1
        start, width = face['angle_start'], face['angle_width']
        intervals[side].append((start, width))
        selected = [p for p in profiles if p['side'] == side
                    and (p['theta']-start) % TAU <= width + CAD_TOL]
        matches &= bool(selected) and math.hypot(*face['center_xy_mm']) <= CAD_TOL
        matches &= abs(abs(face['axis_z'])-1) <= CAD_TOL
        for p in selected:
            matches &= all(abs(face[k]-p[k]) <= CAD_TOL
                           for k in ['major_radius_mm', 'minor_radius_mm', 'center_z_mm'])
    coverage = {str(side): covered(intervals[side]) for side in [1, -1]}
    return {'bore_geometry_matches_mesh': bool(matches and all(coverage.values())),
            'full_circle_coverage': coverage}


def inspect_step(path: Path, surface_path: Path | None = None) -> dict:
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Torus
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone or reader.NbRootsForTransfer() != 1:
        raise ValueError('exported STEP has no unique transferable CAD root')
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise ValueError('exported STEP is empty')
    valid = bool(BRepCheck_Analyzer(shape).IsValid())
    solids = 0
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solids += 1
        explorer.Next()
    faces = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        surface = BRepAdaptor_Surface(TopoDS.Face_s(explorer.Current()), True)
        if surface.GetType() == GeomAbs_Torus:
            torus = surface.Torus()
            position = torus.Location()
            axis_z = float(torus.Axis().Direction().Z())
            xaxis = torus.XAxis().Direction()
            phase = math.atan2(xaxis.Y(), xaxis.X())
            lo, hi = surface.FirstUParameter(), surface.LastUParameter()
            faces.append({'minor_radius_mm': float(torus.MinorRadius()),
                          'major_radius_mm': float(torus.MajorRadius()), 'center_z_mm': float(position.Z()),
                          'center_xy_mm': [float(position.X()), float(position.Y())],
                          'axis_z': axis_z, 'angle_start': (phase + (lo if axis_z > 0 else -hi)) % TAU,
                          'angle_width': float(hi-lo)})
        explorer.Next()
    comparison = {'bore_geometry_matches_mesh': False, 'full_circle_coverage': {}}
    if surface_path is not None:
        try:
            comparison = compare_bore(faces, mesh_bore_profiles(json.loads(surface_path.read_text())))
        except (ValueError, KeyError, TypeError) as exc:
            comparison['bore_validation_error'] = str(exc)
    return {'reader': 'OpenCascade STEP reader + BRepCheck_Analyzer + independent mesh circle fits',
            'valid': valid, 'solids': solids,
            'bore_rolls_on_both_faces': bool(any(f['center_z_mm'] > 0 for f in faces)
                                           and any(f['center_z_mm'] < 0 for f in faces)),
            'bore_edge_radius_mm': min((f['minor_radius_mm'] for f in faces), default=None),
            'toroidal_faces': faces, **comparison}
