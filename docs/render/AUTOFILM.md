# AUTOFILM: `jr-film`, from a design folder to a delivered film in one command

`jr-film` turns a committed design folder (`designs/<family>/<rev>/`) into the marketing film:
EXR/PNG16 frames, an FFV1 master, an H.265 preview and a chat-size H.264 copy. The filenames carry the
manifest stamp (`<family>_<rev>_<rc>_<step-sha8>`, e.g. `switchback_C10a_rc4_441cfabc`).

```bash
# on the render host (xbabe3, RTX 3090; memcap required by runtime.ensure_memcap, #55)
cd ~/jarambit_render/wt_pro
export JR_FEM_STORE=~/jarambit_render_scratch/pro/c10a/fem        # solver results (not in git: large)
ops/render/pro/jr-film --design designs/switchback/C10a --work ~/jarambit_render_scratch/autofilm/C10a \
                       --deliver ~/jarambit_render_scratch/autofilm/C10a/deliver
ops/render/pro/jr-film --latest designs/switchback --work ...       # newest RC (the default family)
ops/render/pro/jr-film --design ... --work ... --plan               # validate everything, render nothing (CI / PR)
ops/render/pro/jr-film --design ... --work ... --res low --spp-scale 0.25   # low-res review preview
```

## The one rule: every on-screen number comes from the design manifest

`design_manifest.py` builds `design_manifest.json` from these sources, and only these:

| value on screen | source (in the design folder unless noted) |
|---|---|
| family, `Rev C.10a`, `rc4` | `README.md` title + status line |
| mass `64.8 g`, material `Gr5 Ti` | `data/<cad json>` `mass_g_Gr5`, cross-checked against the README |
| STEP sha (stamp, provenance) | `cad/*.step` hashed and checked against `SHA256SUMS` |
| Sy `828 MPa`, gate `SF ≥ 1.575` | README (`SF = 828 MPa / σvM`, gate line) |
| test name, load + unit (`SPINE STRIKE · 3,427 N`, `PRY · 13.7 N·m`) | README gate table, cross-checked against the gate JSON |
| SF + verdict (`SF 1.584 · PASS`) | README gate table == gate JSON `C10a.gates` |
| PEAK σvM (MPa) | Sy / SF of record (converged); the raw field max is kept in the receipt |
| `SOLVER MESH · 224,409 TETS` | node/tet count read from the gmsh solver mesh in the FEM store |
| colour field | per-tet von Mises from the solver npz files (sha256 recorded); load scale from the zones JSON |

`fem_cases.json` maps gates to FEM result files and gives the scale-key path for each. It holds no
numbers. If a file, key or sha is missing, or two sources disagree, the run exits non-zero
(`design_manifest: FAIL: ...`). Nothing is ever placeholdered.

The render *recipe* (`autofilm_satin.json`: finish, film plan, spp, emission gain for the data views,
chat-copy budget) holds only how-to-render settings, never design data.

## Stages

Each stage writes `<work>/.stages/<stage>.json` with the manifest sha it was built for. A rerun skips any
stage whose outputs exist under the same manifest. A new design or rc changes the sha, so everything
rebuilds. Use `--force <stage>` to redo one stage and `--until <stage>` to stop after it.

1. **manifest**: `design_manifest.py` (above).
2. **ingest**: `ops/render/marketing/ingest.py` STEP → mesh bundle. Fails unless the bundle's source sha equals
   the manifest STEP sha.
3. **prep**: `prep.py`. Wall-normal smoothing and the flat-seam weld (sub-crease knees on broad faces). Gates:
   flat-seam QA (max normal break ≤ 0.05° on the flats) and the edge-width gate (p99 land ≤ 0.2 mm). Both
   must pass.
4. **fem**: `fem_asset.py`. Solver tet mesh → render-space surface with per-tet von Mises (vm_V3/V6/V7).
   Checks: sha256 of every result file, tet-centroid match, and bundle-pose alignment.
5. **film**: `pro_hero.py --anim <film json>`. The photoreal cut. Per frame: light-clearance QA,
   signature QA wherever the mark is presented to camera (`sig_side: auto`), edge gate, image QA, and the
   object-index and signature passes saved for the overlay QA.
