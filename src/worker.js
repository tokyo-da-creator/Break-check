// Break Check on Cloudflare Workers.
// Static files (page, price catalog, mascot art) are served as assets; this worker handles the few dynamic routes.

const MAX_IMAGE = 1_500_000;                 // bytes per card image
const SHARE_TTL = 60 * 60 * 24 * 365;        // share links live for a year

const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...extra } });

function clean(v, max) {
  if (typeof v !== "string") return "";
  return v.replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function newId() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(10));
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

const ID_RE = /^[A-Za-z0-9]{8,16}$/;

// ---- Chinese singles: completed-sale prices from CardOS, fetched per card and kept 24h ----
const CARDOS = "https://api.getcardos.com/api/v1/pokemon";
const CN_ID = /^[A-Za-z0-9_.-]{2,40}$/;
async function cnPrices(url, env, ctx) {
  const ids = (url.searchParams.get("ids") || "").split(",").map((x) => x.trim()).filter((x) => CN_ID.test(x)).slice(0, 12);
  if (!ids.length) return json({ prices: {} });
  if (!env.CARDOS_API_KEY) return json({ prices: {}, error: "not_configured" }, 200);
  const out = {};
  await Promise.all(ids.map(async (id) => {
    const key = `cnp/${id}`;
    const hit = await env.SHARES.get(key, "json");
    if (hit) { out[id] = hit; return; }
    try {
      const r = await fetch(`${CARDOS}/cards/${encodeURIComponent(id)}/prices`, { headers: { "X-API-Key": env.CARDOS_API_KEY } });
      if (!r.ok) return;
      const d = await r.json(); const p = (d && d.data && d.data.pricing) || {};
      const graded = (p.graded || []).map((g) => ({ company: g.company, grade: g.grade, value: g.value, sold: g.sold_count, last: g.last_sold_at }));
      const row = { market: typeof p.market === "number" ? p.market : null, currency: p.currency || "USD", graded, updated: p.market_updated_at || null, stale: !!p.is_stale };
      out[id] = row;
      ctx.waitUntil(env.SHARES.put(key, JSON.stringify(row), { expirationTtl: 60 * 60 * 24 }));
    } catch (e) {}
  }));
  return json({ prices: out }, 200, { "Cache-Control": "no-store" });
}
// Card images for Chinese singles (same-origin, so share cards can draw them).
const CN_IMG_HOSTS = new Set(["api.rip.fun", "gjnrvwqtdlspyfpezgox.supabase.co"]);
async function cnImage(url, ctx) {
  let u; try { u = new URL(url.searchParams.get("u") || ""); } catch (e) { return new Response("bad", { status: 400 }); }
  if (u.protocol !== "https:" || !CN_IMG_HOSTS.has(u.hostname)) return new Response("bad", { status: 400 });
  const cache = caches.default, ck = new Request(`https://cnimg.cache/${u.hostname}${u.pathname}`);
  let res = await cache.match(ck);
  if (res) return res;
  const r = await fetch(u.toString(), { cf: { cacheTtl: 86400 * 30, cacheEverything: true } });
  if (!r.ok) return new Response("not found", { status: 404 });
  res = new Response(r.body, { headers: { "Content-Type": r.headers.get("Content-Type") || "image/webp", "Cache-Control": "public, max-age=2592000", "Access-Control-Allow-Origin": "*" } });
  ctx.waitUntil(cache.put(ck, res.clone()));
  return res;
}

function isImage(buf) {
  const b = new Uint8Array(buf, 0, Math.min(8, buf.byteLength));
  const jpeg = b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff;
  const png = b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47;
  return jpeg ? "image/jpeg" : png ? "image/png" : null;
}

async function fx(ctx) {
  const cache = caches.default;
  const key = new Request("https://cache.breakcheck/fx");
  const hit = await cache.match(key);
  if (hit) return hit;
  try {
    const r = await fetch("https://open.er-api.com/v6/latest/USD");
    const d = await r.json();
    if (typeof d?.rates?.AUD !== "number") throw new Error("no rate");
    const res = json({ AUD: d.rates.AUD, at: d.time_last_update_utc }, 200, { "Cache-Control": "public, max-age=21600" });
    ctx.waitUntil(cache.put(key, res.clone()));
    return res;
  } catch {
    return json({ error: "Exchange rate unavailable." }, 502, { "Cache-Control": "no-store" });
  }
}

