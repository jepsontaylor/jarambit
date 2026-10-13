# Director-book compliance audit: pro-hero pipeline + DIRECTOR_SCRIPT.md

Sources (all four re-read): **A** = LOOK AGAIN final editorial lock (38 s / 30 s), **B** = NOT FINISHED LOOKING director's book
(40 s / 30 s), **C** = NOT FINISHED LOOKING production bible (40 s), **D** = LOOK AGAIN production bible (40 s).
Status: **DONE** = implemented and evidenced · **PARTIAL** = implemented but not yet verified, or verified only in part · **MISSING** = not done ·
**BLOCKED** = needs an approved input that doesn't exist.
Code paths are relative to `ops/render/pro/`. Run evidence is on xbabe3 under `~/jarambit_render_scratch/pro/c10a/`.

## 1. Source and claim boundary
| # | Directive (book) | Status | Evidence / action |
|---|---|---|---|
| 1.1 | Every image resolves to the exact pictured candidate; captions bind to source (A§3, B§2, C§3) | DONE | `prep.json.source` (sha 441cfabc…, model "SWITCHBACK Rev C.10a") carried into every `*.qa.json` / `anim_qa.json` `code.source`; `plan.py KNOWN_SOURCES` |
| 1.2 | No overall "approved/certified/physically proven" wording (B§2, C§3) | DONE | Receipts carry `release_ready:false` and the label "design candidate, not certified". The script has no PASS wording |
| 1.3 | Quantitative editions (V3 field, C.9.2↔C.9.3 comparison, 1.575 target) need primary-source approval (all) | BLOCKED | No approved C.10a field. DIRECTOR_SCRIPT keeps S04–S06 as finish beats in the same frame slots and keeps no data captions |
| 1.4 | Beauty shader is a false-colour/finish *interpretation*, not proof of a manufactured finish or calibrated oxide model (A§11) | DONE | Stated in PRO_HERO_PIPELINE (flame section). Overlay copy keeps "CAD VISUALIZATION" |
| 1.5 | Don't keep a quantitative edition's captions or score on a beauty film (A§3) | DONE | Art and flame editions carry none |

## 2. Photographic constitution
| # | Directive | Status | Evidence / action |
|---|---|---|---|
| 2.1 | Approved geometry not redesigned: no invented bevels, enlarged recesses, smoothed boundaries or exaggerated tip (A§5, C§5.1) | DONE | Positions are never changed (`prep.py` policy string). Only normal repair, declared |
| 2.2 | Tessellation and normal handling need a declared geometry-preservation policy (C§5.1) | DONE | `prep.json.normal_repair` (25° crease, walls only, positions untouched). Ingest declares 0.01 mm / 0.1 rad |
| 2.3 | 85 mm whole object / 135 mm macro, 36 mm sensor; f/8 whole, f/5.6–8 macro, then judge sharpness (A§5, D§5) | DONE | `shots.json`, `film_*.json`. Lens, sensor and f-stop are recorded per shot and per frame (`state.camera`) |
| 2.4 | H_OPEN characteristic full view keeps broad face, both extremities, ring-to-tip (A§5) | DONE | S01/S08 and the hero fit the whole part bbox (`fit:"part"`). The sig-frame gate also proves the mark is in frame |
| 2.5 | Stage: neutral dark, restrained floor reflection quieter than the object, not a second hero (A§5, B§3, D§4) | PARTIAL | Near-black reflective floor. Flame floor coat is reduced to 0.15. "Quieter than object" is reviewed by eye, with no metric yet |
| 2.6 | One authored movement at a time (D§4) | DONE | Each film shot animates camera **or** light, never both at full amplitude (see the script table) |
| 2.7 | Don't substitute a zoom for a dolly, or a turntable for a camera arc (C§12) | DONE | Moves are camera-position arcs (`az`/`el`). The ±35° rock is a separate, declared object-pose deliverable |
| 2.8 | Contrast reveals and doesn't erase: no white-slab blade, ring opening stays open (A§5, D§4) | DONE | New whole-frame **largest-white-blob gate** (`frame_qa_image`, limit 0.15 %) on stills and every animatic frame |
| 2.9 | Text only in reserved regions, never across the blade (A§6) | PARTIAL | Regions are named in the script. Overlays are post work, so the text compositor and its gate are still **missing** (needs final copy) |

## 3. Invisible rig
| # | Directive | Status | Evidence / action |
|---|---|---|---|
| 3.1 | No recognizable source in background or floor reflection; camera-invisibility alone is not proof (A§10, B§11, C§11, D§4) | DONE | `qa_lights`: a 7×7 grid over each emitter **and its floor mirror image**, checked against the frame with a 6 % guard. Deterministic `clear_lights` raises any offender. The world HDRI was switched off after its boxes showed in the floor |
| 3.2 | Check the entire camera path, not one still (A§10) | DONE | `--anim` runs the gate on every rendered frame. Results are in `anim_qa.json` |
| 3.3 | Review the whole frame including floor/background, not only the object mask (C§11) | DONE | `frame_qa_image` covers the whole frame. Visual review of contact sheets each iteration |
| 3.4 | Don't kill glossy visibility wholesale; solve placement first (C§11) | DONE | Lights stay glossy-visible. `mirror_flat` reflector is placed geometrically |
| 3.5 | Product-only reflection composite only as a declared fallback (all) | DONE | Not used. Single-pass physical floor |
| 3.6 | Rough reflections / final encode reviewed, not only geometry (A§10) | PARTIAL | Encode/decode frame-count check added (`decode_frames.txt`). Rough-reflection review is visual only |

