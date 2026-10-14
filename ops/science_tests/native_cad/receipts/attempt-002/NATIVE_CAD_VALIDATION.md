# Native CAD validation — science v1 diagnostic

Pinned to commit `e150bb906e8b8a265077de60ee148f6ba773a83a`.
C.10a is the comparison baseline. C.10c is an archived diagnostic subject
after revert `#68` and is not a standard-pipeline candidate.
No genome binding exists. No fresh FEM was run. Nothing here is a
physical qualification or a manufacturing release.

S08 native CAD adapter is not established. This diagnostic does not bind a genome, mesh, load, material, or observable, and it does not run fresh FEM. Integration owns assurance/adapters and the certified evaluator. No physical qualification is claimed.

An approved runner obtains a pinned file with `git show e150bb906e8b8a265077de60ee148f6ba773a83a:<path>` from a repository that already has that commit. This diagnostic does not fetch from a remote and does not treat a missing object as a pass.

STEP length units come from the file's LENGTH_UNIT entity, or from the
analytic constructor when the shape was built in millimetres. Extent is
not a unit. Compared bounds use `BRepBndLib.AddOptimal_s`. `Add_s` is
labeled and is not treated as a dimension error.

Mass uses Gr5 density 4.43 g/cm³ and the drawing factor `mm³ × 4.43e-3`
only for a positive signed volume. This is density arithmetic, not a
measured material. STL mass is unavailable unless the exact-merged mesh
is one finite, watertight, winding-consistent component with no
degenerate or nonmanifold edges. An open, inverted, or disconnected
mesh stays a candidate failure. Meshes are not hole-filled or rounded.

Published case text is a reported class only. Verified native
measurement stays false until an S08 exact-subject certificate exists.
The historical receipt `native_cad_e150bb9.json` is unchanged.

## C10a (comparison_baseline)

- Candidate status: **INCOMPLETE**.
- Geometry status: PASS (none).
- Genome binding: INCOMPLETE. Pipeline eligible: false.
- STEP solids 1, valid True, units mm via step_declaration, volume 14636.83139286504 mm³, mass 64.84116307039213 g (PASS).
- STEP compared bounds (BRepBndLib.AddOptimal_s): [209.490944351461, 72.99964243036956, 10.0]. Loose bounds (BRepBndLib.Add_s): [214.27605525754737, 76.36138364545737, 10.000292450362002].
- STL merge exact_coordinate, watertight True, winding True, components 1, degenerate faces 0, boundary edges 0, nonmanifold edges 0, finite True, signed volume 14638.463754825463 mm³, mass input True, mass 64.8483944338768 g (PASS).
- Reported fitness 2.673 is REPORTED_NOT_QUALIFIED.

## C10c (archived_diagnostic)

- Candidate status: **FAIL**.
- Geometry status: FAIL (stl, boundary, mass).
- Genome binding: INCOMPLETE. Pipeline eligible: false.
- STEP solids 1, valid True, units mm via step_declaration, volume 15144.251470879459 mm³, mass 67.089034015996 g (PASS).
- STEP compared bounds (BRepBndLib.AddOptimal_s): [210.95026352011098, 72.99964243036956, 10.0]. Loose bounds (BRepBndLib.Add_s): [214.04040341472054, 78.45649922044055, 10.189632170925167].
- STL merge exact_coordinate, watertight False, winding True, components 1, degenerate faces 0, boundary edges 40, nonmanifold edges 0, finite True, signed volume 15143.724905266672 mm³, mass input False, mass None g (UNAVAILABLE).
- Reported fitness 2.786 is REPORTED_NOT_QUALIFIED.
- Case sources (reported, not verified):
  - GateS: reported_direct_unverified (verified_native_measurement False) — B-rep ray probe
  - V1: reported_carried_or_ratio (verified_native_measurement False) — w80d g2 carry
  - V2: reported_carried_or_ratio (verified_native_measurement False) — record (C.10a 0.738)
  - V3: reported_direct_unverified (verified_native_measurement False) — direct r0p2
  - V4: reported_carried_or_ratio (verified_native_measurement False) — ring-refined × g2 ratio
  - V5: reported_carried_or_ratio (verified_native_measurement False) — g2
  - V6: reported_carried_or_ratio (verified_native_measurement False) — w80d submodel × g2 ratio
  - V7: reported_carried_or_ratio (verified_native_measurement False) — w80d nose submodel

Analytic box controls live in the unit tests and are not knife subjects.
T05's twelve challenge groups are not claimed. This file is the isolated native-CAD subset only.
