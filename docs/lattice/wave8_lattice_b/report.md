# wave8 — crescent internal-machining evolve (island GA + QD) — author Jepson Taylor

islands 8 x pop 48, gens 80, migrate every 5, threads 48, seed 909, FEM search area 2 mm^2 (bias 1.11/1.08), certification min(0.25, 0.125 mm^2) no bias, T_MAX 6.0, mass target Some(78.0) g (JARAMBIT_MASS_CAP; target only, every hard item unchanged), seeds 9 (from docs/crescent/best_genome.csv,seeds/wave6_all_evals.csv + C.4), machining kick 0.8

## Census
evaluations 29184; aesthetic passers 26470; aesthetic + all hard gates 24911; LEGAL (search level) 16884; LEGAL and under the mass target 4690

reject reasons (count):
- BladeEdgeTooLong inside: 377
- BladeTooShort horizontal_reach: 51
- BrandPad not on a clear flat: 256
- GripOutOfBand: 19
- Hausdorff: 10
- Holder envelope: best oriented box: 858
- Ligament cairn-outline: 291
- Ligament ring-outline: 383
- hawkbill edge not continuously concave: 2003
- no thumb seat: 314
- spine not a continuous convex crescent: 861
- straight stem: 65
- certification FAIL id 25558 (fit, 77.3 g): search lat_rob 301 -> certified 251 N, ring 14521
- certification FAIL id 25241 (fit, 76.4 g): search lat_rob 277 -> certified 250 N, ring 14235
- certification FAIL id 21777 (fit, 76.5 g): search lat_rob 296 -> certified 242 N, ring 14709
- certification FAIL id 28234 (fit, 75.8 g): search lat_rob 304 -> certified 211 N, ring 14129

## Certification (min over 0.25 / 0.125 mm^2, no bias)
candidates certified 12, rejected at the converged mesh 4

