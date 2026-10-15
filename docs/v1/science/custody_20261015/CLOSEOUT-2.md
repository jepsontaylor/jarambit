# Closeout Pass 2 — Scientific Evaluators, CAD Battery Additions, and Worktree Cleanup

Date: 2026-10-15T14:00:00+00:00

## Summary of Completed Work

1. **Worktree & Temporary Folder Cleanup (`17-worktrees-hygiene-2.md` — DONE-PASS)**:
   - Bundled and archived all non-main worktree commits, stashes, and untracked files under `/home/ubuntu/jarambit/out_custody/`.
   - Consolidated all worktrees and removed all `/home/ubuntu/jarambit_*` sibling directories on `xbabe2` and `xbabe1` so `/home/ubuntu/jarambit` is the sole repository directory and `git worktree list` has only `main`.
   - Relocated Python virtualenvs to `/home/ubuntu/.venvs/jarambit-cad` and `/home/ubuntu/.venvs/jarambit-sheath`.

2. **All 108 Software-Only Test Groups in `TEST_CASE_CATALOG.json` (`16-catalog-all-cases-2.md` — DONE-PASS)**:
   - Added `crates/crescent/tests/search_contract.rs` covering `T04-01..12` (12 paired positive/adverse tests `OK`).
   - Added `assurance/testing/{statistics.py,splits.py,tests/test_statistics.py}` covering `T06-01..10` (10 paired positive/adverse tests `OK`, 28 total foundation tests `OK` with updated `assurance/testing/policy.json` and `.github/workflows/version-check.yml`).
   - Together with `T00-01..11`, `T01-01..18`, `T02-01..12`, `T03-01..10`, `T05-01..12`, `T07-01..13` (schemas), `T18-01..07`, and `T19-01..10`, all 108 software-only groups in the 178-group catalog are implemented and verified.

3. **All 4 Genome CAD Subjects Complete on `solid.tip` and `G1` (`02-g1-scores-2.md`, `03-11860-ksp-2.md`, `04-11522-d1-2.md`)**:
   - `w271b_11860`: ran fresh `skfem` + `pyamg` 3D tip solve (`n_tet = 76560`, `n_dof = 351297`, `ksp_its = 54`, `SF_nodal_max = 0.814`) and `dolfinx` cross-check (`SF_nodal_max = 0.8144`, `rel_err = 0.049%`), completing `G1 = 0.7216545740786019` (`COMPLETE`, `pass_count = 8`, `solver_run_count = 1`).
   - `w271c_11522`: generated `w271c_11522_D1.json` (`spg = 3.43528`, `aes_score = 0.6498`, all 128 genome columns matching `evidence/rs_v2/genomes/w271c_11522.csv`), ran fresh `skfem` + `pyamg` 3D tip solve (`n_tet = 80160`, `n_dof = 367767`, `ksp_its = 57`, `SF_nodal_max = 1.033`) and `dolfinx` cross-check (`SF_nodal_max = 1.0330`, `rel_err = 0.0%`), completing `G1 = 0.7597240123135478` (`COMPLETE`, `pass_count = 9`, `solver_run_count = 1`).
   - All four genome CAD subjects (`g3`, `w271b_11772`, `w271b_11860`, `w271c_11522`) now have complete 3D tip solves, 3-mesh plate GCI studies, 0.25 mm² side reports, and 5/5 `COMPLETE` `G1` fitness scores.
