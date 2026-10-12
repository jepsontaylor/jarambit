# metrics/ — GLOBAL weighted multi-objective metric G, wave plates

| | |
|---|---|
| Code | `metrics/global_metric.py` (G, title tag, VERSION reader) · plate generators in `ops/wave_figures/` (`make_d1_plate.py` wired) · aesthetic score `crates/crescent/src/aesthetic.rs` |
| Inputs | plate metric dicts / `*_D1_index.json` (keys `solid_tip_sf_nodal_max`, `plate_tipsub_screen_sf`, `spg`, `aes_score`, `mass_g`, `seq_ratio`) |
| Outputs | G per design, plate title suffix `G <g> | <mass> g | jarambit v<VERSION>`, `G` + `G_terms` in the plate index JSON |
| Hard gates | none — G NEVER overrides a hard gate; hard-FAIL designs are labelled and never promoted on G |
| Template | `docs/WAVE_FIGURE_TEMPLATE.md` |

## G (locked, version G1)
`G = 0.35·min(SF_tip,2) + 0.35·SPG/4.0 + 0.20·aes − 0.05·max(0,m−77)/10 − 0.05·max(0,1.2−seq)/1.2`

`G*` (asterisk) = solid tip submodel missing, plate tip-submodel screen SF used instead (provisional).

```bash
python3 metrics/global_metric.py docs/wave24_diversity/plates/wave24_D1_index.json   # rank a wave
```
