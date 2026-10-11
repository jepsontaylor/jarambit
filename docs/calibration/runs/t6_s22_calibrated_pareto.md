# Calibrated Pareto (detailed-plate verification)

Search fitness: detailed plate at 2 mm^2 / mesh bias 1.070, times MC p05/nominal, min with 100 C nominal; floors 180/260/1500 N hard. Verification: detailed plate at 0.25 mm^2 (converged), no knock-down, yield at -10/20/100 C. SF = capacity / floor. LEGAL = red-team clean (blade >= 3.375 in on all three + every gate) AND search-robust floors AND verify-mesh floors at 100 C.

| rank | legal | mass g | SPG robust N/g | SPG verify 100C N/g | t mm | tip-heel / reach / arc mm (in) | lateral -10/20/100 C N | ring 100C N | SF hiker / hunter / ring @100C | peak | neck flare/len/fillet mm | files |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | LEGAL | 57.55 | 4.571 | 4.997 | 5.3 | 87.2 / 86.7 / 99.8 (3.434 / 3.415 / 3.927) | 326 / 315 / 288 | 8663 | 1.60 / 1.11 / 5.78 | grip | 3.6 / 14.6 / 4.4 | `out/cal_t6/s22/pareto/rank00_m57.6g.stl` `.step` `.svg` |
| 1 | LEGAL | 58.64 | 4.649 | 5.014 | 5.3 | 88.3 / 87.4 / 101.0 (3.475 / 3.443 / 3.975) | 333 / 322 / 294 | 8436 | 1.63 / 1.13 / 5.62 | grip | 4.0 / 15.6 / 3.0 | `out/cal_t6/s22/pareto/rank01_m58.6g.stl` `.step` `.svg` |
| 2 | LEGAL | 59.64 | 4.673 | 5.011 | 5.4 | 87.3 / 88.4 / 98.9 (3.436 / 3.481 / 3.895) | 339 / 328 / 299 | 9497 | 1.66 / 1.15 / 6.33 | ricasso | 3.1 / 22.0 / 7.2 | `out/cal_t6/s22/pareto/rank02_m59.6g.stl` `.step` `.svg` |
| 3 | LEGAL | 60.25 | 4.634 | 5.110 | 5.5 | 88.8 / 88.4 / 100.5 (3.494 / 3.481 / 3.957) | 349 / 338 / 308 | 9401 | 1.71 / 1.18 / 6.27 | ricasso | 3.6 / 14.0 / 5.0 | `out/cal_t6/s22/pareto/rank03_m60.3g.stl` `.step` `.svg` |
| 4 | LEGAL | 60.35 | 4.827 | 5.135 | 5.5 | 86.9 / 87.5 / 98.1 (3.421 / 3.445 / 3.863) | 351 / 340 / 310 | 6998 | 1.72 / 1.19 / 4.67 | blade | 3.6 / 17.1 / 1.8 | `out/cal_t6/s22/pareto/rank04_m60.3g.stl` `.step` `.svg` |
| 5 | LEGAL | 61.00 | 4.845 | 5.307 | 5.6 | 87.1 / 88.2 / 98.0 (3.429 / 3.472 / 3.858) | 367 / 355 / 324 | 5160 | 1.80 / 1.25 / 3.44 | ricasso | 2.6 / 17.6 / 1.2 | `out/cal_t6/s22/pareto/rank05_m61.0g.stl` `.step` `.svg` |
| 6 | LEGAL | 61.86 | 4.797 | 4.984 | 5.5 | 86.7 / 86.7 / 97.9 (3.413 / 3.414 / 3.855) | 349 / 338 / 308 | 9035 | 1.71 / 1.19 / 6.02 | blade | 3.8 / 17.4 / 2.6 | `out/cal_t6/s22/pareto/rank06_m61.9g.stl` `.step` `.svg` |
| 7 | LEGAL | 63.57 | 4.709 | 5.167 | 5.6 | 87.2 / 87.2 / 98.3 (3.435 / 3.435 / 3.871) | 372 / 360 / 328 | 8860 | 1.82 / 1.26 / 5.91 | ricasso | 3.4 / 15.4 / 3.0 | `out/cal_t6/s22/pareto/rank07_m63.6g.stl` `.step` `.svg` |
| 8 | LEGAL | 63.71 | 4.699 | 4.856 | 5.6 | 87.1 / 87.2 / 99.7 (3.429 / 3.432 / 3.926) | 350 / 339 / 309 | 6840 | 1.72 / 1.19 / 4.56 | blade | 3.0 / 15.7 / 1.3 | `out/cal_t6/s22/pareto/rank08_m63.7g.stl` `.step` `.svg` |
| 9 | LEGAL | 64.87 | 4.700 | 5.091 | 5.6 | 86.9 / 87.2 / 97.8 (3.421 / 3.435 / 3.852) | 374 / 362 / 330 | 7738 | 1.83 / 1.27 / 5.16 | blade | 4.3 / 17.6 / 1.5 | `out/cal_t6/s22/pareto/rank09_m64.9g.stl` `.step` `.svg` |

10 of 10 front members LEGAL on the verification mesh.
