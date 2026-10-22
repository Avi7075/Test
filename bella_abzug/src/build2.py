"""Build geometry in the photo's camera frame (world units: cm, x right, y up, z toward camera).
Image pixel = (s*x, -s*y)."""
import numpy as np, trimesh, os, pickle
from scipy.spatial import Delaunay
from common import *

E = lambda k, d: float(os.environ.get(k, d))

V, Fc = load_canon(); P = cam_lm(); s, R, t = procrustes(V, P[:468])
tw = t / s
def c2w(X): return X @ R.T + tw
def w2c(W): return (W - tw) @ R
def w2img(W): return np.stack([W[:, 0] * s, -W[:, 1] * s], 1)
def img2w(xy, z=0): return np.stack([xy[:, 0] / s, -xy[:, 1] / s, np.broadcast_to(z, len(xy))], 1)
Fu = w2c(P[:468] / s)
seg = np.load(S + 'seg_cat.npy')[..., 0]

def grid_faces(nu, nv):
    idx = np.arange(nu * nv).reshape(nv, nu)
    a = idx[:-1, :-1].ravel(); b = idx[:-1, 1:].ravel(); c = idx[1:, :-1].ravel(); d = idx[1:, 1:].ravel()
    return np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])

def orient(Vx, F, want):
    """flip faces so that mean normal . want(V) > 0"""
    m = trimesh.Trimesh(Vx, F, process=False)
    fc = m.triangles_center; w = want(fc)
    if np.mean(np.sum(m.face_normals * w, 1)) < 0: F = F[:, ::-1]
    return F

# ------------------------------------------------------------------ canonical head
C = np.array([0, 1.6, -3.2])
NU, NV = 181, 121
th = np.linspace(-np.pi, np.pi, NU); ph = np.linspace(-np.pi / 2, np.pi / 2, NV)
TH, PH = np.meshgrid(th, ph)
D = np.stack([np.cos(PH) * np.sin(TH), np.sin(PH), np.cos(PH) * np.cos(TH)], -1).reshape(-1, 3)
AXH = E('AXH', 8.3)          # half width incl. hair
ax = np.where(D[:, 1] > -0.2, AXH, 7.6 + (AXH - 7.6) * np.clip((D[:, 1] + 0.6) / 0.4, 0, 1))
by = np.where(D[:, 1] > 0, 12.4, 9.0); cz = np.where(D[:, 2] > 0, 9.3, E('BACK', 10.4))
re = 1 / np.sqrt((D[:, 0] / ax) ** 2 + (D[:, 1] / by) ** 2 + (D[:, 2] / cz) ** 2)
fm = trimesh.Trimesh(Fu, Fc, process=False).subdivide_loop(2)
loc, ri, ti = fm.ray.intersects_location(np.repeat(C[None], len(D), 0), D, multiple_hits=False)
rf = np.full(len(D), np.nan); rf[ri] = np.linalg.norm(loc - C, axis=1)
hit = ~np.isnan(rf)
delta = np.zeros(len(D)); delta[hit] = rf[hit] - re[hit]
uvp = np.stack([TH.ravel(), PH.ravel()], 1)
inside = Delaunay(uvp[hit]).find_simplex(uvp) >= 0
dg = delta.reshape(NV, NU); hg = hit.reshape(NV, NU)
decay = np.where(inside.reshape(NV, NU), 1.0, 0.93)
for it in range(1500):
    p = np.pad(dg, 1, mode='edge'); avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
    dg = np.where(hg, dg, avg * decay)
Vh = C + D * (re + dg.ravel())[:, None]
Fh = grid_faces(NU, NV)
Hw = c2w(Vh)
Fh = orient(Hw, Fh, lambda x: x - c2w(C[None])[0])
head = trimesh.Trimesh(Hw, Fh, process=False)

