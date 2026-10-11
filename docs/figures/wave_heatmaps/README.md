# Per-wave FEM plates (wave 1-4) — FEM-UNCALIBRATED, PRE-BLADE-FIX

Copied from `out/mh1/heatmaps/` (box copy kept there) on 2026-10-11. Rendered by `ops/wave_figures/make_wave_figs.py`
per `docs/WAVE_FIGURE_TEMPLATE.md` from an offline Python port of fem.rs DKT+CST on a refined mesh.

- **FEM-UNCALIBRATED**: no per-element export from fem.rs and no MC<->FEM calibration yet.
- **PRE-BLADE-FIX / QUARANTINED**: every design shown was evolved under the inverted blade rule
  (fixed in 444a74d); all have ~44 mm tip-to-heel and are under 3.375 in on all three measures. None is a winner.
- Hunter 260 N floor fails on the plate for every wave. Floors stay 180 / 260 / 1500 N.
