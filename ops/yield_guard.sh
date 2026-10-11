#!/bin/bash
# jarambit yield guard: pause OUR jarambit procs (SIGSTOP) when host CPU 30s avg >= PAUSE%, resume <= RESUME%.
# Keeps us below the JopeDime cpu_safety_guard (pauses its campaign at 88%). Only ever signals processes
# whose exe is a jarambit binary owned by this user. Never touches flywheel/rlfw/jopedime/tabpfn.
PAUSE=${PAUSE:-82}; RESUME=${RESUME:-72}; WIN=${WIN:-30}; LOG=${LOG:-$HOME/jarambit_yield.log}
paused=0
snap(){ awk '/^cpu /{i=$5+$6; t=0; for(k=2;k<=NF;k++) t+=$k; print t, i}' /proc/stat; }
ours(){ for p in $(pgrep -u "$(id -u)" -f 'target/release/jarambit '); do r=$(readlink /proc/$p/exe 2>/dev/null); [[ "$r" == */target/release/jarambit ]] && echo $p; done; }
trap 'kill -CONT $(ours) 2>/dev/null; exit 0' INT TERM
while true; do
  read t0 i0 < <(snap); sleep "$WIN"; read t1 i1 < <(snap)
  busy=$(( 100 * ( (t1-t0) - (i1-i0) ) / (t1-t0 > 0 ? t1-t0 : 1) ))
  if (( paused == 0 && busy >= PAUSE )); then kill -STOP $(ours) 2>/dev/null; paused=1; echo "$(date -u +%FT%TZ) busy=$busy% PAUSE $(ours|tr '\n' ' ')" >> "$LOG"
  elif (( paused == 1 && busy <= RESUME )); then kill -CONT $(ours) 2>/dev/null; paused=0; echo "$(date -u +%FT%TZ) busy=$busy% RESUME" >> "$LOG"; fi
  [[ -z "$(ours)" ]] && { echo "$(date -u +%FT%TZ) no jarambit procs left; exit" >> "$LOG"; exit 0; }
done
