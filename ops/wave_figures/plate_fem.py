"""Offline plate FEM (port of crates/physics/src/fem.rs DKT + CST) on a refined
mesh, for per-wave figures only. NOT in the search loop. FEM-UNCALIBRATED.
Units: mm, N, MPa."""
import re, numpy as np, triangle
import scipy.sparse as sp, scipy.sparse.linalg as spla

E_MPA = {"Ti-6Al-4V": 113800.0, "Ti-3Al-2.5V": 100000.0}
SY = {"Ti-6Al-4V": (880.0, -0.0011), "Ti-3Al-2.5V": (620.0, -0.0012)}
NU = 0.34
BLADE_H = 14.0

def yield_at(mat, T):
    s, d = SY[mat]; return s * (1 + d * (T - 20.0))

def parse_svg(path):
    txt = open(path).read()
    d = re.search(r"<path d='([^']*)'", txt).group(1)
    subs = [s for s in d.split('M') if s.strip()]
    polys = []
    for s in subs:
        pts = re.findall(r'(-?[\d.]+),(-?[\d.]+)', s)
        polys.append(np.array([(float(x), -float(y)) for x, y in pts]))
    return polys[0], polys[1]

def mesh(outer, hole, max_area=0.6):
    def clean(p):
        keep = [p[0]]
        for q in p[1:]:
            if np.hypot(*(q - keep[-1])) > 1e-6: keep.append(q)
        if np.hypot(*(keep[0] - keep[-1])) < 1e-6: keep.pop()
        return np.array(keep)
    o, h = clean(outer), clean(hole)
    no, nh = len(o), len(h)
    segs = [(i, (i + 1) % no) for i in range(no)] + [(no + i, no + (i + 1) % nh) for i in range(nh)]
    A = dict(vertices=np.vstack([o, h]), segments=np.array(segs), holes=np.array([h.mean(0)]))
    T = triangle.triangulate(A, f'pq30a{max_area}')
    xy, tri = T['vertices'], T['triangles']
    bm = T['vertex_markers'].ravel()
    # hole boundary nodes: lie on hole polygon (distance)
    from shapely.geometry import Polygon, Point
    hp = Polygon(h).exterior
    on_hole = np.array([bm[i] == 1 and hp.distance(Point(*xy[i])) < 1e-6 for i in range(len(xy))])
    op = Polygon(o).exterior
    on_outer = np.array([bm[i] == 1 and op.distance(Point(*xy[i])) < 1e-6 for i in range(len(xy))])
    return xy, tri, on_hole, on_outer

def c_plane(e, nu):
    k = e / (1 - nu * nu)
    return np.array([[k, k * nu, 0], [k * nu, k, 0], [0, 0, k * (1 - nu) / 2]])

def cst_b(xs, ys, a2):
    b = np.zeros((3, 6))
    for j in range(3):
        nx = (ys[(j + 1) % 3] - ys[(j + 2) % 3]) / a2
        ny = (xs[(j + 2) % 3] - xs[(j + 1) % 3]) / a2
        b[0, 2 * j] = nx; b[1, 2 * j + 1] = ny; b[2, 2 * j] = ny; b[2, 2 * j + 1] = nx
    return b

