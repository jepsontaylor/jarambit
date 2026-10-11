# Crescent smoke (C.4-anchored aesthetic genotype) — author Jepson Taylor

pop 64 gens 40 threads 48 seed 7 seed-stock 5.7 mm, FEM search area 2 mm^2, plates/winners certified at min(0.25, 0.125) mm^2 (plate-area arg 1 unused), T_MAX 6.0

## C.4 seed at 5.7 mm
mass 82.64 g (blank 101.49 g), blade Blade { tip_to_heel: 96.66506779286105, horizontal_reach: 87.01814403148684, arc_in: 101.17262738288765, arc_sp: 100.65070249940214, sharpened_arc: 101.17262738288765, spine_offset_used: 24.0, hook_drop: 42.09486834180425 }, grip 60.50
aesthetic Aes { hausdorff: 0.7554828568139131, emd: 0.0, straight_mm: 16.5, min_concave_r: 13.306106571637871, spine_convex: 0.935064935064935, inside_concave: 1.0, seat_depth: 0.8166467110561602, lobe_prom: 9.48608031190074, hook_drop: 42.09486834180425, score: 0.8816908369099782, pass: true, fails: [] }
gates ["Holder envelope: best oriented box 200.5 x 100.2 > 200 x 100"]
FEM Some(Fem { lat20: 170.4567553726159, pry20: 777.2312038713893, twist20_nmm: 533.4574576290063, ring20: 24312.725602994615, lat_rob: 140.05095576560873, ring_rob: 20530.74606475101, sf_hiker: 0.7780608653644929, sf_hunter: 0.5386575221754182, sf_ring: 13.68716404316734, lat_at: (187.92142155575831, -49.434770598168825), ring_at: (1.8612323858951256, -12.547409544928962), nodes: 2707, tris: 4548, floors_ok: false })
holder box (false, 200.48524960635763, 100.19488283900832, -8.5)

## Census
evaluations 2624; aesthetic passers 2317; aesthetic + all hard gates 1832; LEGAL (also floors 180/260/1500 robust) 505

reject reasons (count):
- BladeEdgeTooLong inside: 25
- BladeTooShort horizontal_reach: 19
- BrandPad not on a clear flat: 24
- GripOutOfBand: 8
- Holder envelope: best oriented box: 467
- Ligament cairn-outline: 59
- Ligament ring-outline: 19
- hawkbill edge not continuously concave: 239
- no thumb seat: 23
- spine not a continuous convex crescent: 79
- straight stem: 10

## Certification
candidates certified 3, rejected at the converged mesh 0

## Plate designs (aesthetic passers only; certified metrics)
- crescent_smoke_top: {"id":2421,"gen":40,"fit":2.86706,"spg":3.79640,"mass_g":87.472,"blank_g":104.811,"t":5.9,"material":"Ti-6Al-4V","tip_to_heel":96.605,"horizontal_reach":87.533,"arc_in":101.241,"arc_sp":100.250,"grip":61.31,"aes_score":0.7143,"aes_pass":true,"hausdorff":1.457,"emd":0.0047,"straight_mm":11.50,"min_blend_r":9.33,"novelty":0.0572,"lat20":364.1,"lat_rob":332.1,"ring20":17725.1,"ring_rob":16165.3,"pry20":712.2,"twist20_nmm":1246.4,"sf_hiker":1.845,"sf_hunter":1.277,"sf_ring":10.777,"floors_ok":true,"lat_at":[176.87,-32.64],"holder_box":[198.8,99.2,-9.0],"removed_mm3":[289.5978,0.0000,0.0000,76.3054,0.0000],"min_web":3.08,"rejects":[],"aes_fails":[],"legal":true}
- crescent_smoke_qd2: {"id":2345,"gen":39,"fit":2.55710,"spg":3.45829,"mass_g":84.868,"blank_g":101.461,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.801,"horizontal_reach":87.638,"arc_in":101.328,"arc_sp":100.151,"grip":61.34,"aes_score":0.6912,"aes_pass":true,"hausdorff":1.579,"emd":0.0053,"straight_mm":16.00,"min_blend_r":9.10,"novelty":0.0697,"lat20":321.8,"lat_rob":293.5,"ring20":18097.4,"ring_rob":16504.8,"pry20":694.2,"twist20_nmm":1246.5,"sf_hiker":1.631,"sf_hunter":1.129,"sf_ring":11.003,"floors_ok":true,"lat_at":[25.37,-2.51],"holder_box":[198.9,99.0,-9.0],"removed_mm3":[156.2778,0.0000,28.4237,123.9856,0.0000],"min_web":3.36,"rejects":[],"aes_fails":[],"legal":true}
- crescent_smoke_qd3: {"id":2409,"gen":40,"fit":2.18780,"spg":3.18036,"mass_g":84.837,"blank_g":102.183,"t":5.8,"material":"Ti-6Al-4V","tip_to_heel":96.599,"horizontal_reach":87.649,"arc_in":101.269,"arc_sp":100.542,"grip":61.41,"aes_score":0.6485,"aes_pass":true,"hausdorff":1.629,"emd":0.0048,"straight_mm":17.50,"min_blend_r":13.26,"novelty":0.0608,"lat20":295.8,"lat_rob":269.8,"ring20":15961.8,"ring_rob":14557.1,"pry20":697.9,"twist20_nmm":1139.6,"sf_hiker":1.499,"sf_hunter":1.038,"sf_ring":9.705,"floors_ok":true,"lat_at":[12.78,-2.51],"holder_box":[198.9,98.8,-9.0],"removed_mm3":[386.8493,24.2718,0.0000,113.1738,0.0000],"min_web":3.52,"rejects":[],"aes_fails":[],"legal":true}

## Export (top design)
watertight: boundary edges 0, non-manifold 0, max directed-edge repeat 1 => WATERTIGHT; solid volume 19733 mm^3 = 87.42 g (raster 87.47 g); faces 16632

plates: ["crescent_smoke_top", "crescent_smoke_qd2", "crescent_smoke_qd3", "crescent_c4_seed"]
wall time 249 s
