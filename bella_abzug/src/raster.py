import numpy as np
def raster(P2, F, attr, size, depth=None, zbuf=None):
    """P2: (N,2) pixel coords, F (T,3), attr (N,k); depth (N,) larger=closer; returns img (h,w,k), mask"""
    h,w=size; k=attr.shape[1]
    out=np.zeros((h,w,k),np.float32); mask=np.zeros((h,w),bool)
    zb=np.full((h,w),-np.inf) if depth is not None else None
    tri=P2[F]
    mn=np.floor(tri.min(1)).astype(int); mx=np.ceil(tri.max(1)).astype(int)
    for i in range(len(F)):
        x0,y0=max(mn[i,0],0),max(mn[i,1],0); x1,y1=min(mx[i,0],w-1),min(mx[i,1],h-1)
        if x0>x1 or y0>y1: continue
        a,b,c=tri[i]
        xs,ys=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        det=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(det)<1e-12: continue
        l0=((b[1]-c[1])*(xs-c[0])+(c[0]-b[0])*(ys-c[1]))/det
        l1=((c[1]-a[1])*(xs-c[0])+(a[0]-c[0])*(ys-c[1]))/det
        l2=1-l0-l1
        m=(l0>=-1e-4)&(l1>=-1e-4)&(l2>=-1e-4)
        if not m.any(): continue
        f=F[i]
        val=l0[...,None]*attr[f[0]]+l1[...,None]*attr[f[1]]+l2[...,None]*attr[f[2]]
        sub=(slice(y0,y1+1),slice(x0,x1+1))
        if depth is not None:
            z=l0*depth[f[0]]+l1*depth[f[1]]+l2*depth[f[2]]
            m=m&(z>zb[sub]); zb[sub]=np.where(m,z,zb[sub])
        out[sub]=np.where(m[...,None],val,out[sub]); mask[sub]|=m
    return out,mask,zb
