"""Texture baking v3: photo projection + class-aware fill + photo-synthesized hair."""
import numpy as np, pickle, cv2, trimesh, os
from PIL import Image
from scipy import ndimage
from common import *
from raster import raster

E = lambda k, d: float(os.environ.get(k, d))
meshes, meta = pickle.load(open(S + 'scene2.pkl', 'rb'))
s, R, tw, y_chin = meta['s'], meta['R'], meta['tw'], meta['y_chin']
photo = np.asarray(Image.open(IMG).convert('RGB')).astype(np.float32)
H, W = photo.shape[:2]
gray = photo.mean(-1)
seg = np.load(S + 'seg_cat.npy')[..., 0]
conf = np.load(S + 'seg_conf.npy').astype(np.float32)          # bg, hair, body-skin, face-skin, clothes, others
hm = np.load(S + 'hatmask.npy').astype(np.float32)
def soft(m, sg=2.5): return cv2.GaussianBlur(m.astype(np.float32), (0, 0), sg)
dil = np.ones((17, 17), np.uint8)
hat_soft = soft(cv2.dilate(hm.astype(np.uint8), dil), 4)
bg_soft = soft(cv2.dilate((seg == 0).astype(np.uint8), dil), 4)
hair_light = soft(((seg == 1) & (cv2.GaussianBlur(gray, (0, 0), 1.5) > 105)).astype(np.uint8), 3)
if E('BODY_GATE_HAT', 0) > 0:
    body_ok = np.clip(1 - 1.6 * np.maximum(hat_soft, bg_soft), 0, 1) * np.clip(1 - 1.5 * hair_light, 0, 1)
else:
    body_ok = np.clip(1 - 1.6 * bg_soft, 0, 1)
el = np.load(S + 'brim_ellipse.npy')
ell_in = np.zeros((H, W), np.uint8)
cv2.ellipse(ell_in, ((el[0], el[1]), (el[2] - 22, el[3] - 22), el[4]), 1, -1)
hat_ok = np.clip((soft(cv2.erode(hm.astype(np.uint8), np.ones((7, 7))) * ell_in) - 0.3) / 0.5, 0, 1)
rim_ok = soft(hm * cv2.dilate(ell_in, np.ones((15, 15))), 1.5)
p_hair = cv2.GaussianBlur(conf[..., 1], (0, 0), 2)
p_skin = cv2.GaussianBlur(conf[..., 2] + conf[..., 3], (0, 0), 2)

# ---------------- z-buffer (full res, depth = z cm)
allV = []; allF = []; off = 0
for k, (V, F, UV) in meshes.items():
    allV.append(V); allF.append(F + off); off += len(V)
AV = np.concatenate(allV); AF = np.concatenate(allF)
_, _, zb = raster(np.stack([AV[:, 0] * s, -AV[:, 1] * s], 1), AF, np.zeros((len(AV), 1), np.float32), (H, W), depth=AV[:, 2])
zb = np.where(np.isfinite(zb), zb, -1e9).astype(np.float32)

def sample(img, xy):
    x = np.clip(xy[:, 0], 0, img.shape[1] - 1.001); y = np.clip(xy[:, 1], 0, img.shape[0] - 1.001)
    x0 = x.astype(int); y0 = y.astype(int); fx = x - x0; fy = y - y0
    sq = img.ndim == 2
    if sq: img = img[..., None]
    fx = fx[:, None]; fy = fy[:, None]
    v = img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy
    return v[:, 0] if sq else v

FT = E('FACE_T', 0.24)
def project(p, nrm, ok_mask, tol=0.3, t0=FT):
    xy = np.stack([p[:, 0] * s, -p[:, 1] * s], 1)
    inimg = (xy[:, 0] > 1) & (xy[:, 0] < W - 2) & (xy[:, 1] > 1) & (xy[:, 1] < H - 2)
    zz = sample(zb, xy)
    tol = tol + 0.12 / np.maximum(np.abs(nrm[:, 2]), 0.1)
    vis = (p[:, 2] >= zz - tol) & inimg
    wf = np.clip((nrm[:, 2] - t0) / 0.35, 0, 1)
    w = wf * vis * (sample(ok_mask, xy) if ok_mask is not None else 1)
    return sample(photo, xy), w, xy

