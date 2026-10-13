PR #56 fresh independent ramp benchmark: CalculiX 2.21, pinned jarambit-sheath:s1 container.
All four levels have rc=0 and complete histories ending at t=1; deck/history paths and hashes are in ccx_tab.json.
Fresh unique run directory; all DAT mtimes follow the recorded run start. Last-two convergence <=5%.
This ramp benchmark does not validate the spherical-cap sheath export; force-model feasibility is INCOMPLETE.
Existing sweep_*.jsonl files are historical diagnostics, lack current validation proofs, and cannot be loaded as corrections.
Reproduce: python -m sheath.ccx_tab --out NEW_DIR --levels 3,4,6,8 --params '{"L":16,"b":7,"t":2.0,"h":1.508,"a_out":35,"a_in":30,"mu":0.3}'
Heavy jobs: ~/bin/memcap 32G, nice 19, CPU only; container also has a 32G cap/no swap and 4 CPU quota.
