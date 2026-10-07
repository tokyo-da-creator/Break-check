"""Rebuild public/catalog-onepiece.json: every English One Piece Card Game single and sealed product with TCGplayer prices.
Same source and row format as the Pokémon catalog (TCGCSV, a public daily mirror of TCGplayer). Fails loudly rather than publishing a partial catalog."""
import json, urllib.request, time, re, concurrent.futures as cf, datetime, email.utils, sys, os
OUT = os.environ.get("OUT_OP", "public/catalog-onepiece.json")
UA = {"User-Agent": "BreakCheck/1.0 (+https://pokesnipr.com)"}
CAT = 68

def get(u, tries=3):
    for i in range(tries):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception: time.sleep(0.5 * (i + 1))
    raise RuntimeError(u)

def packs_for(n, setname):
    """How many packs a sealed product holds, only where we're sure. English One Piece: booster and extra booster boxes 24, premium booster boxes 10."""
    n = n.lower()
    if re.search(r"\b(case|display|double pack|set|tin|collection|gift|starter|deck|don!!)\b", n) and "booster box" not in n: return None
    if "booster box case" in n or "display" in n: return None
    if "booster box" in n: return 10 if re.search(r"premium booster|^prb", setname, re.I) else 24
    if re.search(r"\bbooster pack\b", n): return 1
    # Extra Boosters are listed as "...Edition Box" / "...Edition Pack".
    if n.startswith("extra booster") and n.endswith(" box"): return 24
    if n.startswith("extra booster") and n.endswith(" pack"): return 1
    return None

def vshort(v): return "" if v == "Normal" else v

req = urllib.request.Request(f"https://tcgcsv.com/tcgplayer/{CAT}/groups", headers=UA, method="HEAD")
lm = urllib.request.urlopen(req, timeout=60).headers.get("Last-Modified")
published = (email.utils.parsedate_to_datetime(lm).astimezone(datetime.timezone.utc) if lm else datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

groups = [(g["groupId"], g["name"], g.get("abbreviation") or "", str(g["publishedOn"])[:10]) for g in get(f"https://tcgcsv.com/tcgplayer/{CAT}/groups")["results"]]

def fetch(g):
    gid = g[0]
    return g, get(f"https://tcgcsv.com/tcgplayer/{CAT}/{gid}/products")["results"], get(f"https://tcgcsv.com/tcgplayer/{CAT}/{gid}/prices")["results"]

sets, items = [], []
t = time.time()
with cf.ThreadPoolExecutor(6) as ex:
    for (gid, name, abbr, date), prods, prices in ex.map(fetch, groups):
        # "OP09: Emperors in the New World": the code is what players search and say.
        code = abbr.split()[0] if abbr else ""
        label = f"{code}: {name}" if code and not name.upper().startswith(code.upper()) else name
        si = len(sets); sets.append([label, date, 0, gid])
        by = {p["productId"]: p for p in prods}
        priced = {pr["productId"] for pr in prices}
        prices = list(prices) + [{"productId": pid, "subTypeName": "", "marketPrice": None, "lowPrice": None, "_unpriced": True} for pid in by if pid not in priced]
        for pr in prices:
            p = by.get(pr["productId"])
            if not p: continue
            m = pr.get("marketPrice"); l = pr.get("lowPrice")
            m = m if isinstance(m, (int, float)) and m > 0 else None
            l = l if isinstance(l, (int, float)) and l > 0 else None
            if m is None and l is None and not pr.get("_unpriced"):
                if any(q["productId"] == pr["productId"] and (q.get("marketPrice") or q.get("lowPrice")) for q in prices): continue
            ext = {e["name"]: e["value"] for e in (p.get("extendedData") or [])}
            num = ext.get("Number", "")
            card = bool(num) or bool(ext.get("Rarity")) or p["name"].startswith("DON!! Card")
            if re.search(r"\b(playmat|sleeves?|deck box|binder|storage)\b", p["name"], re.I): card = False   # accessories, not cards
            items.append([p["productId"], p["name"], num, ext.get("Rarity", ""), vshort(pr.get("subTypeName") or ""), m, l, si, "c" if card else "s",
                          None if card else packs_for(p["name"], label)])

if len(items) < 5000 or len(sets) < 50:
    sys.exit(f"One Piece catalog looks incomplete ({len(items)} items, {len(sets)} sets); not publishing.")
s = json.dumps({"builtAt": published, "game": "onepiece", "sets": sets, "items": items, "cn": {}}, separators=(",", ":"))
open(OUT, "w").write(s)
print("onepiece items", len(items), "sets", len(sets), "MB", round(len(s) / 1e6, 2), "secs", round(time.time() - t))