## Plate designs (aesthetic passers only; certified metrics; twist SF = advisory)
- wave8_c01_fit (twist SF proxy 0.82, advisory; n_win 0, relief_frac 0.0502): {"id":24486,"gen":67,"fit":3.50748,"spg":3.91655,"mass_g":76.257,"blank_g":95.037,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.886,"horizontal_reach":87.631,"arc_in":101.317,"arc_sp":100.057,"grip":61.03,"aes_score":0.7396,"aes_pass":true,"hausdorff":1.446,"emd":0.0030,"straight_mm":10.50,"min_blend_r":7.35,"novelty":0.2109,"lat20":327.5,"lat_rob":298.7,"ring20":16706.8,"ring_rob":15236.6,"pry20":673.0,"twist20_nmm":1138.5,"sf_hiker":1.659,"sf_hunter":1.149,"sf_ring":10.158,"floors_ok":true,"lat_at":[12.65,-2.52],"holder_box":[199.1,99.5,-9.0],"removed_mm3":[199.3566,0.0000,19.4994,0.0000,82.6517,401.2329,375.0960],"min_web":1.65,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17222 mm^3 = 76.29 g (raster 76.26 g)
- wave8_c02_fit (twist SF proxy 0.98, advisory; n_win 0, relief_frac 0.0472): {"id":27794,"gen":77,"fit":3.28170,"spg":3.75916,"mass_g":76.761,"blank_g":95.917,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.779,"horizontal_reach":87.561,"arc_in":100.894,"arc_sp":100.373,"grip":61.13,"aes_score":0.7412,"aes_pass":true,"hausdorff":1.342,"emd":0.0038,"straight_mm":12.50,"min_blend_r":6.46,"novelty":0.1778,"lat20":316.4,"lat_rob":288.6,"ring20":15516.9,"ring_rob":14151.4,"pry20":699.4,"twist20_nmm":1358.5,"sf_hiker":1.603,"sf_hunter":1.110,"sf_ring":9.434,"floors_ok":true,"lat_at":[28.99,-8.05],"holder_box":[199.3,99.4,-9.0],"removed_mm3":[232.0170,9.0175,25.4893,117.1268,142.6005,19.2912,476.4327],"min_web":2.29,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17284 mm^3 = 76.57 g (raster 76.76 g)
- wave8_c03_fit (twist SF proxy 0.98, advisory; n_win 0, relief_frac 0.0509): {"id":25971,"gen":72,"fit":3.04356,"spg":3.72167,"mass_g":77.827,"blank_g":96.124,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.892,"horizontal_reach":87.639,"arc_in":101.319,"arc_sp":100.570,"grip":61.22,"aes_score":0.7460,"aes_pass":true,"hausdorff":1.386,"emd":0.0031,"straight_mm":9.50,"min_blend_r":7.35,"novelty":0.0962,"lat20":317.6,"lat_rob":289.6,"ring20":17678.5,"ring_rob":16122.8,"pry20":781.3,"twist20_nmm":1348.8,"sf_hiker":1.609,"sf_hunter":1.114,"sf_ring":10.749,"floors_ok":true,"lat_at":[46.08,-6.52],"holder_box":[199.1,99.3,-9.0],"removed_mm3":[199.6288,0.0000,0.0000,55.3473,0.0000,577.0329,271.8252],"min_web":1.65,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17539 mm^3 = 77.70 g (raster 77.83 g)
- wave8_c04_fit (twist SF proxy 0.98, advisory; n_win 0, relief_frac 0.0547): {"id":26833,"gen":74,"fit":3.02109,"spg":3.83311,"mass_g":77.079,"blank_g":95.579,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.876,"horizontal_reach":87.619,"arc_in":101.305,"arc_sp":100.046,"grip":61.37,"aes_score":0.7494,"aes_pass":true,"hausdorff":1.367,"emd":0.0030,"straight_mm":10.50,"min_blend_r":7.37,"novelty":0.0517,"lat20":324.0,"lat_rob":295.5,"ring20":16096.8,"ring_rob":14680.3,"pry20":699.8,"twist20_nmm":1354.3,"sf_hiker":1.641,"sf_hunter":1.136,"sf_ring":9.787,"floors_ok":true,"lat_at":[12.85,-1.26],"holder_box":[199.5,99.6,-9.0],"removed_mm3":[183.8370,0.0000,28.6559,12.3179,0.0000,465.2787,489.4884],"min_web":1.65,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17372 mm^3 = 76.96 g (raster 77.08 g)
- wave8_c05_fit (twist SF proxy 1.01, advisory; n_win 0, relief_frac 0.0712): {"id":26383,"gen":73,"fit":3.01056,"spg":3.63607,"mass_g":75.060,"blank_g":96.205,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.797,"horizontal_reach":87.614,"arc_in":100.724,"arc_sp":100.382,"grip":61.15,"aes_score":0.7481,"aes_pass":true,"hausdorff":1.472,"emd":0.0022,"straight_mm":10.00,"min_blend_r":7.64,"novelty":0.1068,"lat20":299.3,"lat_rob":272.9,"ring20":14373.6,"ring_rob":13108.7,"pry20":747.1,"twist20_nmm":1401.8,"sf_hiker":1.516,"sf_hunter":1.050,"sf_ring":8.739,"floors_ok":true,"lat_at":[12.90,-1.25],"holder_box":[199.2,99.3,-9.0],"removed_mm3":[312.6577,193.0550,36.0238,23.3971,0.0000,449.4048,532.5932],"min_web":1.65,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 16934 mm^3 = 75.02 g (raster 75.06 g)
- wave8_c06_fit (twist SF proxy 0.94, advisory; n_win 0, relief_frac 0.0412): {"id":25457,"gen":70,"fit":2.98885,"spg":3.86527,"mass_g":76.914,"blank_g":94.239,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.884,"horizontal_reach":87.628,"arc_in":101.314,"arc_sp":100.055,"grip":61.28,"aes_score":0.7368,"aes_pass":true,"hausdorff":1.446,"emd":0.0032,"straight_mm":10.50,"min_blend_r":7.37,"novelty":0.0495,"lat20":326.0,"lat_rob":297.3,"ring20":14848.6,"ring_rob":13541.9,"pry20":703.9,"twist20_nmm":1305.3,"sf_hiker":1.652,"sf_hunter":1.143,"sf_ring":9.028,"floors_ok":true,"lat_at":[12.89,-1.27],"holder_box":[198.9,99.3,-9.0],"removed_mm3":[191.0479,0.0000,0.0000,72.5451,0.0000,99.3439,513.7913],"min_web":1.79,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17322 mm^3 = 76.73 g (raster 76.91 g)
- wave8_c07_fit (twist SF proxy 0.84, advisory; n_win 0, relief_frac 0.0563): {"id":28216,"gen":78,"fit":2.89861,"spg":3.54710,"mass_g":76.978,"blank_g":96.024,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.815,"horizontal_reach":87.560,"arc_in":101.224,"arc_sp":100.064,"grip":61.26,"aes_score":0.7535,"aes_pass":true,"hausdorff":1.317,"emd":0.0032,"straight_mm":10.50,"min_blend_r":7.39,"novelty":0.0844,"lat20":299.4,"lat_rob":273.0,"ring20":15294.1,"ring_rob":13948.2,"pry20":675.5,"twist20_nmm":1160.5,"sf_hiker":1.517,"sf_hunter":1.050,"sf_ring":9.299,"floors_ok":true,"lat_at":[12.93,-1.10],"holder_box":[199.6,99.7,-9.0],"removed_mm3":[298.1584,0.0000,34.1490,62.6019,0.0000,160.4263,664.1079],"min_web":1.65,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17337 mm^3 = 76.80 g (raster 76.98 g)
- wave8_c08_fit (twist SF proxy 0.98, advisory; n_win 0, relief_frac 0.0587): {"id":21584,"gen":59,"fit":2.80616,"spg":3.50418,"mass_g":76.486,"blank_g":95.648,"t":5.5,"material":"Ti-6Al-4V","tip_to_heel":96.876,"horizontal_reach":87.619,"arc_in":101.305,"arc_sp":100.046,"grip":61.37,"aes_score":0.7494,"aes_pass":true,"hausdorff":1.367,"emd":0.0030,"straight_mm":10.50,"min_blend_r":7.37,"novelty":0.0686,"lat20":293.9,"lat_rob":268.0,"ring20":15768.5,"ring_rob":14380.9,"pry20":684.0,"twist20_nmm":1352.7,"sf_hiker":1.489,"sf_hunter":1.031,"sf_ring":9.587,"floors_ok":true,"lat_at":[45.85,-3.93],"holder_box":[199.5,99.6,-9.0],"removed_mm3":[201.2116,0.0000,28.4254,72.6511,0.0000,440.1279,525.3255],"min_web":1.65,"rejects":[],"aes_fails":[],"legal":true}
  export: boundary edges 0, non-manifold 0, max directed repeat 1 => WATERTIGHT; volume 17220 mm^3 = 76.29 g (raster 76.49 g)

plates: ["wave8_c01_fit", "wave8_c02_fit", "wave8_c03_fit", "wave8_c04_fit", "wave8_c05_fit", "wave8_c06_fit", "wave8_c07_fit", "wave8_c08_fit"]
wall time 1833 s
