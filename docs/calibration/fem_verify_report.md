# Detailed plate FEM verification (jarambit fem-verify)

Element: numerically-built Batoz DKT (bending) + CST (membrane), spade CDT mesh (min angle 25 deg), RCM + skyline Cholesky. Bending stress is the corner value of the linear DKT curvature field; membrane peaks at holes are area-weighted nodal averages.

## 1. Closed-form checks (ratio = model / theory)

| check | max area mm^2 | nodes | model | theory | ratio | err % |
|---|---|---|---|---|---|---|
| cantilever tip deflection | 4.000 | 149 | 2.81233e-2 | 2.81195e-2 | 1.0001 | 0.01 |
| cantilever mid-span stress | 4.000 | 149 | 1.04158e0 | 1.00000e0 | 1.0416 | 4.16 |
| cantilever tip deflection (mesh rotated 33 deg) | 4.000 | 142 | 2.81230e-2 | 2.81195e-2 | 1.0001 | 0.01 |
| cantilever mid-span stress (mesh rotated 33 deg) | 4.000 | 142 | 1.04167e0 | 1.00000e0 | 1.0417 | 4.17 |
| clamped plate point-load deflection | 4.000 | 362 | 1.08608e-4 | 1.07473e-4 | 1.0106 | 1.06 |
| clamped plate uniform-load deflection | 4.000 | 362 | 3.90862e-2 | 3.86902e-2 | 1.0102 | 1.02 |
| clamped plate edge von Mises (uniform) | 4.000 | 362 | 1.17885e2 | 1.09431e2 | 1.0772 | 7.72 |
| curved bar inner-fibre stress (Golovin, T6) | 4.000 | 766 | 6.92526e1 | 6.93263e1 | 0.9989 | 0.11 |
| hole Kt_gross (Heywood, d/W=0.2, T6) | 4.000 | 8192 | 3.09207e0 | 3.14000e0 | 0.9847 | 1.53 |
| cantilever tip deflection | 2.000 | 276 | 2.81210e-2 | 2.81195e-2 | 1.0001 | 0.01 |
| cantilever mid-span stress | 2.000 | 276 | 1.02709e0 | 1.00000e0 | 1.0271 | 2.71 |
| cantilever tip deflection (mesh rotated 33 deg) | 2.000 | 275 | 2.81212e-2 | 2.81195e-2 | 1.0001 | 0.01 |
| cantilever mid-span stress (mesh rotated 33 deg) | 2.000 | 275 | 1.02788e0 | 1.00000e0 | 1.0279 | 2.79 |
| clamped plate point-load deflection | 2.000 | 658 | 1.08125e-4 | 1.07473e-4 | 1.0061 | 0.61 |
| clamped plate uniform-load deflection | 2.000 | 658 | 3.89835e-2 | 3.86902e-2 | 1.0076 | 0.76 |
| clamped plate edge von Mises (uniform) | 2.000 | 658 | 1.14638e2 | 1.09431e2 | 1.0476 | 4.76 |
| curved bar inner-fibre stress (Golovin, T6) | 2.000 | 1205 | 6.92765e1 | 6.93263e1 | 0.9993 | 0.07 |
| hole Kt_gross (Heywood, d/W=0.2, T6) | 2.000 | 16017 | 3.11081e0 | 3.14000e0 | 0.9907 | 0.93 |
| cantilever tip deflection | 1.000 | 526 | 2.81203e-2 | 2.81195e-2 | 1.0000 | 0.00 |
| cantilever mid-span stress | 1.000 | 526 | 1.02013e0 | 1.00000e0 | 1.0201 | 2.01 |
| cantilever tip deflection (mesh rotated 33 deg) | 1.000 | 510 | 2.81203e-2 | 2.81195e-2 | 1.0000 | 0.00 |
| cantilever mid-span stress (mesh rotated 33 deg) | 1.000 | 510 | 1.01984e0 | 1.00000e0 | 1.0198 | 1.98 |
| clamped plate point-load deflection | 1.000 | 1316 | 1.07983e-4 | 1.07473e-4 | 1.0047 | 0.47 |
| clamped plate uniform-load deflection | 1.000 | 1316 | 3.89152e-2 | 3.86902e-2 | 1.0058 | 0.58 |
| clamped plate edge von Mises (uniform) | 1.000 | 1316 | 1.13678e2 | 1.09431e2 | 1.0388 | 3.88 |
| curved bar inner-fibre stress (Golovin, T6) | 1.000 | 1989 | 6.93196e1 | 6.93263e1 | 0.9999 | 0.01 |
| hole Kt_gross (Heywood, d/W=0.2, T6) | 1.000 | 31715 | 3.15077e0 | 3.14000e0 | 1.0034 | 0.34 |
| cantilever tip deflection | 0.500 | 1041 | 2.81199e-2 | 2.81195e-2 | 1.0000 | 0.00 |
| cantilever mid-span stress | 0.500 | 1041 | 1.01400e0 | 1.00000e0 | 1.0140 | 1.40 |
| cantilever tip deflection (mesh rotated 33 deg) | 0.500 | 1024 | 2.81199e-2 | 2.81195e-2 | 1.0000 | 0.00 |
| cantilever mid-span stress (mesh rotated 33 deg) | 0.500 | 1024 | 1.01375e0 | 1.00000e0 | 1.0138 | 1.38 |
| clamped plate point-load deflection | 0.500 | 2578 | 1.07830e-4 | 1.07473e-4 | 1.0033 | 0.33 |
| clamped plate uniform-load deflection | 0.500 | 2578 | 3.88816e-2 | 3.86902e-2 | 1.0049 | 0.49 |
| clamped plate edge von Mises (uniform) | 0.500 | 2578 | 1.12487e2 | 1.09431e2 | 1.0279 | 2.79 |
| curved bar inner-fibre stress (Golovin, T6) | 0.500 | 5810 | 6.93106e1 | 6.93263e1 | 0.9998 | 0.02 |
| hole Kt_gross (Heywood, d/W=0.2, T6) | 0.500 | 64124 | 3.17536e0 | 3.14000e0 | 1.0113 | 1.13 |
| cantilever tip deflection | 0.250 | 2000 | 2.81197e-2 | 2.81195e-2 | 1.0000 | 0.00 |
| cantilever mid-span stress | 0.250 | 2000 | 1.00985e0 | 1.00000e0 | 1.0099 | 0.99 |
| cantilever tip deflection (mesh rotated 33 deg) | 0.250 | 1988 | 2.81197e-2 | 2.81195e-2 | 1.0000 | 0.00 |
| cantilever mid-span stress (mesh rotated 33 deg) | 0.250 | 1988 | 1.00962e0 | 1.00000e0 | 1.0096 | 0.96 |
| clamped plate point-load deflection | 0.250 | 5120 | 1.07777e-4 | 1.07473e-4 | 1.0028 | 0.28 |
| clamped plate uniform-load deflection | 0.250 | 5120 | 3.88679e-2 | 3.86902e-2 | 1.0046 | 0.46 |
| clamped plate edge von Mises (uniform) | 0.250 | 5120 | 1.12034e2 | 1.09431e2 | 1.0238 | 2.38 |
| curved bar inner-fibre stress (Golovin, T6) | 0.250 | 9355 | 6.93191e1 | 6.93263e1 | 0.9999 | 0.01 |
| hole Kt_gross (Heywood, d/W=0.2, T6) | 0.250 | 126759 | 3.18174e0 | 3.14000e0 | 1.0133 | 1.33 |

