"""Build public/grades.json: the PSA 10 value of the most valuable English Pokémon cards, from CardOS.
Powers the "Worth grading" / "Don't bother grading" Top lists.

One search call returns 100 cards with their graded prices for 1 credit, so the top GRADES_PAGES*100 cards
cost GRADES_PAGES credits. Refreshed weekly (Mondays, or GRADES_FULL=1); other runs carry the live file over.
Rows: [tcgplayer_id, variant ('Holo' | 'Reverse' | ''), psa10_value, psa10_sold_count, confidence, cardos_market]"""
import json, os, sys, time, urllib.request, datetime

OUT = "public/grades.json"
LIVE = "https://pokesnipr.com/grades.json"
CARDOS = "https://api.getcardos.com/api/v1/pokemon"
PAGES = int(os.environ.get("GRADES_PAGES", "5"))
UA = {"User-Agent": "Mozilla/5.0 (compatible; BreakCheck/1.0; +https://pokesnipr.com)", "Accept": "application/json"}

def carry_over():
    try:
        raw = urllib.request.urlopen(urllib.request.Request(LIVE, headers=UA), timeout=60).read()
        d = json.loads(raw)
        if d.get("rows"):
            open(OUT, "wb").write(raw); print("grades: carried over", len(d["rows"]), "rows from", d.get("builtAt")); return True
    except Exception as e:
        print("grades: carry-over failed:", e)
    return False

key = os.environ.get("CARDOS_API_KEY", "").strip()
full = key and (datetime.datetime.utcnow().weekday() == 0 or os.environ.get("GRADES_FULL") == "1")
if not full and carry_over(): sys.exit(0)
if not key: print("grades: no CARDOS_API_KEY and nothing to carry over"); sys.exit(0)

def variant(cid):
    return "Reverse" if cid.endswith("vrh") else "Holo" if cid.endswith("vh") else ""

rows = []
for page in range(1, PAGES + 1):
    u = f"{CARDOS}/cards?language=en&orderBy=-market_price&page_size=100&page={page}&include=prices"
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={**UA, "X-API-Key": key}), timeout=60))
    except Exception as e:
        print("grades: page", page, "failed:", e); break
    cards = d.get("data") or []
    for c in cards:
        tcg = c.get("tcgplayer_id")
        p = c.get("pricing") or {}
        g = next((x for x in (p.get("graded") or []) if str(x.get("company")).upper() == "PSA" and str(x.get("grade")) == "10"), None)
        if not tcg or not g or not isinstance(g.get("value"), (int, float)): continue
        try: tcg = int(tcg)
        except ValueError: continue
        rows.append([tcg, variant(c.get("id") or ""), round(g["value"], 2), g.get("sold_count") or 0, g.get("confidence") or "", p.get("market")])
    if len(cards) < 100: break
    time.sleep(0.5)

if len(rows) < 50:
    print("grades: only", len(rows), "rows, keeping the live file"); carry_over(); sys.exit(0)
json.dump({"builtAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}, open(OUT, "w"), separators=(",", ":"))
print("grades: wrote", len(rows), "PSA 10 rows from", page, "requests")
