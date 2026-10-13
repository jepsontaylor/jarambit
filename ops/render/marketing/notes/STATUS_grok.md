# STATUS grok — render/grok-farm-pkg

Date: 2026-10-13. Branch pushed. No pull request opened.

## Landed

- CLI `pipeline.py`: `doctor|ingest|plan|render|finish|encode|qa|package|all`.
- Deterministic plan, farm (shards of 8, yield, flock, receipts, remote scratch rewrite), encode (explicit zscale full to BT.709 limited), QA Q1–Q13 fail closed, package schema `jarambit.render.marketing.v1` with no upload.
- Camera frame `z_up_az0_minus_y` (Z up, blade plane XZ, azimuth 0 on -Y, azimuth 90 on +X). `profile_flat` is az 0, el 0.
- Hero execution pin: SWITCHBACK Rev C.9.2 STEP `2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307`, STL `10b8c41f80b898c255cc090a349559722258f87f8af849ce9a605e14d762e847`. `package` defaults `--cad` and `--cad-sha` to that STEP. `render --execute` refuses any other source. The manifest and Q13 reject hero deliveries sourced from retired `g3_tip+00_t60_tt3.stl` (`04404820cf8385f5e34a42ef9d39a79aecda8eb88895c78aa21f4e3a92fe28c5`). `~/jarambit_render_scratch/hero` is superseded. Claude should render `~/jarambit_render_scratch/hero_C9.2/mesh`.
- Smoke workflow `.github/workflows/render-marketing-smoke.yml` (labels `self-hosted, linux, x64, lan-ci, ubuntu24`). `.github/actionlint.yaml` lists those custom labels so actionlint can pass. That config is the only file outside the brief's path list.
- `ingest` and `finish` delegate. Missing peer modules exit 2. This tree does not vendor Codex or Claude files.

## Checks this session

- `final_4k` is adaptive 0.02, 512 max / 64 min spp, `auto_tile` false (measured 54 s median on a 3090).
- Dispatch runs one shard per free GPU: xbabe1, then xbabe3 when it is under the yield line, then xbabe2 only under that same line. Raw, depth, and normal EXR are removed after the PNG exists.
- `actionlint .github/workflows/render-marketing-smoke.yml`: exit 0.
- `doctor --require ffmpeg,zscale,libx264,libx265,libwebp,blender,gifski --hosts`: `missing` [].

## Toolchain

- Blender 4.2.23 LTS at `/home/ubuntu/opt/blender-4.2.23-linux-x64/blender` on xbabe1, xbabe2, and xbabe3. Binary sha256 `d41fdcd0d5e2a60698011126cf33ebaa448cf9a5f77e88e216c8be71b15e7c92`. Tarball sha256 `bea0eb3146be13eae6225409a117b215184f41b7f79e799f97cb3abb8f6dc404` (`/home/ubuntu/opt/src/blender-4.2.23-linux-x64.tar.xz`).
- ffmpeg 7.0.2-static with libx264, libx265, libwebp, zscale.
- gifski 1.34.0 at `/home/ubuntu/opt/gifski/bin/gifski`, sha256 `c7334a746f753b82148c08d5b671d1486b0984d78f7e20ba26ad1a16b860313a` (encode host only).

## GPU

- xbabe3 RTX 3090: 16×16, 1 sample, OptiX acceleration structure built, render ok. Other process was under both 50% yield lines.
- xbabe1 RTX 4090: same probe, render ok (optional host; ssh reached).
- xbabe2 RTX 3090: yielded. Utilization 62% with another process at about 6702 MiB. Probe was not started. That card was not cleared.

## Not started

- Production 4K stills and the 240-frame turntable. Codex has uncommitted ingest in its own worktree; the C.9.2 bundle was still running when this note was written. Claude `blender/worker.py` is not in this tree.
- `render/marketing-v1`, `ops/ci/gen_readme.py`, and the root README. COORD still has the v0.32 whitepaper claim (PR #42) and says render lanes stay queued. No release upload.

Repo `COORD.md` in this worktree has an unrelated local edit and was not committed.
