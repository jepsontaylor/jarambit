# Calibrated Pareto (detailed-plate verification)

Search fitness: detailed plate at 2 mm^2 / mesh bias 1.070, times MC p05/nominal, min with 100 C nominal; floors 180/260/1500 N hard. Verification: detailed plate at 0.25 mm^2 (converged), no knock-down, yield at -10/20/100 C. SF = capacity / floor. LEGAL = red-team clean (blade >= 3.375 in on all three + every gate) AND search-robust floors AND verify-mesh floors at 100 C.

| rank | legal | mass g | SPG robust N/g | SPG verify 100C N/g | t mm | tip-heel / reach / arc mm (in) | lateral -10/20/100 C N | ring 100C N | SF hiker / hunter / ring @100C | peak | neck flare/len/fillet mm | files |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | LEGAL | 56.65 | 4.610 | 4.966 | 5.3 | 88.6 / 86.9 / 99.0 (3.486 / 3.420 / 3.899) | 319 / 308 / 281 | 7113 | 1.56 / 1.08 / 4.74 | blade | 1.7 / 13.3 / 4.4 | `out/cal_t6/s21/pareto/rank00_m56.7g.stl` `.step` `.svg` |
| 1 | LEGAL | 56.70 | 4.623 | 5.134 | 5.4 | 87.0 / 87.2 / 98.4 (3.426 / 3.433 / 3.872) | 330 / 319 / 291 | 7505 | 1.62 / 1.12 / 5.00 | ricasso | 1.7 / 10.9 / 4.6 | `out/cal_t6/s21/pareto/rank01_m56.7g.stl` `.step` `.svg` |
| 2 | LEGAL | 57.04 | 4.714 | 5.047 | 5.4 | 88.3 / 88.3 / 99.9 (3.476 / 3.475 / 3.934) | 326 / 316 / 288 | 7972 | 1.60 / 1.11 / 5.31 | blade | 2.5 / 9.6 / 4.3 | `out/cal_t6/s21/pareto/rank02_m57.0g.stl` `.step` `.svg` |
| 3 | LEGAL | 57.24 | 4.710 | 5.095 | 5.4 | 87.3 / 87.1 / 98.5 (3.436 / 3.429 / 3.878) | 330 / 320 / 292 | 8282 | 1.62 / 1.12 / 5.52 | blade | 1.8 / 13.7 / 4.7 | `out/cal_t6/s21/pareto/rank03_m57.2g.stl` `.step` `.svg` |
| 4 | LEGAL | 57.33 | 4.730 | 5.129 | 5.4 | 87.9 / 87.9 / 99.2 (3.462 / 3.460 / 3.906) | 333 / 322 / 294 | 7868 | 1.63 / 1.13 / 5.25 | grip | 1.6 / 13.1 / 5.1 | `out/cal_t6/s21/pareto/rank04_m57.3g.stl` `.step` `.svg` |
| 5 | LEGAL | 57.48 | 4.862 | 5.179 | 5.4 | 87.9 / 88.2 / 99.2 (3.459 / 3.471 / 3.904) | 337 / 326 / 298 | 7409 | 1.65 / 1.14 / 4.94 | blade | 1.5 / 13.2 / 5.2 | `out/cal_t6/s21/pareto/rank05_m57.5g.stl` `.step` `.svg` |
| 6 | LEGAL | 58.45 | 4.830 | 5.302 | 5.5 | 87.8 / 87.2 / 99.1 (3.456 / 3.434 / 3.900) | 351 / 340 / 310 | 7939 | 1.72 / 1.19 / 5.29 | blade | 2.0 / 8.5 / 5.5 | `out/cal_t6/s21/pareto/rank06_m58.4g.stl` `.step` `.svg` |
| 7 | LEGAL | 58.54 | 4.881 | 5.160 | 5.5 | 86.8 / 86.6 / 98.2 (3.419 / 3.409 / 3.868) | 342 / 331 / 302 | 8037 | 1.68 / 1.16 / 5.36 | blade | 2.0 / 13.2 / 5.2 | `out/cal_t6/s21/pareto/rank07_m58.5g.stl` `.step` `.svg` |
| 8 | LEGAL | 59.46 | 5.027 | 5.325 | 5.6 | 88.3 / 86.7 / 100.0 (3.477 / 3.415 / 3.936) | 359 / 347 / 317 | 8496 | 1.76 / 1.22 / 5.66 | blade | 2.9 / 11.5 / 4.8 | `out/cal_t6/s21/pareto/rank08_m59.5g.stl` `.step` `.svg` |
| 9 | LEGAL | 60.46 | 4.975 | 5.687 | 5.8 | 87.1 / 87.9 / 97.3 (3.431 / 3.461 / 3.833) | 390 / 377 / 344 | 7929 | 1.91 / 1.32 / 5.29 | ricasso | 2.7 / 12.4 / 4.8 | `out/cal_t6/s21/pareto/rank09_m60.5g.stl` `.step` `.svg` |
| 10 | LEGAL | 60.48 | 5.048 | 5.568 | 5.8 | 87.7 / 87.9 / 99.2 (3.453 / 3.461 / 3.907) | 381 / 369 / 337 | 8747 | 1.87 / 1.30 / 5.83 | ricasso | 2.2 / 10.7 / 5.6 | `out/cal_t6/s21/pareto/rank10_m60.5g.stl` `.step` `.svg` |
| 11 | LEGAL | 61.29 | 5.085 | 5.496 | 5.7 | 86.8 / 86.7 / 97.0 (3.419 / 3.414 / 3.820) | 382 / 369 / 337 | 8750 | 1.87 / 1.30 / 5.83 | ricasso | 2.1 / 10.0 / 5.8 | `out/cal_t6/s21/pareto/rank11_m61.3g.stl` `.step` `.svg` |
| 12 | LEGAL | 61.37 | 5.079 | 5.650 | 5.8 | 87.2 / 87.7 / 98.6 (3.433 / 3.453 / 3.882) | 393 / 380 / 347 | 8607 | 1.93 / 1.33 / 5.74 | grip | 1.9 / 10.5 / 5.9 | `out/cal_t6/s21/pareto/rank12_m61.4g.stl` `.step` `.svg` |
| 13 | LEGAL | 61.74 | 5.144 | 5.567 | 5.8 | 88.2 / 88.0 / 99.6 (3.471 / 3.464 / 3.920) | 389 / 377 / 344 | 8685 | 1.91 / 1.32 / 5.79 | grip | 2.2 / 9.7 / 5.5 | `out/cal_t6/s21/pareto/rank13_m61.7g.stl` `.step` `.svg` |
| 14 | LEGAL | 62.13 | 5.113 | 5.364 | 5.9 | 88.5 / 87.9 / 99.0 (3.485 / 3.460 / 3.898) | 377 / 365 / 333 | 9034 | 1.85 / 1.28 / 6.02 | blade | 2.6 / 14.5 / 5.9 | `out/cal_t6/s21/pareto/rank14_m62.1g.stl` `.step` `.svg` |
| 15 | LEGAL | 62.39 | 5.097 | 5.382 | 5.8 | 87.5 / 88.1 / 98.9 (3.446 / 3.469 / 3.893) | 380 / 368 / 336 | 9614 | 1.87 / 1.29 / 6.41 | blade | 2.5 / 11.3 / 5.6 | `out/cal_t6/s21/pareto/rank15_m62.4g.stl` `.step` `.svg` |
| 16 | LEGAL | 62.41 | 5.175 | 5.646 | 5.9 | 88.4 / 86.9 / 99.8 (3.482 / 3.420 / 3.930) | 399 / 386 / 352 | 9285 | 1.96 / 1.36 / 6.19 | ricasso | 2.6 / 10.0 / 5.9 | `out/cal_t6/s21/pareto/rank16_m62.4g.stl` `.step` `.svg` |
| 17 | LEGAL | 63.22 | 5.165 | 5.222 | 5.9 | 87.2 / 87.7 / 98.9 (3.433 / 3.454 / 3.892) | 374 / 362 / 330 | 9227 | 1.83 / 1.27 / 6.15 | blade | 2.2 / 11.1 / 6.3 | `out/cal_t6/s21/pareto/rank17_m63.2g.stl` `.step` `.svg` |
| 18 | LEGAL | 63.45 | 5.198 | 5.743 | 6.0 | 88.8 / 88.7 / 99.2 (3.496 / 3.493 / 3.906) | 413 / 400 / 364 | 8737 | 2.02 / 1.40 / 5.82 | ricasso | 2.7 / 14.0 / 5.5 | `out/cal_t6/s21/pareto/rank18_m63.5g.stl` `.step` `.svg` |
| 19 | LEGAL | 63.58 | 5.229 | 5.597 | 6.0 | 88.4 / 87.3 / 100.2 (3.480 / 3.437 / 3.943) | 403 / 390 / 356 | 8632 | 1.98 / 1.37 / 5.75 | blade | 2.5 / 14.0 / 5.3 | `out/cal_t6/s21/pareto/rank19_m63.6g.stl` `.step` `.svg` |

20 of 20 front members LEGAL on the verification mesh.
