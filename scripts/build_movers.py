"""Build public/movers.json: how every card and sealed product worth $20+ moved over the last week and month, from
TCGplayer's own price history (near mint for cards, unopened for sealed). Powers the Top lists (biggest gainers, drops, most sold).

Daily scheduled runs do the full refresh. Other runs reuse the live file unless it's missing (or MOVERS_MODE=full)."""
import json, urllib.request, time, os, sys, datetime, concurrent.futures as cf

OUT = "public/movers.json"
LIVE = "https://pokesnipr.com/movers.json"
MIN_PRICE = float(os.environ.get("MOVERS_MIN", "20"))
BUDGET = float(os.environ.get("MOVERS_BUDGET_SECS", "2100"))
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
SEALED_ONLY = False
if mode != "full" and carry_over():
    try: live_rows = json.load(open(OUT))["rows"]
    except Exception: live_rows = []
    has_sealed = any(len(r) > 8 and r[8] == "s" for r in live_rows)
    if len(live_rows) >= 6000 and has_sealed: sys.exit(0)
    if len(live_rows) >= 6000:
        SEALED_ONLY = True; print("movers: live file has no sealed rows yet, adding them")
    else:
        print("movers: live file is thin (", len(live_rows), "rows), rebuilding")

def vfull(v):
    return "Normal" if not v else "Holofoil" if v == "Holo" else "Reverse Holofoil" if v == "Reverse" else v.replace("Holo", "Holofoil") if "Holofoil" not in v else v

# candidates: singles and sealed products worth MIN_PRICE+ (English and Japanese Pokémon, English One Piece)
want = {}
for path, game in (("public/catalog.json", "pokemon"), ("public/catalog-onepiece.json", "onepiece")):
    try: cat = json.load(open(path))
    except Exception as e: print("skip", path, e); continue
    S = cat["sets"]
    for e in cat["items"]:
        if S[e[7]][2] == 2 or e[8] not in ("c", "s"): continue
        if SEALED_ONLY and e[8] != "s": continue
        price = e[5] if e[5] is not None else e[6]
        if price is None or price < MIN_PRICE: continue
        want.setdefault(e[0], []).append((e[4], "Japanese" if S[e[7]][2] == 1 else "English", game, e[8]))
print("movers: products to check", len(want))

today = datetime.date.today()
d7, d30 = today - datetime.timedelta(days=7), today - datetime.timedelta(days=30)

# History comes through the site's own Worker (cached an hour, served from Cloudflare), at a gentle pace.
API = os.environ.get("MOVERS_API", "https://pokesnipr.com/api/card")
def hist(pid):
    url = f"{API}?id={pid}&r=month&sales=0"
    for i in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": H["User-Agent"]}), timeout=40))
            if d.get("ok"): return d
            time.sleep(3 * (i + 1))   # upstream had nothing / was busy: wait and retry
        except Exception: time.sleep(3 * (i + 1))
    return None

def work(pid):
    d = hist(pid)
    if not d: return pid, []
    out = []
    for variant, lang, game, kind in want[pid]:
        vf = vfull(variant)
        ser = [x for x in d.get("series") or [] if x.get("variant") == vf and x.get("condition") in ("Near Mint", "Unopened")]
        ser = [x for x in ser if x.get("language") == lang] or ser
        if not ser: continue
        pts = []
        for p in ser[0].get("points") or []:
            try: pts.append((datetime.date.fromisoformat(p[0][:10]), float(p[1]), int(p[2] or 0)))
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
        out.append([pid, variant, round(now, 2), round(p7, 2) if p7 else None, round(p30, 2), sold7, sold30, game, kind])
    return pid, out

# yesterday's rows, kept for any card TCGplayer doesn't answer for this time
prev = {}
try:
    for r in json.load(urllib.request.urlopen(urllib.request.Request(LIVE, headers={"User-Agent": H["User-Agent"]}), timeout=60)).get("rows", []):
        prev.setdefault(r[0], []).append(r)
except Exception: pass

rows, t0 = [], time.time()
def run(pids, threads, label):
    got, missed = [], []
    with cf.ThreadPoolExecutor(threads) as ex:
        futs = {ex.submit(work, pid): pid for pid in pids}
        for n, f in enumerate(cf.as_completed(futs), 1):
            pid, r = f.result()
            (got.extend(r) if r else missed.append(pid))
            if n % 1000 == 0: print("movers:", label, n, "/", len(pids), "rows", len(got), "secs", round(time.time() - t0))
            if time.time() - t0 > BUDGET:
                print("movers: time budget reached"); ex.shutdown(wait=False, cancel_futures=True)
                missed.extend(p for p in pids if p not in {futs[x] for x in futs if x.done()}); break
    return got, missed
order = sorted(want, key=lambda pid: 0 if any(w[3] == "s" for w in want[pid]) else 1)
got, missed = run(order, int(os.environ.get("MOVERS_THREADS", "4")), "pass 1")
rows.extend(got)
if missed and time.time() - t0 < BUDGET - 120:
    print("movers: retrying", len(missed), "after a pause"); time.sleep(60)
    got, missed = run(missed, 2, "pass 2"); rows.extend(got)
kept = 0
for pid in missed:
    if pid in prev: rows.extend(prev[pid]); kept += 1
done, failed = len(want), len(missed)
print("movers: kept yesterday's numbers for", kept, "cards")

if SEALED_ONLY:
    if len(rows) < 50:
        print("movers: too few sealed rows (", len(rows), "), keeping the live file"); carry_over(); sys.exit(0)
    rows = [r for r in live_rows if not (len(r) > 8 and r[8] == "s")] + rows
elif len(rows) < 200:
    print("movers: too few rows (", len(rows), "), keeping the live file"); carry_over(); sys.exit(0)
json.dump({"builtAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}, open(OUT, "w"), separators=(",", ":"))
print("movers: wrote", len(rows), "rows from", done, "products,", failed, "without history, in", round(time.time() - t0), "secs")
