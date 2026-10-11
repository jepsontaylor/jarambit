import numpy as np, sys; sys.path.insert(0,__import__('os').path.dirname(__file__))
import plate_fem as pf
from plate_fem import *
def rect(nx,ny,L,W):
    xy=[(W*ix/nx,L*iy/ny) for iy in range(ny+1) for ix in range(nx+1)]
    t=[];npx=nx+1
    for iy in range(ny):
        for ix in range(nx):
            a=iy*npx+ix; t+= [[a,a+1,a+npx+1],[a,a+npx+1,a+npx]]
    return np.array(xy,float),np.array(t)
pf.NU=0.0
for nx,ny in [(2,8),(4,16),(8,32)]:
  for flip in [False,True]:
    L,W,t=50.,14.,3.
    xy,tri=rect(nx,ny,L,W)
    if flip: tri=tri[:,[0,2,1]]
    P=Plate(xy,tri,t,"Ti-6Al-4V")
    fix=xy[:,1]<1e-9; tips=np.where(abs(xy[:,1]-L)<1e-8)[0]
    F=np.zeros(len(xy)*5); F[tips*5+2]=1/len(tips)
    u=P.solve(fix,F); sm,sb=P.stresses(u)
    print(nx,ny,flip,"uz ratio",u[tips*5+2].mean()/(L**3/(3*113800*W*t**3/12)),"vm ratio",sb.max()/(6*L/(W*t*t)))
