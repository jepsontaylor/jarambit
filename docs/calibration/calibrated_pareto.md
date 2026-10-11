# First calibrated legal Pareto (merged over 4 runs)

Non-dominated over mass (lower) and search-robust lateral (higher) across runs out/cal_t6/s21..s24. Every member is LEGAL: red-team clean, blade >= 3.375 in (85.725 mm) on tip-heel, reach and arc, calibrated robust floors 180/260/1500 N in the search, AND the converged verification mesh (0.25 mm^2) clears 180/260/1500 N at 100 C. Ti-6Al-4V throughout. SF = verify-mesh capacity at 100 C / floor. Exploratory stock ceiling JARAMBIT_T_MAX=6.0 (default 4.5, see CALIBRATION.md 6).

| # | run/rank | mass g | t mm | robust lat N | SPG robust N/g | SPG verify 100C N/g | tip-heel / reach / arc mm | (in) | lateral -10/20/100 C N | ring 100C N | SF hiker / hunter / ring @100C | peak | neck flare/len/fillet mm | grip mm | svg | STL/STEP (xbabe2 worktree) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | s23/r0 | 56.04 | 5.3 | 262 | 4.675 | 5.029 | 87.8 / 87.5 / 99.3 | 3.456 / 3.445 / 3.911 | 319 / 309 / 282 | 8647 | 1.57 / 1.08 / 5.76 | blade | 2.1 / 12.2 / 9.2 | 61.5 | [svg](pareto/t6_s23_rank00_m56.0g.svg) | `out/cal_t6/s23/pareto/rank00_m56.0g.stl` `.step` |
| 2 | s21/r1 | 56.70 | 5.4 | 262 | 4.623 | 5.134 | 87.0 / 87.2 / 98.3 | 3.426 / 3.433 / 3.872 | 330 / 319 / 291 | 7505 | 1.62 / 1.12 / 5.00 | ricasso | 1.6 / 10.9 / 4.6 | 61.2 | [svg](pareto/t6_s21_rank01_m56.7g.svg) | `out/cal_t6/s21/pareto/rank01_m56.7g.stl` `.step` |
| 3 | s23/r1 | 56.73 | 5.3 | 263 | 4.632 | 5.011 | 86.9 / 87.3 / 98.6 | 3.422 / 3.439 / 3.883 | 322 / 312 / 284 | 9315 | 1.58 / 1.09 / 6.21 | ricasso | 1.8 / 14.8 / 8.6 | 62.0 | [svg](pareto/t6_s23_rank01_m56.7g.svg) | `out/cal_t6/s23/pareto/rank01_m56.7g.stl` `.step` |
| 4 | s23/r2 | 56.94 | 5.3 | 272 | 4.775 | 5.105 | 86.5 / 87.3 / 98.1 | 3.407 / 3.438 / 3.864 | 329 / 319 / 291 | 8022 | 1.61 / 1.12 / 5.35 | blade | 1.1 / 14.7 / 8.2 | 62.9 | [svg](pareto/t6_s23_rank02_m56.9g.svg) | `out/cal_t6/s23/pareto/rank02_m56.9g.stl` `.step` |
| 5 | s23/r3 | 57.31 | 5.4 | 279 | 4.873 | 5.329 | 87.2 / 86.8 / 99.1 | 3.432 / 3.416 / 3.900 | 346 / 335 / 305 | 8725 | 1.70 / 1.17 / 5.82 | ricasso | 1.2 / 15.0 / 9.3 | 62.0 | [svg](pareto/t6_s23_rank03_m57.3g.svg) | `out/cal_t6/s23/pareto/rank03_m57.3g.stl` `.step` |
| 6 | s21/r5 | 57.48 | 5.4 | 280 | 4.862 | 5.179 | 87.9 / 88.2 / 99.2 | 3.459 / 3.471 / 3.904 | 337 / 326 / 298 | 7409 | 1.65 / 1.15 / 4.94 | blade | 1.5 / 13.2 / 5.2 | 62.1 | [svg](pareto/t6_s21_rank05_m57.5g.svg) | `out/cal_t6/s21/pareto/rank05_m57.5g.stl` `.step` |
| 7 | s24/r3 | 58.16 | 5.5 | 283 | 4.865 | 5.253 | 86.6 / 87.5 / 100.1 | 3.409 / 3.445 / 3.941 | 346 / 335 / 306 | 8270 | 1.70 / 1.18 / 5.51 | ricasso | 0.3 / 21.7 / 9.5 | 61.6 | [svg](pareto/t6_s24_rank03_m58.2g.svg) | `out/cal_t6/s24/pareto/rank03_m58.2g.stl` `.step` |
| 8 | s23/r4 | 58.36 | 5.5 | 286 | 4.894 | 5.298 | 86.6 / 86.6 / 98.1 | 3.408 / 3.411 / 3.861 | 350 / 339 / 309 | 9578 | 1.72 / 1.19 / 6.39 | ricasso | 2.4 / 13.3 / 9.6 | 61.8 | [svg](pareto/t6_s23_rank04_m58.4g.svg) | `out/cal_t6/s23/pareto/rank04_m58.4g.stl` `.step` |
| 9 | s23/r5 | 58.37 | 5.5 | 290 | 4.964 | 5.319 | 86.8 / 87.3 / 98.5 | 3.419 / 3.438 / 3.878 | 352 / 340 / 310 | 8413 | 1.73 / 1.19 / 5.61 | ricasso | 0.4 / 13.8 / 8.6 | 61.3 | [svg](pareto/t6_s23_rank05_m58.4g.svg) | `out/cal_t6/s23/pareto/rank05_m58.4g.stl` `.step` |
| 10 | s23/r6 | 59.02 | 5.5 | 290 | 4.923 | 5.212 | 86.8 / 87.5 / 98.3 | 3.415 / 3.443 / 3.869 | 348 / 337 / 308 | 8141 | 1.71 / 1.18 / 5.43 | blade | 0.8 / 13.7 / 7.7 | 61.8 | [svg](pareto/t6_s23_rank06_m59.0g.svg) | `out/cal_t6/s23/pareto/rank06_m59.0g.stl` `.step` |
| 11 | s23/r7 | 59.16 | 5.5 | 292 | 4.928 | 5.412 | 87.7 / 87.2 / 99.5 | 3.451 / 3.431 / 3.918 | 363 / 351 / 320 | 9316 | 1.78 / 1.23 / 6.21 | ricasso | 1.2 / 12.8 / 9.6 | 61.6 | [svg](pareto/t6_s23_rank07_m59.2g.svg) | `out/cal_t6/s23/pareto/rank07_m59.2g.stl` `.step` |
| 12 | s21/r8 | 59.46 | 5.6 | 299 | 5.027 | 5.325 | 88.3 / 86.7 / 100.0 | 3.477 / 3.415 / 3.936 | 359 / 347 / 317 | 8496 | 1.76 / 1.22 / 5.66 | blade | 2.9 / 11.5 / 4.8 | 61.0 | [svg](pareto/t6_s21_rank08_m59.5g.svg) | `out/cal_t6/s21/pareto/rank08_m59.5g.stl` `.step` |
| 13 | s24/r6 | 59.96 | 5.7 | 307 | 5.117 | 5.684 | 86.4 / 87.3 / 100.8 | 3.402 / 3.437 / 3.970 | 386 / 374 / 341 | 9077 | 1.89 / 1.31 / 6.05 | ricasso | 0.5 / 20.4 / 10.0 | 60.9 | [svg](pareto/t6_s24_rank06_m60.0g.svg) | `out/cal_t6/s24/pareto/rank06_m60.0g.stl` `.step` |
| 14 | s24/r7 | 60.07 | 5.6 | 308 | 5.123 | 5.477 | 86.7 / 87.5 / 100.9 | 3.414 / 3.446 / 3.974 | 373 / 361 / 329 | 8987 | 1.83 / 1.26 / 5.99 | ricasso | 0.5 / 21.2 / 9.4 | 61.0 | [svg](pareto/t6_s24_rank07_m60.1g.svg) | `out/cal_t6/s24/pareto/rank07_m60.1g.stl` `.step` |
| 15 | s21/r11 | 61.29 | 5.7 | 312 | 5.085 | 5.496 | 86.8 / 86.7 / 97.0 | 3.419 / 3.414 / 3.820 | 382 / 369 / 337 | 8750 | 1.87 / 1.30 / 5.83 | ricasso | 2.1 / 10.0 / 5.8 | 62.9 | [svg](pareto/t6_s21_rank11_m61.3g.svg) | `out/cal_t6/s21/pareto/rank11_m61.3g.stl` `.step` |
| 16 | s21/r12 | 61.37 | 5.8 | 312 | 5.079 | 5.650 | 87.2 / 87.7 / 98.6 | 3.433 / 3.453 / 3.882 | 393 / 380 / 347 | 8607 | 1.93 / 1.33 / 5.74 | grip | 1.9 / 10.5 / 5.9 | 61.1 | [svg](pareto/t6_s21_rank12_m61.4g.svg) | `out/cal_t6/s21/pareto/rank12_m61.4g.stl` `.step` |
| 17 | s24/r8 | 61.57 | 5.8 | 320 | 5.204 | 5.674 | 86.5 / 87.2 / 101.1 | 3.405 / 3.432 / 3.982 | 396 / 383 / 349 | 9720 | 1.94 / 1.34 / 6.48 | ricasso | 0.4 / 21.4 / 10.0 | 61.1 | [svg](pareto/t6_s24_rank08_m61.6g.svg) | `out/cal_t6/s24/pareto/rank08_m61.6g.stl` `.step` |
| 18 | s24/r9 | 62.22 | 5.8 | 332 | 5.335 | 5.750 | 87.1 / 87.2 / 100.9 | 3.431 / 3.433 / 3.972 | 405 / 392 / 358 | 9295 | 1.99 / 1.38 / 6.20 | blade | 0.6 / 20.1 / 9.9 | 61.0 | [svg](pareto/t6_s24_rank09_m62.2g.svg) | `out/cal_t6/s24/pareto/rank09_m62.2g.stl` `.step` |
| 19 | s21/r19 | 63.58 | 6.0 | 332 | 5.229 | 5.597 | 88.4 / 87.3 / 100.2 | 3.480 / 3.437 / 3.943 | 403 / 390 / 356 | 8632 | 1.98 / 1.37 / 5.75 | blade | 2.5 / 14.0 / 5.3 | 62.1 | [svg](pareto/t6_s21_rank19_m63.6g.svg) | `out/cal_t6/s21/pareto/rank19_m63.6g.stl` `.step` |
| 20 | s24/r11 | 64.20 | 6.0 | 333 | 5.189 | 5.883 | 87.2 / 86.9 / 99.2 | 3.435 / 3.420 / 3.907 | 428 / 414 / 378 | 9786 | 2.10 / 1.45 / 6.52 | blade | 0.6 / 20.9 / 10.0 | 61.0 | [svg](pareto/t6_s24_rank11_m64.2g.svg) | `out/cal_t6/s24/pareto/rank11_m64.2g.stl` `.step` |
| 21 | s24/r12 | 64.35 | 6.0 | 346 | 5.377 | 5.812 | 86.6 / 87.5 / 100.7 | 3.408 / 3.446 / 3.966 | 424 / 410 / 374 | 9889 | 2.08 / 1.44 / 6.59 | ricasso | 0.5 / 21.7 / 9.3 | 62.1 | [svg](pareto/t6_s24_rank12_m64.4g.svg) | `out/cal_t6/s24/pareto/rank12_m64.4g.stl` `.step` |
| 22 | s24/r13 | 64.62 | 6.0 | 350 | 5.421 | 5.886 | 87.0 / 86.7 / 100.8 | 3.424 / 3.412 / 3.969 | 431 / 417 / 380 | 9125 | 2.11 / 1.46 / 6.08 | ricasso | 0.3 / 20.5 / 10.0 | 63.2 | [svg](pareto/t6_s24_rank13_m64.6g.svg) | `out/cal_t6/s24/pareto/rank13_m64.6g.stl` `.step` |
| 23 | s24/r14 | 64.67 | 6.0 | 350 | 5.421 | 5.844 | 86.8 / 87.8 / 101.3 | 3.416 / 3.457 / 3.988 | 428 / 414 / 378 | 9711 | 2.10 / 1.45 / 6.47 | ricasso | 0.5 / 20.5 / 9.3 | 62.6 | [svg](pareto/t6_s24_rank14_m64.7g.svg) | `out/cal_t6/s24/pareto/rank14_m64.7g.stl` `.step` |

