# Intelligence-Designed Titanium Utility Karambits via Monte-Carlo-Robust Evolutionary Search

**Jepson Taylor**

*Draft v0.2 — target IEEE conference format, 6–8 pages. Search snapshot is mh1 in progress, not a finished optimum.*

**Abstract** — We present *jarambit*, a Rust-native pipeline that evolves fixed-blade titanium hiking/utility karambit geometries (SWITCHBACK class) under hard manufacturability and safety constraints. A 20-gene continuous genotype (+ titanium grade) is decoded into a connected genus-1 planar profile with a 25.4 mm finger ring, a ≥60 mm grip, a curved double-edged blade with serrations on both edges, a sheath/holder interface (shoulders, thickness lands, retention detent), 0.1 mm-precision stock thickness and a flat brand pad. The primary fitness is **strength-per-gram** (governing lateral capacity / mass, N/g) at the 5th percentile of a Monte Carlo over CNC/waterjet tolerances and −10…100 °C, subject to hiker and hunter strength floors — not strength alone. Hard limits (blade **≥ 3.375 in on all three measures**, sharpened edge ≤ 4.0 in) are enforced as rejections, never penalties. A red-team gate rejects any candidate that is not a recognisable, connected, double-serrated curved karambit.

## I. Introduction
Motivation: outdoor/utility cutting (cord, webbing, rope, packaging) where a hooked, ring-retained blade gives controlled pull cuts and retention with gloves. Contribution list: (1) constrained genotype, (2) MC-robust fitness, (3) red-team gate, (4) open Rust implementation.

## II. Related Work
Evolutionary structural design; topology optimisation; robust design under tolerance; knife-edge mechanics (edge angle vs. retention in Ti alloys).

## III. Design Space and Genotype
20 continuous genes + `TiGrade` (see `crates/genotype::bounds`): blade arc, mid radius, thickness (0.1 mm quantum), edge angle, inner/outer serration pitch+depth, ring ID, ring wall, grip length, brand pad w/l, and seven holder-interface genes (ricasso land length, shoulder step, detent depth/position, friction length, holder drain Ø, holder shell wall). Sweep is derived (outer arc / outer radius) and repaired to ≥ 56°.

### III-A. Hard constraints (red-team rejects; `crates/redteam::check`, constants in `genotype::limits`) — ASSUMPTIONS, NEVER WEAKEN
1. **Blade length, all-three FLOOR (owner requirement, Jepson Taylor, 2026-10-11).** Each of (a) tip-to-heel straight distance (tip to the farther start-of-sharpening heel), (b) horizontal reach (blade extent perpendicular to the grip axis, heel to farthest blade point), (c) sharpened-edge arc (longer of concave/convex edge centrelines, heel→tip) must be **≥ 3.375 in = 85.725 mm**; a design is rejected if **any one** is below it. A 0.5 mm guard band sits *above* the floor (design floor `BLADE_FLOOR_MM` = 86.225 mm) so CNC/waterjet tolerance cannot drop a part under 3.375 in, and the sharpened edge is capped at **4.0 in = 101.6 mm** (`BLADE_EDGE_MAX_MM`). MC tolerance samples are re-gated, so p05 fitness collapses for designs that can fall under the floor in production. *Errata:* revisions before 2026-10-11 implemented this rule inverted (reject if any measure ≥ 85.225 mm) and capped the outer-arc gene at 72 mm, so every evolved design had a ~44 mm blade (tip 43.6–44.3 / reach 32.3–33.7 / arc 54.2–55.2 mm). All mh1 results produced before the fix are **PRE-BLADE-FIX** and quarantined; none is a winner. The outer-arc gene is now 77.1–92.3 mm (sharpened arc ≈ 86.3–101.5 mm). *Known gap:* the current phenotype starts the blade with its tangent parallel to the grip axis, which bounds horizontal reach at ≈68 mm while the edge stays ≤ 101.6 mm; meeting the reach floor needs a blade rake/cant gene (open work; a red-team canary test tracks it). Until then every candidate is rejected on horizontal reach (and on tip-to-heel for most radii).
2. **Grip floor:** ring-neck to guard (shoulder) ≥ **60 mm**; usable band 60–80 mm (reject outside).
3. **Finger ring:** ID **25.4 mm ± 0.5 mm**; wall ≥ 4 mm; ring at end of grip.
4. **Curved, never straight:** sweep ≥ 55°, mid radius ≤ 45 mm; blade must rise above the grip line (recognisable karambit).
5. **Double-edged, both edges serrated** (≥ 3 teeth each, depth > 0).
6. **Single connected solid:** one outer boundary, exactly one hole (ring), no self-intersection, ≥ 3 mm material around the ring hole.
7. **Flat brand pad** ≥ 6 × 12 mm, inside grip, clear of the holder detent.
8. **Thickness precision:** stock thickness is a multiple of 0.1 mm (mm-precision callout).
9. **Titanium only** (Ti-6Al-4V or Ti-3Al-2.5V); edge ≥ 14°/side (Ti edge roll).
10. **Holder pop-in interface** — see `docs/HOLDER_ENVELOPE.md` (shoulder stop ≥ 0.8 mm, ricasso thickness lands ≥ 5 mm, detent 0.4–1.2 mm inside friction zone, ≥ 30 mm grip exposed, drain Ø ≥ 3 mm, envelope ≤ 100 × 200 × 9 mm).
11. **Use framing:** hiking/utility/game-processing only; no combat framing; no manufacturer contact by the pipeline; any fabrication requires human approval.

