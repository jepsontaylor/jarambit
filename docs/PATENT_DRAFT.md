# PATENT APPLICATION — DRAFT (NOT FILED)

> **DRAFT / NOT FILED / NOT LEGAL ADVICE.** Prepared by the inventor for counsel review. No prior-art search has been performed. Nothing here is a manufacturing release; the described embodiment is an engineering provisional and is **not promoted**. Version: jarambit v0.32 (release candidate), 2026-10-12. **Simulation status:** the embodiment meets the RS-karambit-v1 screen in simulation but does **not** meet the v1 gate set RS-karambit-v2 (human-maximum twist, tip and spine loads, seq ≥ 1.2, finger-bearing width, holder envelope; `docs/WHITEPAPER.md` §IV-A). No embodiment has been built or tested.

**Inventor:** Jepson Taylor
**Type:** Non-provisional utility application (draft)

## TITLE
Ring-Retained Titanium Crescent Karambit Having Continuous Spine Rails, a Tip-Outline/Stock-Thickness Law, and Dual-Face Ring Contrast Channels

## CROSS-REFERENCE
None (draft). Related technical disclosure: `docs/WHITEPAPER.md` (v0.32), `docs/WHITEPAPER_g3_neckrail.md` (v0.1.0-g3neckrail).

## FIELD
The invention relates to fixed-blade cutting tools, and more particularly to a one-piece titanium-alloy hooked (karambit) utility knife with an integral finger ring, and to a computer-implemented method of designing such a knife.

## BACKGROUND
Karambit-style knives combine a curved, hooked blade with a finger ring that retains the knife during pull cuts on cord, webbing and packaging. Lightweight titanium versions face three conflicting demands: (i) the hooked tip is thin and is the usual point of failure under lateral and prying loads; (ii) mass must stay low for hiking carry; (iii) the ring and neck must survive ring-pull and torsion while the user grips with gloves. Conventional designs set a uniform stock and grind by hand, which either over-builds the handle or leaves the tip weak. Decorative anodizing on worn ring faces wears off quickly.

## SUMMARY
A one-piece Ti-6Al-4V crescent karambit comprises a finger ring, a neck, a grip, and a curved double-edged blade terminating in a hooked tip. (1) **Continuous rails**: raised spine rails of width ≈ 3.2 mm run without interruption from the neck through the grip into the blade, carrying lateral and torsional load past lightening pockets. (2) **Tip-outline/stock law**: the stock is 6.0 mm and tapers along a grind law from a taper start (~135 mm from the ring) to a governed tip thickness (≈ 3.10 mm; "tt3" = +0.3 mm over the prior law) while the last three outline control points of the tip are held to a fixed envelope, so the peak solid stress 4 mm from the point stays below allowable with solid tip safety factor ≥ 1.5. (3) **Dual-face ring contrast channels**: a recessed annular channel on both faces of the ring, concentric with the bore and bounded by full-thickness rims, carries a contrast anodize below the worn faces in the ring's low-stress zone. The embodiment `g3_tip+00_t60_tt3` weighs 84.80 g, has ring ID 25.46 mm, tip SF 1.534, strength-per-gram 4.147 N/g (tip×SPG 6.362), meets the RS-karambit-v1 screen in simulation, and does not yet meet RS-karambit-v2.

## BRIEF DESCRIPTION OF THE DRAWINGS
All drawings are generated from the embodiment's STL by `ops/render/patent/figures.py` (orthographic line-art; manifest `docs/patent/figures/figures.json` with input and output sha256, checked in CI).

