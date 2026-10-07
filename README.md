# Break Check

Pokémon and One Piece TCG price and break checker. Check a price before you buy, log what you pulled (or what you bought sealed), and share a BREAK card or itemised receipt with live prices.

**Live:** https://pokesnipr.com

## How it's built

| Part | Where | What it does |
|---|---|---|
| App | `site/index.html` | The whole front end: markup, styles and script (no framework). **Edit this.** |
| Search | `site/search.js` | In-browser search over `public/catalog.json`, language filter, live-price lookups. |
| Server | `src/worker.js` | Cloudflare Worker: live prices (`/api/live`), FX (`/api/fx`), product images (`/img/:id/:size`), share links (`/api/share`, `/i/:id`, `/r/:id`), redirects to pokesnipr.com. |
| Static files | `public/` | Built page, catalog, icons, card art, privacy/terms pages, app manifest. |
| One Piece catalog | `scripts/build_onepiece.py` | Daily: every English One Piece single and sealed product with TCGplayer prices → `public/catalog-onepiece.json`. The app loads it only when someone switches to One Piece. |
| Price catalog | `scripts/build_catalog.py` | Daily: every English and Japanese single and sealed product with TCGplayer prices; Chinese from PriceCharting when `PRICECHARTING_TOKEN` is set. |
| Page build | `scripts/build_site.py` | Injects `site/search.js` into `site/index.html` → `public/index.html`, writes `public/version.json`. |
| Card art | `cards/` | Source images and scripts that make the BREAK card / receipt plates in `public/cards/v3/`. |
| Config | `wrangler.toml` | Worker, routes (pokesnipr.com, www), static assets, KV namespace `SHARES` (share links). |

## Develop and deploy

```bash
python scripts/build_site.py          # after editing site/index.html or site/search.js
python scripts/build_catalog.py       # optional: refresh prices locally (needs internet)
npx wrangler@4 deploy                 # needs CLOUDFLARE_API_TOKEN in the environment
```

Open tabs pick up a new deploy automatically (they poll `/version.json`).

## Automation

`.github/workflows/refresh-prices.yml` rebuilds the catalog and deploys twice a day (after TCGplayer's daily price file lands).

Repo secrets it needs:

- `CLOUDFLARE_API_TOKEN` — Cloudflare API token with *Workers Scripts: Edit* (and KV) on the account.
- `CARDOS_API_KEY` — CardOS key for Chinese singles. Used weekly (Mondays) to refresh the Chinese card list; other days the list is carried over from the live catalog. The Worker also needs it as a secret (`wrangler secret put CARDOS_API_KEY`) for on-pick prices (`/api/cn/prices`, cached 24h in KV).
- `PRICECHARTING_TOKEN` — optional; a PriceCharting Legendary token. Adds Chinese sealed products and cards from eBay sold data.

## Data sources (know these before relying on the site)

- **One Piece prices:** TCGplayer Market Price via TCGCSV (category 68, English only; TCGplayer has no Japanese One Piece).
- **English / Japanese prices:** TCGplayer Market Price via [TCGCSV](https://tcgcsv.com) (daily mirror) plus TCGplayer's live price points endpoint for items on screen. Neither is a contracted API.
- **Chinese singles:** CardOS (getcardos.com) — values built from completed sales; 500 free credits a month, then pay-as-you-go. Card images proxied through `/cnimg`.
- **Chinese sealed (optional):** PriceCharting (eBay sold data) through the subscriber CSV download.
- **Product images:** TCGplayer's CDN, proxied by the Worker. Owned by their rights holders.
- **User data:** none on the server. Saved breaks live in each visitor's browser (`localStorage`). Share links are stored in Cloudflare KV for up to a year.

## Ownership notes

Brand name, logo/mascot (`public/avatar.png`; full-size originals in `brand/`), card art and the ripped-pack photography in `cards/` are part of the project. Pokémon is a trademark of its owners; the site is unofficial and says so in the footer and Terms.
