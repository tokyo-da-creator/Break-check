// Standalone build: answers the page's /api calls in the browser from a bundled price snapshot.
window.__noShare = true;
(function(){
  var realFetch=window.fetch.bind(window);
  var FX_AUD = __FX__;
  // One catalog per game, loaded the first time that game is used.
  var CATS = {pokemon:'catalog.json', onepiece:'catalog-onepiece.json'}, catP = {};
  if(!window.__game){ try{ window.__game = JSON.parse(localStorage.getItem('bc:game')) || 'pokemon'; }catch(e){ window.__game = 'pokemon'; } }
  function game(){ return CATS[window.__game] ? window.__game : 'pokemon'; }
  // Short names collectors type for rarities.
  var RAR=[[/special illustration/i,'sir'],[/special art/i,'sar'],[/illustration rare/i,'ir'],[/art rare/i,'ar'],[/hyper/i,'hr'],
           [/ultra/i,'ur'],[/double/i,'dr'],[/secret/i,'sr'],[/shiny/i,'shiny'],[/super rare/i,'sr']];
  function abbr(r){ r=r||''; for(var i=0;i<RAR.length;i++) if(RAR[i][0].test(r)) return RAR[i][1]; return ''; }
  function lev(a,b,max){
    if(Math.abs(a.length-b.length)>max) return max+1;
    var prev=[],cur,i,j; for(j=0;j<=b.length;j++) prev[j]=j;
    for(i=1;i<=a.length;i++){ cur=[i]; var lo=i;
      for(j=1;j<=b.length;j++){ cur[j]=Math.min(prev[j]+1,cur[j-1]+1,prev[j-1]+(a[i-1]===b[j-1]?0:1)); if(cur[j]<lo) lo=cur[j]; }
      if(lo>max) return max+1; prev=cur; }
    return prev[b.length];
  }
  // Fix a misspelt word by finding the closest real card or product word.
  function fixWord(c, w){
    if(w.length<4 || /\d/.test(w)) return null;
    if(!c.words){ var seen={}; c.items.forEach(function(e){ e[1].toLowerCase().replace(/é/g,'e').split(/[^a-z0-9']+/).forEach(function(x){ if(x.length>=3) seen[x]=1; }); }); c.words=Object.keys(seen); }
    var max = w.length>=7 ? 2 : 1, best=null, bd=max+1;
    for(var i=0;i<c.words.length;i++){ var d=lev(w,c.words[i],max); if(d<bd){ bd=d; best=c.words[i]; if(d===0) break; } }
    return bd<=max ? best : null;
  }
  // Same card, different version. These get searchable aliases and rank below the normal set version unless you ask for them.
  var SPECIAL=[[/prize pack/i,'prize pack stamped stamp pp play pokemon'],[/jumbo/i,'jumbo oversized'],[/deck exclusive/i,'deck exclusive'],
    [/world championship/i,'worlds world championship gold border'],[/mcdonald/i,'mcdonalds mcdonald'],[/trick or trade/i,'trick or trade halloween'],
    [/battle academy/i,'battle academy'],[/league|championship/i,'league championship staff promo'],[/promo/i,'promo'],[/miscellaneous/i,'misc'],
    [/shadowless/i,'shadowless'],[/trainer kit|starter|theme deck|battle deck/i,'deck']];
  function specialOf(setName){ for(var i=0;i<SPECIAL.length;i++) if(SPECIAL[i][0].test(setName)) return SPECIAL[i][1]; return ''; }
  // What collectors call a set vs. what TCGplayer calls it.
  var SET_ALIAS=[[/^celebrations/i,'25th anniversary 25th anni celebration'],[/30th celebration/i,'30th anniversary 30th anni'],
    [/scarlet & violet 151|^sv2a/i,'151 sv151 pokemon 151'],[/shining fates/i,'shiny vault shining'],[/hidden fates/i,'shiny vault hf'],
    [/paldean fates/i,'shiny vault pf'],[/crown zenith/i,'cz galarian gallery'],[/prismatic evolutions/i,'pe prismatic eevee'],
    [/evolving skies/i,'evs eeveelutions'],[/brilliant stars/i,'brs'],[/lost origin/i,'lor'],[/silver tempest/i,'sit'],[/astral radiance/i,'asr'],
    [/surging sparks/i,'ssp'],[/stellar crown/i,'scr'],[/twilight masquerade/i,'twm'],[/temporal forces/i,'tef'],[/paradox rift/i,'par'],
    [/obsidian flames/i,'obf'],[/paldea evolved/i,'pal'],[/journey together/i,'jtg'],[/destined rivals/i,'dri'],[/black bolt/i,'blk zekrom'],
    [/white flare/i,'wht reshiram'],[/mega evolution/i,'meg mega'],[/phantasmal flames/i,'pfl'],[/^base set/i,'base wotc vintage'],
    [/pokemon go/i,'pgo go'],[/champion'?s path/i,'cp champions path'],[/vivid voltage/i,'viv'],[/fusion strike/i,'fst'],[/chilling reign/i,'cre'],
    [/battle styles/i,'bst'],[/darkness ablaze/i,'daa'],[/rebel clash/i,'rcl'],[/sword & shield/i,'swsh'],[/team rocket/i,'rocket']];
  function setAlias(n){ var o=''; for(var i=0;i<SET_ALIAS.length;i++) if(SET_ALIAS[i][0].test(n)) o+=' '+SET_ALIAS[i][1]; return o; }
  function prep(c){
    c.hay = c.items.map(function(e){
      var s = c.sets[e[7]];
      var num=String(e[2]||''), lead=num.split('/')[0], bare=lead.replace(/^0+(?=\d)/,'');
      var tail=num.match(/-(\d+)$/); if(tail){ lead=tail[1]; bare=tail[1].replace(/^0+(?=\d)/,''); }   // One Piece "OP09-004": 004 / 4
      var nl=e[1].toLowerCase(), alias=specialOf(s[0])+setAlias(s[0])+' '+(nl.indexOf('elite trainer box')>=0?'etb ':'')+(nl.indexOf('pokemon center')>=0?'pc ':'')+(nl.indexOf('booster box')>=0?'bb ':'');
      return (e[1]+' '+alias+num+' '+(bare!==lead?bare+' ':'')+s[0]+' '+e[3]+' '+abbr(e[3])+' '+e[4]+' '+(s[2]===1?'japanese jp':s[2]===2?'chinese cn simplified':'english en')+' '+(c.game==='onepiece'?(/\(parallel\)|\(alternate art\)/i.test(e[1])?'alt art aa parallel ':'')+(/\(manga\)/i.test(e[1])?'manga ':'')+(/booster box/i.test(e[1])?'bb ':''):'')+' '+(e[8]==='s'?'sealed':'card single')).toLowerCase().replace(/é/g,'e');
    });
    c.vars={}; c.items.forEach(function(e){ (c.vars[e[0]]=c.vars[e[0]]||[]).push(e[4]); });
    // Chinese singles (CardOS): numeric id -> [CardOS id, image url]
    c.cn=c.cn||{}; window.__cnImg=window.__cnImg||{};
    Object.keys(c.cn).forEach(function(k){ if(c.cn[k][1]) window.__cnImg[k]=c.cn[k][1]; });
    return c;
  }
  // Which TCGplayer printing a catalog row is. Only when it's unambiguous; otherwise the daily price stays.
  function printing(c, e){
    var vs=c.vars[e[0]]||[], v=e[4];
    if(vs.length===1) return e[8]==='s' ? 'N' : (/holo|reverse/i.test(v) ? 'F' : 'N') + '*';
    if(vs.length===2 && vs.indexOf('')>=0 && (vs.indexOf('Reverse')>=0 || vs.indexOf('Holo')>=0)) return v==='' ? 'N' : 'F';
    return null;
  }
  // Swap in TCGplayer's live Market Price (what tcgplayer.com shows right now). Falls back to the daily price.
  // Chinese singles: completed-sale price from CardOS, only for items actually picked (each lookup costs a credit).
  function withCN(c, rows, out, picked){
    if(!picked || window.__noShare) return Promise.resolve(out);
    var want=[], at={};
    rows.forEach(function(i,k){ var e=c.items[i], m=c.cn[e[0]]; if(m){ want.push(m[0]); at[m[0]]=k; } });
    if(!want.length) return Promise.resolve(out);
    return realFetch('/api/cn/prices?ids='+want.slice(0,12).map(encodeURIComponent).join(',')).then(function(r){ return r.json(); }).then(function(d){
      var P=d.prices||{};
      Object.keys(P).forEach(function(id){ var k=at[id], p=P[id]; if(k==null || !p) return;
        if(p.market!=null){ out[k].market=p.market; out[k].best=p.market; out[k].basis='sold'; }
        out[k].graded=p.graded||[]; out[k].source='CardOS'; });
      return out;
    }).catch(function(){ return out; });
  }
  function withLive(c, rows, out){
    if(window.__noShare || !rows.length) return Promise.resolve(out);
    var ask=[], hint=[];
    rows.forEach(function(i,k){
      if(c.sets[c.items[i][7]][2]===2){ hint[k]=null; return; }
      var h=printing(c, c.items[i]); hint[k]=h; if(!h) return;
      var id=c.items[i][0];
      if(h.slice(-1)==='*'){ ask.push(id+':N', id+':F'); } else ask.push(id+':'+h);
    });
    if(!ask.length) return Promise.resolve(out);
    var ctl=new AbortController(), t=setTimeout(function(){ ctl.abort(); }, 3000);
    return realFetch('/api/live?ids='+ask.slice(0,40).join(','), {signal: ctl.signal}).then(function(r){ return r.json(); }).then(function(d){
      clearTimeout(t); var P=d.prices||{};
      rows.forEach(function(i,k){
        var h=hint[k]; if(!h) return; var id=c.items[i][0], v;
        if(h.slice(-1)==='*'){ var pref=h[0], other=pref==='N'?'F':'N'; v=P[id+':'+pref]!=null?P[id+':'+pref]:P[id+':'+other]; }
        else v=P[id+':'+h];
        if(v!=null){ out[k].market=v; out[k].best=v; out[k].basis='live'; window.__liveOK=true; }
      });
      return out;
    }).catch(function(){ clearTimeout(t); return out; });
  }
  function cat(g){ g=g||game(); return catP[g] || (catP[g] = fetch(CATS[g]).then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); }).then(function(c){ c.game=g; return prep(c); })); }
  function allCats(){ return Promise.all(Object.keys(CATS).map(function(g){ return cat(g).catch(function(){ return null; }); })).then(function(a){ return a.filter(Boolean); }); }
  // TCGplayer Market Price (what it actually sells for). Lowest listing only when there are no sales yet.
  function best(m,l){ return m!=null ? m : l; }
  function res(c,i){
    var e=c.items[i], s=c.sets[e[7]];
    return {id:e[0], name:e[1], number:e[2], rarity:e[3], variant:e[4], market:e[5], low:e[6], best:best(e[5],e[6]),
      basis:e[5]==null?'listing':'sales', set:s[0], game:c.game||'pokemon', jp:s[2]===1, cn:s[2]===2, source:s[2]===2?(c.cn[e[0]]?'CardOS':'PriceCharting'):'TCGplayer', lang:s[2]===1?'jp':s[2]===2?'cn':'en', kind:e[8]==='s'?'sealed':'card', packs:e[9]};
  }
  var NOT_A_SET=/miscellaneous|promo|prize pack|trainer kit|collection|deck|championship|jumbo|energ|release event|pre-release|tournament|starter|don!!|premium card/i;
  var BREAKABLE={1:1,6:1,9:1,10:1,11:1,24:1,36:1};
  function search(c, u){
    var q=u.searchParams;
    if(q.get('ids')){
      var want={}; q.get('ids').split(',').forEach(function(x){ want[Number(x)]=1; });
      var rows=[]; for(var i=0;i<c.items.length;i++) if(want[c.items[i][0]]) rows.push(i);
      return {results:rows.map(function(i){ return res(c,i); }), rows:rows};
    }
    if(q.get('packof')){
      // The single booster pack from the same set as a box/ETB/bundle.
      var pid=Number(q.get('packof')), si=-1;
      for(var i=0;i<c.items.length;i++) if(c.items[i][0]===pid){ si=c.items[i][7]; break; }
      var pick=-1;
      for(var j=0;j<c.items.length && si>=0;j++){
        var e=c.items[j]; if(e[7]!==si || e[8]!=='s' || e[9]!==1) continue;
        if(/sleeved|blister|code|art bundle|mini|enhanced|deluxe/i.test(e[1])) continue;
        if(pick<0 || /^[^\[]*booster pack$/i.test(e[1])) pick=j;
      }
      return {results: pick>=0 ? [res(c,pick)] : [], rows: pick>=0 ? [pick] : []};
    }
    if(q.get('featured')){
      var today=new Date().toISOString().slice(0,10);
      var order=c.sets.map(function(s,si){ return {s:s, si:si}; })
        .filter(function(o){ return !o.s[2] && o.s[1]<=today && !NOT_A_SET.test(o.s[0]); })
        .sort(function(a,b){ return b.s[3]-a.s[3]; });
      var picks=[], used=0;
      for(var k=0;k<order.length && used<3;k++){
        var si=order[k].si, before=picks.length;
        (c.game==='onepiece' ? [24,1] : [36,9,1]).forEach(function(packs){
          for(var i=0;i<c.items.length;i++){
            var e=c.items[i];
            if(e[7]!==si || e[8]!=='s' || e[9]!==packs) continue;
            if(/pokemon center|sleeved|exclusive|\bcase\b/i.test(e[1])) continue;
            if(best(e[5],e[6])==null) continue;
            picks.push(i); break;
          }
        });
        if(picks.length>before) used++;
      }
      return {results:picks.map(function(i){ return res(c,i); }), rows:picks};
    }
    var qq=(q.get('q')||'').toLowerCase().replace(/é/g,'e').trim().slice(0,80), kind=q.get('kind');
    if(qq.length<2) return {results:[]};
    var t=qq.replace(/[#,]/g,' ').replace(/\bno\.?\s*/g,'').split(/\s+/).filter(Boolean), loose=false;
    var LW={japanese:1,jp:1,jpn:1,japan:1,chinese:2,cn:2,china:2,schinese:2,'s-chinese':2,english:0,en:0,eng:0};
    var lang=({en:0,jp:1,cn:2})[q.get('lang')];
    var tl=t.filter(function(w){ return !(w in LW); });
    if(tl.length && tl.length<t.length){ if(lang==null) lang=LW[t.filter(function(w){ return w in LW; })[0]]; t=tl; qq=t.join(' '); }
    if(lang===2 && !c.sets.some(function(s){ return s[2]===2; })) return {results:[], note:'Chinese prices are being added. Check back soon.'};
    if(!t.length) return {results:[]};
    function find(tk, need){
      var out=[];
      for(var i=0;i<c.items.length;i++){
        var e=c.items[i];
        if(kind==='card' && e[8]!=='c') continue;
        if(kind==='sealed' && e[8]!=='s') continue;
        if(lang!=null && c.sets[e[7]][2]!==lang) continue;
        var h=c.hay[i], n=0;
        for(var j=0;j<tk.length;j++){ if(h.indexOf(tk[j])>=0) n++; else if(need===tk.length) break; }
        if(n>=need) out.push(i);
      }
      return out;
    }
    var hits=find(t, t.length);
    if(!hits.length){
      // Misspelt name? Swap each word for the nearest real one and try again.
      var fixed=t.map(function(w){ return find([w],1).length ? w : (fixWord(c,w)||w); });
      if(fixed.join(' ')!==t.join(' ')){ t=fixed; hits=find(t, t.length); loose=hits.length>0; }
    }
    if(!hits.length && t.length>1){ hits=find(t, t.length-1); loose=hits.length>0; }
    var f=t[0], score={};
    hits.forEach(function(i){
      var e=c.items[i], s=c.sets[e[7]], n=e[1].toLowerCase(), v=0;
      if(n.indexOf(f)===0) v+=4;
      if(setAlias(s[0]).indexOf(qq)>=0) v+=5;   // e.g. "25th anniversary" means the Celebrations set
      var words=n.replace(/é/g,'e').split(/[^a-z0-9']+/);
      for(var j=0;j<t.length;j++){ if(c.hay[i].indexOf(t[j])>=0) v+=3; if(words.indexOf(t[j])>=0) v+=2; }
      if(/pokemon center/.test(n) && t.indexOf('pc')<0 && t.indexOf('center')<0) v-=3;
      if(e[2] && t.some(function(x){ var n0=e[2].split('/')[0], tl=n0.match(/-(\d+)$/); if(tl) n0=tl[1]; return /^\d+$/.test(x) && (n0.replace(/^0+(?=\d)/,'')===x.replace(/^0+(?=\d)/,'')); })) v+=5;
      if(n.split(/\s+/).indexOf(f)>=0) v+=2;
      if(!s[2] && lang==null) v+=1;
      if(e[8]==='s' && e[9]!=null && BREAKABLE[e[9]]) v+=2;
      if(/\bcase\b/i.test(e[1])) v-=3;
      if(e[5]==null) v-=1;
      // A version you didn't ask for (Prize Pack, Jumbo, promo...) sits below the normal card.
      var sp=specialOf(s[0]); if(sp && !sp.split(' ').some(function(w){ return w.length>2 && t.indexOf(w)>=0; })) v-=6;
      if(e[5]==null && e[6]==null) v-=2;
      v+=(Date.parse(s[1])||0)/1e12;
      score[i]=v;
    });
    hits.sort(function(a,b){ return score[b]-score[a]; });
    var top=hits.slice(0,30);
    return {results:top.map(function(i){ return res(c,i); }), rows:top, total:hits.length, loose:loose};
  }
  function json(body, status){ return new Response(JSON.stringify(body), {status: status||200, headers:{'Content-Type':'application/json'}}); }
  window.fetch=function(input, init){
    var url = typeof input==='string' ? input : input.url;
    if(url.indexOf('/api/search')===0){
      var U=new URL(url, location.href);
      if(U.searchParams.get('ids') || U.searchParams.get('packof')){
        // Saved items can come from any game: look them up in every catalog.
        return allCats().then(function(cs){
          var b={results:[]}, jobs=[];
          cs.forEach(function(c){ var r=search(c, U); if(!r.results.length) return; b.builtAt=b.builtAt||c.builtAt;
            jobs.push(withLive(c, r.rows.slice(0,40), r.results.slice(0,40)).then(function(){ return withCN(c, r.rows.slice(0,40), r.results.slice(0,40), true); }).then(function(){ b.results=b.results.concat(r.results); })); });
          if(!b.builtAt && cs[0]) b.builtAt=cs[0].builtAt;
          return Promise.all(jobs).then(function(){ return json(b); });
        }, function(){ return json({error:'Prices couldn’t load. Refresh the page.', results:[]}, 503); });
      }
      return cat().then(function(c){
          var b=search(c, U); b.builtAt=c.builtAt;
          var rows=b.rows||[]; delete b.rows;
          // Live prices for the first 15 results (the ones you can see); the rest update when picked.
          var picked = /[?&]ids=/.test(url), n = picked ? 40 : 15;
          return withLive(c, rows.slice(0,n), b.results.slice(0,n)).then(function(){ return withCN(c, rows.slice(0,n), b.results.slice(0,n), picked); }).then(function(){ return json(b); });
        },
                        function(){ return json({error:'Prices couldn’t load. Refresh the page.', results:[]}, 503); });
    }
    if(url.indexOf('/api/fx')===0) return Promise.resolve(json({AUD: FX_AUD}));
    if(url.indexOf('/api/')===0) return Promise.resolve(json({error:'Not available here.'}, 503));
    return realFetch(input, init);
  };
  cat();
})();
