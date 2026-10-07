"""BREAK landscape share cards, 1600x900. Renders hit / even / miss from the locked mascot art."""
import os, random, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

S = 2                                   # supersample, downscaled at the end
W, H = 1600, 900
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-{}.otf'
LIME, RED, WHITE = (198,255,61), (255,77,46), (244,241,234)
GRAY, HAIR = (138,137,142), (46,47,52)
LEFT_BG, RIGHT_BG = (18,19,22), (1,1,1)
MOODS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'public', 'moods', '{}.jpg')
PAD = 76

def f(weight, size): return ImageFont.truetype(FONT.format(weight), int(size*S))
def split_x(y): return 1010 - 330*(y/H)        # diagonal: top 1010 → bottom 680

def text(d, xy, s, font, fill, track=0, anchor='ls'):
    """Whole-string draw so the font's kerning and contextual shapes stay intact (tracking is built into Inter Display)."""
    d.text((xy[0]*S, xy[1]*S), s, font=font, fill=fill, anchor=anchor)
def width(s, font, track=0): return font.getlength(s)/S

CARDS = {
  'hit':  dict(mood='thumbs', hero='+412.8%', color=LIME,  sub='2.4x', sub_word=False,
               rows=[('Sealed','0.82'),('Hit','1'),('Paid','0.34')]),
  'even': dict(mood='flat',   hero='1.02x',   color=WHITE, sub='even', sub_word=True,
               rows=[('Sealed','0.82'),('Spot','1.02'),('Paid','0.34')]),
  'miss': dict(mood='sad',    hero='-68.4%',  color=RED,   sub='sealed miss', sub_word=True,
               rows=[('Sealed','0.82'),('Miss','—'),('Paid','0.34')]),
}
# mascot placement (card coords): x0, y0, scale
PLACE = {'thumbs': (1026, 100, .86), 'flat': (1043, 100, .86), 'sad': (995, 110, .86)}

def jag(points, step=20, amp=9, seed=7):
    """Price-chart look: walk the trend in short ticks with seeded noise."""
    rnd = random.Random(seed); out = []
    for (x1,y1),(x2,y2) in zip(points, points[1:]):
        n = max(2, int(np.hypot(x2-x1, y2-y1)/step))
        for i in range(n):
            t = i/n; jitter = 0 if i == 0 else rnd.uniform(-amp, amp)
            out.append((x1+(x2-x1)*t, y1+(y2-y1)*t + jitter))
    out.append(points[-1]); return out

CHARTS = {   # the chart is the verdict
  'hit':  lambda: jag([(0,560),(380,545),(640,512),(820,440),(960,338),(1060,236),(1132,138),(1205,112),(1305,84),
                       (1380,128),(1452,104),(1530,166),(1600,196)], amp=8, seed=3),
  'even': lambda: jag([(0,548),(1600,548)], step=18, amp=2.5, seed=11),
  'miss': lambda: jag([(0,486),(260,506),(480,544),(640,574),(780,600),(900,628),(1030,668)], amp=6, seed=21),
}

def body_mask(mood, x0, y0, k):
    """Card-sized mask of the mascot (each row filled between its outer edges) so the chart passes behind him."""
    a = np.asarray(Image.open(MOODS.format(mood)).convert('RGB')).max(2) > 40
    m = np.zeros((a.shape[0], a.shape[1]), np.uint8)
    for r in range(a.shape[0]):
        c = np.where(a[r])[0]
        if len(c): m[r, c.min():c.max()+1] = 255
    im = Image.fromarray(m).resize((int(a.shape[1]*k*S), int(a.shape[0]*k*S)))
    im = im.filter(ImageFilter.MaxFilter(25))              # keep the line clear of his outline
    card = Image.new('L', (W*S, H*S), 0); card.paste(im, (int(x0*S), int(y0*S))); return card

def render(name, out):
    c = CARDS[name]
    img = Image.new('RGB', (W*S, H*S), RIGHT_BG); d = ImageDraw.Draw(img)
    # left panel and the diagonal cut
    d.polygon([(0,0),(split_x(0)*S,0),(split_x(H)*S,H*S),(0,H*S)], fill=LEFT_BG)
    d.line([(split_x(0)*S,0),(split_x(H)*S,H*S)], fill=(40,41,46), width=2*S)
    # mascot (locked art, its black backdrop is the right panel)
    x0, y0, k = PLACE[c['mood']]
    m = Image.open(MOODS.format(c['mood'])).convert('RGB')
    m = m.resize((int(m.width*k*S), int(m.height*k*S)), Image.LANCZOS)
    img.paste(m, (int(x0*S), int(y0*S)))
    # chart: thin white line, hidden where it passes behind him
    pts = [(x*S, y*S) for x,y in CHARTS[name]()]
    layer = Image.new('L', (W*S, H*S), 0); ld = ImageDraw.Draw(layer)
    ld.line(pts, fill=255, width=int(2.6*S), joint='curve')
    if name == 'miss':                                   # arrowhead pointing at the bench
        (ax,ay),(bx,by) = pts[-2], pts[-1]; ang = np.arctan2(by-ay, bx-ax); L = 24*S
        for s in (-0.5, 0.5):
            ld.line([(bx,by),(bx-L*np.cos(ang+s), by-L*np.sin(ang+s))], fill=255, width=int(2.6*S))
    layer = Image.composite(Image.new('L', layer.size, 0), layer, body_mask(c['mood'], x0, y0, k)) if name != 'miss' else layer
    img.paste(Image.new('RGB', img.size, (236,236,236)), (0,0), layer)
    d = ImageDraw.Draw(img)
    # wordmark: tiny square-horn mark + BREAK
    ix, iy, s = PAD, 74, 30
    d.polygon([((ix+3)*S,(iy+3)*S),((ix+1)*S,(iy-7)*S),((ix+10)*S,(iy+3)*S)], fill=LIME)
    d.polygon([((ix+20)*S,(iy+3)*S),((ix+31)*S,(iy-12)*S),((ix+28)*S,(iy+3)*S)], fill=LIME)
    d.rounded_rectangle([ix*S,(iy+1)*S,(ix+s)*S,(iy+1+s)*S], radius=6*S, fill=LIME)
    text(d, (ix+44, iy+30), 'BREAK', f('ExtraBold', 40), WHITE, track=-0.6)
    # hero: as big as the left panel allows
    hero_base, size = 332, 240
    while size > 80:
        fh = f('Black', size); top = hero_base - size*0.73
        if PAD + width(c['hero'], fh, -size*0.012) <= split_x(top) - 70: break
        size -= 4
    text(d, (PAD-4, hero_base), c['hero'], fh, c['color'], track=-size*0.012)
    # subline
    if c['sub_word']: text(d, (PAD, 440), c['sub'], f('Medium', 50), GRAY, track=-0.5)
    else:             text(d, (PAD-2, 450), c['sub'], f('Bold', 104), WHITE, track=-3)
    # three hairline rows
    right = 640
    for i,(lab,val) in enumerate(c['rows']):
        y = 610 + i*75
        d.line([(PAD*S, y*S), (right*S, y*S)], fill=HAIR, width=S)
        text(d, (PAD, y+50), lab, f('Medium', 32), GRAY)
        text(d, (right, y+50), val, f('SemiBold', 32), WHITE, anchor='rs')
    img.resize((W, H), Image.LANCZOS).save(out)

if __name__ == '__main__':
    import sys
    for n in CARDS: render(n, f'{sys.argv[1] if len(sys.argv)>1 else "."}/break-{n}.png')
