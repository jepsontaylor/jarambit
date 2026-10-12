import numpy as np,re,matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
v=np.array(re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)',open('g3_tip+00_t60_tt3.stl').read()),float).reshape(-1,3,3)
n=np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]+1e-12
L=np.array([-.4,-.5,.77]);sh=np.clip(np.abs(n@L),0,1)
cx=v[:,:,0].mean(1);c=plt.cm.plasma((cx-cx.min())/np.ptp(cx));c[:,:3]*=(.35+.65*sh)[:,None]
fig=plt.figure(figsize=(12,6),facecolor='#0d1117');ax=fig.add_subplot(111,projection='3d',facecolor='#0d1117')
ax.add_collection3d(Poly3DCollection(v,facecolors=c,edgecolor='none'))
mn,mx=v.reshape(-1,3).min(0),v.reshape(-1,3).max(0);ax.set_xlim(mn[0],mx[0]);ax.set_ylim(mn[1],mx[1]);ax.set_zlim(mn[2]-15,mx[2]+15)
ax.set_box_aspect((mx[0]-mn[0],mx[1]-mn[1],36));ax.view_init(40,-62);ax.set_axis_off()
ax.set_title('jarambit v0.27.0 — g3_tip+00_t60_tt3 (watertight STEP, Ti-6Al-4V 6.0 mm)\nG1 0.9805 · tip×SPG 6.362 · 84.80 g · ring 25.46 mm',color='w',fontsize=13)
plt.savefig('wave27_g3_tip+00_t60_tt3_STEP_3D.png',dpi=120,bbox_inches='tight',facecolor='#0d1117')