# ------------------------------------------------------------------ hat
el = np.load(S + 'brim_ellipse.npy'); ecx, ecy, ew, eh, eang = el
a_ = np.radians(eang)
ax1 = np.array([np.cos(a_), np.sin(a_)]); ax2 = np.array([-np.sin(a_), np.cos(a_)])
if ew > eh: maj, mn, A, B = ax1, ax2, ew / 2, eh / 2
else: maj, mn, A, B = ax2, ax1, eh / 2, ew / 2
mnw = np.array([mn[0], -mn[1]]);  mnw = mnw if mnw[1] > 0 else -mnw
tau = np.radians(E('TAU', 42))                                    # plane tilt (camera space)
n = np.array([mnw[0] * np.cos(tau), mnw[1] * np.cos(tau), -np.sin(tau)])
e1 = np.array([maj[0], -maj[1], 0.]); e1 -= n * (e1 @ n); e1 /= np.linalg.norm(e1)
if e1[0] < 0: e1 = -e1
e2 = np.cross(n, e1); e2 = e2 if e2[2] > 0 else -e2                 # in-plane "front/up"
# plane anchor: head surface point under image (x on minor axis, y = HB_Y)
hb_y = E('HB_Y', 318)
hb_x = ecx + (hb_y - ecy) * (mn[0] / mn[1])
o = img2w(np.array([[hb_x, hb_y]]), 200.0)
lh, _, _ = head.ray.intersects_location(o, np.array([[0, 0, -1.]]), multiple_hits=False)
anchor = lh[0] + np.array([0, 0, E('HAT_FWD', 0.25)])
def inplane(p): d = p - anchor; return np.stack([d @ e1, d @ e2], -1)
def plane_z(xy):  # world xy -> z on plane
    return anchor[2] - (n[0] * (xy[:, 0] - anchor[0]) + n[1] * (xy[:, 1] - anchor[1])) / n[2]
# head cross-section -> headband ellipse
segs = trimesh.intersections.mesh_plane(head, n, anchor)
cs = inplane(segs.reshape(-1, 3))
mg = E('HB_MARGIN', 0.35)
a0, a1 = cs[:, 0].min(), cs[:, 0].max(); b0, b1 = cs[:, 1].min(), cs[:, 1].max()
hc2 = np.array([(a0 + a1) / 2, (b0 + b1) / 2]); ha, hb = (a1 - a0) / 2 + mg, (b1 - b0) / 2 + mg
print('headband semi-axes', ha, hb, 'front pt', b1)
# rim: back-project image ellipse onto plane
psi = np.linspace(0, 2 * np.pi, 721)[:-1]
q = np.array([ecx, ecy])[None] + A * np.cos(psi)[:, None] * maj[None] + B * np.sin(psi)[:, None] * mn[None]
qw = img2w(q); qw[:, 2] = plane_z(qw)
rim2 = inplane(qw)
rel = rim2 - hc2; rang = np.arctan2(rel[:, 1] / hb, rel[:, 0] / ha); order = np.argsort(rang)
rang, rrad = rang[order], np.linalg.norm(rel, axis=1)[order]
NA = int(E('NA', 128))
phi = np.linspace(-np.pi, np.pi, NA + 1)
dirs = np.stack([np.cos(phi), np.sin(phi)], 1)
hbpt = hc2 + dirs * np.array([ha, hb])
# rim radius along the ray hc2 + r * dir_norm
def rim_along(phi_):
    ray = np.stack([np.cos(phi_) * ha, np.sin(phi_) * hb], 1); ray /= np.linalg.norm(ray, axis=1, keepdims=True)
    ang = np.arctan2(ray[:, 1] / hb, ray[:, 0] / ha)
    # find rim point with same param angle
    rp = np.interp(ang, rang, rrad, period=2 * np.pi)
    return hc2 + ray * rp[:, None]
rimpt = rim_along(phi)
wid = np.linalg.norm(rimpt - hbpt, axis=1); print('brim width min/max', wid.min(), wid.max())
def toW(ab, off=0.0): return anchor + ab[..., :1] * e1 + ab[..., 1:2] * e2 + off * n
nb = 8; thick = 0.35
rows_u = []; rows_t = []
for k in range(nb + 1):
    f = k / nb
    ab = hbpt + (rimpt - hbpt) * f
    curl = E('CURL', 0.0) * max(0, (f - 0.7) / 0.3) ** 2      # slight upturn of the edge
    rows_u.append(toW(ab, -thick / 2 + curl)); rows_t.append(toW(ab, thick / 2 + curl))
Vbu = np.concatenate(rows_u); Vbt = np.concatenate(rows_t)
Fb = grid_faces(NA + 1, nb + 1)
UVb = np.stack([np.tile(np.linspace(0, 1, NA + 1), nb + 1), np.repeat(np.linspace(0, 1, nb + 1), NA + 1)], 1)
Fbu = orient(Vbu, Fb, lambda x: -n[None]); Fbt = orient(Vbt, Fb, lambda x: n[None])
# rim strip
Vr = np.concatenate([rows_u[-1], rows_t[-1]]); Fr = grid_faces(NA + 1, 2)
UVr = np.stack([np.tile(np.linspace(0, 1, NA + 1), 2), np.repeat([0., 1.], NA + 1)], 1)
hcw = toW(hc2[None])[0]
Fr = orient(Vr, Fr, lambda x: (x - hcw) - ((x - hcw) @ n)[:, None] * n)
# crown
H = E('CROWN_H', 7.0); ncr = 10
def crown_rows(scale):
    rows = []
    for k in range(ncr + 1):
        f = k / ncr
        hgt = H * np.sin(f * np.pi / 2) ** 0.8
        sc = (1 - 0.18 * f ** 1.5) * np.sqrt(max(1 - f ** 6, 0)) if f < 1 else 0.0
        ab = hc2 + dirs * np.array([ha, hb]) * sc * scale
        rows.append(toW(ab, hgt * scale + thick / 2))
    return np.concatenate(rows)
