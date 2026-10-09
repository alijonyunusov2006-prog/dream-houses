# Подбор масштаба аватарки: самый крупный полный логотип, который целиком помещается в круг Instagram.
# Вход: PNG логотипа без фона 1080×1080 (full_logo(bg="none")), выход: scale, dx, dy для avatar_full().
#   python3 fit_avatar.py lockup-alpha.png [запас=0.92]
import sys, numpy as np
from PIL import Image
a = np.array(Image.open(sys.argv[1]).convert('RGBA'))[:, :, 3]
frac = float(sys.argv[2]) if len(sys.argv) > 2 else 0.92
ys, xs = np.nonzero(a > 40)
pts = sorted(set(zip(xs.tolist(), ys.tolist())))
cross = lambda o, p, q: (p[0]-o[0])*(q[1]-o[1]) - (p[1]-o[1])*(q[0]-o[0])
lo, up = [], []
for p in pts:
    while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
    lo.append(p)
for p in reversed(pts):
    while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
    up.append(p)
D = np.array(lo[:-1] + up[:-1], float) - 540            # внешний контур логотипа относительно центра
cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
s, h = 0.5, 3.0
for _ in range(40):                                     # центр рамки логотипа — в центр круга
    m = (s + h) / 2
    d = np.array([m * (540 - cx), m * (540 - cy)])
    s, h = (m, h) if np.sqrt(((m * D + d) ** 2).sum(1)).max() <= 540 * frac else (s, m)
print(f'scale={s:.3f} dx={s*(540-cx):.1f} dy={s*(540-cy):.1f}')
