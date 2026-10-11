#!/bin/bash -l
cd /home/ubuntu/jarambit
export CARGO_BUILD_JOBS=16
exec /home/ubuntu/.local/bin/grok --always-approve --cwd /home/ubuntu/jarambit "You are the jarambit_grok OWNER. Read /home/ubuntu/jarambit/briefs/OWNER_BRIEF_grok.md, README.md and COORD.md, then execute the brief autonomously. Coordinate only via COORD.md."
