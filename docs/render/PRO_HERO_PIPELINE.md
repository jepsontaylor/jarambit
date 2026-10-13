# Pro-hero render pipeline (SWITCHBACK, any CAD)

Code in `ops/render/pro/` (landed from branch `render/pro-hero` on top of the signature-mark merge, main 58bce30).
Hero model: **SWITCHBACK Rev C.10a**, `switchback_revC10a_ground.step`, sha256 `441cfabc284efd63…`
(64.841 g). Every C.10a image is labelled **design candidate, not certified** (V2-S tip SF fails, record-only).

## Steps
| step | file | what it does |
|---|---|---|
| ingest | `marketing/ingest.py` | STEP → OCC tessellation (linear 0.01 mm, angular 0.1 rad), B-rep analytic normals, region tags |
| art | `pro/upscale_art.py` | clean **no-signature** art `psychedelic_wrap_nosig.png` (2048×768, sha 218c31c6…) → Real-ESRGAN x4plus → 8192×3072 16-bit PNG, provenance json |
| prep | `pro/prep.py` | wall-normal repair; edge-sharpness QA; planar art mapping; signature placement solver |
| render | `pro/pro_hero.py` + `pro/shots.json` | Cycles OptiX stills, per-shot QA, 32-bit float multilayer EXR (ZIP, lossless) master + 16-bit PNG |
| film | `pro/film_art_edition.json` + `pro_hero.py --anim` | directed shots, absolute-frame state, per-frame QA |
| any CAD | `marketing/plan.py` `KNOWN_SOURCES` | new CAD = one hash entry; everything downstream is recomputed from the mesh |

## Root cause of the boxy, stepped edge bands (Jepson's crop)
**It's the CAD export, not the renderer and not the metal.** The blade outline in the STEP is a polyline. C.9.3 has
1,423 planar B-rep faces, and 1,398 of them are side-wall strips. Neighbouring strips differ by a median 4.9°
(p90 11°). The ingest gives each B-rep face its exact analytic normal, which is correct per face, so every strip is a
perfectly flat mirror. In a mirror material each strip then reflects one constant patch of the studio, and you
get the stepped rectangular bands. Making the tessellation finer can't remove facets that are in the B-rep
itself (0.01 mm deflection was already used). A part machined literally from this file would also show faint
flats. **Upstream fix:** export the outline as a B-spline or arcs. **Render fix (`prep.smooth_wall_normals`):** on
wall corners (|n·y| < 0.5), use the area-weighted average of adjacent wall normals within a 25° crease angle.
Vertex positions don't change, real corners (> 25°) stay hard, and broad faces, bevels and analytic surfaces
keep their analytic normals. On C.10a this changed 106,408 wall corners.

## Sharpness (hard rule)
`edgeqa.edge_width` measures the land width from the mesh along every wall strip bounded on both sides by
bevel/edge/serration faces. The gate is p99 ≤ 0.20 mm, and the worst point is reported.
C.9.3 FAILS: p99 1.45 mm (the illegal tip-edge flat). C.10a PASSES: p95 0.154, p99 0.158 mm, max 0.29 mm at an
isolated bevel run-out. Geometry is never altered to make an edge look sharp.

## Art and look
- Planar XZ mapping, the same world mapping on both faces (through-print). The art's dark starfield lands on the blade.
- Material: Principled. Art is sRGB 16-bit 8K with Cubic filtering and sat ×1.35 / val ×1.45, metallic 0.82 (blacks 1.0), rough 0.16,
  **clearcoat 0.8 @ 0.025**, and a view-angle hue drift (Layer-Weight facing → hue ±0.06) for an anodized-Ti interference look.
  v4 tried dielectric thin film (320 nm) with 0.15-metallic blacks. It went milky under the broad sweep light, so it was rejected and metallic blacks restored.
  Art blacks become polished dark mirror Ti (0.022, metallic 1), side walls are a dark polished Ti band, and ground bevels/edge are polished raw Ti (0.72, rough 0.06).
- AgX with the Punchy look, no exposure offset. Glossy 12 / max 16 bounces. OIDN with albedo+normal at high quality and adaptive threshold 0.004.
- Stage: R4 dark arc key + 2 face softboxes + blade sweep. The world HDRI is OFF because its studio boxes showed in
  the floor mirror. The floor is near-black with coat 0.6 and roughness 0.06.

