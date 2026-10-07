"""Build public/movers.json: how every card worth $20+ moved over the last week and month, from TCGplayer's own
price history (near mint). Powers the Top lists (biggest gainers, drops, most sold).

Daily scheduled runs do the full refresh. Other runs reuse the live file unless it's missing (or MOVERS_MODE=full)."""
import json, urllib.request, time, os, sys, datetime, concurrent.futures as cf

OUT = "public/movers.json"
LIVE = "https://pokesnipr.com/movers.json"
MIN_PRICE = float(os.environ.get("MOVERS_MIN", "20"))
BUDGET = float(os.environ.get("MOVERS_BUDGET_SECS", "1500"))
H = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; BreakCheck/1.0; +https://pokesnipr.com)",
     "Origin": "https://www.tcgplayer.com", "Referer": "https://www.tcgplayer.com/"}

def carry_over():
    try:
        raw = urllib.request.urlopen(urllib.request.Request(LIVE, headers={"User-Agent": H["User-Agent"]}), timeout=60).read()
        d = json.loads(raw)
        if d.get("rows"):
            open(OUT, "wb").write(raw); print("movers: carried over", len(d["rows"]), "rows from", d.get("builtAt")); return True
    except Exception as e:
        print("movers: carry-over failed:", e)
    return False

mode = os.environ.get("MOVERS_MODE", "carry")
if mode != "full" and carry_over():
    sys.exit(0)

def vfull(v):
    return "Normal" if not v else "Holofoil" if v == "Holo" else "Reverse Holofoil" if v == "Reverse" else v.replace("Holo", "Holofoil") if "Holofoil" not in v else v

# candidates: single cards worth MIN_PRICE+ (English and Japanese Pokémon, English One Piece)
want = {}
for path, game in (("public/catalog.json", "pokemon"), ("public/catalog-onepiece.json", "onepiece")):
    try: cat = json.load(open(path))
    except Exception as e: print("skip", path, e); continue
    S = cat["sets"]
    for e in cat["items"]:
        if e[8] != "c" or S[e[7]][2] == 2: continue
        price = e[5] if e[5] is not None else e[6]
        if price is None or price < MIN_PRICE: continue
        want.setdefault(e[0], []).append((e[4], "Japanese" if S[e[7]][2] == 1 else "English", game))
print("movers: products to check", len(want))

today = datetime.date.today()
d7, d30 = today - datetime.timedelta(days=7), today - datetime.timedelta(days=30)

def hist(pid):
    url = f"https://infinite-api.tcgplayer.com/price/history/{pid}/detailed?range=month"
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30))
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            time.sleep(1.5 * (i + 1))
        except Exception: time.sleep(1.5 * (i + 1))
    return None

def work(pid):
    d = hist(pid)
    if not d: return pid, []
    out = []
    for variant, lang, game in want[pid]:
        vf = vfull(variant)
        ser = [x for x in d.get("result") or [] if x.get("variant") == vf and x.get("condition") in ("Near Mint", "Unopened")]
        ser = [x for x in ser if x.get("language") == lang] or ser
        if not ser: continue
        pts = []
        for b in ser[0].get("buckets") or []:
            try: pts.append((datetime.date.fromisoformat(b["bucketStartDate"][:10]), float(b["marketPrice"]), int(float(b.get("quantitySold") or 0))))
            except Exception: pass
        pts = [p for p in pts if p[1] > 0]
        if len(pts) < 3: continue
        pts.sort()
        now = pts[-1][1]
        w = [p for p in pts if p[0] <= d7]
        p7 = w[-1][1] if w else None
        p30 = pts[0][1]
        sold7 = sum(p[2] for p in pts if p[0] > d7)
        sold30 = sum(p[2] for p in pts)
        out.append([pid, variant, round(now, 2), round(p7, 2) if p7 else None, round(p30, 2), sold7, sold30, game])
    return pid, out

rows, done, t0, failed = [], 0, time.time(), 0
with cf.ThreadPoolExecutor(8) as ex:
    futs = {ex.submit(work, pid): pid for pid in want}
    for f in cf.as_completed(futs):
        pid, r = f.result(); done += 1
        if not r: failed += 1
        rows.extend(r)
        if done % 500 == 0: print("movers:", done, "/", len(want), "rows", len(rows), "secs", round(time.time() - t0))
        if time.time() - t0 > BUDGET:
            print("movers: time budget reached at", done); ex.shutdown(wait=False, cancel_futures=True); break

if len(rows) < 200:
    print("movers: too few rows (", len(rows), "), keeping the live file"); carry_over(); sys.exit(0)
json.dump({"builtAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}, open(OUT, "w"), separators=(",", ":"))
print("movers: wrote", len(rows), "rows from", done, "products,", failed, "without history, in", round(time.time() - t0), "secs")
