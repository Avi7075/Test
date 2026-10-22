import numpy as np, pickle, cv2, trimesh, os
from PIL import Image
from scipy import ndimage
from common import *
from raster import raster

meshes, meta = pickle.load(open(S + 'scene2.pkl', 'rb'))
s, R, tw, y_chin = meta['s'], meta['R'], meta['tw'], meta['y_chin']
photo = np.asarray(Image.open(IMG).convert('RGB')).astype(np.float32)
H, W = photo.shape[:2]
gray = photo.mean(-1)
seg = np.load(S + 'seg_cat.npy')[..., 0]
hm = np.load(S + 'hatmask.npy').astype(np.float32)
def soft(m, sg=2.5): return cv2.GaussianBlur(m.astype(np.float32), (0, 0), sg)
dil = np.ones((17, 17), np.uint8)
hat_soft = soft(cv2.dilate(hm.astype(np.uint8), dil), 4)
bg_soft = soft(cv2.dilate((seg == 0).astype(np.uint8), dil), 4)
hair_light = soft(((seg == 1) & (cv2.GaussianBlur(gray, (0, 0), 1.5) > 105)).astype(np.uint8), 3)
body_ok = np.clip(1 - 1.6 * np.maximum(hat_soft, bg_soft), 0, 1) * np.clip(1 - 1.5 * hair_light, 0, 1)
el = np.load(S + 'brim_ellipse.npy')
ell_in = np.zeros((H, W), np.uint8)
cv2.ellipse(ell_in, ((el[0], el[1]), (el[2] - 22, el[3] - 22), el[4]), 1, -1)
hat_ok = np.clip((soft(cv2.erode(hm.astype(np.uint8), np.ones((7, 7))) * ell_in) - 0.3) / 0.5, 0, 1)
rim_ok = soft(hm * cv2.dilate(ell_in, np.ones((15, 15))), 1.5)

# ---------------- z-buffer (full res, depth = z cm)
allV = []; allF = []; off = 0
for k, (V, F, UV) in meshes.items():
    allV.append(V); allF.append(F + off); off += len(V)
AV = np.concatenate(allV); AF = np.concatenate(allF)
cache = S + 'zb2.npy'
_, _, zb = raster(np.stack([AV[:, 0] * s, -AV[:, 1] * s], 1), AF, np.zeros((len(AV), 1), np.float32), (H, W), depth=AV[:, 2])
zb = np.where(np.isfinite(zb), zb, -1e9).astype(np.float32)

def sample(img, xy):
    x = np.clip(xy[:, 0], 0, img.shape[1] - 1.001); y = np.clip(xy[:, 1], 0, img.shape[0] - 1.001)
    x0 = x.astype(int); y0 = y.astype(int); fx = x - x0; fy = y - y0
    if img.ndim == 2: img = img[..., None]; sq = True
    else: sq = False
    fx = fx[:, None]; fy = fy[:, None]
    v = img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy
    return v[:, 0] if sq else v

def project(p, nrm, ok_mask, tol=0.3):
    xy = np.stack([p[:, 0] * s, -p[:, 1] * s], 1)
    inimg = (xy[:, 0] > 1) & (xy[:, 0] < W - 2) & (xy[:, 1] > 1) & (xy[:, 1] < H - 2)
    zz = sample(zb, xy)
    vis = (p[:, 2] >= zz - tol) & inimg
    wf = np.clip((nrm[:, 2] - 0.2) / 0.35, 0, 1)
    w = wf * vis * (sample(ok_mask, xy) if ok_mask is not None else 1)
    return sample(photo, xy), w

def uvbake(Vx, F, UV, N, tw_, th_, extra=None):
    attr = np.concatenate([Vx, N] + ([extra[:, None]] if extra is not None else []), 1).astype(np.float32)
    img, m, _ = raster(np.stack([UV[:, 0] * tw_, UV[:, 1] * th_], 1), F, attr, (th_, tw_))
    img = img.reshape(-1, attr.shape[1])
    if extra is not None: return img[:, :3], img[:, 3:6], m, img[:, 6]
    return img[:, :3], img[:, 3:6], m