6. **sci**: the same animation over `science_range` (the 3 × 360° turntable), rendered twice more:
   `--sci_mode wire` (the solver's surface tets) and `--sci_mode heat` (von Mises, inferno, 0 … Sy). Camera and
   spin are identical, so the passes are pixel-registered and the cross-fades never slip.
7. **assemble**: `assemble_film.py`. Cross-fades photoreal → mesh → field → photoreal on the timeline in the
   film JSON (`science_timeline_s`). It adds the typewriter data card, the colour scale (drawn with the same
   emission gain as the heat pass), and the **weight badge on every frame**. Per-frame text QA:
   * badge present and fully in frame, never within 24 px of the signature (on macro frames it sits on a dark
     plate over the metal);
   * data card and scale never within 24 px of the knife or the signature, using one layout per shot;
   * any failure exits non-zero.
8. **encode**: FFV1 (`rgb48le`, intra, slice CRC) master, H.265 10-bit preview, two-pass H.264 chat copy
   under `chat_mp4_max_mb`. ffprobe frame counts must equal the assembly.
9. **receipt**: `<stamp>_receipt.json` holds the output shas, the manifest sha and `release_ready: false`
   ("design candidate, not certified").

## Typewriter overlay (data shots)

Every line of a data shot types in when its visual starts: the load at the photoreal open, the mesh line as
the solver mesh fades in, PEAK and SF as the field arrives. The provenance line fades in.

The typing model is deterministic, seeded from the text, so every render matches:
* 60–90 ms per character with jitter;
* 60–110 ms extra after a space and 100–160 ms around `·`;
* about 0.72× inside common words (a burst) and 1.28× on digits;
* about 5 % micro-hesitations.

A block cursor stays solid while typing, then blinks (0.53 s) and leaves after 1 s. Each new glyph gets a
45 ms key-strike settle (a 2 px drop plus a brief brightening). Units always show: N, N·m, MPa, SF.

## Trigger: a new evolution winner or rc renders itself

A new design lands as a commit adding or changing `designs/<family>/<rev>/` (README gate table, SHA256SUMS,
STEP, data JSONs), usually with a tag `<family>-<rev>-rcN` (e.g. `switchback-C10a-rc4`).

`.github/workflows/autofilm.yml` (proposed; add it with the steward's review):

```yaml
on:
  push:
    branches: [main]
    paths: ['designs/**/README.md', 'designs/**/SHA256SUMS', 'designs/**/cad/*.step', 'designs/**/data/*.json']
    tags: ['*-rc*']
  pull_request:
    paths: ['designs/**']
jobs:
  plan:            # every PR touching designs/**: manifest + cross-checks only, fails the PR on bad data
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 ops/render/pro/design_manifest.py --latest designs/switchback --fem-store none --plan-only
  render:          # main / rc tag: full film on the GPU host
    if: github.event_name == 'push'
    runs-on: [self-hosted, xbabe3, gpu]
    concurrency: autofilm-${{ github.ref }}
    steps:
      - uses: actions/checkout@v4
      - run: ops/render/pro/jr-film --latest designs/switchback --work $HOME/jarambit_render_scratch/autofilm/${{ github.sha }} --deliver $HOME/autofilm_out/${{ github.sha }}
        env: {JR_FEM_STORE: /home/ubuntu/jarambit_render_scratch/fem_store}
      - run: echo "film ready; human creative sign-off required before release"   # release_ready stays false
```

How it works:
* `--latest` picks the newest RC folder by README status plus rc tag.
* PRs only validate (`plan`). No GPU time is spent on unmerged data.
* The FEM store is the one input outside git. The analysis lane must copy the new solver results there
  (named in `fem_cases.json`) before the push, or the run stops at the manifest stage with a precise
  message.
* Nothing is published automatically. The output is a review candidate.

(`--plan-only` with no FEM store is part of the CI wiring follow-up. For now `jr-film --plan` needs the store.)

## Files

`jr-film` (wrapper) · `jr_film.py` · `design_manifest.py` · `fem_cases.json` · `fem_asset.py` · `read_msh.py` ·
`pro_hero.py` · `prep.py` · `assemble_film.py` · `overlay.py` (+ `fonts/` Inter, OFL-1.1) · `film_satin_v2.json` ·
`autofilm_satin.json` · `compose_sci.py` (still-based science preview, superseded by the turntable).
