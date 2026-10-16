# w282_s2934 — crescent internal-machining evolve (island GA + QD) — author Jepson Taylor

islands 4 x pop 32, gens 16, migrate every 4, threads 8, seed 2934, FEM search area 4 mm^2 (search bias lat/ring (1.0, 1.0), JARAMBIT_SEARCH_BIAS_* override), certification min(0.25, 0.125 mm^2) no bias, T_MAX 6.0, fitness cap-free v2 (no mass cap; ln(84.8/m) reward, knee 70 g; strength floors hard)"", seeds 4 (from evidence/rs_v2/w281_ultrarunner/w281_s2932_c01_genome.csv,evidence/rs_v2/w281_ultrarunner/w281_s2932_c02_light_genome.csv,evidence/rs_v2/w281_ultrarunner/w281_s2932_c03_cert_genome.csv + C.6), aesthetic anchor SWITCHBACK Rev C.6 (C.5 jimping R0.8/0.45 + C.6 two-sided ring-face groove 0.6/face, 1.6 mm rims), machining kick 0.2, min through-features 0 (JARAMBIT_MIN_THROUGH)

evidence log `evidence.jevl`: 19 frames; fresh evaluations 1984, population appearances 2176

## Census
evaluations 1984; aesthetic passers 1705; aesthetic + all hard gates 1455; LEGAL (search level) 446; FEASIBLE (all strength floors incl. seq + twist) 446

reject reasons (count):
- BladeEdgeTooLong inside: 4
- BladeTooShort horizontal_reach: 5
- BrandPad not on a clear flat: 4
- C.: 91
- GripOutOfBand: 1
- Holder envelope: best oriented box: 281
- Ligament cairn-outline: 49
- Ligament ring-outline: 6
- hawkbill edge not continuously concave: 107
- no thumb seat: 29
- spine not a continuous convex crescent: 97
- straight stem: 8
- certification FAIL id 1902 (res, 75.2 g): search lat_rob 266 -> certified 264 N, strict 258 N, seq 1.19, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 1095 (res, 75.2 g): search lat_rob 267 -> certified 268 N, strict 264 N, seq 1.06, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 1237 (res, 75.3 g): search lat_rob 267 -> certified 268 N, strict 264 N, seq 1.06, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 1143 (res, 75.3 g): search lat_rob 266 -> certified 265 N, strict 260 N, seq 1.07, tip_sf 1.01, tipz_strict 1.09
- certification FAIL id 1563 (res, 75.4 g): search lat_rob 272 -> certified 266 N, strict 261 N, seq 1.09, tip_sf 1.04, tipz_strict 1.10
- certification FAIL id 1911 (res, 75.5 g): search lat_rob 268 -> certified 268 N, strict 264 N, seq 1.06, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 591 (res, 75.5 g): search lat_rob 262 -> certified 267 N, strict 267 N, seq 1.12, tip_sf 1.06, tipz_strict 1.15
- certification FAIL id 1489 (res, 75.6 g): search lat_rob 268 -> certified 268 N, strict 264 N, seq 1.07, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 701 (res, 75.7 g): search lat_rob 262 -> certified 263 N, strict 261 N, seq 1.19, tip_sf 1.05, tipz_strict 1.12
- certification FAIL id 1734 (res, 75.9 g): search lat_rob 263 -> certified 264 N, strict 258 N, seq 1.19, tip_sf 1.05, tipz_strict 1.12
- certification FAIL id 907 (res, 76.0 g): search lat_rob 268 -> certified 268 N, strict 268 N, seq 1.17, tip_sf 1.09, tipz_strict 1.18
- certification FAIL id 105 (res, 76.0 g): search lat_rob 262 -> certified 267 N, strict 267 N, seq 1.18, tip_sf 1.06, tipz_strict 1.16
- certification FAIL id 1838 (res, 76.0 g): search lat_rob 265 -> certified 267 N, strict 267 N, seq 1.18, tip_sf 1.14, tipz_strict 1.05
- certification FAIL id 1590 (res, 76.1 g): search lat_rob 268 -> certified 268 N, strict 264 N, seq 1.07, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 1730 (res, 76.1 g): search lat_rob 268 -> certified 268 N, strict 264 N, seq 1.07, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 1857 (res, 76.1 g): search lat_rob 268 -> certified 268 N, strict 264 N, seq 1.07, tip_sf 1.03, tipz_strict 1.10
- certification FAIL id 272 (res, 76.1 g): search lat_rob 267 -> certified 274 N, strict 267 N, seq 1.12, tip_sf 1.08, tipz_strict 1.09
- certification FAIL id 834 (light, 75.5 g): search lat_rob 260 -> certified 260 N, strict 254 N, seq 1.02, tip_sf 1.08, tipz_strict 1.10
- certification FAIL id 715 (light, 75.6 g): search lat_rob 270 -> certified 269 N, strict 267 N, seq 1.08, tip_sf 1.08, tipz_strict 1.10
- certification FAIL id 526 (fit, 76.2 g): search lat_rob 271 -> certified 265 N, strict 262 N, seq 1.01, tip_sf 1.05, tipz_strict 1.12
- certification FAIL id 245 (fit, 76.4 g): search lat_rob 271 -> certified 265 N, strict 262 N, seq 1.19, tip_sf 1.05, tipz_strict 1.12
- certification FAIL id 1394 (fit, 76.4 g): search lat_rob 271 -> certified 265 N, strict 262 N, seq 1.01, tip_sf 1.05, tipz_strict 1.12
- certification FAIL id 1526 (novel, 81.0 g): search lat_rob 267 -> certified 281 N, strict 277 N, seq 1.17, tip_sf 1.16, tipz_strict 1.11
- certification FAIL id 1530 (novel, 82.0 g): search lat_rob 268 -> certified 273 N, strict 265 N, seq 1.20, tip_sf 1.05, tipz_strict 1.16
- certification FAIL id 1886 (novel, 77.4 g): search lat_rob 264 -> certified 267 N, strict 264 N, seq 1.22, tip_sf 0.98, tipz_strict 1.17

