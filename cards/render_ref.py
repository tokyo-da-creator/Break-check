"""BREAK landscape share cards, 1600x900, built on the approved reference art.
The right side (mascot, chart, black void) is the approved card; the left data side is re-set cleanly
with exact numbers, and the chart is continued across the cut to the left edge."""
import random, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
REF = {'hit': os.path.join(HERE, 'reference', 'hit.jpg'), 'miss': os.path.join(HERE, 'reference', 'miss.jpg')}
W, H, S = 1600, 900, 2
K = H/784; OX = W - 1168*K                      # reference scaled to 900 tall, right-aligned
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-{}.otf'
LIME, RED, WHITE, GRAY, HAIR = (198,255,61), (232,52,46), (244,241,234), (140,139,144), (52,53,58)
PAD = 76

def f(w, size): return ImageFont.truetype(FONT.format(w), int(size*S))
def tw(s, font): return font.getlength(s)/S
def T(d, x, y, s, font, fill, anchor='ls'): d.text((x*S, y*S), s, font=font, fill=fill, anchor=anchor)

# split lines measured on each reference (ref px), and where its chart crosses the split
SPLIT = {'hit': (651, -0.276), 'miss': (731, -0.383)}
CROSS = {'hit': (557, 339), 'miss': (583, 392)}
def to_card(x, y): return (OX + x*K, y*K)
def split_card(name, y):                         # card x of the cut at card y
    a, b = SPLIT[name]; return OX + (a + b*(y/K))*K

def jag(points, step=18, amp=8, seed=7):
    rnd = random.Random(seed); out = []
    for (x1,y1),(x2,y2) in zip(points, points[1:]):
        n = max(2, int(np.hypot(x2-x1, y2-y1)/step))
        for i in range(n):
            t = i/n; out.append((x1+(x2-x1)*t, y1+(y2-y1)*t + (0 if i == 0 else rnd.uniform(-amp, amp))))
    out.append(points[-1]); return out

def left_panel(img, ref, name):
    """Repaint the data side with the reference's own lighting (sampled per row), minus its old text."""
    a = np.asarray(ref).astype(float)
    rows = []
    for yr in range(784):
        sx = int(SPLIT[name][0] + SPLIT[name][1]*yr)
        near = np.median(a[yr, max(sx-40,0):sx-12], axis=0)
        far = np.median(a[yr, 4:40], axis=0)
        rows.append((far, near))
    far = np.array([r[0] for r in rows]); near = np.array([r[1] for r in rows]); yy = np.arange(784)
    def fit(v, cap):
        out = np.zeros_like(v)
        for c in range(3):
            keep = v[:,c] < np.percentile(v[:,c], 70)          # ignore rows where old text/lines sat
            m, b = np.polyfit(yy[keep], v[keep,c], 1); out[:,c] = np.clip(m*yy + b, 4, cap)
        return out
    far, near = fit(far, 26), fit(near, 30)
    px = np.zeros((H*S, W*S, 3), np.uint8); mask = np.zeros((H*S, W*S), np.uint8)
    xs = np.arange(W*S)
    for y in range(H*S):
        yr = min(int(y/S/K), 783); edge = split_card(name, y/S)*S
        t = np.clip(xs/edge, 0, 1)[:, None]
        px[y] = (far[yr]*(1-t) + near[yr]*t).astype(np.uint8)
        mask[y, :int(edge)] = 255
    img.paste(Image.fromarray(px), (0,0), Image.fromarray(mask))

def rows_block(d, rows, top, right):
    for i,(lab,val) in enumerate(rows):
        y = top + i*80
        d.line([(PAD*S, y*S), (right*S, y*S)], fill=HAIR, width=S)
        T(d, PAD, y+50, lab, f('Medium', 32), GRAY)
        T(d, right, y+50, val, f('SemiBold', 32), WHITE, anchor='rs')

def chart_left(d, name, pts):
    cx, cy = to_card(*CROSS[name]); pts = pts + [(cx+6, cy)]
    d.line([(x*S, y*S) for x,y in jag(pts, amp=7, seed=4 if name=='hit' else 9)], fill=(238,238,238), width=int(2.6*S), joint='curve')