def dkt_b(xs, ys, a2, xi, eta):
    xe = [xs[(i + 2) % 3] - xs[(i + 1) % 3] for i in range(3)]
    ye = [ys[(i + 2) % 3] - ys[(i + 1) % 3] for i in range(3)]
    p, q, r, tv = [0]*3, [0]*3, [0]*3, [0]*3
    for i in range(3):
        l2 = xe[i]**2 + ye[i]**2
        p[i] = -6 * xe[i] / l2; q[i] = 3 * xe[i] * ye[i] / l2; r[i] = 3 * ye[i]**2 / l2; tv[i] = -6 * ye[i] / l2
    a = 1 - 2 * xi; c = 1 - 2 * eta
    hx_xi = [p[2]*a + (p[1]-p[2])*eta, q[2]*a - (q[1]+q[2])*eta, -4+6*(xi+eta) + r[2]*a - eta*(r[1]+r[2]),
             -p[2]*a + eta*(p[0]+p[2]), q[2]*a - eta*(q[2]-q[0]), -2+6*xi + r[2]*a + eta*(r[0]-r[2]),
             -eta*(p[1]+p[0]), eta*(q[0]-q[1]), -eta*(r[1]-r[0])]
    hy_xi = [tv[2]*a + (tv[1]-tv[2])*eta, 1 + r[2]*a - (r[1]+r[2])*eta, -q[2]*a + eta*(q[1]+q[2]),
             -tv[2]*a + eta*(tv[0]+tv[2]), -1 + r[2]*a + eta*(r[0]-r[2]), q[2]*a - eta*(q[0]-q[2]),
             -eta*(tv[0]+tv[1]), eta*(r[0]-r[1]), -eta*(q[0]-q[1])]
    hx_eta = [-p[1]*c - xi*(p[2]-p[1]), q[1]*c - xi*(q[1]+q[2]), -4+6*(xi+eta) + r[1]*c - xi*(r[1]+r[2]),
              xi*(p[0]+p[2]), xi*(q[0]-q[2]), -xi*(r[2]-r[0]),
              p[1]*c - xi*(p[0]+p[1]), q[1]*c + xi*(q[0]-q[1]), -2+6*eta + r[1]*c + xi*(r[0]-r[1])]
    hy_eta = [-tv[1]*c - xi*(tv[2]-tv[1]), 1 + r[1]*c - xi*(r[1]+r[2]), -q[1]*c + xi*(q[1]+q[2]),
              xi*(tv[0]+tv[2]), xi*(r[0]-r[2]), -xi*(q[0]-q[2]),
              tv[1]*c - xi*(tv[0]+tv[1]), -1 + r[1]*c + xi*(r[0]-r[1]), -q[1]*c - xi*(q[0]-q[1])]
    hx_xi, hy_xi, hx_eta, hy_eta = map(np.array, (hx_xi, hy_xi, hx_eta, hy_eta))
    b = np.zeros((3, 9))
    b[0] = (ye[1]*hx_xi + ye[2]*hx_eta) / a2
    b[1] = (-xe[1]*hy_xi - xe[2]*hy_eta) / a2
    b[2] = (-xe[1]*hx_xi - xe[2]*hx_eta + ye[1]*hy_xi + ye[2]*hy_eta) / a2
    return b

GP = [(1/6, 1/6, 1/3), (2/3, 1/6, 1/3), (1/6, 2/3, 1/3)]

def vm(s):
    return np.sqrt(s[0]**2 - s[0]*s[1] + s[1]**2 + 3*s[2]**2)

class Plate:
    def __init__(self, xy, tri, t, mat):
        tri = tri.copy()
        a2 = (xy[tri[:,1],0]-xy[tri[:,0],0])*(xy[tri[:,2],1]-xy[tri[:,0],1]) - (xy[tri[:,2],0]-xy[tri[:,0],0])*(xy[tri[:,1],1]-xy[tri[:,0],1])
        self.n_cw = int((a2 < 0).sum())
        tri[a2 < 0] = tri[a2 < 0][:, [0, 2, 1]]  # DKT B (Batoz) assumes CCW node order
        self.xy, self.tri, self.t = xy, tri, t
        self.C = c_plane(E_MPA[mat], NU)
        n = len(xy); rows, cols, vals = [], [], []
        self.Bm, self.Bb = [], []
        for e in tri:
            xs, ys = xy[e, 0], xy[e, 1]
            a2 = (xs[1]-xs[0])*(ys[2]-ys[0]) - (xs[2]-xs[0])*(ys[1]-ys[0])
            area = abs(a2) / 2
            bm = cst_b(xs, ys, a2); self.Bm.append(bm)
            km = bm.T @ self.C @ bm * t * area
            idm = [e[a]*5 + c for a in range(3) for c in range(2)]
            kb = np.zeros((9, 9)); bbs = []
            for xi, eta, w in GP:
                bb = dkt_b(xs, ys, a2, xi, eta); bbs.append(bb)
                kb += bb.T @ self.C @ bb * w * area * t**3 / 12
            self.Bb.append(bbs)
            idb = [e[a]*5 + 2 + c for a in range(3) for c in range(3)]
            for K, ids in ((km, idm), (kb, idb)):
                I, J = np.meshgrid(ids, ids, indexing='ij')
                rows.append(I.ravel()); cols.append(J.ravel()); vals.append(K.ravel())
        self.K = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n*5, n*5))

    def solve(self, fixed_nodes, F):
        n = len(self.xy)
        fixed = np.zeros(n*5, bool)
        for i in np.where(fixed_nodes)[0]: fixed[i*5:i*5+5] = True
        free = np.where(~fixed)[0]
        Kff = self.K[free][:, free].tocsc()
        u = np.zeros(n*5)
        u[free] = spla.spsolve(Kff, F[free])
        return u

    def stresses(self, u):
        """per-element peak von Mises: (membrane, bending surface)."""
        sm, sb = [], []
        for k, e in enumerate(self.tri):
            um = np.array([u[e[a]*5 + c] for a in range(3) for c in range(2)])
            ub = np.array([u[e[a]*5 + 2 + c] for a in range(3) for c in range(3)])
            sm.append(vm(self.C @ (self.Bm[k] @ um)))
            sb.append(max(vm(self.C @ (bb @ ub) * self.t / 2) for bb in self.Bb[k]))
        return np.array(sm), np.array(sb)

