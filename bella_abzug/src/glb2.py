import numpy as np, json, struct, trimesh, pickle, sys
from common import S
meshes,meta=pickle.load(open(S+'scene2.pkl','rb'))
out_path=sys.argv[1] if len(sys.argv)>1 else S+'bella2.glb'
allV=np.concatenate([v[0] for v in meshes.values()])
ctr=(allV.min(0)+allV.max(0))/2
bin_=bytearray(); views=[]; acc=[]; gm=[]; mats=[]; texs=[]; imgs=[]; nodes=[]
def add_view(b,target=None):
    while len(bin_)%4: bin_.append(0)
    o=len(bin_); bin_.extend(b); v={'buffer':0,'byteOffset':o,'byteLength':len(b)}
    if target: v['target']=target
    views.append(v); return len(views)-1
def add_acc(arr,ctype,typ,target,minmax=False):
    vi=add_view(arr.tobytes(),target)
    a={'bufferView':vi,'componentType':ctype,'count':int(arr.shape[0]) if arr.ndim>1 else int(arr.size),'type':typ}
    if minmax: a['min']=arr.min(0).tolist(); a['max']=arr.max(0).tolist()
    acc.append(a); return len(acc)-1
for name,(V,F,UV) in meshes.items():
    Vm=((V-ctr)/100.0).astype(np.float32)
    N=np.array(trimesh.Trimesh(Vm,F,process=False).vertex_normals,dtype=np.float64)
    ln=np.linalg.norm(N,axis=1); bad=~np.isfinite(ln)|(ln<1e-6)
    if bad.any():
        d=Vm[bad]-Vm.mean(0); dl=np.linalg.norm(d,axis=1,keepdims=True)
        N[bad]=np.where(dl>1e-9,d/np.maximum(dl,1e-9),np.array([0,1.,0]))
    N=(N/np.linalg.norm(N,axis=1,keepdims=True)).astype(np.float32)
    pa=add_acc(Vm,5126,'VEC3',34962,True); na=add_acc(N,5126,'VEC3',34962); ua=add_acc(UV.astype(np.float32),5126,'VEC2',34962)
    if len(V)<65536: ia=add_acc(F.astype(np.uint16).ravel(),5123,'SCALAR',34963)
    else: ia=add_acc(F.astype(np.uint32).ravel(),5125,'SCALAR',34963)
    iv=add_view(open(S+f'tex2_{name}.jpg','rb').read())
    imgs.append({'bufferView':iv,'mimeType':'image/jpeg'}); texs.append({'source':len(imgs)-1,'sampler':0})
    mats.append({'name':name,'pbrMetallicRoughness':{'baseColorTexture':{'index':len(texs)-1},'metallicFactor':0.0,'roughnessFactor':0.9},
                 'extensions':{'KHR_materials_unlit':{}}})
    gm.append({'name':name,'primitives':[{'attributes':{'POSITION':pa,'NORMAL':na,'TEXCOORD_0':ua},'indices':ia,'material':len(mats)-1}]})
    nodes.append({'name':name,'mesh':len(gm)-1})
while len(bin_)%4: bin_.append(0)
g={'asset':{'version':'2.0','generator':'photo-fitted head builder'},'extensionsUsed':['KHR_materials_unlit'],'scene':0,
   'scenes':[{'name':'Bella Abzug','nodes':[len(nodes)]}],
   'nodes':nodes+[{'name':'BellaAbzug','children':list(range(len(nodes)))}],'meshes':gm,'materials':mats,'textures':texs,'images':imgs,
   'samplers':[{'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':33071}],'accessors':acc,'bufferViews':views,'buffers':[{'byteLength':len(bin_)}]}
j=json.dumps(g,separators=(',',':')).encode()
while len(j)%4: j+=b' '
out=struct.pack('<III',0x46546C67,2,12+8+len(j)+8+len(bin_))+struct.pack('<II',len(j),0x4E4F534A)+j+struct.pack('<II',len(bin_),0x004E4942)+bytes(bin_)
open(out_path,'wb').write(out); print(out_path,len(out))