## 4. Authoring, absolute state, receipts
| # | Directive | Status | Evidence / action |
|---|---|---|---|
| 4.1 | Every control survives plan → worker → receipt; silently discarded controls are errors (A§12, C§12) | DONE | `physical_state()` records the resolved camera matrix, lens, sensor, focus, f-stop and motion blur, the part pose, every light's matrix/energy/size, floor and world, per still and per frame |
| 4.2 | Absolute global time: frame N alone, after another, or in an irregular shard resolves the same state (A§12, C§12) | DONE | `lerp_shot` is a pure function of the absolute frame. Lights reset each frame. **Gate** `director_gates.py` compares contiguous vs 3 shuffled, reversed shards by physical-state hash (`gates/director_gates.json`) |
| 4.3 | Resolve shot-level light/fit references before sharding; no worker-relative reference (C§12) | DONE | The fit is solved from the frame's own authored state (no history). The rock uses `fit_rot_range` for constant framing |
| 4.4 | Hash physical state separately from material/overlay state (A§12) | DONE | `physical_state_sha256` per frame. `material_state_sha256` per run. Overlay state is none (post) |
| 4.5 | Cache identity includes source, geometry, look versions (C§12) | DONE | `code`: pro_hero.py sha, cfg sha, prep.json sha (holds the mesh npz sha, art sha, mask sha, placements), source sha |
| 4.6 | Motion blur off unless subframes are evaluated (A§12, C§12) | DONE | `use_motion_blur=False` is set and recorded in each receipt |
| 4.7 | Material-snap registration via masks/depth/normals (C§12) | BLOCKED | Only applies to the FEM snap (S04). Passes are already saved (IndexOB, Normal, Depth in the EXR) for when it's unblocked |
| 4.8 | Suggested `director/` module layout (A§12, C§12) | PARTIAL | Implemented as `pro_hero.py --anim` + `film_*.json` + `director_gates.py`. Not split into `schema/compile/tracks` modules (they're proposals, adopted only after integration review) |

## 5. Gates and deliberate failures
| # | Directive | Status | Evidence / action |
|---|---|---|---|
| 5.1 | Image and rig gate must FAIL on a floor-reflected source (C§14) | DONE | `--fault light_in_frame` → gate fails (`director_gates.json fault_light_in_frame`) |
| 5.2 | Signature/overlay never crosses the blade (A§6 + owner) | DONE | Mesh glyph gate (1,500 samples + 1.5 mm ring on the flat), frame gate (in frame, unoccluded). `--fault sig_off_flat` must fail |
| 5.3 | Temporal state gate (shard-relative reference must fail) (C§14) | DONE | Partition hash test, 4.2; gates2/director_gates.json all_pass (33 frames, 0 mismatches; light rig rebuilt from authored base each frame, 1e-5 quantised hash) |
| 5.4 | Delivery: correct frame count/rate, no duplicate endpoint, full decode (C§14) | PARTIAL | Frames [0,1140) with virtual 1140 = frame 0 (S08 end state = S01). ffprobe decoded count vs PNG count. The 30 fps master encode is still **missing** (animatic only) |
| 5.5 | Don't disable gates globally; gates know the shot's purpose (C§14) | DONE | Gates run per shot with shot-specific `sig_side`/fit. Macros are tested against their feature (sig) |
| 5.6 | Human creative + presentation approval; automated QA ≠ art approval (all) | DONE | `release_ready:false` until sign-off. This audit and the animatic are for that review |
| 5.7 | Owner hard rules: edge ≤ 0.2 mm, smooth grind, mark fully visible, bright mirror gold | DONE | `edgeqa` p99 0.158 mm. Wall-normal repair. Sig gates. Gold + keyline (`shots.json flame`) |

## 6. Production order, aspects, sound, audience
| # | Directive | Status | Evidence / action |
|---|---|---|---|
| 6.1 | P4 full low-cost animatic with exact timing before the full render (C§13) | DONE | `animatic_flame/animatic_flame_lossless.mkv` (every 6th frame, exact frame numbers) |
| 6.2 | P1 visual proofs / P2 temporal proofs with deliberate rig faults (C§13) | PARTIAL | Still proofs (flame hero, face-on, macro) and fault fixtures exist. Short full-rate temporal proofs are **missing** |
| 6.3 | Independent native aspects (16:9 and portrait), not centre crops (B§8, C§8) | PARTIAL | `4k_portrait`/`preview_portrait` resolutions are added and the fit is solved natively per aspect. Portrait film framing review is **missing** |
| 6.4 | Primary edition has no narration; image + text carry meaning muted (A§8, B§7) | DONE | The script specifies a nonverbal primary. Sound is post |
| 6.5 | Formative audience test, open questions, no leading prompts (C§15) | MISSING | Out of render scope. Protocol to run after animatic approval |
| 6.6 | Estimate compute from proof timings, not a turntable assumption (C§13) | DONE | Measured: 4K still ≈ 1–3 min (adaptive, 1024 spp max), animatic frame ≈ 14 s @ 720p/24 spp |
