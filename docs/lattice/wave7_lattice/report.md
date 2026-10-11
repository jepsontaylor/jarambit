# wave7 — crescent internal-machining evolve (island GA + QD) — author Jepson Taylor

islands 6 x pop 48, gens 60, migrate every 5, threads 64, seed 707, FEM search area 2 mm^2 (bias 1.11/1.08), certification min(0.25, 0.125 mm^2) no bias, T_MAX 6.0, mass target Some(80.0) g (JARAMBIT_MASS_CAP; target only, every hard item unchanged), seeds 9 (from docs/crescent/best_genome.csv,/home/ubuntu/jarambit/.agent/worktrees/exec-crescent/out/crescent_smoke/all_evals.csv + C.4), machining kick 0.5

## Census
evaluations 16488; aesthetic passers 15048; aesthetic + all hard gates 14217; LEGAL (search level) 9655; LEGAL and under the mass target 2833

reject reasons (count):
- BladeEdgeTooLong inside: 257
- BladeTooShort horizontal_reach: 42
- BrandPad not on a clear flat: 93
- GripOutOfBand: 13
- Hausdorff: 3
- Holder envelope: best oriented box: 362
- Ligament cairn-outline: 169
- Ligament ring-outline: 284
- hawkbill edge not continuously concave: 1037
- no thumb seat: 161
- spine not a continuous convex crescent: 453
- straight stem: 58
- certification FAIL id 5370 (fit, 79.1 g): search lat_rob 265 -> certified 259 N, ring 12496
- certification FAIL id 15622 (fit, 78.9 g): search lat_rob 301 -> certified 231 N, ring 14975
- certification FAIL id 7800 (fit, 78.4 g): search lat_rob 275 -> certified 252 N, ring 12420
- certification FAIL id 16221 (fit, 76.7 g): search lat_rob 288 -> certified 242 N, ring 13463
- certification FAIL id 13014 (fit, 75.8 g): search lat_rob 273 -> certified 238 N, ring 12955

## Certification (min over 0.25 / 0.125 mm^2, no bias)
candidates certified 13, rejected at the converged mesh 5