Theory gate (finest level, every check < 5 % error): **PASS**

## 2. Knife mesh convergence (20 C capacities, N; levels halve the max triangle area)

Six levels (max triangle area 4 -> 0.125 mm^2). f_ref = mean of the two finest levels; err = |f - f_ref| / f_ref. Gate per case: every one of the 4 finest levels within 5 % of f_ref AND the search level (A = 2 mm^2) within 5 %. Richardson extrapolation (h ratio sqrt 2) is shown when the three finest levels are monotone. Lateral and ring pull are floor cases and must pass; pry is reported only.

### wave5_smoke_legal_blade

t = 4.5 mm, mass 48.92 g, neck flare 0.00 mm/side over 15.0 mm, fillet r 0.00 mm; blade tip-heel/reach/arc 89.6/88.8/100.7 mm

| case | A=4 | A=2 | A=1 | A=0.5 | A=0.25 | A=0.125 | f_ref (2 finest) | Richardson | max err 4 finest % | search-level err % | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lateral | 120.0 | 123.8 | 122.2 | 121.1 | 121.8 | 120.3 | 121.0 | n/a (non-monotone) | 1.01 | 2.29 | PASS |
| pry | 304.4 | 306.1 | 307.4 | 297.8 | 305.6 | 301.2 | 303.4 | n/a (non-monotone) | 1.85 | 0.88 | PASS |
| ring pull | 2820.2 | 2814.0 | 2830.7 | 2791.3 | 2790.1 | 2709.8 | 2750.0 | n/a (non-monotone) | 2.94 | 2.33 | PASS |

