import numpy as np, json, struct, trimesh
from common import S
M=np.load(S+'meshes.npy',allow_pickle=True).item()
bin_=bytearray(); views=[]; acc=[]; meshes=[]; mats=[]; texs=[]; imgs=[]; nodes=[]
def add_view(b,target=None):
    while len(bin_)%4: bin_.append(0)
    o=len(bin_); bin_.extend(b); v={'buffer':0,'byteOffset':o,'byteLength':len(b)}
    if target: v['target']=target
    views.append(v); return len(views)-1
def add_acc(arr,ctype,typ,target,minmax=False):
    vi=add_view(arr.tobytes(),target)
    a={'bufferView':vi,'componentType':ctype,'count':len(arr),'type':typ}
    if minmax: a['min']=arr.min(0).tolist(); a['max']=arr.max(0).tolist()
    acc.append(a); return len(acc)-1
for name,(V,F,UV) in M.items():
    V=(V/100.0).astype(np.float32)
    N=np.array(trimesh.Trimesh(V,F,process=False).vertex_normals,dtype=np.float32)
    pa=add_acc(V,5126,'VEC3',34962,True); na=add_acc(N,5126,'VEC3',34962); ua=add_acc(UV.astype(np.float32),5126,'VEC2',34962)
    ia=add_acc(F.astype(np.uint16).ravel(),5123,'SCALAR',34963)
    iv=add_view(open(S+f'tex_{name}.jpg','rb').read())
    imgs.append({'bufferView':iv,'mimeType':'image/jpeg'}); texs.append({'source':len(imgs)-1,'sampler':0})
    mats.append({'name':name,'pbrMetallicRoughness':{'baseColorTexture':{'index':len(texs)-1},'metallicFactor':0.0,'roughnessFactor':0.85},
                 'doubleSided':name in('brim','crown')})
    meshes.append({'name':name,'primitives':[{'attributes':{'POSITION':pa,'NORMAL':na,'TEXCOORD_0':ua},'indices':ia,'material':len(mats)-1}]})
    nodes.append({'name':name,'mesh':len(meshes)-1})
while len(bin_)%4: bin_.append(0)
g={'asset':{'version':'2.0','generator':'custom'},'scene':0,'scenes':[{'nodes':[len(nodes)]}],
   'nodes':nodes+[{'name':'BellaAbzug','children':list(range(len(nodes)))}],'meshes':meshes,'materials':mats,'textures':texs,'images':imgs,
   'samplers':[{'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':33071}],'accessors':acc,'bufferViews':views,'buffers':[{'byteLength':len(bin_)}]}
j=json.dumps(g,separators=(',',':')).encode()
while len(j)%4: j+=b' '
out=struct.pack('<III',0x46546C67,2,12+8+len(j)+8+len(bin_))+struct.pack('<II',len(j),0x4E4F534A)+j+struct.pack('<II',len(bin_),0x004E4942)+bytes(bin_)
open(S+'bella_abzug.glb','wb').write(out); print(len(out))
