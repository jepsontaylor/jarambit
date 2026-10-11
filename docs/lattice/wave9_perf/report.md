# wave9 — crescent internal-machining evolve (island GA + QD) — author Jepson Taylor

islands 6 x pop 48, gens 80, migrate every 5, threads 64, seed 9090, FEM search area 2 mm^2 (bias 1.11/1.08), certification min(0.25, 0.125 mm^2) no bias, T_MAX 6.0, mass target Some(80.0) g (JARAMBIT_MASS_CAP; target only, every hard item unchanged), seeds 18 (from out/wave7_lattice/all_evals.csv,docs/crescent/best_genome.csv + C.4), machining kick 0.6

## Census
evaluations 21888; aesthetic passers 20284; aesthetic + all hard gates 18661; LEGAL (search level) 15378; LEGAL and under the mass target 8204

reject reasons (count):
- BladeEdgeTooLong inside: 384
- BladeTooShort horizontal_reach: 84
- BrandPad not on a clear flat: 213
- GripOutOfBand: 15
- Hausdorff: 4
- Holder envelope: best oriented box: 1058
- Ligament cairn-outline: 333
- Ligament ring-outline: 179
- hawkbill edge not continuously concave: 1084
- no thumb seat: 218
- spine not a continuous convex crescent: 570
- straight stem: 35
- certification FAIL id 11702 (fit, 79.1 g): search lat_rob 300 -> certified 259 N, ring 13560
- certification FAIL id 19915 (fit, 78.3 g): search lat_rob 293 -> certified 230 N, ring 14142
- certification FAIL id 19136 (fit, 79.4 g): search lat_rob 306 -> certified 208 N, ring 14147

## Certification (min over 0.25 / 0.125 mm^2, no bias)
candidates certified 11, rejected at the converged mesh 3