Vco = crown_rows(1.0); Vci = crown_rows(0.97)
Fcr = grid_faces(NA + 1, ncr + 1)
UVc = np.stack([np.tile(np.linspace(0, 1, NA + 1), ncr + 1), np.repeat(np.linspace(0, 1, ncr + 1), NA + 1)], 1)
Fco = orient(Vco, Fcr, lambda x: x - (hcw + n * H * 0.4)); Fci = orient(Vci, Fcr, lambda x: (hcw + n * H * 0.4) - x)

# keep head inside crown (world frame)
relh = Hw - hcw; hn = relh @ n; hx = relh @ e1 - (hc2[0] - 0); hy = relh @ e2
relh_ab = np.stack([relh @ e1, relh @ e2], 1)
capH = H - 1.0
Hw2 = Hw.copy()
over = hn > capH
Hw2[over] -= n * (hn[over] - capH)[:, None]
relh = Hw2 - hcw; hn = relh @ n; pa = relh @ e1; pb = relh @ e2
fl = 2 / np.pi * np.arcsin(np.clip((hn - thick / 2) / H, 0, 1)); loc_ = (1 - 0.18 * fl ** 1.5) * 0.95
ell = np.sqrt((pa / (ha * loc_)) ** 2 + (pb / (hb * loc_)) ** 2)
msk = (hn > -0.8) & (ell > 1)
kk = np.clip((hn + 0.8) / 0.8, 0, 1)
sc = np.where(msk, 1 / ell, 1); sc = 1 - (1 - sc) * kk
Hw2 = hcw + n * hn[:, None] + e1 * (pa * sc)[:, None] + e2 * (pb * sc)[:, None]
head = trimesh.Trimesh(Hw2, Fh, process=False)

# ------------------------------------------------------------------ lathe: head + neck + bust
y_chin = P[152, 1] / s
Cw = c2w(C[None])[0]
# neck centre from body-skin mask a little below chin
row = int(-y_chin * s + 60)
xs = np.nonzero(seg[row] == 2)[0]
neck_cx = (xs.min() + xs.max()) / 2 / s if len(xs) else Cw[0]
neck_w = (xs.max() - xs.min()) / 2 / s if len(xs) else 5.6
print('neck centre x', neck_cx, 'half width', neck_w)
nz_c = c2w(np.array([[0, -9.0, -2.6]]))[0, 2]
def centre(y):
    w = np.clip((y - (y_chin - 4)) / 6.0, 0, 1)
    w = w * w * (3 - 2 * w)
    return np.stack([neck_cx * (1 - w) + Cw[0] * w, nz_c * (1 - w) + Cw[2] * w], -1)
# body cross-section table: d=y-y_chin : half width, front depth, back depth, exponent
NW = E('NECKW', neck_w)
tab = np.array([
    [6.0, NW * 0.9, 4.4, 5.4, 2.0],
    [0.0, NW + 0.2, 5.4, 6.0, 2.0],
    [-2.0, NW + 0.8, 5.8, 7.0, 2.1],
    [-3.6, NW + 3.2, 6.6, 8.0, 2.3],
    [-5.5, 13.0, 8.0, 7.6, 2.5],
    [-7.5, 16.8, 9.6, 8.6, 2.8],
    [-9.5, 18.0, 10.4, 9.0, 2.8],
    [-12.0, 18.6, 11.0, 9.2, 2.8],
    [-16.5, 18.8, 11.2, 9.4, 2.8]])
def body_r(y, thv):
    d = y - y_chin
    a = np.interp(-d, -tab[:, 0], tab[:, 1]); bf = np.interp(-d, -tab[:, 0], tab[:, 2])
    bb = np.interp(-d, -tab[:, 0], tab[:, 3]); ex = np.interp(-d, -tab[:, 0], tab[:, 4])
    bz = np.where(np.cos(thv) > 0, bf, bb)
    cth, sth = np.abs(np.cos(thv)), np.abs(np.sin(thv))
    r = 1 / ((sth / a) ** ex + (cth / bz) ** ex) ** (1 / ex)
    return np.where(d > 6.0, 0.0, r)