# procedural hair: anisotropic noise tile, 16 cm square, wraps
TILE_CM = 16.0; TN = 1024
_r = np.random.default_rng(11)
n1 = ndimage.gaussian_filter(_r.normal(0, 1, (TN, TN)), (14, 1.6), mode='wrap'); n1 /= n1.std()
n2 = ndimage.gaussian_filter(_r.normal(0, 1, (TN, TN)), (40, 8), mode='wrap'); n2 /= n2.std()
n3 = ndimage.gaussian_filter(_r.normal(0, 1, (TN, TN)), (90, 60), mode='wrap'); n3 /= n3.std()
hair_tile = np.pad(n1 * 0.55 + n2 * 0.35 + n3 * 0.25, ((0, 1), (0, 1)), mode='wrap')
def tile_lookup(U, Vv):
    x = np.mod(U / TILE_CM * TN, TN); y = np.mod(-Vv / TILE_CM * TN, TN)
    return sample(hair_tile, np.stack([x, y], 1))

def tile_patch(patch, u, v):
    """mirror-tiled lookup; u,v in patch pixels"""
    ph_, pw_ = patch.shape[:2]
    def tri(x, n): x = np.mod(x, 2 * (n - 1)); return np.where(x < n - 1, x, 2 * (n - 1) - x)
    return sample(patch, np.stack([tri(u, pw_), tri(v, ph_)], 1))

L = np.array([-0.25, 0.75, 0.6]); L /= np.linalg.norm(L)
def shade(nrm, amb=0.62): return (amb + (1 - amb) * np.clip(nrm @ L, 0, 1))[:, None]

def med(mask): return np.median(photo[mask.astype(bool)], 0)
HAIRC = med(seg == 1); SKINC = med((seg == 2) | (seg == 3))
UNDER = med(cv2.erode(hm.astype(np.uint8), np.ones((25, 25))) & (gray > 40)[..., None].squeeze())
print('hair', HAIRC, 'skin', SKINC, 'brim under', UNDER)
hair_patch = photo[600:950, 250:370]
dress_patch = photo[1500:1900, 1080:1340]
FELT = np.array([214., 212, 208])

def pushpull(col, w):
    num = col * w[..., None]; den = w.copy()
    for sg in [2, 4, 8, 16, 32, 64]:
        num = ndimage.gaussian_filter(num, (sg, sg, 0)); den = ndimage.gaussian_filter(den, sg)
    return num / np.maximum(den, 1e-6)[..., None]

def finish(name, out, m, th_, tw_):
    out = out.reshape(th_, tw_, 3)
    if (~m).any():
        idx = ndimage.distance_transform_edt(~m, return_distances=False, return_indices=True)
        out = out[idx[0], idx[1]]
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(S + f'tex2_{name}.jpg', quality=int(os.environ.get('JQ', 87)))

sizes = {'body': (2048, 2048), 'brim_under': (2048, 256), 'brim_top': (512, 128), 'brim_rim': (1024, 16),
         'crown_out': (512, 256), 'crown_in': (512, 128)}
