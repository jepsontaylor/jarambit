#!/usr/bin/env python3
"""SWITCHBACK Rev C.9.2 drawing set 00-09 generated directly from the C.9.2 B-rep STEP (sha16 2ad2a8ecaf4fca67).
jarambit copy (PR-0.32.0e review): paths are relative to designs/switchback/C9.2; fixes vs the W75 pack generator:
 07 plots the current governor (V6 a1, W75.1, from data/w75_1_results.json) and marks the W74 V3 point historical;
 08 thickness map masked to the real mid-plane material footprint (holes and exterior empty);
 06 hero camera zoom reduced until every projected vertex lies inside the axes;
 04 left panel fitted to the inner-edge rope scallops; both panels checked to contain scallops.
Run from designs/switchback/C9.2: python drawings/draw_c92.py  (needs cadquery, matplotlib, scipy, shapely). C.8 overlay (05) needs
the C.8 STEP from the hiking-karambit repo via C8_STEP=...; 05 is not regenerated otherwise."""
import os, json, hashlib, numpy as np, cadquery as cq, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
ST="cad/switchback_revC9_2_ground.step"; C8=os.environ.get("C8_STEP", "")
SHA=hashlib.sha256(open(ST,"rb").read()).hexdigest(); OUT="drawings"; os.makedirs(OUT,exist_ok=True); IN=25.4
S=cq.importers.importStep(ST); SOL=S.val(); MASS=SOL.Volume()*4.43e-3; BB=SOL.BoundingBox()
TB=f"SWITCHBACK Rev C.9.2 RELEASE CANDIDATE (not design of record)  |  Gr5 Ti  {MASS:.3f} g  |  STEP sha256 {SHA[:16]}  |  generated from B-rep (W75)  |  units mm"
def save(fig,n,svg=True):
    fig.text(0.01,0.005,TB,fontsize=6,color="#444"); fig.savefig(f"{OUT}/{n}.png",dpi=200)
    if svg: fig.savefig(f"{OUT}/{n}.svg")
    plt.close(fig)
def tess(sol,tol=0.05):
    v,t=sol.tessellate(tol,0.2); v=np.array([[p.x,p.y,p.z] for p in v]); return v,np.array(t)
def zsec(sol,z=0.0):
    w=cq.Workplane().add(sol).section(z) if False else None
    pl=cq.Face.makePlane(400,400,basePnt=(100,0,z),dir=(0,0,1)); sec=sol.intersect(cq.Solid.makeBox(400,400,1e-3,pnt=cq.Vector(-100,-200,z)))
    return sec
def silhouette(sol):  # outer profile: z-projection of tessellation
    v,t=tess(sol,0.03); return v,t
V,T=tess(SOL,0.02); n=np.cross(V[T[:,1]]-V[T[:,0]],V[T[:,2]]-V[T[:,0]]); nn=n/np.linalg.norm(n,axis=1)[:,None]
top=nn[:,2]>0.05; bot=nn[:,2]<-0.05
def section_edges(sol,plane):  # plane: ("x",x0) or ("z",z0) -> list of polylines
    o,d={"x":((plane[1],0,0),(1,0,0)),"z":((0,0,plane[1]),(0,0,1)),"y":((0,plane[1],0),(0,1,0))}[plane[0]]
    f=cq.Face.makePlane(1000,1000,basePnt=o,dir=d); sec=sol.intersect(f); pls=[]
    for e in sec.Edges():
        pts=[e.positionAt(u) for u in np.linspace(0,1,40)]; pls.append(np.array([[p.x,p.y,p.z] for p in pts]))
    return pls
def draw_profile(ax,lw=.6,col="#c9ced6",ec="k"):
    ax.add_collection(PolyCollection(V[T[top]][:,:,:2],facecolor=col,edgecolor="none"))
    for p in section_edges(SOL,("z",0.0)): ax.plot(p[:,0],p[:,1],ec,lw=lw)
    ax.set_aspect("equal"); ax.autoscale()
