# SWITCHBACK C.10a — LOOK AGAIN (art edition) · director's script v1 (for agreement before the heavy render)

**Model:** SWITCHBACK Rev C.10a rc4, `analysis/w79/ground_c10a.step` (sha16 441cfabc284efd63, 64.841 g).
On-screen context line throughout: `CAD VISUALIZATION · DESIGN CANDIDATE, NOT CERTIFIED`. The V2 tip test is record-only.
**Source of authority:** the four director's books (LOOK AGAIN 38 s lock, NOT FINISHED LOOKING 40 s, production bibles).
This edition keeps their photographic constitution:
- One authored movement at a time.
- No visible studio, and none in the floor reflection.
- 85 mm whole-object / 135 mm macro on a 36 mm sensor, f/8 start.
- Geometry is never altered.
- Text only in reserved regions, never across the blade.

**Data shots are BLOCKED:** the books' S04–S06 (V3 von Mises field, C.9.2↔C.9.3 comparison, PASS wording) need an
approved primary FEM export and comparison sign-off. None is supplied for C.10a. Per the books, the renderer must
not keep their captions or score on a beauty film, so this edition replaces them with art/finish beats. Their
frame boundaries are kept so the data edition can drop in later.

**Format:** 38.0 s, 30 fps, frames [0,1140). Frame 1140 is virtual and equals frame 0, so it loops. Master render: 3840×2160,
32-bit EXR ZIP → 16-bit PNG → lossless FFV1 / ProRes 4444 XQ. Delivery encodes come after approval.
**Per-frame QA (automatic, a failing frame fails the shot):**
- Signature 100 % in frame and unoccluded (1,500 ink samples).
- Glyphs on the flat with ≥ 1.5 mm margin (mesh check).
- No emitter or emitter mirror image in frame.
- Edge land p99 ≤ 0.20 mm (C.10a 0.158).
- Lighting is authored in absolute frame time (`light_rot_deg`, the whole rig about Z), so any frame renders identically alone or in a shard.

| # | frames | time | camera (az / el / lens / f) | move | light arc | picture & intent | text (reserved region) |
|---|---|---|---|---|---|---|---|
| S01 WHOLE OBJECT | [0,72) | 0.0–2.4 | −20° / 12° / 85 / f8, fill 0.80 | locked | rig 0→6° | Complete object at frame 0: ring, crescent, art, the mark, a quiet floor mirror | `IT LOOKS FINISHED.` at f24, upper-left |
| S02 SPINE RECESSES + MARK | [72,180) | 2.4–6.0 | −36→−26° / 24→20° / 135 / f8 | slow lateral drift | 6→12° | 3–5 real spine recesses + bevel + the mark: bright wall / dark recess rhythm | — |
| S03 RING TO MARK, LOW | [180,252) | 6.0–8.4 | −44→−38° / 6→5° / 85 / f8 | short arc | hold 12° | Ring depth and negative space; the mark stays in frame | — |
| S04 THE COLOUR WAKES *(data slot)* | [252,432) | 8.4–14.4 | −14° / 10° / 85 / f8 | locked | −18→+18° sweep | The single movement is the light. Anodized hue drift and coat ribbon cross the art; blacks stay polished dark Ti | `LOOK AGAIN.` at f270 |
| S05 THE MARK | [432,540) | 14.4–18.0 | −14→−8° / 9→7° / 135 / f8 | push fill 0.62→0.70 | 18→10° | Gold signature macro on dark starfield; edge grind runs below it | — |
| S06 THE OTHER FACE *(comparison slot)* | [540,780) | 18.0–26.0 | part rotated 180° (cut), −12→+12° / 6° / 85 / f11 | slow arc | hold | Back face with its own upright mark; the art is the through-print mirror | — |
| S07 FLOOR REFLECTION | [780,990) | 26.0–33.0 | −26→−8° / 2.5→3.5° / 85 / f8 | low arc | −6→+6° | Earned appreciation: object and its quieter reflection | — |
| S08 RESOLVE / LOOP | [990,1140) | 33.0–38.0 | −20° / 12° / 85 / f8 (= S01) | locked | 12→0° (= frame 0) | Returns to the S01 state, so the seam is honest | `NEVER HUMAN` small, f1035 |

Sound (per the books): no narration in the primary edition. A two-note motif first appears in S01 and resolves in S08,
with no brand sting. Typography and sound are post work and are not rendered into the EXR.

**Animatic (for approval):** every 6th frame at 1280×720, 24 spp, lossless PNG frames. The video is assembled at 5 fps, FFV1 lossless, with a per-frame QA log (`anim_qa.json`).
**Open for agreement:**
1. Is the data edition (S04–S06 with an approved C.10a FEM field) wanted? It needs an approved export first.
2. Text overlays are kept in post, not in render.
3. A full 360° turntable can't keep the mark visible edge-on. It's offered as a separate deliverable with a declared mark-hidden interval, or as a ±35° rock.
