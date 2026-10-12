"""wave18 tip 3D SOLID submodel prototype (PREP, not a gate): plate (Kirchhoff DKT, crescent-d1) vs solid (P2 tets) chord-torsion
SF at 1.82 N*m in the 4-15 mm tip annulus of one D1 design. Geometry = D1 plate mesh within R_CUT of the tip, extruded symmetrically
to z = +-th(x,y)/2 from the exported thickness raster (grind law, faces z=+-th/2). BC: cut boundary (dist = R_CUT) fully clamped.
Load: pure chord torque T about d = unit(tip) (ring at origin), min-norm z-forces on all vertices within 2 mm of the tip
(net F = 0, moment about n = 0). Material Ti-6Al-4V E 113.8 GPa nu 0.34, sy20 828 MPa, JOINT thin+hot factor as crescent-d1.
Usage: python3 tip_solid.py D1.json R_CUT NLAYER NSUB out.json"""
import sys, json, math, time, numpy as np
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
class Path:
    def __init__(self, v): self.v = np.asarray(v, float)
    def contains_points(self, P):
        P = np.atleast_2d(P); x, y = P[:, 0][:, None], P[:, 1][:, None]; a = self.v; b = np.roll(a, -1, 0)
        c = ((a[:, 1] > y) != (b[:, 1] > y)) & (x < (b[:, 0]-a[:, 0])*(y-a[:, 1])/(b[:, 1]-a[:, 1]+1e-300)+a[:, 0]); return c.sum(1) % 2 == 1
from skfem import MeshTet, Basis, ElementVector, ElementTetP2, asm
from skfem.models.elasticity import linear_elasticity, lame_parameters
from skfem.helpers import sym_grad, trace, eye
import scipy.sparse.linalg as spla, scipy.sparse as sp
fn, RC, NL, NSUB, OUT = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
T_NMM, E, NU, SY20 = 1820.0, 113.8e3, 0.34, 828.0
t0 = time.time()
d = json.load(open(fn)); m = d["metrics"]; me = d["mesh"]
xy = np.array(me["xy"]); tris = np.array(me["tris"]); twist = np.array([np.nan if v is None else v for v in me["twist"]]); te = np.array(me["te"])
outer = Path(np.array(d["outline"])); holes = [Path(np.array(h)) for h in d["holes"]]
f = d["field"]; th = np.array([np.nan if v is None else v for v in f["th"]], float).reshape(f["ny"], f["nx"])
# nearest-valid fill of the raster (boundary cells straddling the outline are NaN)
from scipy import ndimage
idx = ndimage.distance_transform_edt(np.isnan(th), return_distances=False, return_indices=True); thf = th[tuple(idx)]
def thick(P):
    gx = (P[:, 0]-f["x0"])/f["g"]-0.5; gy = (P[:, 1]-f["y0"])/f["g"]-0.5
    return ndimage.map_coordinates(thf, [gy, gx], order=1, mode="nearest")
# tip = outline point with max x (as zones.py); plate tip node = nearest outer node
gl = json.load(open(fn.replace("_D1.json", "_grind_law.json")))
tip_gl = np.array(gl["edges"][0]["samples"][0][:2])          # inner-edge start = the point (pheno tip)
ob = np.array(d["outline"]); tipo = ob[np.argmin(np.linalg.norm(ob-tip_gl, axis=1))]  # nearest outline vertex (plate: nearest outer node)
dvec = tipo/np.linalg.norm(tipo); nvec = np.array([-dvec[1], dvec[0]])
cen = xy[tris].mean(1); dc = np.linalg.norm(cen-tipo, axis=1)
# ---- PLATE reference from the exported crescent-d1 field (0.25 mm^2 cert mesh, per unit torque) ----
inside = lambda q: outer.contains_points(q[None])[0] and not any(h.contains_points(q[None])[0] for h in holes)
def kc_at(c):
    def w(s):
        dd = 0.0
        while dd < 60 and inside(c + s*(dd+0.05)*nvec): dd += 0.05
        return dd
    b = w(1)+w(-1); return b
def alpha_rect(r):
    r = max(r, 1.0); s1 = s2 = 0.0
    for i in range(60):
        n = 2*i+1; s1 += math.tanh(n*math.pi*r/2)/n**5; s2 += 1/(n*n*math.cosh(min(n*math.pi*r/2, 700)))
    k1 = (1-192/math.pi**5/r*s1)/3; k = 1-8/math.pi**2*s2; return k1/k
