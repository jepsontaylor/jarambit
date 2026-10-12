import json,numpy as np,matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.path import Path
d=json.load(open('g3_tip+00_t60_tt3_D1.json'));t=d['metrics']['t']
loops=[np.array(d['outline'])]+[np.array(h) for h in d['holes']]
fig=plt.figure(figsize=(9,5.2));ax=fig.add_subplot(111,projection='3d')
# side walls
for L in loops:
    L=L[::max(1,len(L)//600)]
    q=[[ (L[i,0],L[i,1],0),(L[i+1,0],L[i+1,1],0),(L[i+1,0],L[i+1,1],t),(L[i,0],L[i,1],t)] for i in range(len(L)-1)]
    ax.add_collection3d(Poly3DCollection(q,facecolor='#8a9bb0',edgecolor='none',alpha=1))
# top face via triangulated grid fill (point-in-polygon)
o=Path(loops[0]);hs=[Path(h) for h in loops[1:]]
xs=np.linspace(loops[0][:,0].min(),loops[0][:,0].max(),260);ys=np.linspace(loops[0][:,1].min(),loops[0][:,1].max(),140)
X,Y=np.meshgrid(xs,ys);P=np.c_[X.ravel(),Y.ravel()]
m=o.contains_points(P)
for h in hs:m&=~h.contains_points(P)
M=m.reshape(X.shape);dx=xs[1]-xs[0];dy=ys[1]-ys[0];q=[]
for i,j in zip(*np.nonzero(M)):
    x,y=X[i,j],Y[i,j];q.append([(x-dx/2,y-dy/2,t),(x+dx/2,y-dy/2,t),(x+dx/2,y+dy/2,t),(x-dx/2,y+dy/2,t)])
ax.add_collection3d(Poly3DCollection(q,facecolor='#c9d3df',edgecolor='none'))
for L in loops: ax.plot(L[:,0],L[:,1],t,color='k',lw=.5); ax.plot(L[:,0],L[:,1],0,color='#333',lw=.3)
ax.set_xlim(xs.min(),xs.max());ax.set_ylim(ys.min(),ys.max());ax.set_zlim(-20,26)
ax.set_box_aspect((np.ptp(xs),np.ptp(ys),46));ax.view_init(38,-60);ax.set_axis_off()
mt=d['metrics']
ax.set_title(f"wave27 g3_tip+00_t60_tt3 — 3D CAD (phenotype solid, t={t:.1f} mm Ti-6Al-4V)\nG 0.980 | {mt['mass_g']:.1f} g | ring 25.46 mm | jarambit v0.27.0",fontsize=10)
plt.savefig('wave27_g3_tip+00_t60_tt3_STEP_3D.png',dpi=110,bbox_inches='tight')