Z0=section_edges(SOL,("z",0.0)); allp=np.vstack(Z0); xmin,xmax=allp[:,0].min(),allp[:,0].max(); ymin,ymax=allp[:,1].min(),allp[:,1].max()
tip=allp[np.argmax(allp[:,0])]
# 01 side profile
fig,ax=plt.subplots(figsize=(14,6)); draw_profile(ax); ax.set_title("01 Side profile (mid-plane section z=0 + top-face fill), Rev C.9.2")
ax.annotate("",(xmin,ymin-6),(xmax,ymin-6),arrowprops=dict(arrowstyle="<->")); ax.text((xmin+xmax)/2,ymin-9,f"OAL {xmax-xmin:.1f} mm ({(xmax-xmin)/IN:.2f}\")",ha="center")
ax.annotate("",(xmax+6,ymin),(xmax+6,ymax),arrowprops=dict(arrowstyle="<->")); ax.text(xmax+8,(ymin+ymax)/2,f"H {ymax-ymin:.1f} mm",rotation=90,va="center")
ax.plot(*tip[:2],"r+",ms=10); ax.text(tip[0],tip[1]+3,f"point ({tip[0]:.1f},{tip[1]:.1f})",color="r",fontsize=7)
ax.plot(0,0,"b+",ms=10); ax.text(1,1,"ring centre (0,0)",color="b",fontsize=7); ax.grid(alpha=.2); ax.set_xlim(xmin-10,xmax+20); ax.set_ylim(ymin-14,ymax+8); save(fig,"01_side_profile")
# thickness map from tessellation: barycentric top z minus bottom z on grid
from matplotlib.tri import Triangulation, LinearTriInterpolator
from scipy.interpolate import griddata
gx,gy=np.meshgrid(np.linspace(xmin,xmax,900),np.linspace(ymin,ymax,320))
def facez(mask,agg):
    c=V[T[mask]].mean(1); return griddata(c[:,:2],c[:,2],(gx,gy),method="linear")
from matplotlib.path import Path
ins=np.zeros(gx.shape,bool); pts=np.c_[gx.ravel(),gy.ravel()]
from shapely.geometry import Polygon
import shapely
TH=facez(top,max)-facez(bot,min)
# material footprint = xy coverage of the top-face triangles (holes/exterior have no triangles -> empty)
from PIL import Image, ImageDraw
_W,_H=gx.shape[1],gx.shape[0]; _im=Image.new("1",(_W,_H),0); _d=ImageDraw.Draw(_im)
_px=lambda x,y:((x-xmin)/(xmax-xmin)*(_W-1),(y-ymin)/(ymax-ymin)*(_H-1))
for t in T: _d.polygon([_px(*V[i,:2]) for i in t],fill=1)
MAT=np.array(_im,bool)
def _m(x,y): i=int(round((y-ymin)/(ymax-ymin)*(_H-1))); j=int(round((x-xmin)/(xmax-xmin)*(_W-1))); return 0<=i<_H and 0<=j<_W and bool(MAT[i,j])
for xy in ((0,0),(35,0),(130,-30)): print("mask check",xy,"material" if _m(*xy) else "empty")
assert not _m(0,0), "ring bore must be empty"
TH=np.ma.masked_invalid(np.where((TH>0.05)&MAT,TH,np.nan))
# 02 top/edge view: max thickness envelope along x + spine/edge
fig,(a1,a2)=plt.subplots(2,1,figsize=(14,6),gridspec_kw=dict(height_ratios=[1,1.4]))
xs=gx[0]; tmax=np.nanmax(np.ma.filled(TH,np.nan),axis=0)
a1.fill_between(xs,-tmax/2,tmax/2,color="#c9ced6",ec="k",lw=.5); a1.set_aspect(4); a1.set_title("02 Edge (top) view: max thickness envelope vs x (z exaggerated 4x)"); a1.set_ylabel("z mm"); a1.grid(alpha=.3)
for x0 in (40,80,95,120,160,175,182):
    i=np.argmin(abs(xs-x0)); a1.annotate(f"{tmax[i]:.2f}",(x0,tmax[i]/2),fontsize=6,ha="center",va="bottom")
