# SWITCHBACK Rev C.10c — true-sharp karambit, release candidate rc5

**Status: CURRENT RELEASE CANDIDATE (rc5). It was selected automatically by the soft-tip fitness, as the owner directed ("humans out of the loop", 2026-10-13). It is not the design of record.** Nothing has been machined or tested. Rev C.10a ([`../C10a/`](../C10a/README.md), PR #54) is now the previous RC.

C.10c starts from w80d (W80: spine-side tip drop plus core ramp, which more than halves the stress at the tip). It adds one local change, a spine-root shoulder: the spine grind narrows to 3.5 mm over x 98–108 (ramps from 94 and back by 116), and the edge bevel keeps its nominal slope out to 1.2 mm so the edge stays sharp. Mass 67.089 g Gr5, STEP sha256 4211f35b1c04d795…

| gate | SF | source |
|---|---|---|
| Gate S | PASS: apex 0.161 mm, S3 23.5°/side, tip t(1) 0.537 mm | B-rep ray probe |
| V1 twist 16.2 N·m | 1.739 | w80d g2 carry |
| V2 tip 1 kN (soft) | 1.245 | record (C.10a 0.738) |
| V3 spine 3427 N | **1.603** (governor, +6.9 %) | direct r0p2 |
| V4 ring-back 3427 N | 1.654 | ring-refined × g2 ratio |
| V5 ring pull 641 N | 7.55 | g2 |
| V6 pry 13.7 N·m | 1.611 | w80d submodel × g2 ratio |
| V7 handle twist 16.2 N·m | 1.620 | w80d nose submodel |

Fitness = min(V1, V3–V7)/(mass/100) × (1 + 0.20·min(V2, 1.5)/1.5): C.10c **2.786**, C.10a 2.673.
Files: `cad/` (STEP, STL), `drawings/` 00–09 generated from the STEP by `draw_c10c.py`, and `data/` (gate board, sharpness check).
Source of record: hiking-karambit 640f041, tag `switchback-revC.10c-rc5` (local).
