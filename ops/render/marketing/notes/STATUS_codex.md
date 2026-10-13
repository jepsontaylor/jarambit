# Codex CAD lane status

Implemented ingest, region segmentation, camera fit, fixtures and pinned CAD
dependencies on `render/codex-cad-mesh`. No PR opened or merged.

The production hero is **SWITCHBACK Rev C.9.2**, from the owner-pinned STEP
`~/jarambit_render/inputs/switchback_C9.2/switchback_revC9_2_ground.step`.
Source SHA256: `2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307`.
The separately pinned C.9.2 STL is supported as an explicit input; ingest never
falls back to it. The legacy g3 source remains only a fixture regression input.

Regions v2 is ready at `~/jarambit_render_scratch/hero_C9.2/mesh_regions_v2/`.
The original production `mesh/` directory is untouched. Its `mesh.npz` and
`bundle.json` are copied byte-identically into v2. Corrected labels/tangents are
external NPY overrides; Claude/Grok must load them before pose/region targets
using `region_io.apply_region_overrides`. See `REGIONS_v2.md` for the exact call.
Labels SHA: `219a10369e9cb3fb02b09f8c4405725a1b48bbe8a6c584f28a16ade7ea6125e0`.
Both front/back and oblique overlay PNGs are included in v2.

Original production bundle: `~/jarambit_render_scratch/hero_C9.2/mesh/` contains `bundle.json`,
`mesh.npz`, `regions.json`, `regions_debug.png`, and `framing.json`.
NPZ SHA256: `062be78fe0828a5f0fc5f2e20e2f4ed07f2d9ffa07741b0645fbb053aa232228`.
There are 50,980 vertices and 101,972 triangles, with analytic B-rep corner normals.
The final path and hashes are posted in the shared COORD log for Claude/Grok.

Current validation: **57 pytest tests passed, zero skips**, plus all 17 repository gates
(workspace release tests, Clippy, D1 smoke, version/generated-doc/media/evidence
checks and existing Python suites). Region v2 annotated STEP face patch IoU is
**1.0** for body, bevel, ring details, serration and finite apex; label/tangent
reruns are identical. All five original production file hashes still match.
See `REGIONS_v2_validation.json`. The earlier production CAD gate passed in 207 s:
repeated bundle/region/overlay bytes identical; geometry round-trip error
`5.55e-17 m`; chamfer IoU **1.0**; 36 turntable angles at 3840×2160 have minimum
margin **14.51%**, with maximum width fill **70%**. See `CAD_validation.json`.

Canonical pose is X length, Z height, blade plane XZ, front -Y, ring left.
Camera az=0 is on -Y; az=90 is +X; angles/roll are degrees. One distance is used
for every frame. Width fill targets the widest frame; end-on frames are narrower.
STEP topology uses a 1 nm tolerance ceiling; mesh-format seam welding is analysis
only. Source vertex positions are never averaged, smoothed or repaired.

The selected C.9.2 CAD is one closed solid with **four holes** (Euler -6), not
the plan's genus-one assumption. Geometry is preserved. V2 uses analytic B-rep
faces first: bore and coaxial ridges, ruled grinds, conical wheel patches, and thin
edge lands. A broad handle plane stays body; pad labels require exporter tags.
I inspected the v2 overlays; owner art review remains **pending**.

Environment: Python 3.12 venv `~/jarambit_render/venv-cad`, installed using uv.
Reproduce portable checks with that venv's `python -m pytest ops/render/marketing/tests`.
Reproduce v2 validation with `python -m ops.render.marketing.notes.validate_regions_v2
--base ~/jarambit_render_scratch/hero_C9.2/mesh --v2 ~/jarambit_render_scratch/hero_C9.2/mesh_regions_v2`.
Missing inputs/tools fail. Re-ingest experiments must use a new scratch output.
Default ingest: `python -m ops.render.marketing.ingest --validated-brep --out DIR`.
Generic CAD: `python -m ops.render.marketing.ingest INPUT --out DIR [--units mm]`.
Face tags use `<cad-stem>.regions.json`, `{"faces":{"0":"bevel"}}`, with zero-based
source face IDs. `--pose pose.json` accepts rigid `R,t`, translation in metres.

The owner-added root `COORD.md` modification is outside this lane's commit.
The authoritative append-only coordination log is `~/jarambit_v1work/COORD.md`.