a2.plot(xs,tmax,"k"); a2.set_xlabel("x mm (from ring centre)"); a2.set_ylabel("max t mm"); a2.grid(alpha=.3); a2.axvspan(80,95,color="y",alpha=.2,label="core ramp 3.175→4.5")
a2.axvspan(160,182,color="r",alpha=.15,label="tip-zone edge flat 0.5→1.45 (C.9.2)"); a2.legend(fontsize=7); save(fig,"02_top_edge_view")
# 03 cross sections
STA=[25,45,72,88,100,120,140,160,172,180]; fig,axs=plt.subplots(2,5,figsize=(16,7))
for ax,x0 in zip(axs.flat,STA):
    for p in section_edges(SOL,("x",x0)): ax.plot(p[:,1],p[:,2],"k",lw=.7)
    ax.set_aspect("equal"); ax.set_title(f"x = {x0}",fontsize=8); ax.grid(alpha=.3); ax.tick_params(labelsize=6)
fig.suptitle("03 Cross sections (y–z) at x stations, cut from B-rep"); save(fig,"03_cross_sections")
# 04 serration detail: zoomed profile of both edges
fig,axs=plt.subplots(1,2,figsize=(14,6))
for ax,(x0,x1,ttl) in zip(axs,((100,155,"inside edge / rope scallops"),(95,185,"spine FINE scallops"))):
    for p in Z0: ax.plot(p[:,0],p[:,1],"k",lw=.6)
    ax.set_aspect("equal"); ax.grid(alpha=.3); ax.set_title(ttl)
lo=allp[allp[:,0]>95]; axs[0].set_xlim(100,155); axs[0].set_ylim(-30,-6); axs[1].set_xlim(95,185); axs[1].set_ylim(lo[:,1].max()-30,lo[:,1].max()+2)
def scallops(xa,ya):  # count local y-extrema of outline points inside the window (teeth)
    n=0
    for p in Z0:
        q=p[(p[:,0]>xa[0])&(p[:,0]<xa[1])&(p[:,1]>ya[0])&(p[:,1]<ya[1])]
        if len(q)>4: d=np.sign(np.diff(q[:,1])); n+=int((np.diff(d[d!=0])!=0).sum())
    return n
for ax,nm in zip(axs,("inside","spine")):
    k=scallops(ax.get_xlim(),ax.get_ylim()); print("04",nm,"extrema",k); assert k>=4, f"04 {nm} panel shows no scallops"
fig.suptitle("04 Serration detail (mid-plane section)"); save(fig,"04_serration_detail")
# 05 C.8 vs C.9.2 overlay (only with C8_STEP; the committed 05 is kept otherwise)
fig,ax=plt.subplots(figsize=(14,6)) if C8 else (None,None)
if C8:
    S8=cq.importers.importStep(C8).val(); m8=S8.Volume()*4.43e-3
    for p in section_edges(S8,("z",0.0)): ax.plot(p[:,0],p[:,1],"b",lw=.6)
    for p in Z0: ax.plot(p[:,0],p[:,1],"r",lw=.6)
    ax.plot([],[],"b",label=f"Rev C.8 (prev. of record) {m8:.2f} g"); ax.plot([],[],"r",label=f"Rev C.9.2 {MASS:.3f} g"); ax.legend(); ax.set_aspect("equal"); ax.grid(alpha=.2)
    ax.set_title("05 Rev C.8 vs Rev C.9.2 mid-plane outline overlay"); save(fig,"05_revC8_vs_revC9_2")
# 06 hero render: shaded tessellation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
L=np.array([-.4,.5,.75]); L/=np.linalg.norm(L); sh=np.clip(nn@L,0,1)*.75+.2
fig=plt.figure(figsize=(14,7),facecolor="#1b1d22"); ax=fig.add_subplot(111,projection="3d",facecolor="#1b1d22")
ax.add_collection3d(Poly3DCollection(V[T],facecolors=plt.cm.bone(sh*.9+.05),edgecolors="none"))
ax.set_xlim(xmin,xmax); ax.set_ylim(ymin,ymax); ax.set_zlim(-6,6); ax.view_init(62,-80); ax.set_axis_off()
from mpl_toolkits.mplot3d import proj3d
for zoom in np.arange(1.4,0.5,-0.05):
    ax.set_box_aspect((xmax-xmin,ymax-ymin,12),zoom=zoom); fig.canvas.draw()
    px,py,_=proj3d.proj_transform(V[:,0],V[:,1],V[:,2],ax.get_proj()); P=ax.transData.transform(np.c_[px,py]); bb=ax.bbox
    if P[:,0].min()>=bb.x0+8 and P[:,0].max()<=bb.x1-8 and P[:,1].min()>=bb.y0+8 and P[:,1].max()<=bb.y1-8: break