def uvbake(Vx, F, UV, N, tw_, th_, extra=None):
    cols = [Vx, N] + ([e[:, None] for e in extra] if extra is not None else [])
    attr = np.concatenate(cols, 1).astype(np.float32)
    img, m, _ = raster(np.stack([UV[:, 0] * tw_, UV[:, 1] * th_], 1), F, attr, (th_, tw_))
    img = img.reshape(-1, attr.shape[1])
    return img[:, :3], img[:, 3:6], m, img[:, 6:]

L = np.array([-0.25, 0.75, 0.6]); L /= np.linalg.norm(L)
def shade(nrm, amb=0.62): return (amb + (1 - amb) * np.clip(nrm @ L, 0, 1))[:, None]
def med(mask): return np.median(photo[mask.astype(bool)], 0)
SKINC = med((seg == 2) | (seg == 3))
_hp = photo[(seg == 1) & (cv2.GaussianBlur(gray, (0, 0), 3) < 110)]
HAIRC = _hp.mean(0) * E('HAIR_GAIN', 1.0)
UNDER = med(cv2.erode(hm.astype(np.uint8), np.ones((25, 25))).astype(bool) & (gray > 40))
FELT = np.array([214., 212, 208])
print('hair', HAIRC, 'skin', SKINC, 'brim under', UNDER)

# ---------------- dress pattern (arc-length coordinates, cm)
def dress_pattern(U, Vv):
    CU, CV = 1.25, 1.1
    fu = U / CU; fv = Vv / CV
    dx = (fu - np.floor(fu) - 0.5) * CU; dy = (fv - np.floor(fv) - 0.5) * CV
    cid = (np.floor(fu) * 7.3 + np.floor(fv) * 3.1)
    rr_ = np.sqrt(dx ** 2 + dy ** 2) * (1 + 0.18 * np.sin(np.arctan2(dy, dx) * 3 + cid))
    blob = np.clip((0.25 - rr_) / 0.05, 0, 1)
    d4 = (np.abs(dx) ** 4 + np.abs(dy) ** 4) ** 0.25
    line = np.exp(-((d4 - 0.48) / 0.035) ** 2)
    return (38 + 34 * line + 175 * blob)[:, None] * np.array([1.0, 0.98, 0.96])

# procedural hair: strands flowing down (along V), 20 px/cm wrap-around tile
_hr = np.random.default_rng(21); HT = (1200, int(round(2 * np.pi * 9.0 * 20)))   # 60 cm (V) x one full turn at R=9cm (U)
def _layer(sv, su):
    n = ndimage.gaussian_filter(_hr.normal(0, 1, HT), (sv, su), mode='wrap'); return n / n.std()
_hv = 0.6 * _layer(16, 1.0) + 0.45 * _layer(45, 3.5) + 0.25 * _layer(120, 30)
_hwave = 0.35 * _layer(160, 60)
HAIR_TILE = np.pad(np.exp(E('HAIR_VAR', 0.3) * _hv) , ((0, 1), (0, 1)), mode='wrap')
HAIR_TILE /= HAIR_TILE.mean()
def hair_ratio(U, Vv):
    x = np.mod(U * 20 * (HT[1] / (2 * np.pi * 9.0 * 20)) + 6 * np.sin(Vv * 0.5), HT[1]); y = np.mod(Vv * 20, HT[0])
    return sample(HAIR_TILE, np.stack([x, y], 1))
def strand_noise(U, Vv):
    return np.log(hair_ratio(U * 0.5, Vv * 0.5)) / E('HAIR_VAR', 0.3)

def cascade_fill(col, wc, G, levels=(48, 16, 6, 2.5), k=5.0):
    """multi-scale normalized convolution: photo colors near data, G far away"""
    out = G.copy()
    for sg in levels:
        num = ndimage.gaussian_filter(col * wc[..., None], (sg, sg, 0)); den = ndimage.gaussian_filter(wc, sg)
        val = num / np.maximum(den, 1e-6)[..., None]
        a = np.clip(den * k, 0, 1)[..., None]
        out = out * (1 - a) + val * a
    return out

def finish(name, out, m, th_, tw_):
    out = out.reshape(th_, tw_, 3)
    if (~m).any():
        idx = ndimage.distance_transform_edt(~m, return_distances=False, return_indices=True)
        out = out[idx[0], idx[1]]
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(S + f'tex2_{name}.jpg', quality=int(E('JQ', 84)))