rng = np.random.default_rng(3)
for name, (Vx, F, UV) in meshes.items():
    N = np.array(trimesh.Trimesh(Vx, F, process=False).vertex_normals)
    tw_, th_ = sizes[name]
    if name == 'body': p, nrm, m, arc = uvbake(Vx, F, UV, N, tw_, th_, meta['arc'])
    else: p, nrm, m = uvbake(Vx, F, UV, N, tw_, th_)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    if name == 'body':
        col, w = project(p, nrm, body_ok)
        # mirror fill (canonical symmetry) for the head
        cp = (p - tw) @ R; cp[:, 0] *= -1; pm = cp @ R.T + tw
        cn = nrm @ R; cn[:, 0] *= -1; nm = cn @ R.T
        colm, wm = project(pm, nm, body_ok, tol=0.6)
        d = p[:, 1] - y_chin
        wm *= np.clip((d + 1.0) / 2.0, 0, 1) * 0.95
        wsum = w + (1 - w) * wm
        col = (w[:, None] * col + ((1 - w) * wm)[:, None] * colm) / np.maximum(wsum, 1e-6)[:, None]
        np.save(S + 'dbg_w.npy', w.reshape(th_, tw_).astype(np.float16)); np.save(S + 'dbg_wm.npy', ((1 - w) * wm).reshape(th_, tw_).astype(np.float16))
        w = wsum
        # fallback: hair / skin / dress, by height
        ang = np.arctan2(p[:, 0] - meta['Cw'][0], p[:, 2] - meta['Cw'][2])
        uu = ang * 9.0 * s * 0.5; vv = -p[:, 1] * s * 0.5
        hair = np.clip(HAIRC[None] * (1.0 + 0.55 * tile_lookup(arc, p[:, 1])[:, None]), 8, 120)
        Uc = arc; Vc = p[:, 1]
        CU, CV = 1.25, 1.1
        fu = Uc / CU; fv = Vc / CV
        dx = (fu - np.floor(fu) - 0.5) * CU; dy = (fv - np.floor(fv) - 0.5) * CV
        cid = (np.floor(fu) * 7.3 + np.floor(fv) * 3.1)
        rr_ = np.sqrt(dx ** 2 + dy ** 2) * (1 + 0.18 * np.sin(np.arctan2(dy, dx) * 3 + cid))
        blob = np.clip((0.25 - rr_) / 0.05, 0, 1)
        d4 = (np.abs(dx) ** 4 + np.abs(dy) ** 4) ** 0.25
        line = np.exp(-((d4 - 0.48) / 0.035) ** 2)
        dress = (38 + 34 * line + 175 * blob)[:, None] * np.array([1.0, 0.98, 0.96])
        back = np.cos(ang - meta['th_face']) < 0.2
        hair_lo = np.where(back, 0.9, 1.5)
        a_h = np.clip((d - hair_lo) / 1.5, 0, 1)[:, None]
        frontness = np.clip((np.cos(ang - meta['th_face']) - 0.55) / 0.3, 0, 1)
        dress_lo = -0.7 * (1 - frontness) - 4.0 * frontness
        a_d = np.clip((dress_lo - d) / 0.8, 0, 1)[:, None]
        nohair_near = (1 - a_h[:, 0]) * (1 - a_d[:, 0]) * np.clip((frontness - 0.2) / 0.5, 0, 1)
        skin = SKINC * 0.92 + rng.normal(0, 2, (len(p), 1))
        fb = a_h * hair + (1 - a_h) * ((1 - a_d) * skin + a_d * dress)
        fb = fb * shade(nrm, 0.58)
    elif name == 'brim_under':
        col, w = project(p, nrm, hat_ok)
        fb = np.broadcast_to(UNDER, p.shape) * shade(-nrm, 0.85) + rng.normal(0, 2, (len(p), 1))
    elif name == 'brim_rim':
        col, w = project(p, nrm, rim_ok)
        fb = FELT * shade(nrm, 0.75)
    elif name == 'crown_in':
        col, w = project(p, nrm, None, tol=0.5)
        fb = np.broadcast_to(np.array([28., 27, 27]), p.shape).copy()
    else:  # brim_top, crown_out
        col = np.zeros_like(p); w = np.zeros(len(p))
        nz = ndimage.gaussian_filter(rng.normal(0, 1, (th_, tw_)), 1.2).reshape(-1, 1) * 5
        fb = FELT * shade(nrm, 0.62) + nz
    w = w.reshape(th_, tw_); col = col.reshape(th_, tw_, 3); fb = fb.reshape(th_, tw_, 3)
    if name == 'body':
        # soften seams: stronger erosion/blur away from the frontal face
        w_s = ndimage.gaussian_filter(ndimage.grey_erosion(w, size=11), 6.0)
        w_f = ndimage.gaussian_filter(ndimage.grey_erosion(w, size=3), 1.2)
        fr = np.clip((nrm[:, 2].reshape(th_, tw_) - 0.35) / 0.3, 0, 1)
        w = w_f * fr + w_s * (1 - fr)
    else:
        w = ndimage.gaussian_filter(ndimage.grey_erosion(w, size=3), 1.2)
    if name == 'body':
        ext = pushpull(col, w)
        near = np.clip(ndimage.gaussian_filter(w, 10) * 2.2, 0, 0.85)[..., None] * nohair_near.reshape(th_, tw_)[..., None]
        fb = fb * (1 - near) + ext * shade(np.array([[0, 0, 1.]]), 0.7)[0] * 0 + ext * near
    out = col * w[..., None] + fb * (1 - w[..., None])
    finish(name, out, m, th_, tw_)
    print(name, 'done', float(w.mean()))
