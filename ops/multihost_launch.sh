#!/bin/bash
# Usage: multihost_launch.sh <host_tag> <run> <threads_per_proc> "<seed:mc> <seed:mc> ..." [gens] [pop] [islands]
# Starts one nice-19 jarambit island-GA process per seed (independent island group), each in its own screen.
# JARAMBIT_FEM=1 in the environment is forwarded (mh2). mh1 leaves it unset.
set -e
TAG=$1; RUN=$2; T=$3; SPECS=$4; GENS=${5:-60}; POP=${6:-48}; ISL=${7:-2}
BIN=${BIN:-$HOME/jarambit/target/release/jarambit}; OUTROOT=${OUTROOT:-$HOME/jarambit/out/$RUN}
FEM=""
if [ "${JARAMBIT_FEM:-0}" = "1" ]; then FEM="JARAMBIT_FEM=1"; fi
mkdir -p "$OUTROOT"
for spec in $SPECS; do
  seed=${spec%%:*}; mc=${spec##*:}; out="$OUTROOT/${TAG}_s${seed}"; mkdir -p "$out"
  name="jarambit_${RUN}_${TAG}_s${seed}"
  screen -dmS "$name" bash -c "cd '$out' && $FEM JARAMBIT_MAX_THREADS=$T MIMALLOC_PURGE_DELAY=-1 exec nice -n 19 '$BIN' --gens $GENS --pop $POP --mc $mc --threads $T --islands $ISL --migrate 5 --seed $seed --out '$out' > '$out/run.log' 2>&1"
  echo "started $name  (threads=$T mc=$mc gens=$GENS pop=$POP islands=$ISL fem=${JARAMBIT_FEM:-0}) -> $out"
done
pgrep -u "$(id -u)" -f yield_guard.sh >/dev/null || screen -dmS jarambit_yield_guard bash "$(dirname "$0")/yield_guard.sh"
