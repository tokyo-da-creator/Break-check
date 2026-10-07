"""Full-bleed BREAK card backgrounds (1600x900): the pack photo, relit per result, sharpened, with the table extended to the left for the type."""
import numpy as np
from PIL import Image, ImageFilter
W, H = 1600, 900
S, OX, OY = 1.2, 372, -20          # pack scale and placement
rng = np.random.default_rng(3)
for name in ['hit','even','miss','cooked']:
    src = Image.open('cards/v3src/pack.jpg' if name == 'hit' else f'cards/v3src/pack-{name}.png').convert('RGB')
    sw, sh = round(src.width*S), round(src.height*S)
    big = src.resize((sw, sh), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=2))
    b = np.asarray(big).astype(np.float32)
    out = np.zeros((H, W, 3), np.float32)
    rows = b[-OY:-OY+H]                                   # rows that land on the card
    cw = min(W - OX, sw); out[:, OX:OX+cw] = rows[:, :cw]
    edge_src = rows[:, 8:48]
    # extend the table to the left from the photo's own edge colour, softly darkening toward the card edge
    edge = edge_src.mean(axis=1)                     # (H,3)
    edge = np.asarray(Image.fromarray(np.clip(edge[:,None,:].repeat(4,1),0,255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))).astype(np.float32)[:,0,:]
    E = OX + 160
    x = np.arange(E)[None,:,None]
    fill = edge[:,None,:] * (0.86 + 0.14*np.clip(x/OX, 0, 1))
    a = np.clip((x - OX)/160, 0, 1); a = a*a*(3-2*a)       # smooth blend into the photo over 160px
    out[:, :E] = fill*(1-a) + out[:, :E]*a
    out[:, :E] += rng.normal(0, 2.2, (H, E, 1))*(1-a)      # match the photo's grain
    Image.fromarray(np.clip(out,0,255).astype(np.uint8)).save(f'public/cards/v3/card-{name}.webp', quality=92)
print('ok')
