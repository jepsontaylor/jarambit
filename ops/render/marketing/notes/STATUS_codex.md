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

The CAD branch is based on main 831818f and retains its protected-metal, memcap
and fail-closed rendering/QA. Heavy jobs use memcap 32G; validation uses CPU
only. Full marketing/pro gate status is recorded in C10A_bundle.md. Rust/D1
gates passed on the rebased sheath branch with identical Rust source trees.
The executor owns PR sequencing; this lane opens no PRs. COORD handoffs go
through the queued sheath PR per the current COORD rule.

Owner-added root COORD entries are preserved outside the CAD lane's commits,
with backups in ~/jarambit_render_scratch/codex-c10a/ and a named git stash.
