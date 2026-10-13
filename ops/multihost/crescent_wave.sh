#!/bin/bash
# Multi-host crescent-evolve launcher (early piece of the v0.35 runner). Run from the controller.
# usage: crescent_wave.sh WAVE ENVFILE SEEDS_CSV "host:threads:seed ..." [gens] [pop] [islands]
#   one nice'd crescent-evolve per spec on the named host (ssh ubuntu@host), in $REMOTE_DIR (default ~/jarambit),
#   distinct seed per job, cap-free fitness (PR-0.31.2; no mass cap), lineage in <out>/evidence.jevl (PR-0.29.1).
#   Out dir: out/<WAVE>_<host>_cap<cap>_s<seed>. Collect with ops/multihost/collect_cert.py.
set -euo pipefail
WAVE=$1; ENVF=$2; SEEDS=$3; SPECS=$4; GENS=${5:-60}; POP=${6:-64}; ISL=${7:-4}
REMOTE_DIR=${REMOTE_DIR:-'~/jarambit'}; USER_AT=${SSH_USER:-ubuntu}
ENVS=$(grep -v '^\s*#' "$ENVF" | grep '=' | tr '\n' ' ')
for spec in $SPECS; do
  IFS=: read -r H T SEED _ <<< "$spec"
  OUT=out/${WAVE}_${H}_s${SEED}
  ssh -o ConnectTimeout=5 "$USER_AT@$H" "cd $REMOTE_DIR && mkdir -p $OUT && (env -u JARAMBIT_P1 -u JARAMBIT_MASS_CAP $ENVS JARAMBIT_MAX_THREADS=$T nohup nice -n 10 ./target/release/jarambit crescent-evolve --out $OUT --wave $WAVE --pop $POP --islands $ISL --gens $GENS --threads $T --seed $SEED --seeds $SEEDS --seed-top 24 --migrate 5 > $OUT/run.log 2>&1 &)" \
    && echo "started $H $OUT (threads $T)" || echo "FAILED to start on $H (unreachable?)" >&2
done
