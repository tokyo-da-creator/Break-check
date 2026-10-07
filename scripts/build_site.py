"""Build public/index.html from the editable source.

  site/index.html  – the whole app (markup, styles, script). Edit this.
  site/search.js   – in-browser price search over public/catalog.json (injected into the page).

Run from the repo root:  python scripts/build_site.py
Writes public/index.html and public/version.json (open tabs auto-reload into a new build).
"""
import json, os, re, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(ROOT, 'site', 'index.html'), encoding='utf-8').read()
search = open(os.path.join(ROOT, 'site', 'search.js'), encoding='utf-8').read()
anchor = "<script>\n(function(){\nconst $ = id"
assert src.count(anchor) == 1, 'app script anchor not found'
# The live site has real /api/fx and /api/share routes, so only search is answered in the browser.
search = search.replace("// Standalone build: answers the page's /api calls in the browser from a bundled price snapshot.\n",
                        "// Price search runs in the browser against the bundled catalog (fast, and no server CPU per keystroke).\n")
search = search.replace("window.__noShare = true;\n", "").replace("  var FX_AUD = __FX__;\n", "")
search = re.sub(r"    if\(url.indexOf\('/api/fx'\).*\n", "", search)
search = re.sub(r"    if\(url.indexOf\('/api/'\)===0\).*\n", "", search)
assert 'FX_AUD' not in search and '__noShare = true' not in search
build = str(int(time.time()))
updater = '''// Auto-update: if a newer version of the site is live, reload into it (never while you're typing).
(function(){ var BUILD='%s';
  function check(){ fetch('/version.json?'+Date.now(),{cache:'no-store'}).then(function(r){return r.json();}).then(function(v){
    if(v && v.build && v.build!==BUILD){ var a=document.activeElement; if(a && /INPUT|TEXTAREA|SELECT/.test(a.tagName)) return; location.reload(); } }).catch(function(){}); }
  document.addEventListener('visibilitychange', function(){ if(!document.hidden) check(); });
  setInterval(check, 120000); setTimeout(check, 4000);
})();''' % build
out = src.replace(anchor, "<script>\n" + search + "\n" + updater + "\n</script>\n" + anchor)
open(os.path.join(ROOT, 'public', 'index.html'), 'w', encoding='utf-8').write(out)
open(os.path.join(ROOT, 'public', 'version.json'), 'w').write(json.dumps({'build': build}))
print('built public/index.html', build)
