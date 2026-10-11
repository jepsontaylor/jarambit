# Calibrated Pareto (detailed-plate verification)

Search fitness: detailed plate at 2 mm^2 / mesh bias 1.070, times MC p05/nominal, min with 100 C nominal; floors 180/260/1500 N hard. Verification: detailed plate at 0.25 mm^2 (converged), no knock-down, yield at -10/20/100 C. SF = capacity / floor. LEGAL = red-team clean (blade >= 3.375 in on all three + every gate) AND search-robust floors AND verify-mesh floors at 100 C.

| rank | legal | mass g | SPG robust N/g | SPG verify 100C N/g | t mm | tip-heel / reach / arc mm (in) | lateral -10/20/100 C N | ring 100C N | SF hiker / hunter / ring @100C | peak | neck flare/len/fillet mm | files |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | LEGAL | 56.04 | 4.675 | 5.029 | 5.3 | 87.8 / 87.5 / 99.3 (3.456 / 3.445 / 3.911) | 319 / 309 / 282 | 8647 | 1.57 / 1.08 / 5.76 | blade | 2.1 / 12.2 / 9.2 | `out/cal_t6/s23/pareto/rank00_m56.0g.stl` `.step` `.svg` |
| 1 | LEGAL | 56.73 | 4.632 | 5.011 | 5.3 | 86.9 / 87.3 / 98.6 (3.422 / 3.439 / 3.883) | 322 / 312 / 284 | 9315 | 1.58 / 1.09 / 6.21 | ricasso | 1.8 / 14.8 / 8.6 | `out/cal_t6/s23/pareto/rank01_m56.7g.stl` `.step` `.svg` |
| 2 | LEGAL | 56.94 | 4.775 | 5.105 | 5.3 | 86.5 / 87.3 / 98.1 (3.407 / 3.438 / 3.864) | 329 / 319 / 291 | 8022 | 1.61 / 1.12 / 5.35 | blade | 1.1 / 14.7 / 8.2 | `out/cal_t6/s23/pareto/rank02_m56.9g.stl` `.step` `.svg` |
| 3 | LEGAL | 57.31 | 4.873 | 5.329 | 5.4 | 87.2 / 86.8 / 99.1 (3.432 / 3.416 / 3.900) | 346 / 335 / 305 | 8725 | 1.70 / 1.17 / 5.82 | ricasso | 1.2 / 15.0 / 9.3 | `out/cal_t6/s23/pareto/rank03_m57.3g.stl` `.step` `.svg` |
| 4 | LEGAL | 58.36 | 4.894 | 5.298 | 5.5 | 86.6 / 86.6 / 98.1 (3.408 / 3.411 / 3.861) | 350 / 339 / 309 | 9578 | 1.72 / 1.19 / 6.39 | ricasso | 2.3 / 13.3 / 9.6 | `out/cal_t6/s23/pareto/rank04_m58.4g.stl` `.step` `.svg` |
| 5 | LEGAL | 58.37 | 4.964 | 5.319 | 5.5 | 86.8 / 87.3 / 98.5 (3.419 / 3.438 / 3.878) | 352 / 340 / 310 | 8413 | 1.72 / 1.19 / 5.61 | ricasso | 0.4 / 13.8 / 8.6 | `out/cal_t6/s23/pareto/rank05_m58.4g.stl` `.step` `.svg` |
| 6 | LEGAL | 59.02 | 4.923 | 5.212 | 5.5 | 86.8 / 87.5 / 98.3 (3.415 / 3.443 / 3.869) | 348 / 337 / 308 | 8141 | 1.71 / 1.18 / 5.43 | blade | 0.8 / 13.7 / 7.7 | `out/cal_t6/s23/pareto/rank06_m59.0g.stl` `.step` `.svg` |
| 7 | LEGAL | 59.16 | 4.928 | 5.412 | 5.5 | 87.7 / 87.2 / 99.5 (3.451 / 3.431 / 3.918) | 363 / 351 / 320 | 9316 | 1.78 / 1.23 / 6.21 | ricasso | 1.2 / 12.8 / 9.6 | `out/cal_t6/s23/pareto/rank07_m59.2g.stl` `.step` `.svg` |
| 8 | LEGAL | 59.78 | 4.885 | 5.349 | 5.5 | 87.0 / 88.3 / 98.7 (3.426 / 3.478 / 3.886) | 362 / 351 / 320 | 9117 | 1.78 / 1.23 / 6.08 | blade | 1.0 / 21.0 / 9.3 | `out/cal_t6/s23/pareto/rank08_m59.8g.stl` `.step` `.svg` |
| 9 | LEGAL | 60.62 | 4.914 | 5.342 | 5.7 | 88.0 / 89.0 / 99.2 (3.464 / 3.504 / 3.907) | 367 / 355 / 324 | 8517 | 1.80 / 1.25 / 5.68 | blade | 1.4 / 11.8 / 7.8 | `out/cal_t6/s23/pareto/rank09_m60.6g.stl` `.step` `.svg` |
| 10 | LEGAL | 60.69 | 5.043 | 5.508 | 5.7 | 87.2 / 86.6 / 99.0 (3.433 / 3.411 / 3.898) | 379 / 367 / 334 | 9397 | 1.86 / 1.29 / 6.26 | ricasso | 1.3 / 14.8 / 9.7 | `out/cal_t6/s23/pareto/rank10_m60.7g.stl` `.step` `.svg` |
| 11 | LEGAL | 60.98 | 5.031 | 5.352 | 5.7 | 87.5 / 88.3 / 98.9 (3.443 / 3.478 / 3.895) | 370 / 358 / 326 | 9126 | 1.81 / 1.26 / 6.08 | ricasso | 1.3 / 14.9 / 9.0 | `out/cal_t6/s23/pareto/rank11_m61.0g.stl` `.step` `.svg` |
| 12 | LEGAL | 61.11 | 5.026 | 5.297 | 5.7 | 87.2 / 87.2 / 98.6 (3.433 / 3.434 / 3.883) | 367 / 355 / 324 | 8886 | 1.80 / 1.24 / 5.92 | blade | 1.4 / 13.9 / 7.7 | `out/cal_t6/s23/pareto/rank12_m61.1g.stl` `.step` `.svg` |
| 13 | LEGAL | 61.66 | 5.010 | 5.284 | 5.7 | 87.7 / 88.6 / 99.0 (3.453 / 3.486 / 3.896) | 369 / 357 / 326 | 8622 | 1.81 / 1.25 / 5.75 | ricasso | 0.5 / 14.4 / 8.4 | `out/cal_t6/s23/pareto/rank13_m61.7g.stl` `.step` `.svg` |
| 14 | LEGAL | 62.20 | 5.122 | 5.584 | 5.8 | 87.0 / 87.7 / 98.4 (3.426 / 3.451 / 3.872) | 393 / 381 / 347 | 8897 | 1.93 / 1.34 / 5.93 | ricasso | 1.5 / 15.7 / 7.3 | `out/cal_t6/s23/pareto/rank14_m62.2g.stl` `.step` `.svg` |
| 15 | LEGAL | 63.35 | 5.177 | 5.779 | 5.9 | 86.8 / 87.3 / 98.3 (3.419 / 3.435 / 3.870) | 415 / 401 / 366 | 9186 | 2.03 / 1.41 / 6.12 | grip | 1.7 / 15.6 / 7.9 | `out/cal_t6/s23/pareto/rank15_m63.3g.stl` `.step` `.svg` |
| 16 | LEGAL | 64.06 | 5.187 | 5.520 | 5.8 | 86.7 / 87.2 / 98.2 (3.414 / 3.432 / 3.866) | 401 / 388 / 354 | 10719 | 1.96 / 1.36 / 7.15 | ricasso | 1.7 / 12.9 / 7.5 | `out/cal_t6/s23/pareto/rank16_m64.1g.stl` `.step` `.svg` |

17 of 17 front members LEGAL on the verification mesh.
