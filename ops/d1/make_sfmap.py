"""D1 P1 parent safety-factor map for shallow-pocket placement (JARAMBIT_P1_SFMAP).
Reads a D1 plate JSON (crescent-d1 D1_PLATES=1 / crescent-evolve plate) of the PARENT design, rasterises its
certified 100 C envelope SF (lateral 260 N, tip chord-torsion 1.82 N*m x 3D, pry 260 N, ring 1500 N; joint
thin+hot) at 0.5 mm and writes the signed distance (mm) INTO the region SF > THRESH (<= 0 outside / off-part).
usage: python3 make_sfmap.py <parent_plate.json> <out.txt> [thresh=2.0] [grid=0.5]"""
import sys, json, numpy as np
import matplotlib.tri as mtri
from scipy.ndimage import distance_transform_edt
src, dst = sys.argv[1], sys.argv[2]
TH = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
G = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
d = json.load(open(src)); xy = np.array(d['mesh']['xy'], float); tri = np.array(d['mesh']['tris'])
sf = np.array(d['mesh']['sf'], float)
T = mtri.Triangulation(xy[:, 0], xy[:, 1], tri); finder = T.get_trifinder()
x0, y0 = xy[:, 0].min() - 2, xy[:, 1].min() - 2; nx = int((xy[:, 0].max() + 2 - x0) / G) + 1; ny = int((xy[:, 1].max() + 2 - y0) / G) + 1
X, Y = np.meshgrid(x0 + (np.arange(nx) + 0.5) * G, y0 + (np.arange(ny) + 0.5) * G)
k = finder(X, Y); inside = k >= 0
s = np.where(inside, sf[np.clip(k, 0, None)], 0.0)
reg = inside & (s > TH)
dist_in = distance_transform_edt(reg) * G           # distance from the nearest SF<=TH / off-part cell
out = np.where(reg, dist_in - 0.5 * G, -1.0)
with open(dst, 'w') as f:
    f.write(f"{x0} {y0} {G} {nx} {ny}\n")
    for j in range(ny): f.write(" ".join(f"{v:.2f}" for v in out[j]) + "\n")
a = reg.sum() * G * G; ain = inside.sum() * G * G
print(f"sfmap {dst}: grid {nx}x{ny} @ {G} mm; SF>{TH} region {a:.0f} mm2 of {ain:.0f} mm2 ({100*a/ain:.1f} %), min SF {sf.min():.2f}")
