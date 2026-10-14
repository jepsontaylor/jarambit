#!/bin/bash
# README hero: ~13 s highlight (whole object, serration macro, science spin mesh->field) as a looping animated WebP < 10 MB.
# make_readme_hero.sh FILM.mp4 OUT.webp [width]
set -euo pipefail
IN=$1; OUT=$2; W=${3:-720}
ffmpeg -v error -y -i "$IN" -filter_complex \
"[0:v]trim=0.5:3.5,setpts=PTS-STARTPTS[a];[0:v]trim=3.0:6.0,setpts=PTS-STARTPTS[b];[0:v]trim=11.6:18.6,setpts=PTS-STARTPTS[c];\
[a][b][c]concat=n=3:v=1,fps=15,scale=${W}:-2:flags=lanczos[v]" -map "[v]" -c:v libwebp -lossless 0 -q:v 62 -compression_level 6 -loop 0 -an "$OUT"
ls -l "$OUT"
