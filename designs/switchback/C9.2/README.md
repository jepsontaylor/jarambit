# SWITCHBACK Rev C.9.2 — titanium hiking/utility karambit (release candidate rc2)

**Status: RELEASE CANDIDATE — NOT the design of record.** Nothing is promoted; no part has been machined or physically tested.

**Which gate set.** The V1–V8 values below come from the SWITCHBACK C.9 human-max gate set used in the hiking-karambit study (W69-sourced loads, solid FEM on the B-rep, SF = 828 MPa / σvM). They are **not** a jarambit RS-karambit-v2 verdict: C.9.2 is a B-rep, not a jarambit genome, so `jarambit rs-v2-eval` has not been run on it, and its loads differ from RS-karambit-v2 in places (ring-back 3427 N here vs 3000 N provisional in RS-karambit-v2; ring pull 641 N here vs the 1500 N RS-karambit-v1 floor). Under that C.9 gate set every V1–V8 case is at SF ≥ 1:

| gate | case | SF | note |
|---|---|---|---|
| V1 | twist 16.2 N·m | 2.01 | carried from C.9.1 |
| V2 | tip 1 kN near-axial thrust | 1.644 | mesh-ladder extrapolation |
| V3 | spine 3427 N | 1.597 | |
| V4 | ring-back 3427 N | 1.755 | |
| V5 | ring pull 641 N | 8.20 | |
| V6 | lateral pry 13.7 N·m (a1 tip / a2 blade) | **1.529** / 1.616 | converged cut-boundary submodel (W75.1); 1.9 % margin |
| V7 | handle twist | 1.624 | converged |
| V8 | mass | 66.764 g Gr5 | B-rep |

Not promotable yet: promotion needs ≥ 5 % V6 margin (owner rule), and 1.9 % is within CNC notch tolerance. Before C.9.2 can be called a design of record it also needs an RS-karambit-v2 evaluation in this repo (or a documented mapping of the C.9 gates onto it), owner aesthetic sign-off and physical test. Next: W76 least-mass jimping relief.

Files: `cad/` B-rep STEP (the geometry of record for this candidate; not a manufacturing release) + reference STL; `drawings/` 00–09 generated from the STEP; `plates/` FEM wave plates W70–W75.1.
Full machinist pack (spec, docs, data, manifest) is published as a release asset: `SWITCHBACK_RevC9_2_RC_machinist_pack.zip` (sha256 in SHA256SUMS).
Public disclosure approved by the owner, Jepson Taylor (2026-10-12). Source of record: hiking-karambit tag `switchback-revC.9.2-rc2`.
