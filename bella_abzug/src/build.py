import numpy as np, trimesh, json, struct, io
from PIL import Image
from scipy.spatial import Delaunay
from common import *

photo=np.asarray(Image.open(IMG).convert('RGB')).astype(np.float32)
H,W=photo.shape[:2]
V,Fc=load_canon(); P=cam_lm(); s,R,t=procrustes(V,P[:468])
def to_cam(X): return s*X@R.T+t           # upright cm -> camera px (y up)
def to_up(Pc): return (Pc-t)@R/s
def to_img(Pc): return np.stack([Pc[:,0],-Pc[:,1]],1)
Fu=to_up(P[:468])

def grid_faces(nu,nv):
    idx=np.arange(nu*nv).reshape(nv,nu)
    a=idx[:-1,:-1].ravel();b=idx[:-1,1:].ravel();c=idx[1:,:-1].ravel();d=idx[1:,1:].ravel()
    return np.concatenate([np.stack([a,c,b],1),np.stack([b,c,d],1)])

def vnormals(Vx,F):
    m=trimesh.Trimesh(Vx,F,process=False); return np.array(m.vertex_normals)

# ---------------- head ----------------
C=np.array([0,1.6,-3.2])
NU,NV=181,121
th=np.linspace(-np.pi,np.pi,NU); ph=np.linspace(-np.pi/2,np.pi/2,NV)
TH,PH=np.meshgrid(th,ph)
D=np.stack([np.cos(PH)*np.sin(TH),np.sin(PH),np.cos(PH)*np.cos(TH)],-1).reshape(-1,3)
ax=8.0; by=np.where(D[:,1]>0,12.2,9.6); cz=np.where(D[:,2]>0,9.3,10.2)
re=1/np.sqrt((D[:,0]/ax)**2+(D[:,1]/by)**2+(D[:,2]/cz)**2)
fm=trimesh.Trimesh(Fu,Fc,process=False)
fm=fm.subdivide_loop(2)
loc,ri,ti=fm.ray.intersects_location(np.repeat(C[None],len(D),0),D,multiple_hits=False)
rf=np.full(len(D),np.nan); rf[ri]=np.linalg.norm(loc-C,axis=1)
hit=~np.isnan(rf)
delta=np.zeros(len(D)); delta[hit]=rf[hit]-re[hit]
# fill holes / blend
uvp=np.stack([TH.ravel(),PH.ravel()],1)
hull=Delaunay(uvp[hit]); inside=hull.find_simplex(uvp)>=0
dg=delta.reshape(NV,NU); hg=hit.reshape(NV,NU); ig=inside.reshape(NV,NU)
decay=np.where(ig,1.0,0.93)
for it in range(1500):
    p=np.pad(dg,1,mode='edge'); avg=(p[:-2,1:-1]+p[2:,1:-1]+p[1:-1,:-2]+p[1:-1,2:])/4
    dg=np.where(hg,dg,avg*decay)
r=re+dg.ravel()
Vh=C+D*r[:,None]
Fh=grid_faces(NU,NV)[:,::-1]
# texture coords: warp to give front more texels
def warp_u(x): return 0.5+0.5*np.sign(x)*(np.abs(x)/np.pi)**0.6
def warp_v(y): return 0.5-0.5*np.sign(y)*(np.abs(y)/(np.pi/2))**0.8
UVh=np.stack([warp_u(TH.ravel()),warp_v(PH.ravel())],1)

# ---------------- hat ----------------
alpha=np.radians(float(__import__('os').environ.get('HAT_A','48')))
n=np.array([0,np.cos(alpha),-np.sin(alpha)])
e1=np.array([1,0,0]); e2=np.cross(n,e1)  # e2 points toward -z-ish/up
front=Fu[10]+np.array([0,float(__import__('os').environ.get('HAT_UP','2.5')),-0.6])
hb_a,hb_b=8.6,10.4   # headband semi axes (x, e2)
# center so front point lies on headband ellipse at angle pointing to front
dirfront=-e2 if (-e2)[2]>0 else e2
hc=front-dirfront*hb_b
hc=hc-n*np.dot(hc-front,n)
R_out=float(__import__('os').environ.get('HAT_R','13.8'))
NA=160
ang=np.linspace(0,2*np.pi,NA+1)
def ring(scale_a,scale_b,off,droop=0):
    return hc[None]+np.cos(ang)[:,None]*scale_a*e1+np.sin(ang)[:,None]*scale_b*e2+n*off
