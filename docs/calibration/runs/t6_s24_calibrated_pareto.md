# Calibrated Pareto (detailed-plate verification)

Search fitness: detailed plate at 2 mm^2 / mesh bias 1.070, times MC p05/nominal, min with 100 C nominal; floors 180/260/1500 N hard. Verification: detailed plate at 0.25 mm^2 (converged), no knock-down, yield at -10/20/100 C. SF = capacity / floor. LEGAL = red-team clean (blade >= 3.375 in on all three + every gate) AND search-robust floors AND verify-mesh floors at 100 C.

| rank | legal | mass g | SPG robust N/g | SPG verify 100C N/g | t mm | tip-heel / reach / arc mm (in) | lateral -10/20/100 C N | ring 100C N | SF hiker / hunter / ring @100C | peak | neck flare/len/fillet mm | files |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | LEGAL | 57.14 | 4.604 | 4.901 | 5.3 | 88.2 / 88.9 / 99.9 (3.471 / 3.499 / 3.932) | 317 / 307 / 280 | 8504 | 1.56 / 1.08 / 5.67 | blade | 2.7 / 13.8 / 6.2 | `out/cal_t6/s24/pareto/rank00_m57.1g.stl` `.step` `.svg` |
| 1 | LEGAL | 57.49 | 4.635 | 5.206 | 5.5 | 87.5 / 87.5 / 97.8 (3.444 / 3.444 / 3.850) | 339 / 328 / 299 | 7228 | 1.66 / 1.15 / 4.82 | blade | 0.0 / 19.7 / 7.3 | `out/cal_t6/s24/pareto/rank01_m57.5g.stl` `.step` `.svg` |
| 2 | LEGAL | 57.66 | 4.770 | 5.077 | 5.4 | 86.8 / 87.9 / 97.0 (3.418 / 3.459 / 3.820) | 332 / 321 / 293 | 8653 | 1.63 / 1.13 / 5.77 | ricasso | 0.3 / 15.8 / 8.0 | `out/cal_t6/s24/pareto/rank02_m57.7g.stl` `.step` `.svg` |
| 3 | LEGAL | 58.16 | 4.865 | 5.253 | 5.5 | 86.6 / 87.5 / 100.1 (3.409 / 3.445 / 3.941) | 346 / 335 / 306 | 8270 | 1.70 / 1.18 / 5.51 | ricasso | 0.3 / 21.7 / 9.5 | `out/cal_t6/s24/pareto/rank03_m58.2g.stl` `.step` `.svg` |
| 4 | LEGAL | 58.48 | 4.849 | 5.424 | 5.6 | 87.2 / 86.4 / 101.0 (3.431 / 3.403 / 3.976) | 359 / 348 / 317 | 8282 | 1.76 / 1.22 / 5.52 | grip | 0.3 / 19.8 / 8.3 | `out/cal_t6/s24/pareto/rank04_m58.5g.stl` `.step` `.svg` |
| 5 | LEGAL | 59.66 | 4.820 | 5.128 | 5.5 | 86.8 / 87.7 / 100.6 (3.416 / 3.451 / 3.961) | 347 / 335 / 306 | 9270 | 1.70 / 1.18 / 6.18 | blade | 0.1 / 15.4 / 9.3 | `out/cal_t6/s24/pareto/rank05_m59.7g.stl` `.step` `.svg` |
| 6 | LEGAL | 59.96 | 5.117 | 5.684 | 5.7 | 86.4 / 87.3 / 100.8 (3.402 / 3.437 / 3.970) | 386 / 374 / 341 | 9077 | 1.89 / 1.31 / 6.05 | ricasso | 0.5 / 20.4 / 10.0 | `out/cal_t6/s24/pareto/rank06_m60.0g.stl` `.step` `.svg` |
| 7 | LEGAL | 60.07 | 5.123 | 5.477 | 5.6 | 86.7 / 87.5 / 100.9 (3.414 / 3.446 / 3.974) | 373 / 361 / 329 | 8987 | 1.83 / 1.27 / 5.99 | ricasso | 0.5 / 21.2 / 9.4 | `out/cal_t6/s24/pareto/rank07_m60.1g.stl` `.step` `.svg` |
| 8 | LEGAL | 61.57 | 5.204 | 5.674 | 5.8 | 86.5 / 87.2 / 101.1 (3.405 / 3.432 / 3.982) | 396 / 383 / 349 | 9720 | 1.94 / 1.34 / 6.48 | ricasso | 0.4 / 21.4 / 10.0 | `out/cal_t6/s24/pareto/rank08_m61.6g.stl` `.step` `.svg` |
| 9 | LEGAL | 62.22 | 5.335 | 5.750 | 5.8 | 87.1 / 87.2 / 100.9 (3.431 / 3.433 / 3.972) | 405 / 392 / 358 | 9295 | 1.99 / 1.38 / 6.20 | blade | 0.6 / 20.1 / 9.9 | `out/cal_t6/s24/pareto/rank09_m62.2g.stl` `.step` `.svg` |
| 10 | LEGAL | 63.92 | 5.198 | 5.737 | 6.0 | 87.5 / 87.6 / 98.9 (3.443 / 3.447 / 3.894) | 415 / 402 / 367 | 8836 | 2.04 / 1.41 / 5.89 | grip | 0.3 / 20.7 / 8.6 | `out/cal_t6/s24/pareto/rank10_m63.9g.stl` `.step` `.svg` |
| 11 | LEGAL | 64.20 | 5.189 | 5.883 | 6.0 | 87.2 / 86.9 / 99.2 (3.435 / 3.420 / 3.907) | 428 / 414 / 378 | 9786 | 2.10 / 1.45 / 6.52 | blade | 0.6 / 20.9 / 10.0 | `out/cal_t6/s24/pareto/rank11_m64.2g.stl` `.step` `.svg` |
| 12 | LEGAL | 64.35 | 5.377 | 5.812 | 6.0 | 86.6 / 87.5 / 100.7 (3.408 / 3.446 / 3.966) | 424 / 410 / 374 | 9889 | 2.08 / 1.44 / 6.59 | ricasso | 0.5 / 21.7 / 9.3 | `out/cal_t6/s24/pareto/rank12_m64.4g.stl` `.step` `.svg` |
| 13 | LEGAL | 64.62 | 5.421 | 5.886 | 6.0 | 87.0 / 86.7 / 100.8 (3.424 / 3.412 / 3.969) | 431 / 417 / 380 | 9125 | 2.11 / 1.46 / 6.08 | ricasso | 0.3 / 20.5 / 10.0 | `out/cal_t6/s24/pareto/rank13_m64.6g.stl` `.step` `.svg` |
| 14 | LEGAL | 64.67 | 5.421 | 5.844 | 6.0 | 86.8 / 87.8 / 101.3 (3.416 / 3.457 / 3.988) | 428 / 414 / 378 | 9711 | 2.10 / 1.45 / 6.47 | ricasso | 0.5 / 20.5 / 9.3 | `out/cal_t6/s24/pareto/rank14_m64.7g.stl` `.step` `.svg` |

15 of 15 front members LEGAL on the verification mesh.