// Live TCGplayer Market Price, the exact number tcgplayer.com shows right now.
// The page asks for "productId:N" (normal printing) or "productId:F" (foil printing); each product is cached for 15 minutes.
const LIVE_TTL = 300;
async function livePoints(id, ctx) {
  const cache = caches.default;
  const key = new Request(`https://cache.breakcheck/live/${id}`);
  const hit = await cache.match(key);
  if (hit) return hit.json();
  const r = await fetch(`https://mpapi.tcgplayer.com/v2/product/${id}/pricepoints`, {
    headers: { "Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; BreakCheck/1.0)" },
  });
  if (!r.ok) throw new Error(`tcgplayer ${r.status}`);
  const d = await r.json();
  if (!Array.isArray(d)) throw new Error("bad shape");
  const pts = { N: null, F: null };
  for (const p of d) {
    const m = typeof p?.marketPrice === "number" && p.marketPrice > 0 ? p.marketPrice : null;
    if (p?.printingType === "Normal") pts.N = m;
    else if (p?.printingType === "Foil") pts.F = m;
  }
  ctx.waitUntil(cache.put(key, new Response(JSON.stringify(pts), { headers: { "Cache-Control": `public, max-age=${LIVE_TTL}` } })));
  return pts;
}
// Cards sold in two printings TCGplayer's price points can't tell apart (Holo vs Reverse, 1st Edition vs Unlimited):
// read each printing's current near-mint market price from TCGplayer's price history instead.
async function liveVariants(id, ctx) {
  const cache = caches.default, key = new Request(`https://cache.breakcheck/livev/${id}`);
  const hit = await cache.match(key); if (hit) return hit.json();
  const r = await fetch(`https://infinite-api.tcgplayer.com/price/history/${id}/detailed?range=month`, {
    headers: { "Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; BreakCheck/1.0)", "Origin": "https://www.tcgplayer.com", "Referer": "https://www.tcgplayer.com/" } });
  if (!r.ok) throw new Error(`tcgplayer ${r.status}`);
  const d = await r.json(), out = {};
  for (const x of d?.result || []) {
    if (!/near mint|unopened/i.test(x.condition || "")) continue;
    const b = (x.buckets || [])[0], m = Number(b?.marketPrice);   // newest bucket first
    if (isFinite(m) && m > 0 && out[x.variant] == null) out[x.variant] = Math.round(m * 100) / 100;
  }
  ctx.waitUntil(cache.put(key, new Response(JSON.stringify(out), { headers: { "Cache-Control": `public, max-age=${LIVE_TTL}` } })));
  return out;
}
async function live(url, ctx) {
  const want = (url.searchParams.get("ids") || "").split(",")
    .map((s) => s.match(/^(\d{1,9}):([NFV])$/)).filter(Boolean).slice(0, 40);
  const ids = [...new Set(want.filter((m) => m[2] !== "V").map((m) => m[1]))];
  const vids = [...new Set(want.filter((m) => m[2] === "V").map((m) => m[1]))].slice(0, 15);
  const got = {}, gotV = {};
  await Promise.all([
    ...ids.map(async (id) => { try { got[id] = await livePoints(id, ctx); } catch {} }),
    ...vids.map(async (id) => { try { gotV[id] = await liveVariants(id, ctx); } catch {} }),
  ]);
  const prices = {};
  for (const m of want) { if (m[2] === "V") continue; const v = got[m[1]]?.[m[2]]; if (v != null) prices[`${m[1]}:${m[2]}`] = v; }
  for (const id of vids) for (const [variant, v] of Object.entries(gotV[id] || {})) prices[`${id}:V:${variant}`] = v;
  return json({ prices, at: new Date().toISOString() }, 200, { "Cache-Control": "no-store" });
}