kc = lambda b, t: (1/3)/alpha_rect(max(b, t)/max(min(b, t), 1e-6))
tj = m["t_joint"]; JK2 = ((tj-0.1)/tj)**2*(1-0.0011*80); SALLOW = SY20*JK2
zone = (dc >= 4.0) & (dc < 15.0) & np.isfinite(twist)
ez = np.where(zone)[0][np.argmax(twist[zone])]; bz = kc_at(cen[ez]); kz = kc(bz, te[ez])
plate = dict(sigma_per_Nmm=float(twist[ez]), at=cen[ez].round(2).tolist(), dist_tip=float(dc[ez]), t_local=float(te[ez]), b_section=round(bz, 2), kc_3d=round(kz, 3),
             sigma_plate_MPa=float(twist[ez]*T_NMM), sigma_plate_x_kc_MPa=float(twist[ez]*T_NMM*kz),
             SF_plate_raw=float(SALLOW/(twist[ez]*T_NMM)), SF_plate_d1=float(SALLOW/(twist[ez]*T_NMM*kz)))
prof_plate = {}
for a, b in [(4, 5), (5, 6), (6, 8), (8, 10), (10, 12), (12, 15), (15, 20), (20, 25)]:
    s = (dc >= a) & (dc < b) & np.isfinite(twist); prof_plate[f"{a}-{b}"] = float(twist[s].max()*T_NMM) if s.any() else None
print("PLATE", json.dumps(plate), flush=True)
# ---- SOLID submodel ----
keep = dc <= RC
from scipy.sparse.csgraph import connected_components
ki = np.where(keep)[0]; kt0 = tris[ki]
rows_ = np.repeat(np.arange(len(ki)), 3); G = sp.csr_matrix((np.ones(len(rows_)), (rows_, kt0.ravel())), shape=(len(ki), len(xy)))
A_ = (G @ G.T).tocsr(); ncomp, lab = connected_components(A_, directed=False)
tri_tip = np.argmin(np.linalg.norm(cen[ki]-tipo, axis=1)); keep[:] = False; keep[ki[lab == lab[tri_tip]]] = True
print(f"components in R_CUT disk: {ncomp} (kept the tip component, {keep.sum()} plate tris)", flush=True)
kt = tris[keep]
used = np.unique(kt); rm = -np.ones(len(xy), int); rm[used] = np.arange(len(used)); P2d = xy[used]; T2d = rm[kt]
# cut nodes: vertices of kept tris that also belong to a dropped tri
dropped = np.unique(tris[~keep]); cutmask = np.zeros(len(xy), bool); cutmask[dropped] = True; cut2d = cutmask[used]
for _ in range(NSUB):   # uniform 1->4 triangle subdivision (midpoints)
    edges = {}; newp = list(P2d); newcut = list(cut2d); NT = []
    def mid(a, b):
        k = (min(a, b), max(a, b))
        if k not in edges:
            edges[k] = len(newp); newp.append((P2d[a]+P2d[b])/2); newcut.append(cut2d[a] and cut2d[b])
        return edges[k]
    for a, b, c in T2d:
        ab, bc, ca = mid(a, b), mid(b, c), mid(c, a); NT += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
    P2d = np.array(newp); T2d = np.array(NT); cut2d = np.array(newcut)
# the cut arc: keep only cut nodes near dist = RC-ish (avoid tagging interior)  -> nodes with dist >= RC-3 that were cut-tagged
dn = np.linalg.norm(P2d-tipo, axis=1); cut2d &= dn > RC-4.0
hh = thick(P2d); N2 = len(P2d)
pts = np.vstack([np.c_[P2d, (k/NL-0.5)*hh] for k in range(NL+1)])
def tets_of_prism(v):
    v = list(v)
    i0 = int(np.argmin(v))
    rot = {0: [0, 1, 2, 3, 4, 5], 1: [1, 2, 0, 4, 5, 3], 2: [2, 0, 1, 5, 3, 4], 3: [3, 5, 4, 0, 2, 1], 4: [4, 3, 5, 1, 0, 2], 5: [5, 4, 3, 2, 1, 0]}[i0]
    w = [v[r] for r in rot]
    if min(w[1], w[5]) < min(w[2], w[4]): return [(w[0], w[1], w[2], w[5]), (w[0], w[1], w[5], w[4]), (w[0], w[4], w[5], w[3])]
    return [(w[0], w[1], w[2], w[4]), (w[0], w[4], w[2], w[5]), (w[0], w[4], w[5], w[3])]