## Plate designs (aesthetic passers only; certified metrics; twist SF = advisory)
- wave7_c01_fit (twist SF proxy 0.94, advisory; n_win 0, relief_frac 0.0769): {"id":15020,"gen":55,"fit":2.93378,"spg":3.44715,"mass_g":77.601,"blank_g":100.382,"t":5.7,"material":"Ti-6Al-4V","tip_to_heel":96.831,"horizontal_reach":87.339,"arc_in":101.349,"arc_sp":100.583,"grip":61.13,"aes_score":0.7370,"aes_pass":true,"hausdorff":1.235,"emd":0.0050,"straight_mm":13.00,"min_blend_r":10.18,"novelty":0.1548,"lat20":293.3,"lat_rob":267.5,"ring20":15265.6,"ring_rob":13922.2,"pry20":737.4,"twist20_nmm":1303.0,"sf_hiker":1.486,"sf_hunter":1.029,"sf_ring":9.281,"floors_ok":true,"lat_at":[12.78,-2.56],"holder_box":[199.8,98.6,-8.5],"removed_mm3":[332.7224,0.0000,66.6108,111.7750,93.2084,467.6082,669.8617],"min_web":1.71,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17461 mm^3 = 77.35 g (raster 77.60 g)
- wave7_c02_fit (twist SF proxy 0.97, advisory; n_win 0, relief_frac 0.0722): {"id":16331,"gen":60,"fit":2.90911,"spg":3.59212,"mass_g":78.577,"blank_g":99.307,"t":5.7,"material":"Ti-6Al-4V","tip_to_heel":96.755,"horizontal_reach":87.230,"arc_in":101.249,"arc_sp":101.264,"grip":61.16,"aes_score":0.7479,"aes_pass":true,"hausdorff":1.259,"emd":0.0040,"straight_mm":13.00,"min_blend_r":9.16,"novelty":0.0828,"lat20":309.5,"lat_rob":282.3,"ring20":15007.2,"ring_rob":13686.6,"pry20":785.7,"twist20_nmm":1337.2,"sf_hiker":1.568,"sf_hunter":1.086,"sf_ring":9.124,"floors_ok":true,"lat_at":[12.74,-2.54],"holder_box":[199.3,98.4,-8.5],"removed_mm3":[324.0314,73.9237,90.8780,122.5742,0.0000,460.2784,547.2704],"min_web":1.71,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17664 mm^3 = 78.25 g (raster 78.58 g)
- wave7_c03_fit (twist SF proxy 0.78, advisory; n_win 0, relief_frac 0.0671): {"id":15803,"gen":58,"fit":2.85209,"spg":3.56909,"mass_g":79.660,"blank_g":101.873,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.755,"horizontal_reach":87.237,"arc_in":101.248,"arc_sp":101.264,"grip":60.97,"aes_score":0.7590,"aes_pass":true,"hausdorff":1.179,"emd":0.0040,"straight_mm":13.00,"min_blend_r":9.16,"novelty":0.0529,"lat20":311.7,"lat_rob":284.3,"ring20":15780.0,"ring_rob":14391.4,"pry20":749.4,"twist20_nmm":1071.5,"sf_hiker":1.580,"sf_hunter":1.094,"sf_ring":9.594,"floors_ok":true,"lat_at":[12.68,-2.51],"holder_box":[199.5,98.6,-8.5],"removed_mm3":[441.8574,0.0000,0.0000,84.7340,0.0000,444.9670,571.5218],"min_web":2.24,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17940 mm^3 = 79.48 g (raster 79.66 g)
- wave7_c04_fit (twist SF proxy 1.00, advisory; n_win 0, relief_frac 0.0630): {"id":16256,"gen":60,"fit":2.82510,"spg":3.54702,"mass_g":78.198,"blank_g":100.433,"t":5.9,"material":"Ti-6Al-4V","tip_to_heel":96.838,"horizontal_reach":87.338,"arc_in":101.334,"arc_sp":101.266,"grip":61.67,"aes_score":0.6972,"aes_pass":true,"hausdorff":1.572,"emd":0.0049,"straight_mm":13.50,"min_blend_r":9.18,"novelty":0.1424,"lat20":304.1,"lat_rob":277.4,"ring20":16111.4,"ring_rob":14693.6,"pry20":677.0,"twist20_nmm":1375.0,"sf_hiker":1.541,"sf_hunter":1.067,"sf_ring":9.796,"floors_ok":true,"lat_at":[105.59,2.97],"holder_box":[199.4,98.3,-8.5],"removed_mm3":[272.9392,0.0000,49.6677,62.8899,116.0895,456.6370,470.9188],"min_web":1.90,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17625 mm^3 = 78.08 g (raster 78.20 g)
- wave7_c05_fit (twist SF proxy 0.94, advisory; n_win 0, relief_frac 0.0755): {"id":15285,"gen":56,"fit":2.73666,"spg":3.41421,"mass_g":78.245,"blank_g":100.928,"t":5.7,"material":"Ti-6Al-4V","tip_to_heel":96.831,"horizontal_reach":87.339,"arc_in":101.349,"arc_sp":100.583,"grip":61.13,"aes_score":0.7370,"aes_pass":true,"hausdorff":1.235,"emd":0.0050,"straight_mm":13.00,"min_blend_r":10.18,"novelty":0.0876,"lat20":292.9,"lat_rob":267.1,"ring20":15311.3,"ring_rob":13963.9,"pry20":737.6,"twist20_nmm":1303.0,"sf_hiker":1.484,"sf_hunter":1.027,"sf_ring":9.309,"floors_ok":true,"lat_at":[12.75,-2.55],"holder_box":[199.8,98.6,-8.5],"removed_mm3":[330.2723,0.0000,49.0196,114.4050,88.5747,467.6082,669.8617],"min_web":1.71,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17600 mm^3 = 77.97 g (raster 78.25 g)
- wave7_c06_fit (twist SF proxy 1.07, advisory; n_win 0, relief_frac 0.0559): {"id":16235,"gen":60,"fit":2.71745,"spg":3.43203,"mass_g":79.325,"blank_g":100.195,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.787,"horizontal_reach":87.514,"arc_in":101.229,"arc_sp":101.263,"grip":61.25,"aes_score":0.7479,"aes_pass":true,"hausdorff":1.347,"emd":0.0033,"straight_mm":14.00,"min_blend_r":9.18,"novelty":0.0586,"lat20":298.5,"lat_rob":272.2,"ring20":14658.0,"ring_rob":13368.1,"pry20":679.6,"twist20_nmm":1479.7,"sf_hiker":1.512,"sf_hunter":1.047,"sf_ring":8.912,"floors_ok":true,"lat_at":[12.91,-1.24],"holder_box":[199.1,99.4,-9.0],"removed_mm3":[333.2714,0.0000,12.8856,67.5577,0.0000,232.2896,617.7141],"min_web":1.80,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17833 mm^3 = 79.00 g (raster 79.33 g)
- wave7_c07_fit (twist SF proxy 1.00, advisory; n_win 0, relief_frac 0.0562): {"id":14291,"gen":52,"fit":2.63171,"spg":3.40195,"mass_g":78.964,"blank_g":99.820,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.831,"horizontal_reach":87.339,"arc_in":101.349,"arc_sp":101.285,"grip":61.48,"aes_score":0.7232,"aes_pass":true,"hausdorff":1.348,"emd":0.0050,"straight_mm":13.00,"min_blend_r":10.17,"novelty":0.0697,"lat20":294.6,"lat_rob":268.6,"ring20":14221.6,"ring_rob":12970.1,"pry20":750.0,"twist20_nmm":1385.2,"sf_hiker":1.492,"sf_hunter":1.033,"sf_ring":8.647,"floors_ok":true,"lat_at":[12.87,-1.27],"holder_box":[199.4,98.3,-8.5],"removed_mm3":[346.8228,0.0000,0.0000,0.0000,0.0000,302.7465,617.6833],"min_web":1.80,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17742 mm^3 = 78.60 g (raster 78.96 g)
- wave7_c08_fit (twist SF proxy 1.06, advisory; n_win 0, relief_frac 0.0655): {"id":13563,"gen":50,"fit":2.63091,"spg":3.34088,"mass_g":78.890,"blank_g":99.077,"t":5.6,"material":"Ti-6Al-4V","tip_to_heel":96.832,"horizontal_reach":87.327,"arc_in":101.348,"arc_sp":101.276,"grip":60.98,"aes_score":0.7372,"aes_pass":true,"hausdorff":1.259,"emd":0.0048,"straight_mm":15.00,"min_blend_r":9.15,"novelty":0.0683,"lat20":289.0,"lat_rob":263.6,"ring20":15180.3,"ring_rob":13844.4,"pry20":799.5,"twist20_nmm":1460.4,"sf_hiker":1.464,"sf_hunter":1.014,"sf_ring":9.230,"floors_ok":true,"lat_at":[12.86,-1.26],"holder_box":[199.7,98.6,-8.5],"removed_mm3":[298.4939,20.1424,0.0000,59.2139,0.0000,517.2462,570.1598],"min_web":1.68,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17765 mm^3 = 78.70 g (raster 78.89 g)

plates: ["wave7_c01_fit", "wave7_c02_fit", "wave7_c03_fit", "wave7_c04_fit", "wave7_c05_fit", "wave7_c06_fit", "wave7_c07_fit", "wave7_c08_fit"]
wall time 1253 s