### III-B. Fitness — strength-per-gram subject to floors (`crates/physics::primary_fitness`)
Strength S = min(blade-heel lateral capacity, grip-at-shoulder lateral capacity) at yield, with serration-depth section loss and a detent notch factor K_t = 1 + 0.6·(d/1.2). Lever = tip-to-heel (blade) and tip-to-heel + ricasso (grip). Floors (capacity at yield, lateral tip load): **hiker ≥ 180 N** (90 N × SF 2), **hunter ≥ 260 N** (130 N × SF 2, joint separation/field dressing), **ring pull ≥ 1500 N**. **These three floors are CONFIRMED by Jepson 2026-10-11 (firm design requirements, no longer placeholders; values unchanged).** Feasible: f = S / m (N/g); infeasible: f = −1 − 10·(floor deficit). Red-team reject on any MC sample: f = −1000. Objective = MC p05 of f. Strength alone is never optimised; the Pareto front (S vs m) and population diversity are logged each run (`pareto.csv/svg`, `diversity.svg`, `fitness.svg`, `history.csv`, `quarantine.csv`).
Material yield is derated linearly with temperature (Ti-6Al-4V −0.11 %/°C ref. 20 °C).

## IV. Phenotype Decoding
The blade is an annular sector about the origin: heel at angle π, sweep = arc length / outer radius, repaired to at least 56°. Both edges are scalloped. Below the guard the outline steps in at the shoulders, runs the grip, cuts a V detent, and closes around one finger-ring hole. The brand pad is an axis-aligned rectangle on the grip.

Export is one extrusion of that profile. An ear clip triangulates the outer ring (counter-clockwise) with the hole (clockwise) by bridging the hole's rightmost vertex to the nearest visible outer vertex. Caps sit at z = 0 and z = t with opposite winding; side walls follow the outer boundary and the hole so each wall normal points outward. The same triangles are written as ASCII STL and as a faceted AP214 `MANIFOLD_SOLID_BREP` (`CLOSED_SHELL` of planar `ADVANCED_FACE`s, no polyline). A release test on 30 random repaired genotypes found no boundary edge, no non-manifold edge, and one STEP face per triangle.

## V. Physics: Beam Surrogate and a Plate Check
Monte Carlo uses a beam section, because that evaluation is microseconds and a plate factor is not.

Let h_eff be the 14 mm blade height minus both serration depths, t the stock, L the tip-to-heel distance, and σ_y the yield at temperature. Lateral capacities (N) are

S_blade = σ_y · h_eff · t² / (6 L),

S_grip = σ_y · h_w · t² / (6 (L + L_ricasso)) / K_t,

with grip width h_w reduced by the detent depth and K_t = 1 + 0.6 · (d / 1.2). Ring pull on one wall is σ_y · wall · t. In-plane capacity swaps the section axes. Governing strength is min(S_blade, S_grip). Primary fitness is that strength over mass when the hiker (180 N), hunter (260 N) and ring-pull (1500 N) floors all hold.

