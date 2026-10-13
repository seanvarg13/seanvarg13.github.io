/* Sean's football site. One IIFE, no build step, no framework, like the baseball site's app.js.
   Data: data/index.js (FB_INDEX: every player), data/teams.js (FB_TEAMS: every team-season's coaches and RB usage),
   data/career.js (FB_CAREER: season lines for the season table), data/fb-<season>.js (FB[season]: that season's
   players with weekly rows), loaded on demand. Pages by hash: #leaders, #player/<id>, #backfields, #team/<TM>/<season>,
   #coaches, #coach/<name>. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const el = (t, cls, txt) => { const e = document.createElement(t); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
  const IDX = window.FB_INDEX || {}, TEAMS = window.FB_TEAMS || {};
  const SEASONS = Object.keys(TEAMS).map(Number).sort((a, b) => a - b), CUR = SEASONS[SEASONS.length - 1];
  const store = { get(k, d) { try { const v = localStorage.getItem("fb." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
                  set(k, v) { try { localStorage.setItem("fb." + k, JSON.stringify(v)); } catch (e) {} } };
  const S = Object.assign({ season: CUR, pos: "WR", sort: null, dir: -1, bfSeason: CUR, coachRole: "hc", coachMin: 2 }, store.get("state", {}));
  const save = () => store.set("state", S);

  // ---------- loading ----------
  const scripts = {};
  function loadScript(src) {   // the season table's career file only loads with a player page
    if (!scripts[src]) scripts[src] = new Promise((res, rej) => { const s = document.createElement("script"); s.src = `${src}?v=${window.FB_BUILD || ""}`; s.onload = res; s.onerror = () => { delete scripts[src]; rej(new Error("load")); }; document.head.append(s); });
    return scripts[src];
  }
  const loading = {};
  function ensure(y) {
    if (window.FB && window.FB[y]) return Promise.resolve(window.FB[y]);
    if (!loading[y]) loading[y] = new Promise((res, rej) => { const s = document.createElement("script"); s.src = `data/fb-${y}.js?v=${window.FB_BUILD || ""}`;
      s.onload = () => res(window.FB[y]); s.onerror = () => { delete loading[y]; rej(new Error("load")); }; document.head.append(s); });
    return loading[y];
  }

  // ---------- formatting and colour ----------
  const STOPS = [[54, 97, 173], [180, 207, 209], [216, 33, 41]];   // Savant's blue / middle / red, as the baseball site's pctStyle
  function heat(p) {
    const t = Math.max(0, Math.min(100, p)) / 100, lo = t < .5, a = lo ? STOPS[0] : STOPS[1], b = lo ? STOPS[1] : STOPS[2], u = lo ? t * 2 : (t - .5) * 2;
    const c = a.map((x, i) => Math.round(x + (b[i] - x) * u)), lum = (.2126 * c[0] + .7152 * c[1] + .0722 * c[2]) / 255;
    return { bg: `rgb(${c})`, fg: lum < .55 ? "#fff" : "#0c2340" };
  }
  const paint = (node, p) => { if (p == null || !isFinite(p)) return node; const h = heat(p); node.style.background = h.bg; node.style.color = h.fg; node.classList.add("heat"); return node; };
  const num = (v, d = 1) => v == null || !isFinite(v) ? "–" : v.toFixed(d);
  const sgn = (v, d = 1) => v == null || !isFinite(v) ? "–" : (Math.abs(v) < Math.pow(10, -d) / 2 ? (0).toFixed(d) : (v > 0 ? "+" : "−") + Math.abs(v).toFixed(d));
  const pc = (v, d = 1) => v == null || !isFinite(v) ? "–" : v.toFixed(d) + "%";
  const ord = (n) => { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };
  const posGroup = (p) => (p === "FB" ? "RB" : p);
  const htFmt = (h) => (h ? `${Math.floor(h / 12)}-${h % 12}` : null);

  // ---------- derived metrics ----------
  const passFP = (p) => (p.pyd || 0) / 25 + 4 * (p.ptd || 0) - 2 * (p.int_ || 0);
  const memo = new WeakMap();
  function M(p) {
    if (memo.has(p)) return memo.get(p);
    const g = Math.max(p.g || 0, 1), opp = (p.car || 0) + (p.tgt || 0), touch = (p.car || 0) + (p.rec || 0);
    const xfp = (p.xr || 0) + (p.xu || 0) + (posGroup(p.pos) === "QB" ? passFP(p) : 0);
    const m = {
      g: p.g, tgt: p.tgt, rec: p.rec, ryd: p.ryd, rtd: p.rtd, car: p.car, ruyd: p.ruyd, rutd: p.rutd,
      att: p.att, pyd: p.pyd, ptd: p.ptd, int: p.int_, rts: p.rts,
      cmpp: p.att ? 100 * p.cmp / p.att : null,
      rte: p.tmdb ? 100 * p.rts / p.tmdb : null,
      tprr: p.rts >= 1 ? 100 * p.tgt / p.rts : null,
      tgtsh: p.tmt ? 100 * p.tgt / p.tmt : null,
      aysh: p.tmay > 0 ? 100 * p.ay / p.tmay : null,
      adot: p.tgt ? p.ay / p.tgt : null,
      wopr: p.tmt && p.tmay > 0 ? 1.5 * p.tgt / p.tmt + 0.7 * p.ay / p.tmay : null,
      rzt: p.rzt, glc: p.glc, rzc: p.rzc,
      yprr: p.rts >= 1 ? p.ryd / p.rts : null,
      ypr: p.rec ? p.ryd / p.rec : null,
      croe: p.xcn ? 100 * (p.cc - p.xc) / p.xcn : null,
      yacoe: p.yacn ? (p.yacs - p.xyac) / p.yacn : null,
      carsh: p.tmc ? 100 * p.car / p.tmc : null,
      snp: p.snpct, ypc: p.car ? p.ruyd / p.car : null,
      ryoe: p.ngsatt ? p.ryoe / p.ngsatt : null,
      oppg: opp / g, fppo: opp ? ((p.frt || 0) + (p.fru || 0)) / opp : null, fppt: touch ? p.fp / touch : null,
      xppo: opp ? ((p.xr || 0) + (p.xu || 0)) / opp : null,
      fpg: p.fp / g, xfpg: xfp / g, fpoeg: (p.fp - xfp) / g,
      tdoe: ((p.rtd || 0) + (p.rutd || 0)) - ((p.xtr || 0) + (p.xtu || 0)),
      epadb: p.db ? p.epa / p.db : null, cpoe: p.cpoe, sackp: p.db ? 100 * p.sk / p.db : null,
      ruxg: (p.xu || 0) / g, carg: (p.car || 0) / g,
    };
    memo.set(p, m); return m;
  }
  // a full season is 17 games; a season in progress scales every minimum by the weeks played
  function frac(meta) { return Math.min(1, (meta.through || 18) / 17); }
  function qualifies(p, meta) {
    const f = frac(meta), g = posGroup(p.pos);
    if (g === "WR" || g === "TE") return p.rts >= 200 * f || p.tgt >= 40 * f;
    if (g === "RB") return (p.car || 0) + (p.tgt || 0) >= 90 * f;
    if (g === "QB") return (p.db || 0) >= 200 * f;
    return false;
  }
  const METRIC = {
    g: { h: "G", d: 0, hib: 1 }, tgt: { h: "Tgt", d: 0, hib: 1 }, rec: { h: "Rec", d: 0, hib: 1 }, ryd: { h: "Yds", d: 0, hib: 1 }, rtd: { h: "TD", d: 0, hib: 1 },
    car: { h: "Car", d: 0, hib: 1 }, ruyd: { h: "Yds", d: 0, hib: 1 }, rutd: { h: "TD", d: 0, hib: 1 },
    att: { h: "Att", d: 0, hib: 1 }, cmpp: { h: "Cmp%", d: 1, p: 1, hib: 1 }, pyd: { h: "Yds", d: 0, hib: 1 }, ptd: { h: "TD", d: 0, hib: 1 }, int: { h: "INT", d: 0, hib: 0 },
    rte: { h: "Route%", d: 0, p: 1, hib: 1, t: "Routes run on his team's dropbacks in his games" },
    tprr: { h: "TPRR", d: 1, p: 1, hib: 1, t: "Targets per route run" },
    tgtsh: { h: "Tgt%", d: 1, p: 1, hib: 1, t: "Share of his team's targets in his games" },
    aysh: { h: "AY%", d: 1, p: 1, hib: 1, t: "Share of his team's air yards in his games" },
    adot: { h: "aDOT", d: 1, hib: 1, t: "Average depth of target" },
    wopr: { h: "WOPR", d: 2, hib: 1, t: "1.5 × target share + 0.7 × air-yard share" },
    rzt: { h: "RZ Tgt", d: 0, hib: 1, t: "Targets inside the 20" },
    glc: { h: "GL Car", d: 0, hib: 1, t: "Carries inside the 5" }, rzc: { h: "RZ Car", d: 0, hib: 1 },
    yprr: { h: "YPRR", d: 2, hib: 1, t: "Receiving yards per route run" }, ypr: { h: "Y/R", d: 1, hib: 1 },
    croe: { h: "CROE", d: 1, s: 1, hib: 1, t: "Catch rate over expected (completion probability of each target)" },
    yacoe: { h: "YACOE", d: 1, s: 1, hib: 1, t: "Yards after catch over expected, per catch" },
    carsh: { h: "Car%", d: 1, p: 1, hib: 1, t: "Share of his team's carries in his games" },
    snp: { h: "Snap%", d: 0, p: 1, hib: 1, t: "Offensive snap share in his games" },
    ypc: { h: "YPC", d: 1, hib: 1 }, ryoe: { h: "RYOE/att", d: 2, s: 1, hib: 1, t: "Next Gen Stats rush yards over expected, per carry" },
    oppg: { h: "Opp/G", d: 1, hib: 1, t: "Carries + targets per game" },
    fppo: { h: "FP/Opp", d: 2, hib: 1, t: "PPR points per carry + target" }, fppt: { h: "FP/Tch", d: 2, hib: 1, t: "PPR points per carry + catch" },
    fpg: { h: "FP/G", d: 1, hib: 1, t: "PPR points per game" },
    xfpg: { h: "xFP/G", d: 1, hib: 1, t: "Expected PPR points per game: each target and carry priced by depth, field position, down and distance" },
    fpoeg: { h: "FPOE/G", d: 1, s: 1, hib: 1, t: "PPR points over expected, per game" },
    tdoe: { h: "TDOE", d: 1, s: 1, hib: 1, t: "Touchdowns over expected" },
    epadb: { h: "EPA/db", d: 2, s: 1, hib: 1, t: "Expected points added per dropback" }, cpoe: { h: "CPOE", d: 1, s: 1, hib: 1, t: "Completion % over expected" },
    sackp: { h: "Sack%", d: 1, p: 1, hib: 0 }, ruxg: { h: "Rush xFP/G", d: 1, hib: 1 }, carg: { h: "Car/G", d: 1, hib: 1 },
  };
  const fmtM = (k, v) => { const d = METRIC[k] || { d: 1 }; return d.s ? sgn(v, d.d) : d.p ? pc(v, d.d) : num(v, d.d); };
  const COLS = {
    WR: [["Basic", ["g", "tgt", "rec", "ryd", "rtd"]], ["Usage", ["rte", "tprr", "tgtsh", "aysh", "adot", "wopr", "rzt"]], ["Efficiency", ["yprr", "ypr", "croe", "yacoe"]], ["Fantasy", ["xfpg", "fpg", "fpoeg", "tdoe"]]],
    RB: [["Basic", ["g", "car", "ruyd", "rutd", "tgt", "rec", "ryd"]], ["Usage", ["snp", "carsh", "tgtsh", "oppg", "glc", "rzc"]], ["Efficiency", ["ypc", "ryoe", "yprr", "fppo"]], ["Fantasy", ["xfpg", "fpg", "fpoeg", "tdoe"]]],
    QB: [["Passing", ["g", "att", "cmpp", "pyd", "ptd", "int"]], ["Efficiency", ["epadb", "cpoe", "sackp"]], ["Rushing", ["car", "ruyd", "rutd", "ruxg"]], ["Fantasy", ["xfpg", "fpg", "fpoeg"]]],
  };
  COLS.TE = COLS.WR;

  // pools: the season's qualifiers at his position, with every metric sorted for percentiles
  const pools = new Map();
  function pool(y, pos) {
    const key = y + ":" + pos; if (pools.has(key)) return pools.get(key);
    const D = window.FB[y], ref = D.players.filter((p) => posGroup(p.pos) === pos && qualifies(p, D.meta));
    const sorted = {}; for (const k in METRIC) sorted[k] = ref.map((p) => M(p)[k]).filter((v) => v != null && isFinite(v)).sort((a, b) => a - b);
    const sum = (f) => ref.reduce((s, p) => s + (f(p) || 0), 0);
    const L = { g: sum((p) => p.g), rts: sum((p) => p.rts), tgt: sum((p) => p.tgt), xr: sum((p) => p.xr), car: sum((p) => p.car), xu: sum((p) => p.xu),
                fp: sum((p) => p.fp), pfp: sum((p) => posGroup(p.pos) === "QB" ? passFP(p) : 0), n: ref.length };
    const r = { ref, sorted, L }; pools.set(key, r); return r;
  }
  function pctOf(y, pos, k, v) {
    const s = pool(y, pos).sorted[k]; if (v == null || !isFinite(v) || !s || s.length < 8) return null;
    let lo = 0, eq = 0; for (const x of s) { if (x < v) lo++; else if (x === v) eq++; }
    const p = 100 * (lo + eq / 2) / s.length; return (METRIC[k] && METRIC[k].hib === 0) ? 100 - p : p;
  }

  // ---------- B-Ref table helper ----------
  function table(groups, opts = {}) {
    const t = el("table", "br"), th = el("thead"), tb = el("tbody");
    if (groups.some((g) => g.name)) { const o = el("tr", "over"); for (const g of groups) { const c = el("th", g.end ? "ge" : "", g.name || ""); c.colSpan = g.cols.length; if (g.cls) c.className += " " + g.cls; o.append(c); } th.append(o); }
    const h = el("tr");
    for (const g of groups) g.cols.forEach((c, i) => { const cell = el("th", [c.cls || "", i === g.cols.length - 1 && g.end ? "ge" : ""].join(" ").trim(), c.h); if (c.t) cell.title = c.t; if (c.onSort) { cell.classList.add("sort"); cell.addEventListener("click", c.onSort); } if (c.lit) cell.classList.add("lit"); h.append(cell); });
    th.append(h); t.append(th, tb);
    const ends = []; let i = 0; for (const g of groups) { i += g.cols.length; if (g.end) ends.push(i - 1); }
    t.addRow = (cells, cls) => { const tr = el("tr", cls || ""); cells.forEach((c, j) => { const td = c instanceof Node ? c : el("td", null, c == null ? "" : String(c)); if (ends.includes(j)) td.classList.add("ge"); tr.append(td); }); tb.append(tr); return tr; };
    const box = el("div", "tbox" + (opts.tall ? " tall" : "")); box.append(t); t.box = box; return t;
  }
  const td = (txt, cls) => el("td", cls || null, txt);
  const link = (txt, href) => { const a = el("a", "lnk", txt); a.href = href; return a; };
  const cellLink = (txt, href, cls) => { const c = td(null, cls || "l"); c.append(link(txt, href)); return c; };

  // ---------- header and search ----------
  function header() {
    const top = el("header", "top"), inn = el("div", "in"), nav = el("nav", "nav");
    nav.setAttribute("aria-label", "Pages");
    for (const [h, lab] of [["#leaders", "Leaders"], ["#backfields", "Backfields"], ["#coaches", "Coaches"]]) { const a = el("a", null, lab); a.href = h; a.dataset.page = h.slice(1); nav.append(a); }
    const base = el("a", "alt", "Baseball"); base.href = "../"; nav.append(base);
    const sr = el("div", "srch"), inp = el("input"); inp.type = "search"; inp.placeholder = "Search players"; inp.setAttribute("aria-label", "Search players");
    const hits = el("div", "hits"); hits.hidden = true; sr.append(inp, hits);
    const ALL = Object.entries(IDX).map(([id, e]) => ({ id, e, k: e.n.toLowerCase(), last: Math.max(...e.s) }));
    let cur = -1;
    const draw = () => {
      const q = inp.value.trim().toLowerCase(); hits.textContent = ""; cur = -1;
      if (q.length < 2) { hits.hidden = true; return; }
      const r = ALL.filter((x) => x.k.includes(q)).sort((a, b) => (b.k.startsWith(q) - a.k.startsWith(q)) || (b.last - a.last)).slice(0, 12);
      for (const x of r) { const b = el("button"); b.type = "button"; b.append(el("span", null, x.e.n), el("small", null, `${x.e.pos} · ${x.e.tm || ""} · ${Math.min(...x.e.s)}–${String(x.last).slice(2)}`)); b.addEventListener("click", () => { inp.value = ""; hits.hidden = true; location.hash = "#player/" + x.id; }); hits.append(b); }
      hits.hidden = !r.length;
    };
    inp.addEventListener("input", draw);
    inp.addEventListener("keydown", (e) => { const bs = [...hits.querySelectorAll("button")]; if (!bs.length) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); cur = (cur + (e.key === "ArrowDown" ? 1 : -1) + bs.length) % bs.length; bs.forEach((b, i) => b.classList.toggle("cur", i === cur)); }
      if (e.key === "Enter") (bs[cur] || bs[0]).click(); if (e.key === "Escape") { hits.hidden = true; } });
    document.addEventListener("click", (e) => { if (!sr.contains(e.target)) hits.hidden = true; });
    inn.append(nav, sr); top.append(inn); return top;
  }

  // ---------- Leaders ----------
  async function leaders(main) {
    const y = SEASONS.includes(+S.season) ? +S.season : CUR, pos = ["WR", "TE", "RB", "QB"].includes(S.pos) ? S.pos : "WR";
    const D = await ensure(y), meta = D.meta;
    const defSort = pos === "QB" ? "fpg" : "xfpg";
    if (!S.sort || !COLS[pos].some((g) => g[1].includes(S.sort))) { S.sort = defSort; S.dir = -1; }
    main.textContent = "";
    const tools = el("div", "tools"), seg = el("div", "seg");
    for (const p of ["WR", "TE", "RB", "QB"]) { const b = el("button", null, p); b.type = "button"; b.setAttribute("aria-pressed", p === pos); b.addEventListener("click", () => { S.pos = p; S.sort = null; save(); route(); }); seg.append(b); }
    const ss = el("select", "sel"); ss.setAttribute("aria-label", "Season");
    for (const s of [...SEASONS].reverse()) { const o = el("option", null, String(s)); o.value = s; if (s === y) o.selected = true; ss.append(o); }
    ss.addEventListener("change", () => { S.season = +ss.value; save(); route(); });
    const all = el("button", "tbtn", "Qualified only"); all.type = "button"; all.setAttribute("aria-pressed", S.qualOnly !== false);
    all.addEventListener("click", () => { S.qualOnly = S.qualOnly === false; save(); route(); });
    const rows = D.players.filter((p) => posGroup(p.pos) === pos && (S.qualOnly === false ? (p.tgt || p.car || p.db) : qualifies(p, meta)));
    const k = S.sort, dir = S.dir;
    rows.sort((a, b) => { const va = M(a)[k], vb = M(b)[k]; if (va == null) return 1; if (vb == null) return -1; return dir * (va - vb); });
    const f = frac(meta), minTxt = pos === "QB" ? `${Math.round(200 * f)}+ dropbacks` : pos === "RB" ? `${Math.round(90 * f)}+ carries + targets` : `${Math.round(200 * f)}+ routes or ${Math.round(40 * f)}+ targets`;
    tools.append(seg, ss, all, el("span", "count", `${rows.length} ${pos}s · ${y}${meta.through < 18 ? " · through week " + meta.through : ""} · PPR${S.qualOnly === false ? "" : " · " + minTxt}`));
    main.append(el("h1", "ttl", `${pos === "QB" ? "Quarterback" : pos === "RB" ? "Running back" : pos === "TE" ? "Tight end" : "Receiver"} Leaderboard`), tools);
    const sortBy = (key) => () => { if (S.sort === key) S.dir = -S.dir; else { S.sort = key; S.dir = METRIC[key].hib === 0 ? 1 : -1; } save(); route(); };
    const groups = [{ cols: [{ h: "Rk", cls: "fz" }, { h: "Player", cls: "l fz2" }, { h: "Tm" }], end: 1 }];
    for (const [name, keys] of COLS[pos]) groups.push({ name, end: 1, cols: keys.map((kk) => ({ h: METRIC[kk].h, t: METRIC[kk].t, onSort: sortBy(kk), lit: kk === k })) });
    const t = table(groups, { tall: true });
    rows.forEach((p, i) => {
      const m = M(p), cells = [td(String(i + 1), "fz"), cellLink(p.n, "#player/" + p.id, "l fz2"), td(p.tms && p.tms.length > 1 ? p.tms.join("/") : p.tm)];
      for (const [, keys] of COLS[pos]) for (const kk of keys) { const c = td(fmtM(kk, m[kk])); if (kk === k) paint(c, pctOf(y, pos, kk, m[kk])); cells.push(c); }
      t.addRow(cells);
    });
    main.append(t.box);
    const pl = pool(y, pos), avg = (kk) => { const v = pl.ref.map((p) => M(p)[kk]).filter((x) => x != null && isFinite(x)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    const ac = [td(""), td(`Qualified avg (${pl.ref.length})`, "l fz2"), td("")];
    for (const [, keys] of COLS[pos]) for (const kk of keys) ac.push(td(fmtM(kk, avg(kk))));
    t.addRow(ac, "tot first");
    requestAnimationFrame(() => { const first = t.querySelector("tbody td.fz"); if (first) t.style.setProperty("--fzw", first.offsetWidth + "px"); });
    main.append(el("p", "note", "Tap a column name to sort, tap a name for his page. xFP prices each target and carry by what a play like it scores on average in PPR, fitted on the other seasons. " + (meta.estRoutes ? "Routes this season are estimated from snap share × team dropbacks until nflverse publishes participation." : "Routes are dropbacks he was on the field for.")));
  }

  // ---------- Player page ----------
  const BARS = {
    WR: [[["Opportunity", ["rte", "tgtsh", "tprr", "aysh", "rzt"]], ["Fantasy", ["xfpg", "fpg", "fpoeg", "tdoe"]]], [["Efficiency", ["yprr", "croe", "yacoe", "ypr"]], ["Profile", ["adot", "wopr", "snp"]]]],
    RB: [[["Opportunity", ["snp", "carsh", "tgtsh", "oppg", "glc"]], ["Fantasy", ["xfpg", "fpg", "fpoeg", "tdoe"]]], [["Efficiency", ["ypc", "ryoe", "fppo", "yprr"]], ["Receiving", ["tprr", "croe", "yacoe"]]]],
    QB: [[["Passing", ["epadb", "cpoe", "cmpp", "sackp"]], ["Fantasy", ["xfpg", "fpg", "fpoeg"]]], [["Rushing", ["carg", "ruxg", "ypc", "rutd"]], ["Volume", ["att", "pyd", "ptd"]]]],
  };
  BARS.TE = BARS.WR;
  const LABEL = { rte: "Route %", tgtsh: "Target share", tprr: "Targets / route", aysh: "Air-yard share", rzt: "Red-zone targets", xfpg: "xFP / game", fpg: "FP / game", fpoeg: "Points over exp. / G",
                  tdoe: "TD over expected", yprr: "Yards / route", croe: "Catch rate over exp.", yacoe: "YAC over exp.", ypr: "Yards / catch", adot: "aDOT", wopr: "WOPR", snp: "Snap %",
                  carsh: "Carry share", oppg: "Opportunities / G", glc: "Goal-line carries", ypc: "Yards / carry", ryoe: "Rush yds over exp.", fppo: "FP / opportunity",
                  epadb: "EPA / dropback", cpoe: "CPOE", cmpp: "Completion %", sackp: "Sack %", carg: "Carries / game", ruxg: "Rush xFP / game", rutd: "Rush TD", att: "Attempts", pyd: "Pass yards", ptd: "Pass TD" };

  async function player(main, id) {
    const e = IDX[id]; if (!e) { main.textContent = ""; main.append(el("p", "load", "No player with that id.")); return; }
    const seasons = [...e.s].sort((a, b) => a - b);
    let y = S.pseason && S.pseason[id] && seasons.includes(S.pseason[id]) ? S.pseason[id] : seasons[seasons.length - 1];
    const [D] = await Promise.all([ensure(y), loadScript("data/career.js").catch(() => null)]), p = D.players.find((q) => q.id === id);
    if (!p) { main.textContent = ""; main.append(el("p", "load", "No line for that season.")); return; }
    const pos = posGroup(p.pos), m = M(p), meta = D.meta;
    main.textContent = "";
    // band
    const band = el("section", "band"), r1 = el("div", "row1"), mug = el("div", "mug"); if (e.img) mug.style.backgroundImage = `url("${e.img}")`;
    const who = el("div", "who"); who.append(el("h1", null, e.n));
    const bio = el("div", "bio"), age = p.age != null ? Math.floor(p.age) : null;
    for (const s of [p.pos, p.tms && p.tms.length > 1 ? p.tms.join(" / ") : p.tm, age != null ? "Age " + age : null, e.ht ? `${htFmt(e.ht)} · ${e.wt}` : null, e.col, e.dr ? `${e.dr[0]} R${e.dr[1]} #${e.dr[2]}` : null]) if (s) bio.append(el("span", null, s));
    who.append(bio);
    const ctl = el("div", "ctl"), sel = el("select"); sel.setAttribute("aria-label", "Season");
    for (const s of [...seasons].reverse()) { const o = el("option", null, String(s)); o.value = s; if (s === y) o.selected = true; sel.append(o); }
    sel.addEventListener("change", () => { S.pseason = Object.assign({}, S.pseason, { [id]: +sel.value }); save(); route(); });
    ctl.append(sel); r1.append(mug, who, ctl);
    const facts = el("div", "facts");
    const fact = (lab, val, pcv) => { const d = el("div"), b = el("b"); if (pcv != null) { const s = el("span", "chip", val); paint(s, pcv); s.classList.remove("heat"); b.append(s); } else b.textContent = val; d.append(b, el("small", null, lab)); facts.append(d); };
    fact("G", String(p.g));
    if (pos === "QB") { fact("Pass Yds", String(p.pyd)); fact("Pass TD", String(p.ptd)); fact("INT", String(p.int_)); fact("Rush Yds", String(p.ruyd)); }
    else if (pos === "RB") { fact("Car", String(p.car)); fact("Rush Yds", String(p.ruyd)); fact("TD", String(p.rutd + p.rtd)); fact("Rec", String(p.rec)); }
    else { fact("Tgt", String(p.tgt)); fact("Rec", String(p.rec)); fact("Yds", String(p.ryd)); fact("TD", String(p.rtd)); }
    fact("FP/G", num(m.fpg), pctOf(y, pos, "fpg", m.fpg)); fact("xFP/G", num(m.xfpg), pctOf(y, pos, "xfpg", m.xfpg)); fact("FPOE/G", sgn(m.fpoeg), pctOf(y, pos, "fpoeg", m.fpoeg));
    band.append(r1, facts); main.append(band);
    // percentile bars
    const q = qualifies(p, meta);
    main.append(el("h2", "pcthd", `${y} ${pos} Percentiles`));
    if (!q) main.append(el("p", "note", `Under the ${pos} minimum this season, so he's placed among the qualified ${pos}s rather than counted in them.`));
    const cols = el("div", "pcols");
    BARS[pos].forEach((col, ci) => {
      const c = el("div");
      const sc = el("div", "scale"), mid = el("div"); mid.append(el("span", null, "Poor"), el("span", null, "Average"), el("span", null, "Great")); sc.append(el("span"), mid, el("span")); if (ci === 0) c.append(sc); else { sc.classList.add("desk"); c.append(sc); }
      for (const [name, keys] of col) {
        const s = el("div", "psec"); s.append(el("h4", null, name));
        for (const k of keys) {
          const v = m[k], pv = pctOf(y, pos, k, v), r = el("div", "prow" + (pv == null ? " none" : "")), trk = el("div", "trk");
          for (const x of [10, 50, 90]) { const tk = el("div", "tick"); tk.style.left = x + "%"; trk.append(tk); }
          if (pv != null) { const P = Math.round(pv), h = heat(P), fill = el("div", "fill"), bub = el("div", "bub", String(P)); fill.style.width = P + "%"; fill.style.background = h.bg; bub.style.left = P + "%"; bub.style.background = h.bg; trk.append(fill, bub); r.title = `${LABEL[k] || k}: ${fmtM(k, v)}, ${ord(P)} percentile among ${pool(y, pos).ref.length} qualified ${pos}s`; }
          r.append(el("div", "lb", LABEL[k] || METRIC[k].h), trk, el("div", "val", fmtM(k, v))); s.append(r);
        }
        c.append(s);
      }
      cols.append(c);
    });
    main.append(cols);
    // tabs
    const tabs = el("div", "tabs"), body = el("div");
    const TABS = [["build", "xFP build-up"], ["log", "Game log"]]; if (pos === "RB" && p.tm) TABS.push(["bf", "Backfield"]);
    const pick = TABS.some((t) => t[0] === S.ptab) ? S.ptab : "build";
    for (const [k, lab] of TABS) { const b = el("button", null, lab); b.type = "button"; b.setAttribute("aria-pressed", k === pick); b.addEventListener("click", () => { if (k === "bf") { location.hash = `#team/${p.tm}/${y}`; return; } S.ptab = k; save(); route(); }); tabs.append(b); }
    main.append(tabs, body);
    if (pick === "log") gameLog(body, p, meta); else buildUp(body, p, y, pos);
    seasonTable(main, id, e, y, pos);
  }

  function buildUp(host, p, y, pos) {
    const L = pool(y, pos).L, g = Math.max(p.g, 1), m = M(p);
    const rows = []; let run;
    const step = (lab, his, lg, next, t) => { const d = next - run; rows.push({ lab, his, lg, d, run: next, t }); run = next; };
    if (pos === "WR" || pos === "TE") {
      const Lr = L.rts / L.g, Lt = L.tgt / L.rts, Lx = L.xr / L.tgt, Lu = L.xu / L.g, r = p.rts / g, t = p.rts ? p.tgt / p.rts : 0, x = p.tgt ? p.xr / p.tgt : 0, u = p.xu / g;
      run = Lr * Lt * Lx + Lu; rows.push({ lab: `League ${pos}`, his: "", lg: "", d: null, run });
      step("Routes / game", num(r), num(Lr), r * Lt * Lx + Lu, "How often he's out running routes");
      step("Targets / route", pc(100 * t), pc(100 * Lt), r * t * Lx + Lu, "How often he gets the ball thrown his way when he's out there");
      step("xFP / target", num(x, 2), num(Lx, 2), r * t * x + Lu, "What his targets are worth: deep, end-zone and red-zone looks price higher");
      step("Rushing xFP / game", num(u, 2), num(Lu, 2), r * t * x + u, "Carries, priced the same way");
    } else if (pos === "RB") {
      const Lc = L.car / L.g, Lxc = L.xu / L.car, Lt = L.tgt / L.g, Lx = L.xr / L.tgt, c = p.car / g, xc = p.car ? p.xu / p.car : 0, t = p.tgt / g, x = p.tgt ? p.xr / p.tgt : 0;
      run = Lc * Lxc + Lt * Lx; rows.push({ lab: "League RB", his: "", lg: "", d: null, run });
      step("Carries / game", num(c), num(Lc), c * Lxc + Lt * Lx, "His share of the work on the ground");
      step("xFP / carry", num(xc, 2), num(Lxc, 2), c * xc + Lt * Lx, "Where his carries come: goal-line work prices highest");
      step("Targets / game", num(t), num(Lt), c * xc + t * Lx, "His role in the passing game");
      step("xFP / target", num(x, 2), num(Lx, 2), c * xc + t * x, "What his targets are worth");
    } else {
      const Lp = L.pfp / L.g, Lc = L.car / L.g, Lxc = L.xu / L.car, pf = passFP(p) / g, c = p.car / g, xc = p.car ? p.xu / p.car : 0;
      run = Lp + Lc * Lxc; rows.push({ lab: "League QB", his: "", lg: "", d: null, run });
      step("Passing points / game", num(pf), num(Lp), pf + Lc * Lxc, "Passing yards, touchdowns and interceptions as scored");
      step("Carries / game", num(c), num(Lc), pf + c * Lxc, "Designed runs and scrambles");
      step("xFP / carry", num(xc, 2), num(Lxc, 2), pf + c * xc, "Where his carries come");
    }
    const xfpg = run; rows[rows.length - 1].mark = true;
    const tdo = ((p.rtd || 0) + (p.rutd || 0)) - ((p.xtr || 0) + (p.xtu || 0));
    const tdPts = 6 * tdo / g, playPts = ((p.frt || 0) + (p.fru || 0) - (p.xr || 0) - (p.xu || 0)) / g - tdPts;
    step("Touchdowns over expected", sgn(tdo), "0.0", run + tdPts, `${(p.rtd || 0) + (p.rutd || 0)} touchdowns against ${num((p.xtr || 0) + (p.xtu || 0))} expected: the least repeatable part`);
    step("Catches and yards over expected", "", "", run + playPts, "Catching more than expected and gaining more after the catch or per carry: partly skill");
    step("Other", "", "", m.fpg, "Fumbles lost, two-point conversions, and for non-QBs any passing");
    const split = el("div", "split"), left = el("div");
    left.append(el("h3", "secttl", "Fantasy points build-up"));
    const t = table([{ cols: [{ h: "Step", cls: "l" }, { h: "His" }, { h: "Lg" }, { h: "± FP/G" }, { h: "FP/G" }] }]);
    for (const r of rows) {
      const lab = td(r.lab, "l"); if (r.t) lab.title = r.t;
      const dc = td(""); if (r.d != null) { const s = el("span", "pill", sgn(r.d)); paint(s, 50 + 14 * r.d); s.classList.remove("heat"); dc.append(s); }
      const rc = td(num(r.run), r.mark ? "kexp" : ""); if (r.mark) rc.title = "Expected FP / game: what his usage says he should score";
      t.addRow([lab, td(r.his), td(r.lg), dc, rc]);
    }
    t.addRow([td("FP / game", "l"), td(""), td(""), td(sgn(m.fpg - rows[0].run)), td(num(m.fpg))], "tot first");
    left.append(t.box, el("p", "note", `Each step swaps the qualified ${pos}s' average for his. The yellow cell is his expected points per game (${num(xfpg)}): his usage priced play by play. Below it, touchdown luck and the rest of the gap to what he scored.`));
    // TD detail
    const right = el("div"); right.append(el("h3", "secttl", "Where the gap comes from"));
    const t2 = table([{ cols: [{ h: "Piece", cls: "l" }, { h: "Exp" }, { h: "Act" }, { h: "± FP/G" }, { h: "Share" }] }]);
    const parts = [];
    if (p.tgt) parts.push(["Receiving TD", num(p.xtr), String(p.rtd), 6 * ((p.rtd || 0) - (p.xtr || 0)) / g]);
    if (p.car) parts.push(["Rushing TD", num(p.xtu), String(p.rutd), 6 * ((p.rutd || 0) - (p.xtu || 0)) / g]);
    if (p.tgt) parts.push(["Catches + rec. yards", num((p.xr - 6 * (p.xtr || 0)) / g, 1) + "/G", num((p.frt - 6 * (p.rtd || 0)) / g, 1) + "/G", ((p.frt - 6 * (p.rtd || 0)) - (p.xr - 6 * (p.xtr || 0))) / g]);
    if (p.car) parts.push(["Rushing yards", num((p.xu - 6 * (p.xtu || 0)) / g, 1) + "/G", num((p.fru - 6 * (p.rutd || 0)) / g, 1) + "/G", ((p.fru - 6 * (p.rutd || 0)) - (p.xu - 6 * (p.xtu || 0))) / g]);
    const other = m.fpg - (p.frt + p.fru) / g - (pos === "QB" ? passFP(p) / g : 0); if (Math.abs(other) >= 0.05) parts.push(["Fumbles, 2-pt, other", "", "", other]);
    const tot = parts.reduce((s, x) => s + Math.abs(x[3]), 0);
    for (const [lab, ex, ac, d] of parts.sort((a, b) => Math.abs(b[3]) - Math.abs(a[3]))) { const dc = td(""), s = el("span", "pill", sgn(d)); paint(s, 50 + 14 * d); s.classList.remove("heat"); dc.append(s); t2.addRow([td(lab, "l"), td(ex), td(ac), dc, td(tot >= 0.1 ? Math.round(100 * Math.abs(d) / tot) + "%" : "–")]); }
    t2.addRow([td("FP / game", "l"), td(num(m.xfpg)), td(num(m.fpg)), td(sgn(m.fpoeg)), td(tot >= 0.1 ? "100%" : "")], "tot first");
    right.append(t2.box, el("p", "note", "Each piece's part of the gap between his expected and actual points; the shares add to 100%. Touchdown luck is the part least likely to carry into next season."));
    split.append(left, right); host.append(split);
  }

  function gameLog(host, p, meta) {
    host.append(el("h3", "secttl", "Game log"));
    const F = meta.wfields, ix = (k) => F.indexOf(k);
    const t = table([{ cols: [{ h: "Wk" }, { h: "Opp" }, { h: "Snap%" }, { h: "Rts" }], end: 1 }, { name: "Receiving", end: 1, cols: [{ h: "Tgt" }, { h: "Rec" }, { h: "Yds" }, { h: "TD" }] },
                     { name: "Rushing", end: 1, cols: [{ h: "Car" }, { h: "Yds" }, { h: "TD" }] }, { name: "Fantasy", end: 1, cols: [{ h: "xFP" }, { h: "FP" }, { h: "Diff" }] }]);
    const xs = p.w.map((r) => r[ix("xfp")]), lo = Math.min(...xs), hi = Math.max(...xs);
    for (const r of p.w) {
      const x = r[ix("xfp")], f = r[ix("fp")], xc = td(num(x)); if (hi > lo) paint(xc, 100 * (x - lo) / (hi - lo));
      const dc = td(sgn(f - x)); dc.style.color = f - x > 0.5 ? "var(--stripe)" : f - x < -0.5 ? "#3661ad" : "";
      t.addRow([td(String(r[ix("wk")])), td((r[ix("tm")] && p.tms && p.tms.length > 1 ? r[ix("tm")] + " v " : "") + (r[ix("opp")] || "")), td(r[ix("snp")] == null ? "–" : r[ix("snp")] + "%"), td(num(r[ix("rts")], 0)),
                td(String(r[ix("tgt")])), td(String(r[ix("rec")])), td(String(r[ix("ryd")])), td(String(r[ix("rtd")])), td(String(r[ix("car")])), td(String(r[ix("ruyd")])), td(String(r[ix("rutd")])), xc, td(num(f)), dc]);
    }
    const sum = (k) => p.w.reduce((s, r) => s + (r[ix(k)] || 0), 0);
    t.addRow([td("Season", "l"), td(""), td(p.snpct == null ? "" : Math.round(p.snpct) + "%"), td(String(Math.round(sum("rts")))), td(String(sum("tgt"))), td(String(sum("rec"))), td(String(sum("ryd"))), td(String(sum("rtd"))),
              td(String(sum("car"))), td(String(sum("ruyd"))), td(String(sum("rutd"))), td(num(sum("xfp"))), td(num(sum("fp"))), td(sgn(sum("fp") - sum("xfp")))], "tot first");
    host.append(t.box, el("p", "note", "xFP is coloured within his own season, darkest red his biggest-opportunity game. Passing stats aren't in the weekly rows yet; a QB's FP includes them."));
  }

  function staffOf(y, tm) { const r = (TEAMS[y] || []).find((x) => x.tm === tm); return r || {}; }
  function seasonTable(host, id, e, cy, pos) {
    const C = (window.FB_CAREER || {})[id] || {}, ys = Object.keys(C).map(Number).sort((a, b) => a - b); if (!ys.length) return;
    host.append(el("h3", "secttl", "Season by season"));
    const recv = pos !== "QB", groups = [{ cols: [{ h: "Season", cls: "fz" }, { h: "Age" }, { h: "Tm" }, { h: "Head coach", cls: "l" }, { h: "Off. coordinator", cls: "l" }], end: 1 }, { cols: [{ h: "G" }], end: 1 }];
    if (pos === "QB") groups.push({ name: "Passing", end: 1, cols: [{ h: "Cmp" }, { h: "Att" }, { h: "Yds" }, { h: "TD" }, { h: "INT" }, { h: "EPA/db" }] });
    groups.push({ name: "Receiving", end: 1, cols: [{ h: "Tgt" }, { h: "Rec" }, { h: "Yds" }, { h: "TD" }, { h: "Tgt%" }] });
    groups.push({ name: "Rushing", end: 1, cols: [{ h: "Car" }, { h: "Yds" }, { h: "TD" }, { h: "Car%" }] });
    groups.push({ name: "Fantasy", end: 1, cols: [{ h: "xFP/G" }, { h: "FP/G" }, { h: "FPOE/G" }, { h: "Rank" }] });
    const t = table(groups);
    let G = 0, fpS = 0, xS = 0; const tot = { tgt: 0, rec: 0, ryd: 0, rtd: 0, car: 0, ruyd: 0, rutd: 0, cmp: 0, att: 0, pyd: 0, ptd: 0, int_: 0 };
    for (const y of ys) {
      const r = C[y], g = Math.max(r.g || 0, 1), xfp = (r.xr || 0) + (r.xu || 0) + (pos === "QB" ? passFP(r) : 0), st = staffOf(y, r.tm);
      G += r.g || 0; fpS += r.fp || 0; xS += xfp; for (const k in tot) tot[k] += r[k] || 0;
      const coachCell = (n) => { const c = td(null, "l"); if (n) for (const [i, nm] of n.split(" / ").entries()) { if (i) c.append(" / "); c.append(link(nm, "#coach/" + encodeURIComponent(nm))); } else c.textContent = "–"; return c; };
      const cells = [td(String(y), "fz"), td(r.age != null ? String(Math.floor(r.age)) : ""), td(r.tms && r.tms.length > 1 ? r.tms.join("/") : r.tm), coachCell(st.hc), coachCell(st.oc || (st.pc ? st.pc + " (HC)" : null)), td(String(r.g))];
      if (pos === "QB") cells.push(td(String(r.cmp || 0)), td(String(r.att || 0)), td(String(r.pyd || 0)), td(String(r.ptd || 0)), td(String(r.int_ || 0)), td(r.db ? sgn(r.epa / r.db, 2) : "–"));
      cells.push(td(String(r.tgt || 0)), td(String(r.rec || 0)), td(String(r.ryd || 0)), td(String(r.rtd || 0)), td(r.tmt ? pc(100 * r.tgt / r.tmt) : "–"));
      cells.push(td(String(r.car || 0)), td(String(r.ruyd || 0)), td(String(r.rutd || 0)), td(r.tmc ? pc(100 * r.car / r.tmc) : "–"));
      const xc = td(num(xfp / g)); paint(xc, Math.min(99, Math.max(1, 100 - 100 * ((r.xrk || 60) - 1) / 60)));
      cells.push(xc, td(num((r.fp || 0) / g)), td(sgn(((r.fp || 0) - xfp) / g)), td(r.rk ? pos + r.rk : "–"));
      const tr = t.addRow(cells, y === cy ? "cur" : ""); tr.querySelector("td").title = y === cy ? "The season shown above" : "";
    }
    const g = Math.max(G, 1), cells = [td(`${ys.length} Yrs`, "fz"), td(""), td(""), td(""), td(""), td(String(G))];
    if (pos === "QB") cells.push(td(String(tot.cmp)), td(String(tot.att)), td(String(tot.pyd)), td(String(tot.ptd)), td(String(tot.int_)), td(""));
    cells.push(td(String(tot.tgt)), td(String(tot.rec)), td(String(tot.ryd)), td(String(tot.rtd)), td(""), td(String(tot.car)), td(String(tot.ruyd)), td(String(tot.rutd)), td(""), td(num(xS / g)), td(num(fpS / g)), td(sgn((fpS - xS) / g)), td(""));
    t.addRow(cells, "tot first"); host.append(t.box);
    host.append(el("p", "note", "Coaches are the team's head coach and offensive coordinator that season (a traded player shows his main team's). xFP/G is coloured by his rank at the position that season by expected points."));
  }

  // ---------- Backfields ----------
  const share = (a, b) => (b ? 100 * a / b : null);
  async function backfields(main) {
    const y = SEASONS.includes(+S.bfSeason) ? +S.bfSeason : CUR, rows = TEAMS[y] || [];
    main.textContent = "";
    main.append(el("h1", "ttl", "Backfields"), el("p", "sub", "How each team split its running back work. Shares count only the games the lead back played, so an injury doesn't make a bell cow look like a committee."));
    const tools = el("div", "tools"), ss = el("select", "sel"); ss.setAttribute("aria-label", "Season");
    for (const s of [...SEASONS].reverse()) { const o = el("option", null, String(s)); o.value = s; if (s === y) o.selected = true; ss.append(o); }
    ss.addEventListener("change", () => { S.bfSeason = +ss.value; save(); route(); }); tools.append(ss); main.append(tools);
    const sortK = S.bfSort || "rb1car", dir = S.bfDir || -1;
    const val = (r, k) => k === "rbtgt" ? share(r.rbtgt, r.tmtgt) : k === "rb1fp" ? fpo(r.rbs[0]) : k === "rb2fp" ? (r.rbs[1] ? fpo(r.rbs[1]) : null) : k === "rb1snp" ? r.rbs[0].snp : r[k];
    const sorted = [...rows].sort((a, b) => { const va = val(a, sortK), vb = val(b, sortK); if (va == null) return 1; if (vb == null) return -1; return dir * (va - vb); });
    const sb = (k) => () => { if (S.bfSort === k) S.bfDir = -(S.bfDir || -1); else { S.bfSort = k; S.bfDir = -1; } save(); route(); };
    const t = table([{ cols: [{ h: "Tm", cls: "fz" }, { h: "Head coach", cls: "l" }, { h: "Off. coordinator", cls: "l" }], end: 1 },
                     { name: "Lead back, in his games", end: 1, cols: [{ h: "RB1", cls: "l" }, { h: "G" }, { h: "Car%", onSort: sb("rb1car"), lit: sortK === "rb1car", t: "His share of the team's RB carries in the games he played" }, { h: "Opp%", onSort: sb("rb1opp"), lit: sortK === "rb1opp", t: "Share of RB carries + targets" }, { h: "Snap%", onSort: sb("rb1snp"), lit: sortK === "rb1snp" }, { h: "GL%", onSort: sb("rb1gl"), lit: sortK === "rb1gl", t: "Share of RB carries inside the 5" }] },
                     { name: "The rest", end: 1, cols: [{ h: "RB2", cls: "l" }, { h: "Car%", onSort: sb("rb2car"), lit: sortK === "rb2car" }, { h: "Backs used", onSort: sb("eff"), lit: sortK === "eff", t: "Effective number of backs: 1 = one back took every carry, 2 = an even split" }] },
                     { name: "Passing game", end: 1, cols: [{ h: "RB Tgt%", onSort: sb("rbtgt"), lit: sortK === "rbtgt", t: "Share of all team targets that went to running backs" }] },
                     { name: "PPR pts per carry + target", end: 1, cols: [{ h: "RB1", onSort: sb("rb1fp"), lit: sortK === "rb1fp" }, { h: "RB2", onSort: sb("rb2fp"), lit: sortK === "rb2fp" }] }], { tall: true });
    const all = rows.map((r) => r.rb1car), pctIn = (arr, v, hib = 1) => { const s = arr.filter((x) => x != null).sort((a, b) => a - b); let lo = 0; for (const x of s) if (x < v) lo++; const p = 100 * lo / Math.max(s.length - 1, 1); return hib ? p : 100 - p; };
    for (const r of sorted) {
      const b1 = r.rbs[0], b2 = r.rbs[1], coach = (n) => { const c = td(null, "l"); if (n) n.split(" / ").forEach((nm, i) => { if (i) c.append(" / "); c.append(link(nm, "#coach/" + encodeURIComponent(nm))); }); else c.textContent = "–"; return c; };
      const car = td(pc(r.rb1car)); paint(car, pctIn(all, r.rb1car));
      const eff = td(num(r.eff, 2)); paint(eff, pctIn(rows.map((x) => x.eff), r.eff));
      const f1 = fpo(b1), f2 = b2 ? fpo(b2) : null, f2c = td(num(f2, 2)); if (f2 != null && f1 != null && f2 > f1 + 0.1) { f2c.style.color = "var(--stripe)"; f2c.style.fontWeight = "700"; f2c.title = "More points per opportunity than the lead back"; }
      t.addRow([cellLink(r.tm, `#team/${r.tm}/${y}`, "fz"), coach(r.hc), coach(r.oc || (r.pc ? r.pc + " (HC)" : null)), cellLink(b1.n, "#player/" + b1.id), td(String(r.rb1g)), car, td(pc(r.rb1opp)), td(b1.snp == null ? "–" : Math.round(b1.snp) + "%"), td(r.rb1gl == null ? "–" : pc(r.rb1gl, 0)),
                b2 ? cellLink(b2.n, "#player/" + b2.id) : td("–"), td(pc(r.rb2car)), eff, td(pc(share(r.rbtgt, r.tmtgt))), td(num(f1, 2)), f2c]);
    }
    main.append(t.box, el("p", "note", "Car% is coloured red for the most bell-cow backfields, blue for the most shared; Backs used the same way round. An RB2 in red outscored his lead back per opportunity, the case where more work tends to follow. Tap a team for its week-by-week split."));
  }
  const fpo = (b) => (b && b.car + b.tgt ? b.fp / (b.car + b.tgt) : null);

  // ---------- one team's backfield, week by week ----------
  const COLORS = ["#c8102e", "#3661ad", "#e0a526", "#2e8b57", "#8a5cc2"];
  async function teamPage(main, tm, y) {
    y = +y; const D = await ensure(y), rec = (TEAMS[y] || []).find((r) => r.tm === tm);
    main.textContent = "";
    const F = D.meta.wfields, ix = (k) => F.indexOf(k);
    const backs = D.players.filter((p) => posGroup(p.pos) === "RB" && p.w.some((r) => r[ix("tm")] === tm && (r[ix("car")] || r[ix("tgt")] || r[ix("snp")])));
    const tot = (p) => p.w.filter((r) => r[ix("tm")] === tm).reduce((s, r) => s + r[ix("car")] + r[ix("tgt")], 0);
    backs.sort((a, b) => tot(b) - tot(a)); const top = backs.slice(0, 5);
    main.append(el("h1", "ttl", `${tm} backfield, ${y}`));
    const sub = el("p", "sub"); if (rec) { sub.append("Head coach "); sub.append(link(rec.hc || "–", "#coach/" + encodeURIComponent(rec.hc || ""))); if (rec.oc) { sub.append(" · coordinator "); rec.oc.split(" / ").forEach((n, i) => { if (i) sub.append(" / "); sub.append(link(n, "#coach/" + encodeURIComponent(n))); }); } }
    main.append(sub);
    const tools = el("div", "tools"), ss = el("select", "sel"); for (const s of [...SEASONS].reverse()) if ((TEAMS[s] || []).some((r) => r.tm === tm)) { const o = el("option", null, String(s)); o.value = s; if (s === y) o.selected = true; ss.append(o); }
    ss.addEventListener("change", () => { location.hash = `#team/${tm}/${ss.value}`; }); tools.append(ss); main.append(tools);
    const lg = el("div", "legend"); top.forEach((p, i) => { const s = el("span"), sw = el("i"); sw.style.background = COLORS[i]; s.append(sw, p.n); lg.append(s); }); main.append(lg);
    const weeks = [...new Set(top.flatMap((p) => p.w.filter((r) => r[ix("tm")] === tm).map((r) => r[ix("wk")])))].sort((a, b) => a - b);
    const groups = [{ cols: [{ h: "Wk" }, { h: "Carry split", cls: "l" }], end: 1 }];
    for (const p of top) groups.push({ name: p.n, end: 1, cols: [{ h: "Snap%" }, { h: "Car" }, { h: "Tgt" }, { h: "FP" }] });
    const t = table(groups);
    for (const w of weeks) {
      const rowsW = top.map((p) => p.w.find((r) => r[ix("wk")] === w && r[ix("tm")] === tm)), cars = rowsW.map((r) => (r ? r[ix("car")] : 0)), sumC = cars.reduce((a, b) => a + b, 0);
      const bar = el("div", "wbar"); cars.forEach((c, i) => { if (!c) return; const s = el("span"); s.style.width = (100 * c / sumC) + "%"; s.style.background = COLORS[i]; s.title = `${top[i].n}: ${c} carries`; bar.append(s); });
      const bc = td(null, "l"); bc.append(bar);
      const cells = [td(String(w)), bc];
      rowsW.forEach((r) => { if (!r) { cells.push(td("–", "dim"), td("", "dim"), td("", "dim"), td("", "dim")); return; } cells.push(td(r[ix("snp")] == null ? "–" : r[ix("snp")] + "%"), td(String(r[ix("car")])), td(String(r[ix("tgt")])), td(num(r[ix("fp")]))); });
      t.addRow(cells);
    }
    const cells = [td("Season", "l"), td("")];
    top.forEach((p) => { const rs = p.w.filter((r) => r[ix("tm")] === tm), n = rs.length, s = (k) => rs.reduce((a, r) => a + (r[ix(k)] || 0), 0), sn = rs.filter((r) => r[ix("snp")] != null); cells.push(td(sn.length ? Math.round(sn.reduce((a, r) => a + r[ix("snp")], 0) / sn.length) + "%" : "–"), td(String(s("car"))), td(String(s("tgt"))), td(n ? num(s("fp") / n) + "/G" : "")); });
    t.addRow(cells, "tot first"); main.append(t.box);
    main.append(el("p", "note", "Each week's bar is that game's carry split. The season row averages his snap share over the games he played here and gives his points per game here."));
  }

  // ---------- Coaches ----------
  // a coach's history is every team-season he was on the offensive staff, in any role (Sean, 13 Oct 2026: "do it based on who is on
  // the offense ... include every team he coached on"): teams.js carries each team-season's offensive staff as [role, name] (`st`,
  // Wikipedia's final staff that season), plus the head coach from the games list and the coordinator / play-caller
  const ROLE_CATS = [["HC", /^(interim )?head coach/i], ["OC", /offensive coordinator/i], ["PGC", /pass(ing)? game coordinator/i], ["RGC", /run(ning)? game coordinator/i],
                     ["QB", /quarterback/i], ["RB", /running back/i], ["WR", /wide receiver/i], ["TE", /tight end/i], ["OL", /offensive line/i]];
  const roleCat = (role) => { for (const [c, re] of ROLE_CATS) if (re.test(role)) return c; return "Asst"; };
  const CAT_WORD = { HC: "head coach", OC: "coordinator", PC: "play-caller", PGC: "pass game coord.", RGC: "run game coord.", QB: "QBs", RB: "RBs", WR: "WRs", TE: "TEs", OL: "O-line", Asst: "assistant" };
  let CS_MEMO = null;
  function coachSeasons() {
    if (CS_MEMO) return CS_MEMO;
    const out = new Map();
    for (const y of SEASONS) for (const r of TEAMS[y] || []) {
      const here = new Map();
      const put = (n, role) => { n = String(n || "").trim(); if (!n) return; let e = here.get(n); if (!e) here.set(n, (e = { roles: [], cats: new Set() })); if (!e.roles.includes(role)) e.roles.push(role); e.cats.add(roleCat(role)); };
      for (const [role, n] of r.st || []) put(n, role);
      for (const n of String(r.hc || "").split(" / ")) put(n, "Head coach");
      for (const n of String(r.oc || "").split(" / ")) put(n, "Offensive coordinator");
      if (r.pc) { put(r.pc, "Head coach"); here.get(r.pc).cats.add("PC"); }
      for (const [n, e] of here) {
        if (e.cats.has("OC") && !r.pc) e.cats.add("PC");
        if (!out.has(n)) out.set(n, []);
        out.get(n).push(Object.assign({}, r, { y, roles: e.roles, cats: e.cats }));
      }
    }
    return (CS_MEMO = out);
  }
  const catLine = (rs) => { const c = {}; for (const r of rs) for (const k of r.cats) if (k !== "PC" || !r.cats.has("HC")) c[k] = (c[k] || 0) + 1; return ROLE_CATS.map((x) => x[0]).concat(["PC", "Asst"]).filter((k) => c[k]).map((k) => `${k} ${c[k]}`).join(" · "); };
  // his stints: consecutive seasons with one club, with the jobs he held there
  function stints(rs) {
    const norm = (x) => x.toLowerCase().replace(/passing game/g, "pass game").replace(/running game/g, "run game");   // the pages write a title two ways
    const add = (L, x) => { if (!L.roles.some((z) => norm(z) === norm(x))) L.roles.push(x); };
    const out = []; for (const r of rs) { let L = out[out.length - 1]; if (!(L && L.tm === r.tm && r.y === L.y1 + 1)) out.push((L = { tm: r.tm, y0: r.y, y1: r.y, roles: [] })); L.y1 = r.y; for (const x of r.roles) add(L, x); }
    return out;
  }
  const yrs = (a, b) => (a === b ? String(a) : `${a}–${String(b).slice(2)}`);
  const agg = (rs) => { const n = rs.length, avg = (f) => { const v = rs.map(f).filter((x) => x != null && isFinite(x)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    return { n, car: avg((r) => r.rb1car), opp: avg((r) => r.rb1opp), eff: avg((r) => r.eff), tgt: avg((r) => share(r.rbtgt, r.tmtgt)), snp: avg((r) => r.rbs[0].snp), gl: avg((r) => r.rb1gl),
             cow: rs.filter((r) => r.rb1car >= COW_YR).length, com: rs.filter((r) => r.rb1car < COM_YR).length }; };
  // cut at the league's own thirds (2016-25): a coach's average lead-back carry share 68%+ / under 60%, one season 72%+ / under 58%
  const COW = 68, COM = 60, COW_YR = 72, COM_YR = 58;
  function verdict(a) { return a.car == null ? ["–", 50] : a.car >= COW ? ["Bell cow", 85] : a.car >= COM ? ["Lead back + change of pace", 62] : ["Committee", 18]; }
  function leagueAvg() { const all = SEASONS.flatMap((y) => TEAMS[y] || []); return agg(all); }
  const ROLE_PICK = { hc: (r) => r.cats.has("HC"), oc: (r) => r.cats.has("OC") || r.cats.has("PC"), all: () => true };

  function coaches(main) {
    main.textContent = "";
    const pick = ROLE_PICK[S.coachRole] ? S.coachRole : "hc";
    main.append(el("h1", "ttl", "Coaches and their backfields"), el("p", "sub", "Every coach on an offensive staff since 2016, by how his teams split running back work in the seasons he was there. A coach's average counts each of those seasons once."));
    const tools = el("div", "tools"), seg = el("div", "seg");
    for (const [k, lab] of [["hc", "Head coaches"], ["oc", "Coordinators"], ["all", "Every offensive coach"]]) { const b = el("button", null, lab); b.type = "button"; b.setAttribute("aria-pressed", pick === k); b.addEventListener("click", () => { S.coachRole = k; save(); route(); }); seg.append(b); }
    const mb = el("label", "minbox"), mi = el("input"); mi.type = "number"; mi.min = 1; mi.max = 11; mi.value = S.coachMin; mi.id = "coachmin"; mb.append("Min seasons", mi);
    mi.addEventListener("change", () => { S.coachMin = Math.max(1, +mi.value || 1); save(); route(); });
    const q = el("input", "csearch"); q.type = "search"; q.placeholder = "Find a coach"; q.setAttribute("aria-label", "Find a coach");
    tools.append(seg, mb, q); main.append(tools);
    const CS = coachSeasons(), L = leagueAvg();
    // the averages are over the seasons in the role picked; Teams / Roles still say where else he's been
    let rows = [...CS.entries()].map(([n, all]) => ({ n, all, rs: all.filter(ROLE_PICK[pick]) })).filter((x) => x.rs.length >= S.coachMin).map((x) => Object.assign(x, { a: agg(x.rs) }));
    const sortK = S.cSort || "car", dir = S.cDir || -1;
    rows.sort((x, z) => { const a = x.a[sortK], b = z.a[sortK]; if (a == null) return 1; if (b == null) return -1; return dir * (a - b); });
    const sb = (k) => () => { if (S.cSort === k) S.cDir = -(S.cDir || -1); else { S.cSort = k; S.cDir = -1; } save(); route(); };
    const t = table([{ cols: [{ h: "Coach", cls: "l fz" }, { h: "Seasons", onSort: sb("n"), lit: sortK === "n" }, { h: "Teams", cls: "l" }, { h: "Every job", cls: "l", t: "Seasons in each job across his whole offensive-staff history: HC head coach, OC coordinator, PC play-caller, PGC / RGC pass / run game coordinator, QB / RB / WR / TE / OL position coach" }, { h: "Style", cls: "l" }], end: 1 },
                     { name: "Lead back (in his games)", end: 1, cols: [{ h: "Car%", onSort: sb("car"), lit: sortK === "car" }, { h: "Opp%", onSort: sb("opp"), lit: sortK === "opp" }, { h: "Snap%", onSort: sb("snp"), lit: sortK === "snp" }, { h: "GL%", onSort: sb("gl"), lit: sortK === "gl" }] },
                     { name: "Backfield", end: 1, cols: [{ h: "Backs used", onSort: sb("eff"), lit: sortK === "eff" }, { h: "Bell-cow yrs", onSort: sb("cow"), lit: sortK === "cow", t: "Seasons his lead back took 72%+ of RB carries in his games (the top third of team-seasons)" }, { h: "Committee yrs", onSort: sb("com"), lit: sortK === "com", t: "Seasons his lead back took under 58% (the bottom third)" }] },
                     { name: "Passing game", end: 1, cols: [{ h: "RB Tgt%", onSort: sb("tgt"), lit: sortK === "tgt" }] }], { tall: true });
    const carAll = rows.map((r) => r.a.car).filter((v) => v != null).sort((a, b) => a - b), pr = (v) => { let lo = 0; for (const x of carAll) if (x < v) lo++; return 100 * lo / Math.max(carAll.length - 1, 1); };
    for (const r of rows) {
      const teams = [...new Set(r.all.map((x) => x.tm))].join(", "), [vd, vp] = verdict(r.a), tag = el("span", "tag", vd), vc = td(null, "l"); paint(tag, vp); tag.classList.remove("heat"); vc.append(tag);
      const car = td(pc(r.a.car)); paint(car, pr(r.a.car));
      const tr = t.addRow([cellLink(r.n, "#coach/" + encodeURIComponent(r.n), "l fz"), td(String(r.a.n)), td(teams, "l"), td(catLine(r.all), "l"), vc, car, td(pc(r.a.opp)), td(pc(r.a.snp, 0)), td(pc(r.a.gl, 0)), td(num(r.a.eff, 2)), td(String(r.a.cow)), td(String(r.a.com)), td(pc(r.a.tgt))]);
      tr.dataset.k = r.n.toLowerCase();
    }
    t.addRow([td("League, 2016–" + String(CUR).slice(2), "l fz"), td(String(L.n)), td(""), td(""), td(""), td(pc(L.car)), td(pc(L.opp)), td(pc(L.snp, 0)), td(pc(L.gl, 0)), td(num(L.eff, 2)), td(String(L.cow)), td(String(L.com)), td(pc(L.tgt))], "tot first");
    q.addEventListener("input", () => { const s = q.value.trim().toLowerCase(); t.querySelectorAll("tbody tr[data-k]").forEach((tr) => { tr.hidden = !!s && !tr.dataset.k.includes(s); }); });
    requestAnimationFrame(() => { const first = t.querySelector("tbody td.fz"); if (first) t.style.setProperty("--fzw", first.offsetWidth + "px"); });
    main.append(t.box, el("p", "note", `${rows.length} coaches. Head coaches and Coordinators average only the seasons in that job; Every offensive coach averages every season he was on the staff, position coach included. Style: Bell cow when his lead backs averaged 68%+ of RB carries in their games (the top third of coaches), Committee under 60% (the bottom third), and between them a lead back with a change of pace. A lead back takes 64% of the carries in his games in a typical season. Staffs are each season's final staff on Wikipedia, so a coach let go mid-season isn't listed that year (a head coach always is, from the games).`));
  }

  function coachPage(main, name) {
    name = decodeURIComponent(name); const rs = [...(coachSeasons().get(name) || [])].sort((a, b) => a.y - b.y);
    main.textContent = "";
    if (!rs.length) { main.append(el("p", "load", "No seasons for that coach.")); return; }
    const a = agg(rs), L = leagueAvg(), [vd, vp] = verdict(a);
    main.append(el("h1", "ttl", name));
    const v = el("div", "verdict"), tag = el("span", "tag", vd); paint(tag, vp); tag.classList.remove("heat");
    v.append(tag, `${rs.length} season${rs.length > 1 ? "s" : ""} on an offensive staff · ${catLine(rs)}`); main.append(v);
    // where he's been, stint by stint
    const st = el("ul", "stints");
    for (const s of stints(rs)) { const li = el("li"); li.append(link(`${s.tm} ${yrs(s.y0, s.y1)}`, `#team/${s.tm}/${s.y1}`), " — " + s.roles.join(", ")); st.append(li); }
    main.append(st);
    const k = el("div", "kpis"), kp = (lab, val, lg) => { const d = el("div"); d.append(el("b", null, val), el("small", null, `${lab} · league ${lg}`)); k.append(d); };
    kp("Lead back's carry share", pc(a.car), pc(L.car)); kp("Lead back's snap share", pc(a.snp, 0), pc(L.snp, 0)); kp("Backs used", num(a.eff, 2), num(L.eff, 2)); kp("RB share of targets", pc(a.tgt), pc(L.tgt)); kp("Lead back's goal-line share", pc(a.gl, 0), pc(L.gl, 0));
    main.append(k);
    main.append(el("h3", "secttl", "Season by season"));
    const t = table([{ cols: [{ h: "Season", cls: "fz" }, { h: "Tm" }, { h: "His job", cls: "l" }, { h: "Head coach", cls: "l" }], end: 1 }, { name: "Lead back, in his games", end: 1, cols: [{ h: "RB1", cls: "l" }, { h: "G" }, { h: "Car%" }, { h: "Opp%" }, { h: "Snap%" }, { h: "GL%" }, { h: "FP/Opp" }] },
                     { name: "Second back", end: 1, cols: [{ h: "RB2", cls: "l" }, { h: "Car%" }, { h: "FP/Opp" }, { h: "Next yr Car%", t: "The same back's carry share the following season, wherever he played" }] }, { name: "Backfield", end: 1, cols: [{ h: "Backs used" }, { h: "RB Tgt%" }] }]);
    const allCar = SEASONS.flatMap((y) => (TEAMS[y] || []).map((r) => r.rb1car)).sort((x, z) => x - z), pr = (val) => { let lo = 0; for (const x of allCar) if (x < val) lo++; return 100 * lo / Math.max(allCar.length - 1, 1); };
    for (const r of rs) {
      const b1 = r.rbs[0], b2 = r.rbs[1], car = td(pc(r.rb1car)); paint(car, pr(r.rb1car));
      const f1 = fpo(b1), f2 = b2 ? fpo(b2) : null, f2c = td(num(f2, 2)); if (f2 != null && f1 != null && f2 > f1 + 0.1) { f2c.style.color = "var(--stripe)"; f2c.style.fontWeight = "700"; }
      let nxt = "–"; if (b2) { const nx = (TEAMS[r.y + 1] || []).find((x) => x.rbs.some((b) => b.id === b2.id)); if (nx) { const i = nx.rbs.findIndex((b) => b.id === b2.id), all = nx.rbcar || 1; nxt = pc(100 * nx.rbs[i].car / all) + (nx.tm !== r.tm ? ` (${nx.tm})` : ""); } }
      const job = td(r.roles.join(", ") + (r.cats.has("PC") && !r.cats.has("OC") ? " (called plays)" : ""), "l");
      const hcc = td(null, "l"); if (r.hc && r.hc !== name) hcc.append(link(r.hc, "#coach/" + encodeURIComponent(r.hc))); else hcc.textContent = r.hc === name ? "himself" : "–";
      t.addRow([cellLink(String(r.y), `#team/${r.tm}/${r.y}`, "fz"), td(r.tm), job, hcc, cellLink(b1.n, "#player/" + b1.id), td(String(r.rb1g)), car, td(pc(r.rb1opp)), td(b1.snp == null ? "–" : Math.round(b1.snp) + "%"), td(r.rb1gl == null ? "–" : pc(r.rb1gl, 0)), td(num(f1, 2)),
                b2 ? cellLink(b2.n, "#player/" + b2.id) : td("–"), td(pc(r.rb2car)), f2c, td(nxt), td(num(r.eff, 2)), td(pc(share(r.rbtgt, r.tmtgt)))]);
    }
    main.append(t.box, el("p", "note", "Every season he was on an offensive staff, in whatever job. Car% is coloured against every team-season since 2016. An RB2's FP/Opp in red beat the lead back's; Next yr Car% shows whether he got more of the work the following season (his share of that team's RB carries over the whole season)."));
  }

  // ---------- routing ----------
  function route() {
    const h = location.hash.replace(/^#/, "") || "leaders", [page, a, b] = h.split("/");
    document.querySelectorAll(".nav a[data-page]").forEach((x) => x.classList.toggle("on", x.dataset.page === page || (page === "team" && x.dataset.page === "backfields") || (page === "coach" && x.dataset.page === "coaches")));
    const main = $("main"); main.innerHTML = '<p class="load">Loading…</p>';
    const go = page === "player" ? player(main, a) : page === "backfields" ? backfields(main) : page === "team" ? teamPage(main, a, b) : page === "coaches" ? coaches(main) : page === "coach" ? coachPage(main, a) : leaders(main);
    Promise.resolve(go).catch((err) => { main.textContent = ""; main.append(el("p", "load", "Couldn't load that season's data. Check the connection and reload.")); console.error(err); });
    if (S.lastPage !== h) { window.scrollTo(0, 0); S.lastPage = h; save(); }
  }
  document.body.prepend(header());
  window.addEventListener("hashchange", route);
  route();
})();