## Default stock ceiling (t <= 4.5 mm): no legal design

Four seeded calibrated runs (out/cal1/s11..s14) used pop 48 x 2 islands, 50 generations and MC 1000 each. They were seeded from the smoke_legal_blade checkpoint plus the SWITCHBACK reference genome with a reinforced neck. All four plateaued at a calibrated robust lateral of 191-202 N (the best was 201 N at 52.9 g), and every run ended pinned at t = 4.5 mm. The hiker floor of 180 N clears; the hunter floor of 260 N does not. The result: **0 LEGAL at t <= 4.5 mm.**

The neck genes did their job: on the detailed plate the peak left the grip-ring neck and moved to the grip body, ricasso shoulder or blade root. The remaining limit is section modulus. The holder fixes the handle width at 14 - 2*shoulder_w <= 12.4 mm, and the all-three blade floor fixes the lever arm, so lateral capacity scales with t^2. Clearing 260 N robust at 100 C needs about 5.2 mm of stock, and the legal fronts start at t = 5.3 mm. Per-generation histories are in `runs/t45_s*_history.csv`.

## Runs

| run | stock ceiling | legal front members | best SPG robust N/g (mass, t) |
|---|---|---|---|
| cal1 s11-s14 | 4.5 mm | 0, 0, 0, 0 | none (robust lat <= 202 N) |
| cal_t6 s21 | 6.0 mm | 20 | 5.229 (63.6 g, 6.0 mm) |
| cal_t6 s22 | 6.0 mm | 10 | 4.845 (61.0 g, 5.6 mm) |
| cal_t6 s23 | 6.0 mm | 17 | 5.187 (64.1 g) |
| cal_t6 s24 | 6.0 mm | 15 | 5.421 (64.6 g, 6.0 mm) |
