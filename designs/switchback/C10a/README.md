# SWITCHBACK Rev C.10a — true-sharp titanium hiking/utility karambit (current release candidate rc4)

**Status: CURRENT RELEASE CANDIDATE (rc4), owner-approved rc (Jepson Taylor, 2026-10-13) — NOT the design of record.** Nothing has been machined or physically tested. Rev C.9.3 ([`../C9.3/`](../C9.3/README.md)) is superseded: it **fails Gate S** (0.50 mm edge flat, 1.45 mm tip-zone flat) and must not become design of record.

**Gate changes (owner decision, Jepson Taylor, 2026-10-13 04:13 MDT).**
- **Gate S (new hard requirement, "genuinely sharp"):** S1 edge apex ≤ 0.20 mm (raw t at 0.05 mm ≤ 0.25) on both edges; S2 tip t(0.25/1/2 mm) ≤ 0.30/0.60/1.00 mm, monotonic over last 10 mm, taper ≥ 5 mm, plan width at 1 mm ≤ 1.3 mm; S3 edge ≤ 25°/side.
- **V2 tip 1 kN in-plane is RECORD-ONLY:** still solved and reported, no longer fails a design (the very tip may chip). Mass is not spent thickening the tip.
- Remaining gates: V1, V3–V7 at SF ≥ 1.5 with the owner's ≥ 5 % margin (≥ 1.575), plus Gate S and mass < 70 g.

These follow the SWITCHBACK C.9 human-max gate set (W69 loads, solid FEM on the B-rep, SF = 828 MPa / σvM). They are not a `jarambit rs-v2-eval` verdict: C.10a is a B-rep, not a genome. RS-karambit-v2 (this PR) encodes Gate S and V2 record-only.

| gate | case | SF / value | margin | note |
|---|---|---|---|---|
| S | true-sharp | apex max 0.152 / 0.189 mm; tip t 0.256 / 0.575 / 0.972 mm; 20.0° / 23.5° per side | | **PASS** (`data/sharp_C10a_recal.json`, `sharp_c10a_s2.json`) |
| V1 | twist 16.2 N·m | 1.768 | 17.9 % | mesh ladder 1.866 / 1.786 / 1.768 |
| V2 | tip 1 kN | 0.738 | — | **RECORD-ONLY** |
| V3 | spine 3427 N | 1.584 | 5.6 % | ladder 1.652 / 1.588 / 1.584; peak at spine-edge root |
| V4 | ring-back 3427 N | 1.767 | 17.8 % | |
| V5 | ring pull 641 N | 7.15 | | |
| V6 | pry 13.7 N·m (a1 / a2 / a1b / a2b) | **1.578** / 1.690 / 1.909 / 2.154 | **5.2 %** | **governor**; W80-S2 solved directly on C.10a (`data/v6_c10a.json`) |
| V7 | handle twist 16.2 N·m | 1.616 | 7.7 % | nose ladder 1.645 / 1.624 / 1.622 / 1.616 (`data/v7_c10a.json`) |
| V8 | mass | 64.841 g Gr5 | | −1.93 g vs C.9.3 |

Change vs C.9.3: edge grind only (outline and jimping unchanged). Edges are 0.15 mm apex to the point with no tip flat. A 10 mm unsharpened, full-thickness ricasso sits behind the spine-edge start (x 86 → 96; break 0.3 mm on drawing; `data/ricasso_check.json`).

Files: `cad/` B-rep STEP (sha256 441cfabc284efd63…) + reference STL 0.01 mm; `drawings/` 00–09 from the STEP by `drawings/draw_c10a.py`; `data/` gate JSONs.
Full machinist pack: `SWITCHBACK_RevC10a_RC4_machinist_pack.zip` (sha256 in SHA256SUMS). **Publication pending.**
Source of record: hiking-karambit commit a47979a, tag `switchback-revC.10a-rc4` (local).