nodes per level: 1819, 2089, 2832, 5891, 9290, 17762; solve s: 0.40, 0.42, 0.54, 1.35, 2.70, 7.89; lateral peak at (-74.9, -68.0) = ring; ring-pull peak per level: (-86.7,-68.0) ring; (-86.7,-68.0) ring; (-74.9,-68.0) ring; (-74.9,-68.0) ring; (-74.8,-68.0) ring; (-86.7,-68.0) ring

### mh1_xbabe1_s3001

t = 4.5 mm, mass 33.78 g, neck flare 0.00 mm/side over 15.0 mm, fillet r 0.00 mm; blade tip-heel/reach/arc 43.7/32.7/54.2 mm

| case | A=4 | A=2 | A=1 | A=0.5 | A=0.25 | A=0.125 | f_ref (2 finest) | Richardson | max err 4 finest % | search-level err % | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lateral | 188.9 | 189.6 | 183.4 | 187.5 | 191.6 | 190.3 | 191.0 | n/a (non-monotone) | 3.97 | 0.73 | PASS |
| pry | 434.1 | 437.0 | 434.1 | 431.2 | 429.9 | 422.9 | 426.4 | n/a (non-monotone) | 1.82 | 2.49 | PASS |
| ring pull | 2357.9 | 2361.5 | 2357.4 | 2309.9 | 2329.3 | 2252.8 | 2291.0 | n/a (non-monotone) | 2.90 | 3.08 | PASS |

nodes per level: 1538, 1722, 2235, 4510, 6889, 12765; solve s: 0.27, 0.37, 0.50, 1.18, 2.32, 5.48; lateral peak at (-22.4, -65.8) = ring; ring-pull peak per level: (-34.6,-65.8) ring; (-34.6,-65.8) ring; (-22.4,-65.8) ring; (-34.6,-65.7) ring; (-34.7,-65.8) ring; (-34.6,-65.8) ring

### switchback_ref_sharp_neck

t = 3.0 mm, mass 31.69 g, neck flare 0.00 mm/side over 13.1 mm, fillet r 0.00 mm; blade tip-heel/reach/arc 86.6/88.1/96.8 mm