## Plate designs (aesthetic passers only; certified metrics; twist SF = advisory)
- wave9_c01_fit (twist SF proxy 1.06, advisory; n_win 0, relief_frac 0.0679): {"id":7598,"gen":28,"fit":3.31174,"spg":3.81661,"mass_g":77.250,"blank_g":98.766,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.814,"horizontal_reach":87.676,"arc_in":101.236,"arc_sp":100.266,"grip":61.54,"aes_score":0.7487,"aes_pass":true,"hausdorff":1.380,"emd":0.0030,"straight_mm":10.50,"min_blend_r":9.94,"novelty":0.1589,"lat20":323.3,"lat_rob":294.8,"ring20":16493.6,"ring_rob":15042.2,"pry20":756.9,"twist20_nmm":1470.1,"sf_hiker":1.638,"sf_hunter":1.134,"sf_ring":10.028,"floors_ok":true,"lat_at":[12.68,-2.53],"holder_box":[199.1,99.2,-9.0],"removed_mm3":[331.5253,0.0000,0.0000,90.2697,107.3456,707.9886,275.8860],"min_web":2.04,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06786,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17391 mm^3 = 77.04 g (raster 77.25 g)
- wave9_c02_fit (twist SF proxy 1.06, advisory; n_win 0, relief_frac 0.0679): {"id":7346,"gen":27,"fit":3.30476,"spg":3.81661,"mass_g":77.250,"blank_g":98.766,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.814,"horizontal_reach":87.676,"arc_in":101.236,"arc_sp":100.266,"grip":61.54,"aes_score":0.7487,"aes_pass":true,"hausdorff":1.380,"emd":0.0030,"straight_mm":10.50,"min_blend_r":9.94,"novelty":0.1565,"lat20":323.3,"lat_rob":294.8,"ring20":16493.6,"ring_rob":15042.2,"pry20":756.9,"twist20_nmm":1470.1,"sf_hiker":1.638,"sf_hunter":1.134,"sf_ring":10.028,"floors_ok":true,"lat_at":[12.68,-2.53],"holder_box":[199.1,99.2,-9.0],"removed_mm3":[331.5253,0.0000,0.0000,90.2697,107.3456,707.9886,275.8860],"min_web":2.04,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06786,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17391 mm^3 = 77.04 g (raster 77.25 g)
- wave9_c03_fit (twist SF proxy 0.94, advisory; n_win 0, relief_frac 0.0771): {"id":16951,"gen":62,"fit":3.09199,"spg":3.65368,"mass_g":77.126,"blank_g":99.779,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.879,"horizontal_reach":87.460,"arc_in":101.306,"arc_sp":100.549,"grip":61.12,"aes_score":0.7475,"aes_pass":true,"hausdorff":1.336,"emd":0.0034,"straight_mm":10.00,"min_blend_r":8.71,"novelty":0.1321,"lat20":309.0,"lat_rob":281.8,"ring20":16000.1,"ring_rob":14592.1,"pry20":713.2,"twist20_nmm":1301.0,"sf_hiker":1.566,"sf_hunter":1.084,"sf_ring":9.728,"floors_ok":true,"lat_at":[12.72,-2.54],"holder_box":[199.4,99.9,-9.0],"removed_mm3":[301.7953,0.0000,38.9131,33.0326,177.9594,510.2997,673.4585],"min_web":1.80,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07705,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17321 mm^3 = 76.73 g (raster 77.13 g)
- wave9_c04_fit (twist SF proxy 1.06, advisory; n_win 0, relief_frac 0.0779): {"id":12956,"gen":47,"fit":3.00732,"spg":3.62952,"mass_g":78.323,"blank_g":101.963,"t":6.0,"material":"Ti-6Al-4V","tip_to_heel":96.964,"horizontal_reach":87.353,"arc_in":101.525,"arc_sp":100.664,"grip":61.50,"aes_score":0.7369,"aes_pass":true,"hausdorff":1.382,"emd":0.0037,"straight_mm":10.00,"min_blend_r":8.45,"novelty":0.1244,"lat20":311.7,"lat_rob":284.3,"ring20":14509.4,"ring_rob":13232.6,"pry20":680.4,"twist20_nmm":1466.1,"sf_hiker":1.579,"sf_hunter":1.093,"sf_ring":8.822,"floors_ok":true,"lat_at":[12.88,-1.27],"holder_box":[199.5,98.3,-8.5],"removed_mm3":[368.8804,25.6955,0.0000,57.0217,149.4497,574.4543,617.6789],"min_web":2.00,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07791,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17580 mm^3 = 77.88 g (raster 78.32 g)
- wave9_c05_fit (twist SF proxy 0.99, advisory; n_win 0, relief_frac 0.0780): {"id":18420,"gen":68,"fit":2.94260,"spg":3.40688,"mass_g":78.470,"blank_g":102.124,"t":6.0,"material":"Ti-6Al-4V","tip_to_heel":96.805,"horizontal_reach":87.492,"arc_in":101.225,"arc_sp":100.255,"grip":61.64,"aes_score":0.7490,"aes_pass":true,"hausdorff":1.421,"emd":0.0026,"straight_mm":14.50,"min_blend_r":9.94,"novelty":0.1532,"lat20":293.1,"lat_rob":267.3,"ring20":14827.4,"ring_rob":13522.6,"pry20":760.3,"twist20_nmm":1368.9,"sf_hiker":1.485,"sf_hunter":1.028,"sf_ring":9.015,"floors_ok":true,"lat_at":[12.89,-1.27],"holder_box":[198.9,99.5,-9.0],"removed_mm3":[448.0489,80.3127,0.0000,77.4223,74.1687,645.0413,473.1286],"min_web":1.80,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07800,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17680 mm^3 = 78.32 g (raster 78.47 g)
- wave9_c06_fit (twist SF proxy 1.06, advisory; n_win 0, relief_frac 0.0766): {"id":18483,"gen":68,"fit":2.88612,"spg":3.66319,"mass_g":78.529,"blank_g":102.044,"t":6.0,"material":"Ti-6Al-4V","tip_to_heel":96.964,"horizontal_reach":87.353,"arc_in":101.525,"arc_sp":100.664,"grip":61.50,"aes_score":0.7369,"aes_pass":true,"hausdorff":1.382,"emd":0.0037,"straight_mm":10.00,"min_blend_r":8.45,"novelty":0.0692,"lat20":315.4,"lat_rob":287.7,"ring20":14514.2,"ring_rob":13236.9,"pry20":680.4,"twist20_nmm":1466.1,"sf_hiker":1.598,"sf_hunter":1.106,"sf_ring":8.825,"floors_ok":true,"lat_at":[12.77,-2.56],"holder_box":[199.5,98.3,-8.5],"removed_mm3":[368.3011,25.6955,0.0000,57.0217,121.6775,574.6543,617.6789],"min_web":2.00,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07662,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17632 mm^3 = 78.11 g (raster 78.53 g)
- wave9_c07_fit (twist SF proxy 1.00, advisory; n_win 0, relief_frac 0.0775): {"id":17676,"gen":65,"fit":2.82923,"spg":3.47364,"mass_g":78.035,"blank_g":101.230,"t":5.9,"material":"Ti-6Al-4V","tip_to_heel":96.954,"horizontal_reach":86.884,"arc_in":101.516,"arc_sp":101.257,"grip":61.54,"aes_score":0.7406,"aes_pass":true,"hausdorff":1.399,"emd":0.0034,"straight_mm":10.00,"min_blend_r":8.47,"novelty":0.0997,"lat20":297.2,"lat_rob":271.1,"ring20":15001.2,"ring_rob":13681.1,"pry20":821.8,"twist20_nmm":1387.0,"sf_hiker":1.506,"sf_hunter":1.043,"sf_ring":9.121,"floors_ok":true,"lat_at":[12.65,-2.65],"holder_box":[198.9,99.1,-8.5],"removed_mm3":[426.1828,23.8851,0.0000,57.6113,83.3245,598.3477,580.6060],"min_web":1.77,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.07746,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17531 mm^3 = 77.66 g (raster 78.03 g)
- wave9_c08_fit (twist SF proxy 1.05, advisory; n_win 0, relief_frac 0.0651): {"id":17698,"gen":65,"fit":2.73432,"spg":3.39511,"mass_g":79.745,"blank_g":101.954,"t":5.9,"material":"Ti-6Al-4V","tip_to_heel":96.954,"horizontal_reach":86.884,"arc_in":101.516,"arc_sp":101.257,"grip":61.65,"aes_score":0.7245,"aes_pass":true,"hausdorff":1.499,"emd":0.0036,"straight_mm":10.00,"min_blend_r":8.47,"novelty":0.1116,"lat20":296.9,"lat_rob":270.7,"ring20":14758.4,"ring_rob":13459.7,"pry20":802.6,"twist20_nmm":1457.1,"sf_hiker":1.504,"sf_hunter":1.041,"sf_ring":8.973,"floors_ok":true,"lat_at":[12.93,-1.28],"holder_box":[198.8,99.0,-8.5],"removed_mm3":[403.4364,16.1870,0.0000,59.0791,0.0000,602.9616,416.6614],"min_web":1.90,"n_win":0,"win_area":0.00,"n_perf":0,"perf_area":0.00,"relief_frac":0.06510,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17993 mm^3 = 79.71 g (raster 79.75 g)

plates: ["wave9_c01_fit", "wave9_c02_fit", "wave9_c03_fit", "wave9_c04_fit", "wave9_c05_fit", "wave9_c06_fit", "wave9_c07_fit", "wave9_c08_fit"]
wall time 1521 s
