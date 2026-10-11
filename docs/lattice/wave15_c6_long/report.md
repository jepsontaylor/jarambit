# wave15 — crescent internal-machining evolve (island GA + QD) — author Jepson Taylor

islands 8 x pop 48, gens 240, migrate every 6, threads 48, seed 1515, FEM search area 2 mm^2 (search bias lat/ring (1.11, 1.08), JARAMBIT_SEARCH_BIAS_* override), certification min(0.25, 0.125 mm^2) no bias, T_MAX 6.0, mass target Some(72.0) g (JARAMBIT_MASS_CAP; target only, every hard item unchanged), seeds 45 (from out/seeds_w15.csv + C.6), aesthetic anchor SWITCHBACK Rev C.6 (C.5 jimping R0.8/0.45 + C.6 two-sided ring-face groove 0.6/face, 1.6 mm rims), machining kick 0.7, min through-features 0 (JARAMBIT_MIN_THROUGH)

## Census
evaluations 86784; aesthetic passers 74894; aesthetic + all hard gates 66546; LEGAL (search level) 42055; LEGAL and under the mass target 4823

reject reasons (count):
- BladeEdgeTooLong inside: 2102
- BladeTooShort horizontal_reach: 253
- BrandPad not on a clear flat: 1203
- C.: 4294
- GripOutOfBand: 64
- Hausdorff: 19
- Holder envelope: best oriented box: 5567
- Ligament cairn-outline: 3169
- Ligament ring-outline: 242
- hawkbill edge not continuously concave: 5203
- no thumb seat: 1447
- spine not a continuous convex crescent: 2986
- straight stem: 97
- certification FAIL id 58611 (fit, 69.8 g): search lat_rob 264 -> certified 156 N, ring 12900
- certification FAIL id 82811 (fit, 71.3 g): search lat_rob 281 -> certified 198 N, ring 13277
- certification FAIL id 83861 (fit, 71.1 g): search lat_rob 273 -> certified 201 N, ring 13259
- certification FAIL id 66103 (fit, 71.1 g): search lat_rob 283 -> certified 241 N, ring 13171
- certification FAIL id 71385 (fit, 69.8 g): search lat_rob 262 -> certified 251 N, ring 13348
- certification FAIL id 78162 (fit, 71.2 g): search lat_rob 266 -> certified 229 N, ring 12260
- certification FAIL id 78110 (fit, 70.8 g): search lat_rob 261 -> certified 230 N, ring 12401
- certification FAIL id 78821 (fit, 70.8 g): search lat_rob 261 -> certified 230 N, ring 12401
- certification FAIL id 70311 (fit, 71.7 g): search lat_rob 271 -> certified 163 N, ring 13247
- certification FAIL id 71362 (fit, 71.3 g): search lat_rob 275 -> certified 243 N, ring 14655
- certification FAIL id 45016 (fit, 70.3 g): search lat_rob 264 -> certified 246 N, ring 14325
- certification FAIL id 78833 (fit, 70.9 g): search lat_rob 271 -> certified 233 N, ring 12406
- certification FAIL id 80556 (fit, 71.9 g): search lat_rob 281 -> certified 191 N, ring 12766
- certification FAIL id 79112 (fit, 71.3 g): search lat_rob 281 -> certified 193 N, ring 12766
- certification FAIL id 81619 (fit, 71.7 g): search lat_rob 266 -> certified 249 N, ring 15006
- certification FAIL id 30041 (fit, 71.7 g): search lat_rob 277 -> certified 247 N, ring 13497
- certification FAIL id 78051 (fit, 71.6 g): search lat_rob 287 -> certified 259 N, ring 12610
- certification FAIL id 82416 (fit, 71.6 g): search lat_rob 281 -> certified 193 N, ring 13289
- certification FAIL id 50544 (fit, 71.8 g): search lat_rob 270 -> certified 245 N, ring 13193
- certification FAIL id 80618 (fit, 71.9 g): search lat_rob 278 -> certified 210 N, ring 12766
- certification FAIL id 59228 (fit, 71.0 g): search lat_rob 275 -> certified 215 N, ring 14306
- certification FAIL id 79688 (light, 68.3 g): search lat_rob 261 -> certified 251 N, ring 12288
- certification FAIL id 86221 (light, 68.3 g): search lat_rob 260 -> certified 250 N, ring 12938