| case | A=4 | A=2 | A=1 | A=0.5 | A=0.25 | A=0.125 | f_ref (2 finest) | Richardson | max err 4 finest % | search-level err % | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lateral | 30.3 | 31.1 | 30.0 | 30.4 | 30.8 | 30.1 | 30.5 | n/a (non-monotone) | 1.66 | 2.15 | PASS |
| pry | 104.3 | 104.9 | 105.4 | 102.5 | 103.9 | 102.0 | 103.0 | n/a (non-monotone) | 2.34 | 1.87 | PASS |
| ring pull | 1087.6 | 1092.7 | 1093.3 | 1077.6 | 1062.7 | 1041.5 | 1052.1 | n/a (non-monotone) | 3.92 | 3.86 | PASS |

nodes per level: 2947, 3179, 3841, 7600, 10679, 19577; solve s: 1.15, 0.84, 0.89, 2.85, 3.61, 11.33; lateral peak at (-77.6, -79.2) = ring; ring-pull peak per level: (-77.6,-79.2) ring; (-87.6,-79.2) ring; (-87.6,-79.2) ring; (-87.6,-79.2) ring; (-87.6,-79.2) ring; (-87.6,-79.2) ring

### switchback_ref_neck_fillet6_flare3

t = 3.0 mm, mass 32.39 g, neck flare 3.00 mm/side over 18.0 mm, fillet r 6.00 mm; blade tip-heel/reach/arc 86.6/88.1/96.8 mm

| case | A=4 | A=2 | A=1 | A=0.5 | A=0.25 | A=0.125 | f_ref (2 finest) | Richardson | max err 4 finest % | search-level err % | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lateral | 50.6 | 51.7 | 49.9 | 51.7 | 50.5 | 50.5 | 50.5 | n/a (non-monotone) | 2.39 | 2.28 | PASS |
| pry | 115.8 | 116.5 | 116.8 | 115.3 | 114.1 | 114.4 | 114.2 | n/a (non-monotone) | 2.24 | 2.01 | PASS |
| ring pull | 3684.9 | 3675.6 | 3657.2 | 3660.7 | 3660.5 | 3530.7 | 3595.6 | n/a (non-monotone) | 1.81 | 2.22 | PASS |

nodes per level: 2878, 3085, 3798, 7554, 10692, 19813; solve s: 1.17, 0.96, 0.85, 2.71, 3.37, 10.60; lateral peak at (-86.6, -28.6) = grip; ring-pull peak per level: (-74.2,-80.1) ring; (-74.0,-80.3) ring; (-74.2,-80.1) ring; (-91.1,-80.3) ring; (-91.1,-80.3) ring; (-91.1,-80.3) ring

### wave5_with_neck_fillet6_flare3

t = 4.5 mm, mass 49.94 g, neck flare 3.00 mm/side over 18.0 mm, fillet r 6.00 mm; blade tip-heel/reach/arc 89.6/88.8/100.7 mm

| case | A=4 | A=2 | A=1 | A=0.5 | A=0.25 | A=0.125 | f_ref (2 finest) | Richardson | max err 4 finest % | search-level err % | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| lateral | 220.5 | 219.7 | 218.7 | 219.1 | 219.9 | 218.7 | 219.3 | n/a (non-monotone) | 0.30 | 0.15 | PASS |
| pry | 401.1 | 401.0 | 399.1 | 394.9 | 395.3 | 394.3 | 394.8 | n/a (non-monotone) | 1.09 | 1.56 | PASS |
| ring pull | 9358.7 | 9329.2 | 9410.6 | 9340.6 | 9368.6 | 9021.0 | 9194.8 | n/a (non-monotone) | 2.35 | 1.46 | PASS |

nodes per level: 1721, 2005, 2791, 5843, 9323, 17914; solve s: 0.15, 0.23, 0.21, 0.92, 1.99, 7.41; lateral peak at (-74.9, -7.7) = ricasso; ring-pull peak per level: (-90.0,-69.0) grip-ring neck; (-71.6,-69.0) grip-ring neck; (-90.1,-69.2) ring; (-71.5,-69.2) ring; (-89.9,-68.8) grip-ring neck; (-71.7,-68.8) grip-ring neck

Knife convergence gate (lateral + ring pull on every design): **PASS**

