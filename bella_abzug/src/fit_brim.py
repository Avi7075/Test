"""Hat mask (largest component of the 'others' class) + ellipse fit of the brim's outer edge."""
import numpy as np, cv2
from PIL import Image
from common import S, IMG
cat = np.load(S + 'seg_cat.npy')[..., 0]
hat = (cat == 5).astype(np.uint8)
op = cv2.morphologyEx(hat, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
n, lab, st, _ = cv2.connectedComponentsWithStats(op)
hm = (lab == 1 + np.argmax(st[1:, 4])).astype(np.uint8)
np.save(S + 'hatmask.npy', hm)
ph = np.asarray(Image.open(IMG).convert('L')).astype(float)
cx0, cy0 = 720, 700
pts = []
for a in np.radians(np.r_[np.arange(-55, 30, 3), np.arange(150, 214, 3)]):   # reliable side sectors
    d = np.array([np.cos(a), np.sin(a)]); last = None
    for rr in range(200, 900):
        x, y = (np.array([cx0, cy0]) + rr * d).astype(int)
        if x < 0 or y < 0 or x >= ph.shape[1] or y >= ph.shape[0]: break
        if hm[y, x]: last = (x, y)
    if last: pts.append(last)
sm = cv2.GaussianBlur(ph, (0, 0), 2)
for x in range(300, 1200, 20):                                            # top: walk up through dark underside, then bright rim
    y = 330
    while y > 40 and sm[y, x] < 165: y -= 1
    y2 = y
    while y2 > 20 and sm[y2, x] >= 150 and y - y2 < 40: y2 -= 1
    pts.append((x, y2))
el = cv2.fitEllipse(np.array(pts, np.float32))
np.save(S + 'brim_ellipse.npy', np.array([*el[0], *el[1], el[2]]))
print(el)
