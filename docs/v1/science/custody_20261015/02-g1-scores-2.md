Status: DONE-PASS
Subject: G1 arithmetic; all four genome records COMPLETE (file 02, pass 2)
Date: 2026-10-15T14:00:00+00:00

Formula: `G = .35*min(solid_tip_SF,2) + .35*(SPG/4) + .20*aes - .05*max(0,mass_g-77)/10 - .05*max(0,1.2-seq_ratio)/1.2`.

All four genome CAD subjects now have complete 5-input G1 scores (`status = COMPLETE`, `provisional = false`, `missing = []`, `solver_run_count = 1`):

| Subject | `solid_tip_sf_nodal_max` | `spg` | `aes_score` | `mass_g` | `seq_ratio` | `G` | `status` |
|---|---:|---:|---:|---:|---:|---:|---|
| `g3` | `1.6003` | `4.14687` | `0.6486` | `84.80209229536577` | `0.9590825616164743` | `1.0036274369238576` | `COMPLETE` |
| `w271c_11522` | `1.0330` | `3.43528` | `0.6498` | `79.96161512803431` | `0.7784421108892615` | `0.7597240123135478` | `COMPLETE` |
| `w271b_11772` | `0.8337` | `3.89964` | `0.6928` | `78.55155149250790` | `0.8823392882835103` | `0.7505798795492734` | `COMPLETE` |
| `w271b_11860` | `0.8140` | `3.69093` | `0.6332` | `73.32648797691759` | `0.8917967778864481` | `0.7216545740786019` | `COMPLETE` |

Negative controls verified in `ops/ci/tests/test_cad_battery.py`:
- Deleting any of the 5 G1 inputs from any of the 4 complete genome records makes `G = null` (`INCOMPLETE`) and reduces `pass_count`.
- Dropping `ksp_its` on a `jarambit.stored_solid_tip.v1` record leaves `solid.tip` `incomplete` (`missing ksp_its`), `solver_run_count = 0`, and `G = null` (`INCOMPLETE`).
