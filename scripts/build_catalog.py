"""Rebuild public/catalog.json: every English + Japanese Pokémon single and sealed product with TCGplayer prices.
Source: TCGCSV, a public daily mirror of TCGplayer's price data. Fails loudly rather than publishing a partial catalog."""
import json, urllib.request, time, re, concurrent.futures as cf, datetime, email.utils, sys, os
OUT = os.environ.get("OUT", "public/catalog.json")
UA={"User-Agent":"BreakCheck/1.0 (+https://break-check-vr59.netlify.app)"}
def get(u, tries=3):
    for i in range(tries):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60))
        except Exception: time.sleep(0.5*(i+1))
    raise RuntimeError(u)
SV="2023-03-31"
# English special sets whose Elite Trainer Box has 10 packs instead of the usual 8.
ETB10=re.compile(r"crown zenith|hidden fates|champion'?s path|shining fates|celebrations|pokemon go|shining legends|dragon majesty", re.I)
# Japanese box sizes: standard 30 packs; 7-card sets 20; High Class 10. Only sets we are sure of get a per-pack split.
JP20=re.compile(r"^(SV2a|SV11B|SV11W|M6a):", re.I)
JP10=re.compile(r"^(SV4a|SV8a|M2a|S12a|S8b):|high class", re.I)
JP_UNSURE=re.compile(r"^(S8a|s8a-G|S10b):", re.I)
def packs_for(n, pub, setname="", jp=0):
    n=n.lower()
    if re.search(r"\b(case|code card|display|blister|art bundle|fun pack|collection|tins?|deluxe|golden)\b", n): return None
    if jp:
        if "booster box" not in n: return 1 if "booster pack" in n else None
        if pub < "2021-01-01" or JP_UNSURE.search(setname): return None
        if JP10.search(setname): return 10
        if JP20.search(setname): return 20
        return 30
    if "half booster box" in n: return 18
    if "booster box" in n: return 36
    if "pokemon center elite trainer box" in n: return 11 if pub>=SV else (None if "plus" in n else 10)
    if "elite trainer box" in n: return 9 if pub>=SV else 10 if ETB10.search(setname+" "+n) else 8
    if "booster bundle" in n: return 6
    if "build & battle box" in n: return 4
    if "booster pack" in n: return 1
    return None
def vshort(v): return "" if v=="Normal" else "Holo" if v=="Holofoil" else "Reverse" if v=="Reverse Holofoil" else v.replace("Holofoil","Holo")
# When TCGplayer's daily price file was published (shown in the app header as "updated Xh ago").
req=urllib.request.Request("https://tcgcsv.com/tcgplayer/3/groups", headers=UA, method="HEAD")
lm=urllib.request.urlopen(req, timeout=60).headers.get("Last-Modified")
published=email.utils.parsedate_to_datetime(lm).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if lm else datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
groups=[]
for cid,jp in ((3,0),(85,1)):
    for g in get(f"https://tcgcsv.com/tcgplayer/{cid}/groups")["results"]:
        groups.append((cid,jp,g["groupId"],g["name"],str(g["publishedOn"])[:10]))
def fetch(g):
    cid,jp,gid,name,date=g
    prods=get(f"https://tcgcsv.com/tcgplayer/{cid}/{gid}/products")["results"]
    prices=get(f"https://tcgcsv.com/tcgplayer/{cid}/{gid}/prices")["results"]
    return g,prods,prices
sets=[]; items=[]
t=time.time()
with cf.ThreadPoolExecutor(6) as ex:
    for g,prods,prices in ex.map(fetch, groups):
        cid,jp,gid,name,date=g
        si=len(sets); sets.append([name,date,jp,gid])
        by={p["productId"]:p for p in prods}
        # Every product is listed, even ones TCGplayer has no price for yet (they show as unpriced, never left out).
        priced={pr["productId"] for pr in prices}
        prices=list(prices)+[{"productId":pid,"subTypeName":"","marketPrice":None,"lowPrice":None,"_unpriced":True} for pid in by if pid not in priced]
        for pr in prices:
            p=by.get(pr["productId"])
            if not p or re.search("code card",p["name"],re.I): continue
            m=pr.get("marketPrice"); l=pr.get("lowPrice")
            m=m if isinstance(m,(int,float)) and m>0 else None
            l=l if isinstance(l,(int,float)) and l>0 else None
            if m is None and l is None and not pr.get("_unpriced"):
                # Price row exists but empty: keep it only if no other variant of this product has a price.
                if any(q["productId"]==pr["productId"] and (q.get("marketPrice") or q.get("lowPrice")) for q in prices): continue
            ext={e["name"]:e["value"] for e in (p.get("extendedData") or [])}
            num=ext.get("Number","")
            card=bool(num) or bool(ext.get("Rarity"))
            nm=re.sub(r"\s+-\s+[\w/-]+$","",p["name"]) if card else p["name"]
            items.append([p["productId"],nm,num,ext.get("Rarity",""),vshort(pr.get("subTypeName") or ""),m,l,si,"c" if card else "s",None if card else packs_for(p["name"],date,name,jp)])
