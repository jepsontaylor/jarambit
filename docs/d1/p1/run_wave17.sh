#!/bin/bash
cd ~/jarambit_d1p1
S=out/wave17_p1
export JARAMBIT_P1=1 JARAMBIT_P1_SFMAP=$S/sfmap_wave14_c03.txt JARAMBIT_MAX_THREADS=40 JARAMBIT_T_MAX=6.0 JARAMBIT_MASS_CAP=77 JARAMBIT_CERT_STRICT=1
exec nice -n 19 $S/jarambit_wave17.bin crescent-evolve --out $S --wave wave17 --islands 8 --pop 48 --gens 160 --threads 40 --seed 1717 --area 2.0 --seeds $S/wave14_c03_genome.csv,$S/wave13_c01_genome.csv --seed-top 1 --migrate 6 --kick 0.5 --cert 16 > out/wave17_p1.log 2>&1