A coarse 3D check with linear tetrahedra was tried and rejected. On a 50 × 14 × 3 mm cantilever, one, two and four elements through the thickness all returned about 7 % of the beam bending stress and about 1.4 % of the beam tip deflection. The same solver on a straight bar in tension was within 40 % of F/A, so the element locks in bending rather than mis-scaling the constitutive law. The blade model is therefore a flat Kirchhoff plate on the ear-cut outline: a discrete Kirchhoff triangle for lateral bending [2] and a constant-strain membrane triangle for in-plane load and ring pull. Serration scallops are not meshed; blade bending stress is scaled by h / h_eff and in-plane stress by (h / h_eff)². Poisson's ratio is 0.34. For a tip load the finger-ring nodes are fixed (the hand). For ring pull the ricasso band is fixed and the hole is loaded. Those are different supports, so each case has its own factorisation. Degrees of freedom are (u, v, w, θx, θy); a mesh that would exceed 420 free dofs falls back to the surrogate.

Release checks, all passing:

- Cantilever, ν = 0, 8 × 2 quads, L = 50 mm, width 14 mm, t = 3 mm, E = 113.8 GPa. Tip deflection must lie in 0.70–1.35 of F L³ / (3 E I) and the peak surface von Mises in 0.50–1.80 of 6 F L / (b t²).
- Uniform tension patch: membrane von Mises in 0.70–1.40 of F / (width · t).
- Twenty random in-spec karambits, Ti-6Al-4V at 20 °C, none failing to mesh. Median plate/surrogate governing lateral strength **0.526** (range about 0.20–0.84). The plate grip usually governs: the ring support puts a longer moment arm through the grip than the surrogate's ricasso lever. Blade-only ratios cluster nearer 1.
- Ring pull on eight designs versus the two-wall net section σ_y · 2 · wall · t: median inside 0.15–4. The surrogate is the stricter one-wall formula.

The plate solve is reported once, at 20 °C, on the logged winner. It is not inside the 10k-sample loop. Temperature scales yield only, so a single unit-load stress would convert to any temperature; the tolerance cloud still changes the mesh every draw. `JARAMBIT_FEM=1` (mh2) still does not factor the plate per draw. It scores each candidate from one nominal 20 °C plate solve, then applies the beam-surrogate Monte Carlo knockdown: robust strength = plate strength × (p05 surrogate strength / nominal surrogate strength), and the same ratio on ring pull. The firm floors, 180 / 260 / 1500 N, apply to that robust estimate. A missed plate mesh is infeasible. This ratio is not a scale that forces the plate to match the beam.

## VI. Monte Carlo Robustness
Each candidate is scored on an exact sample count (default 10 000 in the live search). Sample i is seeded from a mix of the run seed and i, so the multiset does not depend on the thread count. Threads default to at most 48 (`JARAMBIT_MAX_THREADS` raises that per host, still clamped to the machine). Thickness noise (σ = 0.03 mm) is applied after the red-team thickness gate, which sees the nominal 0.1 mm stock. Profile, ring, edge, detent, shoulder and shell-wall genes are perturbed and not clamped; the red team re-gates every draw. A draw that fails the gate contributes −1000 to fitness, so a design that fails on 5 % or more of draws cannot win on p05. Temperature: 12.5 % of draws at −10 °C, 12.5 % at 100 °C, the rest uniform on that interval.

Cut media are a second objective, not part of the primary scalar. Each draw picks wood, cord/webbing, hide, muscle, bone or gel (weights 20/20/15/20/10/15). The medium supplies a work level, an edge-lead fraction (in-plane versus lateral) and an edge-quality need. Margin is the worse of structural reserve and (sharpness + serration − need). Bone is more lateral than hide; a dull edge fails cord. p05 of that margin is maximised beside strength-per-gram. It cannot zero the robust strength score.

The holder pop-in proxy is inside the same gate. A Kydex-like shell (E = 2.2 GPa, 12 mm tab, 10 mm snap) gives insertion 6.6 · wall³ · detent newtons and draw at 0.55 of that. The allowed window is 3–80 N insertion and 1.5–45 N draw, on the nominal design and on every perturbed draw.

