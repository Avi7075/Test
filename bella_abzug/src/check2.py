import numpy as np, pickle, cv2
from PIL import Image
from common import *
from raster import raster
meshes,meta=pickle.load(open(S+'scene2.pkl','rb')); s=meta['s']
q=0.5; H,W=2000,1390; h,w=int(H*q),int(W*q)
allV=[];allF=[];ids=[];off=0
for i,(k,(V,F,UV)) in enumerate(meshes.items()):
    allV.append(V);allF.append(F+off);off+=len(V);ids.append(np.full(len(V),i))
AV=np.concatenate(allV);AF=np.concatenate(allF);ID=np.concatenate(ids)
xy=np.stack([AV[:,0]*s,-AV[:,1]*s],1)*q
nm=len(meshes)
img,mask,zb=raster(xy,AF,np.eye(nm)[ID].astype(np.float32),(h,w),depth=AV[:,2])
cols=np.array([[255,60,60],[60,255,60],[60,160,255],[255,255,0],[255,0,255],[0,255,255]])
ph=np.asarray(Image.open(IMG).convert('RGB').resize((w,h))).astype(float)
ov=ph.copy(); lab=img.argmax(-1)
ov[mask]=0.6*ph[mask]+0.4*cols[lab[mask]]
seg=np.load(S+'seg_cat.npy')[...,0]; seg=cv2.resize(seg,(w,h),interpolation=cv2.INTER_NEAREST)
edges=cv2.Canny((seg*40).astype(np.uint8),10,30)>0
ov[edges]=[255,255,255]
Image.fromarray(ov.astype(np.uint8)).save(S+'overlay2.png')
