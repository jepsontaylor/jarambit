# Maker's mark: Jepson T (v2, bold)

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
