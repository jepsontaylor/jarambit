#!/bin/bash
# watch_remote_wave.sh N HOST REMOTE_LOG REMOTE_DIR [POLL_S]
# Runs on xbabe2 (screen). Waits until REMOTE_LOG on HOST contains an 'EXIT' line (written by the run's screen wrapper),
# pulls REMOTE_DIR (no binaries / STL / STEP) into out/waveN_remote/, then runs post_wave_hook.sh with commit+push.
# Read-only on the remote host: never signals or renices the run.
set -uo pipefail
N=$1; H=$2; LOG=$3; DIR=$4; POLL=${5:-180}
cd "$(dirname "$0")/../.."
ST=out/WATCH_wave${N}.txt; mkdir -p out
echo "watching wave$N on $H:$LOG since $(date -u +%FT%TZ)" > "$ST"
while true; do
  if ssh -o BatchMode=yes -o ConnectTimeout=10 "$H" "grep -q '^EXIT' $LOG" 2>/dev/null; then break; fi
  echo "poll $(date -u +%FT%TZ): $(ssh -o BatchMode=yes -o ConnectTimeout=10 "$H" "tail -1 $LOG" 2>/dev/null | cut -c1-120)" >> "$ST"
  sleep "$POLL"
done
L=out/wave${N}_remote; mkdir -p "$L"
rsync -a --exclude '*.bin' --exclude '*.stl' --exclude '*.step' "$H:$DIR/" "$L/"
EXITLINE=$(ssh -o BatchMode=yes "$H" "grep '^EXIT' $LOG | tail -1")
BINSHA=$(ssh -o BatchMode=yes "$H" "sha256sum $DIR/*.bin 2>/dev/null | head -1 | cut -c1-12")
SOLVER="wave$N binary sha256:${BINSHA:-NV} on $H (exec/d1 P1 snapshot); run $EXITLINE"
echo "finished: $EXITLINE at $(date -u +%FT%TZ); generating pack" >> "$ST"
WAVE_REPORT_COMMIT=1 bash ops/wave_reports/post_wave_hook.sh "$N" "$L" "$SOLVER" >> "$ST" 2>&1
echo "DONE $(date -u +%FT%TZ)" >> "$ST"