# ---- Chinese (Simplified / Traditional) from PriceCharting: eBay-sold prices, refreshed daily ----
# Needs PRICECHARTING_TOKEN (a PriceCharting subscription). Without it, or if the download fails, the catalog simply has no Chinese sets.
CN_BASE = 900_000_000   # keeps PriceCharting ids clear of TCGplayer product ids
def add_chinese():
    tok = os.environ.get("PRICECHARTING_TOKEN", "").strip()
    if not tok: print("chinese: no PRICECHARTING_TOKEN, skipped"); return 0
    import csv, io
    url = f"https://www.pricecharting.com/price-guide/download-custom?t={tok}&category=pokemon-cards"
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read().decode("utf-8", "replace")
    except Exception as e:
        print("chinese: download failed:", e); return 0
    rows = list(csv.DictReader(io.StringIO(raw)))
    def money_(v):
        v = (v or "").replace("$", "").replace(",", "").strip()
        try: f = float(v); return f if f > 0 else None
        except ValueError: return None
    by_set = {}
    for r in rows:
        con = r.get("console-name") or ""
        if not re.search(r"chinese", con, re.I): continue
        by_set.setdefault(con, []).append(r)
    n = 0
    SEALED = re.compile(r"booster (box|pack|bundle)|\bbox\b|\bpack\b|\btin\b|collection|gift|display|\bcase\b|bundle|blister|deck|starter|premium|special set", re.I)
    for con, rs in sorted(by_set.items()):
        dates = [r.get("release-date") or "" for r in rs if r.get("release-date")]
        name = re.sub(r"^pokemon\s+", "", con, flags=re.I)
        si = len(sets); sets.append([name, (min(dates) if dates else "2020-01-01")[:10], 2, CN_BASE])
        for r in rs:
            pn = (r.get("product-name") or "").strip()
            if not pn: continue
            m = re.search(r"#\s*([\w/-]+)\s*$", pn)
            num = m.group(1) if m else ""
            nm = re.sub(r"\s*#\s*[\w/-]+\s*$", "", pn)
            sealed = not num and bool(SEALED.search(pn))
            price = money_(r.get("loose-price")) or money_(r.get("new-price"))
            packs = (1 if re.search(r"booster pack|\bpack\b", pn, re.I) and not re.search(r"box|bundle", pn, re.I) else None) if sealed else None
            if sealed and name.lower().split()[-1] not in nm.lower(): nm = f"{name} {nm}"
            items.append([CN_BASE + int(r["id"]), nm, num, "", "", price, None, si, "s" if sealed else "c", packs])
            n += 1
    print("chinese: sets", len(by_set), "items", n)
    return n
add_chinese()

# ---- Chinese singles from CardOS (completed-sale prices; fetched per card on demand by the Worker) ----
# The card list (names, numbers, images) is synced weekly to stay inside CardOS's free monthly credits.
# On other days, or without CARDOS_API_KEY, the Chinese part of the live catalog is carried over unchanged.
import zlib
CARDOS = "https://api.getcardos.com/api/v1/pokemon"
cn_map = {}
def cn_num(cid): return 800_000_000 + zlib.crc32(cid.encode()) % 99_999_999
def add_cardos():
    key = os.environ.get("CARDOS_API_KEY", "").strip()
    full = key and (datetime.datetime.utcnow().weekday() == 0 or os.environ.get("CN_FULL_SYNC") == "1")
    if not full:
        try:
            live = json.load(urllib.request.urlopen(urllib.request.Request("https://pokesnipr.com/catalog.json", headers=UA), timeout=60))
            old_sets = live.get("sets", []); keep = {i for i, st in enumerate(old_sets) if st[2] == 2 and st[3] == -1}
            remap = {}
            for i in sorted(keep): remap[i] = len(sets); sets.append(old_sets[i])
            n = 0
            for it in live.get("items", []):
                if it[7] in remap: it = list(it); it[7] = remap[it[7]]; items.append(it); n += 1
            cn_map.update(live.get("cn", {}))
            print("cardos: carried over", len(remap), "sets", n, "cards")
            if n or not key: return
        except Exception as e:
            print("cardos: carry-over failed:", e)
            if not key: return
    by_set = {}; page = 1; total = None
    while True:
        u = f"{CARDOS}/cards?language=zh&page_size=100&page={page}"
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={**UA, "X-API-Key": key}), timeout=60))
        rows = d.get("data") or []
        total = d.get("total_count") or total
        for c in rows:
            ex = c.get("expansion") or {}
            sid = ex.get("id") or "zh"
            if sid not in by_set:
                rd = (ex.get("release_date") or "2020/01/01").replace("/", "-")[:10]
                by_set[sid] = [ex.get("name") or sid, rd, 2, -1]
            img = ((c.get("images") or [{}])[0] or {}).get("large") or ""
            num = cn_num(c["id"]); cn_map[str(num)] = [c["id"], img]
            by_set[sid].append(c)
        if not rows or page * 100 >= (total or 0): break
        page += 1
    n = 0
    for sid, row in sorted(by_set.items(), key=lambda kv: kv[1][1]):
        meta, cards = row[:4], row[4:]
        si = len(sets); sets.append(meta)
        for c in cards:
            items.append([cn_num(c["id"]), c.get("name") or "", c.get("printed_number") or c.get("number") or "", c.get("rarity") or "", "", None, None, si, "c", None])
            n += 1
    print("cardos: synced", len(by_set), "sets", n, "cards in", page, "requests")
add_cardos()
out={"builtAt":published,"sets":sets,"items":items,"cn":cn_map}
if len(items) < 70000 or len(sets) < 600:
    sys.exit(f"Catalog looks incomplete ({len(items)} items, {len(sets)} sets); not publishing.")
s=json.dumps(out,separators=(",",":"))
open(OUT,"w").write(s)
print("items",len(items),"sets",len(sets),"MB",round(len(s)/1e6,2),"secs",round(time.time()-t))