## VII. Evolutionary Search
Search is NSGA-II with constraint domination [1]. A design that clears the floors with positive fitness dominates one that does not; among infeasible designs, the less-negative penalty wins. Feasible objectives, in order: maximise p05 strength-per-gram (primary), minimise nominal mass, maximise p05 cut margin. Crowding uses those three axes, with infinite crowding at the extremes so the unique primary-best is kept. Ten percent of each generation are random immigrants. Mutation scale shrinks from 0.10 to 0.02 across the run. Islands are optional; the logged best is still the feasible individual with the highest primary fitness. Every fifth generation the primary-best migrates around the ring of islands if it beats the neighbour's worst. A checkpoint file resumes a run; history and quarantine logs append.

The live search **mh1** (started 2026-10-11 ~10:23Z) is 20 independent island pairs, not one shared population: six on xbabe2 (seeds 1001–1006, 10k samples), seven on xbabe3 (three of them at 50k samples) and seven on xbabe1. Each process is 2 islands, population 48, 60 generations, 16 threads, `nice` 19. Cross-host migration is not wired. A yield guard pauses only these processes if the host CPU average reaches 82 %.

## VIII. Red-Team Safety Gate
Rejection taxonomy: BladeTooShort{tip_to_heel|horizontal_reach|sharpened_arc}, BladeEdgeTooLong, GripOutOfBand, RingIdOutOfSpec, NotCurved, NotKarambit, NoFingerRing, NotDoubleSerrated, Disconnected, BrandPad, Holder, NonTitanium, ThicknessPrecision, UnsafeGeometry. Geometric checks, beyond the gene values, require a serration ripple on both edges, a hooked planform, a single connected outline (a legitimate grip edge is long; a spike is not), an axis-aligned brand pad, and holder insertion/draw inside the window above. Applied to every candidate in every generation and to every MC sample; rejected phenotypes are quarantined to `quarantine.csv`.

## IX. Results
Plate and export checks are in §V and §IV. They are release tests, not a fitted scale factor: the plate is not multiplied to match the beam.

**mh1 snapshot, 2026-10-11 10:29Z** (not a finished study; **PRE-BLADE-FIX** — run under the inverted blade rule, every design is under 3.375 in and quarantined). On the six xbabe2 island pairs the log lines then in `out/mh1/xbabe2_s1001`–`s1006` were generations 14–20 of 60. Best p05 strength-per-gram was 12.8–13.9 N/g, governing surrogate strength 466–542 N at 32–37 g, thickness 4.3–4.5 mm, grip 61–65 mm, rejected count 0. A positive primary fitness means that candidate's Monte Carlo p05 cleared the 180 / 260 / 1500 N floors on the beam model. The same minute, the read-only monitor in `COORD.md` reported best p05 13.921 N/g on xbabe2, 13.709 N/g on xbabe1 (generations 12–19) and 13.729 N/g on xbabe3 (10k groups near generations 12–19; the three 50k groups still on generations 1–2). Plate numbers for each winner are written when that process exits (`best_report.md`). Do not read 13.9 N/g as the optimum.

## X. Limitations and Ethics
The beam surrogate and the plate disagree on the grip lever: the hand-fixed plate is the longer, usually weaker, path. The default search optimises the surrogate. `JARAMBIT_FEM=1` optimises the nominal plate times the surrogate knockdown, and that knockdown is still the surrogate's shape sensitivity, not the plate's. Serrations and the edge bevel are scales, not geometry, in both models. The outline used by the plate is decimated; a sharp detent can dominate membrane stress. Linear tetrahedra are the wrong element for this thickness and are not used. mh1 islands do not exchange individuals across hosts, and the run was still open when §IX was written. Utility/hiking framing only. Designs require human approval before any fabrication. The pipeline does not contact manufacturers.

## References
[1] K. Deb, A. Pratap, S. Agarwal, and T. Meyarivan, "A fast and elitist multiobjective genetic algorithm: NSGA-II," IEEE Trans. Evol. Comput., vol. 6, no. 2, pp. 182–197, 2002.

[2] J.-L. Batoz, K.-J. Bathe, and L.-W. Ho, "A study of three-node triangular plate bending elements," Int. J. Numer. Methods Eng., vol. 15, no. 12, pp. 1771–1812, 1980. doi:10.1002/nme.1620151205.
