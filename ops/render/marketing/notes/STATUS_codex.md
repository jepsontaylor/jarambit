# Codex CAD lane status

Implemented ingest, region segmentation, camera fit, fixtures and pinned CAD
dependencies on `render/codex-cad-mesh`. No PR opened or merged.

The production hero is **SWITCHBACK Rev C.9.2**, from the owner-pinned STEP
`~/jarambit_render/inputs/switchback_C9.2/switchback_revC9_2_ground.step`.
Source SHA256: `2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307`.
The separately pinned C.9.2 STL is supported as an explicit input; ingest never
falls back to it. The legacy g3 source remains only a fixture regression input.

Ready bundle: `~/jarambit_render_scratch/hero_C9.2/mesh/` contains `bundle.json`,
`mesh.npz`, `regions.json`, `regions_debug.png`, and `framing.json`.
NPZ SHA256: `062be78fe0828a5f0fc5f2e20e2f4ed07f2d9ffa07741b0645fbb053aa232228`.
There are 50,980 vertices and 101,972 triangles, with analytic B-rep corner normals.
The final path and hashes are posted in the shared COORD log for Claude/Grok.

Validation: **47 pytest tests passed, zero skips**, plus all 16 repository gates
(workspace release tests, Clippy, D1 smoke, version/generated-doc/media/evidence
checks and existing Python suites). The production CAD gate passed in 207 s:
repeated bundle/region/overlay bytes identical; geometry round-trip error
`5.55e-17 m`; chamfer IoU **1.0**; 36 turntable angles at 3840×2160 have minimum
margin **14.51%**, with maximum width fill **70%**. See `CAD_validation.json`.

Canonical pose is X length, Z height, blade plane XZ, front -Y, ring left.
Camera az=0 is on -Y; az=90 is +X; angles/roll are degrees. One distance is used
for every frame. Width fill targets the widest frame; end-on frames are narrower.
STEP topology uses a 1 nm tolerance ceiling; mesh-format seam welding is analysis
only. Source vertex positions are never averaged, smoothed or repaired.

The selected C.9.2 CAD is one closed solid with **four holes** (Euler -6), not
the plan's genus-one assumption. Geometry is preserved. Pad boundaries and
serration segmentation remain appearance heuristics unless face tags are supplied.
I inspected both region overlays; owner art review remains **pending**.

Environment: Python 3.12 venv `~/jarambit_render/venv-cad`, installed using uv.
Reproduce portable checks with that venv's `python -m pytest ops/render/marketing/tests`.
Reproduce the production gate with `python -m ops.render.marketing.notes.validate_cad
--out ~/jarambit_render_scratch/hero_C9.2`; missing inputs/tools fail.
Default ingest: `python -m ops.render.marketing.ingest --validated-brep --out DIR`.
Generic CAD: `python -m ops.render.marketing.ingest INPUT --out DIR [--units mm]`.
Face tags use `<cad-stem>.regions.json`, `{"faces":{"0":"bevel"}}`, with zero-based
source face IDs. `--pose pose.json` accepts rigid `R,t`, translation in metres.

The owner-added root `COORD.md` modification is outside this lane's commit.
The authoritative append-only coordination log is `~/jarambit_v1work/COORD.md`.