## Certification (min over 0.25 / 0.125 mm^2, no bias)
candidates certified 32, rejected at the converged mesh 23

## Plate designs (aesthetic passers only; certified metrics; twist SF = advisory)
- wave15_c01_fit (strict 0.0625 mm^2 check: PASS; twist SF proxy 0.94, advisory; n_win 0, n_perf 0, relief_frac 0.0691): {"id":79314,"gen":220,"fit":3.17756,"spg":3.88209,"mass_g":71.649,"blank_g":94.792,"t":5.7,"material":"Ti-6Al-4V","tip_to_heel":96.881,"horizontal_reach":87.601,"arc_in":101.272,"arc_sp":101.259,"grip":61.21,"aes_score":0.7460,"aes_pass":true,"hausdorff":1.325,"emd":0.0036,"straight_mm":10.50,"min_blend_r":13.18,"novelty":0.0973,"lat20":305.0,"lat_rob":278.1,"ring20":14160.9,"ring_rob":12914.7,"pry20":643.5,"twist20_nmm":1295.9,"sf_hiker":1.545,"sf_hunter":1.070,"sf_ring":8.610,"floors_ok":true,"lat_at":[12.40,-3.76],"holder_box":[199.2,99.6,-9.0],"removed_mm3":[535.5219,0.0000,0.0000,52.0006,121.7973,318.9796,450.1785],"min_web":1.71,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06909,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16165 mm^3 = 71.61 g (raster 71.65 g)
- wave15_c02_fit (strict 0.0625 mm^2 check: PASS; twist SF proxy 0.95, advisory; n_win 0, n_perf 0, relief_frac 0.0681): {"id":77688,"gen":215,"fit":3.12498,"spg":3.86596,"mass_g":71.818,"blank_g":93.986,"t":5.7,"material":"Ti-6Al-4V","tip_to_heel":96.882,"horizontal_reach":87.579,"arc_in":101.253,"arc_sp":100.045,"grip":61.54,"aes_score":0.7296,"aes_pass":true,"hausdorff":1.448,"emd":0.0037,"straight_mm":14.50,"min_blend_r":13.63,"novelty":0.1079,"lat20":304.4,"lat_rob":277.6,"ring20":14290.4,"ring_rob":13032.9,"pry20":666.7,"twist20_nmm":1306.3,"sf_hiker":1.542,"sf_hunter":1.068,"sf_ring":8.689,"floors_ok":true,"lat_at":[12.89,-1.31],"holder_box":[199.2,99.5,-9.0],"removed_mm3":[243.8576,7.0457,51.6666,32.3941,67.7286,532.1314,510.9538],"min_web":1.71,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06815,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16179 mm^3 = 71.67 g (raster 71.82 g)
- wave15_c03_fit (strict 0.0625 mm^2 check: PASS; twist SF proxy 0.94, advisory; n_win 0, n_perf 0, relief_frac 0.0650): {"id":63725,"gen":176,"fit":3.05479,"spg":3.74817,"mass_g":71.514,"blank_g":93.004,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.886,"horizontal_reach":87.589,"arc_in":101.264,"arc_sp":101.256,"grip":61.27,"aes_score":0.7265,"aes_pass":true,"hausdorff":1.427,"emd":0.0041,"straight_mm":14.50,"min_blend_r":13.51,"novelty":0.1218,"lat20":293.9,"lat_rob":268.0,"ring20":14849.0,"ring_rob":13542.3,"pry20":668.5,"twist20_nmm":1295.1,"sf_hiker":1.489,"sf_hunter":1.031,"sf_ring":9.028,"floors_ok":true,"lat_at":[12.51,-3.78],"holder_box":[199.2,99.6,-9.0],"removed_mm3":[423.7706,9.4525,0.0000,0.0000,76.7244,466.1136,388.4930],"min_web":1.68,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06500,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16116 mm^3 = 71.40 g (raster 71.51 g)
- wave15_c04_fit (strict 0.0625 mm^2 check: PASS; twist SF proxy 0.86, advisory; n_win 0, n_perf 0, relief_frac 0.0770): {"id":77542,"gen":215,"fit":2.95445,"spg":3.68390,"mass_g":71.126,"blank_g":94.032,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.893,"horizontal_reach":87.617,"arc_in":101.268,"arc_sp":101.256,"grip":61.21,"aes_score":0.7425,"aes_pass":true,"hausdorff":1.325,"emd":0.0038,"straight_mm":10.00,"min_blend_r":13.19,"novelty":0.0801,"lat20":287.3,"lat_rob":262.0,"ring20":14014.2,"ring_rob":12780.9,"pry20":704.2,"twist20_nmm":1192.9,"sf_hiker":1.456,"sf_hunter":1.008,"sf_ring":8.521,"floors_ok":true,"lat_at":[12.75,-2.43],"holder_box":[199.2,99.6,-9.0],"removed_mm3":[421.6304,0.0000,39.6381,11.5927,129.9617,507.3041,524.5282],"min_web":1.68,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07701,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16054 mm^3 = 71.12 g (raster 71.13 g)
- wave15_c05_fit (strict 0.0625 mm^2 check: PASS; twist SF proxy 1.00, advisory; n_win 0, n_perf 0, relief_frac 0.0616): {"id":77169,"gen":214,"fit":2.92435,"spg":3.71757,"mass_g":71.958,"blank_g":93.295,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.905,"horizontal_reach":87.612,"arc_in":101.261,"arc_sp":101.255,"grip":61.22,"aes_score":0.7406,"aes_pass":true,"hausdorff":1.325,"emd":0.0040,"straight_mm":10.00,"min_blend_r":13.61,"novelty":0.0621,"lat20":293.3,"lat_rob":267.5,"ring20":14106.5,"ring_rob":12865.1,"pry20":716.7,"twist20_nmm":1379.9,"sf_hiker":1.486,"sf_hunter":1.029,"sf_ring":8.577,"floors_ok":true,"lat_at":[12.40,-3.75],"holder_box":[199.2,99.6,-9.0],"removed_mm3":[324.8738,0.0000,0.0000,42.0880,103.8735,338.0411,489.1321],"min_web":1.68,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06163,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16232 mm^3 = 71.91 g (raster 71.96 g)
- wave15_c06_fit (strict 0.0625 mm^2 check: PASS; twist SF proxy 0.96, advisory; n_win 0, n_perf 0, relief_frac 0.0591): {"id":77962,"gen":216,"fit":2.83643,"spg":3.64641,"mass_g":71.927,"blank_g":92.807,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.881,"horizontal_reach":87.601,"arc_in":101.272,"arc_sp":101.259,"grip":61.28,"aes_score":0.7429,"aes_pass":true,"hausdorff":1.325,"emd":0.0038,"straight_mm":11.00,"min_blend_r":13.17,"novelty":0.0471,"lat20":287.6,"lat_rob":262.3,"ring20":14406.0,"ring_rob":13138.3,"pry20":675.3,"twist20_nmm":1329.0,"sf_hiker":1.457,"sf_hunter":1.009,"sf_ring":8.759,"floors_ok":true,"lat_at":[12.40,-3.80],"holder_box":[199.2,99.5,-9.0],"removed_mm3":[424.0405,4.8066,15.8462,50.3040,0.0000,379.9639,363.0729],"min_web":1.68,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.05910,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16238 mm^3 = 71.94 g (raster 71.93 g)
- wave15_c07_fit (strict 0.0625 mm^2 check: FAIL; twist SF proxy 0.99, advisory; n_win 0, n_perf 0, relief_frac 0.0658): {"id":76730,"gen":213,"fit":3.05672,"spg":3.88920,"mass_g":71.623,"blank_g":92.991,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.886,"horizontal_reach":87.589,"arc_in":101.264,"arc_sp":101.256,"grip":61.34,"aes_score":0.7308,"aes_pass":true,"hausdorff":1.427,"emd":0.0038,"straight_mm":14.50,"min_blend_r":13.51,"novelty":0.0754,"lat20":305.4,"lat_rob":278.6,"ring20":14863.1,"ring_rob":13555.2,"pry20":695.9,"twist20_nmm":1369.2,"sf_hiker":1.548,"sf_hunter":1.071,"sf_ring":9.037,"floors_ok":true,"lat_at":[12.46,-3.76],"holder_box":[199.2,99.5,-9.0],"removed_mm3":[376.4685,9.1644,0.0000,0.0000,116.7876,496.6972,381.5264],"min_web":1.68,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06577,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16177 mm^3 = 71.66 g (raster 71.62 g)
- wave15_c08_fit (strict 0.0625 mm^2 check: FAIL; twist SF proxy 0.83, advisory; n_win 0, n_perf 0, relief_frac 0.0763): {"id":82918,"gen":230,"fit":3.02184,"spg":3.74537,"mass_g":71.987,"blank_g":94.487,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.886,"horizontal_reach":87.608,"arc_in":101.258,"arc_sp":101.245,"grip":61.29,"aes_score":0.7484,"aes_pass":true,"hausdorff":1.294,"emd":0.0037,"straight_mm":9.00,"min_blend_r":13.18,"novelty":0.0781,"lat20":295.6,"lat_rob":269.6,"ring20":14307.4,"ring_rob":13048.3,"pry20":671.0,"twist20_nmm":1149.2,"sf_hiker":1.498,"sf_hunter":1.037,"sf_ring":8.699,"floors_ok":true,"lat_at":[12.43,-3.77],"holder_box":[199.2,99.5,-9.0],"removed_mm3":[428.7920,0.0000,41.6524,11.4150,176.1996,513.5605,455.8065],"min_web":1.68,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07630,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16211 mm^3 = 71.82 g (raster 71.99 g)
- wave15_c09_fit (strict 0.0625 mm^2 check: FAIL; twist SF proxy 0.93, advisory; n_win 0, n_perf 0, relief_frac 0.0746): {"id":69483,"gen":192,"fit":2.96012,"spg":3.72083,"mass_g":70.251,"blank_g":92.751,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.886,"horizontal_reach":87.589,"arc_in":101.264,"arc_sp":101.256,"grip":61.27,"aes_score":0.7265,"aes_pass":true,"hausdorff":1.427,"emd":0.0041,"straight_mm":14.50,"min_blend_r":13.51,"novelty":0.0950,"lat20":286.6,"lat_rob":261.4,"ring20":13756.2,"ring_rob":12545.7,"pry20":663.3,"twist20_nmm":1289.5,"sf_hiker":1.452,"sf_hunter":1.005,"sf_ring":8.364,"floors_ok":true,"lat_at":[12.42,-3.78],"holder_box":[199.2,99.6,-9.0],"removed_mm3":[423.1356,4.9548,24.5289,54.6428,68.5972,453.6415,531.9972],"min_web":1.68,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07458,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 15829 mm^3 = 70.12 g (raster 70.25 g)

plates: ["wave15_c01_fit", "wave15_c02_fit", "wave15_c03_fit", "wave15_c04_fit", "wave15_c05_fit", "wave15_c06_fit", "wave15_c07_fit", "wave15_c08_fit", "wave15_c09_fit"]
wall time 4959 s
