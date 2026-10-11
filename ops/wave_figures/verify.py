import numpy as np, sys; sys.path.insert(0,__import__('os').path.dirname(__file__))
from plate_fem import *
L,W,t=60.,10.,3.
outer=np.array([[0,0],[L,0],[L,W],[0,W]],float)
# no hole: trick - tiny hole far away? use triangle directly
T=triangle.triangulate(dict(vertices=outer,segments=np.array([[0,1],[1,2],[2,3],[3,0]])),'pq30a0.5')
xy,tri=T['vertices'],T['triangles']
P=Plate(xy,tri,t,"Ti-6Al-4V")
fix=xy[:,0]<1e-6
F=np.zeros(len(xy)*5); tipn=np.where(xy[:,0]>L-1e-6)[0]
for i in tipn: F[i*5+2]=1/len(tipn)
u=P.solve(fix,F); sm,sb=P.stresses(u)
cx=xy[tri].mean(1)[:,0]
print("bending root (x<3):",sb[cx<3].max(),"mid x~30:",np.median(sb[abs(cx-30)<1]),"beam root 6FL/bt2=",6*L/(W*t*t),"at30=",6*30/(W*t*t))
print("tip defl",u[tipn*5+2].mean(),"beam FL3/3EI=",L**3/(3*113800*W*t**3/12))
F=np.zeros(len(xy)*5)
for i in tipn: F[i*5+0]=1/len(tipn)
u=P.solve(fix,F); sm,sb=P.stresses(u); print("tension",np.median(sm),"exp",1/(W*t))