- **FIG. 1** is a perspective view of the knife. ![FIG. 1](patent/figures/fig01.png)
- **FIG. 2** is a front elevation (left face). ![FIG. 2](patent/figures/fig02.png)
- **FIG. 3** is a rear elevation (right face). ![FIG. 3](patent/figures/fig03.png)
- **FIG. 4** is a top view (edge-on). ![FIG. 4](patent/figures/fig04.png)
- **FIG. 5** is a bottom view (edge-on). ![FIG. 5](patent/figures/fig05.png)
- **FIG. 6** is a left end view (ring end). ![FIG. 6](patent/figures/fig06.png)
- **FIG. 7** is a right end view (tip end). ![FIG. 7](patent/figures/fig07.png)
- **FIG. 8** is the front elevation of FIG. 2 with reference numerals. ![FIG. 8](patent/figures/fig08.png)
- **FIG. 9** (supporting, not a formal drawing) — plan FEM colormaps of components 10, 20, 30/32 and 40 (`docs/figures/components/`, WHITEPAPER §III-H).
- **FIG. 10** (to be drawn) — ring cross-section through the dual-face channels; **FIG. 11** (to be drawn) — thickness vs. arc length (grind law, `evidence/wave27/g3_tip+00_t60_tt3_grind_law.json`); **FIG. 12** (to be drawn) — flow chart of the design method.

### Reference numerals
| numeral | element |
|---|---|
| 10 | finger ring |
| 12 | ring bore (finger-bearing surface) |
| 20 | grip / spine (continuous spine rails) |
| 30 | concave (inner) sharpened, serrated edge |
| 32 | convex (outer) sharpened, serrated edge |
| 40 | hooked tip |
| 50 | distal thickness taper / relief pockets |

## DETAILED DESCRIPTION
### Overall form
Referring to FIGS. 1–8, a single connected planar Ti-6Al-4V body, 6.0 mm stock, has a finger ring 10 with a bore 12 (ID 25.4 ± 0.5 mm; embodiment 25.46 mm, wall ≈ 5.74 mm), neck (fillet radius ≈ 17.8 mm, length ≈ 9.9 mm), a grip 20 of 60–80 mm (embodiment 61.0 mm) and a curved double-edged blade with a concave edge 30 and a convex edge 32, terminating in a hooked tip 40, whose tip-to-heel (97.0 mm), horizontal reach (87.5 mm) and sharpened arc (101.1–101.3 mm) each meet or exceed 3.375 in while the sharpened edge stays ≤ 4.0 in. Both edges are serrated (large/small/fine). Inner/outer edge angles ≈ 22°.

### Callout A — ring face channels
On each face of the ring 10, an annular recess of depth ≈ 0.6 mm extends from r_bore + 1.6 mm to r_OD − 1.6 mm with an R0.5 floor fillet. Full-thickness rims at bore and OD protect the anodized channel floor from wear. Ring-pull safety factor stays ≈ 9–11 (embodiment 11.6), so the channel removes mass at no structural cost.

### Callout B — continuous rails
Spine rails of width ≈ 3.18 mm (gene `rail_w`) run along the grip 20 continuously from the neck to the blade. Ablation in wave25 showed that a neck graft alone lowers lateral capacity, and that restoring full continuous rails raised SPG (3.60 → 3.81 N/g at 82.4 g). Lightening pockets, fullers and a ring flute (depth ≈ 1.64 mm over ≈ 236° of arc) sit between the rails.

### Callout C — tip-outline / stock law
Stock thickness t_stock = 6.0 mm is held to the taper start x0 ≈ 135 mm, then reduced along the grind law (taper 50) to t_tip ≈ 3.10 mm at the tip 40. The tip outline control points (cp36–cp38) are held at the base envelope (+0 offset). Across 24 arms (tip offset −1/0/+1 mm × stock 5.8/6.0 mm × t_tip +0/+0.3 mm) only the +0 outline passed every hard gate; +0.3 mm tip stock raised solid tip SF from 1.525 to 1.534 for +0.21 g, giving the best global metric G1 = 0.9805.

### Design method
A genotype of control points and feature genes is decoded into an outline and thickness field, exported as a watertight STEP solid, screened by plate FEM (lateral 180/260 N, ring pull 1500 N, chord torsion 1.82 N·m), checked by a solid tetrahedral tip submodel, made robust by Monte Carlo over tolerances, −10…100 °C and cut media, and evolved by island NSGA-II. Designs are ranked by G1 = 0.35·min(SF_tip,2) + 0.35·SPG/4 + 0.20·aes − 0.05·max(0,m−77)/10 − 0.05·max(0,1.2−seq)/1.2. Hard limits reject; they are never penalties.

