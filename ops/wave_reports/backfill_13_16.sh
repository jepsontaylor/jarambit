#!/bin/bash
# Backfill WAVE REPORT packs for wave13-16 from existing D1 collect + pre-D1 lattice records (xbabe2 worktrees).
set -euo pipefail
WT=$HOME/jarambit/.agent/worktrees
R=$WT/exec-wave-reports
D1=$WT/exec-d1
LAT=$WT/exec-lattice
cd "$R"
DIFFH=$(git -C "$D1" diff | sha256sum | cut -c1-12)
BIN_T=$(date -u -r "$D1/target_d1/release/jarambit" +%Y-%m-%dT%H:%M:%SZ)
SOLVER="exec/d1@$(git -C "$D1" rev-parse --short HEAD)+dirty(P1 diff sha256:$DIFFH) target_d1 built $BIN_T"
COLLECT=$D1/out/d1_w15w16_collect
P0CSV=$D1/docs/d1/d1_rescreen_p0.csv
OUT=docs/wave_reports
COPY=${COPY_TO:-}
declare -A PRE=( [12]=wave12_through [13]=wave13_c6 [14]=wave14_c6_through [15]=wave15_c6_long [16]=wave16_c6_through4 )
for N in 13 14 15 16; do
  P=$((N-1)); args=()
  if [ -f "$OUT/wave${P}_paper_data.json" ]; then args+=(--prior-pack "$OUT/wave${P}_paper_data.json"); else args+=(--prior-pre-dir "$LAT/docs/lattice/${PRE[$P]}"); fi
  [ -n "$COPY" ] && args+=(--copy-to "$COPY")
  python3 ops/wave_reports/make_wave_report.py --wave $N --d1-dir "$COLLECT" --d1-csv "$P0CSV" \
     --pre-dir "$LAT/docs/lattice/${PRE[$N]}" --out "$OUT" --solver-commit "$SOLVER" \
     --signoff-dir "$OUT/signoff" --run-label "${PRE[$N]} (pre-D1 run) re-screened by crescent-d1 (D1 rules)" "${args[@]}"
done