## Certification (min over 0.25 / 0.125 mm^2, no bias)
candidates certified 27, rejected at the converged mesh 25

## Plate designs (aesthetic passers only; certified metrics; twist SF = advisory)
- w282_s2934_c01_fit (strict 0.0625 mm^2 check: PASS; chord-torsion SF vs 1.82 N*m joint+3D 1.04, advisory; n_win 0, n_perf 1, relief_frac 0.1033): {"id":1543,"gen":13,"fit":1.12799,"spg":3.49017,"mass_g":76.32,"blank_g":99.469,"t":5.9,"material":"Ti-6Al-4V","tip_to_heel":96.815,"horizontal_reach":87.276,"arc_in":101.009,"arc_sp":97.334,"grip":61.82,"aes_score":0.3677,"aes_pass":true,"hausdorff":2.613,"emd":0.0072,"straight_mm":22.0,"min_blend_r":8.53,"novelty":0.0074,"fem_status":"complete","lat20":302.2,"lat_rob":266.4,"ring20":16141.9,"ring_rob":14471.9,"pry20":610.3,"twist20_nmm":2576.7,"sf_hiker":1.48,"sf_hunter":1.024,"sf_ring":9.648,"floors_ok":true,"lat_at":[135.53,-9.6],"seq_ratio":1.213,"seq_case":"lateral","twist_tip_sf":1.038,"twist_tip_joint3d_nmm":1888.0,"twist_tip_peak_tipdist":4.1,"twist_body_sf":3.942,"twist_tipzone_sf":1.038,"holder_box":[199.8,99.8,-9.0],"removed_mm3":[255.0328,164.9998,303.7715,59.6613,0.0,627.3275,550.6158],"min_web":1.77,"n_win":0,"win_area":0.0,"n_perf":1,"perf_area":60.74,"relief_frac":0.10332,"rejects":[],"aes_fails":[],"legal":true,"t_joint":5.9,"p1":false,"rail_w":3.21,"neck_l":9.9,"pocket_d":0.016,"pocket_r":3.81,"knots":[5.9],"parents":[526,1425],"op":"crossover_mutate","op_version":1}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17204 mm^3 = 76.21 g (raster 76.32 g)
- w282_s2934_c02_novel (strict 0.0625 mm^2 check: PASS; chord-torsion SF vs 1.82 N*m joint+3D 1.08, advisory; n_win 0, n_perf 0, relief_frac 0.0370): {"id":695,"gen":5,"fit":0.99726,"spg":3.09072,"mass_g":84.642,"blank_g":102.864,"t":5.9,"material":"Ti-6Al-4V","tip_to_heel":96.623,"horizontal_reach":87.235,"arc_in":100.978,"arc_sp":97.247,"grip":61.27,"aes_score":0.3696,"aes_pass":true,"hausdorff":2.613,"emd":0.0069,"straight_mm":22.0,"min_blend_r":8.68,"novelty":0.2155,"fem_status":"complete","lat20":296.8,"lat_rob":261.6,"ring20":18930.3,"ring_rob":16971.8,"pry20":608.8,"twist20_nmm":2695.3,"sf_hiker":1.453,"sf_hunter":1.006,"sf_ring":11.315,"floors_ok":true,"lat_at":[164.28,-25.46],"seq_ratio":1.279,"seq_case":"lateral","twist_tip_sf":1.083,"twist_tip_joint3d_nmm":1972.0,"twist_tip_peak_tipdist":4.1,"twist_body_sf":3.983,"twist_tipzone_sf":1.083,"holder_box":[199.8,99.8,-9.0],"removed_mm3":[256.1018,174.3294,310.8576,59.5319,0.0,19.3193,39.2109],"min_web":1.95,"n_win":0,"win_area":0.0,"n_perf":0,"perf_area":0.0,"relief_frac":0.03701,"rejects":[],"aes_fails":[],"legal":true,"t_joint":5.9,"p1":false,"rail_w":3.21,"neck_l":9.9,"pocket_d":0.016,"pocket_r":3.81,"knots":[5.9],"parents":[468],"op":"archive_mutate","op_version":1}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 19111 mm^3 = 84.66 g (raster 84.64 g)

plates: ["w282_s2934_c01_fit", "w282_s2934_c02_novel"]
wall time 1226 s
