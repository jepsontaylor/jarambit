#!/bin/bash -l
cd /home/ubuntu/jarambit
export CARGO_BUILD_JOBS=16
exec /home/ubuntu/.npm-global/bin/codex --yolo -m gpt-6.1-sol -c model_reasoning_effort=xhigh "You are the jarambit_codex OWNER. Read /home/ubuntu/jarambit/briefs/OWNER_BRIEF_codex.md, README.md and COORD.md, then execute the brief autonomously. Coordinate only via COORD.md."
