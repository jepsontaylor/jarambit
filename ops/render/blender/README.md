# Candidate re-render command

After the automated winner, exported geometry and certificate artifacts are
committed on main, fetch main and run from this worktree:

```sh
python3 ops/render/blender/rerender.py CERTIFIED_GENOME_ID
```

This resolves the ID in the committed automatic leaderboards and renders all 16
gate plates plus oblique, reverse and section views. Use `--leaderboard PATH` if
the same ID occurs in more than one retained leaderboard. Final mode requires
the actual qualified champion, `all_16_gates=true`, `rs_v2_all_hard=true`, no
unverified assessments, matching exported-geometry/raw-solver hashes, and inputs
unchanged from `origin/main`. It validates retained observations; it does not run
the export, search, FEM or certification. This command cannot issue a certificate.

Outputs go to `docs/figures/whitepaper/winner/GENOME_ID/`. Integrate the admitted
images into the existing final-design slot, regenerate documentation and run the
required checks before opening the one paper PR. Nothing is inserted into the
paper automatically. The catalog denominator remains 23×18=414.

The scene library is reused unchanged, so the existing #84 failure atlas and its
manifests stay intact. The adapter supplies the actual candidate STL, saved D1
plate field and gate verdicts. Typography states the candidate's status. Section
views cut the actual STL at z=0; finishes and fixtures are illustrative. Stress
colors, where shown, are the retained multi-load D1 envelope, not a new solve or
a load-specific solid field. Every output manifest binds the exact inputs,
render scripts, context, annotations and raw frame hash.

For a local rehearsal on an assessed failure:

```sh
python3 ops/render/blender/rerender.py cert_pipeline_r01_p14_c02 \
  --leaderboard evidence/evolve_certifiable/automatic/leaderboard.json \
  --preview --samples 16
```

This committed fixture is an assessed failure. Every scene says **NOT-A-WINNER · LOCAL
PREVIEW · NOT FOR PAPER**. Preview mode defaults to ignored
`target/paper/rerender-preview/GENOME_ID/` and refuses output under this worktree's
`docs/` or the source checkout's `docs/`. `--output-dir PATH` can archive the rehearsal outside the repository.
`--scene NAME` renders one plate; `--plan-only` validates and prints the resolved
inputs without starting Blender. Normal rendering uses Cycles CPU, four threads,
`nice -n 10`, `~/bin/memcap 32G --`, denoising and 48 samples (16 in the preview
command above).
The wrapper uses `~/opt/blender-4.5.3-linux-x64/blender` when installed (the same
official build as the retained atlas); otherwise it uses `blender` from PATH.
Set `BLENDER` to another denoising-capable build if needed. The host's packaged
4.0.2 build lacks OpenImageDenoiser and cannot run the denoising scene settings.

# Stage the IV-D wave-history insertion

```sh
python3 ops/render/paper/wave_history.py \
  --output-dir target/paper/wave-history \
  evidence/evolution_plateau/2026-10-17/xbabe2/out/w298/leaderboard.json \
  evidence/evolution_plateau/2026-10-17/xbabe3/out/w401c3/leaderboard.json
```

This reads the actual files and generates `fig_wave_history.png`, a hash-bound
manifest, a JSON-pointer/reduction ledger and `iv_d_wave_history.md`. It reports
mass and W_CAD ranges/medians only for selected completed Stage-2 candidates;
these are not full-population statistics. Missing waves are not imputed. Add a
later wave only after its actual leaderboard exists. A partial live leaderboard
does not prove a wave completed; use the owner's completed-wave handoff and
committed capture scope when publishing.

Before publication, replace runtime paths with the evidence paths actually
committed on main, fetch main, use this worktree (the default source root), omit `--preview`, and regenerate. Without preview,
the script rejects any input absent from or different from `origin/main`. Insert
the resulting subsection into IV-D and keep the companion consistent. No docs PR
may cite the runtime preview as committed evidence. Never copy or edit another
lane's evidence to bypass that admission rule.

The numerical collection and insertion functions use the standard library, so
provenance controls run without plotting packages. Generating the actual PNG
requires NumPy and a complete Matplotlib installation; Blender typography also
uses Pillow, as described in the repository prerequisites.
