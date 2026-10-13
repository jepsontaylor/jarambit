# Marketing render pipeline

Offline tooling for stills and a looping turntable of the SWITCHBACK-class titanium hiking/utility karambit. Appearance is `appearance_assumed`: a physically based visualization under stated material assumptions, not a measured coating.

The host process never imports `bpy`. Blender, when the scene worker is present, is a separate process. Mesh ingest and the display transform live in sibling modules (`ingest.py`, `regions.py`, `framing.py`, `finish.py`, `blender/worker.py`) and are called when they exist. A missing required tool fails the command. It is not skipped.

```
python3 ops/render/marketing/pipeline.py doctor --require ffmpeg,zscale,libx264,libx265,libwebp,blender --hosts
python3 ops/render/marketing/pipeline.py plan --bundle mesh/bundle.json --regions mesh/regions.json --out plan.json
python3 ops/render/marketing/pipeline.py render --plan plan.json --dest ~/jarambit_render_scratch/<plan_key> --bundle mesh/bundle.json --regions mesh/regions.json
python3 ops/render/marketing/pipeline.py encode --frames frames/ --out delivery/
python3 ops/render/marketing/pipeline.py qa --measurements qa_input.json --out qa.json --stills stills/*.png
python3 ops/render/marketing/pipeline.py package --root stage/ --bundle-sha <sha> --plan-key <key> --file still.png=hero_3q_1920.jpg:poster
```

`render` writes one request JSON per shard of 8 frames and does not launch Blender unless `--execute` is set. Launch is `nice -n 10` with at most 16 threads, detached with `nohup`. The coordinator (this machine) runs locally. `xbabe3` and, when ssh answers, `xbabe1` are reached with ssh. `ssh xbabe2` is a different host in this ssh config, so it is not used.

The yield rule: if another process holds more than half the GPU memory, or the GPU is over half utilized while another compute process is present, the shard stays unlaunched. Jobs are not killed for time. A receipt whose file hash still matches is skipped on the next run.

Camera frame recorded on every plan: Z up, blade plane XZ, azimuth 0 on -Y (face-on), azimuth 90 on +X, elevation above XY. One distance per shot, solved on the widest frame, so the turntable does not breathe. End-on frames are narrower and still keep a 6% margin. Frame 240 of a 240-frame loop is not rendered.

Encodes use zscale to convert full-range frames to BT.709 limited. They do not retag. `+faststart` is set on the MP4 files. GIF uses gifski at `~/opt/gifski` when that binary exists, otherwise ffmpeg `palettegen=stats_mode=diff`.

`package` writes `manifest.marketing.json`, `SHA256SUMS` and `README_SNIPPET.md` in the staging directory. It does not upload. `art_review` stays `pending` until a person sets it. QA release stays blocked until that happens and Q1–Q13 pass.

Pinned Blender is 4.2.23 LTS at `~/opt/blender-4.2.23-linux-x64/` on each host. The lock file is `toolchain.lock.json`.

Hero stills and the turntable use SWITCHBACK Rev C.9.2 only. `package` defaults `--cad` to `~/jarambit_render/inputs/switchback_C9.2/switchback_revC9_2_ground.step` and `--cad-sha` to `2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307`. The STL sha256 is `10b8c41f80b898c255cc090a349559722258f87f8af849ce9a605e14d762e847`. `render --execute` refuses any other source hash. The manifest and Q13 reject hero deliveries whose source is the retired STL `evidence/wave27/g3_tip+00_t60_tt3.stl` (`04404820cf8385f5e34a42ef9d39a79aecda8eb88895c78aa21f4e3a92fe28c5`). The earlier scratch bundle at `~/jarambit_render_scratch/hero` is superseded. Claude renders `~/jarambit_render_scratch/hero_C9.2/mesh`.
