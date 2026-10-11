# Intelligence-Designed Titanium Utility Karambits via Monte-Carlo-Robust Evolutionary Search

*Draft v0.1 — target IEEE conference format, 6–8 pages.*

**Abstract** — We present *jarambit*, a Rust-native pipeline that evolves fixed-blade titanium hiking/utility karambit geometries (SWITCHBACK class) under hard manufacturability and safety constraints. A 14-parameter genotype is decoded into a connected genus-1 planar profile with a finger ring, a curved double-edged blade with serrations on both edges, millimetre-precision stock thickness and a flat brand pad. Fitness is the 5th-percentile score under Monte Carlo sampling of CNC/waterjet tolerances, combining edge-sharpness, serration coverage, ergonomics, mass and a bending safety factor for Ti-6Al-4V. A red-team gate rejects any candidate that is not a recognisable, connected, double-serrated curved karambit.

## I. Introduction
Motivation: outdoor/utility cutting (cord, webbing, rope, packaging) where a hooked, ring-retained blade gives controlled pull cuts and retention with gloves. Contribution list: (1) constrained genotype, (2) MC-robust fitness, (3) red-team gate, (4) open Rust implementation.

## II. Related Work
Evolutionary structural design; topology optimisation; robust design under tolerance; knife-edge mechanics (edge angle vs. retention in Ti alloys).

## III. Design Space and Genotype
Table of 14 genes with bounds (see `crates/genotype::bounds`). Thickness quantised to 0.1 mm.

## IV. Phenotype Decoding
Annular-sector blade, scalloped serration on concave and convex edges, tang, ring, brand pad; STL/STEP export.

## V. Physics Surrogates and FEM
Euler–Bernoulli root-bending surrogate (current), planned linear-elastic FEM verification.

## VI. Monte Carlo Robustness
Tolerance model (σ_t = 0.05 mm, σ_profile = 0.1 mm, σ_edge = 0.5°); p05 objective.

## VII. Evolutionary Search
(μ+λ) with elitism; NSGA-II planned.

## VIII. Red-Team Safety Gate
Rejection taxonomy: NotCurved, NoFingerRing, NotDoubleSerrated, Disconnected, UnsafeGeometry, ThicknessPrecision.

## IX. Results
*TBD — populated from `out/results.md`.*

## X. Limitations and Ethics
Utility/hiking framing; designs require human approval before any fabrication; no manufacturer contact by the pipeline.

## References
[1] K. Deb et al., "A fast and elitist multiobjective genetic algorithm: NSGA-II," IEEE TEVC, 2002.
