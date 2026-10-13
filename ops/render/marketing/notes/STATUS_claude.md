# STATUS: Claude (scene / materials / rigs / finishing), branch `render/claude-scene`

**Delivered** (`ops/render/marketing/`)
- `blender/worker.py` reads INTERFACES `request.json` and writes, atomically, `<shot>_<idx>.{raw,denoised,normal,depth,mask}.exr` plus a receipt per frame and `<shot>.result.json`. It resumes by receipt sha, fails with exit 11 and never falls back (OptiX/CUDA requested without a device, missing required HDRI, bad bundle sha).
- `blender/scene.py materials.py lights.py cameras.py rigmath.py` (rigmath is pure numpy and host-testable).
- `presets/finish_ti64.json rig_studio_softbox.json rig_dark_strip.json rig_product_white.json shots_default.json`.
- `finish.py`: EXR → OCIO AgX (Medium High Contrast) → PNG16 + JPEG q92, Lanczos3 resize in linear light, Q4/Q5/Q7/Q8/Q9 metric helpers, CIEDE2000, contact sheets. It re-execs under Blender's Python for OIIO/OCIO.
- `lookdev.py` builds requests from `shots_default.json` for stills and short turntables, runs the worker and finishes the frames. It waits while another process holds > 50 % of GPU VRAM or utilization.
- Tests (`pytest ops/render/marketing/tests`): 25 pass in about 25 s on xbabe3. They cover the smoke render (160×90 CPU 8 spp, 4 frames → EXR → PNG → MP4 bt709 → full decode, resume, Q12 rerun determinism, fail-loud cases), the ColorChecker Q6, AgX parity with Blender, CIEDE2000 reference pairs, preset consistency and rigmath. A missing Blender 4.2 or ffmpeg fails the run; nothing is skipped.
- `tests/_stl_bundle.py` is a temporary STL → bundle stand-in for tests only. Production bundles come from Codex's ingest.
- `notes/LOOKDEV.md` has the C.9.2 contact sheet and the measured Q1/Q4–Q8/Q12 numbers.

**Toolchain**: Blender 4.2.23 LTS (official tarball sha256 `bea0eb31…dc404`) at `~/opt/blender-4.2.23-linux-x64` on xbabe3 and xbabe1. It is not yet installed on xbabe2 (Grok's doctor).

**Hand-offs**
- Grok: set `final_4k` to adaptive 0.02, 512/64 spp, `auto_tile:false` (Q1 measured 54 s median on the 3090). The request extensions the worker understands are documented in the worker docstring. All are optional, and the result JSON records every resolved value.
- Codex: the C.9.2 region labels need review (ring ridges labelled as bevel, no ring/edge_apex). Details are in LOOKDEV open items.

GPU use: the xbabe3 3090 was busy with flywheel training (rlfw-g-abl) at first, so I yielded it and ran lookdev on the idle xbabe1 4090. Q1 ran on the 3090 later, once it was idle. No PRs were opened.