## Signature (jepson_t.svg → 4096 mask, bold06)
`prep.py` solves each side's placement on a 0.1 mm layout grid. The ink footprint is dilated by 1.5 mm margin
plus a 0.3 mm raster guard. It must sit entirely on flat broad-face pixels (no bevel, edge, serration or wall within
the margin) and on dark art (dilated luminance < 0.10). The solver takes the largest size, then the left end closest to the blade start.
It is a protected **bare laser-etched metal** region with an AOV `sig`. Its separate metal shader takes
precedence over every finish, including antialiased ink coverage: no coat, thin film/LUT colour, brushing,
or emission. Finish `gold_*` look settings do not affect it. Bevel, edge-apex and serration grinds also
always use bare metal; `bevel_flamed` cannot opt them into a film shader.

## Memory and admission
Every pro CLI entry verifies a real cgroup limit, or re-executes itself through the host's **`memcap 32G`**
wrapper (systemd user scope, `MemoryMax=32G`, `MemorySwapMax=0`). A missing wrapper fails closed.
`runtime.safe_workers` chooses worker-thread counts from `MemAvailable`, current cgroup headroom,
resolution-dependent buffer estimates, CPU affinity and a maximum of 16; it leaves 20% of free memory
for other work. Director children run sequentially inside the same capped scope. There is no render-process fan-out.
Animation receipts stream frame records to disk rather than collecting them in RAM. Each QA image is copied
with `foreach_get` and removed from Blender in `finally`, including failed reads and still-side QA loads.

## QA (fails the shot/frame)
1. **Mesh glyph check:** 1,500 ink samples plus an 8-point 1.5 mm margin ring each, ray-cast onto the mesh. Every hit must be a flat face (|n·y| > 0.95) in a flat region.
2. **Frame check:** every ink sample is inside the image (1 % guard), front-facing, and unoccluded (camera ray hits the same point).
3. **Lights:** a 7×7 sample grid over every emitter, plus its floor mirror image, stays outside the frame (6 % guard). A deterministic fix-up raises an offending light's elevation and records it.
4. **Edge sharpness:** the gate above.
5. Records: per-shot `*.qa.json` (camera, lens, f-stop, spp, view transform, EXR/PNG sha256), `run_<res>.json` (lights, cfg, Blender version), `prep.json` (source sha, art/mask sha, placements, normal repair).
Failed or missing hard checks give a nonzero command exit and `all_pass:false`. Pre-render failures stop
before rendering; image/clipping failures produce `FAIL_POST_RENDER`. Only stills that pass every hard
check receive `RENDERED`; delivery validates the entire receipt set before writing anything. Empty runs
fail. Animation `render_ready` depends on the gate verdict, and `release_ready` remains false for human sign-off.
Director checks require successful, complete normal runs and matching shard state, plus nonzero exits
and the intended failed gate for deliberate faults. An unrelated worker crash is not a successful fault test.
CPU regressions run in `ops/render/pro/tests` and in marketing CI; full GPU film review remains separate.

## Deliverables
32-bit EXR master → 16-bit PNG. There is also an 8-bit RGB PNG for chat (< 25 MB, blue-noise-style dithered with a high-passed noise
field, ±0.5 LSB). Signature crops are at 100 %. No JPG deliverables; JPG is used only for thumbnails.

## Anodized finishes: `ti_flame_heat` (`--finish flame`, `shots.json:flame`)
- The colour comes from `marketing/anodize.py`: `film_metal(d)`, an air/TiO2/Ti thin film. It's baked into a 64-entry LUT
  (`film_lut_12_62nm.json`) that feeds the conductor's Base Color (F0) and Specular Tint (F82). Blender 4.2's Thin Film input
  doesn't act on metals. Oxide thickness runs from 21 nm at the ring end to 60 nm at the tip, with slight z "licks": straw/gold → bronze/rose
  → purple → blue. Clearcoat is 1.0 @ 0.02 and the view is AgX Punchy at +0.55 EV. The edge-apex strip is polished raw Ti.
  Bevel and serration grinds also remain raw Ti. This is a reflective visualization, not a calibrated finish claim.
- Vertical mirror flats only show colour when they reflect something. A `mirror_flat` reflector is placed per shot or frame on the
  mirror direction of the visible broad face, plus 8°. Camera elevations are kept ≤ 6° so that direction stays above the floor.
  The lights-out-of-frame gate still applies.
- To stop the serrations and spine walls blowing out, the arc key is −3.4 EV and the rim −1.8 EV, and walls are rough 0.38. A whole-frame
  largest-white-blob gate is limited to 0.15 % of the frame.
- Signature: the protected metal footprint uses the supplied prep mask; a dilated mask such as
  `jepson_t_mask_4096_key40.png` counts its full footprint toward the 1.5 mm margin. No gold, ink, coat,
  oxide colour or satin brushing is applied to that region. The solver config is `prep_flame.json`:
  no dark-art requirement, so the largest size on the flat wins.
- OpenCV is pinned at 4.12.0 (`requirements.txt`). `prep.py` refuses any other version because placements depend on the cv2 version.
