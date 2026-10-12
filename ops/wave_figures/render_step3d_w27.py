#!/usr/bin/env python3
"""3D hero render of a design (PR-0.29.4: parameterised; caption derived from observations; figure manifest).
usage: render_step3d_w27.py --stl STL --index D1_index.json --label LABEL --out PNG
Caption: G1 recomputed by metrics/global_metric.py from the index record; 'faceted STL preview' unless the record
carries a `step_validation` observation with valid=true. Shading colour = x position only (declared norm step3d_x_mm)."""
import argparse, json, os, re, sys
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'metrics'))
from figlib import hero_caption, write_manifest, NORMS  # noqa: E402
from global_metric import global_G, read_version  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('--stl', required=True); ap.add_argument('--index', required=True); ap.add_argument('--label', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()
rec = next(r for r in json.load(open(a.index)) if r.get('label') == a.label)
G, _ = global_G(rec)
obs = {**rec, 'G1': G}
version = read_version(ROOT)
v = np.array(re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)', open(a.stl).read()), float).reshape(-1, 3, 3)
n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
L = np.array([-.4, -.5, .77]); sh = np.clip(np.abs(n @ L), 0, 1)
cx = v[:, :, 0].mean(1); c = plt.get_cmap(NORMS['step3d_x_mm']['cmap'])((cx - cx.min()) / np.ptp(cx)); c[:, :3] *= (.35 + .65 * sh)[:, None]
fig = plt.figure(figsize=(12, 6), facecolor='#0d1117'); ax = fig.add_subplot(111, projection='3d', facecolor='#0d1117')
ax.add_collection3d(Poly3DCollection(v, facecolors=c, edgecolor='none'))
mn, mx = v.reshape(-1, 3).min(0), v.reshape(-1, 3).max(0); ax.set_xlim(mn[0], mx[0]); ax.set_ylim(mn[1], mx[1]); ax.set_zlim(mn[2] - 15, mx[2] + 15)
ax.set_box_aspect((mx[0] - mn[0], mx[1] - mn[1], 36)); ax.view_init(40, -62); ax.set_axis_off()
ax.set_title(hero_caption(obs, version), color='w', fontsize=13)
plt.savefig(a.out, dpi=120, bbox_inches='tight', facecolor='#0d1117', metadata={'Software': None})
write_manifest(a.out, [a.stl, a.index], __file__, norms=['step3d_x_mm'], extra={'label': a.label, 'caption': hero_caption(obs, version)})
print('wrote', a.out)
