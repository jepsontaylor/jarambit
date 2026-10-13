The MAJOR-release hero is SWITCHBACK Rev C.10a rc4, 64.841 g reference mass,
as requested by the owner after main 831818f. It remains a release candidate,
not the design of record. The pinned STEP is
`~/jarambit_render/inputs/switchback_C10a/switchback_revC10a_ground.step`, SHA256
`441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7`.
Both STEP and STL pins match designs/switchback/C10a/SHA256SUMS on main.

The new bundle is `~/jarambit_render_scratch/hero_C10a/codex_v1/mesh/`.
NPZ SHA256: `85f37bb8ba50b991251761576b22a3049caf6a568ba3cb5a4f153669a5d0a973`.
Labels SHA256: `6f75f4c29378ea6f103eea125504443b26ba70879ea3e2ffe6afa34aa17302e6`.
There are 50,680 vertices and 101,372 triangles with analytic B-rep corner normals.
B-rep regions v2 labels and tangents are embedded in this NPZ; no external
overrides are needed. Ring details, grinds, serrations and the finite apex are
labeled. A broad handle remains body unless explicitly tagged.

The production CAD gate passed in 40.581 s under ~/bin/memcap 32G:
repeated NPZ/manifest/region/overlay bytes identical; geometry round-trip error
5.55e-17 m; chamfer fixture IoU 1.0; 36 native-4K framing angles with minimum
margin 14.50% and maximum width fill 70%. V/F/N_corner/face_id arrays match the
existing C.10a bundle exactly; that directory was untouched. Both overlays were
inspected; owner art review is pending. The closed source has four holes (Euler
-6), with no mesh boundary or nonmanifold edges. See
[C10A_validation.json](C10A_validation.json) and [C10A_bundle.md](C10A_bundle.md).

Old C.9.2 production and regions-v2 bundles remain unchanged. C.9.2 and C.9.3
source pins remain supported. C.9.2's immutable NPZ plus external overrides are
documented in [REGIONS_v2.md](REGIONS_v2.md).

The CAD branch is rebased onto main `6853184` after sheath follow-up #58.
Fresh validation: 214 marketing/pro pytest pass, zero skips; 15 tool/CAD/docs
checks pass; two finish-library mark/budget tests pass. The production CAD
rerun matches all six published artifact hashes, with chamfer IoU 1.0 and
36 native-4K framing angles at minimum margin 14.50%. Existing C.10a and
C.9.2 bundle files remain unchanged. Signature stays protected bare
laser-etched metal; grinds, serrations and apex stay raw.

Validation used memcap 32G, nice 19, CPU only and eight-core affinity; outputs
are in this checkout's `target/cadmesh-rebase-6853184/`. The Rust source tree
matches current main. See [CAD_rebase_6853184_validation.json](CAD_rebase_6853184_validation.json)
for the fresh receipt; C10A_validation.json records the original bundle build.
The executor opens the next CAD PR. This lane opens or merges none, leaves
jr_grok's farm alone, and stops after its READY handoff.

The two owner-added root COORD entries are preserved outside this lane's
commits, with a named stash and backups in `target/cadmesh-rebase-6853184/`.
