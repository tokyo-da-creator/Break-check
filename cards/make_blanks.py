"""Remove the sample numbers from the approved cards (inpaint), keeping everything else pixel-identical."""
import cv2, numpy as np
import os
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, 'approved') + '/'; B = os.path.join(HERE, 'blank') + '/'
# erase boxes per card (x0, y0, x1, y1) in original 1168x784 pixels: hero, subline (if numeric), row values
ERASE = {
  'hit-wink-412.8':   [(48,178,550,310), (48,322,245,408), (360,535,448,570), (405,604,446,637), (360,671,448,706)],
  'hit-stool-228.4':  [(37,143,608,276), (37,289,222,374), (37,470,140,520), (198,470,232,520), (328,470,425,520)],
  'hit-jump-960':     [(44,147,578,297), (47,297,362,410)],
  'hit-absurd-1840':  [(45,140,578,298), (48,306,360,436)],
  'even-ball-1.01x':  [(54,146,424,280), (400,388,479,432), (400,460,479,507), (400,535,479,575)],
  'even-couch-1.04x': [(59,218,436,340), (1080-640,492,507,523), (1080-640,562,507,597), (1080-640,630,507,665)],
  'miss-chair-54.6':  [(53,146,512,265), (478,468,540,505), (478,527,540,564), (478,586,540,623)],
  'cooked-tear-91.2': [(42,182,508,340), (350,488,428,542), (350,568,428,622), (280,648,428,706)],
}
rng = np.random.default_rng(1)
for name, boxes in ERASE.items():
    im = cv2.imread(A+name+'.jpg').astype(float); out = im.copy()
    for x0,y0,x1,y1 in boxes:
        reg = im[y0:y1, x0:x1]; lum = reg.max(2)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        def fitp(keep):
            A_ = np.c_[xx[keep], yy[keep], np.ones(keep.sum())]; pl = np.zeros_like(reg)
            for c in range(3):
                coef, *_ = np.linalg.lstsq(A_, reg[...,c][keep], rcond=None)
                pl[...,c] = coef[0]*xx + coef[1]*yy + coef[2]
            return pl
        plane = fitp(lum <= np.percentile(lum, 35))
        for _ in range(2):                                   # refit on everything that isn't text
            text = (np.abs(reg - plane).max(2) > 9).astype(np.uint8)
            text = cv2.dilate(text, np.ones((17,17), np.uint8)) > 0
            if (~text).sum() > 50: plane = fitp(~text)
        text = cv2.dilate((np.abs(reg - plane).max(2) > 7).astype(np.uint8), np.ones((19,19), np.uint8)) > 0
        grain = rng.normal(0, 1.2, reg.shape)
        fill = np.where(text[...,None], plane + grain, reg)
        # feather the patch edge so no seam shows
        a = cv2.GaussianBlur(text.astype(float), (0,0), 1.5)[...,None]
        out[y0:y1, x0:x1] = reg*(1-a) + fill*a
        if name == 'hit-stool-228.4' and x1 > 560:           # box crosses the light beam: let inpainting follow its edge
            m = np.zeros(im.shape[:2], np.uint8); m[y0:y1, x0:x1] = text.astype(np.uint8)*255
            out = cv2.inpaint(np.clip(out,0,255).astype(np.uint8), m, 9, cv2.INPAINT_TELEA).astype(float)
    cv2.imwrite(B+name+'.jpg', np.clip(out,0,255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 95])
print('ok')
