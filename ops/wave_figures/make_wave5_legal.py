"""Wave 5 plate: first LEGAL-blade winner (all three blade measures >= 86.225 mm) after the
blade-angle knob (152ad95) and FEM mesh caps (b46c774). Offline plotting only.
usage: WAVE_TIP=far python3 ops/wave_figures/make_wave5_legal.py <repo_root> [run_dir]"""
import os, sys, json
os.environ.setdefault("WAVE_TIP", "far")
import make_wave_figs as M
root = M.ROOT
run = sys.argv[2] if len(sys.argv) > 2 else "smoke_legal_blade"
d = os.path.join(root, "out", run)
s = M.plate("5", f"legal-blade smoke ({run}, first legal winner, post blade-angle knob)", d,
            os.path.join(d, "pareto.csv"), False, M.OUT, extra_note="| tip=farthest blade node (raked)")
idx = os.path.join(M.OUT, "index.json")
try: res = json.load(open(idx))
except Exception: res = []
res = [x for x in res if str(x.get("wave")) != "5"] + [s]
json.dump(res, open(idx, "w"), indent=1, default=float)
print(json.dumps(s, indent=1, default=float))
