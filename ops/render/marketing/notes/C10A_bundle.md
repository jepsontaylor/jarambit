The owner-selected MAJOR-release render source is SWITCHBACK Rev C.10a rc4.
STEP pin: `441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7`.
STL pin: `0bcadad61bff550d9c527266e183440e8242c3a0222b9a89755cdc682b214411`.
Both match the C.10a machinist-pack manifest on main `831818f`.

Use these consumer paths together:

```text
bundle_path: /home/ubuntu/jarambit_render_scratch/hero_C10a/codex_v1/mesh/bundle.json
regions_path: /home/ubuntu/jarambit_render_scratch/hero_C10a/codex_v1/mesh/regions.json
```

| artifact | SHA256 |
|---|---|
| bundle.json | `655138786aeb20c357a3cdcfd1925d1e82e75587a0936692a268ddca57099d71` |
| mesh.npz | `85f37bb8ba50b991251761576b22a3049caf6a568ba3cb5a4f153669a5d0a973` |
| regions.json | `7453a2a312c5a733fe40937c4abeda7077d3226c659c36032027b257e8ba50f6` |
| raw region_id bytes | `6f75f4c29378ea6f103eea125504443b26ba70879ea3e2ffe6afa34aa17302e6` |
| framing.json | `a8df89920457afc0065c0e934ede3786f3fdc163c50b39db22754b6f4bd889d3` |

This new NPZ contains B-rep regions v2 labels and tangents directly; the normal
worker loader suffices. No external C.9.2 overrides should be applied. Use a new
plan key and ship this directory's manifest, NPZ and regions JSON together.
The previous `hero_C10a/mesh` was not modified. Its V/F/N_corner/face_id arrays
match the new bundle exactly; appearance attributes differ. Source positions
are preserved with only units and a rigid canonical pose applied.

Regions are body 0, bevel 1, edge_apex 2, serration 3, ring 4, pad 5, spine 6.
Coaxial ring ridges/bore stay ring; planar/ruled grinds are bevel, conical wheel
grinds are serration, and thin finite lands are apex. A broad handle stays body;
pad requires exporter tags. These labels work with main's #55 protected-metal
shader for raw grinds and the laser mark.

The production gate passed with deterministic output, chamfer fixture IoU 1.0,
36-angle native-4K framing margin at least 14.50%, and analytic normal/unit
contracts. Detailed receipt: [C10A_validation.json](C10A_validation.json).
The source topology has four holes, Euler -6, and is preserved. Front/back
regions_debug.png and oblique regions_debug_3q.png were inspected; owner art
review remains pending.

Gate status: all 214 marketing/pro pytest passed (zero skips), including CPU
protected-metal shader, memcap and failure-propagation regressions.
Required-tool and 12 documentation/evidence checks passed. All 21 repository/
sheath checks passed on feat/sheath-v1 after rebasing onto the same main. The
CAD branch's Rust sources/build manifests match that validated tree.
Logs: `~/jarambit_render_scratch/codex-c10a/cad-gates/gates/` and
`~/jarambit_render_scratch/codex-c10a/sheath-rebase/gates/`.

Reproduce in a new output directory, under the memory cap:

```bash
~/bin/memcap 32G -- env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  ~/jarambit_render/venv-cad/bin/python -m ops.render.marketing.notes.validate_cad \
  --out /path/to/new/C10a-output
```

This lane opens no PR. The executor opens the single queued sheath PR first
and sequences subsequent render integration for the MAJOR release.
