"""Recolour the light coming out of the ripped Break Check pack, one plate per result."""
import numpy as np
from PIL import Image, ImageFilter
src = Image.open('cards/v3src/pack.jpg').convert('RGB')
a = np.asarray(src).astype(np.float32)/255
mx, mn = a.max(-1), a.min(-1); chroma = mx - mn
lum = (0.3*a[...,0] + 0.59*a[...,1] + 0.11*a[...,2])
w = np.clip((chroma - 0.03)/0.20, 0, 1)
w = np.asarray(Image.fromarray((w*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32)/255
def ramp(stops, x):
    xs = [s[0] for s in stops]; out = np.zeros(x.shape+(3,), np.float32)
    for c in range(3): out[...,c] = np.interp(x, xs, [s[1][c]/255 for s in stops])
    return out
T = {
  'hit':    (1.35, [(0,(10,22,0)),(0.25,(70,140,0)),(0.6,(182,255,46)),(1,(246,255,214))], 1.0),
  'even':   (1.05, [(0,(12,12,14)),(0.3,(96,98,104)),(0.7,(214,216,222)),(1,(255,255,255))], 1.0),
  'miss':   (1.0,  [(0,(20,0,0)),(0.3,(120,6,8)),(0.65,(227,25,27)),(1,(255,170,140))], 0.92),
  'cooked': (0.42,  [(0,(8,2,0)),(0.3,(70,10,0)),(0.7,(190,50,10)),(1,(255,140,60))], 0.70),
}
for name,(gain,stops,body) in T.items():
    tgt = ramp(stops, np.clip(lum*gain, 0, 1))
    base = a*body
    if name == 'cooked':
        g = lum[...,None]; base = (base*0.5 + g*0.5)*0.9     # ashy, drained
    out = base*(1-w[...,None]) + tgt*w[...,None]
    im = Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8))
    im.save(f'public/cards/v3/pack-{name}.webp', quality=88)
    im.save(f'cards/v3src/pack-{name}.png')
    # upright pack (rotated level), for the receipt
    im.rotate(-50, resample=Image.BICUBIC, center=(590,410)).crop((330,0,860,770)).save(f'public/cards/v3/upright-{name}.webp', quality=88)
# Textures cut from the levelled pack: crinkled foil body and the ribbed crimp seal.
lv = src.rotate(-50, resample=Image.BICUBIC, center=(590,410))
lv.crop((425,230,545,600)).save('public/cards/v3/foil.webp', quality=85)
print('ok')
# Crumpled black foil, generated: random flat facets (like crushed plastic) at two scales, lit from the top-left.
import numpy as np
from scipy.spatial import cKDTree
rng = np.random.default_rng(11)
Wf, Hf = 1300, 720
yy, xx = np.mgrid[0:Hf, 0:Wf]; P = np.c_[xx.ravel(), yy.ravel()]
def creases(n, amp):
    pts = rng.random((n,2))*[Wf,Hf]; d, _ = cKDTree(pts).query(P, k=2)
    f = (d[:,1]-d[:,0]).reshape(Hf,Wf); return amp*np.sqrt(f/f.max())
h = creases(90, 1.0) + creases(500, 0.35) + creases(2500, 0.06)
h = np.asarray(Image.fromarray((h/h.max()*255).astype(np.float32)).filter(ImageFilter.GaussianBlur(2)), np.float32) if False else h
gy, gx = np.gradient(h)
nx, ny, nz = -gx*22, -gy*22, np.ones((Hf,Wf))
nl = np.sqrt(nx*nx+ny*ny+nz*nz); L = np.array([-0.45,-0.55,0.7]); L/=np.linalg.norm(L)
shade = np.clip((nx*L[0]+ny*L[1]+nz*L[2])/nl, 0, 1)
v = 10 + 30*shade**1.8 + 85*shade**16
im = Image.fromarray(np.clip(v,0,255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.1))
im.convert('RGB').save('public/cards/v3/foil.webp', quality=86)
print('foil ok')
