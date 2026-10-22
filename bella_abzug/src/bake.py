import numpy as np, os
from PIL import Image, ImageFilter
from scipy import ndimage
from common import *
from raster import raster
exec(open(S+'build.py').read().split('# ---------------- head')[0])  # transforms
meshes=np.load(S+'meshes.npy',allow_pickle=True).item()
import trimesh
# z-buffer in camera image space (half res)
q=0.5; h,w=int(H*q),int(W*q)
allV=[];allF=[];off=0;ids=[]
for i,(k,(Vx,F,UV)) in enumerate(meshes.items()):
    allV.append(Vx);allF.append(F+off);off+=len(Vx);ids.append(np.full(len(Vx),i))
AV=np.concatenate(allV);AF=np.concatenate(allF);ID=np.concatenate(ids)
Pc=to_cam(AV); img2=to_img(Pc)*q
idimg,mask,zb=raster(img2,AF,np.eye(4)[ID].astype(np.float32),(h,w),depth=Pc[:,2])
np.save(S+'zb.npy',zb)
# overlay
cols=np.array([[255,0,0],[0,255,0],[0,0,255],[255,255,0]])
ph=np.asarray(Image.open(IMG).convert('RGB').resize((w,h))).astype(float)
ov=ph.copy(); lab=idimg.argmax(-1)
ov[mask]=0.55*ph[mask]+0.45*cols[lab[mask]]
Image.fromarray(ov.astype(np.uint8)).save(S+'overlay.png')
print('overlay done')

# --------- texture baking ---------
def uvbake(Vx,F,UV,N,tw,th):
    attr=np.concatenate([Vx,N],1).astype(np.float32)
    uvp=np.stack([UV[:,0]*tw,UV[:,1]*th],1)
    img,m,_=raster(uvp,F,attr,(th,tw))
    return img[...,:3],img[...,3:],m
def sample(img,xy):
    x=np.clip(xy[:,0],0,img.shape[1]-1.001); y=np.clip(xy[:,1],0,img.shape[0]-1.001)
    x0=x.astype(int);y0=y.astype(int);fx=(x-x0)[:,None];fy=(y-y0)[:,None]
    return (img[y0,x0]*(1-fx)*(1-fy)+img[y0,x0+1]*fx*(1-fy)+img[y0+1,x0]*(1-fx)*fy+img[y0+1,x0+1]*fx*fy)
def region(x0,x1,y0,y1): return np.median(photo[y0:y1,x0:x1].reshape(-1,3),0)
HAIR=np.array([38,36,35.]); SKIN=region(560,660,1060,1120); HAT=region(250,420,190,260); DRESS=np.array([42,40,40.])
print('skin',SKIN,'hat',HAT)
def fill_dilate(col,w,iters=40):
    # push colors from weighted region outward (normalized blur)
    num=col*w[...,None]; den=w.copy()
    for s_ in [2,4,8,16,32]:
        num=ndimage.gaussian_filter(num,(s_,s_,0)); den=ndimage.gaussian_filter(den,s_)
    return num/np.maximum(den,1e-6)[...,None]
sizes={'head':(2048,1024),'brim':(1024,256),'crown':(512,128),'bust':(2048,1024)}
texs={}
rng=np.random.default_rng(1)
for name,(Vx,F,UV) in meshes.items():
    N=np.array(trimesh.Trimesh(Vx,F,process=False).vertex_normals)
    tw,th_=sizes[name]
    pos,nor,m=uvbake(Vx,F,UV,N,tw,th_)
    p=pos.reshape(-1,3); nn=nor.reshape(-1,3); nn/=np.maximum(np.linalg.norm(nn,axis=1,keepdims=True),1e-9)
    pc=to_cam(p); ncam=nn@R.T
    xy=to_img(pc)
    zz=sample(np.where(np.isfinite(zb),zb,-1e9)[...,None],xy*q)[:,0]
    inimg=(xy[:,0]>2)&(xy[:,0]<W-3)&(xy[:,1]>2)&(xy[:,1]<H-3)
    vis=(pc[:,2]>=zz-12)&inimg
    col=sample(photo,xy)
    if name in('brim','crown'):
        wgt=np.zeros(len(p))
    else:
        wgt=np.clip((ncam[:,2]-0.12)/0.3,0,1)*vis
    if name=='head':
        lum=col.mean(1)
        side=(ncam[:,2]<0.55)&(p[:,1]>-6)&(lum>140)&(p[:,2]<1.0)
        wgt=np.where(side,0,wgt)
    wgt=wgt.reshape(th_,tw); col=col.reshape(th_,tw,3)
    wgt=ndimage.gaussian_filter(ndimage.grey_erosion(wgt,size=5),2.5)
    # base colors
    pu=p.reshape(th_,tw,3)
    if name=='head':
        y=pu[...,1]; z=pu[...,2]
        hairness=np.clip((y-(-3.0))/3.0,0,1)
        hairness=np.maximum(hairness,np.clip((-z-4)/3,0,1)*np.clip((y+8)/3,0,1))
        base=HAIR*hairness[...,None]+SKIN*0.85*(1-hairness[...,None])
        noise=ndimage.gaussian_filter(rng.normal(0,1,(th_,tw)),1.0)*14*hairness
        base=base+noise[...,None]
        ext=fill_dilate(col,wgt)
        dist_w=ndimage.gaussian_filter(wgt,25)
        base=base*(1-np.clip(dist_w*2,0,0.6))[...,None]+ext*np.clip(dist_w*2,0,0.6)[...,None]
    elif name=='bust':
        y=pu[...,1]; x=pu[...,0]; z=pu[...,2]; ZCm=-3.3
        # polka dot dress
        u=np.arctan2(x,z-ZCm)*13.0; v=y
        d=np.sin(u*2.1)*np.sin(v*2.1)
        dots=np.clip((np.abs(np.cos(u*1.6)*np.cos(v*1.6))-0.82)*8,0,1)
        dress=DRESS*(1-dots[...,None])+np.array([225,225,222.])*dots[...,None]
        neck=np.clip((y+13.5)/2,0,1)[...,None]
        base=SKIN*0.9*neck+dress*(1-neck)
    else:
        base=np.broadcast_to(HAT,(th_,tw,3)).copy()
        shade=ndimage.gaussian_filter(rng.normal(0,1,(th_,tw)),1.5)*6
        base=base+shade[...,None]
        if name=='crown': base=base*0.95
    out=col*wgt[...,None]+base*(1-wgt[...,None])
    # pad: fill empty texels to avoid seams
    mm=m
    if (~mm).any():
        idx=ndimage.distance_transform_edt(~mm,return_distances=False,return_indices=True)
        out=out[idx[0],idx[1]]
    texs[name]=Image.fromarray(np.clip(out,0,255).astype(np.uint8))
    texs[name].save(S+f'tex_{name}.jpg',quality=88)
    print(name,'done')
