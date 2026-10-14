"""Synthetic fixtures. These are controls, not knife geometry."""

import numpy as np
import trimesh


SYNTHETIC_LABEL = "SYNTHETIC_NOT_A_KNIFE"


def _label(mesh, defect=None):
    mesh.metadata["synthetic"] = SYNTHETIC_LABEL
    if defect is not None:
        mesh.metadata["planted_defect"] = defect
    return mesh


def analytic_box(extents_mm=(10.0, 20.0, 30.0)):
    """Closed box. Volume is the product of the three edge lengths."""
    return _label(trimesh.creation.box(extents=extents_mm))


def open_box(extents_mm=(10.0, 20.0, 30.0)):
    """Box with one face removed. A planted boundary, not a repair target."""
    mesh = analytic_box(extents_mm)
    mesh.faces = mesh.faces[:-2]
    return _label(mesh, "boundary")


def inverted_box(extents_mm=(10.0, 20.0, 30.0)):
    """Closed box with inward winding. Signed volume is negative."""
    mesh = analytic_box(extents_mm)
    mesh.invert()
    return _label(mesh, "inverted")


def two_closed_boxes():
    """Two disjoint closed boxes. Watertight does not make them one solid."""
    left = analytic_box((10.0, 20.0, 30.0))
    right = analytic_box((4.0, 5.0, 6.0))
    right.apply_translation([100.0, 0.0, 0.0])
    mesh = trimesh.util.concatenate([left, right])
    return _label(mesh, "disconnected_components")


def near_coincident_gap(offset_mm=1e-9):
    """One box corner split by a gap smaller than trimesh's default weld.

    Exact coordinate merging must leave the boundary. Rounded merging hides it.
    """
    mesh = analytic_box()
    vertices = np.vstack([mesh.vertices, mesh.vertices[0] + np.array([offset_mm, 0.0, 0.0])])
    faces = mesh.faces.copy()
    faces[0] = np.where(faces[0] == 0, len(mesh.vertices), faces[0])
    gapped = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    gapped.metadata["offset_mm"] = offset_mm
    return _label(gapped, "near_coincident_gap")


def degenerate_face():
    """Three collinear vertices. Area is zero."""
    vertices = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]], dtype=float)
    faces = np.array([[0, 1, 2]], dtype=int)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return _label(mesh, "degenerate")


def nonmanifold_edge():
    """Three triangles share one edge."""
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [-1.0, 0.0, 0.0],
        ],
        dtype=float,
    )
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 1, 4]], dtype=int)
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return _label(mesh, "nonmanifold_edge")


def nonfinite_triangle():
    mesh = analytic_box()
    mesh.vertices[0, 0] = np.nan
    return _label(mesh, "nonfinite")