def render(name, out):
    ref = Image.open(REF[name]).convert('RGB')
    img = Image.new('RGB', (W*S, H*S), (0,0,0))
    img.paste(ref.resize((int(1168*K*S), H*S), Image.LANCZOS), (int(OX*S), 0))
    left_panel(img, ref, name)
    d = ImageDraw.Draw(img)
    if name == 'hit':
        # Style 1: tiny lime horned mark + BREAK, enormous lime hero, white multiple, three rows, chart climbs
        ix, iy, s = PAD, 96, 30
        d.polygon([((ix+3)*S,(iy+3)*S),((ix+1)*S,(iy-7)*S),((ix+10)*S,(iy+3)*S)], fill=LIME)
        d.polygon([((ix+20)*S,(iy+3)*S),((ix+31)*S,(iy-12)*S),((ix+28)*S,(iy+3)*S)], fill=LIME)
        d.rounded_rectangle([ix*S,(iy+1)*S,(ix+s)*S,(iy+1+s)*S], radius=6*S, fill=LIME)
        T(d, ix+46, iy+30, 'BREAK', f('Bold', 38), WHITE)
        T(d, PAD-6, 342, '+412.8%', f('Bold', 196), LIME)
        T(d, PAD-2, 462, '2.4x', f('SemiBold', 116), WHITE)
        chart_left(d, name, [(0, 566), (210, 552), (420, 520), (600, 478), (760, 430)])
        rows_block(d, [('Sealed','0.82'),('Hit','1'),('Paid','0.34')], 592, 700)
    else:
        # Style 2: BREAK large white, huge red hero, gray "sealed miss", rows, chart falls to the bench
        d.line([(split_card(name,0)*S, 0), (split_card(name,H)*S, H*S)], fill=(225,225,225), width=int(2*S))
        T(d, PAD-4, 228, 'BREAK', f('ExtraBold', 132), WHITE)
        T(d, PAD-6, 418, '-68.4%', f('Bold', 176), RED)
        T(d, PAD, 494, 'sealed miss', f('Regular', 46), GRAY)
        chart_left(d, name, [(0, 92), (200, 84), (420, 94), (560, 116), (700, 250)])
        rows_block(d, [('Sealed','0.82'),('Miss','—'),('Paid','0.34')], 574, 700)
    img.resize((W, H), Image.LANCZOS).save(out)

def render_even(out):
    ref = Image.open(REF['hit']).convert('RGB')
    img = Image.new('RGB', (W*S, H*S), (1,1,1))
    mood = Image.open(os.path.join(ROOT, 'public', 'moods', 'flat.jpg')).convert('RGB')
    k = 0.93; x0, y0 = 1003, 900 - 898*k - 6
    big = mood.resize((int(mood.width*k*S), int(mood.height*k*S)), Image.LANCZOS)
    img.paste(big, (int(x0*S), int(y0*S)))
    # flat line, hidden where it passes behind him
    a = np.asarray(mood).max(2) > 40; m = np.zeros(a.shape, np.uint8)
    for r in range(a.shape[0]):
        c = np.where(a[r])[0]
        if len(c): m[r, c.min():c.max()+1] = 255
    body = Image.new('L', (W*S, H*S), 0)
    body.paste(Image.fromarray(m).resize(big.size).filter(ImageFilter.MaxFilter(25)), (int(x0*S), int(y0*S)))
    layer = Image.new('L', (W*S, H*S), 0)
    ImageDraw.Draw(layer).line([(x*S, y*S) for x,y in jag([(0,540),(W,540)], step=16, amp=2.5, seed=11)], fill=255, width=int(2.6*S), joint='curve')
    layer = Image.composite(Image.new('L', layer.size, 0), layer, body)
    left_panel(img, ref, 'hit')
    img.paste(Image.new('RGB', img.size, (238,238,238)), (0,0), layer)
    d = ImageDraw.Draw(img)
    ix, iy, s_ = PAD, 96, 30
    d.polygon([((ix+3)*S,(iy+3)*S),((ix+1)*S,(iy-7)*S),((ix+10)*S,(iy+3)*S)], fill=LIME)
    d.polygon([((ix+20)*S,(iy+3)*S),((ix+31)*S,(iy-12)*S),((ix+28)*S,(iy+3)*S)], fill=LIME)
    d.rounded_rectangle([ix*S,(iy+1)*S,(ix+s_)*S,(iy+1+s_)*S], radius=6*S, fill=LIME)
    T(d, ix+46, iy+30, 'BREAK', f('Bold', 38), WHITE)
    T(d, PAD-6, 342, '1.02x', f('Bold', 196), WHITE)
    T(d, PAD, 452, 'even', f('Regular', 52), GRAY)
    rows_block(d, [('Sealed','0.82'),('Spot','1.02'),('Paid','0.34')], 592, 700)
    img.resize((W, H), Image.LANCZOS).save(out)

if __name__ == '__main__':
    render_even(os.path.join(HERE, 'break-even.png'))
    for n in REF: render(n, os.path.join(HERE, f'break-{n}.png'))
