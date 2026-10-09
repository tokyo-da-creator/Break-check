"""Adds officially revealed cards (data/reveals.json) to the catalog for sets TCGplayer hasn't listed singles for yet.
They carry no price and no TCGplayer picture; the app shows them as upcoming. Ids sit at 950,000,000+ so they can never
clash with TCGplayer's, and once TCGplayer lists a card with the same number in that set, the reveal entry is dropped."""
import json, os, re, zlib
REVEAL_BASE = 950_000_000
def _num(n): return re.sub(r"^0+(?=\d)", "", str(n).split("/")[0].strip()).lower()
def add_reveals(sets, items, path=os.path.join(os.path.dirname(__file__), "..", "data", "reveals.json")):
    try: data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError: return 0
    added = 0
    for set_name, block in data.items():
        if set_name.startswith("_"): continue
        si = next((i for i, s in enumerate(sets) if s[0] == set_name), None)
        if si is None: print("reveals: set not on TCGplayer yet, skipped:", set_name); continue
        have = {_num(it[2]) for it in items if it[7] == si and it[8] == "c" and it[2]}
        for num, name, rarity in block.get("cards", []):
            if _num(num) in have: continue
            items.append([REVEAL_BASE + zlib.crc32(f"{set_name}|{num}".encode()) % 49_999_999, name, num, rarity, "", None, None, si, "c", None])
            added += 1
        print(f"reveals: {set_name}: {added} revealed cards added ({len(have)} already on TCGplayer)")
    return added