# rows
y_bot = y_chin - 16.5
y_top = Hw2[:, 1].max() - 0.05
y_face_lo, y_face_hi = y_chin - 3.0, Fu[10, 1] * 0 + c2w(Fu[[10]])[0, 1] + 2.5
ys = np.concatenate([np.linspace(y_bot, y_face_lo, 26, endpoint=False),
                     np.linspace(y_face_lo, y_face_hi, int(E('NFACE', 104)), endpoint=False),
                     np.linspace(y_face_hi, y_top, 18)])
# columns: denser around face direction
face_dir = (c2w(np.array([[0, 0, 1.]])) - tw)[0]; th_face = np.arctan2(face_dir[0], face_dir[2])
g = np.linspace(-1, 1, int(E('NCOL', 161)))
thv = th_face + np.pi * np.sign(g) * (0.55 * np.abs(g) + 0.45 * np.abs(g) ** 2.2)
NJ, NK = len(thv), len(ys)
YY, TT = np.meshgrid(ys, thv, indexing='ij')
cen = centre(YY.ravel())
dirv = np.stack([np.sin(TT.ravel()), np.zeros(YY.size), np.cos(TT.ravel())], 1)
orig = np.stack([cen[:, 0], YY.ravel(), cen[:, 1]], 1) + dirv * 60
lc, ri2, _ = head.ray.intersects_location(orig, -dirv, multiple_hits=False)
rh = np.zeros(YY.size); rh[ri2] = 60 - np.linalg.norm(lc - orig[ri2], axis=1)
rh = np.maximum(rh, 0)
rb = body_r(YY.ravel(), TT.ravel() - th_face * 0)
k_ = 0.7
rr = k_ * np.logaddexp(rh / k_, rb / k_)
rr = np.where((rh <= 0) & (rb <= 0), 0, rr)
rr = np.where(rh <= 0, rb, np.where(rb <= 0, rh, rr))
# top rows: if no hit, shrink to centre
Vl = np.stack([cen[:, 0], YY.ravel(), cen[:, 1]], 1) + dirv * rr[:, None]
Vl = Vl.reshape(NK, NJ, 3)
# fix rows with zero radius near top: collapse to row centroid
for k in range(NK):
    z = rr.reshape(NK, NJ)[k] <= 1e-6
    if z.any() and (~z).any(): Vl[k, z] = Vl[k, ~z].mean(0)
    elif z.all(): Vl[k] = Vl[k - 1].mean(0)
# bottom cap row
cap = np.repeat(np.array([[centre(np.array([y_bot]))[0, 0], y_bot - 0.01, centre(np.array([y_bot]))[0, 1]]]), NJ, 0)
apex = Vl[-1].mean(0)
Vl = np.concatenate([cap[None], Vl, np.repeat(apex[None, None], NJ, 1)], 0)
NK2 = NK + 2
seg_len = np.linalg.norm(np.diff(Vl, axis=1), axis=2)
arc = np.concatenate([np.zeros((NK2, 1)), np.cumsum(seg_len, 1)], 1)
arc = (arc - arc[:, [NJ // 2]]).ravel()
Vl = Vl.reshape(-1, 3)
Fl = grid_faces(NJ, NK2)
UVl = np.stack([np.tile(np.linspace(0, 1, NJ), NK2), np.repeat(np.linspace(1, 0, NK2), NJ)], 1)
def want_l(x):
    c = centre(x[:, 1]); d = x.copy(); d[:, 0] -= c[:, 0]; d[:, 2] -= c[:, 1]; d[:, 1] = 0; return d
Fl = orient(Vl, Fl, want_l)

meshes = {
    'body': (Vl, Fl, UVl),
    'brim_under': (Vbu, Fbu, UVb), 'brim_top': (Vbt, Fbt, UVb), 'brim_rim': (Vr, Fr, UVr),
    'crown_out': (Vco, Fco, UVc), 'crown_in': (Vci, Fci, UVc)}
meta = dict(s=s, R=R, t=t, tw=tw, y_chin=y_chin, Cw=Cw, n=n, e1=e1, e2=e2, anchor=anchor, hc2=hc2, ha=ha, hb=hb,
            th_face=th_face, NJ=NJ, NK2=NK2, arc=arc)
pickle.dump((meshes, meta), open(S + 'scene2.pkl', 'wb'))
print({k: (len(v[0]), len(v[1])) for k, v in meshes.items()})