rows=[]
nb=10
for k in range(nb+1):
    f=k/nb
    a=hb_a+(R_out-hb_a)*f; b=hb_b+(R_out*1.12-hb_b)*f
    droop=-0.9*f**2
    rows.append(ring(a,b,droop))
Vb=np.concatenate(rows); Fb=grid_faces(NA+1,nb+1)
UVb=np.stack([np.tile(ang/(2*np.pi),nb+1),np.repeat(np.linspace(0,1,nb+1),NA+1)],1)
rows=[]; ncr=14; crown_h=7.0
for k in range(ncr+1):
    f=k/ncr
    sc=np.sqrt(max(1-f**3,0))*0.95+0.05 if f>0 else 1
    sc=1-0.25*f**2 if f<1 else 0.0
    rows.append(ring(hb_a*sc,hb_b*sc,crown_h*np.sin(f*np.pi/2)))
Vcr=np.concatenate(rows); Fcr=grid_faces(NA+1,ncr+1)[:,::-1]
UVcr=np.stack([np.tile(ang/(2*np.pi),ncr+1),np.repeat(np.linspace(0,1,ncr+1),NA+1)],1)

# ---------------- bust ----------------
# cross sections: (y, half width x, half depth z, z center)
secs=[(-3,5.0,4.6,-3.4),(-8,5.6,5.0,-3.0),(-12.5,5.9,5.4,-2.6),(-15.5,9.5,7.4,-2.8),(-18,17,9,-3.2),(-21,22,10,-3.6),(-26,24,11,-3.6),(-36,24,11.5,-3.4),(-48,24,11.5,-3.4)]
NB=121; tb=np.linspace(-np.pi,np.pi,NB)
ys=np.array([s_[0] for s_ in secs]); hs=np.linspace(0,1,len(secs))
# interpolate finely
fine=np.linspace(0,1,40)
def interp(i): return np.interp(fine,hs,np.array([s_[i] for s_ in secs]))
Y,AX,DZ,ZC=interp(0),interp(1),interp(2),interp(3)
rows=[]
for k in range(len(fine)):
    e=2.0+1.2*(AX[k]>8)  # superellipse exponent
    x=np.sign(np.sin(tb))*np.abs(np.sin(tb))**(2/ (e+1)) *AX[k]
    z=np.sign(np.cos(tb))*np.abs(np.cos(tb))**(2/(e+1))*DZ[k]+ZC[k]
    rows.append(np.stack([x,np.full(NB,Y[k]),z],1))
Vs=np.concatenate(rows); Fs=grid_faces(NB,len(fine))
UVs=np.stack([np.tile(0.5+tb/(2*np.pi),len(fine)),np.repeat(fine,NB)],1)

# keep head inside crown
rel=Vh-hc; hn=rel@n; hx=rel@e1; hy=rel@e2
Vh=np.where((hn>crown_h-1.2)[:,None],Vh-n*(hn-(crown_h-1.2))[:,None],Vh); rel=Vh-hc; hn=rel@n
fl=2/np.pi*np.arcsin(np.clip(hn/crown_h,0,1)); loc=(1-0.25*fl**2)*0.95
ell=np.sqrt((hx/(hb_a*loc))**2+(hy/(hb_b*loc))**2)
m=(hn>-1.0)&(ell>1)
k=np.clip((hn+1.0)/1.0,0,1)
sc=np.where(m,1/ell,1); sc=1-(1-sc)*k
Vh=hc+n*hn[:,None]+(e1*(hx*sc)[:,None]+e2*(hy*sc)[:,None])
Vh=np.where(m[:,None],Vh,hc+rel)
meshes={'head':(Vh,Fh,UVh),'brim':(Vb,Fb,UVb),'crown':(Vcr,Fcr,UVcr),'bust':(Vs,Fs,UVs)}
np.save(S+'meshes.npy',np.array(meshes,dtype=object),allow_pickle=True)
print({k:(len(v[0]),len(v[1])) for k,v in meshes.items()})