TT = []
for k in range(NL):
    for a, b, c in T2d: TT += tets_of_prism((a+k*N2, b+k*N2, c+k*N2, a+(k+1)*N2, b+(k+1)*N2, c+(k+1)*N2))
TT = np.array(TT)
v = pts[TT]; vol = np.einsum("ij,ij->i", np.cross(v[:, 1]-v[:, 0], v[:, 2]-v[:, 0]), v[:, 3]-v[:, 0])
TT[vol < 0] = TT[vol < 0][:, [0, 2, 1, 3]]
mesh = MeshTet(pts.T.copy(), TT.T.copy())
e = ElementVector(ElementTetP2()); ib = Basis(mesh, e, intorder=2)
lam, mu = lame_parameters(E, NU)
K = None if __import__("os").environ.get("DUMP_ONLY") == "1" else asm(linear_elasticity(lam, mu), ib).tocsr()  # DUMP_ONLY: dolfinx assembles
print(f"mesh: {len(TT)} P2 tets, {ib.N} dof, assembled {time.time()-t0:.0f}s", flush=True)
# load: vertices within 2 mm of tip (all layers); min-norm z-forces with sum F=0, sum F*s = T, sum F*q = 0
loc = ib.doflocs; zd = ib.nodal_dofs[2] if hasattr(ib, "nodal_dofs") else None
vert = np.arange(mesh.p.shape[1]); pv = mesh.p.T
PATCH = float(__import__("os").environ.get("PATCH", "2.0"))
pat = vert[np.linalg.norm(pv[:, :2]-tipo, axis=1) <= PATCH]
r = pv[pat, :2]-pv[pat, :2].mean(0); s = r@nvec; q = r@dvec
A = np.vstack([np.ones(len(pat)), s, q]); Fz = A.T@np.linalg.solve(A@A.T, np.array([0.0, T_NMM, 0.0]))
fvec = np.zeros(ib.N); fvec[ib.nodal_dofs[2, pat]] = Fz
# check torque about chord through the patch: moment about d of F_z at r = F_z*(n.r)
print(f"load: {len(pat)} vertices, torque {np.sum(Fz*s):.1f} N*mm, netF {Fz.sum():.2e}, M_n {np.sum(Fz*q):.2e}", flush=True)
# clamp: all dofs at points whose xy lies on the cut arc (vertices + P2 edge nodes)
cutxy = P2d[cut2d]
from scipy.spatial import cKDTree
tr = cKDTree(cutxy)
dl = loc.T; dist_cut, _ = tr.query(dl[:, :2]); 
# P2 edge-midnodes on the cut: midpoint of two cut vertices -> within half an edge of a cut vertex AND dn>RC-4 AND on boundary; use vertex-based test
fixed_v = np.where(cut2d[np.arange(mesh.p.shape[1]) % N2])[0]
D = ib.get_dofs(lambda X: np.zeros(X.shape[1], bool))  # placeholder
fixdofs = set(ib.nodal_dofs[:, fixed_v].ravel().tolist())
# edge dofs whose both endpoints are fixed vertices
ed = mesh.edges; both = np.isin(ed[0], fixed_v) & np.isin(ed[1], fixed_v)
fixdofs |= set(ib.edge_dofs[:, np.where(both)[0]].ravel().tolist())
fixdofs = np.array(sorted(fixdofs)); free = np.setdiff1d(np.arange(ib.N), fixdofs)
print(f"clamp: {len(fixed_v)} vertices on cut (R_CUT {RC} mm), {len(fixdofs)} dofs", flush=True)
if __import__("os").environ.get("DUMP_MESH"):  # PR-0.30.2: hand the exact submodel to fem_solid/cross_check.py (dolfinx)
    np.savez_compressed(__import__("os").environ["DUMP_MESH"], pts=pv, tets=mesh.t.T, fixed_v=fixed_v, edges_fixed=ed[:, both].T, pat=pat, Fz=Fz, tipo=tipo,
                        cutxy=cutxy, sallow=SALLOW, E=E, nu=NU)
    if __import__("os").environ.get("DUMP_ONLY") == "1": print("DUMP_ONLY: mesh written, skfem solve skipped", flush=True); sys.exit(0)
