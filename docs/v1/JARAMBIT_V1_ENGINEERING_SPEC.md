# JARAMBIT v1.0 — Engineering Specification & Roadmap Rationale

**Author:** Jepson Taylor  
**Spec version:** 1.0-draft (2026-10-12)  
**Baseline audited:** public `main` = `727b28b9690704924d94bed8b5094b4c43fc3f67` ("Release/v0.27.0 (#7)"), `docs/VERSION` = `0.27.0`.  
xbabe2 `/home/ubuntu/jarambit` local `main` is **2 commits behind** its origin and on `67fe83c`; the commit `17b14875` (#6) named in the brief is an **ancestor** of public `727b28b` (#7) with an **identical tree** (`git diff 17b14875 727b28b` is empty), so the two are reconciled; public GitHub is the source of truth. All path:line citations below are against `727b28b`.  
**Companion files:** `jarambit_v1_roadmap.json` (machine-readable PR plan), `FEEDBACK_SYNTHESIS.md` (keep/reject/defer per idea).

**Scope statement (owner-locked).** "Strength" in this spec means *structural break resistance of a hiker/runner utility tool* under utility loads: chord twist 1.82 N·m, lateral 260 N (hunter) / 180 N (hiker), pry, ring pull 1500 N with SF ≥ 2, tip load, fatigue, −10…100 °C, tolerance/thin-part effects, wood/baton/pry utility work. The spec does **not** design or optimize penetration or strike effectiveness into flesh or bone. The existing gel/muscle/bone "cut media" Monte Carlo (`crates/monte_carlo/src/lib.rs:42-75`) is **retired**. It is replaced by adversarial / rare-event *load-case discovery* (§8).

---

## 0. Executive summary

1. **What v0.27.0 is.** A real Rust workspace with 9 crates (~9.5 kLOC Rust/Python audited). It has two separate evolutionary engines, a DKT+CST plate FEM with analytical verification, a faceted watertight STEP exporter, MAP-Elites-style archives, and CI with a known-negative promotion fixture. The headline provisional design `g3_tip+00_t60_tt3` is 84.80 g, G1 0.9805, tip SF 1.534 × SPG 4.147 = 6.362, and is **not promoted** (`README.md:12`, `docs/WHITEPAPER.md:130-133`).
2. **What it is not yet.** It is not reproducible end to end. The tip SF that carries 35 % of G1 comes from an **out-of-repo scikit-fem/pyamg tet solver** on xbabe2 (`/home/ubuntu/jarambit_tools`, outputs in uncommitted worktree `exec-w27d/out/wave27/…_solid.json`, 422,955 dof, **1,419.5 s wall per solve**). Its source and outputs are not in the public repo (`docs/wave27_diversity/SOLIDS.md:3`). It also does not have one meaning of PASS, one engine, or one objective (§2, §3).
3. **The 70 g holy grail is a geometry problem, not an optimizer-tuning problem.** 70 g of Ti-6Al-4V (ρ = 4.43 g/cm³) is 15.80 cm³; the provisional design is 19.14 cm³. A **−17.5 % volume cut** is required. Uniform thinning of 6.0 → 5.0 mm gets to ~70.7 g, but out-of-plane bending and torsion capacity scale ≈ t². That drops tip SF to ≈ 1.534 × (5/6)² ≈ **1.07** and SPG similarly, so the current *planar-plus-thickness (2.5D)* family cannot reach 70 g with margin. v1 therefore adds **rib/rail thickness fields, through-pocket lattices (connectivity-guaranteed), and SIMP/level-set-in-the-loop mutation** (§5). The mass target becomes a strong soft G2 term (not a gate; owner decision 2026-10-12), with < 80 g as the first target and 70 g as the stretch target.
4. **Speed.** The current certification-grade evaluation of one design (`jarambit crescent-d1`) took **90.9 s on 1 core** in this audit (box, release build, wave14_c03 fixture). The solid tip submodel took 1,419.5 s. The v1 target is ≥ 50,000 search-tier evals/h across xbabe2+xbabe3 (2 × 128 cores + 2 × RTX 3090 24 GB) and **≤ 15 s per 0.4 M-dof tet10 solid submodel on one RTX 3090**, a ≥ 90× speedup (§10). xbabe1 was **unreachable** from the audit box (ssh timeout), so it is planned as optional.
5. **Order of work.** (a) Truth and evidence (v0.28–v0.29): fix reporting bugs, add typed observations, run IDs, an event log, and figure manifests. (b) Reproducible FEM ladder in-repo (v0.30–v0.31). (c) Part-agnostic core plus new genotypes (v0.32–v0.33). (d) QD/MOO engine plus surrogates plus HPC (v0.34–v0.35). (e) Adversarial loads, aesthetics model, DFM/cost (v0.36–v0.37). (f) The 70 g campaign plus release (v0.38 → v1.0.0). This sequencing follows all six reviews' consensus: *fix evidence first, then scale*.
6. **IP is urgent and outside engineering.** The repo is public. `docs/PATENT_DRAFT.md` is an **unfiled utility** draft with no prior-art search, while the goal is a **design** patent, and there is no US provisional route for designs. Engage counsel now (§14).

---

## 1. Inputs reviewed

| ID | File (attachments dir) | Nature | Size |
|---|---|---|---|
| FB1 | `72238e2a…md` | Narrative review, 11 sections, "Yes—the repository is accessible now" | 21.7 kB |
| FB2 | `81673801…md` | Red-team + evidence spec, findings A01–A17 | 40.7 kB |
| FB3 | `826d3a13…md` | Integrity review, R01–R14, WP-A..E | 41.6 kB |
| FB4 | `be6b3ecf…md` | Review + spec, F01–F20, requirements R01–R20, 10 probes | 59.6 kB |
| FB5 | `a6e35505…md` | Red-team, F01–F17, acceptance matrix A01–A22 | 65.1 kB |
| FB6 | `4c2f05b7…md` | Review, F01–F18, contracts A–F, AT01–AT24 | 47.6 kB |

All six reviewed the same commit `727b28b`. None ran the code. All six **declined** to advise on structural strength, material, manufacturing, or HPC acceleration of the knife workload, so their engineering content is limited to evidence and provenance. This spec covers those engineering areas within the owner's utility-load scope, and it independently **verified every code claim** against the clone at `/workspace/jarambit_review`.

---

## 2. Common themes across the six feedback files (verified against code)

Status legend: **VERIFIED** = reproduced from source at the cited line. **STALE** = true of an older state, not of `727b28b`. **UNSUPPORTED** = not borne out by the code, or out of scope. **PARTIAL** = true with qualification.

| # | Theme | Files citing | Status | Evidence (path:line @727b28b) |
|---|---|---|---|---|
| T1 | "PASS" means different things; the whitepaper says the mass < 80 g cap is a hard gate, yet 84.8 g rows are labelled PASS | FB1–FB6 | **VERIFIED** | `docs/WHITEPAPER.md:28` ("mass < 80 g cap") vs `:130` (84.8 g, PASS); `crates/crescent/src/fem.rs:57` `MASS_BAND (74,77)`, `MASS_CAP_HARD 80`; `fem.rs:62` `promote_eligible`; `README.md:12` "all hard gates PASS" |
| T2 | `seq ≥ 1.2` is called "soft" in the docs but is HARD in crescent `legal()` when P1 is on | (implicit FB2/FB4) | **VERIFIED (new)** | `docs/WHITEPAPER.md:28` "seq ≥ 1.2 soft"; `crates/crescent/src/qd.rs:26` `legal()` requires `seq_ratio >= SEQ_TARGET` when `g.p1()` |
| T3 | G1 maps missing → 0. Missing mass removes the penalty, and `provisional` reflects only the tip field | FB1–FB6 | **VERIFIED** | `metrics/global_metric.py:33-36` (`or 0.0`); `:28` `provisional = tip is None` |
| T4 | `title_tag` re-parses raw mass, so None raises TypeError | FB4, FB5 | **VERIFIED** | `metrics/global_metric.py:49` `float(rec.get('mass_g', nan))` |
| T5 | Absent FEM becomes default zeros in JSON/CSV | FB4, FB6, FB3 | **VERIFIED** | `crates/cli/src/crescent.rs:13`, `:54`, `:215` `unwrap_or_default()` |
| T6 | Duplicate `pry20` key in hand-built JSON; scalar NaN is not guarded | FB2, FB4, FB6 | **VERIFIED** | `crates/cli/src/crescent.rs:14` (`"pry20"` appears twice); `:10` `jnum` guards arrays only |
| T7 | README "plate level by default" vs CLI opt-in `JARAMBIT_FEM=="1"` | FB1, FB4, FB5, FB6 | **VERIFIED** | `README.md:67`; `crates/cli/src/main.rs:82` |
| T8 | Checkpoint lossy (`{:.8}`/`{:.4}`); seed/migration lines not validated; no evaluator identity; missing checkpoint → silent fresh start | FB1–FB6 | **VERIFIED** | `crates/evolve/src/lib.rs:339-343` (`genes_exact` `{x:.8}`), `:362` (`{:.6}`/`{:.4}`), `:408` `let _seed = lines.next()`, `:443-450` (`exists()` filter → `Vec::new()` → re-init) |
| T9 | History/quarantine buffered in RAM and written after `run()`; quarantine drops genotype | FB1, FB5, FB6 | **VERIFIED** | `crates/cli/src/main.rs:103-125` (written at `:125`), `:115` `for (_, why)` |
| T10 | "Feasible mean" uses `fit > -100`, not `feasible()` | FB1 | **VERIFIED** | `crates/cli/src/main.rs:109` vs `crates/evolve/src/lib.rs:110` |
| T11 | Log callback fires before reproduction; no terminal snapshot | FB1, FB5, FB6 | **VERIFIED** | `crates/evolve/src/lib.rs:469` (log), `:506` (ckpt), `:508` (return, no final log) |
| T12 | `evals` = population length; elites re-counted | FB1, FB2, FB4, FB6 | **VERIFIED** | `crates/crescent/src/qd.rs:147` `all.extend(pop…)`, `:151` `pop.len()`, `:157` 4 elites; census text `crates/cli/src/crescent.rs:66` "evaluations {n_all}" |
| T13 | QD archive CSV header `cell_hausdorff` but the axis is mass | FB2 | **VERIFIED** | `crates/cli/src/crescent.rs:59` vs `crates/crescent/src/qd.rs:102-108` (comment says Hausdorff, code uses mass bins 72–90 g) |
| T14 | Novelty is context-dependent but archive replacement compares stored `fit` | FB2, FB3, FB5 | **VERIFIED** | `crates/crescent/src/qd.rs:143-145`, `:196-199` |
| T15 | No parent IDs / operator / RNG lineage in `Rec` | FB1–FB6 | **VERIFIED** | `crates/crescent/src/qd.rs:15-21` |
| T16 | Aesthetic = similarity to the C.6 reference (Hausdorff ≤ 6 mm, EMD), not preference; C.4/C.5 names are stale | FB1–FB6 | **VERIFIED** | `crates/crescent/src/aesthetic.rs:1,6,11,101,118` (`use crate::c6_ref as c4`) |
| T17 | Hero renderer reads STL, titles "watertight STEP", hard-codes metrics | FB1–FB6 | **VERIFIED** | `ops/wave_figures/render_step3d_w27.py:3,11` |
| T18 | Aesthetic PASS badge is hard-coded | FB4, FB6 | **VERIFIED** | `ops/wave_figures/make_d1_plate.py:71` (literal `PASS`, colour `#2a7`) |
| T19 | Theory subgate fails open on missing check / NaN | FB5 | **VERIFIED** | `crates/cli/src/calib.rs:69` `theory_ok = true`; `:72-76` `if let Some`; `:79` `err >= 5.0` (NaN → false) |
| T20 | `err_vs_extrap` column is actually error vs the two-finest mean | FB5 | **VERIFIED** | `crates/cli/src/calib.rs:100-101,123` |
| T21 | `certify` mixes meshes (min of two runs; fields from one) | FB3, FB5 | **VERIFIED** | `crates/crescent/src/fem.rs:108-117` |
| T22 | Exporter `HashMap` iteration → byte non-determinism | FB3, FB5 | **PARTIAL** (risk; not measured) | `crates/crescent/src/export.rs:6,20,30,63` |
| T23 | Two engines (NSGA-II legacy; scalar-GA + novelty + MAP-Elites crescent) described as one | FB1–FB6 | **VERIFIED** | `crates/evolve/src/lib.rs:1,141-201`; `crates/crescent/src/qd.rs:2,77-90,128,176`; `README.md:33` "NSGA-II islands" |
| T24 | "Reject, never penalise" is contradicted by graded negative fitness | FB1 | **VERIFIED** | `README.md:29`; `crates/crescent/src/qd.rs:78-88`; `docs/WHITEPAPER.md:226` (−1000 per failing draw) |
| T25 | MC media model is a lookup, not an impact simulation | FB1–FB6 | **VERIFIED → RETIRE** | `crates/monte_carlo/src/lib.rs:42-75` (Wood/Cord/Hide/Muscle/Bone/Gel profiles) |
| T26 | Representation is 2.5D (planform + single-valued thickness) | FB3, FB5, FB6 | **VERIFIED** | `crates/crescent/src/export.rs` (two surfaces + walls); `crates/crescent/src/genome.rs:9-10` (`N_CP=40`, `NG=128`) |
| T27 | Patent draft is an unfiled **utility** draft with no prior-art search; repo is public | FB1–FB6 | **VERIFIED** | `docs/PATENT_DRAFT.md` header |
| T28 | CI is green but on a moving toolchain; the metric smoke covers only one happy path | FB2, FB3, FB4 | **VERIFIED** | `.github/workflows/d1-gates.yml` (`ubuntu-latest`, `dtolnay/rust-toolchain@stable`) |
| T29 | GAPS/STATUS/Appendix A mix history and current state | FB2–FB6 | **VERIFIED** | `GAPS.md` (dated 2026-10-11), `STATUS.md`, `docs/WHITEPAPER.md` App. A |
| T30 | "Add a worker pool/threads" would be redundant; MC is already thread-stable with persistent workers | FB1–FB6 | **VERIFIED** | `crates/monte_carlo/src/lib.rs` (seed per sample index); `crates/cli/src/main.rs:2` mimalloc |
| T31 | Calibration rows (258) are correlated and not an ML benchmark | FB5, FB3 | **PARTIAL** (count from doc, not re-derived) | `docs/calibration/calibration.md` |
| T32 | Field plots use per-figure p99.5 normalization | FB6 | **PARTIAL** (plotted elsewhere: `ops/wave_figures/plate_fem.py`) | to confirm in PR-0.29.4 |
| T33 | "Earlier GAPS says no convergence study" | GAPS.md | **STALE** | `docs/CALIBRATION.md`, `crates/physics/src/verify.rs`, `docs/calibration/knife_convergence.csv` exist |
| T34 | "Can't advise on strength/material/HPC" (all six) | FB1–FB6 | **UNSUPPORTED for this owner scope** | utility structural integrity is in scope (§0 scope) |

### New findings not raised by any reviewer (this audit)

| # | Finding | Evidence |
|---|---|---|
| N1 | **The G1 tip term is produced by out-of-repo code.** scikit-fem + pyamg in `xbabe2:/home/ubuntu/jarambit_tools` (vendored `skfem/`, `venv_solid`). Outputs live in uncommitted `exec-w27d/out/`. Branch `exec/wave27-diversity` is not on the public remote. | `docs/wave27_diversity/SOLIDS.md:3`; `git ls-remote` (no wave27 branch); xbabe2 `…_solid.json`: `n_tet 92448, n_dof 422955, wall_s 1419.5` |
| N2 | Solid tip SF has a **13 % spread across stress-recovery methods** (nodal-max 1.534 / nodal-avg 1.65 / elem-mean 1.74). G1 uses the most conservative value, but no mesh-convergence evidence for the solid exists in the repo. | xbabe2 `g3_tip+00_t60_tt3_solid.json` |
| N3 | `sallow_joint = 730.2 MPa = 828 × 0.8819` (JK2 = thin-stock × 100 °C knockdown). The tip SF is therefore *already* temperature- and stock-knocked-down, and G1 must not apply it twice. | same JSON (`JK2 0.8819`) |
| N4 | README crate table says genotype = "20-gene vector" (legacy crate). The crescent lane, which produced every recent winner, uses **128 genes** (40 CP + 88). | `README.md:50`; `crates/crescent/src/genome.rs:9-10` |
| N5 | The whitepaper says linear tets "lock in bending" (7 % of beam stress). That was a reason to avoid solids; quadratic tet10 does not lock this way, and the out-of-repo solid uses ~4.6 dof/tet (consistent with P2). | `docs/WHITEPAPER.md:214`; N1 dof ratio |
| N6 | Certification eval is ~91 s single-core (box measurement) and is dominated by the multi-resolution plate solves with a skyline Cholesky. | this audit: `time jarambit crescent-d1 … --threads 1` = 90.9 s; `crates/physics/src/fine.rs:3-4,195-271` |
| N7 | The provisional winner fails nothing that is *labelled* hard, yet fails the 80 g cap that the paper *calls* hard. That makes the README badge "all hard gates PASS" literally false under `WHITEPAPER §II-C`. | T1 |

---

## 3. Red-team findings (ranked)

| Rank | ID | Severity | Finding | Consequence | Fix (PR id in roadmap) |
|---|---|---|---|---|---|
| 1 | RT-01 | P0 | Headline tip SF is out-of-repo and unreproducible (N1) | 35 % of G1 cannot be audited or replayed | Vendor and port the solid submodel in-repo (`fem-solid` crate + Python reference), commit JSON outputs as LFS evidence (PR-0.30.x) |
| 2 | RT-02 | P0 | PASS semantics are inconsistent (T1, T2, T24, N7) | Public badge overclaims | `requirements/RS-*.toml` registry + scoped verdicts (PR-0.28.2) |
| 3 | RT-03 | P0 | G1 missing → 0 (T3, T4) | Deleting mass *raises* G | Typed `Obs` + completeness gate (PR-0.28.1) |
| 4 | RT-04 | P0 | Resume not bound to the config; lossy; silent re-init (T8) | Mixed-evaluator experiments | Manifest hash + lossless `f64::to_bits` hex checkpoint (PR-0.29.2) |
| 5 | RT-05 | P0 | Absent FEM → zeros; duplicate keys (T5, T6) | Poisoned datasets and surrogates | serde-typed records, `Option<f64>` → `null` (PR-0.28.3) |
| 6 | RT-06 | P1 | Theory gate fails open (T19) | Verification PASS without evidence | Expected-check manifest (PR-0.28.4) |
| 7 | RT-07 | P1 | Eval counters wrong (T12) | Throughput and budget claims inflated by elite re-count: 2,624 rows vs 2,464 fresh evals at pop 64 × 40 gens (FB2 arithmetic, reproduced from `qd.rs:157,160`) | Event-derived counters (PR-0.29.1) |
| 8 | RT-08 | P1 | No lineage (T15) | Genealogy animations would be fiction | Event log with parent IDs (PR-0.29.1) |
| 9 | RT-09 | P1 | Figure/claim decoupling (T17, T18) | Stale captions | Figure manifests (PR-0.29.4) |
| 10 | RT-10 | P1 | 2.5D representation cannot reach 70 g at margin (§0 item 3) | Holy grail infeasible in the current family | Rib/rail thickness field + lattice + SIMP mutation (v0.32–0.33) |
| 11 | RT-11 | P1 | Strike-media MC is out of scope and physically unfounded (T25) | Wrong objective; reputational risk | Retire; replace with adversarial load discovery (v0.36) |
| 12 | RT-12 | P1 | No fatigue case anywhere | A utility tool fails by fatigue at the ring/neck under repeated pry | Goodman/Marin fatigue check (PR-0.31.3) |
| 13 | RT-13 | P2 | Faceted STEP is not a machining release (export.rs comment) | A CNC shop needs analytic B-rep (planes + B-splines) | OCCT-based B-rep export (PR-0.33.3) |
| 14 | RT-14 | P2 | Moving CI toolchain | Non-reproducible builds | `rust-toolchain.toml` pin + SHA-pinned actions (PR-0.28.5) |
| 15 | RT-15 | P2 | Docs drift (T29, N4) | Agents act on stale state | Generated `STATUS.md` from the release manifest (PR-0.28.5) |

**Mistakes in the reviews themselves** (so they are not blindly adopted):
- All six refuse structural/HPC guidance. Under the owner's utility-load scope that refusal is a scope mismatch and is not adopted.
- FB4's "isolated probes" re-implemented the metric. Their conclusions match the code (verified above), but the probes are not in the repo. PR-0.28.1 makes them real tests.
- Several reviews suggest proving generality on a non-knife "thermal/enclosure" demonstrator. **Adopted in modified form:** the generalization demo is a Ti bracket (§12). That is still a part-agnostic structural use case.
- FB2 says "fix the smoke archive's second axis". The code comment at `qd.rs:102` is *also* wrong (it says Hausdorff), so both the comment and the CSV must change.

---

## 4. Target architecture (part-agnostic core)

```
┌───────────────────────── jarambit-core (part-agnostic) ──────────────────────────┐
│ evidence/   RunManifest, ObjId, Obs<T>{value|missing(reason)}, Verdict(RS-id),  │
│             EventLog (append-only, JSONL+zstd, fsync per gen), FigureManifest    │
│ geom/       SDF2/SDF3, skeleton+thickness field, spline planform, lattice/TPMS,  │
│             connectivity (union-find on voxel/graph), B-rep export (OCCT)        │
│ fem/        Tier0 surrogate │ Tier1 DKT/CST plate │ Tier2 tet10 solid │ Tier3 sub │
│ loads/      LoadCase{bc,load,temp,tol}, adversarial search (CMA-ES/BO/IS)       │
│ search/     Island NSGA-III, CVT-MAP-Elites, novelty, CMA-ES refine, SAEA        │
│ dfm/        min wall, tool radius, 2.5D accessibility, cost proxy                │
│ aesthetics/ silhouette descriptors, learned pairwise model (Bradley–Terry)       │
│ hpc/        job queue (Ray or MPI), GPU solver service, content-addressed cache  │
└──────────────────────────────────────────────────────────────────────────────────┘
          ▲ trait PartSpec                                  ▲ trait PartSpec
┌─────────┴───────────────┐                     ┌───────────┴───────────────┐
│ part-karambit (plugin)  │                     │ part-bracket (demo plugin) │
│ hard gates, load cases, │                     │ L-bracket, 2 bolt holes,   │
│ aesthetics priors (C.6) │                     │ 2 load cases               │
└─────────────────────────┘                     └───────────────────────────┘
```

### 4.1 `PartSpec` trait (Rust)
```rust
pub trait PartSpec: Send + Sync {
    const ID: &'static str;                     // "karambit.v1"
    type Genome: Genotype;                      // see §5
    fn decode(&self, g: &Self::Genome) -> Result<Phenotype, DecodeFail>;  // never panics
    fn hard_gates(&self, p: &Phenotype) -> Vec<GateResult>;               // geometric, pre-FEM
    fn load_cases(&self) -> &[LoadCase];                                  // utility loads only
    fn requirement_set(&self) -> &RequirementSet;                         // RS-id, versioned
    fn descriptors(&self, p: &Phenotype) -> Descriptors;                  // QD axes, versioned
    fn aesthetic(&self, p: &Phenotype) -> Option<AestheticObs>;           // optional
    fn material(&self) -> &Material;                                      // Ti-6Al-4V Gr5 table
}
```
**Success criteria.** (a) `part-bracket` compiles and runs a 1,000-eval search with **zero imports** from `part-karambit` (enforced by `cargo deny`/a dependency-graph test). (b) `jarambit-core` has no string literal containing "blade|ring|karambit" (grep test in CI).

### 4.2 Migration
`crates/crescent` (which today spans genotype, phenotype, FEM, and evolve; see `TECHNOLOGY_MAP.md` lane row) is split in 4 PRs. Legacy `crates/evolve` (NSGA-II, 20 genes) is **frozen** behind a `legacy` feature and retired in v0.35. Each split PR must keep `cargo test --workspace` green and keep the `d1_smoke.py` known-negative fixture (`w14c03 → promote=false`) byte-for-byte identical in its decision.

---

## 5. Genotype representations (connectivity guaranteed by construction)

| Rep | Description | Gene count | Connectivity guarantee | Use |
|---|---|---|---|---|
| G-A **Spline planform + thickness field** (current, kept) | 40 CP outline + 88 features (`genome.rs`) | 128 | Single outline polygon; holes validated | Baseline, warm start |
| G-B **Skeleton + radius/thickness field** (new) | Medial-axis graph: spine curve (Bézier, 8 CP), ring circle (ID locked ≥ 25.4), 2–6 struts. Each edge carries a width w(s) and thickness t(s) as 4-knot B-splines. Shape = union of swept discs → SDF. | 60–110 | Graph is a spanning tree over {ring, spine, tip} before decoding; union of overlapping swept discs ⇒ connected | Main v1 lattice/rib explorer |
| G-C **SDF/implicit** | Base G-A/G-B SDF ⊖ (smooth-min of N ≤ 24 pocket primitives: capsules, superellipses) | +5/pocket | Pocket accepted only if the remaining min ligament ≥ w_min (2.0 mm) **and** a union-find on a 0.25 mm raster still has 1 component | Lightening pockets |
| G-D **Lattice/TPMS infill** | Region mask × gyroid/Schwarz-D or 2D isogrid (period p, rib r, angle) inside a skin offset ≥ 1.2 mm | 6–10 | Skin offset keeps the outer shell connected; ribs are periodic and intersect the skin | Mass removal in the grip/neck. **2.5D only** (through-pockets or blind pockets ≥ 0.6 mm floor) for CNC; true TPMS is flagged *non-machinable* (DFM rejects) |
| G-E **Rib/rail thickness field** | t(x,y) = t_web + Σ rails(Δt_k, width, path). Spine rail plus ring rim rail. t_web ∈ [3.0, 6.0], rail ∈ [t_web, 6.35] | 12–20 | Thickness field > 0 everywhere | **Key to 70 g**: I-beam-like sections recover t² losses |
| G-F **TO-as-mutation** | SIMP (penal 3, filter r = 1.5 mm) or level-set run for 20–40 iterations on the plate mesh under the case basket. Result → contour → G-C pockets (projection back to genes). | n/a (operator) | Final union-find connectivity check; reject if > 1 component | Directed mutation, ≤ 10 % of offspring |

**Key quantitative hypothesis (H70).** A G-E design with spine rail 6.0 mm × 7 mm wide, ring rim 6.0 mm, web 4.2 mm, and grip pockets removing 1.8 cm³ reaches ≈ 15.6–16.0 cm³ (69–71 g). It keeps ≥ 92 % of the 6.0 mm design's lateral section modulus at the governing belly section (rail at the extreme fibre carries the bending). **Falsification:** if three v0.38 campaigns (≥ 200k search-tier evals each) produce no tier-2-verified design ≤ 72 g with tip SF ≥ 1.25 and all hard gates, publish H70 as falsified and reset the target to the achieved Pareto knee.

**Success criteria (§5).** Decode failure rate < 2 % on 10k random genomes per rep. 100 % of decoded phenotypes pass the union-find single-component test (property test, 10k samples). Round-trip `genome → json → genome` is bit-exact (`to_bits`).

---

## 6. Phenotype → watertight B-rep STEP + DFM

### 6.1 Geometry pipeline
1. Planform SDF → marching squares at 0.05 mm → polygon simplify (Douglas–Peucker 0.01 mm) → fit G2 B-spline loops (OpenCASCADE `GeomAPI_PointsToBSpline`).
2. Thickness field → extrude a flat stock body (t_max), then **machined features as solid subtractions**: pockets (planar floors), rails (step faces), grinds (ruled/planar bevel faces), serrations (circular arcs, R ≥ tool radius). This makes STEP faces correspond to machining ops.
3. Export AP242 STEP via OCCT (`opencascade-rs` or a Python `OCP` sidecar). Validate with `BRepCheck_Analyzer`, check closed-shell volume vs mesh volume within 0.1 %, and compute mass at 4.43 g/cm³.
4. Keep the existing faceted STL/STEP export for FEM meshing and figures, labelled `artifact.kind = "faceted_preview"`.

### 6.2 DFM rules (karambit plugin; Chinese 3-axis CNC, Gr5 plate)
| Rule | Value | Rationale |
|---|---|---|
| Stock | 6.35 mm (1/4") or 6.0 mm Gr5 plate (AMS 4911 / ASTM B265 Gr5), finished faces ≥ 0.1 mm skim | Common plate sizes |
| Min internal corner radius (profile) | ≥ 1.0 mm (Ø2 mm end mill); ≥ 0.5 mm only for serration roots with a premium flag | Ti tool life; Ø1 mm tools are slow and fragile in Ti |
| Min wall / ligament | ≥ 2.0 mm through-thickness ligament; ≥ 1.2 mm skin around pockets | Chatter/vibration in Ti; existing `min_web` 3.08 mm precedent (`WHITEPAPER.md:265`) |
| Pocket floor | ≥ 0.8 mm; depth/width ≤ 3 | Tool reach |
| Accessibility | All features 2.5D from ±Z (two setups max) | Two-op flip with soft jaws |
| Tolerances | Profile ±0.05 mm, thickness ±0.05 mm, ring ID +0.10/−0.00 mm (ID ≥ 25.40 measured) | ISO 2768-m feasible; ring ID is a gauge-checked CTQ |
| Edges | Bevel by 4-axis or ground; serrations by Ø1.5–3 mm ball/radius tools | Shop practice |
| Surface | Ra ≤ 1.6 µm machined; bead-blast + optional Type II anodize | Fatigue knockdown (Marin k_a) uses machined |

### 6.3 Cost proxy (planning model; validate with ≥ 3 RFQs)
`cost_usd = C_mat + C_setup/qty + r_machine × (t_profile + t_pocket + t_bevel + t_serr) + C_finish`
- C_mat: blank 210 × 105 × 6.35 mm ≈ 140 cm³ ≈ 0.62 kg; Gr5 plate assumed **$35–60/kg** ⇒ $22–37.
- r_machine (China 3-axis, Ti): assumed **$25–40/h**.
- t_pocket ≈ removed_volume / MRR, MRR_Ti ≈ 2–4 cm³/min (roughing), plus finishing time ∝ pocket perimeter / 300 mm/min.
- Target: **≤ $65/pc at qty 200**, ≤ $45 at qty 1,000. Every design carries `cost_obs` with ±30 % error until RFQ-calibrated, then ±15 %.

**Success criteria (§6).** 100 % of v1 finalists produce STEP that imports into FreeCAD/OCCT with 0 BRepCheck errors. STEP volume vs FEM-mesh volume |Δ| ≤ 0.2 %. DFM violations = 0. ≥ 3 RFQ quotes obtained for the v1 finalist, and the cost proxy is within ±25 % of the median quote.

---

## 7. FEM tier ladder

| Tier | Model | Cost target | Use | Error bar requirement |
|---|---|---|---|---|
| T0 | Surrogate: GNN on plate mesh or neural field (SDF-conditioned) predicting {lat, ring, twist, tip SF, seq} | ≤ 5 ms GPU batch | Pre-screen 100 % of offspring; evaluate only top ~20 % at T1 | Held-out *family-grouped* MAPE ≤ 8 % on T1 labels; 90 % conformal interval coverage 0.88–0.92 |
| T1 | Existing DKT+CST plate (`crates/physics/src/fine.rs`), search area 2.0 mm² | ≤ 1.5 s/design/core (target; measure in PR-0.31.1) | Search fitness | Calibrated factor vs T2 per case, with residual σ published |
| T1c | T1 at 2 resolutions (certify) | 91 s/core today (measured) → ≤ 20 s after sparse LDLᵀ (faer/CHOLMOD) | Archive entry | Two-level agreement ≤ 5 %, else flag `mesh_disagree` (fixes T21) |
| T2 | **tet10 solid**, whole part (gmsh, 0.6 mm global, 0.15 mm at tip/serration roots), linear elastic, E = 113.8 GPa, ν = 0.34 | ≤ 15 s/design on RTX 3090 (≤ 1 M dof) | Finalists (top 1 %); labels for T0 | Mesh convergence: 3 levels, Richardson GCI ≤ 3 % on governing σ_vm |
| T3 | Submodel: tip/neck/ring with cut-boundary displacements from T2, h = 0.05 mm | ≤ 30 s GPU | Hot spots, SF reporting | GCI ≤ 2 %; report nodal-max, nodal-avg, and elem-mean (N2) |

### 7.1 Verification and validation
- **Code verification:** keep `crates/physics/src/verify.rs` (cantilever, clamped plate, curved beam, Kirsch hole Kt). Add tet10 patch tests, Kirsch 3D, and a Saint-Venant torsion bar (rectangle b/t = 3: τ_max = T/(0.267 b t²), Roark Table 10.7). Target error ≤ 1 % at the finest level.
- **Expected-check manifest** (fixes T19): `verify/expected.toml` lists check IDs × levels. Missing / NaN / duplicate ⇒ FAIL.
- **Calibration:** T1 → T2 factor per load case, with σ. Recalibrate when the representation changes (new G-B/E families invalidate the old domain).
- **Physical validation (v1 gate):** 3 machined coupons/prototypes from the first RFQ. (1) Ring pull to 3,000 N (SF 2 proof), no yield (dial indicator < 0.05 mm permanent set). (2) Chord twist to 1.82 N·m × 1.25 with a strain gauge at the predicted hotspot, |ε_meas − ε_FEM| ≤ 15 %. (3) Lateral 260 N tip load, deflection within 15 %.

### 7.2 Material model (Ti-6Al-4V Gr5, annealed)
| Property | Value | Source / status |
|---|---|---|
| σ_y (20 °C) | 828 MPa (min, screening) | Spec minimum (AMS 4911 / ASTM B265 Gr5); repo `fem.rs:12` |
| σ_u | 895 MPa min | Spec minimum |
| E, ν | 113.8 GPa, 0.34 | Typical handbook (MMPDS lists design allowables; use MMPDS A/B-basis once licensed) |
| ρ | 4.43 g/cm³ | Handbook |
| σ_y(100 °C)/σ_y(20 °C) | ≈ 0.90 (repo uses `yield_at`, JK2 = 0.8819 incl. stock) | To be sourced to MMPDS curves |
| Fatigue S_e′ (smooth, R = −1, 10⁷) | ~500 MPa planning value; Marin k_a (machined) ≈ 0.75, k_b ≈ 0.9 ⇒ S_e ≈ 340 MPa | Shigley Marin method; replace with MMPDS/vendor data |

### 7.3 Load-case basket (utility only; RS-karambit-v2)
| ID | Case | Magnitude | BC | Criterion |
|---|---|---|---|---|
| L1 | Lateral tip (hiker) | 180 N | Ring fixed (finger), grip contact | σ_vm,joint ≤ σ_y,joint (SF ≥ 1) |
| L2 | Lateral tip (hunter) | 260 N, aim 286 N | same | SF ≥ 1 |
| L3 | Ring pull | 1500 N, **SF ≥ 2** ⇒ 3000 N proof | Ricasso band fixed | SF ≥ 2 |
| L4 | Chord twist | 1.82 N·m body **and** tip zone | Ring fixed | SF ≥ 1 each (`fem.rs:55`) |
| L5 | Pry at tip | 4 mm engagement, worst angle 0–45° | Ring fixed | SF ≥ 1 |
| L6 | Baton (wood splitting) | Spine impact equivalent static 600 N at mid-spine (dynamic factor 2 on 300 N) | Edge supported on wood (elastic foundation k = 50 N/mm²) | SF ≥ 1.2 |
| L7 | Fatigue: repeated pry/twist | 0.6 × L4 and 0.6 × L5, 10⁵ cycles | — | Modified Goodman SF ≥ 1.5 |
| L8 | Thermal | −10 °C and 100 °C yield; stock −0.1 mm | All above | Joint knockdown (existing `joint_k`) |
| L9 | Tolerance | ±0.05 mm profile, ±0.05 mm t, edge flat ±0.05 | All | p05 across the tolerance cloud ≥ floor |
| L10 | Drop | 1.5 m onto granite, tip-first and ring-first (explicit dynamics deferred; static equivalent 2000 N at contact for now) | — | Report-only until v1.1 |

**Success criteria (§7).** T0 MAPE ≤ 8 % (grouped split). T1↔T2 calibration residual σ ≤ 7 % per case. T2 GCI ≤ 3 %. All verification checks within 1 %. Physical coupon agreement ≤ 15 %.

---

## 8. Adversarial / rare-event load-case discovery (replaces strike MC)

**Goal:** find utility-plausible load combinations that break a candidate first, then add them to a curated basket. Strike-media sampling is removed.

### 8.1 Load space Θ (10-D, bounded by physical plausibility)
Contact point s ∈ [0,1] along the edge/spine/tip; direction (θ, φ); magnitude F ≤ F_max(s) (hand-limited: ≤ 300 N, torque ≤ 3 N·m); couple about the chord T ≤ 3 N·m; support mode ∈ {ring-finger, full-grip, vice-at-ricasso}; temperature ∈ [−10, 100] °C; stock deviation δt ∈ [−0.1, 0]. Plausibility prior p(θ): hiker/runner use-profile mixture (elicited, documented in `loads/prior.toml`).

### 8.2 Methods
1. **Worst-case search:** CMA-ES (Hansen) on min SF(θ) over Θ using T0/T1 with a 200-eval budget per candidate. It returns θ* and SF*.
2. **Bayesian optimization** (GP-EI with a constraint on plausibility p(θ) ≥ p_min) for expensive T2 confirmation, 30 evals.
3. **Rare-event probability:** subset simulation or cross-entropy importance sampling for P_f = P(SF < 1 | p(θ)), reported *with the sampling distribution named* (per FB2/FB5: discovery sets ≠ prevalence estimates).
4. **Basket curation:** any θ* with SF* < 1.1 on ≥ 3 distinct Pareto designs is promoted to the curated basket `loads/basket/EC-xxxx.toml` with provenance (discovering run ID, design IDs). The basket is versioned, and a basket change bumps the RS-id.
5. **MC only for discovery:** Latin hypercube over Θ × tolerance, 10k samples per finalist at T0, to seed CMA-ES restarts.

**Success criteria (§8).** On a planted-weakness fixture (a notch inserted at a known location), CMA-ES finds a θ with SF within 5 % of the analytic minimum in ≤ 200 evals in ≥ 95 % of 20 seeds. The basket grows by ≥ 5 validated edge cases by v0.37. P_f estimates carry a CoV ≤ 0.3, with the sampling distribution recorded. Zero gel/bone/muscle code remains (grep CI test).

---

## 9. Evolution engine

### 9.1 Architecture
- **Island model:** 8 islands × 2 hosts. Each island runs a different operator mix and representation (G-A, G-B, G-B+G-D, G-E, G-B+TO, …). Ring migration every 10 gens, 2 migrants, with **migration events logged** (fixes T15).
- **Multi-objective core:** NSGA-III (Deb & Jain 2014) on 4 objectives: mass ↓, min SF over basket ↑, aesthetic ↑, cost ↓, with reference directions (Das–Dennis, p = 6 ⇒ 84 refs). Constraints by Deb's constrained-domination (feasibility first). Graded violation is used **only** for ranking infeasibles and is documented as such (fixes T24 wording).
- **Quality-diversity:** CVT-MAP-Elites (Vassiliades et al. 2018), 1,024 centroids on a 6-D descriptor: {mass, removed-volume fraction, silhouette curvature entropy, ring-to-blade sweep angle, spine-rail coverage, Fourier-descriptor PC1}. Elite replacement uses a **context-free** quality (min-SF × aesthetic / mass); novelty is kept separate (fixes T14).
- **Novelty search** (Lehman & Stanley 2011): k = 15 NN in descriptor space, archive threshold adaptive. Used as an island-level bonus on 2 of 8 islands only.
- **Surrogate-assisted EA:** T0 pre-screen with an expected-improvement-style acquisition. Only offspring in the top 20 % by predicted dominance plus 5 % random (exploration/calibration) go to T1. Retrain T0 every 2,000 new T1 labels.
- **Local refinement:** CMA-ES (σ₀ = 0.05 normalized) on the top-10 Pareto knees, 300 T1 evals each, constrained by all gates.
- **Topology-respecting crossover:** for G-B, crossover swaps whole subtrees of the skeleton graph rooted at matching anchors (ring, spine, tip). For G-A/E, SBX (η = 15) on aligned arc-length-parameterized control points. Children failing connectivity are repaired by a strut-insertion operator, never silently dropped.

### 9.2 Success criteria
- Hypervolume (normalized, ref point [100 g, 0 SF, 0 aes, $120]) at a fixed budget of 100k T1 evals ≥ **1.3×** the v0.27 crescent GA on the same RS-id and seed set (10 seeds, Wilcoxon p < 0.05).
- QD-score and coverage ≥ 60 % of the 1,024 cells filled.
- ≥ 10 distinct hard-PASS designs (pairwise Hausdorff ≥ 8 mm) ≤ 80 g.

---

## 10. Aesthetic model (anti-stick-figure, runner-beautiful)

**Current:** reference-similarity to C.6 (`aesthetic.rs:118`: `score = exp(−H/6) · exp(−EMD/0.05) · straight_pen`, hard Hausdorff ≤ 6 mm). This is renamed `style_conformance_C6` (FB1–FB6 consensus).

**v1 model (3 layers):**
1. **Hard priors (gates):** ring present, ID ≥ 25.4 mm measured (CMM spec), crescent continuity (curvature sign changes ≤ 3 along the spine), min ligament width / length ratio ≥ 0.12 everywhere (**anti-stick-figure**: no strut thinner than 12 % of its length), and solidity (area/convex-hull area) ≥ 0.45.
2. **Descriptors:** elliptic Fourier descriptors (20 harmonics), curvature histogram, ring-blade proportion, negative-space fraction, symmetry of pocket rhythm.
3. **Learned preference:** Bradley–Terry / pairwise logistic model on descriptors, plus a small CNN on 256 px silhouettes. Trained from (a) SWITCHBACK C.4–C.8 refs as anchors and (b) **human pairwise labels**: ≥ 2,000 comparisons from ≥ 15 raters (runners/hikers), on blinded standardized renders, with disagreement preserved. Held-out rater split.

**Success criteria (§10).** Pairwise accuracy on held-out raters ≥ 70 % (chance 50 %). The model's top-decile designs are preferred over the C.6 reference by ≥ 50 % of raters in a blinded A/B test (n ≥ 30). The stick-figure rule rejects 100 % of a 50-design curated stick-figure fixture and ≤ 2 % of the C.4–C.8 refs.

---

## 11. GLOBAL metric G2 (G1-compatible)

**Keep G1 frozen.** `metrics/global_metric.py` keeps producing G1 for historical rows, but a G1 row with any required input missing returns `status=INCOMPLETE` (no number shown in titles).

**G2 definition** (dimensionless, higher is better), computed only when `completeness == COMPLETE` and all hard gates under RS-karambit-v2 pass:

```
G2 = 0.30·min(SF_tip_T3, 2)          # tip, same cap as G1
   + 0.25·SPG_cert/4.0
   + 0.15·aes_pref                    # learned preference in [0,1]; falls back to style_conformance with flag
   + 0.20·mass_term                   # = clip((85 - m)/15, 0, 1): 85 g→0, 70 g→1  (holy-grail term)
   + 0.05·min(SF_fatigue/1.5, 1)
   + 0.05·min(SF_adv*/1.2, 1)         # worst adversarial basket SF
   − 0.05·cost_pen                    # max(0, cost-65)/65
```
- **Hard gates (G2 undefined if any fail):** ring ID ≥ 25.4 mm; blade ≥ 3.375 in on tip-to-heel, horizontal reach, and sharpened arc; sharpened edge ≤ 4.0 in; grip 60–80 mm; connected; Ti-6Al-4V; L1–L5 SF ≥ 1 (L3 ≥ 2); seq ≥ 1.2 (now hard, unifying T2); DFM violations = 0.
- **Compatibility:** publish G1 and G2 side by side for v0.27 designs. For `g3_tip+00_t60_tt3`, G2 is undefined (mass 84.8 > 80, seq 0.959 < 1.2), which is the honest status.
- **Uncertainty:** G2 is reported as mean ± 1σ propagated from the term error bars (T2 GCI, calibration σ, cost ±%). Two designs are "different" only if the intervals don't overlap.

**Success criteria (§11).** Property test: deleting any required input never increases rank (it yields INCOMPLETE). Bool inputs are rejected. Golden fixtures for 5 historical designs are reproduced to 1e-9.

---

## 12. Evidence / provenance layer

### 12.1 Types (Rust, serde, schema `evidence.v1`)
```rust
pub struct RunManifest { run_id: Ulid, git_sha: String, dirty: bool, toolchain: String, cargo_lock_sha256: String,
  host: String, cpu: String, gpu: Option<String>, part: String, rs_id: String, evaluator_ids: Vec<String>,
  search_method_id: String, descriptor_id: String, metric_id: String, seed: u64, config_sha256: String, env_resolved: BTreeMap<String,String> }
pub enum Obs<T> { Measured{ value: T, unit: Unit, evaluator: String, mesh_id: Option<String>, err: Option<ErrBar> },
                  Missing{ reason: MissingReason }, Failed{ reason: String }, NotApplicable{ reason: String } }
pub struct Verdict { rs_id: String, criterion: String, outcome: Pass|Fail|Incomplete|NotEvaluated, obs_refs: Vec<ObsId> }
pub enum Event { CandidateProposed{id, parents, op, op_version, rng_stream}, EvalStarted{eval_id,id,tier},
  EvalCompleted{eval_id, obs}, EvalFailed{..}, Selected{..}, ArchiveChanged{cell, old, new, quality_ctx}, Migrated{..},
  HumanDecision{..}, FigureRendered{fig_id, inputs_sha256, manifest} , RunTerminated{reason} }
```
**Rules:** no `bool` where a number is expected; no `unwrap_or_default` on observations (clippy `disallowed_methods` in evidence paths); JSON via serde only (no `format!` JSON); duplicate-key rejection on ingest (`serde_json` + a `deny_duplicate_keys` visitor). The event log is fsynced each generation, and the checkpoint stores `last_event_seq`.

### 12.2 Honest counters (derived from events)
proposals, decode_fail, gate_reject, T0_evals, T1_evals, T2_evals, cache_hits, unique_phenotypes (content hash), population_appearances, archive_insertions.

### 12.3 Claim-linked figures
Every figure has a `fig.manifest.json` with input artifact SHA-256 values, the obs IDs used, renderer git SHA, camera, colour semantics (`position|stress_vm|SF`), normalization (`shared|per-figure p99.5`) and clipping. CI step `ops/ci/verify_figures.py` recomputes the hashes and fails on drift. Captions are generated from obs, never literals (fixes T17/T18).

**Success criteria (§12).** The acceptance matrix AT01–AT24 (FB6) and A01–A22 (FB5) is implemented as tests, with ≥ 40 fixtures green in CI. Replay: an interrupted run at gens {3, 7, 12} resumed ≡ the uninterrupted run (bitwise on genomes/obs, same event sequence) on 3 seeds. Every README number resolves to an obs ID.

---

## 13. Logging schema for animations / eye candy

Per generation `g`, per island `i`, written to `runs/<run_id>/`:
- `events.jsonl.zst`: all events (above).
- `gen/<g>/pop.parquet`: id, island, parents, op, genome (f64 bits), objectives, descriptors, verdicts.
- `gen/<g>/thumbs/<id>.png`: 128 px silhouette, 3 colourways (plain / SF field / thickness), rendered by a headless `tiny-skia` rasterizer at ~0.5 ms each.
- `gen/<g>/archive.parquet`: CVT cell → elite id plus quality (context-free).
- `gen/<g>/pareto.parquet`: NSGA-III front plus ref-direction association.

Generated media (all with manifests): (1) **Lineage river**: a Sankey/phylogeny of the final top-20 back to gen 0, edges from `parents`, unknown ancestry drawn dashed. (2) **QD heat-map film**: MAP-Elites grid per generation → mp4 (ffmpeg, 12 fps). (3) **Pareto drift**: 3-D scatter (mass, SF, aes) with cost as colour, gif. (4) **Morph reel**: real evaluated parent → child sequences; interpolated frames watermarked "INTERPOLATED". (5) **Stress-field turntable**: T2 von Mises on the STEP-derived mesh, shared colour scale across designs, with a labelled colour bar. (6) **Adversarial load glyphs**: arrows at θ* with SF annotation.

**Success criteria (§13).** A 200-gen run produces all six media in ≤ 10 min of post-processing on one host. Every frame traces to a run ID and generation. Storage ≤ 2 GB per 200 gens × 16 islands × 64 pop (≈ 205k rows).

---

## 14. HPC plan

### 14.1 Hardware (verified this audit)
| Host | CPU threads | GPU | RAM | Reachable |
|---|---|---|---|---|
| xbabe2 | 128 | 1 × RTX 3090 24 GB | 125 GB | yes |
| xbabe3 | 128 | 1 × RTX 3090 24 GB | (not queried) | yes |
| xbabe1 | ? | ? | ? | **ssh timed out from box**; treat as optional |

**Red-team note:** the RTX 3090 (GA102) FP64 throughput is 1/64 of FP32 (~0.56 TFLOPS). Sparse CG is memory-bandwidth-bound (936 GB/s), so FP64 SpMV is still fine. Dense FP64 factorizations on the GPU are **not** a good fit, which favours iterative AMG-PCG and mixed precision (FP32 preconditioner, FP64 residuals, iterative refinement).

### 14.2 Baselines (measured or recorded)
- Certification (T1c) eval: **90.9 s/design single-core** (box, 8 cores available, release build).
- Solid tip (out-of-repo T3): **1,419.5 s** for 422,955 dof (xbabe2 JSON).
- Search-tier T1 eval: unmeasured. PR-0.31.1 adds `criterion` benches.

### 14.3 Plan
1. **Rust hot path:** replace the skyline Cholesky (`fine.rs:195-271`) with a supernodal sparse LDLᵀ (`faer` sparse Cholesky) plus **factorization reuse across load cases with the same BC** (L1/L2/L5/L6 share ring-fixed BCs ⇒ 1 factorization, multiple RHS). Expected ≥ 4× on T1c.
2. **Parallelism:** `rayon` work-stealing over candidates (replace the manual `thread::scope` chunking in `qd.rs:eval_batch`, which load-imbalances by `i % th`). 1 design per core; T1 is not internally threaded.
3. **Distributed:** a **Ray** cluster (Python driver, Rust evaluator as a `pyo3` extension or a subprocess) *or* a lightweight Rust gRPC job queue. Recommendation: **Ray**, because of the mature fault tolerance and object store, and because surrogate training is in Python anyway. Islands map to Ray actors, and evaluations are Ray tasks.
4. **GPU T2/T3:** gmsh tet10 mesh → assemble in Rust/`cudarc` or via PETSc (`-mat_type aijcusparse -pc_type gamg`) **or** NVIDIA AmgX classical AMG-PCG. The reference is FEniCSx/dolfinx with PETSc GAMG on CPU for verification parity. Batch 4–8 small solves concurrently per GPU via CUDA streams (0.4 M dof ≈ 34 M nnz ≈ 0.4 GB CSR, so 8 fit in 24 GB).
5. **Surrogate on GPU:** T0 GNN inference batched at 4k designs per call.
6. **Caching:** content-addressed cache keyed by `sha256(canonical genome bits ‖ evaluator_id ‖ rs_id)`, stored in LMDB on each host and replicated via Ray. Expected hit rate 10–25 % (elites, re-evaluated migrants).
7. **Accounting** (FB-consensus): fixed-workload benchmark `bench/fixed_1k` (1,000 frozen genomes, RS-id frozen), reporting wall, CPU-s, GPU-s, peak RSS, failures, and cache hits, with repeated runs ×3.

### 14.4 Targets
| Metric | Today | v0.35 target | v1.0 target |
|---|---|---|---|
| T1c cert eval / core | 91 s | 25 s | 15 s |
| T1 search eval / core | unmeasured | ≤ 2 s | ≤ 1 s |
| Search-tier throughput (2 hosts, 256 threads) | unmeasured (cert-tier ≈ 256×3600/91 ≈ 10k/h) | **≥ 50k T1/h** | ≥ 150k T1/h + 2M T0/h |
| T2/T3 solid 0.4 M dof | 1,419 s (Python CPU) | ≤ 60 s (PETSc CPU 32 cores) | **≤ 15 s (RTX 3090)** |
| Wall to 100k-eval campaign | n/a | ≤ 2 h | ≤ 45 min |

---

## 15. Manufacturability and cost (Chinese CNC shop)
- **Process:** waterjet or 3-axis profile from Gr5 plate → flip-op pockets/rails (2.5D) → 4-axis or fixtured bevel grind → serrations with a radius tool → deburr, bead-blast, optional anodize → laser mark.
- **Inspection:** ring ID go/no-go plug gauge 25.40 mm (must enter) and CMM first article; thickness micrometer at 5 points; blade measures (3 × 3.375 in) by optical comparator.
- **Material certs:** mill test report to AMS 4911 / ASTM B265 Gr5 (σ_y ≥ 828 MPa) required per heat. This retires the "828 provisional" caveat for production lots.
- **RFQ package (v0.37):** STEP AP242, 2D PDF drawing with GD&T, material spec, qty ladder 50/200/1000, finishing spec.
- **Success criteria:** ≥ 3 quotes; lead time ≤ 6 weeks; first article passes 100 % of CTQs; unit cost ≤ $65 at qty 200.

---

## 16. Generalization to any titanium machine part
- `PartSpec` plugin (§4.1) plus generic load cases, DFM, and cost. The demonstrator `part-bracket` is a Ti L-bracket with 2 × M5 holes, 2 load cases, and mass minimization at SF ≥ 2.
- **Success:** the same core, search, and evidence code; the bracket search reaches within 10 % of a SIMP reference topology mass on the same load case (compliance-equivalent). No knife terms appear in the core (grep test).

---

## 17. Patent / design strategy (process, not legal advice)
1. **Now:** preserve the disclosure timeline (repo public date, releases, figures). Brief a registered patent practitioner on the design (ornamental) vs utility tracks, US grace period vs foreign absolute novelty, and the fact that there is no design provisional.
2. Mark `docs/PATENT_DRAFT.md` as "UNFILED UTILITY DRAFT — not a design application" (header only; counsel decides further disclosure).
3. Design-application assets come from v1 finalists: 7 standard views (front, rear, top, bottom, left, right, perspective), solid-line claimed ornamental features, broken lines for unclaimed environment. These are generated from STEP by `ops/patent_views/` with manifests.
4. **Inventorship log:** a `HumanDecision` event for every human selection/modification (USPTO Nov-2025 revised AI-assisted inventorship guidance: natural persons only; contribution must be significant).
5. Prior-art search (counsel-led) on karambit/ring-knife designs before filing.

---

## 18. Risks
| Risk | P | Impact | Mitigation |
|---|---|---|---|
| H70 infeasible at margin | M | H | Falsification protocol §5; publish the Pareto knee honestly |
| Surrogate exploits model error (Goodhart) | H | M | 5 % random T1 audit, conformal intervals, T2 on all finalists |
| GPU solver parity bugs | M | H | dolfinx CPU reference; 50-design parity suite ≤ 0.5 % |
| Refactor breaks CI/known-negative | M | M | Small PRs; `d1_smoke` invariant; golden fixtures |
| Human-label scarcity for aesthetics | M | M | Start with 15 raters × 150 pairs; active learning |
| Public disclosure harms IP | H | H | Counsel now; restrict new figure disclosure |
| xbabe1 unavailable | H | L | Plan on 2 hosts |
| RFQ cost > proxy | M | M | Calibrate proxy; DFM cost term in G2 |
| Fatigue data uncertain | M | M | Conservative Marin factors; coupon test in v1 gate |

---

## 19. Success criteria summary (v1.0.0 release gate)
1. Evidence: 100 % of README/whitepaper numbers are obs-linked; AT01–AT24 green; replay equivalence on 3 seeds.
2. FEM: in-repo T2/T3 with GCI ≤ 3 %; T0 MAPE ≤ 8 % grouped; T2 ≤ 15 s on a 3090.
3. Search: HV ≥ 1.3× baseline at a fixed budget; ≥ 60 % CVT coverage.
4. **Mass:** at least one tier-2-verified, all-hard-gate (RS-karambit-v2) design ≤ **75 g**. Stretch: **< 70 g** (holy grail). Either way the Pareto front {mass, SF_min} is published with error bars.
5. Manufacturing: STEP AP242 clean; 3 RFQs; first article passes CTQs; coupon tests within 15 %.
6. Aesthetics: learned model ≥ 70 % held-out pairwise accuracy; blinded A/B vs C.6 ≥ 50 %.
7. Generality: bracket demo passes the §16 criteria.

---

## 20. References (real works only)
- Mouret, J.-B., Clune, J. (2015). *Illuminating search spaces by mapping elites.* arXiv:1504.04909.
- Vassiliades, V., Chatzilygeroudis, K., Mouret, J.-B. (2018). *Using Centroidal Voronoi Tessellations to Scale Up the MAP-Elites Algorithm.* IEEE TEVC 22(4).
- Gaier, A., Asteroth, A., Mouret, J.-B. (2018). *Data-efficient design exploration through surrogate-assisted illumination.* Evolutionary Computation 26(3). arXiv:1806.05865.
- Deb, K., Pratap, A., Agarwal, S., Meyarivan, T. (2002). *A fast and elitist multiobjective genetic algorithm: NSGA-II.* IEEE TEVC 6(2).
- Deb, K., Jain, H. (2014). *An Evolutionary Many-Objective Optimization Algorithm Using Reference-Point-Based Nondominated Sorting Approach (NSGA-III), Part I.* IEEE TEVC 18(4).
- Hansen, N., Ostermeier, A. (2001). *Completely derandomized self-adaptation in evolution strategies.* Evolutionary Computation 9(2). Hansen, N. (2016). *The CMA Evolution Strategy: A Tutorial.* arXiv:1604.00772.
- Lehman, J., Stanley, K. O. (2011). *Abandoning objectives: Evolution through the search for novelty alone.* Evolutionary Computation 19(2).
- Bendsøe, M. P., Sigmund, O. (2003). *Topology Optimization: Theory, Methods and Applications.* Springer.
- Sigmund, O. (2001). *A 99 line topology optimization code written in Matlab.* Struct. Multidisc. Optim. 21.
- Allaire, G., Jouve, F., Toader, A.-M. (2004). *Structural optimization using sensitivity analysis and a level-set method.* J. Comput. Phys. 194.
- Batoz, J.-L., Bathe, K.-J., Ho, L.-W. (1980). *A study of three-node triangular plate bending elements.* IJNME 15.
- Au, S.-K., Beck, J. L. (2001). *Estimation of small failure probabilities in high dimensions by subset simulation.* Prob. Eng. Mech. 16(4).
- Rubinstein, R. Y., Kroese, D. P. (2004). *The Cross-Entropy Method.* Springer.
- Roache, P. J. (1994). *Perspective: A method for uniform reporting of grid refinement studies.* J. Fluids Eng. 116 (GCI).
- Bradley, R. A., Terry, M. E. (1952). *Rank analysis of incomplete block designs.* Biometrika 39.
- Kuhl, F. P., Giardina, C. R. (1982). *Elliptic Fourier features of a closed contour.* CGIP 18.
- Budynas, R., Nisbett, K. *Shigley's Mechanical Engineering Design* (Marin factors, Goodman).
- Young, W., Budynas, R. *Roark's Formulas for Stress and Strain* (torsion of rectangular sections).
- MMPDS (Metallic Materials Properties Development and Standardization), Ti-6Al-4V sections (Battelle/FAA).
- Tools: Gmsh (Geuzaine & Remacle, IJNME 2009); FEniCSx/DOLFINx; PETSc (Balay et al.); NVIDIA AmgX; scikit-fem (Gustafsson & McBain, JOSS 2020); PyAMG; OpenCASCADE; Ray (Moritz et al., OSDI 2018); faer (Rust linear algebra).
- NASA-STD-7009 (models & simulations credibility). USPTO Design Patent Application Guide; USPTO Revised Inventorship Guidance for AI-Assisted Inventions (Nov 2025).


## Addendum (2026-10-12, owner decision): mass is soft — G2 notes

Jepson decision: mass > 80 g is **not** a hard promotion gate. Robust global fitness is the priority; mass is a strong
soft penalty in G, and the search keeps pushing toward < 80 g and then < 70 g. Implemented in v0.28 (RS-karambit-v1
version 2: `promote_eligible` no longer takes mass; `mass_target_g = 80`, `mass_stretch_g = 70`; 74–77 g band reported only).

G2 mass term (proposal, to be fixed in the G2 PR; G1 is unchanged and versioned):

- `P_mass(m) = a·max(0, m − 70)/10 + b·max(0, m − 80)/10`, a two-slope hinge: a moderate pull below 80 g toward 70 g
  and a steeper penalty above 80 g. Starting point **a = 0.05, b = 0.15** (above 80 g the slope is 4x G1's
  0.05 per 10 g over 77 g). Example: the provisional 84.80 g pays 0.074 + 0.072 = 0.146.
- Mass is never a G2 "undefined" condition. Only the structural / geometric hard gates make G2 undefined.
- The weights are calibrated so that no plausible structural gain (tip SF, SPG terms) makes a ≥ 85 g design outrank an
  otherwise-equal design at ≤ 80 g with SF ≥ 1.5. This goes in as a G2 property test.
- Reporting: every verdict prints mass as `soft: … (G penalty)`, never as a promotion failure (see `ops/ci/rs_verdicts.py`).
- Items above that said "mass ≤ 80 g hard gate" are superseded by this addendum.
