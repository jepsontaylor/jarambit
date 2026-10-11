# D1 re-screen — screening yield 828 MPa (TIMET min, provisional), JOINT thin+hot, chord-torsion floor 1.82 N*m

Certification min(0.25, 0.125 mm^2) unbiased; strict 0.0625 mm^2 unbiased; joint factor = ((t-0.1)/t)^2 x yield(100C)/yield(20C) (ring: ^1). PASS = hiker 180 / hunter 260 / ring 1500 N at certification AND hunter at strict. Twist = advisory proposed floor (not a gate yet). Seq ratio = hand-zone / blade-zone yield-onset load (min over lateral, chord-torsion, pry), target >= 1.2.

| design | mass g | t mm | A pass | gates | joint lat N (cert) | SF hiker | SF hunter | joint ring N | SF ring | strict 0.0625 joint lat N (SF hunter) | PASS @828 joint | pre-D1 lat_rob 880/min N (SF hunter) | chord-torsion plate N*mm @20C | 3D k (b/t) | joint+3D N*mm | SF vs 1.82 N*m | twist | peak dist from tip mm | body (>15 mm from tip) joint N*mm | hand-side joint N*mm | pre-D1 couple N*mm (old SF) | seq ratio (case) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| wave13_c01 | 74.37 | 5.6 | yes | ok | 234.4 | 1.302 | 0.902 | 12521 | 8.35 | 248.6 (0.956) | **FAIL** | 258.3 (0.993) | 1069 | 1.153 (4.7) | 816 | 0.448 | FAIL | 4.1 | 5270 | 31779 | 1200 (0.92) | 0.84 (lateral) |
| wave14_c03 | 76.95 | 5.8 | yes | ok | 280.2 | 1.557 | 1.078 | 12913 | 8.61 | 269.8 (1.038) | **PASS** | 308.3 (1.186) | 1286 | 1.167 (4.4) | 970 | 0.533 | FAIL | 4.2 | 6214 | 24702 | 1368 (1.05) | 0.84 (lateral) |
| wave13_c07 | 74.03 | 5.5 | yes | ok | 237.4 | 1.319 | 0.913 | 12585 | 8.39 | 214.5 (0.825) | **FAIL** | 261.8 (1.007) | 1117 | 1.148 (4.9) | 867 | 0.476 | FAIL | 4.1 | 6012 | 27403 | 1174 (0.90) | 0.92 (lateral) |
| wave14_c01 | 76.38 | 5.8 | yes | ok | 269.2 | 1.496 | 1.035 | 14275 | 9.52 | 260.3 (1.001) | **PASS** | 296.2 (1.139) | 1328 | 1.153 (4.7) | 1014 | 0.557 | FAIL | 4.1 | 6577 | 23499 | 1520 (1.17) | 0.83 (lateral) |
| C6seed_t5.7_REF | 81.01 | 5.7 | yes | FAIL | 137.7 | 0.765 | 0.529 | 18550 | 12.37 | 147.0 (0.565) | **FAIL** | 151.6 (0.583) | 457 | 1.124 (5.7) | 358 | 0.197 | FAIL | 4.2 | 2641 | 26528 | 549 (0.42) | 1.55 (lateral) |
| REF_C6_thin_3.175 | 48.34 | 3.2 | yes | FAIL | 54.8 | 0.305 | 0.211 | 9776 | 6.52 | 54.3 (0.209) | **FAIL** | 62.1 (0.239) | 414 | 1.108 (6.5) | 320 | 0.176 | FAIL | 4.1 | 1990 | 10205 | 437 (0.34) | 0.44 (lateral) |
