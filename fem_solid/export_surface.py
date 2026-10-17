"""Preserve the actual exported CAD skin while refining its solid submodel."""
import numpy as np


def load_surface(surface):
    if surface.get('schema')!='jarambit.export_surface.v1':raise ValueError('unsupported exported surface')
    vertices=np.asarray(surface['verts'],float);tris=np.asarray(surface['tris'],int)
    if vertices.ndim!=2 or vertices.shape[1]!=3 or tris.ndim!=2 or tris.shape[1]!=3:
        raise ValueError('invalid exported surface arrays')
    if not len(tris) or tris.min()<0 or tris.max()>=len(vertices) or not np.isfinite(vertices).all():
        raise ValueError('invalid exported surface topology')
    if np.any(vertices[np.unique(tris),2]<=0):raise ValueError('source must contain the actual upper CAD skin')
    return vertices[:,:2],tris,2.0*vertices[:,2]


def refine(xy,tris,cut,heights):
    edges={};points=list(xy);cuts=list(cut);newh=list(heights) if heights is not None else None;refined=[]
    def mid(a,b):
        key=(min(a,b),max(a,b))
        if key not in edges:
            edges[key]=len(points);points.append((xy[a]+xy[b])/2.0);cuts.append(cut[a] and cut[b])
            if newh is not None:newh.append((heights[a]+heights[b])/2.0)
        return edges[key]
    for a,b,c in tris:
        ab,bc,ca=mid(a,b),mid(b,c),mid(c,a)
        refined.extend([(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)])
    return np.asarray(points),np.asarray(refined),np.asarray(cuts),np.asarray(newh) if newh is not None else None
