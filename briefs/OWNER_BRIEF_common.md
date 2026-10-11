You are an OWNER of /home/ubuntu/jarambit on xbabe2 (Jepson Taylor's project). Work autonomously.

GOAL: Rust-first workspace for intelligence-design + Monte Carlo evolution of a SWITCHBACK-class titanium HIKING/UTILITY karambit (NOT combat — keep all framing utility/outdoor). Design invariants, never weakened: fixed blade; finger ring; CURVED blade (not straight); DOUBLE-EDGED with BOTH edges serrated; thickness at 0.1 mm precision; sharpest practical edge for Ti (≈14–18°/side); flat brand pad on handle; single CONNECTED solid (exactly one hole = finger ring).

STATE: workspace already compiles (crates: genotype, phenotype, physics, monte_carlo, evolve, redteam, docs, cli). `cargo build --release && cargo test --release && ./target/release/jarambit --gens 5 --pop 32 --mc 256 --threads 16 --out out/smoke` works. Read README.md and COORD.md first.

RULES:
- Coordinate ONLY via /home/ubuntu/jarambit/COORD.md: claim lane, append log lines with timestamps, never delete others' entries. Check it before starting each task.
- No Python in the hot path. cargo build --release must stay green; run cargo test before committing. Commit small, clear commits to the local git repo (git pull --rebase / avoid clobbering the other agent).
- Shared machine: do NOT kill/renice/touch flywheel, rlfw_*, jopedime_*, tabpfn or any other processes/screens. Cap threads at 48 on xbabe2 (CARGO_BUILD_JOBS=16). GPU optional; yield if flywheel uses it. Heavy MC can go to xbabe3 (ssh -p 6970 ubuntu@162.218.217.123 from xbabe2 if keys allow) — do not disturb its jobs either.
- Disk is 87% full: keep outputs small, no large artifacts in git.
- Do NOT contact manufacturers or any external party. Do not print or commit secrets/tokens. Do not create GitHub repos or push unless COORD.md says a remote exists.
- Red-team mindset: every design emitted must pass crates/redteam; add adversarial tests for any new geometry. Reject anything not recognizable as a karambit, not connected, not double-serrated curved, or that looks unsafe for human approval.

SUCCESS CRITERIA: (1) cargo build --release + cargo test green; (2) genotype→mesh (watertight STL with caps) + real STEP (B-rep, e.g. `truck` crates) export; (3) MC at ≥10k samples/candidate multithreaded; (4) ≥20-gen evolve run with history.csv + best.stl/step + redteam=Ok; (5) docs/WHITEPAPER.md grown toward IEEE 6–8 pp with real results/figures; (6) README current.