# ---- Numerically constructed DKT (Batoz 1980 definition), independent of the
# closed-form Hx/Hy coefficients above. Node bending dofs: (w, dw/dx, dw/dy).
def dkt_T(xs, ys):
    T = np.zeros((12, 9))   # rows: beta_x at 6 nodes, then beta_y at 6 nodes
    for i in range(3):
        T[i, 3*i+1] = 1.0; T[6+i, 3*i+2] = 1.0
    for m, (i, j) in zip((3, 4, 5), ((1, 2), (2, 0), (0, 1))):
        dx, dy = xs[j]-xs[i], ys[j]-ys[i]; l = np.hypot(dx, dy); c, s = dx/l, dy/l
        ws = np.zeros(9); wn = np.zeros(9)
        ws[3*i] = -1.5/l; ws[3*j] = 1.5/l
        ws[3*i+1] += -0.25*c; ws[3*i+2] += -0.25*s; ws[3*j+1] += -0.25*c; ws[3*j+2] += -0.25*s
        wn[3*i+1] += -0.5*s; wn[3*i+2] += 0.5*c; wn[3*j+1] += -0.5*s; wn[3*j+2] += 0.5*c
        T[m] = c*ws - s*wn; T[6+m] = s*ws + c*wn
    return T

def dkt_b2(xs, ys, a2, L):
    b = np.array([ys[(i+1)%3]-ys[(i+2)%3] for i in range(3)]) / a2
    c = np.array([xs[(i+2)%3]-xs[(i+1)%3] for i in range(3)]) / a2
    def dN(d):
        g = np.zeros(6)
        for i in range(3): g[i] = (4*L[i]-1)*d[i]
        g[3] = 4*(L[1]*d[2]+L[2]*d[1]); g[4] = 4*(L[2]*d[0]+L[0]*d[2]); g[5] = 4*(L[0]*d[1]+L[1]*d[0])
        return g
    Nx, Ny = dN(b), dN(c)
    T = dkt_T(xs, ys)
    B = np.zeros((3, 9))
    B[0] = Nx @ T[:6]; B[1] = Ny @ T[6:]; B[2] = Ny @ T[:6] + Nx @ T[6:]
    return B

GPL = [((2/3, 1/6, 1/6), 1/3), ((1/6, 2/3, 1/6), 1/3), ((1/6, 1/6, 2/3), 1/3)]

class Plate2(Plate):
    def __init__(self, xy, tri, t, mat):
        global dkt_b
        orig = dkt_b
        try:
            dkt_b = lambda xs, ys, a2, xi, eta: dkt_b2(xs, ys, a2, (1-xi-eta, xi, eta))
            super().__init__(xy, tri, t, mat)
        finally:
            dkt_b = orig