Kff = K[free][:, free]; t1 = time.time()
u = np.zeros(ib.N)
try:
    import pyamg
    B = np.zeros((ib.N, 6)); xd = ib.doflocs
    B[0::3, 0] = 1; B[1::3, 1] = 1; B[2::3, 2] = 1
    B[0::3, 3] = -xd[1, 0::3]; B[1::3, 3] = xd[0, 1::3]; B[1::3, 4] = -xd[2, 1::3]; B[2::3, 4] = xd[1, 2::3]
    B[0::3, 5] = xd[2, 0::3]; B[2::3, 5] = -xd[0, 2::3]
    ml = pyamg.smoothed_aggregation_solver(Kff, B=B[free], max_coarse=3000); rr = []
    u[free] = ml.solve(fvec[free], tol=1e-10, accel="cg", maxiter=3000, residuals=rr); print(f"AMG-CG its {len(rr)-1}", flush=True)
except ImportError:
    u[free] = spla.spsolve(Kff.tocsc(), fvec[free], permc_spec="MMD_AT_PLUS_A")
res = np.linalg.norm(Kff@u[free]-fvec[free])/np.linalg.norm(fvec[free])
print(f"solved {time.time()-t1:.0f}s rel.res {res:.1e}", flush=True)
# stresses at element VERTICES (reference points) -> nodal max/avg; P2 -> linear stress per element
Xr = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], float); Wr = np.ones(4)/24
bv = Basis(mesh, e, quadrature=(Xr, Wr))
ui = bv.interpolate(u); eps = sym_grad(ui); sg = 2*mu*eps+lam*eye(trace(eps), 3)
vm = np.sqrt(0.5*((sg[0, 0]-sg[1, 1])**2+(sg[1, 1]-sg[2, 2])**2+(sg[2, 2]-sg[0, 0])**2)+3*(sg[0, 1]**2+sg[1, 2]**2+sg[0, 2]**2))  # (nel, 4)
# quadrature points map vertex order of each element: reference vertex k -> mesh.t[k]
nv = mesh.p.shape[1]; acc = np.zeros(nv); cnt = np.zeros(nv); mx = np.zeros(nv)
for k in range(4):
    np.add.at(acc, mesh.t[k], vm[:, k]); np.add.at(cnt, mesh.t[k], 1); np.maximum.at(mx, mesh.t[k], vm[:, k])
avg = acc/np.maximum(cnt, 1)
dv = np.linalg.norm(pv[:, :2]-tipo, axis=1); dcut = tr.query(pv[:, :2])[0]
def zpk(a, b, f_):
    s_ = (dv >= a) & (dv < b) & (dcut > 3.0)
    if not s_.any(): return None
    i = np.where(s_)[0][np.argmax(f_[s_])]; return dict(MPa=round(float(f_[i]), 1), at=pv[i].round(2).tolist(), dist=round(float(dv[i]), 2))
zs = zpk(4, 15, avg); zx = zpk(4, 15, mx)
# element-mean (centroid) vM, as earlier 3D waves' element-mean metric (non-conservative)
vmc = vm.mean(1); cc = mesh.p[:, mesh.t].mean(1).T; dcc = np.linalg.norm(cc[:, :2]-tipo, axis=1)
sz = (dcc >= 4) & (dcc < 15); ic = np.where(sz)[0][np.argmax(vmc[sz])]
prof_solid = {}
for a, b in [(4, 5), (5, 6), (6, 8), (8, 10), (10, 12), (12, 15), (15, 20), (20, 25)]:
    z_ = zpk(a, b, avg); prof_solid[f"{a}-{b}"] = z_["MPa"] if z_ else None
solid = dict(PATCH_mm=PATCH, n_tet=int(len(TT)), n_dof=int(ib.N), R_CUT=RC, NL=NL, NSUB=NSUB, nodal_avg_peak=zs, nodal_max_peak=zx,
             elem_mean_peak=dict(MPa=round(float(vmc[ic]), 1), at=cc[ic].round(2).tolist()),
             SF_solid_nodal_avg=round(SALLOW/zs["MPa"], 3), SF_solid_nodal_max=round(SALLOW/zx["MPa"], 3), SF_solid_elem_mean=round(SALLOW/float(vmc[ic]), 3),
             twist_rot_check=None, wall_s=round(time.time()-t0, 1))
outj = dict(design=fn, T_Nmm=T_NMM, sallow_joint_MPa=round(SALLOW, 1), JK2=round(JK2, 4), plate=plate, solid=solid, profile_MPa=dict(plate_raw=prof_plate, solid_nodal_avg=prof_solid))
json.dump(outj, open(OUT, "w"), indent=1)
print(json.dumps(outj, indent=1))
