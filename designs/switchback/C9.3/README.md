# SWITCHBACK Rev C.9.3 — titanium hiking/utility karambit (current release candidate rc3)

**Status: CURRENT RELEASE CANDIDATE (rc3) — NOT the design of record.** Nothing has been machined or physically tested. Rev C.9.2 ([`../C9.2/`](../C9.2/README.md)) is the **previous RC**; Rev C.8 remains the fallback.

**Which gate set.** The V1–V8 values below come from the SWITCHBACK C.9 human-max gate set used in the hiking-karambit study (W69-sourced loads, solid FEM on the B-rep, SF = 828 MPa / σvM, gate SF 1.5, owner promotion rule ≥ 5 % margin). They are **not** a jarambit RS-karambit-v2 verdict: C.9.3 is a B-rep, not a jarambit genome, so `jarambit rs-v2-eval` has not been run on it, and its loads differ from RS-karambit-v2 in places (ring-back 3427 N here vs 3000 N provisional; ring pull 641 N here vs the 1500 N RS-karambit-v1 floor). Under that C.9 gate set all V1–V8 pass with ≥ 5 % margin:

| gate | case | SF | margin | note |
|---|---|---|---|---|
| V1 | twist 16.2 N·m | 2.016 | 34.4 % | |
| V2 | tip 1 kN near-axial thrust | 1.644 | 9.6 % | |
| V3 | spine 3427 N | **1.597** | 6.5 % | **governor**; W77 re-solve on the C.9.3 solid (94.8k tets) |
| V4 | ring-back 3427 N | 1.755 | 17.0 % | |
| V5 | ring pull 641 N | 8.20 | | |
| V6 | lateral pry 13.7 N·m (a1 / a2) | 1.632 / 1.697 | 8.8 % / 13.1 % | W76 converged; was 1.9 % on C.9.2 |
| V7 | handle twist 16.2 N·m | 1.613 | 7.5 % | W77 nose submodel ladder, converged |
| V8 | mass | 66.773 g Gr5 | | +0.009 g vs C.9.2 |

Change vs C.9.2 (W76): least-mass thumb-seat jimping relief, 7 notches R1.0 / depth 0.35 / pitch 2.0 (was R0.8 / D0.45), land 0.48 mm. Values: `data/w77_results.json` (board), `data/w76_results.json`, `data/jimp_c93.json`.

Before C.9.3 can be called a design of record it still needs an RS-karambit-v2 evaluation in this repo (or a documented mapping of the C.9 gates onto it), owner aesthetic sign-off and physical test.

Files: `cad/` B-rep STEP (geometry of record for this candidate; STEP sha256 3a818183bcb5b9a9…; not a manufacturing release) + reference STL; `drawings/` 00–09 regenerated in-repo by `drawings/draw_c93.py` from the committed STEP and `data/` (05 needs `C8_STEP=` the hiking-karambit Rev C.8 STEP); `plates/` FEM wave plates W70–W77.
Full machinist pack: `SWITCHBACK_RevC9_3_RC3_machinist_pack.zip` (sha256 in SHA256SUMS). **Publication pending** — it will be attached to the v0.32.0 release-candidate GitHub release (with the C.9.2 pack as previous RC).
Source of record: hiking-karambit commit 94d9f4d, tags `switchback-revC.9.3-rc3` / `v0.9.3-rc.3`.