### Finger-bearing width (planned embodiment)
The bore 12 bears on the finger along the finger axis; RS-karambit-v2 asks for ≥ 10 mm bearing width, which a 6 mm planar stock cannot give. A planned embodiment (roadmap PR-0.33.4) adds a ring flare or 3D ring lip so the bore length along the finger axis reaches ≥ 10 mm while the grip and blade keep the planar stock. See claim 15.

## CLAIMS (draft)
1. A one-piece titanium-alloy karambit knife comprising: a finger ring having a bore; a neck joined to the ring; a grip; a curved blade having a concave edge and a convex edge, both sharpened, terminating in a hooked tip; and at least one spine rail extending continuously from the neck through the grip into the blade, the rail being thicker than adjacent lightening regions; wherein the blade thickness is constant at a stock thickness up to a taper start and decreases along a predetermined grind law to a tip thickness of at least 50% of the stock thickness at the tip governing section.
2. The knife of claim 1, wherein the stock thickness is 5.8–6.2 mm and the tip thickness is 2.9–3.3 mm.
3. The knife of claim 1, wherein each face of the finger ring has an annular recessed channel concentric with the bore and bounded by full-thickness rims at the bore and at the ring outer diameter.
4. The knife of claim 3, wherein the channel floor bears an anodized finish of a color contrasting with the ring faces.
5. The knife of claim 3, wherein the channel depth is 0.4–0.8 mm per face and the channel lies 1.0–2.5 mm from each rim.
6. The knife of claim 1, wherein the bore has a diameter of 25.4 ± 0.5 mm.
7. The knife of claim 1, wherein the tip-to-heel distance, the horizontal reach, and the sharpened arc length are each at least 85.7 mm and the sharpened edge is at most 101.6 mm.
8. The knife of claim 1, wherein both edges are serrated.
9. The knife of claim 1, wherein the alloy is Ti-6Al-4V and the knife mass is 78–88 g.
10. The knife of claim 1, further comprising a ring flute recessed into the ring over an arc of 200–270°.
11. A titanium karambit comprising a finger ring whose two faces each carry a recessed annular contrast channel bounded by full-thickness rims, the ring joined by tangent neck fillets to a single-spline crescent planform ending in a hooked double-edged blade.
12. A computer-implemented method of designing a knife, comprising: encoding a candidate as a genotype of outline control points and thickness-law genes; decoding the genotype into a watertight solid; rejecting candidates failing any of a set of hard geometric and strength gates; computing plate-FEM and solid tip-submodel safety factors under Monte Carlo sampling of tolerances and temperature; evolving a population by multi-objective island search; and ranking surviving candidates by a single scalar combining tip safety factor, strength-per-gram, an aesthetic score, mass, and failure sequence.
13. The method of claim 12, wherein the hard gates include a minimum blade length on each of three measures and a maximum sharpened-edge length.
14. The method of claim 12, further comprising outputting the ranked design as a STEP file for subtractive manufacture.
15. The knife of claim 1, wherein the finger ring comprises a flare or lip such that the bore length measured along the bore axis exceeds the stock thickness of the grip and is at least 10 mm.
16. The method of claim 12, wherein every reported performance value is generated from stored evaluation records and is accompanied by the requirement set against which it was judged, and a candidate is reported as meeting a requirement set only when every hard gate of that set is met.

## ABSTRACT
A one-piece titanium karambit has a finger ring, a neck, a grip, and a hooked double-edged blade. Continuous spine rails run from neck to blade past lightening pockets. Blade thickness follows a stock/tip law (6.0 mm stock tapering to about 3.1 mm at the tip) with a fixed tip outline, so the hooked tip keeps a solid tip-submodel safety factor above 1.5 at about 85 g under screening loads. Both ring faces carry recessed annular contrast-anodize channels bounded by full-thickness rims. A computer-implemented evolutionary method with FEM and Monte Carlo verification produces the geometry.
