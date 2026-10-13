# Maker's mark: NeverHuman (DEFAULT since 2026-10-13 11:15) · Jepson T kept for re-enable

## NeverHuman (active)

| file | what |
|---|---|
| `neverhuman.svg` | vector. potrace (`-t 6 -a 1.0 -O 0.2`) traced from the alpha of `source/neverhuman_signature_v1_src.png` at 3x Lanczos upsample, threshold 50 %. Single fill `#000000`, transparent background. |
| `neverhuman_4096.png` | transparent PNG (4096 x 1009, RGBA, black ink, alpha = coverage), rendered from the same trace. |
| `neverhuman_mask_4096.png` | alpha mask (L8, white = ink), 4096 x 1009, aspect 4.059, ink fraction 0.0689. |
| `neverhuman_mask_4096_boldNN.png`, `nh_occ_boldNN.npy`, `variants_neverhuman.json` | stroke-weight variants (outline grown NN px at 4096 px) + block-any occupancy grids, same contract as the Jepson T set. |
| `source/neverhuman_signature_v1_src.png` | preferred source (2172 x 724 RGBA, black script). `..._alt_src.png` = alternate scan (2244 x 701 RGB), archived. |

Trace check: rasterised trace vs source alpha IoU 0.975 (the hairline swash tail is kept). Base stroke p5 is
12.7 px at 4096 px width, so at a typical ~42 mm on the flat use bold04 or more (p5 >= 0.15 mm).
The pro pipeline uses `neverhuman_mask_4096_bold06.png` (p5 about 0.27 mm). Placement is the same: the largest
height that keeps the whole ink silhouette, including the long trailing swash, >= 1.5 mm inside the flat (auto-fail).

Selection points (NeverHuman is the default in each):
* `ops/render/marketing/signature.py` (`ASSET_MASK` / `ASSET_SVG` / `INK_FRACTION` / `ASPECT` / `VARIANTS`)
* `ops/render/pro/autofilm_satin.json` (`sig_mask`)

**Re-enable Jepson T:** in `signature.py`, comment out the five NeverHuman lines and uncomment the Jepson T
block below them. In `autofilm_satin.json`, set `sig_mask` to the value stored in `_sig_mask_jepson_t`.
Every Jepson T asset below is unchanged.

---

## Jepson T (v2, bold): previous mark, kept (not active)

Jepson Taylor's signature, applied automatically to every marketing render as a matte black mark
(see `ops/render/marketing/signature.py`).

| file | what |
|---|---|
| `jepson_t.svg` | **primary** vector. potrace 1.16 (`-t 6 -a 1.0 -O 0.2`) traced from the alpha of `source/jepson_signature_v2_bold.png` at 3x Lanczos upsample, threshold 50 %. Single fill `#000000`, transparent background, viewBox cropped to ink bbox + 12 px pad (2026 x 665 source px, aspect 3.045). |
| `jepson_t_4096.png` | high-res transparent PNG rendered from the SVG (4096 x 1345, RGBA, black ink, alpha = coverage). |
| `jepson_t_mask_4096.png` | alpha mask (L8, white = ink), same size. Used by the Blender shader. Ink fraction of bbox = 0.0579. |
| `jepson_t_v1_alt.svg` | archived alternate, traced the same way from the first (thinner) scan. Not used by the pipeline. |
| `source/jepson_signature_v2_bold.png` | primary source (2172 x 724 RGBA, black ink on transparent). |
| `source/jepson_signature_v1_src.png` | first source (2508 x 627 RGB, black on white). Archived. |
| `SHA256SUMS` | sha256 of every file above. |

Trace check: the SVG rasterized back at source scale vs the source alpha (both thresholded at 50 %)
gives IoU 0.993. The fine hairline entry/exit strokes are kept (`-t 6` only drops specks under 6 px
at 3x scale, about 0.7 source px²).

Version: v2 (2026-10-13). To revise, add `jepson_t_v3.svg` and friends, regenerate the PNG/mask,
update `ASPECT` / `INK_FRACTION` in `signature.py`, and refresh `SHA256SUMS`.

Rendering contract: the mark is the **final material overlay** in every shot (mixed into every
material slot just before the output node), roughness 0.9, base linear 0.012, specular 0, no coat.
QA gate Q15 fails a delivery if any shot lacks it or a hero still loses it.

## v2 placement (2026-10-13): as large as the flat allows
- `fit: "ink"`: the traced ink silhouette itself (block-any occupancy grids `occ_boldNN.npy`), not its
  bounding box, must fit inside the flat face eroded by `margin_mm` (default 1.25 mm, band 1.0-1.5). This
  hugs the slanted script and gains ~25-30 % width over the bbox fit. `fill` 0.95 of the largest fit;
  no max-width cap; angles principal axis +-30 deg (2.5 deg steps); up to 4 coplanar flats tried.
- Manufacturable strokes: `variants.json` lists stroke-weight variants (`jepson_t_mask_4096_boldNN.png`,
  outline grown by NN px at 4096 px). Placement picks the thinnest variant whose p5 stroke width is
  >= `min_stroke_mm` (0.15 mm) at final scale, then refits with that variant.
