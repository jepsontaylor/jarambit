#!/bin/bash
# post_wave_hook.sh N RUN_DIR [SOLVER_DESC]
# Evolve post-hook: write the WAVE REPORT pack for wave N from a finished crescent-evolve / crescent-d1 output dir
# (plates.txt + <label>.json plate JSONs + certification.csv + report.md). Run from the repo root of a checkout
# that has ops/wave_reports/ (xbabe2: ~/jarambit/.agent/worktrees/exec-wave-reports).
# env: WAVE_REPORT_COMMIT=1 -> git add/commit/push docs/wave_reports/waveN_* on the current branch
#      COPY_TO=<dir>        -> also copy the pack there
# Wire into a run script AFTER the evolve command, e.g.  ... crescent-evolve --out $S ...; ops/wave_reports/post_wave_hook.sh 18 $S
set -uo pipefail
N=$1; RUN=$2; SOLVER=${3:-"$(git rev-parse --short HEAD 2>/dev/null)+$(git diff --quiet 2>/dev/null && echo clean || echo dirty)"}
OUT=docs/wave_reports; P=$((N-1))
args=(--wave "$N" --d1-dir "$RUN" --pre-dir "$RUN" --out "$OUT" --solver-commit "$SOLVER" --signoff-dir "$OUT/signoff" --run-label "$RUN")
[ -f "$OUT/wave${P}_paper_data.json" ] && args+=(--prior-pack "$OUT/wave${P}_paper_data.json")
[ -n "${COPY_TO:-}" ] && args+=(--copy-to "$COPY_TO")
nice -n 19 python3 ops/wave_reports/make_wave_report.py "${args[@]}"; rc=$?
echo "post_wave_hook wave$N rc=$rc $(date -u +%FT%TZ)" >> "$OUT/HOOK_LOG.txt"
if [ "${WAVE_REPORT_COMMIT:-0}" = 1 ] && [ $rc = 0 ]; then
  git add "$OUT"/wave${N}_* "$OUT/HOOK_LOG.txt"
  git commit -q -m "wave reports: wave$N auto pack (D1 rules; NOT promoted; aesthetic sign-off pending) (author Jepson Taylor)" && \
  { git pull -q --rebase origin "$(git rev-parse --abbrev-ref HEAD)" 2>/dev/null; git push -q origin HEAD; }
fi
exit $rc