// Product photos from TCGplayer, served from our own domain so the page can cut out the white backdrop.
async function productImage(id, size, ctx) {
  const cache = caches.default;
  const key = new Request(`https://cache.breakcheck/img/${id}/${size}`);
  const hit = await cache.match(key);
  if (hit) return hit;
  const r = await fetch(`https://tcgplayer-cdn.tcgplayer.com/product/${id}_in_${size === "l" ? "1000x1000" : size === "m" ? "400x400" : "200x200"}.jpg`);
  if (!r.ok) return new Response("Not found", { status: 404, headers: { "Cache-Control": "public, max-age=86400" } });
  const res = new Response(r.body, { headers: { "Content-Type": "image/jpeg", "Cache-Control": "public, max-age=2592000, immutable" } });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

// Card spotlight data: TCGplayer's own 90-day price history and latest sales for one product (what tcgplayer.com shows).
// Normalised and cached for an hour so a busy card costs TCGplayer one call per hour, not one per visitor.
async function cardData(url, ctx) {
  const id = url.searchParams.get("id") || "";
  if (!/^\d{1,9}$/.test(id)) return json({ error: "Bad id." }, 400);
  const range = ({ month: "month", quarter: "quarter", annual: "annual" })[url.searchParams.get("r")] || "quarter";
  const cache = caches.default, key = new Request(`https://cache.breakcheck/card3/${id}/${range}`);
  const hit = await cache.match(key); if (hit) return hit;
  const H = { "Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; BreakCheck/1.0)", "Origin": "https://www.tcgplayer.com", "Referer": "https://www.tcgplayer.com/" };
  const num = (v) => { const n = Number(v); return isFinite(n) && n > 0 ? Math.round(n * 100) / 100 : null; };
  const [h, sl] = await Promise.all([
    fetch(`https://infinite-api.tcgplayer.com/price/history/${id}/detailed?range=${range}`, { headers: H }).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch(`https://mpapi.tcgplayer.com/v2/product/${id}/latestsales`, { method: "POST", headers: { ...H, "Content-Type": "application/json" },
      body: JSON.stringify({ conditions: [], languages: [], variants: [], listingType: "All", limit: 25 }) }).then(r => r.ok ? r.json() : null).catch(() => null),
  ]);
  const series = (h?.result || []).map((x) => ({
    variant: x.variant || "", condition: x.condition || "", language: x.language || "",
    sold: Number(x.totalQuantitySold) || 0,
    // oldest first: [date, market, quantity sold, low sale, high sale]
    points: (x.buckets || []).map((b) => [String(b.bucketStartDate || "").slice(0, 10), num(b.marketPrice), Number(b.quantitySold) || 0, num(b.lowSalePrice), num(b.highSalePrice)])
      .filter((p) => p[0] && p[1] != null).reverse(),
  })).filter((x) => x.points.length);
  const sales = (sl?.data || []).map((x) => ({
    d: String(x.orderDate || "").slice(0, 10), p: num(x.purchasePrice), ship: num(x.shippingPrice) || 0, q: Number(x.quantity) || 1,
    cond: x.condition || "", variant: x.variant || "", language: x.language || "", photos: x.listingType === "ListingWithPhotos",
  })).filter((x) => x.p != null && x.d);
  const res = json({ id: Number(id), range, series, sales, at: new Date().toISOString(), ok: !!(h || sl) }, 200, { "Cache-Control": "public, max-age=900" });
  if (h || sl) ctx.waitUntil(cache.put(key, new Response(res.clone().body, { headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=3600" } })));
  return res;
}

// An X (Twitter) profile picture for the creator badge on share cards. Looked up through the public
// FxTwitter API (no X account needed), image from X's own CDN. Cached a day per handle.
async function xAvatar(url, ctx) {
  const u = (url.searchParams.get("u") || "").replace(/^@/, "").trim();
  if (!/^[A-Za-z0-9_]{1,15}$/.test(u)) return json({ error: "That isn't a valid X username." }, 400);
  const cache = caches.default;
  const key = new Request(`https://cache.breakcheck/xavatar2/${u.toLowerCase()}`);
  const hit = await cache.match(key);
  if (hit) return hit;
  const UA = { "User-Agent": "BreakCheck/1.0 (+https://pokesnipr.com)" };
  let img = null, handle = u;
  try {
    const p = await fetch(`https://api.fxtwitter.com/${encodeURIComponent(u)}`, { headers: UA });
    const d = p.ok ? await p.json() : null;
    const av = d?.user?.avatar_url;
    if (av && /^https:\/\/pbs\.twimg\.com\//.test(av)) {
      handle = d.user.screen_name || u;
      const r = await fetch(av.replace(/_normal(\.\w+)$/, "_400x400$1"), { headers: UA });
      if (r.ok && (r.headers.get("Content-Type") || "").startsWith("image/")) img = r;
    }
  } catch {}
  if (!img) return json({ error: "Couldn't find that X profile picture." }, 404, { "Cache-Control": "public, max-age=300" });
  const res = new Response(img.body, { headers: { "Content-Type": img.headers.get("Content-Type"), "X-Handle": handle, "Access-Control-Expose-Headers": "X-Handle", "Cache-Control": "public, max-age=86400" } });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

async function createShare(req, env) {
  let body;
  try { body = await req.json(); } catch { return json({ error: "Invalid request." }, 400); }
  const items = Array.isArray(body?.items)
    ? body.items.slice(0, 24).map((it) => ({
        name: clean(it?.name, 80), detail: clean(it?.detail, 120), value: clean(it?.value, 24), verified: it?.verified === true,
      })).filter((it) => it.name)
    : [];
  const meta = {
    kind: body?.kind === "verdict" ? "verdict" : "receipt",
    title: clean(body?.title, 90) || "Break Check",
    desc: clean(body?.desc, 220),
    items,
    verified: body?.verified === true,
    currency: body?.currency === "AUD" ? "AUD" : body?.currency === "USD" ? "USD" : "",
    priced: clean(body?.priced, 24),
    created: new Date().toISOString(),
  };
  const id = newId();
  await env.SHARES.put(`meta/${id}`, JSON.stringify(meta), { expirationTtl: SHARE_TTL });
  return json({ id, url: `${new URL(req.url).origin}/r/${id}` });
}

async function uploadImage(req, env, id, which) {
  if (!ID_RE.test(id)) return json({ error: "Not found." }, 404);
  if (!(await env.SHARES.get(`meta/${id}`))) return json({ error: "Not found." }, 404);
  if (await env.SHARES.get(`${which}/${id}`, { type: "stream" })) return json({ error: "Already uploaded." }, 409);
  const buf = await req.arrayBuffer();
  if (!buf.byteLength || buf.byteLength > MAX_IMAGE) return json({ error: "Image too large." }, 413);
  const type = isImage(buf);
  if (!type) return json({ error: "Not an image." }, 400);
  await env.SHARES.put(`${which}/${id}`, buf, { expirationTtl: SHARE_TTL, metadata: { type } });
  return json({ ok: true });
}

async function serveImage(env, id, which) {
  if (!ID_RE.test(id)) return new Response("Not found", { status: 404 });
  const { value, metadata } = await env.SHARES.getWithMetadata(`${which}/${id}`, { type: "stream" });
  if (!value) return new Response("Not found", { status: 404 });
  return new Response(value, {
    headers: { "Content-Type": metadata?.type || "image/jpeg", "Cache-Control": "public, max-age=31536000, immutable" },
  });
}

function sharePage(origin, id, meta) {
  const url = `${origin}/r/${id}`;
  const og = `${origin}/i/${id}/og`;
  const card = `${origin}/i/${id}/card`;
  const t = esc(meta.title);
  const d = esc(meta.desc);
  const cta = meta.kind === "verdict" ? "Check a price yourself" : "Check your own break";
  const ratio = "16 / 9";
  const rows = (meta.items || []).map((it) =>
    `<tr><td><div class="in">${esc(it.name)}</div><div class="id">${esc(it.detail)}</div></td><td class="iv">${esc(it.value)}<div class="${it.verified ? "ok" : "self"}">${it.verified ? "✓ today’s price" : "self-reported"}</div></td></tr>`).join("");
  const breakdown = rows ? `<section class="bd"><h2>Price breakdown${meta.currency ? ` · ${esc(meta.currency)}` : ""}</h2>
<p class="small">${meta.kind === "receipt" ? (meta.verified ? "✓ Every value on this receipt came from TCGplayer prices" + (meta.priced ? ` on ${esc(meta.priced)}` : "") + "." : "Some values on this receipt were entered by hand, so it isn’t verified.") : "How this verdict was worked out."}</p>
<div class="tw"><table>${rows}</table></div></section>` : "";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0B0B0C">
<link rel="icon" href="/favicon.png" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<title>${t} · Break Check</title>
<meta name="description" content="${d}">
<link rel="canonical" href="${url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Break Check">
<meta property="og:title" content="${t}">
<meta property="og:description" content="${d}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${og}">
<meta property="og:image:type" content="image/jpeg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${t}">
<meta name="twitter:description" content="${d}">
<meta name="twitter:image" content="${og}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@500;800&display=swap">
<style>
:root{--bg:#0B0B0C;--fg:#F4F1EA;--muted:#A3A09A;--line:#2C2C30;--win:#C6FF3D;--loss:#FF4D2E;--ink:#0B0B0C;color-scheme:dark}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--fg);font-family:'Archivo','Helvetica Neue',Helvetica,sans-serif;padding-inline:16px;padding-block:20px 48px}
.wrap{max-width:520px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--fg)}
.brand img{width:40px;height:40px;object-fit:contain}
.mark{font-family:'Anton','Impact',sans-serif;font-size:32px;letter-spacing:.04em;line-height:1}
.mark span{color:var(--loss)}
.card{width:100%;max-width:100%;aspect-ratio:${ratio};display:block;border-radius:14px;border:1px solid var(--line);background:#151517}
h1{font-size:22px;line-height:1.25;margin:0;text-wrap:balance}
p{margin:0;color:var(--muted);line-height:1.5}
.cta{display:flex;align-items:center;justify-content:center;min-height:54px;border-radius:12px;background:var(--fg);color:var(--ink);font-weight:800;font-size:17px;text-decoration:none}
.cta:focus-visible{outline:2px solid var(--win);outline-offset:3px}
.small{font-size:13px;color:var(--muted)}
.bd{display:flex;flex-direction:column;gap:10px;border-top:1px dashed var(--line);padding-top:16px}
.bd h2{margin:0;font:700 13px ui-monospace,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse}
td{padding:10px 0;border-bottom:1px solid var(--line);vertical-align:top}
.in{font-weight:700}
.id{font:12px ui-monospace,Menlo,monospace;color:var(--muted)}
.iv{text-align:right;font:700 15px ui-monospace,Menlo,monospace;white-space:nowrap;padding-left:12px;color:var(--win)}
.ok{font:11px ui-monospace,Menlo,monospace;color:var(--win)}
.self{font:11px ui-monospace,Menlo,monospace;color:#FFB020}
</style>
</head>
<body>
<main class="wrap">
<a class="brand" href="/"><img src="/avatar.png" alt=""><span class="mark">BREAK<span>/</span>CHECK</span></a>
<img class="card" src="${card}" alt="${t}">
<h1>${t}</h1>
<p>${d}</p>
${breakdown}
<a class="cta" href="/">${cta} →</a>
<p class="small">Pokémon TCG break checker. Not affiliated with Nintendo, The Pokémon Company or TCGplayer.</p>
</main>
</body>
</html>`;
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const path = url.pathname;

    // One address: www and the old workers.dev link both go to pokesnipr.com (share links keep working).
    if (url.hostname === "www.pokesnipr.com" || url.hostname.endsWith(".workers.dev")) {
      return Response.redirect(`https://pokesnipr.com${path}${url.search}`, 301);
    }

    if (path === "/api/fx") return fx(ctx);

    if (path === "/api/live") return live(url, ctx);
    if (path === "/api/xavatar") return xAvatar(url, ctx);
    if (path === "/api/card") return cardData(url, ctx);
    if (path === "/api/cn/prices") return cnPrices(url, env, ctx);
    if (path === "/cnimg") return cnImage(url, ctx);

    let im = path.match(/^\/img\/(\d{1,9})\/(s|m|l)$/);
    if (im) return productImage(im[1], im[2], ctx);

    if (path === "/api/share" && req.method === "POST") return createShare(req, env);

    let m = path.match(/^\/api\/share\/([A-Za-z0-9]+)\/(card|og)$/);
    if (m && req.method === "PUT") return uploadImage(req, env, m[1], m[2]);

    m = path.match(/^\/i\/([A-Za-z0-9]+)\/(card|og)(?:\.(?:jpg|png))?$/);
    if (m) return serveImage(env, m[1], m[2]);

    m = path.match(/^\/r\/([A-Za-z0-9]+)$/);
    if (m) {
      if (!ID_RE.test(m[1])) return Response.redirect(`${url.origin}/`, 302);
      const raw = await env.SHARES.get(`meta/${m[1]}`);
      if (!raw) return Response.redirect(`${url.origin}/`, 302);
      return new Response(sharePage(url.origin, m[1], JSON.parse(raw)), {
        headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=300" },
      });
    }

    // Static files (page, catalog, mascot art); anything unknown goes back to the app.
    let asset = await env.ASSETS.fetch(req);
    if (asset.status === 404) asset = await env.ASSETS.fetch(new Request(`${url.origin}/`, req));
    // The page itself must never be served stale from any cache: every visit gets the newest version.
    const type = asset.headers.get("Content-Type") || "";
    if (type.includes("text/html")) {
      const res = new Response(asset.body, asset);
      res.headers.set("Cache-Control", "no-store, max-age=0");
      res.headers.set("CDN-Cache-Control", "no-store");
      return res;
    }
    // Price catalog: short cache so daily refreshes show up quickly.
    if (path === "/version.json") {
      const res = new Response(asset.body, asset);
      res.headers.set("Cache-Control", "no-store, max-age=0"); res.headers.set("CDN-Cache-Control", "no-store");
      return res;
    }
    if (path === "/catalog.json") {
      const res = new Response(asset.body, asset);
      res.headers.set("Cache-Control", "public, max-age=300");
      return res;
    }
    return asset;
  },
};
