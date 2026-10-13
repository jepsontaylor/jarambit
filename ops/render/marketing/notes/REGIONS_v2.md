# C.9.2 region revision 2

Output: `~/jarambit_render_scratch/hero_C9.2/mesh_regions_v2/`.
The production `mesh/` directory is untouched. Both `mesh.npz` and `bundle.json`
are copied byte for byte. NPZ SHA remains
`062be78fe0828a5f0fc5f2e20e2f4ed07f2d9ffa07741b0645fbb053aa232228`.

Corrected labels SHA (raw uint8 array):
`219a10369e9cb3fb02b09f8c4405725a1b48bbe8a6c584f28a16ade7ea6125e0`.
The labels live in `region_id.npy`; `tangent.npy` provides the associated finish
directions. `regions.json` retains schema v1 and adds `revision: 2`, the base NPZ
pin and hashed `attribute_overrides`. Its JSON hash must enter the next plan key.

Classification now reads the original STEP's analytic face types and axes before
using surface normals: concave bore plus coaxial ring details -> ring; conical
wheel patches -> serration; ruled BSpline grinds -> bevel; finite thin edge lands
adjacent to grinds -> edge apex. Exporter face tags take precedence. Untagged broad
handle planes remain body instead of receiving the glossy brand-pad finish.

The LOOKDEV first pass used NPZ `99691975…`, predating the final `062be78f…`
bundle. Revision 2 is explicitly bound to `062be78f…`; applying its overrides to
the earlier NPZ fails. `brep_faces.json` records the analytic source descriptors.

Validation: 57 fixture tests pass with zero skips. Chamfer, ring ridge and finite
land construction fixtures have area IoU 1.0. The production gate reports IoU
1.0 for body, bevel, bore/ridges, serration and apex over independently annotated
STEP face patches in `fixtures/c9_2_regions.expected.json`. Unannotated blend
faces are outside that IoU claim. Label and tangent reruns are identical.
See `REGIONS_v2_validation.json` for the receipt. Both front/back and oblique
false-color overlays are in the output directory; owner art review is pending.

## Worker adoption (Claude/Grok)

Set `bundle_path` and `regions_path` to the new directory. Load overrides **before
posing vertices/normals/tangents or computing region targets**; changing only the
regions JSON path does not change the old embedded NPZ labels. The new
`region_io.py` depends only on NumPy and can run inside Blender.

```python
# worker.py imports: add the marketing directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from region_io import apply_region_overrides

# immediately after loading regions.json, before POSES transformations
mesh = apply_region_overrides(mesh, req['regions_path'], bundle['npz_sha256'])
```

The loader verifies base hash, file hashes, shapes, dtypes, raw label hash, allowed
label IDs and unit tangents; geometry overrides are rejected. It returns a fresh
mapping and never edits the NPZ or the caller's original mapping. Farm transfer
must include the `.npy` override files. Use a new plan key to avoid old frame
receipts; the production render already in flight can finish unchanged.

## Reproduction

Using `~/jarambit_render/venv-cad/bin/python`, from the Codex worktree:

```sh
python -m pytest ops/render/marketing/tests
python -m ops.render.marketing.regions --bundle BASE/bundle.json --out NEW_DIR
python -m ops.render.marketing.notes.validate_regions_v2 --base BASE --v2 NEW_DIR
```

The writer refuses an existing destination or any destination inside the
production mesh directory. Both writer and production gate hash every original
file before and after their work. The production gate never re-ingests geometry.