print("06 zoom",round(float(zoom),2))
fig.text(.5,.92,f"SWITCHBACK Rev C.9.2  —  {MASS:.2f} g titanium",color="w",ha="center",fontsize=16); save(fig,"06_hero_render",svg=False)
# 07 strength vs weight (records from WAVE_LOG / W74 board)
W751=json.load(open("data/w75_1_results.json")); GOV=W751["a1"]["SF_converged_design"]
R=[("C.8",45.71,1.41,"twist (C.8 basis)"),("C.9",66.275,1.302,"W72 corr."),("C.9.1",66.671,1.449,"V2 FAIL"),
   ("C.9.2 (historical W74)",MASS,1.597,"V3 spine — superseded"),("C.9.2 (current, W75.1)",MASS,GOV,f"V6 a1 lateral pry, margin {100*(GOV/1.5-1):.1f} % < 5 % promotion rule")]
fig,ax=plt.subplots(figsize=(10,6))
for r,m,sf,nt in R: ax.scatter(m,sf,s=60,marker="x" if "historical" in r else "o"); ax.annotate(f"{r}\n{nt}",(m,sf),fontsize=7,xytext=(-6 if "C.9.2" in r else 4,4 if "current" not in r else -22),ha="right" if "C.9.2" in r else "left",textcoords="offset points")
ax.axhline(1.5,color="r",ls="--",lw=.8,label="V-gate SF 1.5 (W69 human-max loads)"); ax.set_xlabel("mass g (Gr5)"); ax.set_ylabel("governing SF")
ax.set_title("07 Strength vs weight — note C.8 SF is on the pre-W69 load basis, not comparable"); ax.legend(); ax.grid(alpha=.3); save(fig,"07_strength_vs_weight")
# 08 thickness map
fig,ax=plt.subplots(figsize=(14,6)); im=ax.pcolormesh(gx,gy,TH,cmap="viridis",shading="auto"); plt.colorbar(im,label="local thickness mm")
for p in Z0: ax.plot(p[:,0],p[:,1],"k",lw=.4)
ax.set_aspect("equal"); ax.set_title("08 Ground 3D check — through-thickness map from B-rep tessellation"); save(fig,"08_ground_3d_check",svg=False)
# 09 jimping detail
fig,(a,b)=plt.subplots(1,2,figsize=(14,6))
for p in Z0: a.plot(p[:,0],p[:,1],"k",lw=.8)
a.set_xlim(62,92); a.set_ylim(2,20); a.set_aspect("equal"); a.grid(alpha=.3); a.set_title("thumb-seat jimping (mid-plane)")
for xy,lab in (((73.12,12.89),"V6 a1 hot spot"),((77.05,12.5),"V6 a2 hot spot")): a.plot(*xy,"rx"); a.annotate(lab,xy,fontsize=7,color="r",xytext=(3,-10),textcoords="offset points")
for p in section_edges(SOL,("x",73.12)): b.plot(p[:,1],p[:,2],"k",lw=.8)
b.set_aspect("equal"); b.set_xlim(0,16); b.grid(alpha=.3); b.set_title("section x = 73.12 through notch")
fig.suptitle("09 Jimping detail, Rev C.9.2"); save(fig,"09_jimping_detail")
# 00 sheet
fig,axs=plt.subplots(2,2,figsize=(16,10))
for ax,f in zip(axs.flat,("01_side_profile","02_top_edge_view","08_ground_3d_check","06_hero_render")): ax.imshow(plt.imread(f"{OUT}/{f}.png")); ax.axis("off")
fig.suptitle(f"00 SWITCHBACK Rev C.9.2 concept sheet — {MASS:.3f} g, OAL {xmax-xmin:.1f} mm"); fig.tight_layout(); save(fig,"00_concept_sheet",svg=False)
json.dump(dict(step=ST,sha256=SHA,mass_g=round(MASS,3),OAL=round(xmax-xmin,2),H=round(ymax-ymin,2),point=tip.round(2).tolist(),bbox=[BB.xlen,BB.ylen,BB.zlen]),open(f"{OUT}/draw_meta.json","w"),indent=1)
print("ok",MASS)