sizes = {'body': (2048, 2048), 'brim_under': (2048, 256), 'brim_top': (512, 128), 'brim_rim': (1024, 16),
         'crown_out': (512, 256), 'crown_in': (512, 128)}
rng = np.random.default_rng(3)
for name, (Vx, F, UV) in meshes.items():
    N = np.array(trimesh.Trimesh(Vx, F, process=False).vertex_normals)
    tw_, th_ = sizes[name]
    extra = [meta['arc'], meta['varc']] if name == 'body' else None
    p, nrm, m, ex = uvbake(Vx, F, UV, N, tw_, th_, extra)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    if name == 'body':
        arc, varc = ex[:, 0], ex[:, 1]
        cpc0 = (p - tw) @ R
        lat0 = np.abs(p[:, 0] - meta['Cw'][0])
        t_arr = FT + E('JAW_T', 0.14) * np.clip((-4.5 - cpc0[:, 1]) / 1.5, 0, 1) * np.clip((p[:, 1] - y_chin + 2.0) / 1.0, 0, 1) * np.clip((7.0 - lat0) / 1.5, 0, 1)
        _ps0 = sample(p_skin, np.stack([p[:, 0] * s, -p[:, 1] * s], 1))
        _dn = p[:, 1] - y_chin
        t_arr = np.maximum(t_arr, FT + E('NECK_T', 0.12) * np.clip((1.0 - _dn) / 1.5, 0, 1) * np.clip((_dn + 3.5) / 1.0, 0, 1) * np.clip(_ps0 * 1.5 - 0.3, 0, 1))
        col, w, xy = project(p, nrm, body_ok, t0=t_arr)
        ph_ = sample(p_hair, xy); ps_ = sample(p_skin, xy)
        nz = nrm[:, 2]
        d = p[:, 1] - y_chin
        # mirror (canonical symmetry) for the head
        cp = cpc0.copy(); cp[:, 0] *= -1; pm = cp @ R.T + tw
        cn = nrm @ R; cn[:, 0] *= -1; nm = cn @ R.T
        colm, wm, xym = project(pm, nm, body_ok, tol=0.6)
        phm = sample(p_hair, xym); psm = sample(p_skin, xym)
        wm *= np.clip((d + 1.0) / 2.0, 0, 1) * 0.95
        # on grazing skin, prefer the mirrored texel when it faces the camera clearly better;
        # its detail is used at the direct view's low-frequency tone so the lighting stays continuous
        pref = (np.clip((nm[:, 2] - nz - E('MP_M', 0.15)) / 0.2, 0, 1) * np.clip((wm - 0.4) / 0.3, 0, 1)
                * np.clip((ps_ - 0.4) / 0.3, 0, 1) * np.clip((psm - 0.4) / 0.3, 0, 1) * E('MP_ON', 1.0))
        base = np.broadcast_to(SKINC, (th_, tw_, 3)).copy()
        lowD = cascade_fill(col.reshape(th_, tw_, 3), w.reshape(th_, tw_), base, levels=(24,), k=4.0).reshape(-1, 3)
        lowM = cascade_fill(colm.reshape(th_, tw_, 3), wm.reshape(th_, tw_), base, levels=(24,), k=4.0).reshape(-1, 3)
        colm_t = colm * (lowD.mean(1) / np.maximum(lowM.mean(1), 1.0))[:, None]
        colm = colm * (1 - pref[:, None]) + colm_t * pref[:, None]
        w_d = w * (1 - pref)
        wmm = (1 - w_d) * wm
        wsum = w_d + wmm
        inv = 1 / np.maximum(wsum, 1e-6)
        col = (w_d[:, None] * col + wmm[:, None] * colm) * inv[:, None]
        ph_ = (w_d * ph_ + wmm * phm) * inv
        ps_ = (w_d * ps_ + wmm * psm) * inv
        nz_eff = np.where(wsum > 1e-6, (w_d * nz + wmm * nm[:, 2]) * inv, nz)
        w = wsum
        col0 = col.copy()
        # region rule for hidden texels
        ang = np.arctan2(p[:, 0] - meta['Cw'][0], p[:, 2] - meta['Cw'][2])
        cfa = np.cos(ang - meta['th_face'])
        back_s = np.clip((E('HL_C0', 0.75) - cfa) / E('HL_W', 0.9), 0, 1); back_s = back_s * back_s * (3 - 2 * back_s)
        hair_lo = E('HAIR_FRONT', 1.5) * (1 - back_s) + E('HAIR_BACK', -0.5) * back_s
        a_h = np.clip((d - hair_lo) / 0.35, 0, 1)
        frontness = np.clip((cfa - 0.55) / 0.3, 0, 1)
        dress_lo = E('COLLAR', -0.3) * (1 - frontness) - 4.0 * frontness
        a_d = np.clip((dress_lo - d) / 0.5, 0, 1)
        # hair zone (canonical head frame): lateral/back of head above the jaw angle
        lat = np.clip((np.abs(cpc0[:, 0]) - E('HZ_X', 5.6)) / 1.0, 0, 1) * np.clip((E('HZ_Z', 1.8) - cpc0[:, 2]) / 1.2, 0, 1)
        behind = np.clip((E('HZ_ZB', -2.0) - cpc0[:, 2]) / 1.5, 0, 1)
        hz = np.maximum(lat, behind) * np.clip((cpc0[:, 1] + 4.5) / 1.5, 0, 1)
        a_h = np.maximum(a_h, hz)
        # photo tones (dark hair / skin) spread outward over far-field bases with baked shading
        G_hair = (HAIRC * shade(nrm, 0.55)).reshape(th_, tw_, 3)
        G_skin = (SKINC * 0.8 * shade(nrm, 0.5) * (1 - 0.4 * np.clip(-nrm[:, 1:2] * 1.5, 0, 1))).reshape(th_, tw_, 3)
        dark = np.clip((E('HAIR_DARK', 95) - col0.mean(1)) / 25, 0, 1)
        col0T = col0.reshape(th_, tw_, 3)
        L_hair = cascade_fill(col0T, (w * np.clip((ph_ - 0.45) / 0.3, 0, 1) * dark).reshape(th_, tw_), G_hair)
        L_skin = cascade_fill(col0T, (w * np.clip(ps_ * 1.3 - 0.2, 0, 1)).reshape(th_, tw_), G_skin)
        Uh = np.unwrap(ang.reshape(th_, tw_), axis=1).reshape(-1) * 9.0
        Rh = hair_ratio(Uh, varc)
        vdark = (0.62 + 0.38 * np.clip((nrm[:, 2] + 0.3) / 0.8, 0, 1))[:, None]
        hair_fb = L_hair.reshape(-1, 3) * Rh[:, None] * (0.85 + 0.15 * vdark)
        # grazing hair: the photo's strands are smeared there, so use synthetic strands in the photo's hair tone
        g_h = np.clip((nz_eff - E('HAIR_T', 0.36)) / 0.22, 0, 1)
        rep_h = (1 - g_h) * np.clip((ph_ - E('REP_H0', 0.3)) / 0.3, 0, 1)
        col = col * (1 - rep_h[:, None]) + hair_fb * rep_h[:, None]
        # grazing skin: keep the tone, drop the stretched detail
        L_sm = cascade_fill(col0T, w.reshape(th_, tw_), col0T, levels=(14, 6), k=6.0).reshape(-1, 3)
        g_s = np.clip((nz_eff - E('SKIN_T', 0.1)) / E('SKIN_R', 0.25), 0, 1)
        rep_s = (1 - g_s) * np.clip(1 - ph_ * 1.3, 0, 1) * (1 - rep_h)
        col = col * (1 - rep_s[:, None]) + L_sm * rep_s[:, None]
        # soften weights (texture space), stronger away from frontal face
        wt = w.reshape(th_, tw_)
        w_s = ndimage.gaussian_filter(ndimage.grey_erosion(wt, size=5), E('WS_SIG', 2.0))
        w_f = ndimage.gaussian_filter(ndimage.grey_erosion(wt, size=3), 1.2)
        fr = np.clip((nrm[:, 2].reshape(th_, tw_) - E('FR0', 0.18)) / 0.2, 0, 1)
        wt = w_f * fr + w_s * (1 - fr)
        # fallback class follows the photo's own hair/skin label wherever the photo has evidence;
        # the region rule only decides where it has none
        ev = np.clip(w * E('EV_K', 3.0), 0, 1) * E('EV_ON', 1.0)
        ph_s = np.clip((ph_ - 0.3) / 0.4, 0, 1); ph_s = ph_s * ph_s * (3 - 2 * ph_s)
        a_h = ev * ph_s + (1 - ev) * a_h
        sn = strand_noise(Uh, varc).reshape(th_, tw_)
        wt = np.clip(wt + 0.25 * sn * (wt * (1 - wt) * 4) * a_h.reshape(th_, tw_), 0, 1)
        colT = col.reshape(th_, tw_, 3)
        # nape shadow just below hair edge
        hair_edge_d = np.where(hz > 0.5, -1e3, hair_lo)
        under_edge = np.clip(1 - (hair_lo - d) / 0.7, 0, 1) * (1 - a_h) * (d < hair_lo)
        # shadow under the bob at the sides: skin just below the hair zone
        hz_below = ndimage.gaussian_filter(hz.reshape(th_, tw_), 6).reshape(-1)
        under_edge = np.maximum(under_edge, np.clip(hz_below * 1.6, 0, 1) * (1 - hz))
        jaw_ao = 1 - 0.35 * np.clip(-nrm[:, 1] * 1.6 - 0.2, 0, 1) * (1 - wt.reshape(-1))
        neckzone = np.clip((3.0 - d) / 2.0, 0, 1) * np.clip((d + 5.0) / 2.0, 0, 1)
        side_occ = 1 - E('NECK_OCC', 0.38) * np.clip((0.45 - nrm[:, 2]) / 0.5, 0, 1) * neckzone
        jaw_ao = jaw_ao * side_occ
        skin_fb = L_skin.reshape(-1, 3) * ((1 - 0.28 * under_edge) * jaw_ao)[:, None] * vdark * (1 + rng.normal(0, 0.015, (len(p), 1)))
        # make pattern periodic around each row: arc scaled so the row circumference is a whole number of cells
        Lrow = (meta['arc'].reshape(meta['NK2'], meta['NJ']))
        Lrow = (Lrow[:, -1] - Lrow[:, 0])                       # full circumference per row
        vtex = (np.repeat(np.arange(th_), tw_) + 0.5) / th_
        krow = (1 - vtex) * (meta['NK2'] - 1)
        Lt = np.interp(krow, np.arange(meta['NK2']), Lrow)
        ncell = np.maximum(np.round(Lt / 1.25), 1)
        dress = dress_pattern(arc * (ncell * 1.25 / np.maximum(Lt, 1e-3)), varc) * shade(nrm, 0.58)
        fb = a_h[:, None] * hair_fb + (1 - a_h[:, None]) * ((1 - a_d[:, None]) * skin_fb + a_d[:, None] * dress)
        out = colT.reshape(-1, 3) * wt.reshape(-1, 1) + fb * (1 - wt.reshape(-1, 1))
        if os.environ.get('DEBUG_W'):
            out = np.stack([wt.reshape(-1) * 255, hz * 255, a_d * 255], 1) * 0.7 + out * 0.3
        finish(name, out, m, th_, tw_)
        print(name, 'done', float(wt.mean()))
        continue
    if name == 'brim_under':
        col, w, _ = project(p, nrm, hat_ok, t0=0.14)
        fb = np.broadcast_to(UNDER, p.shape) * shade(-nrm, 0.85) + rng.normal(0, 2, (len(p), 1))
    elif name == 'brim_rim':
        col, w, _ = project(p, nrm, rim_ok, t0=0.14)
        fb = FELT * shade(nrm, 0.75)
    elif name == 'crown_in':
        col, w, _ = project(p, nrm, None, tol=0.5, t0=0.14)
        fb = np.broadcast_to(np.array([28., 27, 27]), p.shape).copy()
    else:  # brim_top, crown_out
        col = np.zeros_like(p); w = np.zeros(len(p))
        nz = ndimage.gaussian_filter(rng.normal(0, 1, (th_, tw_)), 1.2).reshape(-1, 1) * 5
        fb = FELT * shade(nrm, 0.62) + nz
    w = w.reshape(th_, tw_); col = col.reshape(th_, tw_, 3); fb = fb.reshape(th_, tw_, 3)
    w = ndimage.gaussian_filter(ndimage.grey_erosion(w, size=3), 1.2)
    out = col * w[..., None] + fb * (1 - w[..., None])
    finish(name, out, m, th_, tw_)
    print(name, 'done', float(w.mean()))
