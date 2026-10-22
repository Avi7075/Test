import numpy as np
S='/tmp/claude-0/-home-user-Test/3a0a4803-ad4f-5cb4-8388-66ccf635481c/scratchpad/'
IMG='/tmp/claude-0/-home-user-Test/3a0a4803-ad4f-5cb4-8388-66ccf635481c/images/1.jpg'
def load_canon():
    V=[];F=[];VT=[]
    for l in open(S+'models/canonical_face_model.obj'):
        p=l.split()
        if not p: continue
        if p[0]=='v': V.append([float(x) for x in p[1:4]])
        if p[0]=='f': F.append([int(x.split('/')[0])-1 for x in p[1:4]])
    return np.array(V),np.array(F)
def cam_lm():
    lm=np.load(S+'lm.npy')
    P=np.stack([lm[:,0],-lm[:,1],-lm[:,2]],1)
    return P
def procrustes(A,B):
    # find s,R,t: B ~ s R A + t
    ma,mb=A.mean(0),B.mean(0);A0=A-ma;B0=B-mb
    U,s,Vt=np.linalg.svd(B0.T@A0)
    D=np.eye(3);D[2,2]=np.sign(np.linalg.det(U@Vt))
    R=U@D@Vt; sc=(s*np.diag(D)).sum()/(A0**2).sum()
    return sc,R,mb-sc*R@ma
