/* 2027 Draft Board — rankings + draft mode on one data set. No build step, no dependencies.
   Percentiles and scores are computed here, within the pool the user's minimum (AB / IP) defines. */
(function () {
  "use strict";
  const DATA = window.DRAFT_DATA;
  if (!DATA) { document.getElementById("board").textContent = "data.js is missing — run build_data.py first."; return; }

  const HIT_TABS = ["ALL", "C", "1B", "2B", "3B", "SS", "OF", "DH"];
  const PIT_TABS = ["ALLP", "SP", "RP"];
  const TAB_LABEL = { ALL: "All hitters", ALLP: "All pitchers" };
  const SHORT = { pu: "Popup%", ev: "EV", brl: "Brl%", pull: "Pull Air", air: "Air%", osw: "O-Sw", zsw: "Z-Sw", zcon: "Z-Con", ocon: "O-Con", whf: "Whiff", swstr: "SwStr", strk: "Strike", gb: "GB%", nera: "nERA", uera: "uERA", ukb: "u(K-BB%)", pullp: "Pull%", npull: "Non-pull", cent: "Cent%", oppo: "Oppo%", zmo: "(Z−O) Sw", ba: "BA", slg: "SLG", xba: "xBA", xslg: "xSLG" };
  const LS = { drafted: "draft2027.drafted", prefs: "draft2027.prefs", extra: "draft2027.extraRoles", roles: "draft2027.roles", ranks: "draft2027.ranks",
               tiers: "draft2027.tiers", tierNames: "draft2027.tierNames", sets: "draft2027.rankSets", extraPos: "draft2027.extraPos", stars: "draft2027.stars" };
  // MLB teams by league and division (the codes the data uses; the A's were OAK through 2024)
  const DIVS = { "AL East": ["BAL", "BOS", "NYY", "TB", "TOR"], "AL Central": ["CWS", "CLE", "DET", "KC", "MIN"], "AL West": ["ATH", "HOU", "LAA", "SEA", "TEX"],
                 "NL East": ["ATL", "MIA", "NYM", "PHI", "WSH"], "NL Central": ["CHC", "CIN", "MIL", "PIT", "STL"], "NL West": ["AZ", "COL", "LAD", "SD", "SF"] };
  const TEAM_ALIAS = { OAK: "ATH" };
  const TEAM_NAMES = { BAL: "Orioles", BOS: "Red Sox", NYY: "Yankees", TB: "Rays", TOR: "Blue Jays", CWS: "White Sox", CLE: "Guardians", DET: "Tigers", KC: "Royals", MIN: "Twins",
                       ATH: "Athletics", HOU: "Astros", LAA: "Angels", SEA: "Mariners", TEX: "Rangers", ATL: "Braves", MIA: "Marlins", NYM: "Mets", PHI: "Phillies", WSH: "Nationals",
                       CHC: "Cubs", CIN: "Reds", MIL: "Brewers", PIT: "Pirates", STL: "Cardinals", AZ: "D-backs", COL: "Rockies", LAD: "Dodgers", SD: "Padres", SF: "Giants" };
  const teamCode = (t) => TEAM_ALIAS[t] || t;
  const teamsIn = (f) => (f.kind === "team" ? [f.v] : f.kind === "div" ? DIVS[f.v] || [] : Object.entries(DIVS).filter(([d]) => d.startsWith(f.v)).flatMap(([, t]) => t));
  const teamOK = (p) => { const f = state.teamF; if (!f) return true; return teamsIn(f).includes(teamCode(p.team)); };
  const teamLabel = (f) => (!f ? "Team" : f.kind === "team" ? f.v : f.v);
  const HEAD = DATA.meta.hitterHeadline;   // {key: "xwoba", label: "xwOBA"} — the hitter headline number
  const CARD = DATA.meta.hitterCard;        // grouped hitter card metrics
  const CARD_P = DATA.meta.pitcherCard;     // grouped pitcher card metrics

  // A dataset is one season-level population: the current season (data.js + days.js) or a past season from
  // hist/<key>.js. DS is the dataset in effect while computing; Rankings/Draft always use CUR, Explore switches.
  const CUR = {
    key: "mlb-" + DATA.meta.season, label: DATA.meta.season + " MLB", season: DATA.meta.season, level: "MLB", levelName: "MLB", hist: false,
    players: DATA.players, consts: DATA.meta.consts, refPA: DATA.meta.refMinPA || 300, airNoPU: !!DATA.meta.airNoPU,
    days: DATA.meta.days,
    rows: (p) => (window.DRAFT_DAYS && window.DRAFT_DAYS[p.type + p.id]) || [],
    er: (p) => (window.DRAFT_DAYS && window.DRAFT_DAYS[p.type + p.id + ":er"]) || [],
    ready: () => !!window.DRAFT_DAYS,
    load: () => ensureDays(),
  };
  let DS = CUR;
  function withDataset(ds, fn) { const prev = DS; DS = ds; try { return fn(); } finally { DS = prev; } }
  function histDataset(key) {
    if (key === CUR.key) return CUR;
    if (isMulti(key)) return multiDataset(key);
    const h = window.DRAFT_HIST && window.DRAFT_HIST[key];
    if (!h) return null;
    const daily = () => window.DRAFT_HIST_DAYS && window.DRAFT_HIST_DAYS[key];
    const ds = { key, label: h.label, season: h.season, level: h.level || "MLB", levelName: h.levelName || h.level || "MLB", hist: true, kind: h.kind || "",
                 noStatcast: !!h.noStatcast, tracked: h.tracked,
                 players: h.players, consts: h.consts, refPA: h.refPA, airNoPU: !!h.airNoPU, days: h.days || null,
                 er: (p) => (daily() && daily()[p.type + p.id + ":er"]) || [] };
    // split rows (hand x venue) are inline; per-day rows come from hist/days-<season>.js when a date range is set
    ds.rows = (p) => (winRequested() ? (daily() ? daily()[p.type + p.id] : null) : h.rows[p.type + p.id]) || [];
    ds.ready = () => !winRequested() || !!daily();
    ds.load = () => { if (h.days) ensureScript(`hist/${h.daysFile || `days-${h.season}.js`}`, () => !!daily()); };
    return ds;
  }
  // A span of seasons on the Leaderboard. "mlb-2023_2025" folds every season a player had in the span into one
  // line (his rows are summed like a date window); "mlb-2023_2025+each" lists every player-season as its own line.
  // Members are the built seasons in the range at that level and game type.
  const isMulti = (key) => /^[a-z]+-\d{4}_\d{4}/.test(key || "");
  function parseMulti(key) {
    const m = /^([a-z]+)-(\d{4})_(\d{4})(-spring|-post)?(\+each)?$/.exec(key || ""); if (!m) return null;
    const years = []; for (let y = Number(m[2]); y <= Number(m[3]); y++) years.push(y);
    return { level: m[1], from: Number(m[2]), to: Number(m[3]), kind: m[4] ? m[4].slice(1) : "", each: !!m[5], years, members: years.map((y) => `${m[1]}-${y}${m[4] || ""}`) };
  }
  const multiKey = (level, from, to, kind, each) => `${level}-${from}_${to}${kind ? "-" + kind : ""}${each ? "+each" : ""}`;
  const builtKeys = () => (indexReady() ? window.DRAFT_INDEX.seasons : [CUR.key]);
  const yearSpan = (years) => (years.length > 1 ? `${years[0]}–${String(years[years.length - 1]).slice(2)}` : String(years[0] ?? ""));
  const meanOf = (objs) => { const out = {}; for (const k of Object.keys(objs[0] || {})) { const v = objs.map((o) => o[k]).filter((x) => x != null); if (!v.length) continue; out[k] = typeof v[0] === "object" ? meanOf(v) : Math.round(1e4 * v.reduce((a, b) => a + b, 0) / v.length) / 1e4; } return out; };
  const multiCache = new Map();
  function multiDataset(key) {
    if (multiCache.has(key)) return multiCache.get(key);
    const mp = parseMulti(key); if (!mp) return null;
    const keys = mp.members.filter((k) => builtKeys().includes(k)); if (!keys.length) return null;
    for (const k of keys) ensureHist(k);
    const parts = keys.map((k) => histDataset(k)); if (parts.some((d) => !d)) return null;   // still loading a member
    const years = parts.map((d) => d.season), n = parts.length, last = parts[n - 1];
    const ds = { key, label: `${yearSpan(years)} ${last.levelName}${kindTag(keys[0])}${mp.each ? " · each season" : ""}`, season: yearSpan(years), years, level: last.level, levelName: last.levelName,
                 hist: true, kind: mp.kind, multi: true, each: mp.each, aggregate: !mp.each, noStatcast: parts.every((d) => d.noStatcast), tracked: undefined,
                 consts: meanOf(parts.map((d) => d.consts)), airNoPU: parts.every((d) => d.airNoPU),
                 days: parts.reduce((a, d) => (d.days && d.days.length > a.length ? d.days : a), []),
                 refPA: Math.round(parts.reduce((a, d) => a + d.refPA, 0) / n) * (mp.each ? 1 : n), minScale: mp.each ? 1 : n,
                 ready: () => parts.every((d) => d.ready()), load: () => parts.forEach((d) => { if (!d.ready()) d.load(); }) };
    if (mp.each) {
      // one line per player-season; the id carries the year so the same player can sit in the list several times
      ds.players = parts.flatMap((d) => d.players.map((q) => Object.assign({}, q, { id: `${q.id}@${d.season}`, pid: q.id, dsKey: d.key, season: d.season, src: d, real: q })));
      ds.rows = (p) => p.src.rows(p.real);
      ds.er = (p) => p.src.er(p.real);
    } else {
      const byKey = new Map();
      for (const d of parts) for (const q of d.players) { const k = q.type + q.id; if (!byKey.has(k)) byKey.set(k, []); byKey.get(k).push([d, q]); }
      const sum = (arr, f) => arr.reduce((a, x) => a + (f(x) || 0), 0);
      ds.players = [...byKey.values()].map((pairs) => {
        const q0 = pairs[pairs.length - 1][1], qs = pairs.map((x) => x[1]);         // the latest season names him
        const p = { id: q0.id, name: q0.name, team: q0.team, type: q0.type, primary: q0.primary, bats: q0.bats, throws: q0.throws, age: q0.age,
                    pos: {}, milb: {}, parts: pairs, seasons: pairs.map((x) => x[0].season), m: {}, ctx: {} };
        for (const q of qs) { for (const [k, g] of Object.entries(q.pos || {})) p.pos[k] = (p.pos[k] || 0) + g; for (const [k, g] of Object.entries(q.milb || {})) p.milb[k] = (p.milb[k] || 0) + g; }
        if (p.type === "H") { p.pa = sum(qs, (q) => q.pa); p.ab = sum(qs, (q) => q.ab); }
        else {
          p.bf = sum(qs, (q) => q.bf); p.ip = Math.round(1000 * sum(qs, (q) => q.ip)) / 1000;
          const er = qs.filter((q) => q.m && q.m.era != null && q.ip);
          p.ctx = { G: sum(qs, (q) => q.ctx.G), GS: sum(qs, (q) => q.ctx.GS), IPs: sum(qs, (q) => q.ctx.IPs), IPr: sum(qs, (q) => q.ctx.IPr),
                    ER: er.length ? Math.round(sum(er, (q) => q.m.era * q.ip / 9)) : null };
        }
        return p;
      });
      ds.rows = (p) => { if (p._rows) return p._rows; const rows = p.parts.flatMap(([d, q]) => d.rows(q)); if (ds.ready()) p._rows = rows; return rows; };
      ds.er = () => [];
    }
    multiCache.set(key, ds);
    return ds;
  }
  const K = () => DS.consts;                // league ERA, FIP constant, SIERA shift of the dataset in effect
  // every metric that needs a percentile: the card groups plus the row bubbles
  const union = (card, row) => { const seen = new Map(); for (const g of card) for (const m of g.metrics) if (!seen.has(m.key)) seen.set(m.key, m); for (const m of row) if (!seen.has(m.key)) seen.set(m.key, m); return [...seen.values()]; };
  const SUB = DATA.meta.hitterSub || {};      // fold-out breakdown rows under a card metric (Air% -> FB%, LD%)
  const RULE_H = new Set(DATA.meta.hitterCardRules || ["ev90"]);   // hitter card rows that start a ruled-off block
  const SUB_P = DATA.meta.pitcherSub || {};   // pitcher fold-outs (K-BB% -> K%, BB% …)
  const ALL_H = union([...CARD, { metrics: Object.values(SUB).flat() }], DATA.meta.hitterMetrics);
  const ALL_P = union([...CARD_P, { metrics: Object.values(SUB_P).flat() }], DATA.meta.pitcherMetrics);
  const allFor = (g) => (g === "H" ? ALL_H : ALL_P);
  // Swartz's SIERA (2011) plus this season's shift
  function siera(k, bb, gb, fb, pu, pa) {
    if (!pa) return null;
    const so = k / pa, w = bb / pa, x = (gb - fb - pu) / pa;
    return 6.145 - 16.986 * so + 11.434 * w - 1.858 * x + 7.653 * so * so - 6.664 * x * Math.abs(x) + 10.13 * so * x - 5.195 * w * x + K().sieraShift;
  }

  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };

  /* ---------- state ---------- */
  const prefs = load(LS.prefs, {});
  if (prefs.v !== 2) { delete prefs.min; prefs.v = 2; }     // hitter minimum switched from AB to PA
  const state = {
    mode: "rankings",
    pos: prefs.pos || "ALL",
    q: "",
    sort: prefs.sort || "score",
    dir: prefs.dir || "desc",
    min: Object.assign({}, DATA.meta.defaultMin, prefs.min || {}),   // {H: AB, SP: IP, RP: IP, P: IP}
    pageSize: prefs.pageSize != null ? prefs.pageSize : (window.DRAFT_THEMES && window.DRAFT_THEMES.view() === "mobile" ? 25 : 50),   // rows per page; 0 = all
    cols: prefs.cols || {},                    // {rankings: {H: [...keys], P: [...]}, trending: …, draft: …}; the Leaderboard keeps state.lb
    panel: null,                               // "stats" | "splits": the open toolbar panel
    cardTools: !!prefs.cardTools,              // the card's splits / dates block shown
    stars: load("draft2027.stars", {}),        // the working list's starred players: key -> {note, at}; saved into a list with it
    starOnly: !!prefs.starOnly,                // Rankings / Draft: show only starred players
    starOpen: null,                            // the card whose star panel is open
    page: 1, pageSig: "",
    ref: prefs.ref || "own",          // pitcher tabs: rank vs "own" pool, "SP", "RP", or "P" (all pitchers)
    win: { from: "", to: "", last: "" },       // list window (session only): dates, or "last N" PA / IP per player, optionally through a date
    // Trending page: hitters by xwOBA and pitchers by score over each player's last N PA / IP, or the last N days
    // per group: the unit in use, the span for each unit, and the least playing time inside the span to be listed
    trend: { H: Object.assign({ unit: "pa", pa: 100, days: 14, min: { pa: 50, days: 15 } }, (prefs.trend || {}).H),
             P: Object.assign({ unit: "ip", ip: 30, days: 30, min: { ip: 10, days: 5 } }, (prefs.trend || {}).P) },
    cardWin: { from: "", to: "", last: "" },   // the open card's own window; a blank side means the season's start / end
    cardDs: null,                                  // the open card's season (dataset key); null = current season
    editRanks: false,                              // Rankings page: edit mode (rank / tier boxes, drag, tier picker)
    tierPick: null,                                // tier picker open for the current selection
    selKeys: [],                                   // edit mode: selected rows (in click order)
    selAnchor: null,
    flash: "",
    split: { hand: "all", venue: "all" },   // the open card's split (session only, never saved) — hand: all | L | R · venue: all | home | away
    daysLoading: false,
    x: Object.assign({ id: null, type: null, ds: null }, prefs.x || {}),   // Explore: selected player + season
    gq: "",                                        // the header's player search
    colPick: false,                                // Leaderboard: the column picker is open
    lbDs: prefs.lbDs || null,                      // Leaderboard: the season / level shown (null = the current season)
    lbTo: prefs.lbTo || null,                      // Leaderboard: the last year of a span (null = one season)
    lbEach: !!prefs.lbEach,                        // span: every player-season on its own line (else one combined line per player)
    pre: Object.assign({ year: "auto", age: false }, prefs.pre || {}),
    tbFold: !!prefs.tbFold,
    teamF: prefs.teamF || null,                    // {kind: "lg" | "div" | "team", v} — only that league, division or team                        // filters tucked away behind a slim bar (it stays pinned, so they can come back from anywhere)   // Year / Age columns right after the name ("auto": Year when the list spans seasons)
    lbSplit: { hand: "all", venue: "all" },       // Leaderboard: vs L / R and home / away (session only, like the card's)
    lb: Object.assign({ H: ["woba", "ev", "brl", "hh", "pull", "air", "gb", "zsw", "osw", "whf", "k", "bb"],
                        P: ["whf", "strk", "gb", "k", "bb", "kbb", "ukb", "era", "nera", "uera", "siera", "fip", "fbv"] }, prefs.lb || {}),   // Leaderboard columns
    open: prefs.open || {},          // which fold-out rows are expanded, e.g. {air: true}
    cmp: Object.assign({ type: "H", players: [] }, prefs.cmp || {}),   // Compare page: [{id, ds}]
    cmpCols: prefs.cmpCols || {},              // Compare: chosen stats per type {H: [keys], P: [keys]}; missing = every card stat
    rawMode: prefs.rawMode || "mlb",           // Season by season: "mlb" | "milb" | "all"
    tbl: Object.assign({ heat: false, band: true, sortHl: true, density: "comfortable", numbers: "auto", breaks: {} }, prefs.tbl || {}),   // Table features; breaks: {"mode:H": [keys with a rule after them]}
    cq: "",
    showDrafted: !!prefs.showDrafted,
    expanded: null,
    drafted: load(LS.drafted, []),   // [{id, name, t}]
    extraPos: load(LS.extraPos, {}), // positions you've added to a player's eligibility: {id: ["2B", "SP"]}
    ranks: load(LS.ranks, {}),       // manual rankings per tab: {ALL: ["H670541", ...], SS: [...], SP: [...]}
    tiers: load(LS.tiers, {}),       // tier members per tab: {ALL: [["H1", "H2"], ["H5"]]} — independent of the rank order
    tierView: prefs.tierView || "tiers",           // Rankings / Draft: "tiers" groups the list by tier, "list" is the raw order
    tierNames: load(LS.tierNames, {}),   // optional tier names per tab: {ALL: ["Elite", "Studs"]}
    rankSets: load(LS.sets, {}),     // saved sets: {name: {ranks, tiers, tierNames, saved}}
    currentSet: prefs.currentSet || null,          // the saved list the working rankings were opened from (Save writes back to it)
    draftOrder: prefs.draftOrder || "board",   // Draft page: "board", "mine" (working rankings) or "set:<name>"

  };
  if (state.lb.P.includes("nera") && !state.lb.P.includes("uera")) state.lb.P.splice(state.lb.P.indexOf("nera") + 1, 0, "uera");     // uERA back 2026-09-21
  if (state.lb.P.includes("kbb") && !state.lb.P.includes("ukb")) state.lb.P.splice(state.lb.P.indexOf("kbb") + 1, 0, "ukb");       // added 2026-09-21
  let poolVersion = 0;               // bumps when eligibility changes, so cached pools rebuild
  // tiers used to be stored as break ranks ([5, 12]); convert to sizes ([5, 7]) once
  const breaksToSizes = (t) => { const out = {}; for (const [tab, br] of Object.entries(t || {})) { const b = br.slice().sort((x, y) => x - y); out[tab] = b.map((v, i) => v - (i ? b[i - 1] : 0)); } return out; };
  (function migrateTiers() {
    const flag = load("draft2027.tiersFmt", 1);
    if (flag >= 2) return;
    state.tiers = breaksToSizes(state.tiers);
    for (const s of Object.values(state.rankSets)) s.tiers = breaksToSizes(s.tiers);
    save(LS.tiers, state.tiers); save(LS.sets, state.rankSets); save("draft2027.tiersFmt", 2);
  })();
  (function migrate() {
    const oldExtra = load(LS.extra, null), oldRoles = load(LS.roles, null); let changed = false;
    if (oldExtra) { for (const [id, roles] of Object.entries(oldExtra)) for (const r of roles) { const l = state.extraPos[id] || (state.extraPos[id] = []); if (!l.includes(r)) l.push(r); } changed = true; }
    if (oldRoles) { for (const [id, r] of Object.entries(oldRoles)) { const l = state.extraPos[id] || (state.extraPos[id] = []); if (!l.includes(r)) l.push(r); } changed = true; }
    if (changed) { save(LS.extraPos, state.extraPos); try { localStorage.removeItem(LS.extra); localStorage.removeItem(LS.roles); } catch {} }
  })();
  function load(k, fb) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : fb; } catch { return fb; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode etc. */ } }
  function savePrefs() { save(LS.prefs, { v: 2, pos: state.pos, sort: state.sort, dir: state.dir, min: state.min, ref: state.ref, x: state.x, open: state.open, cmp: state.cmp, draftOrder: state.draftOrder, showDrafted: state.showDrafted, tierView: state.tierView, currentSet: state.currentSet, trend: state.trend, lb: state.lb, lbDs: state.lbDs, lbTo: state.lbTo, lbEach: state.lbEach, pre: state.pre, tbFold: state.tbFold, teamF: state.teamF, pageSize: state.pageSize, cols: state.cols, cardTools: state.cardTools, starOnly: state.starOnly, cmpCols: state.cmpCols, rawMode: state.rawMode, tbl: state.tbl }); }
  const draftedIds = () => new Set(state.drafted.map((d) => d.id));

  /* ---------- date window ---------- */
  const DF = { H: DATA.meta.dayFields.H, P: DATA.meta.dayFields.P };
  const seasonDays = () => DS.days || DATA.meta.days;
  const seasonFirst = () => seasonDays()[0], seasonLast = () => seasonDays()[seasonDays().length - 1];
  // active window as {from, to} ISO dates, or null for the full season
  let WIN = null;                                  // window in effect while computing (null = the list's)
  function withWindow(w, fn) { const prev = WIN; WIN = w; try { return fn(); } finally { WIN = prev; } }
  // dates typed into the from/to boxes: a blank side means the season's first / last day
  const lastN = (w) => (Number(w.last) > 0 ? Math.round(Number(w.last)) : 0);
  const addDays = (iso, k) => new Date(Date.parse(iso + "T12:00:00Z") + k * 864e5).toISOString().slice(0, 10);
  // Trending: each player's last N PA / IP, or the last N calendar days through the data's last day
  const TREND_TABS = [...HIT_TABS, ...PIT_TABS];
  const trendCfg = (g = groupFor(state.pos)) => state.trend[isPitcherGroup(g) ? "P" : "H"];
  const trendMin = (g) => { const t = trendCfg(g); return Number((t.min || {})[t.unit]) || 0; };
  function trendWin(g) {
    const t = trendCfg(g), n = Math.max(1, Math.round(Number(t[t.unit]) || 1));
    if (t.unit === "days") { const days = DATA.meta.days, from = addDays(days[days.length - 1], 1 - n); return { from: from > days[0] ? from : "", to: "", last: "" }; }
    return { from: "", to: "", last: String(n) };
  }
  const listWin = () => (state.mode === "trending" ? trendWin() : state.win);
  const daysBack = (n) => { const d = new Date(DATA.meta.through + "T12:00:00"); d.setDate(d.getDate() - (n - 1)); return d.toISOString().slice(0, 10); };
  const winRequested = () => { const w = WIN || listWin(); return !!(w.from || w.to || lastN(w)); };
  function winDates() {
    const w = WIN || listWin(), last = lastN(w);
    if (!w.from && !w.to && !last) return null;
    const days = seasonDays();
    const from = (last ? "" : w.from) || days[0], to = w.to || days[days.length - 1];   // "last N" starts wherever each player's N begins
    if (!last && from <= days[0] && to >= days[days.length - 1]) return null;
    return { from, to, last };
  }
  // the window as day-index bounds [lo, hi], or null (also null while a past season's day rows are still loading)
  function winIdx() {
    const w = winDates(); if (!w) return null;
    if (DS.hist && !DS.ready()) return null;
    const days = seasonDays();
    let lo = days.findIndex((d) => d >= w.from); if (lo < 0) lo = days.length;
    let hi = days.length - 1; while (hi >= 0 && days[hi] > w.to) hi--;
    return { lo, hi, from: w.from, to: w.to, last: w.last };
  }
  const winKey = () => { const w = winIdx(); return w ? w.lo + "-" + w.hi + (w.last ? "L" + w.last : "") : winRequested() ? "pending" : "all"; };
  const fmtDate = (iso) => new Date(iso + "T12:00:00Z").toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const lastUnit = (type) => ((type ? type === "P" : isPitcherGroup(groupFor(state.pos))) ? "IP" : "PA");
  const winLabel = (type) => {
    const w = winIdx(); if (!w) return "full season";
    if (w.last) return `last ${w.last} ${lastUnit(type)}${w.to < seasonLast() ? ` through ${fmtDate(w.to)}` : ""}`;
    return `${fmtDate(w.from)} – ${fmtDate(w.to)}`;
  };

  // The list always shows the unsplit view; a player's card can be drawn for a split. SPLIT is the split in
  // effect while computing — NONE for the list, state.split inside the open card (see withSplit).
  const NONE = { hand: "all", venue: "all" };
  let SPLIT = NONE;
  function withSplit(sp, fn) { const prev = SPLIT; SPLIT = sp; try { return fn(); } finally { SPLIT = prev; } }
  // game-by-game split rows live in days.js and load the first time a window or split is chosen
  const splitActive = () => SPLIT.hand !== "all" || SPLIT.venue !== "all";
  // pool minimum in effect: the tab's Min PA / IP, always judged on the FULL season (a date range or split only
  // changes the numbers being compared, never who qualifies)
  // the Min PA / IP box is a full-season number; spring training and postseason sets (tiny refPA) scale it down
  function effMin(g) { return DS.refPA < 100 ? Math.max(1, Math.round(state.min[g] * DS.refPA / REF_PA)) : state.min[g] * (DS.minScale || 1); }
  const seasonSample = (p) => (p.type === "P" ? p.ip : p.pa);
  // the reference population every percentile is measured against: hitters with 300+ PA (pro-rated for a
  // date window or split); pitchers use the tab's minimum
  const REF_PA = DATA.meta.refMinPA || 300;
  function refMin(g) { return DS.refPA; }                 // hitters: PA; pitchers: batters faced — same bar, any position or role
  const refSample = (p) => (p.type === "P" ? p.bf : p.pa);   // the full-season count that qualifies a player for the reference population
  const needsDays = () => winRequested() || splitActive();
  const daysReady = () => DS.ready();
  // the hosted copy versions every file it serves (window.DRAFT_BUILD), so a changed file is fetched at once
  // instead of being served from the phone's cache; anywhere else the map is absent and the plain name is used
  const vsrc = (src) => { const v = window.DRAFT_BUILD && window.DRAFT_BUILD[src]; return v ? src + "?v=" + v : src; };
  function ensureDays() {
    if (daysReady() || state.daysLoading) return;
    state.daysLoading = true;
    const sc = document.createElement("script"); sc.src = vsrc("days.js");
    sc.onload = () => { state.daysLoading = false; valCache.clear(); poolCache.clear(); rankCache.clear(); render(); };
    sc.onerror = () => { state.daysLoading = false; state.daysFailed = true; render(); };
    document.head.append(sc);
  }
  const rowsOf = (p) => DS.rows(p);
  // Explore data: hist/index.js (who exists in which seasons) and hist/<key>.js per past season, loaded on demand
  const loading = new Set(), failed = new Set();
  function ensureScript(src, isReady) {
    if (isReady() || loading.has(src) || failed.has(src)) return;
    loading.add(src);
    const sc = document.createElement("script"); sc.src = vsrc(src);
    sc.onload = () => { loading.delete(src); valCache.clear(); poolCache.clear(); rankCache.clear(); render(); if (state.gq) renderGlobalSearch(); };
    sc.onerror = () => { loading.delete(src); failed.add(src); render(); };
    document.head.append(sc);
  }
  const indexReady = () => !!window.DRAFT_INDEX;
  const ensureIndex = () => ensureScript("hist/index.js", indexReady);
  const ensureHist = (key) => (key === CUR.key ? ensureDays() : isMulti(key) ? multiDataset(key) : ensureScript(`hist/${key}.js`, () => !!(window.DRAFT_HIST && window.DRAFT_HIST[key])));
  const needsRows = () => needsDays() || !!DS.aggregate;   // a combined span always sums rows, window or not
  const ensureView = () => { if (needsRows() && !DS.ready()) DS.load(); };   // fetch whatever the current view needs
  const viewKey = () => DS.key + ":" + winKey() + ":" + SPLIT.hand + ":" + SPLIT.venue;
  const splitLabel = () => {
    const parts = [];
    if (SPLIT.hand !== "all") parts.push("vs " + SPLIT.hand + "H" + (isPitcherGroup(groupFor(state.pos)) ? "B" : "P"));
    if (SPLIT.venue !== "all") parts.push(SPLIT.venue === "home" ? "home" : "away");
    return parts.join(" · ");
  };
  const viewLabel = (type) => [winLabel(type), splitLabel()].filter(Boolean).join(" · ");

  // fill derived hitter metrics that older data files may lack
  // season xwOBA = Savant's number; a file built while the headline was the directional model gets it rebuilt
  // from its own rows (EV + launch angle numerator)
  function seasonXw(p) {
    const m = p.m;
    if (m.xwoba_dir !== undefined) return m.xwoba;
    if (m.xwoba_sav != null) return m.xwoba_sav;
    let xn = 0, xd = 0; const f = DF.H, xi = f.indexOf("xnum"), di = f.indexOf("xden");
    for (const r of DS.rows(p)) { xn += r[xi]; xd += r[di]; }
    return xd ? Math.round(1000 * xn / xd) / 1000 : m.xwoba;
  }
  function seasonHitterM(p) {
    const m = p.m;
    if (m._full) return m;
    // Air% is every ball in play that isn't a ground ball (fly balls, line drives and popups); Center% closes the spray split
    const out = Object.assign({}, m, {
      xwoba: seasonXw(p),
      zmo: m.zmo !== undefined ? m.zmo : m.zsw == null || m.osw == null ? null : Math.round(10 * (m.zsw - m.osw)) / 10,
      con: m.con !== undefined ? m.con : m.whf == null ? null : Math.round(10 * (100 - m.whf)) / 10,
      air: m.gb != null ? Math.round(10 * (100 - m.gb)) / 10 : m.air,
      cent: m.cent !== undefined ? m.cent : m.pullp != null && m.oppo != null ? Math.round(10 * (100 - m.pullp - m.oppo)) / 10 : null,
      oppo: m.oppo !== undefined ? m.oppo : null,
      npull: m.pullp != null ? Math.round(10 * (100 - m.pullp)) / 10 : null,
      _full: true,
    });
    p.m = out;                                                    // computed once per player
    return out;
  }
  function withFB(m) {   // FB% = Air% − LD% − Popup% when a file predates the field
    if (m.fb !== undefined || m.air == null || m.ld == null) return m;
    return Object.assign({}, m, { fb: Math.round(10 * (m.air - m.ld - (m.pu || 0))) / 10 });
  }
  const rate = (a, b, dec = 1) => (b > 0 ? Math.round((100 * a / b) * 10 ** dec) / 10 ** dec : null);
  const valCache = new Map();
  // a player's numbers for the active window: metric values, sample (AB or IP), context stats
  function V(p) {
    const key = viewKey() + ":" + p.type + p.id;
    if (valCache.has(key)) return valCache.get(key);
    let v;
    const w = winIdx() || { lo: 0, hi: seasonDays().length - 1 };
    if (!needsRows() || !daysReady()) {
      v = p.type === "P"
        ? { m: p.m, sample: p.ip, ip: p.ip, bf: p.bf, g: p.ctx.G, gs: p.ctx.GS, ctx: p.ctx }
        : { m: withFB(seasonHitterM(p)), sample: p.pa, ab: p.ab, pa: p.pa, ctx: p.ctx };
    } else {
      const f = DF[p.type], t = {}; f.forEach((k) => (t[k] = 0));
      const hand = SPLIT.hand === "all" ? -1 : SPLIT.hand === "R" ? 1 : 0;
      const home = SPLIT.venue === "all" ? -1 : SPLIT.venue === "home" ? 1 : 0;
      const dayset = new Set(), gsset = new Set(), evs = [];
      const ei = f.indexOf("evs");
      let hasEvs = false, lo = w.lo;
      if (w.last) {   // trailing window: the fewest most-recent game days that reach N PA (hitters) / N IP (pitchers)
        const si = f.indexOf(p.type === "P" ? "outs" : "pa"), need = p.type === "P" ? 3 * w.last : w.last, byDay = new Map();
        for (const row of rowsOf(p)) { if (row[0] > w.hi || (hand >= 0 && row[1] !== hand) || (home >= 0 && row[2] !== home)) continue; byDay.set(row[0], (byDay.get(row[0]) || 0) + row[si]); }
        let acc = 0; lo = w.hi + 1;
        for (const d of [...byDay.keys()].sort((x, y) => y - x)) { acc += byDay.get(d); lo = d; if (acc >= need) break; }
      }
      for (const row of rowsOf(p)) {
        if (row[0] < lo || row[0] > w.hi || (hand >= 0 && row[1] !== hand) || (home >= 0 && row[2] !== home)) continue;
        dayset.add(row[0]);
        f.forEach((k, i) => { if (i >= 3 && k !== "gs" && k !== "evs" && row[i] !== undefined) t[k] += row[i]; });   // older files lack trailing fields
        if (p.type === "P" && row[f.indexOf("gs")]) gsset.add(row[0]);
        if (ei >= 0 && Array.isArray(row[ei])) { hasEvs = true; for (const e of row[ei]) evs.push(e); }
      }
      evs.sort((x, y) => x - y);
      const q90 = hasEvs && evs.length ? (() => { const pos = 0.9 * (evs.length - 1), lo = Math.floor(pos); return Math.round(10 * (evs[lo] + (evs[Math.min(lo + 1, evs.length - 1)] - evs[lo]) * (pos - lo))) / 10; })() : null;
      const games = DS.hist ? (p.ctx.G ?? null) : dayset.size;
      if (p.type === "P") {
        const ip = t.outs / 3, gs = DS.hist ? p.ctx.GS : gsset.size;
        // earned runs come from the game logs (per game, so only when no handedness split)
        let er = null;
        const erLog = hand < 0 ? DS.er(p) : [];
        if (hand < 0 && (!DS.hist || erLog.length)) { er = 0; for (const [d, h, e] of erLog) if (d >= lo && d <= w.hi && (home < 0 || h === home)) er += e; }
        else if (DS.hist && hand < 0 && home < 0) er = p.ctx.ER ?? null;
        const r2 = (x) => (x == null ? null : Math.round(100 * x) / 100);
        const wi = f.indexOf("wbip"), c = K();
        const hasBB = !!(c.bbw && wi >= 0 && rowsOf(p).some((row) => row[wi] !== undefined));   // files built before the field lack it
        let nera = null, bbl = null;
        if (hasBB && t.wden) {
          const untyped = Math.max(0, t.bip - t.gb - t.ld - t.fbt - t.pu);
          const xnum = t.wnum - t.wbip + t.gb * c.bbw.gb + t.ld * c.bbw.ld + t.fbt * c.bbw.fb + t.pu * c.bbw.pu + untyped * c.bbw.ut;
          nera = r2(c.lgERA + (xnum / t.wden - c.lgwOBA) / c.wobaScale * c.pa9);
          bbl = { gb: [t.gb, t.gb ? Math.round(1000 * t.wgb / t.gb) / 1000 : null], ld: [t.ld, t.ld ? Math.round(1000 * t.wld / t.ld) / 1000 : null],
                  fb: [t.fbt, t.fbt ? Math.round(1000 * t.wfb / t.fbt) / 1000 : null], pu: [t.pu, t.pu ? Math.round(1000 * t.wpu / t.pu) / 1000 : null] };
        }
        v = { m: { whf: rate(t.whf, t.sw), swstr: rate(t.whf, t.pit), strk: rate(t.strk, t.pit), gb: rate(t.gb, t.bip), pu: rate(t.pu, t.bip), nera,
                   k: rate(t.k, t.bf), bb: rate(t.bb, t.bf), kbb: t.bf ? Math.round(1000 * (t.k - t.bb) / t.bf) / 10 : null,
                   era: er == null || !ip ? null : r2(9 * er / ip),
                   fip: ip ? r2((13 * t.hr + 3 * (t.bb + t.hbp) - 2 * t.k) / ip + K().fipC) : null,
                   siera: r2(siera(t.k, t.bb, t.gb, t.fbt, t.pu, t.bf)),
                   csw: rate(t.cs + t.whf, t.pit), zcon: rate(t.zcon, t.zsw), zone: rate(t.zpit, t.pit), osw: rate(t.osw, t.opit), swing: rate(t.sw, t.pit),
                   fbv: t.fbn ? Math.round(10 * t.fbv / t.fbn) / 10 : null, ext: t.extn ? Math.round(10 * t.exts / t.extn) / 10 : null,
                   ev: (t.evn || t.bbe) ? Math.round(10 * t.evsum / (t.evn || t.bbe)) / 10 : null, hh: rate(t.hh, t.bip || t.bbe), brl: rate(t.brl, t.bip || t.bbe) },
              sample: ip, ip, bf: t.bf, g: games, gs,
              ctx: { G: games, GS: gs, wOBA: t.wden ? Math.round(1000 * t.wnum / t.wden) / 1000 : null, Pitches: t.pit, bbl, PAw: t.wden, HBP: t.hbp } };
      } else {
        const bden = t.bbt || t.bbe;                      // batted-ball type / direction: every typed ball in play (older files: tracked BBE)
        const noEV = DS.tracked != null && DS.tracked < 0.05;
        const evn = t.evn || t.bbe, bipn = t.bip || t.bbe;   // EV-eligible balls (no bunts) and all balls in play; older files carry tracked BBE only
        v = { m: { ev: evn ? Math.round(10 * t.evsum / evn) / 10 : null, brl: rate(t.brl, bipn), pull: rate(t.pullair, bden), air: rate(bden - (t.gbh || 0), bden),
                   oppo: t.oppn === undefined ? null : rate(t.oppn, bden), cent: t.oppn === undefined ? null : rate(bden - (t.pulln || 0) - (t.oppn || 0), bden),
                   npull: rate(bden - (t.pulln || 0), bden),
                   ba: t.h === undefined || !t.ab ? null : Math.round(1000 * t.h / t.ab) / 1000, slg: t.tb === undefined || !t.ab ? null : Math.round(1000 * t.tb / t.ab) / 1000,
                   xba: t.xbsum === undefined || !t.ab ? null : Math.round(1000 * t.xbsum / t.ab) / 1000, xslg: t.xssum === undefined || !t.ab ? null : Math.round(1000 * t.xssum / t.ab) / 1000,
                   osw: rate(t.osw, t.opit), zsw: rate(t.zsw, t.zpit), zcon: rate(t.zcon, t.zsw), ocon: rate(t.ocon, t.osw), whf: rate(t.whf, t.sw),
                   xwoba: t.xden && !noEV ? Math.round(1000 * t.xnum / t.xden) / 1000 : null,      // xwOBA: exit velocity + launch angle
                   woba: t.wden ? Math.round(1000 * t.wnum / t.wden) / 1000 : null,
                   bs: t.bsn ? Math.round(10 * t.bssum / t.bsn) / 10 : null,
                   zmo: t.zpit && t.opit ? Math.round(10 * (100 * t.zsw / t.zpit - 100 * t.osw / t.opit)) / 10 : null,
                   con: t.sw ? Math.round(10 * (100 - 100 * t.whf / t.sw)) / 10 : null,
                   pullp: rate(t.pulln, bden), ld: rate(t.ld, bden), gb: rate(t.gbh, bden), pu: rate(t.puh, bden),
                   fb: rate((DS.airNoPU ? t.air : t.air - (t.puh || 0)) - t.ld, bden),
                   ev90: q90, maxev: hasEvs && evs.length ? evs[evs.length - 1] : null,
                   hh: rate(t.hh, bipn), ss: rate(t.ss, bipn), strk: rate(t.strk, t.pit), swing: rate(t.sw, t.pit), k: rate(t.k, t.pa), bb: rate(t.bb, t.pa) },
              sample: t.pa, ab: t.ab, pa: t.pa,
              ctx: { wOBA: t.wden ? Math.round(1000 * t.wnum / t.wden) / 1000 : null, "K%": rate(t.k, t.pa), "BB%": rate(t.bb, t.pa), BBE: bipn, BIP: t.bbt || null, G: games } };
      }
    }
    valCache.set(key, v);
    return v;
  }

  /* ---------- groups & pools ---------- */
  // group = which pool the tab ranks within: H (all hitters), SP, RP, or P (all pitchers)
  const groupFor = (pos) => (pos === "ALLP" ? "P" : PIT_TABS.includes(pos) ? pos : "H");
  const isPitcherGroup = (g) => g !== "H";
  const metricsFor = (g) => (isPitcherGroup(g) ? DATA.meta.pitcherMetrics : DATA.meta.hitterMetrics);
  const TREND_P = ["whf", "strk", "k", "bb", "era", "nera", "uera", "siera", "gb"];
  // every card metric in card order, fold-outs right after their parent (the Leaderboard's column order)
  const lbOrder = (g) => { const pit = isPitcherGroup(g), seen = new Set(), out = []; for (const grp of (pit ? CARD_P : CARD)) for (const m of grp.metrics) for (const x of [m, ...((pit ? SUB_P : SUB)[m.key] || [])]) if (!seen.has(x.key)) { seen.add(x.key); out.push(x); } return out; };
  // Year and Age: plain columns that always sit right after the name (no percentile)
  const PRE_COLS = { year: { key: "year", label: "Year" }, age: { key: "age", label: "Age" } };
  const preCols = () => { const pre = state.pre || {}; const out = []; if (pre.year === true || (pre.year !== false && DS.each)) out.push(PRE_COLS.year); if (pre.age) out.push(PRE_COLS.age); return out; };
  const seasonOf = (p) => p.season ?? (p.seasons ? p.seasons[p.seasons.length - 1] : DS.season);
  const preValue = (k, p) => (k === "age" ? (p.age ?? "–") : p.season != null ? String(p.season) : p.seasons ? yearSpan(p.seasons) : String(DS.season));
  const lbCols = (g) => { const all = lbOrder(g); return state.lb[isPitcherGroup(g) ? "P" : "H"].map((k) => all.find((m) => m.key === k)).filter(Boolean).map((m) => Object.assign({}, m, { showValue: true })); };
  // the stats shown as columns on each list page: the Leaderboard's set (state.lb), or a page's own chosen set, else the page's defaults
  const defaultColKeys = (mode, g) => (mode === "trending" && isPitcherGroup(g) ? TREND_P.slice() : metricsFor(g).map((m) => m.key));
  const colKeys = (g) => { const k = isPitcherGroup(g) ? "P" : "H"; if (state.mode === "leaderboard") return state.lb[k]; const own = state.cols[state.mode]; return own && own[k] ? own[k] : defaultColKeys(state.mode, g); };
  const setColKeys = (g, keys) => { const k = isPitcherGroup(g) ? "P" : "H"; const known = new Set(lbOrder(g).map((m) => m.key)); const ordered = [...new Set(keys)].filter((x) => known.has(x)); if (state.mode === "leaderboard") state.lb[k] = ordered; else { state.cols[state.mode] = state.cols[state.mode] || {}; state.cols[state.mode][k] = ordered; } savePrefs(); };
  const brkKey = (g) => `${state.mode}:${isPitcherGroup(g) ? "P" : "H"}`;
  const hasBreak = (g, key) => ((state.tbl.breaks || {})[brkKey(g)] || []).includes(key);
  const toggleBreak = (g, key) => { const b = state.tbl.breaks = state.tbl.breaks || {}; const cur = b[brkKey(g)] || []; b[brkKey(g)] = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]; savePrefs(); };
  const moveColKey = (g, key, dir) => { const keys = colKeys(g).slice(), i = keys.indexOf(key), j = i + dir; if (i < 0 || j < 0 || j >= keys.length) return; [keys[i], keys[j]] = [keys[j], keys[i]]; setColKeys(g, keys); };
  const colsFor = (g) => {
    if (state.mode === "leaderboard") return lbCols(g);
    const keys = colKeys(g), all = allFor(g), dflt = metricsFor(g);
    return keys.map((k) => dflt.find((m) => m.key === k) || all.find((m) => m.key === k)).filter(Boolean);
  };
  const sample = (p) => V(p).sample;   // PA for hitters, IP for pitchers
  const addedPos = (p) => (DS.hist ? [] : state.extraPos[p.id] || []);
  const hasExtra = (p, g) => addedPos(p).includes(g);
  function addPos(p, pos) {
    const l = state.extraPos[p.id] || (state.extraPos[p.id] = []);
    if (!l.includes(pos)) { l.push(pos); save(LS.extraPos, state.extraPos); poolsChanged(); }
  }
  function removePos(id, pos) {
    const l = (state.extraPos[id] || []).filter((x) => x !== pos);
    if (l.length) state.extraPos[id] = l; else delete state.extraPos[id];
    save(LS.extraPos, state.extraPos); poolsChanged();
  }
  function inGroup(p, g) {
    if (g === "H") return p.type === "H";
    if (g === "P") return p.type === "P";
    return p.type === "P" && pitcherRoles(p).includes(g);
  }
  function poolsChanged() { poolVersion++; poolCache.clear(); rankCache.clear(); }

  // pandas-style average-rank percentile: 100 * rank / n, ties share their mean rank; null stays null
  function percentiles(vals) {
    const idx = vals.map((v, i) => [v, i]).filter(([v]) => v != null && !Number.isNaN(v)).sort((a, b) => a[0] - b[0]);
    const n = idx.length, out = new Array(vals.length).fill(null);
    for (let i = 0; i < n;) {
      let j = i; while (j + 1 < n && idx[j + 1][0] === idx[i][0]) j++;
      const pct = Math.round(100 * ((i + 1 + j + 1) / 2) / n);
      for (let k = i; k <= j; k++) out[idx[k][1]] = pct;
      i = j + 1;
    }
    return out;
  }
  // u(K-BB%): the K% his whiff rate implies minus the BB% his Strike% percentile implies
  const quantile = (arr, p) => { if (!arr || !arr.length) return null; const pos = (p / 100) * (arr.length - 1), lo = Math.floor(pos); return arr[lo] + (arr[Math.min(lo + 1, arr.length - 1)] - arr[lo]) * (pos - lo); };
  // the K% his whiff rate implies and the BB% his Strike% percentile implies (as shares of PA), or null
  function impliedKBB(pv, pctS, sorted) {
    if (pv.m.whf == null || pctS == null || !sorted.bb) return null;
    const kp = pv.m.whf / 100;                                       // implied K%: his whiff rate, as is
    const bbp = -quantile(sorted.bb, pctS) / 100;                    // implied BB% (sorted.bb holds -BB%)
    if (kp == null || bbp == null || Number.isNaN(kp) || Number.isNaN(bbp)) return null;
    return { k: Math.round(1000 * kp) / 10, bb: Math.round(1000 * bbp) / 10 };
  }
  // underlying ERA: what his ERA looks like with strikeouts at his whiff rate, walks at the walk rate his strike rate implies,
  // and every ball in play worth the league's value for its type — with his air balls split into line drives and fly balls
  // at the population's ratio (his own ground-ball and pop-up shares stand). Luck-neutral ERA on top of process-implied K and BB.
  function underlyingERA(pv, pctS, sorted) {
    const c = K(), ctx = pv.ctx || {}, bbl = ctx.bbl;
    if (!c.bbw || c.wbb == null || !bbl || pctS == null || !ctx.PAw || !sorted.bb || pv.m.whf == null) return null;
    const kp = pv.m.whf / 100;                                       // expected K%: his whiff rate
    const bbp = -quantile(sorted.bb, pctS) / 100;                    // expected BB%: the walk rate at his Strike% percentile
    if (Number.isNaN(kp) || Number.isNaN(bbp)) return null;
    const pa = ctx.PAw, hbp = ctx.HBP || 0;
    const counts = ["gb", "ld", "fb", "pu"].map((t) => (bbl[t] || [0])[0]), tot = counts.reduce((a, n) => a + n, 0);
    if (!tot) return null;
    const share = { gb: counts[0] / tot, ld: counts[1] / tot, fb: counts[2] / tot, pu: counts[3] / tot };
    const air = share.ld + share.fb, la = sorted.ldAir != null ? sorted.ldAir : (air ? share.ld / air : 0);
    const norm = { gb: share.gb, pu: share.pu, ld: air * la, fb: air * (1 - la) };
    const perBip = ["gb", "ld", "fb", "pu"].reduce((a, t) => a + norm[t] * c.bbw[t], 0);
    const bip = Math.max(0, pa - kp * pa - bbp * pa - hbp);
    const xw = (bbp * pa * c.wbb + hbp * c.whbp + bip * perBip) / pa;
    return Math.round(100 * (c.lgERA + (xw - c.lgwOBA) / c.wobaScale * c.pa9)) / 100;
  }
  const poolCache = new Map();
  // returns { list: players in pool, stats: Map key -> {pct: {metric: pctl}, score, rank} }
  function pool(g) {
    const key = g + ":" + effMin(g) + ":" + refMin(g) + ":" + poolVersion + ":" + viewKey() + ":" + daysReady();
    if (poolCache.has(key)) return poolCache.get(key);
    const all = DS.players.filter((p) => inGroup(p, g));
    // qualification is by full-season PA / IP; inside a date range or split, only players who actually appeared count
    const active = (p) => !needsDays() || V(p).sample > 0;
    // the listing minimum is playing time inside the window when one is set (a date range's innings, not the season's)
    const smp = (p) => (needsDays() ? V(p).sample : seasonSample(p));
    const listed = all.filter((p) => (smp(p) >= effMin(g) || hasExtra(p, g)) && active(p));
    // reference population: every hitter with 300+ PA, or every pitcher with 300+ batters faced, whatever the tab
    const everyone = isPitcherGroup(g) ? DS.players.filter((p) => p.type === "P") : all;
    const list = everyone.filter((p) => refSample(p) >= refMin(g) && active(p));
    const ms = metricsFor(g);
    const pct = {};
    for (const m of allFor(g)) pct[m.key] = percentiles(list.map((p) => { const x = V(p).m[m.key]; return x == null ? null : m.hib ? x : -x; }));
    let score, scorePct, blend, zmoVals = [], rawBlend = [];
    if (g === "H") {
      const hk = DS.noStatcast ? "woba" : HEAD.key;            // no tracking at this level: wOBA carries the headline
      const xw = list.map((p) => V(p).m[hk]);
      if (!pct[hk]) pct[hk] = percentiles(xw);
      score = xw.map((x) => (x == null ? -1 : x));             // headline: the xwOBA value itself
      scorePct = pct[hk];
      zmoVals = list.map((p) => { const x = V(p).m; return x.zsw == null || x.osw == null ? null : x.zsw - x.osw; });
      pct.zmo = percentiles(zmoVals);
      const w = DATA.meta.hitterWeights, tot = Object.values(w).reduce((a, b) => a + b, 0);
      rawBlend = list.map((_, i) => Object.entries(w).reduce((s, [k, v]) => s + (pct[k][i] ?? 50) * v, 0) / tot);
      const ranked = percentiles(rawBlend);                    // Formula 1: the blend is re-ranked as a percentile
      blend = rawBlend.map((b, i) => ranked[i] + b / 1000);    // exact blend breaks ties among equal percentiles
    } else {
      const w = DATA.meta.pitcherWeights, tot = Object.values(w).reduce((a, b) => a + b, 0);
      score = list.map((_, i) => Object.entries(w).reduce((s, [k, v]) => s + (pct[k][i] ?? 50) * v, 0) / tot);
      scorePct = score.map((x) => Math.round(x));
    }
    const stats = new Map();
    list.forEach((p, i) => stats.set(p.type + p.id, { pct: Object.fromEntries(allFor(g).map((m) => [m.key, pct[m.key][i]])),
                                                       score: score[i], scorePct: scorePct[i], blend: blend ? blend[i] : null }));
    [...stats.entries()].sort((a, b) => b[1].score - a[1].score).forEach(([k, s], i) => { s.rank = i + 1; });
    // sorted oriented values + scores, so a player outside this pool can be placed in it
    const sorted = {};
    for (const m of allFor(g)) sorted[m.key] = list.map((p) => { const x = V(p).m[m.key]; return x == null ? null : m.hib ? x : -x; }).filter((v) => v != null).sort((a, b) => a - b);
    if (isPitcherGroup(g) && pct.whf && pct.strk) {                  // underlying ERA for the population, then its percentiles
      let ldN = 0, fbN = 0;
      for (const p of list) { const b = (V(p).ctx || {}).bbl; if (b) { ldN += (b.ld || [0])[0]; fbN += (b.fb || [0])[0]; } }
      sorted.ldAir = ldN + fbN ? ldN / (ldN + fbN) : null;             // the population's line-drive share of air balls
      list.forEach((p, i) => { const s = stats.get(p.type + p.id); s.ukbb = impliedKBB(V(p), pct.strk[i], sorted); s.ukb = s.ukbb ? Math.round(10 * (s.ukbb.k - s.ukbb.bb)) / 10 : null; s.uera = underlyingERA(V(p), pct.strk[i], sorted); });
      const ukbs = list.map((p) => stats.get(p.type + p.id).ukb), ukp = percentiles(ukbs);
      list.forEach((p, i) => { stats.get(p.type + p.id).pct.ukb = ukp[i]; });
      sorted.ukb = ukbs.filter((x) => x != null).sort((a, b) => a - b);
      const ues = list.map((p) => stats.get(p.type + p.id).uera), uep = percentiles(ues.map((x) => (x == null ? null : -x)));
      list.forEach((p, i) => { stats.get(p.type + p.id).pct.uera = uep[i]; });
      sorted.uera = ues.filter((x) => x != null).map((x) => -x).sort((a, b) => a - b);
    }
    const scores = score.slice().sort((a, b) => a - b);
    if (g === "H") { sorted.zmo = zmoVals.filter((v) => v != null).sort((a, b) => a - b); sorted.blend = rawBlend.slice().sort((a, b) => a - b); }
    // the tail: everyone else in the group (under the tab's minimum) — the Rankings list appends them at the bottom,
    // most playing time first, so they can be ranked and tiered without their small samples moving anyone else
    const listedSet = new Set(listed), tail = all.filter((p) => !listedSet.has(p) && active(p)).sort((x, y) => smp(y) - smp(x));
    const res = { list: listed, tail, ref: list, stats, sorted, scores };
    for (const p of listed) if (!stats.has(p.type + p.id)) stats.set(p.type + p.id, placeIn(res, g, p));   // listed but under the reference minimum
    for (const p of tail) stats.set(p.type + p.id, placeIn(res, g, p));
    poolCache.set(key, res);
    return res;
  }
  // where player p would land if inserted into pool pl (percentiles, score, blend, rank)
  function placeIn(pl, g, p) {
    const pct = {};
    const pm = V(p).m;
    for (const m of allFor(g)) pct[m.key] = pm[m.key] == null ? null : insertPct(pl.sorted[m.key], m.hib ? pm[m.key] : -pm[m.key]);
    if (g === "H") {
      const hk = DS.noStatcast ? "woba" : HEAD.key;
      const score = pm[hk] ?? -1;
      pct.zmo = pm.zsw == null || pm.osw == null ? null : insertPct(pl.sorted.zmo, pm.zsw - pm.osw);
      const w = DATA.meta.hitterWeights, tot = Object.values(w).reduce((a, b) => a + b, 0);
      const raw = Object.entries(w).reduce((s, [k, v]) => s + (pct[k] ?? 50) * v, 0) / tot;
      let above = 0; for (const s of pl.scores) if (s > score) above++;
      return { pct, score, scorePct: pct[hk], blend: DS.noStatcast ? null : insertPct(pl.sorted.blend, raw) + raw / 1000, rank: above + 1, outside: true };
    }
    const w = DATA.meta.pitcherWeights, tot = Object.values(w).reduce((a, b) => a + b, 0);
    const score = Object.entries(w).reduce((s, [k, v]) => s + (pct[k] ?? 50) * v, 0) / tot;
    let above = 0; for (const s of pl.scores) if (s > score) above++;
    const ukbb = pl.sorted.ukb ? impliedKBB(V(p), pct.strk, pl.sorted) : null;
    const ukb = ukbb ? Math.round(10 * (ukbb.k - ukbb.bb)) / 10 : null;
    pct.ukb = ukb == null || !pl.sorted.ukb ? null : insertPct(pl.sorted.ukb, ukb);
    const uera = pl.sorted.uera ? underlyingERA(V(p), pct.strk, pl.sorted) : null;
    pct.uera = uera == null || !pl.sorted.uera ? null : insertPct(pl.sorted.uera, -uera);
    return { pct, score, scorePct: Math.round(score), rank: above + 1, outside: true, ukbb, ukb, uera };
  }

  // percentile of x if it were inserted into the sorted ascending array (ties share the mean rank)
  function insertPct(arr, x) {
    let lo = 0, hi = arr.length;                      // first index >= x
    while (lo < hi) { const mid = (lo + hi) >> 1; if (arr[mid] < x) lo = mid + 1; else hi = mid; }
    let lo2 = lo, hi2 = arr.length;                   // first index > x
    while (lo2 < hi2) { const mid = (lo2 + hi2) >> 1; if (arr[mid] <= x) lo2 = mid + 1; else hi2 = mid; }
    const below = lo, equal = lo2 - lo;
    return Math.round(100 * (below + 1 + equal / 2) / (arr.length + 1));
  }
  const rankCache = new Map();
  // percentiles, score and rank for pitcher p measured against pool g (SP, RP or P)
  function rankIn(g, p) {
    const key = g + ":" + effMin(g) + ":" + refMin(g) + ":" + poolVersion + ":" + viewKey() + ":" + daysReady() + ":" + p.type + p.id;
    if (rankCache.has(key)) return rankCache.get(key);
    const pl = pool(g);
    const res = pl.stats.get(p.type + p.id) || placeIn(pl, g, p);
    rankCache.set(key, res);
    return res;
  }
  // the pool a pitcher tab's numbers are measured against: its own, or the "Rank vs" choice
  const refFor = (g) => g;                                  // percentiles always come from the type's own 300+ population
  const POOL_NAME = { H: "all hitters", P: "all pitchers", SP: "starters", RP: "relievers" };
  const LEVELS = { mlb: "MLB", aaa: "AAA", aa: "AA", ap: "A+", a: "A" }, LEVEL_ORDER = ["mlb", "aaa", "aa", "ap", "a"];
  const LEVEL_NAMES = { mlb: "MLB", aaa: "Triple-A", aa: "Double-A", ap: "High-A", a: "Single-A" };
  const levelOf = (key) => key.split("-")[0];
  const keyLevel = (key) => (key.startsWith("mlb-") ? "" : LEVELS[levelOf(key)] || levelOf(key).toUpperCase());   // "" for MLB, "AAA" …
  // game type of a dataset key: "" regular season, "spring", "post"  (mlb-2026 · mlb-2026-spring · mlb-2025-post)
  const KINDS = [["", "Regular season"], ["spring", "Spring training"], ["post", "Postseason"]];
  const KIND_SHORT = { "": "", spring: "Spring", post: "Postseason" };
  const keyKind = (key) => { const parts = key.split("-"); return parts.length > 2 && (parts[2] === "spring" || parts[2] === "post") ? parts[2] : ""; };
  const keyBase = (key) => key.split("-").slice(0, 2).join("-");                       // the year-level key without the game type
  const kindTag = (key) => (KIND_SHORT[keyKind(key)] ? " " + KIND_SHORT[keyKind(key)] : "");
  // a select drawn as a pill (the native chevron collides with text in Safari, so the real select sits invisibly on top)
  function pillSelect(text, options, value, onChange, aria) {
    const pill = el("label", "pill");
    pill.append(el("span", "pill-text", text));
    pill.insertAdjacentHTML("beforeend", '<svg class="chev" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>');
    const sel = el("select"); sel.setAttribute("aria-label", aria);
    for (const [v, l] of options) { const o = el("option", null, l); o.value = v; sel.append(o); }
    sel.value = value; sel.addEventListener("click", (e) => e.stopPropagation()); sel.addEventListener("change", (e) => onChange(e.target.value));
    pill.append(sel); return pill;
  }
  // Year + Level pickers for one player's seasons (index rows [key, season, type, role, sample, team] of one type)
  function renderSeasonPicker(seasons, curKey, onPick, compact) {
    const box = el("div", "spick");
    const cur = seasons.find((sv) => sv[0] === curKey) || seasons[0]; if (!cur) return box;
    const years = [...new Set(seasons.map((sv) => sv[1]))].sort((x, y) => y - x);
    const inYear = (y) => seasons.filter((sv) => sv[1] === y).sort((p, q) => LEVEL_ORDER.indexOf(levelOf(p[0])) - LEVEL_ORDER.indexOf(levelOf(q[0])));
    const sampleTxt = (sv) => (compact ? sv[5] : `${sv[2] === "H" ? sv[4] + " PA" : fmtIP(sv[4]) + " IP"} · ${sv[5]}`);
    box.append(pillSelect(String(cur[1]), years.map((y) => [String(y), String(y)]), String(cur[1]), (y) => {
      const opts = inYear(Number(y)); const same = opts.find((sv) => levelOf(sv[0]) === levelOf(cur[0])) || opts[0]; onPick(same[0]);
    }, "Season"));
    const lv = inYear(cur[1]).filter((sv) => keyKind(sv[0]) === keyKind(cur[0]) || keyBase(sv[0]) !== keyBase(cur[0]) && !keyKind(sv[0]));
    const lvl = (k) => `${LEVELS[levelOf(k)] || levelOf(k)}${kindTag(k)}`;
    const lvPill = pillSelect(`${lvl(cur[0])} · ${sampleTxt(cur)}`, lv.map((sv) => [sv[0], `${lvl(sv[0])} · ${sampleTxt(sv)}`]), cur[0], (k) => onPick(k), "Level");
    lvPill.classList.add("lvl"); if (lv.length === 1) lvPill.classList.add("solo");
    box.append(lvPill);
    // regular season / spring training / postseason, where this year and level has them
    const kinds = seasons.filter((sv) => keyBase(sv[0]) === keyBase(cur[0]));
    if (kinds.length > 1) {
      const seg = el("div", "seg kindseg"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Games");
      for (const [k, l] of KINDS) {
        const sv = kinds.find((x) => keyKind(x[0]) === k); if (!sv) continue;
        const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(sv[0] === cur[0]));
        b.addEventListener("click", (e) => { e.stopPropagation(); if (sv[0] !== cur[0]) onPick(sv[0]); });
        seg.append(b);
      }
      box.append(seg);
    }
    return box;
  }
  const seasonTag = (sv) => `${sv[1]}${keyLevel(sv[0]) ? " " + keyLevel(sv[0]) : ""}${kindTag(sv[0])}`;   // index entry -> "2026 AAA", "2025 Postseason"
  const dsSeason = () => `${DS.season}${DS.level !== "MLB" ? " " + DS.level : ""}${DS.kind ? " " + KIND_SHORT[DS.kind] : ""}`;
  // "vs all hitters with 300+ PA this season" / "vs Triple-A hitters with 280+ PA that season"
  const poolPhrase = (ref) => `vs ${DS.level === "MLB" ? "all" : DS.levelName} ${isPitcherGroup(ref) ? "pitchers" : "hitters"} with ${refMin(ref)}+ ${isPitcherGroup(ref) ? "BF" : "PA"} ${DS.hist ? "that season" : "this season"}`;

  /* ---------- color: diverging blue(0) → neutral(50) → red(100), mixed in OKLab ---------- */
  const tokens = {};
  function readTokens() {
    const cs = getComputedStyle(document.documentElement);
    for (const k of ["lo", "mid", "hi"]) tokens[k] = hexToRgb(cs.getPropertyValue("--" + k).trim());
  }
  function hexToRgb(h) { h = h.replace("#", ""); if (h.length === 3) h = h.split("").map((c) => c + c).join(""); const n = parseInt(h, 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const gam = (c) => { c = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055; return Math.max(0, Math.min(255, Math.round(c * 255))); };
  function rgbToOklab([r, g, b]) {
    r = lin(r); g = lin(g); b = lin(b);
    const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
    const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
    const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
    return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
  }
  function oklabToRgb([L, a, b]) {
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3, s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
    return [gam(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s), gam(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s), gam(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s)];
  }
  function mix(c1, c2, t) { const a = rgbToOklab(c1), b = rgbToOklab(c2); return oklabToRgb([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]); }
  const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const contrast = (a, b) => { const la = lum(a) + 0.05, lb = lum(b) + 0.05; return la > lb ? la / lb : lb / la; };
  const colorCache = new Map();
  function pctStyle(p) {
    if (p == null) return null;
    if (colorCache.has(p)) return colorCache.get(p);
    const t = (p - 50) / 50;
    const fill = t >= 0 ? mix(tokens.mid, tokens.hi, t) : mix(tokens.mid, tokens.lo, -t);
    const white = [255, 255, 255], dark = [21, 24, 26];
    const ink = contrast(fill, dark) >= contrast(fill, white) ? dark : white;
    const s = { bg: `rgb(${fill.join(",")})`, fg: `rgb(${ink.join(",")})` };
    colorCache.set(p, s);
    return s;
  }
  function paint(node, pct) { const s = pctStyle(pct); if (s) { node.style.background = s.bg; node.style.color = s.fg; } }

  /* ---------- formatting ---------- */
  function fmt(v, m) { return m.dec === 3 ? fmtX(v) : m.dec === 2 ? v.toFixed(2) : m.unit === "%" ? v.toFixed(1) + "%" : v.toFixed(1) + (m.unit ? " " + m.unit : ""); }
  const fmtX = (x) => (x == null || x < 0 ? "–" : x.toFixed(3).replace(/^0/, ""));
  function fmtIP(ip) { const w = Math.floor(ip + 1e-6), t = Math.round((ip - w) * 3); return t === 3 ? `${w + 1}.0` : `${w}.${t}`; }
  function ordinal(n) { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  const sampleLabel = (g) => (isPitcherGroup(g) ? "IP" : "PA");

  /* ---------- filtering ---------- */
  // Eligibility for the coming season: hitters 20+ games at a position last season (OF combined, DH included);
  // pitchers SP with 25+ innings as a starter, RP with 25+ innings in relief (both possible); plus any position
  // you add from a player's card. Stats shown are always the full season.
  const ESPN = { posGames: 20, spIP: 25, rpIP: 25 };
  function pitcherRoles(p) {
    const r = [];
    if (p.ctx.IPs != null) { if (p.ctx.IPs >= ESPN.spIP) r.push("SP"); if (p.ctx.IPr >= ESPN.rpIP) r.push("RP"); }
    if (!r.length) r.push(p.primary);
    for (const x of addedPos(p)) if ((x === "SP" || x === "RP") && !r.includes(x)) r.push(x);
    return r;
  }
  // "2B, 3B, OF" — with the tab you're on listed first
  function posLabel(p) {
    const list = eligiblePositions(p).slice();
    const i = list.indexOf(state.pos);
    if (i > 0) list.splice(0, 0, list.splice(i, 1)[0]);
    return list.join(", ");
  }
  function eligiblePositions(p) {
    if (p.type === "P") return pitcherRoles(p);
    const order = HIT_TABS.slice(1);
    // games at a position this season: MLB plus the minors (ESPN grants eligibility for positions a call-up played down there)
    const games = Object.assign({}, p.pos);
    for (const [k, g] of Object.entries(p.milb || {})) games[k] = (games[k] || 0) + g;
    const out = Object.entries(games).filter(([k, g]) => g >= ESPN.posGames && order.includes(k)).map(([k]) => k);
    if (!out.length) out.push(HIT_TABS.includes(p.primary) ? p.primary : "DH");
    for (const x of addedPos(p)) if (order.includes(x) && !out.includes(x)) out.push(x);
    return out.sort((x, y) => order.indexOf(x) - order.indexOf(y));
  }
  function inPos(p, pos) {
    if (pos === "ALL" || pos === "ALLP" || PIT_TABS.includes(pos)) return true;   // group already narrowed
    return eligiblePositions(p).includes(pos);
  }
  function visiblePlayers(opts = {}) {
    const g = groupFor(state.pos);
    const { list } = pool(g);
    const ref = refFor(g);
    const q = opts.all ? "" : state.q.trim().toLowerCase();
    const drafted = draftedIds();
    const hideDrafted = !opts.all && state.mode === "draft" && !state.showDrafted;
    const src = orderSource(), trending = state.mode === "trending";
    let out = (trending ? list.concat(pool(g).tail) : list).filter((p) => inPos(p, state.pos));   // Trending: full-season minimums don't apply
    if (trending) out = out.filter((p) => sample(p) >= trendMin(g));
    let starF = null;
    if (state.starOnly && (state.mode === "rankings" || state.mode === "draft") && !opts.all) { const stars = listStars(); starF = (p) => !!stars[p.type + p.id]; out = out.filter(starF); }
    let tail = src ? pool(g).tail.filter((p) => inPos(p, state.pos)) : [];   // Rankings / Draft-from-rankings: the under-minimum players, at the bottom
    if (starF) tail = tail.filter(starF);
    const match = (p) => p.name.toLowerCase().includes(q) || p.team.toLowerCase() === q;
    if (q) { out = out.filter(match); tail = tail.filter(match); }
    if (state.teamF && !opts.all) { out = out.filter(teamOK); tail = tail.filter(teamOK); }
    if (hideDrafted) { out = out.filter((p) => !drafted.has(p.id)); tail = tail.filter((p) => !drafted.has(p.id)); }
    const key = state.sort, dir = state.dir === "asc" ? 1 : -1;
    const stats = new Map(out.concat(tail).map((p) => [p.type + p.id, ref === g ? pool(g).stats.get(p.type + p.id) : rankIn(ref, p)]));   // pool() places every listed player
    const st = (p) => stats.get(p.type + p.id);
    const val = (p) => {
      if (key === "score") return st(p).score;
      if (key === "blend") return st(p).blend;
      if (key === "name") return p.name;
      if (key === "sample") return sample(p);
      if (key === "age") return p.age ?? 0;
      if (key === "year") return Number(seasonOf(p)) || 0;
      if (key === "ukb") return st(p).ukb;
      if (key === "uera") { const u = st(p).uera; return u == null ? null : -u; }
      const mm = sortMetric, v = V(p).m[key];
      if (mm && v != null) return mm.hib === false ? -v : v;       // oriented so "desc" is always best first
      return st(p).pct[key];
    };
    const sortMetric = allFor(g).find((m) => m.key === key);
    out.sort((a, b) => {
      const va = val(a), vb = val(b);
      if (va == null && vb == null) return 0; if (va == null) return 1; if (vb == null) return -1;
      if (typeof va === "string") return va.localeCompare(vb) * dir;
      return (va - vb) * dir || st(b).score - st(a).score;
    });
    out = out.concat(tail);
    // manual rankings: the saved order for this tab first, then anyone not yet ranked in big-board order
    const order = src ? src.ranks[state.pos] : null;
    if (order && order.length) {
      const idx = new Map(order.map((k, i) => [k, i]));
      out = out.map((p, i) => [p, idx.has(p.type + p.id) ? idx.get(p.type + p.id) : order.length + i]).sort((a, b) => a[1] - b[1]).map((x) => x[0]);
    }
    return { list: out, stats, g, ref, manual: !!(order && order.length) };
  }
  // drag & drop on the Rankings list: one listener on the list, the indicator moves only when the target changes
  let dragKey = null, dropMark = null;
  function clearDropMark() { if (dropMark) { dropMark.el.classList.remove("dragover", "dragover-below"); dropMark = null; } }
  function dropTarget(e) {
    const li = e.target.closest && e.target.closest("#rows > li");
    if (!li) return null;
    if (li.classList.contains("tierhead") || li.classList.contains("tierdrop")) return { el: li, head: true };
    const r = li.getBoundingClientRect();
    return { el: li, below: e.clientY > r.top + r.height / 2 };
  }
  $("rows").addEventListener("dragover", (e) => {
    if (state.mode !== "rankings" || !state.editRanks || !dragKey) return;
    e.preventDefault(); e.dataTransfer.dropEffect = "move";
    const t = dropTarget(e); if (!t) { clearDropMark(); return; }
    if (dropMark && dropMark.el === t.el && dropMark.below === t.below) return;
    clearDropMark(); dropMark = t;
    t.el.classList.add(t.head || !t.below ? "dragover" : "dragover-below");
  });
  $("rows").addEventListener("dragleave", (e) => { if (!$("rows").contains(e.relatedTarget)) clearDropMark(); });
  $("rows").addEventListener("drop", (e) => {
    if (state.mode !== "rankings" || !state.editRanks || !dragKey) return;
    e.preventDefault();
    const t = dropTarget(e); const k = dragKey; clearDropMark(); dragKey = null;
    if (!t) return;
    const tiers = tierLists(), idx = tierIndex(tiers), rest = fullOrder().filter((q) => q !== k);   // the order without him
    if (t.head) {                                          // tier header / empty-tier box: join that tier, at its top
      const tier = Number(t.el.dataset.tier);
      const first = rest.find((q) => (tier < tiers.length ? idx.get(q) === tier : !idx.has(q)));
      setTier([k], tier < tiers.length ? tier + 1 : 0, true);
      if (first) setRank(k, rest.indexOf(first) + 1, true);
      render(); return;
    }
    const key = t.el.dataset.key; if (!key || key === k) return;
    setRank(k, rest.indexOf(key) + (t.below ? 1 : 0) + 1, true);
    if (tiers.length && showTiers()) setTier([k], idx.has(key) ? idx.get(key) + 1 : 0, true);   // he lands in that player's tier
    render();
  });
  // edit-mode selection: plain click and cmd/ctrl-click toggle a row, shift-click selects the range from the last click
  function toggleSel(key, e) {
    const order = [...document.querySelectorAll("#rows .row")].map((li) => li.dataset.key);   // as displayed
    if (e && e.shiftKey && state.selAnchor && order.includes(state.selAnchor)) {
      const a = order.indexOf(state.selAnchor), b = order.indexOf(key);
      const range = order.slice(Math.min(a, b), Math.max(a, b) + 1);
      for (const k of range) if (!state.selKeys.includes(k)) state.selKeys.push(k);
    } else {
      const i = state.selKeys.indexOf(key);
      if (i >= 0) state.selKeys.splice(i, 1); else state.selKeys.push(key);
      state.selAnchor = key;
    }
    render();
  }
  // tiers: per tab, an array of member-key lists — [["H1", "H2"], ["H5"]]. A player is in at most one tier; everyone
  // else is "Not tiered". Membership is independent of rank: a tier shows its members in rank order with their ranks,
  // so tier 1 can hold ranks 1, 2, 3, 5 while rank 4 sits at the top of Not tiered.
  const tierLists = (tab = state.pos, src) => ((src || state).tiers[tab] || []).map((l) => l.slice());
  const tierIndex = (tiers) => { const m = new Map(); tiers.forEach((l, t) => l.forEach((k) => m.set(k, t))); return m; };
  const showTiers = () => state.tierView !== "list";
  function saveTiers(tiers) {
    if (tiers.length) state.tiers[state.pos] = tiers; else delete state.tiers[state.pos];
    save(LS.tiers, state.tiers); state.flash = "";
  }
  const fullOrder = () => visiblePlayers({ all: true }).list.map((p) => p.type + p.id);
  // the rank order for a tab: its saved order first, then everyone else in big-board order
  function fullOrderFor(tab, ranks) {
    const keep = { pos: state.pos, mode: state.mode };
    state.pos = tab; state.mode = "board";
    let board = []; try { board = fullOrder(); } catch {} finally { state.pos = keep.pos; state.mode = keep.mode; }
    const seen = new Set(ranks); return ranks.concat(board.filter((k) => !seen.has(k)));
  }
  // an empty tier at position t (0 = above tier 1, tiers.length = below the last tier); later tiers and names shift down
  function insertTier(t) {
    const tiers = tierLists(); t = Math.max(0, Math.min(tiers.length, t));
    tiers.splice(t, 0, []);
    const names = (state.tierNames[state.pos] || []).slice(); if (names.length > t) names.splice(t, 0, "");
    if (names.length) state.tierNames[state.pos] = names; save(LS.tierNames, state.tierNames);
    saveTiers(tiers); state.tierView = "tiers"; savePrefs(); render();
  }
  const addTier = () => insertTier(tierLists().length);
  // the bottom-most selected player as displayed (the "Add tier below…" anchor)
  const selBottom = () => { const s = new Set(state.selKeys); return [...document.querySelectorAll("#rows .row")].map((li) => li.dataset.key).filter((k) => s.has(k)).pop() || null; };
  // a tier boundary right below this player: everyone shown above him in his section, through him, becomes a tier
  function tierBelow(key) {
    const tiers = tierLists(), idx = tierIndex(tiers), full = fullOrder();
    const t = idx.has(key) ? idx.get(key) : tiers.length;
    const section = full.filter((k) => (t < tiers.length ? idx.get(k) === t : !idx.has(k)));
    const i = section.indexOf(key); if (i < 0) return;
    const names = (state.tierNames[state.pos] || []).slice();
    if (t < tiers.length) { tiers.splice(t, 1, section.slice(0, i + 1), section.slice(i + 1)); if (names.length > t + 1) names.splice(t + 1, 0, ""); }
    else tiers.push(section.slice(0, i + 1));
    if (names.length) state.tierNames[state.pos] = names; save(LS.tierNames, state.tierNames);
    saveTiers(tiers); state.tierView = "tiers"; savePrefs(); render();
  }
  // tier membership for one or more players: t = 1-based tier, 0 = Not tiered, "new" = a fresh tier holding them
  function setTier(keys, t, quiet) {
    const tiers = tierLists();
    for (const l of tiers) for (const k of keys) { const i = l.indexOf(k); if (i >= 0) l.splice(i, 1); }
    if (t === "new") { tiers.push([]); t = tiers.length; }
    if (t >= 1) { if (!tiers.length) tiers.push([]); tiers[Math.min(t, tiers.length) - 1].push(...keys); state.tierView = "tiers"; savePrefs(); }
    saveTiers(tiers); if (!quiet) render();
  }
  const moveToTier = (key, t, quiet) => setTier([key], t, quiet);
  const selectedInOrder = () => { const s = new Set(state.selKeys); return fullOrder().filter((k) => s.has(k)); };
  function moveSelectionToTier(t) { setTier(selectedInOrder(), t, true); state.selKeys = []; state.selAnchor = null; render(); }
  // remove tier t: its players go back to Not tiered (ranks untouched), later tiers shift up
  function removeTier(t) {
    const tiers = tierLists(); if (t < 0 || t >= tiers.length) return;
    tiers.splice(t, 1);
    const names = (state.tierNames[state.pos] || []).slice(); if (names.length > t) names.splice(t, 1);
    while (names.length && !names[names.length - 1]) names.pop();
    if (names.length) state.tierNames[state.pos] = names; else delete state.tierNames[state.pos]; save(LS.tierNames, state.tierNames);
    saveTiers(tiers); render();
  }
  function setTierName(t, name) {
    const l = (state.tierNames[state.pos] || []).slice();
    while (l.length <= t) l.push("");
    l[t] = name;
    while (l.length && !l[l.length - 1]) l.pop();
    if (l.length) state.tierNames[state.pos] = l; else delete state.tierNames[state.pos];
    save(LS.tierNames, state.tierNames); state.flash = ""; render();
  }
  // rank only: move a player to rank r (1-based) in this tab's order; his tier doesn't change
  function setRank(key, rank, quiet) {
    const full = fullOrder(); const from = full.indexOf(key); if (from < 0) return;
    full.splice(from, 1);
    full.splice(Math.max(0, Math.min(full.length, rank - 1)), 0, key);
    state.ranks[state.pos] = full; save(LS.ranks, state.ranks); state.flash = ""; if (!quiet) render();
  }
  // tiers were stored as sizes over the rank order ([5, 7]); convert to member lists once (needs the pools, so it
  // runs right before the first render). Also used for imported blocks from older copies of the site.
  const sizesToMembers = (ranks, tiers) => {
    const out = {};
    for (const [tab, v] of Object.entries(tiers || {})) {
      if (!Array.isArray(v) || !v.length) continue;
      if (typeof v[0] !== "number") { out[tab] = v; continue; }
      const full = fullOrderFor(tab, (ranks || {})[tab] || []); let acc = 0;
      out[tab] = v.map((n) => { const l = full.slice(acc, acc + n); acc += n; return l; });
    }
    return out;
  };
  function migrateTiersToMembers() {
    if (load("draft2027.tiersFmt", 1) >= 3) return;
    state.tiers = sizesToMembers(state.ranks, state.tiers);
    for (const s of Object.values(state.rankSets)) s.tiers = sizesToMembers(s.ranks, s.tiers);
    save(LS.tiers, state.tiers); save(LS.sets, state.rankSets); save("draft2027.tiersFmt", 3);
  }

  /* ---------- render ---------- */
  function renderTabs() {
    const box = $("postabs"); box.innerHTML = "";
    const drafted = draftedIds();
    const hide = state.mode === "draft" && !state.showDrafted;
    const withTail = manualOrder(), trending = state.mode === "trending";
    const count = (pos) => {
      const g = groupFor(pos);
      const n = () => { const pl = pool(g); return pl.list.concat(withTail || trending ? pl.tail : []).filter((p) => inPos(p, pos) && teamOK(p) && !(hide && drafted.has(p.id)) && (!trending || sample(p) >= trendMin(g))).length; };
      return trending ? withWindow(trendWin(g), n) : n();
    };
    const make = (pos) => {
      const b = el("button", "postab"); b.type = "button"; b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(pos === state.pos)); b.dataset.pos = pos;
      b.textContent = TAB_LABEL[pos] || pos; b.append(el("small", null, count(pos)));
      b.addEventListener("click", () => { state.pos = pos; state.expanded = null; ensureSortValid(); savePrefs(); render(); });
      return b;
    };
    HIT_TABS.forEach((p) => box.append(make(p)));
    box.append(el("span", "sep"));
    PIT_TABS.forEach((p) => box.append(make(p)));
  }
  function ensureSortValid() {
    const keys = new Set(allFor(groupFor(state.pos)).map((m) => m.key));
    if (state.sort === "blend" && isPitcherGroup(groupFor(state.pos))) state.sort = "score";
    if (!["score", "blend", "name", "sample", "age", "year"].includes(state.sort) && !keys.has(state.sort)) { state.sort = "score"; state.dir = "desc"; }
  }
  function renderSortSelect() {
    const g = groupFor(state.pos);
    const sel = $("sort"); sel.innerHTML = "";
    const opts = [["score", isPitcherGroup(g) ? "Score" : HEAD.label], ...(isPitcherGroup(g) ? [] : [["blend", "Skills blend pctl"]]),
                  ...(isPitcherGroup(g) ? ALL_P : ALL_H.filter((m) => m.key !== HEAD.key)).map((m) => [m.key, m.label + " pctl"]),
                  ["sample", isPitcherGroup(g) ? "Innings pitched" : "Plate appearances"], ...(preCols().some((c) => c.key === "year") ? [["year", "Year"]] : []), ["age", "Age"], ["name", "Name"]];
    for (const [v, l] of opts) { const o = el("option", null, l); o.value = v; sel.append(o); }
    sel.value = state.sort;
  }
  function renderRef() {
    const g = groupFor(state.pos);
    const box = $("reffield"); box.hidden = true;
    if (box.hidden) return;
    const sel = $("ref"); sel.innerHTML = "";
    for (const [v, l] of [["own", `Own pool (${POOL_NAME[g]})`], ["SP", "Starters"], ["RP", "Relievers"], ["P", "All pitchers"]]) {
      if (v === g) continue;                                   // "own" already means this
      const o = el("option", null, l); o.value = v; sel.append(o);
    }
    if (state.ref === g) state.ref = "own";
    sel.value = state.ref;
  }
  // the split bar at the top of an open card
  function renderSplitBar(p) {
    const bar = el("div", "splitbar");
    const pit = p.type === "P";
    {
      // folded by default: a button with what's in effect; open it to change splits and dates
      const head = el("div", "splithead");
      const b = el("button", "btn btn-quiet tbtn", "Splits & dates"); b.type = "button"; b.setAttribute("aria-expanded", String(state.cardTools));
      b.addEventListener("click", (e) => { e.stopPropagation(); state.cardTools = !state.cardTools; savePrefs(); render(); });
      const bits = [];
      if (state.split.hand !== "all") bits.push(`vs ${state.split.hand}H${pit ? "B" : "P"}`);
      if (state.split.venue !== "all") bits.push(state.split.venue);
      if (state.cardWin.from || state.cardWin.to || lastN(state.cardWin)) bits.push(withWindow(state.cardWin, () => winLabel(p.type)));
      b.classList.toggle("on", bits.length > 0);
      head.append(b, el("span", "tsum", bits.length ? bits.join(" · ") : "full season · all splits"));
      if (state.daysLoading) head.append(el("span", "winnote", "Loading game-by-game data…"));
      bar.append(head);
      if (!state.cardTools) return bar;
    }
    const seg = (name, opts, cur, set) => {
      const g = el("div", "seg"); g.setAttribute("role", "group"); g.setAttribute("aria-label", name);
      for (const [v, l] of opts) {
        const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(cur === v));
        b.addEventListener("click", (e) => { e.stopPropagation(); if (cur !== v) { set(v); render(); } });
        g.append(b);
      }
      return g;
    };
    bar.append(seg("Handedness", [["all", pit ? "All batters" : "All pitchers"], ["L", pit ? "vs LHB" : "vs LHP"], ["R", pit ? "vs RHB" : "vs RHP"]], state.split.hand, (v) => (state.split.hand = v)));
    bar.append(seg("Venue", [["all", "Home + away"], ["home", "Home"], ["away", "Away"]], state.split.venue, (v) => (state.split.venue = v)));
    if (state.mode !== "compare") bar.append(renderCardDates(p));
    if (state.daysLoading && state.mode === "compare") bar.append(el("span", "winnote", "Loading game-by-game data…"));
    if (state.split.hand !== "all" || state.split.venue !== "all") {
      const warn = el("span", "splitwarn");
      warn.append(`Showing ${[state.split.hand !== "all" ? "vs " + state.split.hand + "H" + (pit ? "B" : "P") : "", state.split.venue !== "all" ? state.split.venue : ""].filter(Boolean).join(" · ")} — not the full season. `);
      const r = el("button", "linkbtn", "Show all"); r.type = "button"; r.addEventListener("click", (e) => { e.stopPropagation(); state.split = { hand: "all", venue: "all" }; render(); });
      warn.append(r); bar.append(warn);
    }
    return bar;
  }
  // the card's own Dates control (presets + custom range); season-level past seasons have it disabled
  function renderCardDates(p) {
    const box = el("div", "datesbar");
    const can = !!DS.days;
    box.append(el("span", "to", "Dates"));
    for (const k of ["from", "to"]) {
      const i = el("input"); i.type = "date"; i.min = seasonFirst(); i.max = seasonLast(); i.value = state.cardWin[k] || "";
      i.setAttribute("aria-label", k); i.disabled = !can; i.title = can ? (k === "from" ? "Blank = season start" : "Blank = season end") : "Day-by-day data isn't built for this season";
      i.addEventListener("click", (e) => e.stopPropagation());
      i.addEventListener("change", (e) => { state.cardWin[k] = e.target.value; if (k === "from" && e.target.value) state.cardWin.last = ""; if (state.cardWin.from && state.cardWin.to && state.cardWin.from > state.cardWin.to) state.cardWin[k === "from" ? "to" : "from"] = e.target.value; render(); });
      if (k === "from" && lastN(state.cardWin)) { i.disabled = true; i.title = "Clear Last to use a start date"; }
      if (k === "to") box.append(el("span", "to", "to"));
      box.append(i);
    }
    // "Last N": his most recent N plate appearances (innings for a pitcher), optionally through the To date — its own row
    const unit = p.type === "P" ? "IP" : "PA";
    const row2 = el("span", "lastrow"); box.append(row2);
    row2.append(el("span", "to", "Last"));
    const li = el("input", "lastin"); li.type = "number"; li.min = 0; li.step = unit === "IP" ? 5 : 25; li.inputMode = "numeric"; li.placeholder = "all"; li.value = state.cardWin.last || ""; li.disabled = !can;
    li.setAttribute("aria-label", `Last ${unit}`); li.title = can ? `Only his most recent ${unit === "IP" ? "innings" : "plate appearances"}` : "Day-by-day data isn't built for this season";
    li.addEventListener("click", (e) => e.stopPropagation());
    li.addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
    li.addEventListener("change", (e) => { const v = Math.max(0, Math.round(Number(e.target.value) || 0)); state.cardWin.last = v ? String(v) : ""; if (v) state.cardWin.from = ""; render(); });
    row2.append(li, el("span", "to", unit));
    if (state.cardWin.from || state.cardWin.to || lastN(state.cardWin)) { const x = el("button", "unadd", "×"); x.type = "button"; x.title = "Full season"; x.addEventListener("click", (e) => { e.stopPropagation(); state.cardWin = { from: "", to: "", last: "" }; render(); }); row2.append(x); }
    return box;
  }
  function renderDates() {
    for (const [id, k] of [["dfrom", "from"], ["dto", "to"]]) { const i = $(id); i.min = seasonFirst(); i.max = seasonLast(); if (document.activeElement !== i) i.value = state.win[k] || ""; }
    const dd = $("ddays"); if (document.activeElement !== dd) dd.value = state.win.days || "";
    const li = $("dlast"); if (document.activeElement !== li) li.value = state.win.last || ""; li.step = lastUnit() === "IP" ? 5 : 25;
    $("dlastunit").textContent = lastUnit(); $("dfrom").disabled = !!lastN(state.win); $("dfrom").title = lastN(state.win) ? "Clear Last to use a start date" : "Blank = season start";
    $("dclear").hidden = !winRequested();
    const w = winIdx();
    $("winnote").textContent = state.daysLoading ? "Loading game-by-game data…" : w ? (w.last ? `each player's ${winLabel()}` : `${winLabel()} · ${w.hi - w.lo + 1} game days`) : "";
  }
  function renderMin() {
    const g = groupFor(state.pos);
    $("minlabel").textContent = "Min " + sampleLabel(g);
    const inp = $("min");
    if (document.activeElement !== inp) inp.value = state.min[g];
    inp.step = isPitcherGroup(g) ? 5 : 10;
  }
  function renderColhead() {
    const g = groupFor(state.pos), ref = refFor(g);
    const ms = colsFor(g), trending = state.mode === "trending";
    const h = $("colhead"); h.innerHTML = ""; h.className = "colhead grid";
    { const wrapEl = $("colwrap"), bs = $("bscroll"), board = $("board");   // the header sits above the scroll box and sticks to the screen
      if (wrapEl.parentNode !== board) board.insertBefore(wrapEl, bs); }
    h.style.setProperty("--n", ms.length); h.style.setProperty("--act", state.mode === "draft" ? "78px" : "0px"); h.style.setProperty("--colw", trending || ms.some((m) => m.showValue) ? "72px" : "56px");
    const editing = state.mode === "rankings" && state.editRanks, hasTiers = editing && (state.tiers[state.pos] || []).length;
    const mobile = document.documentElement.dataset.view === "mobile";
    h.style.setProperty("--rankw", editing ? (mobile ? (hasTiers ? "108px" : "72px") : hasTiers ? "190px" : "134px") : mobile ? "30px" : "44px");
    h.append(el("div", "h", editing ? (hasTiers ? "Rank · tier" : "My rank") : mobile ? "Rk" : "Rank"), el("div", "h left", ref === g ? "Player" : `Player · ranked vs ${POOL_NAME[ref]}`));
    const head = (key, label, title) => { const h = customOrder() ? Object.assign(el("div", "h", label), { title }) : sortButton(key, label, title); if (/^[a-z]/.test(label)) h.classList.add("lc"); return h; };
    const pre = preCols(), preOn = (k) => pre.some((c) => c.key === k);
    for (const k of ["year", "age"]) h.style.setProperty("--pre" + (k === "year" ? 1 : 2), preOn(k) ? "var(--prew, 64px)" : "0px");
    for (const c of [PRE_COLS.year, PRE_COLS.age]) { const on = preOn(c.key); const hb = on ? head(c.key, c.label, c.key === "year" ? "Season" : "Age that season") : el("div", "h"); hb.classList.add("pre"); if (!on) hb.classList.add("off"); h.append(hb); }
    { const sh = head("score", isPitcherGroup(g) ? "Score" : DS.noStatcast ? "wOBA" : HEAD.label, DS.noStatcast && !isPitcherGroup(g) ? "wOBA — no tracking at this level" : DATA.meta.scoreNote[isPitcherGroup(g) ? "P" : "H"]); if (hasBreak(g, "score")) sh.classList.add("brk"); h.append(sh); }
    // stat headers: click to sort (the column order is changed in the Table panel)
    for (const m of ms) {
      const hb = head(m.key, SHORT[m.key] || m.label, m.label + (m.hib ? " — higher is better" : " — lower is better"));
      hb.dataset.key = m.key; if (hasBreak(g, m.key)) hb.classList.add("brk");
      h.append(hb);
    }
    if (state.mode === "draft") h.append(el("div", "h", ""));
  }
  function sortButton(key, label, title) {
    const b = el("button", "h", label); b.type = "button"; b.title = title;
    if (state.sort === key) b.setAttribute("aria-sort", state.dir === "asc" ? "ascending" : "descending");
    b.addEventListener("click", () => {
      if (state.sort === key) state.dir = state.dir === "desc" ? "asc" : "desc"; else { state.sort = key; state.dir = key === "name" ? "asc" : "desc"; }
      savePrefs(); render();
    });
    return b;
  }
  function renderRows() {
    const { list, stats, g, ref, manual } = visiblePlayers();
    const rankMode = state.mode === "rankings" && state.editRanks;
    const src = orderSource();
    const allTiers = src ? tierLists(state.pos, src) : [], tiers = showTiers() ? allTiers : [];
    const idx = tierIndex(allTiers);
    const fullRank = new Map(src ? visiblePlayers({ all: true }).list.map((p, i) => [p.type + p.id, i + 1]) : []);
    const rankOf = (p, i) => (src ? fullRank.get(p.type + p.id) || i + 1 : i + 1);
    // group the visible rows by tier (the untiered section is index tiers.length); rows stay in rank order
    const groups = Array.from({ length: tiers.length + 1 }, () => []);
    list.forEach((p, i) => { const k = p.type + p.id; groups[tiers.length && idx.has(k) ? idx.get(k) : tiers.length].push([p, i]); });
    const tierHeader = (t) => {
      const th = el("li", "tierhead"); const untiered = t === tiers.length;
      if (untiered) { th.classList.add("untiered"); th.append(el("span", "tierlbl", "Not tiered")); th.append(el("small", null, `${groups[t].length} players${rankMode ? " — tick players and use Move to tier…, or drag them into a tier" : ""}`)); }
      else {
        const nm = ((src.names || {})[state.pos] || [])[t] || "";
        const lbl = el("span", "tierlbl", `Tier ${t + 1}${nm ? " · " + nm : ""}`);
        if (rankMode) {
          lbl.classList.add("editable"); lbl.title = "Click to name this tier";
          lbl.addEventListener("click", () => {
            const inp = el("input", "tiername"); inp.value = nm; inp.placeholder = `Name for tier ${t + 1}`; inp.maxLength = 40;
            const done = () => { setTierName(t, inp.value.trim()); };
            inp.addEventListener("keydown", (e) => { if (e.key === "Enter") done(); if (e.key === "Escape") render(); });
            inp.addEventListener("blur", done);
            lbl.replaceWith(inp); inp.focus();
          });
        }
        th.append(lbl);
        if (rankMode) { const pen = el("button", "pen", "✎"); pen.type = "button"; pen.title = nm ? "Rename this tier" : "Give this tier a nickname"; pen.addEventListener("click", () => lbl.click()); th.append(pen); }
        const ranks = tiers[t].map((k) => fullRank.get(k)).filter(Boolean);
        th.append(el("small", null, ranks.length ? `${ranks.length} player${ranks.length === 1 ? "" : "s"} · ranks ${Math.min(...ranks)}–${Math.max(...ranks)}` : "empty"));
        if (rankMode) { const x = el("button", "unadd", "×"); x.type = "button"; x.title = "Remove this tier (players return to Not tiered)"; x.addEventListener("click", () => removeTier(t)); th.append(x); }
      }
      if (rankMode) { const plus = el("button", "pen plus", "+ tier above"); plus.type = "button"; plus.title = untiered ? "Add an empty tier above Not tiered" : `Insert an empty tier above tier ${t + 1}`; plus.addEventListener("click", () => insertTier(t)); th.append(plus); }
      th.dataset.tier = t;
      return th;
    };
    const ms = colsFor(g), trending = state.mode === "trending";
    const drafted = draftedIds();
    const ol = $("rows"); ol.innerHTML = "";
    const empty = $("empty"); empty.hidden = list.length > 0; empty.innerHTML = "";
    if (needsRows() && !DS.ready()) {
      empty.hidden = false; ol.innerHTML = "";
      empty.textContent = state.daysFailed ? "Couldn't load days.js — the game-by-game data file is missing." : "Loading game-by-game data…";
      return;
    }
    if (!pool(g).list.length) {
      empty.append(`No ${isPitcherGroup(g) ? "pitchers" : "hitters"} reach ${effMin(g)} ${sampleLabel(g)} ${DS.kind ? "in these games" : "this season"}${needsDays() ? " with games in this range" : ""}. Lower the minimum.`);
    } else if (!list.length) empty.textContent = "No players match.";
    const frag = document.createDocumentFragment();
    const listDs = DS === CUR ? null : DS.key;   // the season this list is drawn from (captured now: click handlers run later)
    const listSplit = state.mode === "leaderboard" ? { hand: SPLIT.hand, venue: SPLIT.venue } : null;
    // pages: a new list (tab, search, sort, window, season…) starts back at page 1
    const sig = [state.mode, state.pos, state.q, state.sort, state.dir, JSON.stringify(state.min), JSON.stringify(listWin()), listDs, JSON.stringify(listSplit), customOrder(), state.tierView, list.length].join("|");
    if (sig !== state.pageSig) { state.pageSig = sig; state.page = 1; }
    const pg = pageWindow(list.length);
    const onPage = (i) => i >= pg.start && i < pg.end;
    renderPager($("pagertop"), list.length, pg); renderPager($("pagerbot"), list.length, pg);
    const pre = preCols(), preOn = (k) => pre.some((c) => c.key === k);
    const emitRow = (p, i, rows, j) => {          // rows / j: the displayed section and his place in it (▲ ▼ swap with neighbours)
      const st = stats.get(p.type + p.id);
      const li = el("li", "row"); li.dataset.key = p.type + p.id;
      if (drafted.has(p.id)) li.classList.add("drafted");
      const ck = p.type + (p.pid ?? p.id), cds = p.dsKey ? (p.dsKey === CUR.key ? null : p.dsKey) : listDs;   // the card: the real player in his own season
      const exp = state.expanded === ck && (state.cardDs || null) === cds;
      if (exp) li.classList.add("open");
      const main = el("div", "row-main grid");
      main.style.setProperty("--n", ms.length); main.style.setProperty("--act", state.mode === "draft" ? "78px" : "0px"); main.style.setProperty("--colw", trending || ms.some((m) => m.showValue) ? "72px" : "56px");
      const mobile = document.documentElement.dataset.view === "mobile";
      main.style.setProperty("--rankw", rankMode ? (mobile ? (allTiers.length ? "108px" : "72px") : allTiers.length ? "190px" : "134px") : mobile ? "30px" : "44px");
      main.style.setProperty("--pre1", preOn("year") ? "var(--prew, 64px)" : "0px"); main.style.setProperty("--pre2", preOn("age") ? "var(--prew, 64px)" : "0px");
      if (rankMode) {
        const key = p.type + p.id;
        const ctl = el("div", "rankctl");
        const cb = el("input", "selbox"); cb.type = "checkbox"; cb.checked = state.selKeys.includes(key); cb.setAttribute("aria-label", `Select ${p.name}`);
        cb.addEventListener("click", (e) => { e.stopPropagation(); toggleSel(key, e); });
        if (cb.checked) li.classList.add("selected");
        ctl.append(cb);
        const drag = el("span", "drag", "⋮⋮"); drag.title = "Drag to reorder"; ctl.append(drag);
        const inp = el("input"); inp.type = "number"; inp.min = 1; inp.max = fullRank.size || list.length; inp.value = rankOf(p, i); inp.setAttribute("aria-label", `Rank of ${p.name}`); inp.title = "Rank (his tier stays the same)";
        inp.addEventListener("click", (e) => e.stopPropagation());
        inp.addEventListener("change", (e) => { e.stopPropagation(); const r = Number(e.target.value); if (r >= 1) setRank(key, r); });
        inp.addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
        const arrows = el("div", "arrows");
        const swap = (n) => { const [q, qi] = rows[n]; setRank(key, rankOf(q, qi)); };
        const up = el("button", null, "▲"); up.type = "button"; up.title = "Move above the player shown above"; up.addEventListener("click", (e) => { e.stopPropagation(); if (j > 0) swap(j - 1); });
        const dn = el("button", null, "▼"); dn.type = "button"; dn.title = "Move below the player shown below"; dn.addEventListener("click", (e) => { e.stopPropagation(); if (j < rows.length - 1) swap(j + 1); });
        arrows.append(up, dn); ctl.append(inp, arrows);
        if (allTiers.length) {                               // tier box: type a tier number (blank = Not tiered)
          const ti = el("input", "tierin"); ti.type = "number"; ti.min = 0; ti.max = allTiers.length; ti.placeholder = "T";
          ti.value = idx.has(key) ? idx.get(key) + 1 : ""; ti.title = "Tier (blank = Not tiered; his rank stays the same)";
          ti.setAttribute("aria-label", `Tier of ${p.name}`);
          ti.addEventListener("click", (e) => e.stopPropagation());
          ti.addEventListener("change", (e) => { e.stopPropagation(); const v = e.target.value === "" ? 0 : Number(e.target.value); moveToTier(key, isNaN(v) ? 0 : v); });
          ti.addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
          ctl.append(ti);
        }
        main.append(ctl);
        li.draggable = true; li.dataset.index = i + 1;
        li.addEventListener("dragstart", (e) => { dragKey = key; li.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", key); } catch {} });
        li.addEventListener("dragend", () => { dragKey = null; li.classList.remove("dragging"); clearDropMark(); });
      } else {
        main.append(el("div", "rank", rankOf(p, i)));
      }
      const who = el("div", "who");
      const nameEl = el("div", "name", p.name);
      if (state.mode === "rankings" || state.mode === "draft") { const sk = listStars()[p.type + p.id]; if (sk) { const star = el("span", "rowstar", "★"); star.title = sk.note || "Starred"; nameEl.append(" ", star); if (sk.note) nameEl.title = sk.note; } }
      who.append(nameEl);
      const meta = el("div", "meta");
      meta.append(el("span", "team", p.team));
      meta.append(el("span", null, p.type === "P" ? `${posLabel(p)} · ${p.throws}HP` : posLabel(p) + (p.bats ? ` · ${p.bats}` : "")));
      const v = V(p);
      const flag = el("span", "flag", p.type === "P" ? `${fmtIP(v.ip)} IP` : `${v.pa} PA`);
      if (seasonSample(p) < effMin(g) && !hasExtra(p, state.pos)) { flag.classList.add("low"); flag.title = `Under the Min ${sampleLabel(g)} — listed after everyone who qualifies; his percentiles are where he'd land among them`; }
      meta.append(flag);
      if (hasExtra(p, state.pos)) {
        const tag = el("span", "added", `added ${state.pos}`);
        const x = el("button", "unadd", "×"); x.type = "button"; x.title = `Remove ${state.pos} from ${p.name}'s eligibility`;
        x.setAttribute("aria-label", x.title);
        x.addEventListener("click", (e) => { e.stopPropagation(); removePos(p.id, state.pos); state.expanded = null; render(); });
        tag.append(x); meta.append(tag);
      }
      who.append(meta);
      main.append(who);
      for (const c of [PRE_COLS.year, PRE_COLS.age]) { const on = preOn(c.key); const b = el("div", "pct pre", on ? preValue(c.key, p) : ""); if (!on) b.classList.add("off"); else { if (state.sort === c.key && !customOrder()) b.classList.add("sorted"); b.prepend(el("span", "lbl", c.label)); } main.append(b); }
      const sc = el("div", "score", p.type === "H" ? fmtX(st.score) : Math.round(st.score)); if (state.tbl.heat) paint(sc, st.scorePct); if (state.sort === "score" && !customOrder()) sc.classList.add("sorted"); if (hasBreak(g, "score")) sc.classList.add("brk");
      sc.title = p.type === "H" ? `${HEAD.label} ${fmtX(st.score)} · ${st.scorePct == null ? "n/a" : ordinal(st.scorePct)} pctl` : "Score"; main.append(sc);
      const pcts = el("div", "pcts");
      for (const m of ms) {
        const v = metricValue(m, V(p), st), pct = st.pct[m.key];
        const b = el("div", "pct"); const showV = state.tbl.numbers === "values" ? true : state.tbl.numbers === "pct" ? false : (trending || m.showValue);
        if (pct == null && (showV ? v == null : true)) { b.classList.add("na"); b.textContent = "–"; } else { b.textContent = showV ? (v == null ? "–" : fmt(v, m).replace(" mph", "")) : pct; if (state.tbl.heat && pct != null) paint(b, pct); }
        if (state.sort === m.key && !customOrder()) b.classList.add("sorted");
        if (hasBreak(g, m.key)) b.classList.add("brk");
        b.title = `${m.label}: ${v == null ? "n/a" : fmt(v, m)} (${pct == null ? "n/a" : ordinal(pct)} pctl)`;
        b.prepend(el("span", "lbl", SHORT[m.key] || m.label));
        pcts.append(b);
      }
      main.append(pcts);
      if (state.mode === "draft") {
        const act = el("div", "act");
        const btn = el("button", "draftbtn", drafted.has(p.id) ? "Undo" : "Draft"); btn.type = "button";
        btn.setAttribute("aria-label", (drafted.has(p.id) ? "Return to board: " : "Mark drafted: ") + p.name);
        btn.addEventListener("click", (e) => { e.stopPropagation(); drafted.has(p.id) ? undraft(p.id) : draft(p); });
        act.append(btn); main.append(act);
      }
      main.addEventListener("click", (e) => {
        const k = p.type + p.id;
        if (rankMode) { toggleSel(k, e); return; }                     // edit mode: select (cmd/ctrl adds, shift ranges)
        if (!exp) { const lw = listWin(); state.cardDs = cds; state.cardWin = { from: lw.from, to: lw.to, last: lw.last }; if (listSplit) state.split = listSplit; } state.expanded = exp ? null : ck; render();
      });
      li.append(main);
      frag.append(li);
    };
    if (src && tiers.length) {
      groups.forEach((rows, t) => {
        const untiered = t === tiers.length;
        const here = rows.some(([, i]) => onPage(i));
        if (!rankMode && !here) return;                        // Draft page / later pages: skip tiers with nothing to show
        if (rankMode && !here && !(state.page === 1 && !rows.length)) return;   // empty tiers show once, on page 1
        frag.append(tierHeader(t));
        rows.forEach(([p, i], j) => { if (onPage(i)) emitRow(p, i, rows, j); });
        if (rankMode && !untiered && !tiers[t].length) { const dz = el("li", "tierdrop", "Drop players here"); dz.dataset.tier = t; frag.append(dz); }
      });
    } else { const rows = list.map((p, i) => [p, i]); rows.forEach(([p, i], j) => { if (onPage(i)) emitRow(p, i, rows, j); }); }
    ol.append(frag);
    fitNameCol();
  }
  // The name column is as wide as the widest name on the page, so every row's stats start in the same place.
  // Each row is its own grid, so a single long name would otherwise push that row's columns out of line; the
  // measured width becomes the column's minimum (it still stretches to fill whatever the stats leave over).
  let measureCtx = null;
  function textWidth(text, font) {
    measureCtx = measureCtx || document.createElement("canvas").getContext("2d");
    measureCtx.font = font;
    return measureCtx.measureText(text).width;
  }
  function fitNameCol() {
    const board = $("board"), first = $("rows").querySelector(".who");
    if (!first) { board.style.removeProperty("--namew"); return; }
    const cs = getComputedStyle(first), pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    const fontOf = (n) => { const c = getComputedStyle(n); return `${c.fontStyle} ${c.fontWeight} ${c.fontSize} ${c.fontFamily}`; };
    const nameFont = fontOf(first.querySelector(".name"));
    let w = 0;
    for (const who of $("rows").querySelectorAll(".who")) {
      const nm = who.querySelector(".name");
      let own = nm ? textWidth(nm.textContent, nameFont) : 0;
      const meta = who.querySelector(".meta");                     // team · position · PA, laid out as a flex row
      if (meta) {
        const gap = parseFloat(getComputedStyle(meta).columnGap) || 0;
        let line = 0, n = 0;
        for (const part of meta.children) { line += part.offsetWidth; n++; }
        own = Math.max(own, line + Math.max(0, n - 1) * gap);
      }
      w = Math.max(w, own);
    }
    const head = $("colhead").children[1];                          // "Player", or "Player · ranked vs …"
    if (head && head.textContent) w = Math.max(w, textWidth(head.textContent, fontOf(head)));
    const mobile = document.documentElement.dataset.view === "mobile";
    const lo = mobile ? 142 : 180, hi = mobile ? 230 : 460;
    board.style.setProperty("--namew", Math.min(hi, Math.max(lo, Math.ceil(w + pad + 2))) + "px");
  }
  // ---- pages ----
  const PAGE_SIZES = [25, 50, 100, 0];
  function pageWindow(total) {
    const size = state.pageSize || 0, pages = size ? Math.max(1, Math.ceil(total / size)) : 1;
    if (state.page > pages) state.page = pages; if (state.page < 1) state.page = 1;
    const start = size ? (state.page - 1) * size : 0;
    return { size, pages, page: state.page, start, end: size ? Math.min(total, start + size) : total };
  }
  // a pager bar: "1–50 of 597", first / previous / page numbers / next / last, and rows-per-page
  function renderPager(box, total, pg, onChange) {
    if (!box) return;
    box.innerHTML = "";
    const go = (n) => { state.page = Math.min(pg.pages, Math.max(1, n)); (onChange || renderRows)(); const top = box.closest(".board, .fboard") || box; const sb = top.querySelector(".board-scroll, .fscroll"); if (sb) sb.scrollTop = 0; const y = top.getBoundingClientRect().top + window.scrollY - 8; if (window.scrollY > y) window.scrollTo({ top: y }); };
    const setSize = (n) => { state.pageSize = n; state.page = 1; savePrefs(); (onChange || renderRows)(); };
    if (!total) { box.hidden = true; return; }
    box.hidden = false;
    box.append(el("span", "pcount", pg.size ? `${pg.start + 1}–${pg.end} of ${total}` : `${total} players`));
    if (pg.pages > 1) {
      const nav = el("div", "pnav");
      const b = (label, n, title, dis) => { const x = el("button", "pbtn", label); x.type = "button"; x.title = title; x.disabled = dis; x.addEventListener("click", () => go(n)); return x; };
      const first = b("«", 1, "First page", pg.page === 1); first.classList.add("pend");
      nav.append(first, b("‹", pg.page - 1, "Previous page", pg.page === 1));
      const near = document.documentElement.dataset.view === "mobile" ? 1 : 2;
      const nums = new Set([1, pg.pages, ...Array.from({ length: 2 * near + 1 }, (_, i) => pg.page - near + i)].filter((n) => n >= 1 && n <= pg.pages));
      let last = 0;
      for (const n of [...nums].sort((a, c) => a - c)) {
        if (n - last > 1) nav.append(el("span", "pgap", "…"));
        const x = b(String(n), n, `Page ${n}`, false); if (n === pg.page) x.setAttribute("aria-current", "page"); nav.append(x); last = n;
      }
      const lastb = b("»", pg.pages, "Last page", pg.page === pg.pages); lastb.classList.add("pend");
      nav.append(b("›", pg.page + 1, "Next page", pg.page === pg.pages), lastb);
      box.append(nav);
    }
    const sz = el("label", "psize"); sz.append(el("span", null, "Per page"));
    const sel = el("select");
    for (const n of PAGE_SIZES) { const o = el("option", null, n ? String(n) : "All"); o.value = String(n); if (n === (state.pageSize || 0)) o.selected = true; sel.append(o); }
    sel.addEventListener("change", () => setSize(Number(sel.value)));
    sz.append(sel); box.append(sz);
  }

  // a metric's value for display: season / window values live on V(p).m, pool-derived ones (underlying ERA) on the stats
  const metricValue = (m, pv, st) => (m.key === "ukb" ? (st ? st.ukb : null) : m.key === "uera" ? (st ? st.uera : null) : pv.m[m.key]);
  function meterRow(m, v, pct) {
    const row = el("div", "meter");
    row.append(el("div", "lbl", m.label));
    const track = el("div", "track");
    if (pct != null) {
      const s = pctStyle(pct);
      const fill = el("div", "fill"); fill.style.width = pct + "%"; fill.style.background = s.bg; track.append(fill);
      const bub = el("div", "bub", pct); bub.style.left = pct + "%"; bub.style.background = s.bg; track.append(bub);
    }
    row.append(track);
    row.append(el("div", "val", v == null ? "–" : fmt(v, m)));
    row.title = `${m.label}: ${v == null ? "n/a" : fmt(v, m)} · ${pct == null ? "n/a" : ordinal(pct) + " pctl"}${m.hib ? "" : " (lower is better)"}`;
    return row;
  }

  function renderHitterCard(p, st, g, ref) {
    const card = el("div", "card hcard");
    card.append(renderSplitBar(p));
    const pv = V(p);
    const strip = el("div", "hstrip");
    const chip = (k, v) => { const c = el("span", "hchip"); c.append(el("b", null, v), " ", k); strip.append(c); };
    chip("PA", pv.pa); chip("AB", pv.ab);
    if (pv.ctx.BBE || pv.ctx.BIP == null) chip("BBE", pv.ctx.BBE); else chip("BIP", pv.ctx.BIP);
    const gH = pv.ctx.G != null ? pv.ctx.G : careerG(p);
    if (gH != null) chip("G", gH);
    card.append(strip);
    card.append(el("h3", null, `Percentile rank · ${viewLabel(p.type)} · ${poolPhrase(ref)} (${pool(ref).ref.length})`));
    const cols = [el("div", "hcol"), el("div", "hcol")];
    const leftH = DATA.meta.hitterCardLeft || 2;
    if (DS.noStatcast) card.append(el("p", "note", DS.tracked > 0.05
      ? `Only some ${DS.levelName} parks track pitches (${Math.round(100 * DS.tracked)}% of balls in play, the Florida State League): exit velocity, barrels, xwOBA and zone numbers cover those games only, and bat speed isn't tracked. Hitters rank by wOBA here.`
      : `No pitch tracking at this level (${DS.levelName}): exit velocity, barrels, xwOBA, bat speed and zone / chase numbers aren't available — swings, contact, batted-ball type and direction come from the play-by-play. Hitters rank by wOBA here.`));
    CARD.forEach((grp, gi) => {
      const box = el("section", "hgroup");
      box.append(el("h4", null, grp.group));
      const meters = el("div", "meters");
      const metrics = DS.hist ? grp.metrics.filter((m) => pv.m[m.key] != null) : grp.metrics;   // past / minor-league seasons: only stats that exist
      if (!metrics.length) return;
      let prev = null;
      for (const m of metrics) {
        const row = meterRow(m, pv.m[m.key], st.pct[m.key]);
        if (prev && RULE_H.has(m.key)) row.classList.add("ruled");      // the peak-EV block sits under a dotted rule
        prev = m;
        if (SUB[m.key]) {
          const isOpen = !!state.open[m.key];
          const t = el("button", "fold", isOpen ? "▾" : "▸"); t.type = "button"; t.title = `${isOpen ? "Hide" : "Show"} the ${SUB[m.key].map((x) => x.label).join(" / ")} breakdown`; t.setAttribute("aria-expanded", String(isOpen));
          t.addEventListener("click", (e) => { e.stopPropagation(); state.open[m.key] = !isOpen; savePrefs(); render(); });
          row.querySelector(".lbl").append(t);
          meters.append(row);
          if (isOpen) for (const sm of SUB[m.key]) { if (DS.hist && pv.m[sm.key] == null) continue; const r = meterRow(sm, pv.m[sm.key], st.pct[sm.key]); r.classList.add("sub"); meters.append(r); }
        } else meters.append(row);
      }
      box.append(meters);
      cols[gi < leftH ? 0 : 1].append(box);
    });
    const grid = el("div", "hgroups"); grid.append(...cols); card.append(grid);
    card.dataset.notes = `${HEAD.label} = ${DATA.meta.scoreNote.H}. Bat speed is averaged over competitive swings (Savant's number for the full season). Strike% and Swing% are the hitter's own rates — lower Strike% and O-Swing%, Whiff% and K% count as better. Every percentile is ${poolPhrase(ref)}.`;
    return card;
  }
  // a card section that folds: a heading with an arrow; the body only when open (remembered per section)
  function foldSection(key, title, build, open0) {
    const sec = el("section", "fold-sec");
    const isOpen = state.open[key] != null ? !!state.open[key] : !!open0;
    const h = el("button", "foldhead", ""); h.type = "button"; h.setAttribute("aria-expanded", String(isOpen));
    h.append(el("span", "arrow", isOpen ? "▾" : "▸"), " ", title);
    h.addEventListener("click", (e) => { e.stopPropagation(); state.open[key] = !isOpen; savePrefs(); render(); });
    sec.append(h);
    if (isOpen) sec.append(build());
    return sec;
  }

  const careerReady = () => !!window.DRAFT_CAREER;
  // games played this season from the official record (the season line carries no game count of its own)
  function careerG(p) {
    if (DS.kind || DS.level !== "MLB" || needsDays()) return null;
    ensureScript("hist/career.js", careerReady);
    const rec = careerReady() ? window.DRAFT_CAREER[String(p.id)] : null, rows = rec ? rec[p.type] : null;
    if (!rows) return null;
    const hit = (DS.years || [DS.season]).map((y) => rows.find((x) => x[0] === y)).filter(Boolean);
    return hit.length ? hit.reduce((a, r) => a + r[p.type === "H" ? 2 : 5], 0) : null;
  }
  const RAW_H = ["G", "PA", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "K", "AVG", "OBP", "SLG", "OPS"];
  const RAW_P = ["W", "L", "ERA", "G", "GS", "SV", "IP", "H", "HR", "BB", "K", "WHIP", "K/9"];
  // Season by season: MLB (official), MiLB (every level; a year at several levels folds out), or All (MLB + minors,
  // combined per year with the pieces folded underneath). Rates are recomputed from the counts for combined lines.
  const ipNum = (v) => { if (v == null) return 0; const n = Number(v); const w = Math.floor(n), t = Math.round((n - w) * 10); return w + (t === 1 ? 1 / 3 : t === 2 ? 2 / 3 : 0); };
  const ipStr = (x) => { const w = Math.floor(x + 1e-9), t = Math.round((x - w) * 3); return `${w}.${t}`; };
  function rawLines(p) {
    // every line as {season, level, team, c: counts by key, mlb: bool}
    const rec = careerReady() ? window.DRAFT_CAREER[String(p.id)] : null; if (!rec) return null;
    const H = p.type === "H", lines = [];
    const keysMLB = H ? RAW_H : RAW_P;
    const advOf = (a, mlb) => {                       // our numbers where the season is built, as one object
      if (!Array.isArray(a)) return {};
      if (H) return { woba: a[0], xwoba: a[1], whf: mlb ? null : a[2] };
      return mlb ? { fip: a[0], siera: a[1], whf: a[5], strk: a[6] } : { fip: a[0], siera: a[1], whf: a[2], strk: a[3] };
    };
    for (const r of rec[p.type] || []) {
      const c = {}; keysMLB.forEach((k, i) => { c[k] = r[2 + i]; });
      const extra = r.length > 2 + keysMLB.length + 1 ? r.slice(2 + keysMLB.length, -1) : [];
      if (H) { c.HBP = extra[0] || 0; c.SF = extra[1] || 0; } else { c.ER = extra[0]; c.BF = extra[1]; }
      c.adv = advOf(r[r.length - 1], true);
      lines.push({ season: r[0], level: "MLB", team: r[1], c, mlb: true });
    }
    const mrec = window.DRAFT_MINORS ? window.DRAFT_MINORS[String(p.id)] : null;
    for (const r of (mrec && mrec[p.type]) || []) {
      const c = {}; keysMLB.forEach((k, i) => { c[k] = r[3 + i]; });
      const hasAdv = Array.isArray(r[r.length - 1]) || r[r.length - 1] === null;
      const extra = hasAdv ? r.slice(3 + keysMLB.length, -1) : r.slice(3 + keysMLB.length);
      if (H) { c.HBP = extra[0] || 0; c.SF = extra[1] || 0; } else { c.ER = extra[0]; c.BF = extra[1]; }
      c.adv = hasAdv ? advOf(r[r.length - 1], false) : {};
      lines.push({ season: r[0], level: r[1], team: r[2], c, mlb: false, combo: r[1] === "Minors" });
    }
    return lines;
  }
  function combineLines(H, parts) {
    const c = {};
    const sum = (k) => parts.reduce((a, x) => a + (Number(x.c[k]) || 0), 0);
    if (H) {
      for (const k of ["G", "PA", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "K", "HBP", "SF"]) c[k] = sum(k);
      const tb = c.H + c["2B"] + 2 * c["3B"] + 3 * c.HR;
      c.AVG = c.AB ? c.H / c.AB : null; c.OBP = c.AB + c.BB + c.HBP + c.SF ? (c.H + c.BB + c.HBP) / (c.AB + c.BB + c.HBP + c.SF) : null;
      c.SLG = c.AB ? tb / c.AB : null; c.OPS = c.OBP != null && c.SLG != null ? c.OBP + c.SLG : null;
    } else {
      for (const k of ["W", "L", "G", "GS", "SV", "H", "HR", "BB", "K", "ER", "BF"]) c[k] = sum(k);
      const ip = parts.reduce((a, x) => a + ipNum(x.c.IP), 0);
      c.IP = ipStr(ip); c.ERA = ip ? 9 * c.ER / ip : null; c.WHIP = ip ? (c.H + c.BB) / ip : null; c["K/9"] = ip ? 9 * c.K / ip : null;
    }
    // our rates, weighted by plate appearances / batters faced across the pieces that have them
    const wkey = H ? "PA" : "BF", adv = {};
    for (const k of ["woba", "xwoba", "fip", "siera", "whf", "strk"]) {
      let num = 0, den = 0;
      for (const x of parts) { const v = x.c.adv && x.c.adv[k]; const w = Number(x.c[wkey]) || 0; if (v != null && w) { num += v * w; den += w; } }
      adv[k] = den ? num / den : null;
    }
    c.adv = adv;
    return c;
  }
  function renderRawStats(p, noHead) {
    const box = el("div", "rawstats");
    if (!noHead) box.append(el("h3", null, "Season stats"));
    ensureScript("hist/career.js", careerReady);
    if (!careerReady()) { box.append(el("p", "note", failed.has("hist/career.js") ? "hist/career.js hasn't been built — run build_career.py" : "Loading career stats…")); return box; }
    const H = p.type === "H", mode = state.rawMode || "mlb";
    if (mode !== "mlb") ensureScript("hist/minors.js", () => !!window.DRAFT_MINORS);
    const lines = rawLines(p) || [];
    const seg = el("div", "seg rawseg"); seg.setAttribute("role", "group");
    for (const [v, l] of [["mlb", "MLB"], ["milb", "MiLB"], ["all", "All levels"]]) {
      const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(mode === v));
      b.addEventListener("click", (e) => { e.stopPropagation(); state.rawMode = v; savePrefs(); render(); }); seg.append(b);
    }
    box.append(seg);
    const cols = H ? RAW_H : RAW_P, extra = H ? ["wOBA", "xwOBA", "K%", "BB%", "Whiff%"] : ["FIP", "SIERA", "K%", "BB%", "K-BB%", "Whiff%", "Strike%"];
    const fmtv = (k, v) => v == null ? "–" : ["AVG", "OBP", "SLG", "OPS", "wOBA", "xwOBA"].includes(k) ? fmtX(v) : ["ERA", "WHIP", "K/9", "FIP", "SIERA"].includes(k) ? Number(v).toFixed(2) : k.endsWith("%") ? Number(v).toFixed(1) + "%" : k === "IP" ? String(v) : v;
    // the extra columns: strikeout and walk rates from the official counts, the rest from this site where built
    const extraVal = (c, k) => {
      const den = H ? Number(c.PA) : Number(c.BF), a = c.adv || {};
      const rate = (n) => (den ? 100 * Number(n || 0) / den : null);
      if (k === "K%") return rate(c.K); if (k === "BB%") return rate(c.BB); if (k === "K-BB%") { const x = rate(c.K), y = rate(c.BB); return x == null ? null : x - y; }
      return { "wOBA": a.woba, "xwOBA": a.xwoba, "FIP": a.fip, "SIERA": a.siera, "Whiff%": a.whf, "Strike%": a.strk }[k];
    };
    // rows to show: [{season, level, team, c, subs: [...]}]
    let rows = [];
    if (mode === "mlb") rows = lines.filter((l) => l.mlb).map((l) => ({ ...l })).sort((a, b) => b.season - a.season);
    else {
      const pick = mode === "milb" ? lines.filter((l) => !l.mlb) : lines;
      const seasons = [...new Set(pick.map((l) => l.season))].sort((a, b) => b - a);
      for (const y of seasons) {
        const here = pick.filter((l) => l.season === y);
        const combo = here.find((l) => l.combo), pieces = here.filter((l) => !l.combo);
        if (mode === "milb") {
          if (combo) rows.push({ ...combo, level: "Minors", team: `${pieces.length} levels`, subs: pieces });
          else rows.push({ ...pieces[0] });
        } else {
          if (pieces.length === 1) rows.push({ ...pieces[0] });
          else rows.push({ season: y, level: "All", team: `${pieces.length} teams`, c: combineLines(H, pieces), subs: pieces });
        }
      }
    }
    if (mode !== "mlb" && !window.DRAFT_MINORS) { box.append(seg.cloneNode(false)); box.append(el("p", "note", failed.has("hist/minors.js") ? "hist/minors.js hasn't been built — run build_career.py" : "Loading minor-league seasons…")); return box; }
    if (!rows.length) { box.append(el("p", "note", mode === "mlb" ? "No MLB seasons on record." : mode === "milb" ? "No minor-league seasons on record." : "Nothing on record.")); return box; }
    const table = el("table"), thead = el("thead"), tr = el("tr");
    const head = ["Season", ...(mode === "mlb" ? [] : ["Level"]), "Team", ...cols, ...extra];
    for (const h of head) tr.append(el("th", ["Season", "Level", "Team"].includes(h) ? "l" : null, h));
    thead.append(tr); table.append(thead);
    const tbody = el("tbody");
    const line = (r, sub) => {
      const row = el("tr"); if (sub) row.classList.add("sub"); if (!sub && r.season === DS.season && (mode === "mlb" || r.level === "MLB" || r.level === "All")) row.classList.add("cur");
      const sc = el("td", "l"); sc.textContent = sub ? "" : String(r.season);
      if (!sub && r.subs && r.subs.length) {
        const k = "raw:" + mode + ":" + r.season, isOpen = !!state.open[k];
        const t = el("button", "fold", isOpen ? "▾" : "▸"); t.type = "button"; t.title = `${isOpen ? "Hide" : "Show"} the ${r.subs.length} lines`; t.setAttribute("aria-expanded", String(isOpen));
        t.addEventListener("click", (e) => { e.stopPropagation(); state.open[k] = !isOpen; savePrefs(); render(); });
        sc.append(" ", t);
      }
      row.append(sc);
      if (mode !== "mlb") row.append(el("td", "l", r.level));
      row.append(el("td", "l", r.team || ""));
      cols.forEach((k) => row.append(el("td", null, fmtv(k, r.c[k]))));
      extra.forEach((k) => { const v = extraVal(r.c, k); row.append(el("td", null, v == null ? "–" : fmtv(k, v))); });
      tbody.append(row);
      if (!sub && r.subs && state.open["raw:" + mode + ":" + r.season]) for (const x of r.subs) line(x, true);
    };
    rows.forEach((r) => line(r, false));
    if (mode === "mlb") {
      const rec = window.DRAFT_CAREER[String(p.id)], career = rec ? rec[p.type + "C"] : null;
      if (career) { const row = el("tr", "career"); row.append(el("td", "l", "Career"), el("td", "l", `${rows.length} yr`)); cols.forEach((k, i) => row.append(el("td", null, fmtv(k, career[i])))); extra.forEach(() => row.append(el("td", null, ""))); tbody.append(row); }
    }
    table.append(tbody);
    const scroll = el("div", "rawscroll"); scroll.append(table); box.append(scroll);
    box.append(el("p", "note", (mode === "mlb" ? "MLB regular seasons from the official record. " : mode === "milb" ? "Minor-league regular seasons from the official record, every level; a year at several levels shows the combined line — open it for each level. " : "MLB and minor-league regular seasons together; a year with several stops shows one combined line — open it for each stop. ")
      + `K% and BB% come from the official counts; ${H ? "wOBA, xwOBA and Whiff%" : "FIP, SIERA, Whiff% and Strike%"} from this site where that season and level is built (MLB from 2015, Triple-A from 2022, the lower levels from 2021). Combined lines average those by ${H ? "PA" : "batters faced"}.`));
    return box;
  }
  function renderCard(p, ms, st, g, ref) {
    const card = p.type === "H" ? renderHitterCard(p, st, g, ref) : renderPitcherCard(p, ms, st, g, ref);
    if (state.mode !== "compare") card.append(foldSection("raw", "Season stats", () => renderRawStats(p, true)));
    if (card.dataset.notes) card.append(el("p", "note cardnotes", card.dataset.notes));
    return card;
  }
  function renderPitcherCard(p, ms, st, g, ref) {
    const card = el("div", "card hcard");
    card.append(renderSplitBar(p));
    const pv = V(p);
    const strip = el("div", "hstrip");
    const chip = (k, v) => { const c = el("span", "hchip"); c.append(el("b", null, v), " ", k); strip.append(c); };
    chip("IP", fmtIP(pv.ip)); chip("BF", pv.bf);
    chip("G / GS", `${pv.g} / ${pv.gs}`); chip("pitches", pv.ctx.Pitches);
    card.append(strip);
    card.append(el("h3", null, `Percentile rank · ${viewLabel(p.type)} · ${poolPhrase(ref)} (${pool(ref).ref.length})`));
    const cols = [el("div", "hcol"), el("div", "hcol")];
    const left = DATA.meta.pitcherCardLeft || 2;
    if (DS.noStatcast) card.append(el("p", "note", DS.tracked > 0.05
      ? `Only some ${DS.levelName} parks track pitches (the Florida State League): velocity, zone / chase and exit-velocity numbers cover those games only.`
      : `No pitch tracking at this level (${DS.levelName}): velocity, extension, zone / chase and exit-velocity numbers aren't available — strikes, swings, whiffs and batted-ball types come from the play-by-play.`));
    CARD_P.forEach((grp, gi) => {
      const box = el("section", "hgroup");
      box.append(el("h4", null, grp.group));
      const meters = el("div", "meters");
      if (grp.group === "Results") meters.classList.add("results");
      const metrics = DS.hist ? grp.metrics.filter((m) => metricValue(m, pv, st) != null) : grp.metrics;
      if (!metrics.length) return;
      let seenEra = false;
      for (const m of metrics) {
        const row = meterRow(m, metricValue(m, pv, st), st.pct[m.key]);
        if (grp.group === "Results" && seenEra && m.key === "nera") row.classList.add("after-era");
        if (m.key === "era") seenEra = true;
        const subs = (SUB_P[m.key] || []).filter((sm) => !DS.hist || metricValue(sm, pv, st) != null);
        if (subs.length) {
          const isOpen = !!state.open["p:" + m.key];
          const t = el("button", "fold", isOpen ? "▾" : "▸"); t.type = "button"; t.title = `${isOpen ? "Hide" : "Show"} ${subs.map((x) => x.label).join(" / ")}`; t.setAttribute("aria-expanded", String(isOpen));
          t.addEventListener("click", (e) => { e.stopPropagation(); state.open["p:" + m.key] = !isOpen; savePrefs(); render(); });
          row.querySelector(".lbl").append(t);
          meters.append(row);
          if (isOpen) for (const sm of subs) { const r = meterRow(sm, pv.m[sm.key], st.pct[sm.key]); r.classList.add("sub"); meters.append(r); }
        } else meters.append(row);
      }
      box.append(meters);
      cols[gi < left ? 0 : 1].append(box);
    });
    const grid = el("div", "hgroups"); grid.append(...cols); card.append(grid);
    if (st && st.ukbb) card.append(foldSection("ukbb", "Underlying K% and BB%", () => renderUnderlyingKBB(pv, st, true)));
    if (pv.ctx.bbl && K().bbw) card.append(foldSection("luck", "Batted-ball luck", () => renderLuckTable(p, pv, true)));
    card.dataset.notes = (`Every percentile is against ${DS.level === "MLB" ? "all" : DS.levelName} pitchers with ${refMin(g)}+ batters faced ${DS.hist ? "that" : "this"} season, starters and relievers together. ERA is official (per-game earned runs from MLB game logs inside date windows; not available in a handedness split). FIP = (13·HR + 3·(BB+HBP) − 2·K) / IP + ${K().fipC}; SIERA is Swartz's 2011 formula shifted ${K().sieraShift >= 0 ? "+" : ""}${K().sieraShift} so the league averages its ${K().lgERA} ERA. Fastball velo averages four-seamers and sinkers. Lower ERA / FIP / SIERA / BB%, Z-Contact% and contact quality allowed count as better.`);
    return card;
  }

  // luck-neutral ERA breakdown: what each batted-ball type actually produced against him vs the league average
  // what his whiff rate and strike rate say the K% and BB% should be, next to the real ones
  function renderUnderlyingKBB(pv, st, noHead) {
    const box = el("div", "luck ukbb"), ik = st && st.ukbb;
    if (!noHead) box.append(el("h3", null, "Underlying K% and BB%"));
    if (!ik) { box.append(el("p", "note", "Needs Whiff% and Strike% against the season's population.")); return box; }
    const table = el("table", "ukbbt"), thead = el("thead"), tr = el("tr");
    for (const h of ["", "Expected", "Actual", "Diff"]) tr.append(el("th", h === "" ? "l" : null, h));
    thead.append(tr); table.append(thead);
    const tbody = el("tbody");
    // [label, caption (what drives the expectation), expected, actual, higher-is-better, isEra]
    const rows = [["K%", pv.m.whf == null ? "" : `from Whiff% ${pv.m.whf.toFixed(1)}${st.pct.whf == null ? "" : " · " + ordinal(st.pct.whf) + " pctl"}`, ik.k, pv.m.k, true, false],
                  ["BB%", pv.m.strk == null ? "" : `from Strike% ${pv.m.strk.toFixed(1)}${st.pct.strk == null ? "" : " · " + ordinal(st.pct.strk) + " pctl"}`, ik.bb, pv.m.bb, false, false],
                  ["K−BB%", "", st.ukb, pv.m.kbb, true, false],
                  ["ERA", "uERA: those rates, batted balls at league value", st.uera, pv.m.era, false, true]];
    for (const [what, cap, exp, act, hib, isEra] of rows) {
      const r = el("tr"); const d = act == null || exp == null ? null : (isEra ? Math.round(100 * (act - exp)) / 100 : Math.round(10 * (act - exp)) / 10);
      const good = d == null ? null : hib ? d > 0 : d < 0;
      const fv = (x) => (x == null ? "–" : isEra ? x.toFixed(2) : x.toFixed(1) + "%");
      const lc = el("td", "l"); lc.append(el("b", null, what)); if (cap) lc.append(el("small", null, cap));
      r.append(lc, el("td", null, fv(exp)), el("td", null, fv(act)),
               el("td", d == null ? null : Math.abs(d) < (isEra ? 0.25 : 1) ? "even" : good ? "lucky" : "unlucky", d == null ? "–" : (d > 0 ? "+" : "") + (isEra ? d.toFixed(2) : d.toFixed(1))));
      tbody.append(r);
    }
    table.append(tbody); box.append(table);
    box.append(el("p", "note", "Expected K% is his whiff rate; expected BB% is the walk rate at his Strike% percentile. Blue diff: results beat the process; red: they trail it."));
    return box;
  }
  function renderLuckTable(p, pv, noHead) {
    const c = K(), bbl = pv.ctx.bbl, box = el("div", "luck");
    const names = { gb: "Ground balls", ld: "Line drives", fb: "Fly balls", pu: "Popups" };
    const n = Object.values(bbl).reduce((s, x) => s + (x[0] || 0), 0);
    const head = el("h3", null, "Batted-ball luck");
    if (!noHead) box.append(head);
    const era = pv.m.era, nera = pv.m.nera;
    if (era != null && nera != null) {
      const diff = Math.round(100 * (era - nera)) / 100;
      const line = el("p", "luckline");
      line.append(el("b", null, `ERA ${era.toFixed(2)}`), " vs ", el("b", null, `luck-neutral ${nera.toFixed(2)}`), " — ",
                  el("span", diff < -0.15 ? "lucky" : diff > 0.15 ? "unlucky" : "even", diff < -0.15 ? `${Math.abs(diff).toFixed(2)} runs of good luck` : diff > 0.15 ? `${diff.toFixed(2)} runs of bad luck` : "about what his contact deserved"));
      box.append(line);
    }
    const table = el("table"), thead = el("thead"), tr = el("tr");
    for (const h of ["Type", "BIP", "Share", "wOBA allowed", "League", "Diff"]) tr.append(el("th", h === "Type" ? "l" : null, h));
    thead.append(tr); table.append(thead);
    const tbody = el("tbody");
    for (const t of ["gb", "ld", "fb", "pu"]) {
      const [cnt, w] = bbl[t] || [0, null], lg = c.bbw[t];
      const row = el("tr");
      row.append(el("td", "l", names[t]), el("td", null, cnt), el("td", null, n ? (100 * cnt / n).toFixed(1) + "%" : "–"), el("td", null, w == null ? "–" : fmtX(w)), el("td", null, fmtX(lg)));
      const d = w == null ? null : Math.round(1000 * (w - lg));
      const dc = el("td", d == null ? null : d > 15 ? "unlucky" : d < -15 ? "lucky" : null, d == null ? "–" : (d > 0 ? "+" : "") + d);
      row.append(dc); tbody.append(row);
    }
    table.append(tbody);
    const scroll = el("div", "rawscroll"); scroll.append(table); box.append(scroll);
    box.append(el("p", "note", `Luck-neutral ERA gives every ball in play the league's average wOBA for its type (ground ball ${fmtX(c.bbw.gb)}, line drive ${fmtX(c.bbw.ld)}, fly ball ${fmtX(c.bbw.fb)}, popup ${fmtX(c.bbw.pu)}) — so BABIP and HR/FB luck wash out while strikeouts, walks and a ground-ball profile keep their value — then puts that expected wOBA on the ERA scale around the league's ${c.lgERA} (wOBA scale ${c.wobaScale}, ${c.pa9} PA per nine). Diff is his wOBA allowed minus the league's, in points; red means the type has hurt him more than it should.`));
    return box;
  }
  // a pitcher's numbers measured against starters, relievers and all pitchers at once
  function renderPoolTable(p, ms) {
    const box = el("div", "cmp");
    box.append(el("h3", null, "Ranked as a starter, a reliever, and among all pitchers"));
    const table = el("table");
    const thead = el("thead"), hr = el("tr");
    hr.append(el("th", "l", "Pool"), el("th", null, "Score"));
    for (const m of ms) hr.append(el("th", null, SHORT[m.key] || m.label));
    hr.append(el("th", "l", "Rank"));
    thead.append(hr); table.append(thead);
    const tbody = el("tbody");
    for (const [g, label] of [["SP", "As a starter"], ["RP", "As a reliever"], ["P", "All pitchers"]]) {
      const r = rankIn(g, p), n = pool(g).ref.length;
      const tr = el("tr");
      const first = el("td", "l"); first.append(el("b", null, label), el("small", null, ` ${effMin(g)}+ IP ${DS.hist ? "that season" : "this season"} · ${n}`)); tr.append(first);
      const sc = el("td"); const sb = el("span", "pct", Math.round(r.score)); paint(sb, Math.round(r.score)); sc.append(sb); tr.append(sc);
      for (const m of ms) { const td = el("td"); const b = el("span", "pct", r.pct[m.key] ?? "–"); paint(b, r.pct[m.key]); td.append(b); tr.append(td); }
      tr.append(el("td", "l", r.outside ? `would be ${g}${r.rank} of ${n + 1}` : `${g}${r.rank} of ${n}` + (p.primary === g ? "" : "")));
      tbody.append(tr);
    }
    table.append(tbody);
    const wrap = el("div", "cmp-scroll"); wrap.append(table); box.append(wrap);
    box.append(el("p", "note", `Starters and relievers are classified by that season's usage (${p.ctx.GS} starts in ${p.ctx.G} games here). Pools use the Min IP set on each tab.`));
    return box;
  }

  /* ---------- player popup (Rankings / Draft / Trending) ---------- */
  function renderPlate(p, st, g, ref) {
    const plate = el("div", "mplate");
    plate.append(headshot(p.id, p.name));
    const txt = el("div");
    const h2 = el("h2", null, p.name); h2.id = "modal-title"; txt.append(h2);
    txt.append(el("div", "mline", `${p.team} · ${posLabel(p)}${p.type === "P" ? " · " + p.throws + "HP" : p.bats ? " · " + p.bats : ""} · ${dsSeason()}${p.age != null ? " · age " + p.age : ""}`));
    const v = V(p);
    const r = el("div", "mrank");
    if (st.pct) r.append(el("b", null, p.type === "P" ? fmtIP(v.ip) + " IP" : v.pa + " PA"), el("span", null, ` · ${viewLabel(p.type)}`));
    txt.append(r);
    txt.append(renderStarControl(p));
    plate.append(txt);
    if (state.mode === "draft") {
      const drafted = draftedIds().has(p.id);
      const b = el("button", "draftbtn", drafted ? "Undo draft" : "Draft"); b.type = "button";
      b.addEventListener("click", () => { drafted ? undraft(p.id) : draft(p); });
      plate.append(b);
    }
    return plate;
  }
  // season chips for the popup (from the search index): the same player in another year
  function renderSeasonChips(p0) {
    const wrap = el("div", "xseasons mchips");
    ensureIndex();
    const entry = indexReady() ? window.DRAFT_INDEX.players.find((e) => e.id === p0.id) : null;
    if (!entry) { wrap.append(el("span", "winnote", indexReady() ? "" : "Loading seasons…")); return wrap; }
    const curKey = state.cardDs || CUR.key;
    wrap.append(el("span", "splbl", "Season"));
    const goTo = (key) => { state.cardDs = key === CUR.key ? null : key; state.cardWin = { from: "", to: "", last: "" }; render(); };
    if (isMulti(curKey)) {   // a combined span: say so, and offer the seasons that make it up
      const mp = parseMulti(curKey), mine = entry.s.filter((sv) => sv[2] === p0.type && mp.members.includes(sv[0]));
      wrap.append(pillSelect(`${yearSpan(mp.years)} combined`, [[curKey, `${yearSpan(mp.years)} combined`], ...mine.map((sv) => [sv[0], `${sv[1]}${kindTag(sv[0])} · ${sv[5]}`])], curKey, (k) => { if (k !== curKey) goTo(k); }, "Season"));
      return wrap;
    }
    wrap.append(renderSeasonPicker(entry.s.filter((sv) => sv[2] === p0.type), curKey, goTo));
    return wrap;
  }
  function renderAddPos(p) {
    const box = el("div", "addpos");
    const have = eligiblePositions(p), added = addedPos(p);
    for (const x of added) { const t = el("span", "tag", x); const b = el("button", "unadd", "×"); b.type = "button"; b.title = `Remove ${x}`; b.addEventListener("click", (e) => { e.stopPropagation(); removePos(p.id, x); render(); }); t.append(b); box.append(t); }
    const opts = (p.type === "H" ? HIT_TABS.slice(1) : ["SP", "RP"]).filter((x) => !have.includes(x));
    if (opts.length) {
      const sel = el("select"); sel.setAttribute("aria-label", "Position to add");
      const o0 = el("option", null, "Add position…"); o0.value = ""; sel.append(o0);
      for (const x of opts) { const o = el("option", null, x); o.value = x; sel.append(o); }
      sel.addEventListener("click", (e) => e.stopPropagation());
      sel.addEventListener("change", (e) => { if (e.target.value) { addPos(p, e.target.value); render(); } });
      box.append(sel);
    }
    return box;
  }
  function renderEligibility() {
    const box = $("eboard"); box.innerHTML = "";
    // add a position: find a player, then pick from what he hasn't earned
    const adder = el("div", "eadder");
    adder.append(el("h3", null, "Add a position"));
    const row = el("div", "prow");
    const search = el("div", "xsearch"); const inp = el("input"); inp.type = "search"; inp.placeholder = "Find a player on this season's board…"; inp.autocomplete = "off"; inp.value = state.eq || "";
    const hits = el("ul", "addlist xlist"); hits.hidden = true; search.append(inp, hits); row.append(search);
    const draw = () => {
      hits.innerHTML = ""; const q = (state.eq || "").trim().toLowerCase();
      const found = q.length < 2 ? [] : DATA.players.filter((p) => p.name.toLowerCase().includes(q)).slice(0, 8);
      hits.hidden = !found.length;
      for (const p of found) {
        const li = el("li"); const b = el("button", null); b.type = "button"; b.append(el("b", null, p.name), ` ${p.team} · ${p.type === "P" ? pitcherRoles(p).join(", ") : eligiblePositions(p).join(", ")}`);
        b.addEventListener("click", () => { state.epick = p.id; state.eq = ""; render(); }); li.append(b); hits.append(li);
      }
    };
    inp.addEventListener("input", () => { state.eq = inp.value; draw(); });
    draw();
    const pick = state.epick ? DATA.players.find((p) => p.id === state.epick) : null;
    if (pick) { const who = el("div", "epick"); who.append(el("b", null, pick.name), ` ${pick.team} · earned: ${pick.type === "P" ? pitcherRoles(pick).join(", ") : eligiblePositions(pick).join(", ")}`, renderAddPos(pick)); row.append(who); }
    adder.append(row); box.append(adder);
    const ids = Object.keys(state.extraPos);
    if (!ids.length) { box.append(Object.assign(el("p", "xempty"), { innerHTML: "No added positions yet.<br><b>Find a player above</b> and add a position to extend his 2027 eligibility; it shows up here." })); return; }
    const list = el("div", "elist");
    for (const id of ids) {
      const p = DATA.players.find((q) => q.id === Number(id)) || { id: Number(id), name: `Player ${id}`, team: "", type: "H", pos: {}, ctx: {} };
      const row = el("div", "erow");
      row.append(headshot(p.id, p.name));
      const mid = el("div"); mid.append(el("div", "ename", p.name));
      const nat = p.type === "P" ? pitcherRoles({ ...p, id: -1 }).join(", ") : eligiblePositions({ ...p, id: -1 }).join(", ");
      mid.append(el("div", "emeta", `${p.team} · earned: ${nat}`)); row.append(mid);
      const tags = el("div", "addpos");
      for (const x of state.extraPos[id]) { const t = el("span", "tag", x); const b = el("button", "unadd", "×"); b.type = "button"; b.title = `Remove ${x}`; b.addEventListener("click", () => { removePos(Number(id), x); render(); }); t.append(b); tags.append(t); }
      row.append(tags); list.append(row);
    }
    box.append(list);
  }
  function renderTextModal() {
    const modal = $("modal"), body = $("modal-body"), tm = state.textModal;
    modal.hidden = false; document.body.classList.add("modal-open"); parkControls(); body.innerHTML = "";
    const w = el("div", "textmodal");
    const h2 = el("h2", null, tm.title); h2.id = "modal-title"; w.append(h2);
    if (tm.hint) w.append(el("p", "note", tm.hint));
    const row = el("div", "row");
    const close = () => { state.textModal = null; render(); };
    if (tm.ask) {                                        // confirm / prompt replacement
      let inp = null;
      if (tm.input) { inp = el("input", "dlginput"); inp.type = "text"; inp.value = tm.input.value || ""; inp.placeholder = tm.input.placeholder || ""; inp.maxLength = 60; w.append(inp); }
      const ok = el("button", "btn", tm.input ? (tm.input.button || "Save") : "Yes"); ok.type = "button";
      ok.addEventListener("click", () => { const v = inp ? inp.value.trim() : true; if (inp && !v) { inp.focus(); return; } state.textModal = null; tm.onSubmit(v); });
      if (inp) inp.addEventListener("keydown", (e) => { if (e.key === "Enter") ok.click(); });
      const no = el("button", "btn btn-quiet", tm.input ? "Cancel" : "No"); no.type = "button"; no.addEventListener("click", close);
      row.append(ok, no); w.append(row); body.append(w);
      if (inp) setTimeout(() => inp.focus(), 0);
      return;
    }
    const ta = el("textarea"); ta.value = tm.text; ta.readOnly = !tm.onSubmit; w.append(ta);
    const checks = {};
    for (const [k, label] of Object.entries((tm.opts || {}))) { const l = el("label", "toggle"); const c = el("input"); c.type = "checkbox"; c.checked = true; checks[k] = c; l.append(c, " ", label); w.append(l); }
    if (tm.onSubmit) { const b = el("button", "btn", "Import"); b.type = "button"; b.addEventListener("click", () => tm.onSubmit(ta.value, Object.fromEntries(Object.entries(checks).map(([k, c]) => [k, c.checked])))); row.append(b); }
    else { const b = el("button", "btn", "Copy to clipboard"); b.type = "button"; b.addEventListener("click", async () => { try { await navigator.clipboard.writeText(ta.value); b.textContent = "Copied"; } catch { ta.select(); } }); row.append(b); }
    const c = el("button", "btn btn-quiet", "Close"); c.type = "button"; c.addEventListener("click", close); row.append(c);
    w.append(row); body.append(w);
  }
  function renderTierPick() {
    const modal = $("modal"), body = $("modal-body");
    const full = visiblePlayers({ all: true }).list;
    const keys = full.map((q) => q.type + q.id).filter((k) => state.selKeys.includes(k));
    if (!keys.length) { state.tierPick = null; modal.hidden = true; return; }
    modal.hidden = false; document.body.classList.add("modal-open"); parkControls(); body.innerHTML = "";
    const w = el("div", "textmodal tierpick");
    const who = keys.map((k) => full.find((q) => q.type + q.id === k).name);
    const h2 = el("h2", null, keys.length === 1 ? `Move ${who[0]} to a tier` : `Move ${keys.length} players to a tier`); h2.id = "modal-title"; w.append(h2);
    if (keys.length > 1) w.append(el("p", "note", who.slice(0, 12).join(", ") + (who.length > 12 ? ` +${who.length - 12} more` : "")));
    const tiers = tierLists(), idx = tierIndex(tiers), names = state.tierNames[state.pos] || [];
    const cur = keys.length === 1 ? (idx.has(keys[0]) ? idx.get(keys[0]) : tiers.length) : -1;
    const choice = (label, sub, onPick, isCur) => {
      const b = el("button", "tierchoice"); b.type = "button"; b.setAttribute("aria-pressed", String(isCur));
      b.append(el("b", null, label)); if (sub) b.append(el("span", null, sub));
      b.addEventListener("click", () => { state.tierPick = null; onPick(); });
      w.append(b);
    };
    tiers.forEach((l, t) => {
      const members = full.filter((q) => idx.get(q.type + q.id) === t).map((q) => q.name.split(" ").slice(-1)[0]), n = members.length;
      const sub = n ? members.slice(0, 8).join(", ") + (n > 8 ? ` +${n - 8} more` : "") : "empty";
      choice(`Tier ${t + 1}${names[t] ? " · " + names[t] : ""}`, sub, () => moveSelectionToTier(t + 1), t === cur);
    });
    choice("Not tiered", `${full.filter((q) => !idx.has(q.type + q.id)).length} players`, () => moveSelectionToTier(0), cur === tiers.length);
    const row = el("div", "row");
    const nb = el("button", "btn", keys.length === 1 ? "New tier with him" : `New tier with these ${keys.length}`); nb.type = "button";
    nb.addEventListener("click", () => { state.tierPick = null; moveSelectionToTier("new"); });
    row.append(nb);
    if (keys.length === 1) { const tb = el("button", "btn btn-quiet", `+ Tier below ${who[0].split(" ").slice(-1)[0]}`); tb.type = "button"; tb.title = "New tier boundary right below him: the players below him in his section become the next tier"; tb.addEventListener("click", () => { state.tierPick = null; state.selKeys = []; tierBelow(keys[0]); }); row.append(tb); }
    const cb = el("button", "btn btn-quiet", "Cancel"); cb.type = "button"; cb.addEventListener("click", () => { state.tierPick = null; render(); });
    row.append(cb); w.append(row); body.append(w);
  }
  function renderModal() {
    if (state.textModal) { renderTextModal(); return; }
    if (state.tierPick && state.mode === "rankings" && state.editRanks && state.selKeys.length) { renderTierPick(); return; }
    const listNow = ["rankings", "draft", "trending", "leaderboard"].includes(state.mode);
    if (state.panel === "splits" && listNow) { renderSplitsPanel(); return; }
    if (state.panel === "stats" && listNow) { renderColPick(); return; }
    if (state.panel === "table" && listNow) { renderTablePanel(); return; }
    if (state.panel === "team" && listNow) { renderTeamPanel(); return; }
    if (state.panel === "lists" && state.mode === "rankings") { renderListsPanel(); return; }
    if (state.panel === "cmpstats" && state.mode === "compare") { renderCmpPick(); return; }
    if (state.panel) { state.panel = null; parkControls(); }
    state.colPick = false;
    state.tierPick = null;
    const modal = $("modal"), body = $("modal-body");
    const key = state.expanded;
    const listMode = ["rankings", "draft", "trending", "leaderboard", "fantasy"].includes(state.mode);
    const src = state.cardDs && histDataset(state.cardDs) ? histDataset(state.cardDs).players : DATA.players;
    const p0 = key && listMode ? (src.find((q) => q.type + q.id === key) || DATA.players.find((q) => q.type + q.id === key)) : null;
    modal.hidden = !p0; document.body.classList.toggle("modal-open", !!p0);
    parkControls(); body.innerHTML = "";
    if (!p0) return;
    // which season: the current one (list pool + Rank vs apply) or another year from the chips
    const dsKey = state.cardDs || CUR.key;
    if (dsKey !== CUR.key) ensureHist(dsKey);
    const ds = histDataset(dsKey);
    if (!ds) { body.append(renderPlate(p0, { rank: "–" }, "H", "H"), renderSeasonChips(p0), el("p", "note", `Loading ${dsKey.startsWith("mlb-") ? dsKey.slice(4) : dsKey.replace("aaa-", "") + " Triple-A"} season…`)); return; }
    withDataset(ds, () => withWindow(state.cardWin, () => withSplit(state.split, () => {
      const p = ds.players.find((q) => q.id === p0.id && q.type === p0.type) || p0;
      const g = ds === CUR ? groupFor(state.pos) : (p.type === "H" ? "H" : p.primary);
      const ref = ds === CUR ? refFor(g) : g;
      if (needsRows() && !DS.ready()) { DS.load(); body.append(renderPlate(p, { rank: "–" }, g, ref), renderSeasonChips(p0)); const c = el("div", "card"); c.append(renderSplitBar(p), el("p", "note", "Loading game-by-game data…")); body.append(c); return; }
      const st = ref === g ? (pool(g).stats.get(p.type + p.id) || rankIn(g, p)) : rankIn(ref, p);
      body.append(renderPlate(p, st, g, ref));
      body.append(renderSeasonChips(p0));
      body.append(renderCard(p, metricsFor(g), st, g, ref));
    })));
  }

  /* ---------- draft actions ---------- */
  function draft(p) {
    state.drafted.push({ id: p.id, name: p.name, t: Date.now() });
    save(LS.drafted, state.drafted); if (state.expanded === p.type + p.id && !state.showDrafted) state.expanded = null; render();
  }
  function undraft(id) { state.drafted = state.drafted.filter((d) => d.id !== id); save(LS.drafted, state.drafted); render(); }
  function undoLast() { state.drafted.pop(); save(LS.drafted, state.drafted); render(); }
  function resetBoard() {
    if (!state.drafted.length) return;
    ask("Reset the draft board?", `Returns all ${state.drafted.length} drafted players to the board.`, () => { state.drafted = []; save(LS.drafted, state.drafted); render(); });
  }

  // the Leaderboard's dataset: one season, or the span from the season picked to "to"
  const keyYear = (key) => Number(key.split("-")[1]);
  function lbKey() {
    const base = state.lbDs || CUR.key; if (!state.lbTo) return base;
    const y = keyYear(base); if (!(state.lbTo > y)) return base;
    return multiKey(levelOf(base), y, state.lbTo, keyKind(base), state.lbEach);
  }
  const lbMulti = () => state.mode === "leaderboard" && isMulti(lbKey());
  function renderLbTools() {
    const on = state.mode === "leaderboard"; $("lbtools").hidden = !on; if (!on) return;
    const g = groupFor(state.pos);
    // splits: vs L / R and home / away
    const pit = isPitcherGroup(g), sp = $("lbsplit"); sp.innerHTML = "";
    const seg = (name, opts, cur, set) => {
      const s = el("div", "seg"); s.setAttribute("role", "group"); s.setAttribute("aria-label", name);
      for (const [v, l] of opts) { const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(cur === v)); b.addEventListener("click", () => { if (cur !== v) { set(v); state.expanded = null; render(); } }); s.append(b); }
      return s;
    };
    sp.append(seg("Handedness", [["all", pit ? "All batters" : "All pitchers"], ["L", pit ? "vs LHB" : "vs LHP"], ["R", pit ? "vs RHB" : "vs RHP"]], state.lbSplit.hand, (v) => (state.lbSplit.hand = v)));
    sp.append(seg("Venue", [["all", "Home + away"], ["home", "Home"], ["away", "Away"]], state.lbSplit.venue, (v) => (state.lbSplit.venue = v)));
    // season picker: every built season and level, from the index
    ensureIndex();
    const box = $("lbseason"); box.innerHTML = "";
    const keys = indexReady() ? window.DRAFT_INDEX.seasons : [CUR.key];
    const cur = state.lbDs && keys.includes(state.lbDs) ? state.lbDs : CUR.key;
    const year = (k) => Number(k.split("-")[1]);
    const years = [...new Set(keys.map(year))].sort((x, y) => y - x);
    const inYear = (y) => keys.filter((k) => year(k) === y).sort((p, q) => LEVEL_ORDER.indexOf(levelOf(p)) - LEVEL_ORDER.indexOf(levelOf(q)));
    const pick = (k) => { state.lbDs = k === CUR.key ? null : k; if (state.lbTo && state.lbTo <= year(k)) state.lbTo = null; state.win = { from: "", to: "", last: "" }; state.expanded = null; savePrefs(); render(); };
    box.append(el("span", "splbl", "Season"));
    box.append(pillSelect(String(year(cur)), years.map((y) => [String(y), String(y)]), String(year(cur)), (y) => { const opts = inYear(Number(y)); pick((opts.find((k) => levelOf(k) === levelOf(cur) && !keyKind(k)) || opts.find((k) => levelOf(k) === levelOf(cur)) || opts[0])); }, "Season"));
    // "to": a later year at the same level and game type makes the list a span of seasons
    const later = years.filter((y) => y > year(cur) && keys.includes(`${levelOf(cur)}-${y}${keyKind(cur) ? "-" + keyKind(cur) : ""}`)).sort((x, y) => x - y);
    if (later.length) {
      const to = state.lbTo && later.includes(state.lbTo) ? state.lbTo : null;
      box.append(el("span", "splbl", "to"));
      const toPill = pillSelect(to ? String(to) : "—", [["", "— (one season)"], ...later.map((y) => [String(y), String(y)])], to ? String(to) : "", (y) => { state.lbTo = y ? Number(y) : null; state.win = { from: "", to: "", last: "" }; state.expanded = null; savePrefs(); render(); }, "Through");
      toPill.classList.add("topill"); if (!to) toPill.classList.add("solo"); box.append(toPill);
      if (to) {
        const seg = el("div", "seg kindseg"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Span");
        for (const [v, l, t] of [[false, "Combined", "One line per player: every season in the span added together"], [true, "Each season", "Every player-season on its own line"]]) {
          const b = el("button", "segbtn small", l); b.type = "button"; b.title = t; b.setAttribute("aria-pressed", String(state.lbEach === v));
          b.addEventListener("click", () => { if (state.lbEach !== v) { state.lbEach = v; state.expanded = null; savePrefs(); render(); } }); seg.append(b);
        }
        box.append(seg);
      }
    }
    const lv = inYear(year(cur)).filter((k) => !keyKind(k) || k === cur);          // one entry per level; the game type is its own control
    const lvPill = pillSelect((LEVEL_NAMES[levelOf(cur)] || levelOf(cur)) + kindTag(cur), lv.map((k) => [k, (LEVEL_NAMES[levelOf(k)] || levelOf(k)) + kindTag(k)]), cur, pick, "Level");
    lvPill.classList.add("lvl"); if (lv.length === 1) lvPill.classList.add("solo");
    box.append(lvPill);
    // regular season / spring training / postseason for this year and level, where built
    const kinds = keys.filter((k) => keyBase(k) === keyBase(cur));
    if (kinds.length > 1) {
      const seg = el("div", "seg kindseg"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Games");
      for (const [kk, l] of KINDS) {
        const k = kinds.find((x) => keyKind(x) === kk); if (!k) continue;
        const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(k === cur));
        b.addEventListener("click", () => { if (k !== cur) pick(k); }); seg.append(b);
      }
      box.append(seg);
    }
  }
  // the Leaderboard's column picker: every card metric, grouped as on the card
  function renderColPick() {
    parkControls();                                   // the shared controls must be out of the modal before it is cleared
    const modal = $("modal"), body = $("modal-body"); modal.hidden = false; document.body.classList.add("modal-open"); body.innerHTML = "";
    const g = groupFor(state.pos), pit = isPitcherGroup(g), key = pit ? "P" : "H";
    const w = el("div", "textmodal colpick");
    const h2 = el("h2", null, `Included stats · ${pit ? "pitchers" : "hitters"}`); h2.id = "modal-title"; w.append(h2);
    // sort by: the same select the header clicks drive
    const sortRow = el("div", "prow"), sf = $("sortfield"); sf.hidden = customOrder(); sortRow.append(sf); w.append(sortRow);
    if (customOrder()) w.append(el("p", "note", "This tab has a saved order of its own, so it isn't sorted by a stat — the order is the order."));
    w.append(el("p", "note", `Tick the stats to show on ${{ rankings: "Rankings", draft: "the Draft board", trending: "Trending", leaderboard: "the Leaderboard" }[state.mode] || "this page"}${state.mode === "leaderboard" ? "; the value shows in each cell, coloured by its percentile" : ""}. Clicking a column heading on the board also sorts by it.`));
    const drawOrder = () => {};                       // the column order lives in the Table panel
    const groups = (pit ? CARD_P : CARD).map((grp) => ({ group: grp.group, metrics: grp.metrics.flatMap((m) => [m, ...((pit ? SUB_P : SUB)[m.key] || [])]) }));
    const seen = new Set();
    const grid = el("div", "colgrid");
    { // Year and Age always sit right after the name
      const sec = el("div", "colgroup"); sec.append(el("h4", null, "Player"));
      const multi = state.mode === "leaderboard" && isMulti(lbKey());
      for (const [k, label, hint] of [["year", "Year", multi ? "" : " (on by itself when the list spans seasons)"], ["age", "Age", ""]]) {
        const l = el("label", "toggle"); const c = el("input"); c.type = "checkbox"; c.checked = preCols().some((x) => x.key === k);
        c.addEventListener("change", () => { state.pre[k] = c.checked; ensureSortValid(); renderSortSelect(); renderColhead(); renderRows(); renderToolSummary(); });
        l.append(c, " ", label + hint); sec.append(l);
      }
      grid.append(sec);
    }
    for (const grp of groups) {
      const sec = el("div", "colgroup"); sec.append(el("h4", null, grp.group));
      for (const m of grp.metrics) {
        if (seen.has(m.key)) continue; seen.add(m.key);
        const l = el("label", "toggle"); const c = el("input"); c.type = "checkbox"; c.checked = colKeys(g).includes(m.key);
        c.addEventListener("change", () => { const cur = colKeys(g).filter((k) => k !== m.key); if (c.checked) cur.push(m.key); setColKeys(g, cur); ensureSortValid(); drawOrder(); renderColhead(); renderRows(); renderToolSummary(); });
        l.append(c, " ", m.label); sec.append(l);
      }
      grid.append(sec);
    }
    w.append(grid);
    const row = el("div", "row");
    const all = el("button", "btn btn-quiet", "Reset to defaults"); all.type = "button"; all.addEventListener("click", () => { if (state.mode === "leaderboard") state.lb[key] = key === "P" ? ["whf", "strk", "gb", "k", "bb", "kbb", "ukb", "era", "nera", "uera", "siera", "fip", "fbv"] : ["woba", "ev", "brl", "hh", "pull", "air", "gb", "zsw", "osw", "whf", "k", "bb"]; else if (state.cols[state.mode]) delete state.cols[state.mode][key]; savePrefs(); render(); });
    const done = el("button", "btn", "Done"); done.type = "button"; done.addEventListener("click", () => closePanel(false));
    const cancel = el("button", "btn btn-quiet", "Cancel"); cancel.type = "button"; cancel.title = "Close without keeping these changes"; cancel.addEventListener("click", () => closePanel(true));
    row.append(done, cancel, all); w.append(row); body.append(w);
  }
  function renderTrendTools() {
    const on = state.mode === "trending";
    $("trendtools").hidden = !on; $("winnote").hidden = on;
    if (!on) return;
    const g = groupFor(state.pos), pit = isPitcherGroup(g), t = trendCfg();
    const n = $("trendn"); if (document.activeElement !== n) n.value = t[t.unit]; n.step = t.unit === "days" ? 1 : pit ? 5 : 25;
    const seg = $("trendunit"); seg.innerHTML = "";
    for (const [v, l] of [[pit ? "ip" : "pa", pit ? "innings" : "plate appearances"], ["days", "days"]]) {
      const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(t.unit === v));
      b.addEventListener("click", () => { if (t.unit !== v) { t.unit = v; savePrefs(); state.expanded = null; render(); } }); seg.append(b);
    }
    const mn = $("trendmin"); if (document.activeElement !== mn) mn.value = trendMin(); mn.step = pit ? 5 : 10; mn.title = `Only players with this much playing time inside the span (${t.unit === "days" ? "the last " + t.days + " days" : "his last " + t[t.unit] + " " + (pit ? "IP" : "PA")})`;
    $("trendminunit").textContent = (pit ? "IP" : "PA") + " in that span";
    $("trendchip").textContent = pit ? "Score = Whiff% + Strike% pctl" : `Hot bats · by ${HEAD.label}`;
    const w = winIdx();
    $("trendnote").textContent = state.daysLoading ? "Loading game-by-game data…" : w ? (w.last ? `each player's ${winLabel()}` : `${winLabel()} · ${w.hi - w.lo + 1} game days`) : "full season";
  }
  function renderRankTools() {
    const on = state.mode === "rankings";
    $("ranktools").hidden = !on;
    if (!on) return;
    const n = (state.ranks[state.pos] || []).length, tn = (state.tiers[state.pos] || []).length;
    const tabLabel = TAB_LABEL[state.pos] || state.pos, tierTxt = tn ? ` · ${tn} tier${tn === 1 ? "" : "s"}` : "";
    $("rankcount").textContent = n || tn ? `${tabLabel}${tierTxt}` : `${tabLabel} · model order`;
    $("rankedit").textContent = state.editRanks ? "Done editing" : "Edit rankings";
    const ns0 = Object.keys(listStars()).length; $("rankstars").textContent = state.starOnly ? `★ Starred only (${ns0})` : `☆ Starred (${ns0})`; $("rankstars").classList.toggle("on", state.starOnly); $("rankstars").hidden = !ns0 && !state.starOnly;
    $("rankedit").classList.toggle("btn-quiet", state.editRanks);
    $("rankaddtier").hidden = !state.editRanks; $("rankreset").hidden = !state.editRanks;
    const bottom = state.editRanks && selBottom(), bp = bottom && DATA.players.find((q) => q.type + q.id === bottom);
    $("rankaddtier").textContent = bp ? `+ Tier below ${bp.name.split(" ").slice(-1)[0]}` : "+ Add tier";
    $("rankaddtier").title = bp ? `New tier boundary right below ${bp.name}: he and everyone above him in his section stay together, the players below him become the next tier` : "Add an empty tier at the bottom";
    const ns = state.selKeys.length;
    $("rankmove").hidden = !state.editRanks; $("rankmove").disabled = !ns; $("rankmove").textContent = ns ? `Move ${ns} to tier…` : "Move to tier…";
    $("rankclear").hidden = !state.editRanks || !ns;
    const idx = tierIndex(tierLists());
    $("rankuntier").hidden = !state.editRanks; $("rankuntier").disabled = !state.selKeys.some((k) => idx.has(k));
    renderViewSeg("rankview", tn > 0);
    $("rankreset").disabled = !(n || tn);
  }
  /* saved sets: the working rankings can be opened from a set, edited, and saved back to it without renaming */
  const deep = (o) => JSON.parse(JSON.stringify(o));
  const currentSetName = () => (state.currentSet && state.rankSets[state.currentSet] ? state.currentSet : null);
  const hasWorking = () => !!(Object.keys(state.ranks).length || Object.keys(state.tiers).length || Object.keys(state.stars).length);
  // ---- stars: a player starred on a rankings list, with a note explaining the call ----
  // "" = the list that's open (or the unsaved working list); a saved list's name writes straight into that list
  const starsOf = (name) => (name ? ((state.rankSets[name] || {}).stars || {}) : state.stars);
  function setStar(name, key, note) {
    if (name) { const sset = state.rankSets[name]; if (!sset) return; sset.stars = sset.stars || {}; if (note == null) delete sset.stars[key]; else sset.stars[key] = { note, at: new Date().toISOString() }; save(LS.sets, state.rankSets); }
    else { if (note == null) delete state.stars[key]; else state.stars[key] = { note, at: new Date().toISOString() }; save(LS.stars, state.stars); }
  }
  // every list this player is starred on: [[listName or "", star]]
  const starredOn = (key) => [["", state.stars[key]], ...Object.keys(state.rankSets).sort().map((n) => [n, starsOf(n)[key]])].filter(([, v]) => v);
  const listLabel = (name) => (name ? name : currentSetName() ? `${currentSetName()} (open)` : "Working list (unsaved)");
  // the stars the list on screen uses: the working list's, or the saved list the Draft page draws from
  function listStars() { const src = orderSource(); if (!src) return state.stars; return src.live ? state.stars : (state.draftOrder.startsWith("set:") ? starsOf(state.draftOrder.slice(4)) : state.stars); }
  function renderStarControl(p) {
    const key = p.type + p.id, box = el("div", "starbox");
    const on = starredOn(key), here = state.stars[key];
    const b = el("button", "starbtn" + (on.length ? " on" : ""), (on.length ? "★ " : "☆ ") + (on.length ? `Starred${on.length > 1 ? " ×" + on.length : ""}` : "Star")); b.type = "button";
    b.title = on.length ? on.map(([n, v]) => `${listLabel(n)}: ${v.note || "(no note)"}`).join("\n") : "Star this player on a rankings list, with a note";
    b.addEventListener("click", (e) => { e.stopPropagation(); state.starOpen = state.starOpen === key ? null : key; render(); });
    box.append(b);
    if (here && here.note && state.starOpen !== key) box.append(el("span", "starnote", here.note));
    if (state.starOpen === key) {
      const panel = el("div", "starpanel"); panel.addEventListener("click", (e) => e.stopPropagation());
      const sel = el("select"); const names = Object.keys(state.rankSets).sort();
      for (const [v, l] of [["", listLabel("")], ...names.filter((n) => n !== currentSetName()).map((n) => [n, n])]) { const o = el("option", null, l + (starsOf(v)[key] ? " ★" : "")); o.value = v; sel.append(o); }
      sel.value = state.starList && (state.starList === "" || state.rankSets[state.starList]) ? state.starList : "";
      const ta = el("textarea"); ta.rows = 3; ta.placeholder = "Why he's here — the note shows on the Rankings page";
      const fill = () => { const st = starsOf(sel.value)[key]; ta.value = st ? st.note || "" : ""; };
      fill(); sel.addEventListener("change", () => { state.starList = sel.value; fill(); });
      const row = el("div", "fbtns");
      const sv = el("button", "btn", "Save star"); sv.type = "button"; sv.addEventListener("click", () => { setStar(sel.value, key, ta.value.trim()); state.starOpen = null; render(); });
      const rm = el("button", "btn btn-quiet", "Remove star"); rm.type = "button"; rm.disabled = !starsOf(sel.value)[key]; rm.addEventListener("click", () => { setStar(sel.value, key, null); state.starOpen = null; render(); });
      const cx = el("button", "btn btn-quiet", "Cancel"); cx.type = "button"; cx.addEventListener("click", () => { state.starOpen = null; render(); });
      row.append(sv, rm, cx);
      const lbl = el("label", "field"); lbl.append(el("span", null, "On list"), sel);
      panel.append(lbl, ta, row);
      box.append(panel);
    }
    return box;
  }
  const canon = (o) => JSON.stringify(Object.keys(o || {}).sort().filter((k) => o[k] && (!Array.isArray(o[k]) || o[k].length)).map((k) => [k, o[k]]));
  const snapshot = () => ({ ranks: deep(state.ranks), tiers: deep(state.tiers), tierNames: deep(state.tierNames), stars: deep(state.stars), saved: new Date().toISOString() });
  function setDirty() {
    const s = state.rankSets[currentSetName()]; if (!s) return false;
    return canon(state.ranks) !== canon(s.ranks) || canon(state.tiers) !== canon(s.tiers) || canon(state.tierNames) !== canon(s.tierNames) || canon(state.stars) !== canon(s.stars || {});
  }
  let flashTimer;
  function flash(msg) { state.flash = msg; render(); clearTimeout(flashTimer); flashTimer = setTimeout(() => { state.flash = ""; render(); }, 4000); }
  function saveCurrent() {
    const cur = currentSetName(); if (!cur) return saveAs();
    state.rankSets[cur] = snapshot(); save(LS.sets, state.rankSets); flash(`Saved “${cur}”`);
  }
  function saveAs() {
    const cur = currentSetName();
    ask(cur ? "Save a copy as…" : "Save these rankings", "Every tab's order, tiers and tier names, under one name. You'll find it under Saved rankings here and under Draft from on the Draft page.", (name) => {
      const write = () => { state.rankSets[name] = snapshot(); save(LS.sets, state.rankSets); state.currentSet = name; savePrefs(); flash(`Saved “${name}”`); };
      if (state.rankSets[name] && name !== cur) ask(`Replace “${name}”?`, "A saved set already has that name; its rankings will be overwritten.", write); else write();
    }, { value: cur ? `${cur} copy` : `Rankings ${new Date().toISOString().slice(0, 10)}`, placeholder: "Set name", button: "Save" });
  }
  function openSet(name) {
    const s = state.rankSets[name]; if (!s) return;
    const go = () => {
      state.ranks = deep(s.ranks || {}); state.tiers = deep(s.tiers || {}); state.tierNames = deep(s.tierNames || {}); state.stars = deep(s.stars || {});
      save(LS.ranks, state.ranks); save(LS.tiers, state.tiers); save(LS.tierNames, state.tierNames); save(LS.stars, state.stars);
      state.currentSet = name; savePrefs(); flash(`Opened “${name}”`);
    };
    const cur = currentSetName();
    if (cur === name && !setDirty()) { render(); return; }
    const unsaved = cur ? setDirty() : hasWorking();
    if (!unsaved) return go();
    ask(`Open “${name}”?`, cur ? `Unsaved changes to “${cur}” will be lost — Cancel and press Save to keep them.` : "Your working rankings aren't saved under a name and will be replaced — Cancel and use Save… to keep them.", go);
  }
  function renameSet(old) {
    ask(`Rename “${old}”`, "", (name) => {
      if (name === old) { render(); return; }
      if (state.rankSets[name]) { flash(`“${name}” already exists`); return; }
      state.rankSets[name] = state.rankSets[old]; delete state.rankSets[old]; save(LS.sets, state.rankSets);
      if (state.currentSet === old) state.currentSet = name;
      if (state.draftOrder === "set:" + old) state.draftOrder = "set:" + name;
      savePrefs(); flash(`Renamed to “${name}”`);
    }, { value: old, placeholder: "Set name", button: "Rename" });
  }
  function deleteSet(name) {
    ask(`Delete “${name}”?`, "The saved set is removed; your working rankings stay as they are.", () => {
      delete state.rankSets[name]; save(LS.sets, state.rankSets);
      if (state.currentSet === name) state.currentSet = null;
      if (state.draftOrder === "set:" + name) state.draftOrder = "board";
      savePrefs(); flash(`Deleted “${name}”`);
    });
  }
  // the list bar: which saved list is open (a picker), whether it's saved, and Save / Save as / New / Rename / Delete
  function renderSetBar() {
    const bar = $("setbar"); bar.hidden = state.mode !== "rankings"; if (bar.hidden) return;
    const cur = currentSetName(), dirty = cur ? setDirty() : false, working = hasWorking();
    const names = Object.keys(state.rankSets).sort((x, y) => x.localeCompare(y));
    const sel = $("setpick"); sel.innerHTML = "";
    const o0 = el("option", null, cur ? "＋ New list…" : working ? "New list (not saved yet)" : "New list"); o0.value = "new"; sel.append(o0);
    if (names.length) { const grp = el("optgroup"); grp.label = "Saved lists"; for (const n of names) { const o = el("option", null, n); o.value = "set:" + n; grp.append(o); } sel.append(grp); }
    sel.value = cur ? "set:" + cur : "new";
    sel.title = cur ? `Editing “${cur}” — pick another saved list, or start a new one` : names.length ? "Pick a saved list to edit it" : "Save this list to see it here";
    const st = $("setstatus"); st.className = "setstatus";
    if (state.flash) { st.textContent = state.flash; st.classList.add("ok"); }
    else if (cur && dirty) { st.textContent = `Unsaved changes to “${cur}”`; st.classList.add("dirty"); }
    else if (cur) { const s = state.rankSets[cur]; st.textContent = `Saved${s.saved ? " " + fmtDate(s.saved.slice(0, 10)) : ""} — every tab's order and tiers`; st.classList.add("ok"); }
    else if (working) { st.textContent = "Not saved yet — Save… keeps this list under a name"; st.classList.add("dirty"); }
    else st.textContent = "Order a tab, then Save… to keep it as a list";
    $("ranksave").textContent = cur ? "Save" : "Save…"; $("ranksave").disabled = cur ? !dirty : !working;
    $("ranksave").title = cur ? (dirty ? `Save changes to “${cur}”` : `“${cur}” is up to date`) : working ? "Save this list under a name" : "Nothing to save yet";
    $("ranksaveas").hidden = !cur; $("rankrename").hidden = !cur; $("rankdelete").hidden = !cur;
    $("ranknew").disabled = !cur && !working; $("ranknew").title = cur ? `Close “${cur}” and start a fresh, empty list` : "Clear the working list and start over";
    $("listsbtn").textContent = cur ? `Rankings list: ${cur}` : working ? "Rankings list: unsaved" : "Rankings lists";
    $("listsbtn").classList.toggle("on", !!cur);
  }
  // the lists popup: pick a saved list, or save / rename / delete / export the one that's open
  function renderListsPanel() {
    parkControls();
    const modal = $("modal"), body = $("modal-body"); modal.hidden = false; document.body.classList.add("modal-open"); body.innerHTML = "";
    const cur = currentSetName(), dirty = cur ? setDirty() : false, working = hasWorking();
    const names = Object.keys(state.rankSets).sort((x, y) => x.localeCompare(y));
    const w = el("div", "textmodal panel lists");
    const h2 = el("h2", null, "Rankings lists"); h2.id = "modal-title"; w.append(h2);
    w.append(el("p", "note", cur ? (dirty ? `Editing “${cur}” — it has unsaved changes.` : `Editing “${cur}”.`) : working ? "The working list isn't saved yet — Save… keeps it under a name." : "Order a tab, then Save… to keep it as a list. A list holds every tab's order and tiers."));
    const sec = el("div", "psec"); sec.append(el("h4", null, "Saved lists"));
    if (!names.length) sec.append(el("p", "note", "No saved lists yet."));
    const ul = el("div", "listrows");
    for (const n of names) {
      const b = el("button", "listrow", n); b.type = "button"; if (n === cur) { b.setAttribute("aria-current", "true"); b.append(el("small", null, dirty ? " · open, unsaved changes" : " · open")); }
      else { const sv = state.rankSets[n]; if (sv && sv.saved) b.append(el("small", null, ` · saved ${fmtDate(sv.saved.slice(0, 10))}`)); }
      b.addEventListener("click", () => { if (n !== cur) openSet(n); closePanel(); });
      ul.append(b);
    }
    sec.append(ul); w.append(sec);
    const act = el("div", "psec"); act.append(el("h4", null, cur ? `“${cur}”` : "This list"));
    const row = el("div", "fbtns");
    const mk = (label, fn, quiet, dis) => { const b = el("button", quiet ? "btn btn-quiet" : "btn", label); b.type = "button"; b.disabled = !!dis; b.addEventListener("click", () => { fn(); }); return b; };
    row.append(mk(cur ? "Save" : "Save…", () => { saveCurrent(); renderListsPanel(); }, false, cur ? !dirty : !working));
    if (cur) row.append(mk("Save as…", () => { saveAs(); renderListsPanel(); }, true), mk("Rename", () => { renameSet(cur); renderListsPanel(); }, true), mk("Delete", () => { deleteSet(cur); renderListsPanel(); }, true));
    row.append(mk("New list", () => { newList(); closePanel(); }, true, !cur && !working));
    act.append(row);
    const io = el("p", "note"); const ex = el("button", "linkbtn", "Export"); ex.type = "button"; ex.addEventListener("click", exportSets);
    const im = el("button", "linkbtn", "Import"); im.type = "button"; im.addEventListener("click", () => { importSets(); renderListsPanel(); });
    io.append(ex, " every list as text for another device · ", im, " text exported elsewhere"); act.append(io);
    w.append(act);
    const done = el("div", "row"); const d = el("button", "btn", "Done"); d.type = "button"; d.addEventListener("click", () => closePanel()); done.append(d); w.append(done);
    body.append(w);
  }
  // close the open list and start over with the model's order on every tab
  function newList() {
    const cur = currentSetName(), unsaved = cur ? setDirty() : hasWorking();
    const go = () => { state.ranks = {}; state.tiers = {}; state.tierNames = {}; state.stars = {}; save(LS.ranks, state.ranks); save(LS.tiers, state.tiers); save(LS.tierNames, state.tierNames); save(LS.stars, state.stars); state.currentSet = null; state.selKeys = []; state.selAnchor = null; savePrefs(); flash("New list — every tab is back to the model's order"); };
    if (!unsaved) return go();
    ask("Start a new list?", cur ? `Unsaved changes to “${cur}” will be lost — Cancel and press Save to keep them.` : "This list isn't saved under a name and will be cleared — Cancel and use Save… to keep it.", go);
  }
  function exportSets() {
    const payload = { v: 3, working: { ranks: state.ranks, tiers: state.tiers, tierNames: state.tierNames }, sets: state.rankSets, extraPos: state.extraPos, exported: new Date().toISOString() };
    openTextModal("Export rankings", JSON.stringify(payload), "Copy this text and paste it into Import on another copy of the site.");
  }
  function importSets() {
    openTextModal("Import rankings", "", "Paste an exported rankings block, then Import. Saved sets are added to yours; the boxes choose what else comes along.", (txt, o) => {
      let d; try { d = JSON.parse(txt); } catch { state.textModal.hint = "That isn't a rankings export — paste the whole block from Export."; render(); return; }
      if (d.sets) { for (const s of Object.values(d.sets)) s.tiers = sizesToMembers(s.ranks, s.tiers); Object.assign(state.rankSets, d.sets); }
      if (d.working && o.working) { state.ranks = d.working.ranks || {}; state.tiers = sizesToMembers(state.ranks, d.working.tiers); state.tierNames = d.working.tierNames || {}; state.currentSet = null; savePrefs(); }
      if (d.extraPos && o.extraPos) { Object.assign(state.extraPos, d.extraPos); poolsChanged(); }
      save(LS.sets, state.rankSets); save(LS.ranks, state.ranks); save(LS.tiers, state.tiers); save(LS.tierNames, state.tierNames); save(LS.extraPos, state.extraPos);
      if (state.mode === "draft" && d.sets) { const first = Object.keys(d.sets)[0]; if (first) state.draftOrder = "set:" + first; savePrefs(); }
      state.textModal = null; render();
    }, { working: "Also replace my working rankings and tiers", extraPos: "Import added positions" });
  }
  function openTextModal(title, text, hint, onSubmit, opts) { state.textModal = { title, text, hint, onSubmit, opts }; render(); }
  // yes/no or single-line-input dialogs drawn in the page
  function ask(title, message, onYes, input) { state.textModal = { title, hint: message, ask: true, input, onSubmit: onYes }; render(); }
  function renderDraftTools() {
    { const on = state.mode === "draft", ns0 = on ? Object.keys(listStars()).length : 0; const b = $("draftstars"); b.hidden = !on || (!ns0 && !state.starOnly); b.textContent = state.starOnly ? `★ Starred only (${ns0})` : `☆ Starred (${ns0})`; b.classList.toggle("on", state.starOnly); }
    const on = state.mode === "draft";
    $("drafttools").hidden = !on;
    if (!on) return;
    const dsel = $("draftorder"); dsel.innerHTML = "";
    const cur = currentSetName(), names = Object.keys(state.rankSets).sort((x, y) => x.localeCompare(y));
    for (const [v, l] of [["board", "Big board order"], ["mine", cur ? `My rankings (working copy of “${cur}”)` : "My rankings (working)"], ...names.map((n) => ["set:" + n, "Saved: " + n])]) { const o = el("option", null, l); o.value = v; dsel.append(o); }
    dsel.title = names.length ? "Big board, your working rankings, or any set you saved on the Rankings page" : "Save a set on the Rankings page and it appears here";
    if (![...dsel.options].some((o) => o.value === state.draftOrder)) state.draftOrder = "board";
    dsel.value = state.draftOrder;
    const n = state.drafted.length;
    $("draftcount").textContent = `${n} drafted`;
    $("undo").disabled = n === 0;
    $("undo").textContent = n ? `Undo ${state.drafted[n - 1].name.split(" ").slice(-1)[0]}` : "Undo last";
    $("showdrafted").checked = state.showDrafted;
    const src = orderSource(); renderViewSeg("draftview", !!(src && (src.tiers[state.pos] || []).length));
  }
  // Tiers / List switch (Rankings and Draft): group by tier, or the raw rank order
  function renderViewSeg(id, show) {
    const seg = $(id); seg.hidden = !show; seg.innerHTML = ""; if (!show) return;
    for (const [v, l] of [["tiers", "Tiers"], ["list", "List"]]) {
      const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(showTiers() === (v === "tiers")));
      b.addEventListener("click", () => { state.tierView = v; savePrefs(); render(); }); seg.append(b);
    }
  }
  function renderHub() {
    const box = $("hub"); box.innerHTML = "";
    box.append(el("h2", null, "Draft Mode"), el("p", "hublead", "Three pages that work together on draft day. Rank players and tier them, then draft from that list as picks come off the board."));
    const grid = el("div", "hubgrid");
    const cards = [
      ["#rankings", "Rankings", "Your board. Start from the model's order, sort by any column, then drag, type ranks or tick players into tiers. Save as many lists as you like and reopen them here.", "Open Rankings"],
      ["#draft", "Draft board", "For the draft itself. Pick which list to draft from — the model, your working list or a saved one — and mark players as they go; the board keeps only who's left, tiers intact, and remembers it if you close the tab.", "Open Draft board"],
      ["#eligibility", "Eligibility", "Who counts where. ESPN's rules run automatically (20+ games at a position this season, MLB and minors together; SP / RP by innings), and this page lists the positions you've added yourself on player cards, with a way to take them back.", "Open Eligibility"],
    ];
    for (const [href, title, blurb, cta] of cards) {
      const c = el("a", "hubcard"); c.href = href;
      c.append(el("h3", null, title), el("p", null, blurb), el("span", "btn", cta));
      grid.append(c);
    }
    box.append(grid);
    const m = DATA.meta;
    box.append(el("p", "note", `Data: ${m.season} Statcast through ${m.through}. Trending Players, the Leaderboard and Compare live in the top bar; type a name at the top right to open any player's card.`));
  }
  function renderChrome() {
    const navMode = DRAFT_GROUP.includes(state.mode) ? "draftmode" : state.mode;
    document.querySelectorAll(".modes a").forEach((a) => { if (a.dataset.mode === navMode) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    document.querySelectorAll("#subnav a").forEach((a) => { if (a.dataset.sub === state.mode) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    document.title = { draft: "Sean's Site · Draft board", player: "Sean's Site · Player", rankings: "Sean's Site · Rankings", compare: "Sean's Site · Compare", eligibility: "Sean's Site · Eligibility", trending: "Sean's Site · Trending", leaderboard: "Sean's Site · Leaderboard", draftmode: "Sean's Site · Draft Mode", appearance: "Sean's Site · Appearance", fantasy: "Sean's Site · Fantasy points" }[state.mode] || "Sean's Site";
    const m = DATA.meta;
    const thr = new Date(m.through + "T12:00:00"); $("stamp").innerHTML = `through <b>${thr.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</b>`; $("stamp").title = `${m.season} Statcast through ${m.through} (built ${m.built})`;
    const notes = $("notes"); notes.innerHTML = "";
    const scale = el("span", "scale"); [5, 25, 50, 75, 95].forEach((p) => { const i = el("i"); paint(i, p); scale.append(i); });
    const l1 = el("div"); l1.append("Percentiles run 0–100 within the pool", scale, "blue is cold, red is hot. O-Swing% and Whiff% (for hitters) are flipped so 100 is always the best. Click a column heading to sort by it; click a player for the full card.");
    notes.append(l1);
    notes.append(renderViewSwitch());
    notes.append(Object.assign(el("div"), { innerHTML: `<b>Eligibility</b> — a hitter is listed at every position where he played ${ESPN.posGames}+ games this season, counting MLB and minor-league games together (ESPN's rule for call-ups), OF combined, DH counts; pitchers are SP with ${ESPN.spIP}+ IP as a starter and RP with ${ESPN.rpIP}+ IP in relief. Add anything ESPN gives him that the games don't from his card. <b>Pools</b> — every hitter percentile is measured against hitters with <b>${REF_PA}+ PA</b> on the season, any position; every pitcher percentile against pitchers with <b>${REF_PA}+ batters faced</b>, starters and relievers together. That population never changes — a date range or split only changes the numbers being compared — and the <b>Min PA / Min IP</b> boxes only set who is listed: a player under the bar is placed against that same population rather than reshaping it.` }));
    notes.append(Object.assign(el("div"), { innerHTML: `<b>xwOBA</b> — ${m.scoreNote.H}. The directional (spray-angle) model's number is kept in the data as <code>xwoba_dir</code>. <b>Batted-ball definitions</b> follow Savant's leaderboards: BBE is every ball in play, Avg EV / 90th% / max EV skip bunts, Barrel%, Hard-Hit% and Sweet-Spot% are per ball in play. Seasons before 2020 have a few percent of untracked balls that Savant's public feed fills with placeholder values, so an Avg EV there can sit a tenth or two off the leaderboard.` }));
    notes.append(Object.assign(el("div"), { innerHTML: `<b>Splits</b> — open a player and pick vs LHP / RHP (vs LHB / RHB for pitchers) and home / away at the top of his card. His card is redrawn from those plate appearances and ranked against the season's qualifiers on their numbers in the same split; the list itself stays unsplit. Pitcher IP in a handedness split is the outs recorded against that side. <b>Dates</b> — type a from and/or to date (a blank side means the season's start or end) and every stat and percentile is recomputed from those games only. Who qualifies never changes: the comparison group is always the players who meet the season bar (hitters ${REF_PA}+ PA, pitchers ${REF_PA}+ batters faced), each measured on his own numbers in that range — even a very short one. Past seasons work the same once their day-by-day file loads. Inside a window, Air% and Pull Air% come from Statcast batted-ball data (pull = spray angle beyond ${m.pullLine}°, which tracks Savant within about half a point); the full-season view uses Savant's published numbers.` }));
    notes.append(Object.assign(el("div"), { innerHTML: `<b>Eligibility</b> — hitters: ${ESPN.posGames}+ games at a position in ${m.season} (outfield combined, DH counts). Pitchers: SP with ${ESPN.spIP}+ innings as a starter, RP with ${ESPN.rpIP}+ innings in relief — either or both; stats are always the full season. Add any position from a player's card; the <b>Eligibility</b> page lists what you've added.` }));
    notes.append(Object.assign(el("div"), { innerHTML: `<b>Hitters</b> rank by ${m.scoreNote.H}; the colour is its percentile in the pool. <b>Skills blend</b> (in the Sort menu and on each card) is the ${m.scoreNote.blend}. <b>Pitcher score</b> — ${m.scoreNote.P}.` }));
    notes.append(Object.assign(el("div"), { innerHTML: `<b>Position for 2027</b> — on a pitcher's card, switch SP / RP to move him to the other list and pool (a reliever expected to start next year, say). It's remembered in this browser and shows on his row as "SP (was RP)".` }));
    notes.append(Object.assign(el("div"), { innerHTML: `Air% and Pull Air% use Baseball Savant's batted-ball direction; everything else is computed from pitch-level Statcast. AB and IP are official MLB totals. Built ${m.built}.` }));
    if (state.mode === "rankings") notes.append(Object.assign(el("div"), { innerHTML: `<b>Rankings</b> — the model's order until you touch a tab (sort by any column, or pick a sort up top), then your own order, one list per tab, plus tiers that are separate from the order: a tier holds whoever you put in it and lists them by rank, so tier 1 can be ranks 1, 2, 3, 5 while rank 4 sits at the top of <b>Not tiered</b>. <b>Tiers / List</b> switches between the tiered view and the raw order. Press <b>Edit rankings</b> to change anything: tick players (click, Cmd/Ctrl-click, Shift-click for a range), then <b>Move to tier…</b> puts them in a tier (or a new one) and <b>Remove from tier</b> sends them back to Not tiered. The rank box, ▲ ▼ and dragging change the order; dragging into another tier's section also moves him there. <b>Add tier</b> adds an empty tier at the bottom; with a player ticked it becomes <b>Tier below him</b> — a boundary right under him, splitting his tier (or cutting a tier off the top of Not tiered). <b>+ tier above</b> on any tier header slots an empty tier in there. ✎ gives a tier a nickname; × removes it. Outside edit mode, clicking a player opens his card. Players you haven't touched follow the big board beneath the ones you have; everyone under the Min PA / IP box is listed after them (most playing time first, PA in amber) so nobody is missing but small samples never push a qualifier around. The bar at the top says which list you're editing: pick a saved list from the menu to open it, <b>Save</b> writes your changes back to it, <b>Save as…</b> keeps a copy under a new name, and <b>New list</b> closes it and starts fresh from the model's order. Rename and Delete act on the open list; Export / Import move lists between browsers as text. The Draft page can draft from your working rankings or any saved set (Draft from).` }));
    if (state.mode === "leaderboard") notes.append(Object.assign(el("div"), { innerHTML: `<b>Leaderboard</b> — every hitter or pitcher over the Min PA / IP box, for any season and level you pick (MLB from 2015, the minors from 2021), with the stats you choose (<b>Columns…</b>). The vs-L / R and home / away toggles redraw every number and percentile from those plate appearances only (the comparison group stays the season's qualifiers on their numbers in the same split); ERA needs full games, so it's blank in a handedness split. Each cell shows the number, coloured by where it ranks among the season's qualifiers; click a heading to sort, click it again to flip. Dates and Last-N work here too, and the position tabs narrow the list.` }));
    if (state.mode === "trending") notes.append(Object.assign(el("div"), { innerHTML: `<b>Trending</b> — who's hot right now. The position tabs use the same eligibility as everywhere else (${ESPN.posGames}+ games at a position this season, plus anything you've added). Hitters are ordered by ${HEAD.label} over each player's last N plate appearances (or the last N days); pitchers by the average of their Whiff% and Strike% percentiles over their last N innings (or days), with K%, BB%, ERA, SIERA and GB% for that span alongside. Full-season minimums don't apply here — <b>at least</b> sets how much playing time a player needs inside the span to be listed. The chips show the actual number, coloured by where it ranks among the season's qualifiers on their numbers in the same span. Click a player for his card over that span.` }));
    if (state.mode === "draft") notes.append(Object.assign(el("div"), { innerHTML: `<b>Draft mode</b> — <b>Draft from</b> picks the order: the big board, your working rankings, or any set you saved on the Rankings page (tiers included). Drafted players are saved in this browser, so you can close the tab and come back mid-draft. “Show drafted” keeps them on the board, dimmed.` }));
  }

  function render() {
    const player = state.mode === "player", compare = state.mode === "compare", elig = state.mode === "eligibility", hub = state.mode === "draftmode", appear = state.mode === "appearance", fant = state.mode === "fantasy", other = player || compare || elig || hub || appear || fant;
    $("xboard").hidden = !player; $("hub").hidden = !hub; $("pboard").hidden = !appear; $("fboard").hidden = !fant;
    document.body.dataset.mode = state.mode;
    const T = state.tbl; document.body.dataset.heat = T.heat ? "on" : "off"; document.body.dataset.band = T.band ? "on" : "off"; document.body.dataset.sorthl = T.sortHl ? "on" : "off"; document.body.dataset.density = T.density;
    $("ctoolbar").hidden = !compare; $("cboard").hidden = !compare;
    $("eboard").hidden = !elig;
    $("subnav").hidden = !DRAFT_GROUP.includes(state.mode);
    document.querySelector(".toolbar:not(.xtoolbar)").hidden = other; $("board").hidden = other; $("drafttools").hidden = true; $("ranktools").hidden = true; $("setbar").hidden = true; $("lbtools").hidden = true;
    renderChrome();
    if (state.textModal) { renderTextModal(); } else if (other) { $("modal").hidden = true; document.body.classList.remove("modal-open"); }
    if (hub) { renderHub(); return; }
    if (appear) { renderAppearance(); return; }
    if (fant) { renderFantasy(); renderModal(); return; }
    if (player) { renderExplore(); return; }
    if (compare) { renderCompare(); renderModal(); return; }
    if (elig) { renderEligibility(); return; }
    const listRender = () => {
      ensureView();
      if (state.mode === "trending" && !TREND_TABS.includes(state.pos)) state.pos = "ALL";
      renderTabs(); renderSortSelect(); renderDates(); renderMin(); renderRef(); renderColhead(); renderRows(); renderRankTools(); renderSetBar(); renderDraftTools(); renderTrendTools(); renderLbTools();
      const sf = $("sortfield"); if (sf) sf.hidden = customOrder();
      renderToolSummary();
    };
    if (state.mode === "leaderboard") {
      const run = () => withSplit(state.lbSplit, listRender);        // the Leaderboard can be drawn for a split
      const key = lbKey();
      if (key !== CUR.key) {
        ensureHist(key);
        const ds = histDataset(key);
        if (!ds) { renderLbTools(); $("rows").innerHTML = ""; $("colhead").innerHTML = ""; const e = $("empty"); e.hidden = false; e.textContent = failed.has(`hist/${key}.js`) ? `hist/${key}.js is missing.` : isMulti(key) ? "Loading those seasons…" : "Loading that season…"; renderModal(); return; }
        withDataset(ds, run);
      } else run();
    } else listRender();
    renderModal();
  }

  // Mobile / desktop layout switch (footer of every page and the Appearance page)
  function renderViewSwitch() {
    const T = window.DRAFT_THEMES, box = el("div", "viewsw");
    if (!T) return box;
    box.append("Layout: ");
    const pref = T.viewPref();
    [["auto", `Auto (${T.view() === "mobile" ? "mobile" : "desktop"} now)`], ["mobile", "Mobile"], ["desktop", "Desktop"]].forEach(([v, l], i) => {
      if (i) box.append(" · ");
      const b = el("button", "linkbtn", l); b.type = "button"; b.setAttribute("aria-pressed", String(v === pref));
      b.addEventListener("click", () => { T.setView(v); document.body.classList.remove("mopen"); render(); window.scrollTo(0, 0); });
      box.append(b);
    });
    return box;
  }

  /* ---------- Fantasy points: ESPN-style scoring presets, leaderboards, per-opportunity rates, luck-neutral what-ifs ---------- */
  // Every scoring category ESPN offers that the official season line supports. Values come from fantasy.js
  // (MLB Stats API counting stats + per-game pitching logs) and points are computed here from the preset in use.
  const FCATS = {
    H: [["TB", "Total bases"], ["H", "Hits"], ["1B", "Singles"], ["2B", "Doubles"], ["3B", "Triples"], ["HR", "Home runs"], ["XBH", "Extra-base hits"],
        ["R", "Runs"], ["RBI", "RBI"], ["BB", "Walks"], ["IBB", "Intentional walks"], ["HBP", "Hit by pitch"], ["K", "Strikeouts"], ["SB", "Stolen bases"],
        ["CS", "Caught stealing"], ["GIDP", "Grounded into DP"], ["SF", "Sacrifice flies"], ["SH", "Sacrifice bunts"], ["E", "Errors"], ["AB", "At bats"],
        ["PA", "Plate appearances"], ["OUT", "Outs (AB − H)"], ["G", "Games played"]],
    P: [["IP", "Innings pitched (per inning: ⅓ per out)"], ["OUT", "Outs recorded"], ["K", "Strikeouts"], ["W", "Wins"], ["L", "Losses"], ["SV", "Saves"],
        ["HD", "Holds"], ["BS", "Blown saves"], ["ER", "Earned runs"], ["R", "Runs allowed"], ["H", "Hits allowed"], ["HR", "Home runs allowed"],
        ["BB", "Walks issued"], ["IBB", "Intentional walks"], ["HBP", "Hit batters"], ["QS", "Quality starts (6+ IP, ≤ 3 ER)"], ["CG", "Complete games"],
        ["SHO", "Shutouts"], ["NH", "No-hitters"], ["PG", "Perfect games"], ["WP", "Wild pitches"], ["BK", "Balks"], ["PK", "Pickoffs"], ["BF", "Batters faced"],
        ["GS", "Games started"], ["G", "Games pitched"]],
  };
  const ESPN_PRESET = { id: "espn", name: "ESPN standard", builtin: true, teams: 10,
                        w: { H: { TB: 1, R: 1, RBI: 1, SB: 1, BB: 1, K: -1 }, P: { IP: 3, W: 2, L: -2, HD: 2, SV: 5, ER: -2, H: -1, K: 1, BB: -1 } } };
  const FSLOTS = { C: 1, "1B": 1, "2B": 1, "3B": 1, SS: 1, OF: 3, DH: 1 };              // ESPN default lineup (UTIL counted at DH)
  const FLS = "draft2027.fantasy";
  const fstore = Object.assign({ presets: [], current: "espn", ui: {} }, load(FLS, {}));
  const fsave = () => save(FLS, fstore);
  const fpresets = () => [ESPN_PRESET, ...fstore.presets];
  const fpreset = () => fpresets().find((p) => p.id === fstore.current) || ESPN_PRESET;
  const NOWIN = { from: "", to: "", last: "" };
  state.f = Object.assign({ view: "points", grp: "H", pos: "ALL", year: String(DATA.meta.season), q: "", sort: null, dir: "desc", minH: 100, minP: 20, edit: null }, fstore.ui);
  const FYEARS = [DATA.meta.season, DATA.meta.season - 1, DATA.meta.season - 2].map(String);

  const fData = (y) => window.DRAFT_FANTASY && window.DRAFT_FANTASY[y];
  const fFile = (y) => (y === String(DATA.meta.season) ? "fantasy.js" : `hist/fantasy-${y}.js`);
  const fDsKey = (y) => (y === String(DATA.meta.season) ? CUR.key : `mlb-${y}`);
  const fEnsure = (y) => { ensureScript(fFile(y), () => !!fData(y)); if (fDsKey(y) !== CUR.key) ensureHist(fDsKey(y)); };
  const sum = (a, k) => a.reduce((s, o) => s + (o[k] || 0), 0);

  function fHit(F, id) {
    const a = F.hitters[id]; if (!a) return null;
    const o = {}; F.hk.forEach((k, i) => { o[k] = a[i] || 0; });
    o["1B"] = o.H - o["2B"] - o["3B"] - o.HR; o.XBH = o["2B"] + o["3B"] + o.HR; o.OUT = o.AB - o.H;
    return o;
  }
  function fGame(F, row) {
    const o = {}; F.gk.forEach((k, i) => { o[k] = row[i] || 0; });
    o.IP = o.OUTS / 3; o.OUT = o.OUTS; o.G = 1;
    o.QS = o.GS && o.OUTS >= 18 && o.ER <= 3 ? 1 : 0;
    o.NH = o.CG && o.H === 0 ? 1 : 0; o.PG = o.NH && o.BB === 0 && o.HBP === 0 ? 1 : 0;
    return o;
  }
  function fPit(F, id) {
    const r = F.pitchers[id]; if (!r) return null;
    const o = {}; F.pk.forEach((k, i) => { o[k] = r.s[i] || 0; });
    o.IP = o.OUTS / 3; o.OUT = o.OUTS;
    o.games = r.g.map((g) => fGame(F, g));
    o.QS = sum(o.games, "QS"); o.NH = sum(o.games, "NH"); o.PG = sum(o.games, "PG");
    return o;
  }
  const fPts = (w, o) => Object.entries(w || {}).reduce((s, [k, v]) => s + (Number(v) || 0) * (o[k] || 0), 0);
  const div = (a, b) => (b ? a / b : null);
  const f1 = (x) => (x == null ? "–" : x.toFixed(1)), f2 = (x) => (x == null ? "–" : x.toFixed(2)), f0 = (x) => (x == null ? "–" : String(Math.round(x)));
  const fDelta = (x) => (x == null ? "–" : (x >= 0 ? "+" : "") + x.toFixed(1));
  const fERA = (er, ip) => (ip ? f2(er * 9 / ip) : "–"), fWHIP = (o) => (o.IP ? f2((o.H + o.BB) / o.IP) : "–");
  const fAvg = (h, ab) => (ab ? fmtX(h / ab) : "–");
  const fOBP = (o) => { const d = o.AB + o.BB + o.HBP + o.SF; return d ? fmtX((o.H + o.BB + o.HBP) / d) : "–"; };

  // rows for a season: every player of the group with fantasy stats, plus the preset's points
  function fRows(y, grp) {
    const F = fData(y), ds = histDataset(fDsKey(y)); if (!F || !ds) return null;
    const w = fpreset().w;
    const out = [];
    for (const p of ds.players) {
      if (p.type !== (grp === "H" ? "H" : "P")) continue;
      const o = grp === "H" ? fHit(F, p.id) : fPit(F, p.id); if (!o) continue;
      const r = { p, o, pts: fPts(w[grp], o) };
      if (grp === "P") {
        r.starts = o.games.filter((g) => g.GS); r.relief = o.games.filter((g) => !g.GS);
        r.ptsS = r.starts.reduce((s, g) => s + fPts(w.P, g), 0); r.ptsR = r.relief.reduce((s, g) => s + fPts(w.P, g), 0);
      }
      out.push(r);
    }
    return out;
  }
  const fPos = (p) => (p.type === "H" ? eligiblePositions(p) : pitcherRoles(p));
  const fInPos = (p, pos) => pos === "ALL" || pos === "ALLP" || fPos(p).includes(pos);
  const fMinOK = (r) => (r.p.type === "H" ? r.o.PA >= state.f.minH : r.o.IP >= state.f.minP);

  // luck-neutral lines. Pitchers: K and BB from his underlying rates (uK% = Whiff%, uBB% = BB% at his Strike% percentile),
  // ER from luck-neutral ERA, hits allowed from Savant xBA. Hitters: hits and total bases from Savant xBA / xSLG, with the
  // extra-base mix scaled to hit both; everything else (R, RBI, SB, BB, K) as it happened.
  function fNeutralP(F, p, o, pl) {
    const st = pl.stats.get("P" + p.id), pv = V(p), xp = F.xp[p.id];
    const n = Object.assign({}, o), why = {};
    if (st && st.ukbb) { n.K = o.BF * st.ukbb.k / 100; n.BB = o.BF * st.ukbb.bb / 100; why.uk = st.ukbb.k; why.ubb = st.ukbb.bb; }
    if (pv.m.nera != null && o.IP) { n.ER = pv.m.nera * o.IP / 9; n.R = o.R + (n.ER - o.ER); why.nera = pv.m.nera; }
    if (xp && xp[0] != null) { n.H = xp[0] * o.AB; why.xba = xp[0]; }
    const f = (k) => (o[k] ? n[k] / o[k] : 1);
    n.games = o.games.map((g) => Object.assign({}, g, { K: g.K * f("K"), BB: g.BB * f("BB"), ER: g.ER * f("ER"), H: g.H * f("H"), R: g.R + g.ER * (f("ER") - 1) }));
    n.why = why;
    return n;
  }
  function fNeutralH(F, p, o) {
    const x = F.xh[p.id]; if (!x || x[0] == null || x[1] == null || !o.AB) return null;
    const xH = x[0] * o.AB, xTB = x[1] * o.AB;
    const s1 = o["1B"], xb = o.XBH, tbx = 2 * o["2B"] + 3 * o["3B"] + 4 * o.HR;
    let f = tbx !== xb ? (xTB - xH) / (tbx - xb) : 1, g = s1 ? (xH - f * xb) / s1 : 1;
    f = Math.max(0, f); g = Math.max(0, g);
    return Object.assign({}, o, { H: xH, TB: xTB, "1B": g * s1, "2B": f * o["2B"], "3B": f * o["3B"], HR: f * o.HR, XBH: f * xb, OUT: o.AB - xH, why: { xba: x[0], xslg: x[1] } });
  }
  // starters at a position: the top (teams × slots) hitters by PA who are eligible there
  function fStarters(rows, pos, teams) {
    const el0 = rows.filter((r) => fInPos(r.p, pos)).sort((a, b) => b.o.PA - a.o.PA).slice(0, Math.max(1, teams * (FSLOTS[pos] || 1)));
    return { n: el0.length, pa: el0.reduce((s, r) => s + r.o.PA, 0) / el0.length, pag: el0.reduce((s, r) => s + div(r.o.PA, r.o.G), 0) / el0.length };
  }
  const rankOf = (vals, v, higher = true) => vals.filter((x) => x != null && (higher ? x > v : x < v)).length + 1;

  // ----- page -----
  function renderFantasy() {
    const box = $("fboard"); box.innerHTML = "";
    const f = state.f, y = f.year, T = window.DRAFT_THEMES;
    fEnsure(y);
    // sub-nav
    const nav = el("nav", "subnav fsubnav");
    for (const [v, l] of [["points", "Points"], ["advanced", "Per opportunity"], ["whatif", "What if"], ["settings", "Scoring settings"]]) {
      const a = el("a", null, l); a.href = `#fantasy/${v}`; if (v === f.view) a.setAttribute("aria-current", "page"); nav.append(a);
    }
    box.append(nav);
    if (f.view === "settings") { renderFSettings(box); return; }
    // toolbar: preset · year · group · position · search · minimum
    const bar = el("div", "fbar");
    const pre = el("label", "field"); pre.append(el("span", null, "Scoring"));
    const sel = el("select");
    for (const p of fpresets()) { const o = el("option", null, p.name); o.value = p.id; if (p.id === fpreset().id) o.selected = true; sel.append(o); }
    sel.addEventListener("change", () => { fstore.current = sel.value; fsave(); renderFantasy(); });
    pre.append(sel); bar.append(pre);
    const edit = el("button", "btn btn-quiet", "Edit scoring"); edit.type = "button"; edit.addEventListener("click", () => { location.hash = "#fantasy/settings"; }); bar.append(edit);
    bar.append(pillSelect(y, FYEARS.map((yy) => [yy, yy]), y, (yy) => { f.year = yy; fUi(); renderFantasy(); }, "Season"));
    const seg = el("div", "seg"); seg.setAttribute("role", "group");
    for (const [g, l] of [["H", "Hitters"], ["P", "Pitchers"]]) {
      const b = el("button", "segbtn", l); b.type = "button"; b.setAttribute("aria-pressed", String(g === f.grp));
      b.addEventListener("click", () => { f.grp = g; f.pos = g === "H" ? "ALL" : "ALLP"; f.sort = null; fUi(); renderFantasy(); }); seg.append(b);
    }
    bar.append(seg);
    const q = el("input"); q.type = "search"; q.placeholder = "Search name or team"; q.value = f.q; q.className = "fq";
    q.addEventListener("input", () => { f.q = q.value; renderFTable(box); });
    bar.append(q);
    const mn = el("label", "field"); mn.append(el("span", null, f.grp === "H" ? "Min PA" : "Min IP"));
    const mi = el("input"); mi.type = "number"; mi.min = 0; mi.step = f.grp === "H" ? 10 : 5; mi.value = f.grp === "H" ? f.minH : f.minP; mi.inputMode = "numeric";
    mi.addEventListener("change", () => { if (f.grp === "H") f.minH = Math.max(0, Number(mi.value) || 0); else f.minP = Math.max(0, Number(mi.value) || 0); fUi(); renderFTable(box); });
    mn.append(mi); bar.append(mn);
    box.append(bar);
    // position tabs
    const tabs = el("div", "postabs ftabs"); tabs.setAttribute("role", "tablist");
    const tabList = f.grp === "H" ? HIT_TABS : PIT_TABS;
    for (const t of tabList) {
      const b = el("button", "postab", t === "ALL" ? "All hitters" : t === "ALLP" ? "All pitchers" : t); b.type = "button"; b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(t === f.pos));
      b.addEventListener("click", () => { f.pos = t; fUi(); renderFTable(box); }); tabs.append(b);
    }
    box.append(tabs);
    box.append(el("div", "ftable-wrap"));
    box.append(el("p", "note fnote"));
    renderFTable(box);
  }
  const fUi = () => { fstore.ui = { view: state.f.view, grp: state.f.grp, pos: state.f.pos, year: state.f.year, minH: state.f.minH, minP: state.f.minP }; fsave(); };

  function fColumns(view, grp) {
    const P = fpreset(), teams = P.teams || 10;
    const num = (get, fmt, opts = {}) => Object.assign({ get, fmt, num: true }, opts);
    const cols = [];
    if (grp === "H") {
      const o = (k, fmt = f0) => num((r) => r.o[k], fmt);
      if (view === "points") cols.push(
        ["Pts", num((r) => r.pts, f1, { paint: true })], ["Pts/G", num((r) => div(r.pts, r.o.G), f2, { paint: true })],
        ["G", o("G")], ["PA", o("PA")], ["AB", o("AB")], ["H", o("H")], ["R", o("R")], ["HR", o("HR")], ["RBI", o("RBI")], ["SB", o("SB")], ["BB", o("BB")], ["K", o("K")],
        ["AVG", num((r) => div(r.o.H, r.o.AB), (x) => fmtX(x))], ["OBP", num((r) => { const d = r.o.AB + r.o.BB + r.o.HBP + r.o.SF; return div(r.o.H + r.o.BB + r.o.HBP, d); }, (x) => fmtX(x))],
        ["SLG", num((r) => div(r.o.TB, r.o.AB), (x) => fmtX(x))], ["OPS", num((r) => { const d = r.o.AB + r.o.BB + r.o.HBP + r.o.SF; const obp = div(r.o.H + r.o.BB + r.o.HBP, d), slg = div(r.o.TB, r.o.AB); return obp == null || slg == null ? null : obp + slg; }, (x) => fmtX(x))]);
      else if (view === "advanced") cols.push(
        ["Pts", num((r) => r.pts, f1, { paint: true })], ["Pts/G", num((r) => div(r.pts, r.o.G), f2, { paint: true })],
        ["Pts/PA", num((r) => div(r.pts, r.o.PA), (x) => (x == null ? "–" : x.toFixed(3)), { paint: true })], ["Pts/AB", num((r) => div(r.pts, r.o.AB), (x) => (x == null ? "–" : x.toFixed(3)), { paint: true })],
        ["Pts per 600 PA", num((r) => (r.o.PA ? r.pts / r.o.PA * 600 : null), f0, { paint: true })], ["PA/G", num((r) => div(r.o.PA, r.o.G), f2)], ["G", o("G")], ["PA", o("PA")], ["AB", o("AB")]);
      else cols.push(
        ["Pts", num((r) => r.pts, f1)], ["xPts", num((r) => r.npts, f1, { paint: true, title: "Points with hits and total bases at his expected (xBA / xSLG) rates, same PA" })], ["Δ", num((r) => (r.npts == null ? null : r.npts - r.pts), fDelta, { paint: true })],
        ["Pts/PA", num((r) => div(r.pts, r.o.PA), (x) => (x == null ? "–" : x.toFixed(3)))], ["xPts/PA", num((r) => div(r.npts, r.o.PA), (x) => (x == null ? "–" : x.toFixed(3)), { paint: true })],
        ["Pts/G", num((r) => div(r.pts, r.o.G), f2)], ["xPts/G at starter PA", num((r) => r.xpg, f2, { paint: true, title: `Expected points per game if he got the plate appearances per game of a starter at his position (top ${teams} × lineup slots by PA)` })],
        ["xPts at starter PA", num((r) => r.xfull, f0, { paint: true, title: "Expected points over a full starter's plate appearances at his position" })],
        ["Rank", num((r) => r.rank, f0, { title: "Rank at the position by actual points", low: true })], ["What-if rank", num((r) => r.xrank, f0, { title: "Rank at the position by expected points at a starter's plate appearances", low: true })],
        ["H → xH", { get: (r) => `${r.o.H} → ${r.n ? f0(r.n.H) : "–"}` }], ["TB → xTB", { get: (r) => `${r.o.TB} → ${r.n ? f0(r.n.TB) : "–"}` }],
        ["xBA", num((r) => (r.n ? r.n.why.xba : null), (x) => fmtX(x))], ["xSLG", num((r) => (r.n ? r.n.why.xslg : null), (x) => fmtX(x))], ["PA", o("PA")], ["G", o("G")]);
    } else {
      const o = (k, fmt = f0) => num((r) => r.o[k], fmt);
      if (view === "points") cols.push(
        ["Pts", num((r) => r.pts, f1, { paint: true })], ["Pts/G", num((r) => div(r.pts, r.o.G), f2, { paint: true })],
        ["G", o("G")], ["GS", o("GS")], ["IP", num((r) => r.o.IP, (x) => fmtIP(x))], ["W", o("W")], ["L", o("L")], ["SV", o("SV")], ["HD", o("HD")], ["K", o("K")], ["BB", o("BB")], ["H", o("H")], ["ER", o("ER")],
        ["ERA", num((r) => div(r.o.ER * 9, r.o.IP), f2, { low: true })], ["WHIP", num((r) => div(r.o.H + r.o.BB, r.o.IP), f2, { low: true })], ["K/9", num((r) => div(r.o.K * 9, r.o.IP), f2)], ["QS", o("QS")]);
      else if (view === "advanced") cols.push(
        ["Pts", num((r) => r.pts, f1, { paint: true })], ["Pts/G", num((r) => div(r.pts, r.o.G), f2, { paint: true })], ["Pts/IP", num((r) => div(r.pts, r.o.IP), f2, { paint: true })],
        ["Pts/start", num((r) => div(r.ptsS, r.starts.length), f2, { paint: true })], ["Pts/relief app", num((r) => div(r.ptsR, r.relief.length), f2, { paint: true })],
        ["IP/start", num((r) => div(sum(r.starts, "IP"), r.starts.length), f2)], ["QS", o("QS")], ["QS%", num((r) => (r.o.GS ? 100 * r.o.QS / r.o.GS : null), (x) => (x == null ? "–" : x.toFixed(0) + "%"))],
        ["Pts as SP", num((r) => r.ptsS, f1)], ["Pts as RP", num((r) => r.ptsR, f1)], ["GS", o("GS")], ["G", o("G")], ["IP", num((r) => r.o.IP, (x) => fmtIP(x))]);
      else cols.push(
        ["Pts", num((r) => r.pts, f1)], ["uPts", num((r) => r.npts, f1, { paint: true, title: "Points with K and BB at his underlying rates, ER at his luck-neutral ERA and hits allowed at his xBA" })], ["Δ", num((r) => (r.npts == null ? null : r.npts - r.pts), fDelta, { paint: true })],
        ["Rank", num((r) => r.rank, f0, { title: "Rank at the role by actual points", low: true })], ["What-if rank", num((r) => r.xrank, f0, { title: "Rank at the role by underlying points", low: true })],
        ["Pts/start", num((r) => div(r.ptsS, r.starts.length), f2)], ["uPts/start", num((r) => (r.n ? div(r.n.ptsS, r.starts.length) : null), f2, { paint: true })],
        ["Pts/IP", num((r) => div(r.pts, r.o.IP), f2)], ["uPts/IP", num((r) => div(r.npts, r.o.IP), f2, { paint: true })],
        ["K → uK", { get: (r) => `${r.o.K} → ${r.n ? f0(r.n.K) : "–"}` }], ["BB → uBB", { get: (r) => `${r.o.BB} → ${r.n ? f0(r.n.BB) : "–"}` }],
        ["H → xH", { get: (r) => `${r.o.H} → ${r.n ? f0(r.n.H) : "–"}` }], ["ER → nER", { get: (r) => `${r.o.ER} → ${r.n ? f0(r.n.ER) : "–"}` }],
        ["uK%", num((r) => (r.n ? r.n.why.uk : null), f1)], ["uBB%", num((r) => (r.n ? r.n.why.ubb : null), f1, { low: true })], ["nERA", num((r) => (r.n ? r.n.why.nera : null), f2, { low: true })],
        ["IP", num((r) => r.o.IP, (x) => fmtIP(x))], ["GS", o("GS")]);
    }
    return cols.map(([label, c]) => Object.assign({ label }, c));
  }

  function renderFTable(box) {
    const f = state.f, y = f.year, wrap = box.querySelector(".ftable-wrap"), note = box.querySelector(".fnote");
    if (!wrap) return;
    wrap.innerHTML = "";
    const F = fData(y), ds = histDataset(fDsKey(y));
    if (!F || !ds) { wrap.append(el("p", "xempty", failed.has(fFile(y)) ? `No fantasy data for ${y} yet — run python3 build_fantasy.py ${y}.` : "Loading…")); return; }
    const P = fpreset(), teams = P.teams || 10;
    let rows = fRows(y, f.grp);
    // what-if numbers need the season's pool (underlying K / BB) and starters at each position
    if (f.view === "whatif") withDataset(ds, () => withWindow(NOWIN, () => {
      if (f.grp === "P") {
        const pl = pool("P");
        for (const r of rows) { r.n = fNeutralP(F, r.p, r.o, pl); r.npts = fPts(P.w.P, r.n); r.n.ptsS = r.n.games.filter((g) => g.GS).reduce((s, g) => s + fPts(P.w.P, g), 0); }
      } else {
        const st = {}; for (const pos of HIT_TABS.slice(1)) st[pos] = fStarters(rows, pos, teams);
        for (const r of rows) {
          r.n = fNeutralH(F, r.p, r.o); r.npts = r.n ? fPts(P.w.H, r.n) : null;
          const pos = f.pos === "ALL" ? (r.p.primary || fPos(r.p)[0] || "DH") : f.pos, s = st[pos] || st.DH;
          const rate = r.o.PA && r.npts != null ? r.npts / r.o.PA : null;
          r.xpg = rate == null ? null : rate * s.pag; r.xfull = rate == null ? null : rate * s.pa;
        }
      }
    }));
    // ranks at the position / role (among everyone over the minimum), before search narrows the table
    const inPos = rows.filter((r) => fInPos(r.p, f.pos) && fMinOK(r));
    if (f.view === "whatif") {
      const act = inPos.map((r) => r.pts), what = inPos.map((r) => (f.grp === "P" ? r.npts : r.xfull));
      for (const r of inPos) { r.rank = rankOf(act, r.pts); r.xrank = (f.grp === "P" ? r.npts : r.xfull) == null ? null : rankOf(what, f.grp === "P" ? r.npts : r.xfull); }
    }
    const qq = f.q.trim().toLowerCase();
    let shown = inPos.filter((r) => !qq || r.p.name.toLowerCase().includes(qq) || (r.p.team || "").toLowerCase().includes(qq));
    const cols = fColumns(f.view, f.grp);
    const sortKey = f.sort && cols.some((c) => c.label === f.sort) ? f.sort : cols[0].label;
    const sc = cols.find((c) => c.label === sortKey);
    const dir = f.dir === "asc" ? 1 : -1;
    shown.sort((a, b) => { const x = sc.get(a), z = sc.get(b); if (x == null && z == null) return 0; if (x == null) return 1; if (z == null) return -1; return typeof x === "number" ? dir * (x - z) : dir * String(x).localeCompare(String(z)); });
    // colour the rate columns by percentile within what is shown
    const pcts = {};
    for (const c of cols) if (c.paint) { const vals = shown.map((r) => c.get(r)); const oriented = vals.map((v) => (v == null ? null : c.low ? -v : v)); pcts[c.label] = percentiles(oriented); }
    const fsig = ["f", f.view, f.grp, f.pos, f.year, f.q, sortKey, f.dir, f.minH, f.minP, fpreset().id, shown.length].join("|");
    if (fsig !== state.pageSig) { state.pageSig = fsig; state.page = 1; }
    const pg = pageWindow(shown.length);
    const pagerTop = el("div", "pager"), pagerBot = el("div", "pager");
    const redraw = () => renderFTable(box);
    renderPager(pagerTop, shown.length, pg, redraw); renderPager(pagerBot, shown.length, pg, redraw);
    wrap.append(pagerTop);
    const table = el("table", "ftable"), thead = el("thead"), tr = el("tr");
    tr.append(el("th", "n", document.documentElement.dataset.view === "mobile" ? "Rk" : "Rank"), el("th", "who", "Player"));
    for (const c of cols) {
      const th = el("th", c.num ? "num" : "txt"); const b = el("button", "h", c.label); b.type = "button"; if (c.title) b.title = c.title;
      if (c.label === sortKey) th.setAttribute("aria-sort", f.dir === "asc" ? "ascending" : "descending");
      b.addEventListener("click", () => { if (f.sort === c.label) f.dir = f.dir === "asc" ? "desc" : "asc"; else { f.sort = c.label; f.dir = c.low ? "asc" : "desc"; } renderFTable(box); });
      th.append(b); tr.append(th);
    }
    thead.append(tr); table.append(thead);
    const tbody = el("tbody");
    shown.slice(pg.start, pg.end).forEach((r, k) => {
      const i = pg.start + k;
      const trr = el("tr"); trr.tabIndex = 0;
      trr.append(el("td", "n", String(i + 1)));
      const who = el("td", "who"); who.append(el("b", null, r.p.name), el("small", null, ` ${r.p.team} · ${fPos(r.p).join(", ") || r.p.primary || ""}`)); trr.append(who);
      cols.forEach((c, j) => {
        const v = c.get(r), td = el("td", c.num ? "num" : "txt", c.fmt ? c.fmt(v) : String(v ?? "–"));
        if (c.paint && v != null) { const pct = pcts[c.label][i]; if (pct != null) paint(td, pct); td.classList.add("pc"); }
        trr.append(td);
      });
      const open = () => { state.cardDs = fDsKey(y) === CUR.key ? null : fDsKey(y); state.cardWin = Object.assign({}, NOWIN); state.expanded = r.p.type + r.p.id; renderModal(); };
      trr.addEventListener("click", open); trr.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
      tbody.append(trr);
    });
    table.append(tbody);
    const scroll = el("div", "fscroll"); scroll.append(table); wrap.append(scroll, pagerBot);
    fFloatHead(wrap, scroll, table);
    if (!shown.length) wrap.append(el("p", "xempty", "No players match."));
    const wtxt = Object.entries(P.w[f.grp]).filter(([, v]) => Number(v)).map(([k, v]) => `${k} ${v > 0 ? "+" : ""}${v}`).join(", ");
    note.textContent = `${P.name}: ${wtxt || "no categories scored"}. ${y} official season stats through ${F.through}; ${shown.length} ${f.grp === "H" ? "hitters" : "pitchers"} with ${f.grp === "H" ? state.f.minH + "+ PA" : state.f.minP + "+ IP"}` +
      (f.view === "whatif" ? (f.grp === "P" ? ". uPts: strikeouts and walks at his underlying rates (uK% = Whiff%, uBB% = the walk rate at his Strike% percentile), earned runs at his luck-neutral ERA, hits allowed at his Savant xBA; wins, saves, holds and quality starts as they happened. Per-start numbers scale each start by the same ratios."
        : `. xPts: hits and total bases at his Savant xBA / xSLG (extra-base mix scaled to hit both) over his actual plate appearances; runs, RBI, walks, strikeouts and steals as they happened. Starter workload = the top ${teams} × lineup slots at the position by PA (OF 3), their average PA and PA per game.`) : ".");
  }

  // phone: a copy of the header row that sticks to the top of the screen while the page scrolls (it overlays the real
  // header exactly while the table top is in view), kept aligned with the columns as the table is dragged sideways
  function fFloatHead(wrap, scroll, table) {
    const head = el("div", "fhead"), clip = el("div", "fhead-clip"), t2 = el("table", "ftable fhead-table");
    t2.append(table.tHead.cloneNode(true)); clip.append(t2); head.append(clip);
    wrap.insertBefore(head, scroll);
    const size = () => {
      const src = table.tHead.querySelectorAll("th"), dst = t2.querySelectorAll("th");
      src.forEach((th, i) => { const w = th.getBoundingClientRect().width + "px"; dst[i].style.width = w; dst[i].style.minWidth = w; dst[i].style.maxWidth = w; });
      t2.style.width = table.getBoundingClientRect().width + "px"; clip.style.width = scroll.clientWidth + "px";
      clip.scrollLeft = scroll.scrollLeft;
    };
    requestAnimationFrame(size); setTimeout(size, 300);
    scroll.addEventListener("scroll", () => { clip.scrollLeft = scroll.scrollLeft; }, { passive: true });
    clip.addEventListener("scroll", () => { scroll.scrollLeft = clip.scrollLeft; }, { passive: true });
    t2.addEventListener("click", (e) => { const b = e.target.closest("button.h"); if (!b) return; const i = [...t2.querySelectorAll("button.h")].indexOf(b); const real = table.tHead.querySelectorAll("button.h")[i]; if (real) real.click(); });
  }

  // ----- scoring settings: presets and the editor -----
  function renderFSettings(box) {
    const f = state.f;
    const head = el("div", "fsethead"); head.append(el("h2", "ahead", "Scoring settings"));
    box.append(head);
    box.append(el("p", "hublead", "Any of ESPN's categories, any point values. The preset in use drives every fantasy page. Presets are saved in this browser."));
    const list = el("div", "fpresets");
    for (const p of fpresets()) {
      const card = el("div", "fpreset"); if (p.id === fpreset().id) card.classList.add("inuse");
      card.append(el("h3", null, p.name + (p.builtin ? " (built in)" : "")));
      const summary = (g) => Object.entries(p.w[g] || {}).filter(([, v]) => Number(v)).map(([k, v]) => `${k} ${v > 0 ? "+" : ""}${v}`).join(", ") || "nothing";
      card.append(el("p", null, `Hitting: ${summary("H")}`), el("p", null, `Pitching: ${summary("P")}`), el("p", "note", `${p.teams || 10}-team league`));
      const btns = el("div", "fbtns");
      const use = el("button", "btn", p.id === fpreset().id ? "In use" : "Use"); use.type = "button"; use.disabled = p.id === fpreset().id;
      use.addEventListener("click", () => { fstore.current = p.id; fsave(); renderFantasy(); }); btns.append(use);
      if (!p.builtin) { const ed = el("button", "btn btn-quiet", "Edit"); ed.type = "button"; ed.addEventListener("click", () => { f.edit = JSON.parse(JSON.stringify(p)); renderFantasy(); }); btns.append(ed); }
      const dup = el("button", "btn btn-quiet", "Duplicate"); dup.type = "button";
      dup.addEventListener("click", () => { f.edit = { id: "p" + Date.now().toString(36), name: p.name + " copy", teams: p.teams || 10, w: JSON.parse(JSON.stringify(p.w)) }; renderFantasy(); }); btns.append(dup);
      if (!p.builtin) { const del = el("button", "btn btn-quiet", "Delete"); del.type = "button"; del.addEventListener("click", () => { if (!confirm(`Delete "${p.name}"?`)) return; fstore.presets = fstore.presets.filter((x) => x.id !== p.id); if (fstore.current === p.id) fstore.current = "espn"; fsave(); renderFantasy(); }); btns.append(del); }
      card.append(btns); list.append(card);
    }
    const nw = el("button", "btn", "+ New preset"); nw.type = "button";
    nw.addEventListener("click", () => { f.edit = { id: "p" + Date.now().toString(36), name: "My league", teams: 10, w: { H: {}, P: {} } }; renderFantasy(); });
    box.append(list, nw);
    if (f.edit) box.append(renderFEditor());
  }
  function renderFEditor() {
    const f = state.f, e = f.edit;
    const form = el("form", "feditor"); form.addEventListener("submit", (ev) => ev.preventDefault());
    form.append(el("h3", null, fstore.presets.some((p) => p.id === e.id) ? "Edit preset" : "New preset"));
    const top = el("div", "frow");
    const nm = el("label", "field"); nm.append(el("span", null, "Name")); const ni = el("input"); ni.value = e.name; ni.addEventListener("input", () => { e.name = ni.value; }); nm.append(ni);
    const tm = el("label", "field"); tm.append(el("span", null, "Teams")); const ti = el("input"); ti.type = "number"; ti.min = 2; ti.max = 30; ti.value = e.teams || 10; ti.addEventListener("change", () => { e.teams = Math.max(2, Number(ti.value) || 10); }); tm.append(ti);
    top.append(nm, tm); form.append(top);
    const grid = el("div", "fgrid");
    for (const [g, title] of [["H", "Hitting"], ["P", "Pitching"]]) {
      const col = el("div", "fcol"); col.append(el("h4", null, title));
      for (const [k, label] of FCATS[g]) {
        const row = el("label", "fcat"); row.append(el("span", "k", k), el("span", "l", label));
        const inp = el("input"); inp.type = "number"; inp.step = "0.25"; inp.placeholder = "0"; inp.inputMode = "decimal"; inp.value = e.w[g] && e.w[g][k] != null && e.w[g][k] !== 0 ? e.w[g][k] : "";
        inp.addEventListener("input", () => { e.w[g] = e.w[g] || {}; const v = Number(inp.value); if (inp.value === "" || !v) delete e.w[g][k]; else e.w[g][k] = v; });
        row.append(inp); col.append(row);
      }
      grid.append(col);
    }
    form.append(grid);
    const btns = el("div", "fbtns");
    const sv = el("button", "btn", "Save preset"); sv.type = "submit";
    sv.addEventListener("click", () => { e.name = (e.name || "").trim() || "My league"; const i = fstore.presets.findIndex((p) => p.id === e.id); if (i >= 0) fstore.presets[i] = e; else fstore.presets.push(e); fstore.current = e.id; f.edit = null; fsave(); poolsChanged(); renderFantasy(); });
    const cx = el("button", "btn btn-quiet", "Cancel"); cx.type = "button"; cx.addEventListener("click", () => { f.edit = null; renderFantasy(); });
    btns.append(sv, cx); form.append(btns);
    return form;
  }

  /* ---------- Appearance: colour scheme, type, light / dark ---------- */
  function renderAppearance() {
    const T = window.DRAFT_THEMES, box = $("pboard"); box.innerHTML = "";
    if (!T) { box.append(el("p", "xempty", "themes.js didn't load.")); return; }
    const cur = T.current();
    box.append(el("h2", "ahead", "Appearance"));
    box.append(el("p", "hublead", "Colours and type for the whole site. A device follows the site default until you pick something on it; the phone app and Safari each count as their own device."));
    // site default: what every device shows until it picks its own (written from the Mac, shipped by Publish)
    const d = T.defaults, own = T.hasOwn();
    const def = el("div", "sitedef");
    def.append(el("b", null, "Site default: "), `${T.schemes[d.scheme] ? T.schemes[d.scheme].name : d.scheme} · ${T.fonts[d.font] ? T.fonts[d.font].name : d.font} · ${d.theme === "system" ? "match device" : d.theme} · ${d.view || "auto"} layout`);
    def.append(el("span", "note", own ? " — this device has its own choices." : " — this device is following it."));
    if (own) { const b = el("button", "btn btn-quiet", "Follow the site default here"); b.type = "button"; b.addEventListener("click", () => { T.useDefaults(); render(); }); def.append(" ", b); }
    if (window.DRAFT_LOCAL) {
      const b = el("button", "btn", "Make my choices the site default"); b.type = "button"; b.title = "Writes defaults.js — press Publish afterwards so the phone gets it";
      b.addEventListener("click", async () => {
        const c = T.current(), body = { scheme: c.scheme, font: c.font, theme: c.theme, view: T.viewPref() };
        const r = await fetch("/api/appearance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const j = await r.json(); if (j.ok) { Object.assign(T.defaults, j.defaults); T.useDefaults(); render(); alert("Saved as the site default. Press Publish in the header to send it to the phone."); }
      });
      def.append(" ", b);
    }
    box.append(def);

    // colour schemes: each card is a miniature of the banner, a button, a tier head and the chips in that scheme
    box.append(el("h3", "asub", "Color scheme"));
    const sg = el("div", "schemes");
    for (const [id, sc] of Object.entries(T.schemes)) {
      const L = sc.light;
      const b = el("button", "scheme"); b.type = "button"; b.setAttribute("aria-pressed", String(id === cur.scheme));
      const pv = el("div", "spv");
      const bar = el("div", "spv-bar"); bar.style.background = L["accent-2"]; bar.style.borderBottom = `3px solid ${L.rule}`; bar.style.boxShadow = `0 2px 0 ${L["stripe-line"]}`;
      const year = el("span", "spv-year", "2027"); year.style.color = L.pop;
      const word = el("span", "spv-word", "Draft Board"); word.style.color = L["accent-2-ink"];
      const tab = el("span", "spv-tab", "Rankings"); tab.style.color = L["accent-2-dim"];
      bar.append(year, word, tab);
      const row = el("div", "spv-row");
      const btn = el("span", "spv-btn", "Edit rankings"); btn.style.background = L.btn || L["accent-2"]; btn.style.color = L["btn-ink"] || L["accent-2-ink"];
      const chip = el("span", "spv-chip", "All hitters · 597"); chip.style.color = L["accent-2-text"];
      row.append(btn, chip);
      const tier = el("div", "spv-tier", "Tier 1"); tier.style.background = L["accent-2"]; tier.style.color = L["accent-2-ink"];
      const meters = el("div", "spv-meters");
      for (const [w, pct] of [[0.9, 92], [0.35, 30], [0.62, 64]]) { const m = el("div", "spv-meter"); const f = el("i"); f.style.width = `${w * 100}%`; paint(f, pct); m.append(f); meters.append(m); }
      pv.append(bar, row, tier, meters);
      b.append(pv, el("span", "sname", sc.name), el("span", "sblurb", sc.blurb));
      b.addEventListener("click", () => { T.set({ scheme: id }); renderAppearance(); });
      sg.append(b);
    }
    box.append(sg);

    // light / dark
    box.append(el("h3", "asub", "Light or dark"));
    const seg = el("div", "seg"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Light or dark");
    for (const [v, l] of [["system", "Match the phone / Mac"], ["light", "Light"], ["dark", "Dark"]]) {
      const sb = el("button", "segbtn", l); sb.type = "button"; sb.setAttribute("aria-pressed", String(v === cur.theme));
      sb.addEventListener("click", () => { T.set({ theme: v }); renderAppearance(); });
      seg.append(sb);
    }
    box.append(seg);

    // layout
    box.append(el("h3", "asub", "Layout"));
    const lseg = el("div", "seg"); lseg.setAttribute("role", "group"); lseg.setAttribute("aria-label", "Layout");
    for (const [v, l] of [["auto", "Auto"], ["mobile", "Mobile"], ["desktop", "Desktop"]]) {
      const sb = el("button", "segbtn", l); sb.type = "button"; sb.setAttribute("aria-pressed", String(v === T.viewPref()));
      sb.addEventListener("click", () => { T.setView(v); renderAppearance(); });
      lseg.append(sb);
    }
    box.append(lseg);
    box.append(el("p", "note", "Auto gives phones the compact layout: filters fold behind one button, each row's percentile chips scroll sideways, and the card opens as a full-width sheet. Desktop on a phone shows the full layout zoomed out."));

    // type
    box.append(el("h3", "asub", "Font"));
    T.preloadFonts();
    const fg = el("div", "fonts");
    for (const [id, f] of Object.entries(T.fonts)) {
      const b = el("button", "fontcard"); b.type = "button"; b.setAttribute("aria-pressed", String(id === cur.font));
      const h = el("span", "fhead", "2027 Draft Board"); h.style.fontFamily = f.display;
      const body = el("span", "fbody", "Yordan Alvarez · HOU · OF, DH · .442 xwOBA · 94.2 mph"); body.style.fontFamily = f.body;
      const nums = el("span", "fnums", "0123456789 · K% BB% u(K-BB%) nERA"); nums.style.fontFamily = f.body;
      b.append(h, body, nums, el("span", "sname", f.name), el("span", "sblurb", f.blurb));
      b.addEventListener("click", () => { T.set({ font: id }); renderAppearance(); });
      fg.append(b);
    }
    box.append(fg);
    box.append(el("p", "note", "The percentile colours (blue cold, red hot) are the same in every scheme."));
  }

  /* ---------- Explore: any player, any season ---------- */
  function renderXDates() {}
  function renderExplore() {
    ensureIndex();
    const box = $("xboard"); box.innerHTML = "";
    const x = state.x;
    if (!indexReady()) { box.append(el("p", "xempty", failed.has("hist/index.js") ? "The player index (hist/index.js) hasn't been built yet." : "Loading…")); return; }
    const entry = x.id != null ? window.DRAFT_INDEX.players.find((e) => e.id === x.id) : null;
    renderXDates(null);
    if (!entry) { box.append(Object.assign(el("p", "xempty"), { innerHTML: `Type a name in the search box at the top right to open a player's card.<br><b>${indexReady() ? window.DRAFT_INDEX.players.length + " players — " : ""}every MLB season from 2015 on, plus the minors (Triple-A from 2022, Double-A / High-A / Single-A from 2021)</b> — pick the year and level under his name; percentiles are against that season and level's own league.` })); return; }
    // hitting or pitching: default by what the player primarily is, then the latest season of that kind
    const types = [...new Set(entry.s.map((sv) => sv[2]))];
    const type = types.includes(x.type) ? x.type : primaryType(entry);
    const ofType = entry.s.filter((sv) => sv[2] === type);
    const cur = ofType.find((sv) => sv[0] === x.ds) || ofType[0];
    const head = el("div", "xhead");
    head.append(headshot(entry.id, entry.name));
    head.append(el("h2", null, entry.name));
    head.append(el("span", "xmeta", `${cur[5]} · ${seasonTag(cur)}`));
    if (types.length > 1) {
      const seg = el("div", "seg"); seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Hitting or pitching");
      for (const [t, l] of [["H", "Hitting"], ["P", "Pitching"]]) {
        const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(t === type));
        b.addEventListener("click", () => { if (t !== type) { const first = entry.s.find((sv) => sv[2] === t && sv[1] === cur[1]) || entry.s.find((sv) => sv[2] === t); state.x = { id: entry.id, type: t, ds: first[0] }; savePrefs(); render(); } });
        seg.append(b);
      }
      head.append(seg);
    } else head.append(el("span", "xmeta", type === "P" ? "Pitching" : "Hitting"));
    const curP = DATA.players.find((q) => q.id === entry.id && q.type === type);
    if (curP) head.append(renderStarControl(curP));
    box.append(head);
    const chips = el("div", "xseasons");
    chips.append(el("span", "splbl", "Season"));
    chips.append(renderSeasonPicker(ofType, cur[0], (key) => { state.x = { id: entry.id, type, ds: key }; savePrefs(); render(); }));
    box.append(chips);
    // the card, drawn against that season's dataset
    const key = cur[0];
    if (!state.x.ds || state.x.ds !== key || state.x.type !== type) state.x = { id: entry.id, type, ds: key };
    ensureHist(key);
    const ds = histDataset(key);
    renderXDates(ds);
    if (!ds) { box.append(el("p", "xempty", failed.has(`hist/${key}.js`) ? `hist/${key}.js is missing — run build_history.py` : `Loading ${key.startsWith("mlb-") ? key.slice(4) : key.replace("aaa-", "") + " Triple-A"} season…`)); return; }
    withDataset(ds, () => withWindow(state.cardWin, () => withSplit(state.split, () => {
      const p = ds.players.find((q) => q.id === entry.id && q.type === type);
      if (!p) { box.append(el("p", "xempty", "No card for that season.")); return; }
      if (needsDays() && !DS.ready()) { DS.load(); const c = el("div", "card"); c.append(renderSplitBar(p), el("p", "note", "Loading game-by-game data…")); box.append(c); return; }
      const g = p.type === "H" ? "H" : p.primary;
      const st = pool(g).stats.get(p.type + p.id) || rankIn(g, p);
      box.append(renderCard(p, metricsFor(g), st, g, g));
    })));
  }
  // a player is primarily a pitcher if he has pitching seasons and never a real hitting season (100+ PA)
  function primaryType(entry) {
    const hasP = entry.s.some((sv) => sv[2] === "P");
    const bigH = entry.s.some((sv) => sv[2] === "H" && sv[4] >= 100);
    return hasP && !bigH ? "P" : "H";
  }
  const norm = (t) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  function searchHits(q) {
    q = q.trim();
    if (!indexReady() || q.length < 2) return [];
    return window.DRAFT_INDEX.players.filter((e) => norm(e.name).includes(norm(q))).slice(0, 10);
  }
  function renderSearchList(ul, q, onPick) {
    ul.innerHTML = "";
    const hits = searchHits(q);
    ul.hidden = hits.length === 0;
    for (const e of hits) {
      const li = el("li"); const b = el("button", "addhit"); b.type = "button";
      const years = e.s.map((sv) => sv[1]), span = Math.min(...years) === Math.max(...years) ? String(years[0]) : `${Math.min(...years)}–${Math.max(...years)}`;
      b.append(el("b", null, e.name), el("span", null, `${e.s[0][5]} · ${span}`));
      b.addEventListener("click", () => onPick(e));
      li.append(b); ul.append(li);
    }
  }
  // the header search: pick a player and go to his page
  function renderGlobalSearch() {
    renderSearchList($("glist"), state.gq, (e) => {
      const t = primaryType(e), first = e.s.find((sv) => sv[2] === t);
      state.x = { id: e.id, type: t, ds: first[0] }; state.gq = ""; $("gq").value = ""; $("gq").blur();
      state.cardWin = { from: "", to: "", last: "" }; state.split = { hand: "all", venue: "all" };   // a searched player always opens on his full season
      renderSearchList($("glist"), "", () => {});                      // close the list of hits
      savePrefs(); location.hash = "#player/" + e.id; if (state.mode === "player") render();
    });
  }

  // MLB headshot with an initials fallback (the hosted artifact can't load outside images)
  function headshot(id, name) {
    const img = el("img", "mug"); img.alt = ""; img.loading = "lazy";
    // MLB's cut-out ("silo") portrait — head and shoulders on a transparent background, the way Savant shows them
    img.src = `https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:silo:current.png/w_240,q_auto:best/v1/people/${id}/headshot/silo/current`;
    img.addEventListener("error", () => { const f = el("div", "mug initials", (name || "?").split(" ").map((w) => w[0]).slice(0, 2).join("")); img.replaceWith(f); });
    return img;
  }

  /* ---------- Compare: players side by side ---------- */
  const MAXC = 6;
  function renderCompare() {
    ensureIndex();
    renderSearchList($("clist"), state.cq, (e) => {
      if (state.cmp.players.length >= MAXC) { state.cq = ""; $("cq").value = ""; render(); return; }
      const t = state.cmp.players.length ? state.cmp.type : primaryType(e);
      const first = e.s.find((sv) => sv[2] === t) || e.s[0];
      if (!state.cmp.players.length) state.cmp.type = first[2];
      state.cmp.players.push({ id: e.id, ds: first[0] }); state.cq = ""; $("cq").value = ""; savePrefs(); render();
    });
    $("cq").disabled = state.cmp.players.length >= MAXC;
    $("cq").placeholder = state.cmp.players.length >= MAXC ? `Up to ${MAXC} players` : "Add a player to compare…";
    // hitting / pitching for the page
    const seg = $("ctype"); seg.innerHTML = "";
    for (const [t, l] of [["H", "Hitting"], ["P", "Pitching"]]) {
      const b = el("button", "segbtn small", l); b.type = "button"; b.setAttribute("aria-pressed", String(state.cmp.type === t));
      b.addEventListener("click", () => { if (state.cmp.type !== t) { state.cmp.type = t; savePrefs(); render(); } });
      seg.append(b);
    }
    const sb = $("csplit"); sb.innerHTML = ""; sb.append(renderSplitBar({ type: state.cmp.type }));
    const box = $("cboard"); box.innerHTML = "";
    const type = state.cmp.type;
    if (!indexReady()) { box.append(el("p", "cempty", "Loading player index…")); return; }
    if (!state.cmp.players.length) { box.append(Object.assign(el("p", "cempty"), { innerHTML: `Add up to six columns above to compare side by side — different players, or the same player's seasons (add him, then use “+ season” on his column).<br>Each column is that player's season, ranked against that season's league.` })); return; }
    // resolve each column: index entry, season, dataset, values + percentiles
    const cols = state.cmp.players.map((c) => {
      const entry = window.DRAFT_INDEX.players.find((e) => e.id === c.id);
      if (!entry) return { c, missing: true };
      const seasons = entry.s.filter((sv) => sv[2] === type);
      const cur = seasons.find((sv) => sv[0] === c.ds) || seasons[0];
      if (!cur) return { c, entry, seasons, none: true };
      if (cur[0] !== c.ds) c.ds = cur[0];
      ensureHist(cur[0]);
      const ds = histDataset(cur[0]);
      if (!ds) return { c, entry, seasons, cur, loading: true };
      return withDataset(ds, () => withSplit(state.split, () => {
        const p = ds.players.find((q) => q.id === c.id && q.type === type);
        if (!p) return { c, entry, seasons, cur, none: true };
        if (needsDays() && !DS.ready()) { DS.load(); return { c, entry, seasons, cur, loading: true }; }
        const g = p.type === "H" ? "H" : p.primary;
        const st = pool(g).stats.get(p.type + p.id) || rankIn(g, p);
        return { c, entry, seasons, cur, p, ds, g, st, v: V(p), n: pool(g).ref.length };
      }));
    });
    const wrap = el("div", "cwrap");
    const grid = el("div", "cgrid"); grid.style.setProperty("--np", cols.length);
    const mobile = document.documentElement.dataset.view === "mobile";
    const avail = Math.max(320, (box.clientWidth || document.documentElement.clientWidth) - 32);
    const cw = mobile ? 150 : Math.max(160, Math.min(246, Math.floor((avail - 132 - 22 * cols.length) / Math.max(1, cols.length))));
    grid.style.setProperty("--cw", cw + "px");
    grid.append(el("div", "ccorner"));                        // corner (sticky with the header row)
    cols.forEach((col, i) => {
      const cellHd = el("div", "chead"); const hd = el("div", "plate"); cellHd.append(hd);
      const top = el("div", "cmeta");
      const x = el("button", "unadd big", "×"); x.type = "button"; x.title = "Remove"; x.addEventListener("click", () => { state.cmp.players.splice(i, 1); savePrefs(); render(); });
      hd.append(headshot(col.c.id, col.entry ? col.entry.name : "?"));
      hd.append(el("h3", null, col.entry ? col.entry.name : "?"));
      if (col.seasons && col.seasons.length) {
        hd.append(renderSeasonPicker(col.seasons, col.cur[0], (key) => { col.c.ds = key; savePrefs(); render(); }, true));
        if (col.seasons.length > 1 && state.cmp.players.length < MAXC) {
          const used = new Set(state.cmp.players.filter((q) => q.id === col.c.id).map((q) => q.ds));
          const next = col.seasons.find((sv) => !used.has(sv[0]));
          if (next) { const add = el("button", "linkbtn cadd", `+ ${seasonTag(next)}`); add.type = "button"; add.title = "Add another column for this player's next season"; add.addEventListener("click", () => { state.cmp.players.splice(i + 1, 0, { id: col.c.id, ds: next[0] }); savePrefs(); render(); }); top.append(add); }
        }
      }
      if (col.none) top.append(el("span", null, `No ${type === "H" ? "hitting" : "pitching"} seasons`));
      else if (col.loading) top.append(el("span", null, "Loading…"));
      else top.append(el("span", null, `${type === "H" ? col.v.pa + " PA" : fmtIP(col.v.ip) + " IP"} · ${col.v.ctx && col.v.ctx.G != null ? col.v.ctx.G + " G · " : ""}${col.p.age != null ? "age " + col.p.age : ""}`));
      top.append(x); hd.append(top);
      grid.append(cellHd);
    });
    const groups = type === "H" ? CARD : CARD_P;
    const cell = (m, col) => {
      const d = el("div", "ccell");
      if (!col.st) { d.classList.add("na"); d.append(el("div", "track"), el("div", "val", "–")); return d; }
      const v = metricValue(m, col.v, col.st), pct = col.st.pct[m.key];
      const track = el("div", "track");
      if (pct != null) { const s = pctStyle(pct); const f = el("div", "fill"); f.style.width = pct + "%"; f.style.background = s.bg; track.append(f); const b = el("div", "bub", pct); b.style.left = pct + "%"; b.style.background = s.bg; track.append(b); }
      else d.classList.add("na");
      d.append(track, el("div", "val", v == null ? "–" : fmt(v, m)));
      d.title = `${col.entry.name} ${col.cur[1]} — ${m.label}: ${v == null ? "n/a" : fmt(v, m)} (${pct == null ? "n/a" : ordinal(pct) + " pctl"})`;
      return d;
    };
    const chosen = cmpKeys(type), SUBS = type === "H" ? SUB : SUB_P;
    for (const grp of groups) {
      const ms = grp.metrics.filter((m) => chosen.has(m.key));
      if (!ms.length) continue;
      grid.append(el("div", "cgroup", grp.group));
      for (const m of ms) {
        const lbl = el("div", "clbl", m.label);
        const subs = (SUBS[m.key] || []).filter((sm) => chosen.has(sm.key));
        const isOpen = !!state.open[m.key];
        if (subs.length) {
          const t = el("button", "fold", isOpen ? "▾" : "▸"); t.type = "button"; t.title = `${isOpen ? "Hide" : "Show"} ${subs.map((x) => x.label).join(" / ")}`; t.setAttribute("aria-expanded", String(isOpen));
          t.addEventListener("click", () => { state.open[m.key] = !isOpen; savePrefs(); render(); });
          lbl.append(t);
        }
        grid.append(lbl);
        for (const col of cols) grid.append(cell(m, col));
        if (isOpen) for (const sm of subs) { grid.append(el("div", "clbl sub", sm.label)); for (const col of cols) grid.append(cell(sm, col)); }
      }
    }
    wrap.append(grid); box.append(wrap);
    box.style.setProperty("--ctb-h", $("ctoolbar").offsetHeight + "px");
    box.append(el("p", "note", `Each column is ranked against its own season's qualifiers (hitters ${REF_PA}+ PA; pitchers by that season's usage). Splits apply to every column; date ranges live on the player cards.`));
  }

  // Compare: which stats are on the grid (every card stat and fold-out unless chosen otherwise)
  const cmpAll = (type) => { const seen = new Set(); for (const grp of (type === "H" ? CARD : CARD_P)) for (const m of grp.metrics) for (const x of [m, ...((type === "H" ? SUB : SUB_P)[m.key] || [])]) seen.add(x.key); return [...seen]; };
  const cmpKeys = (type) => new Set(state.cmpCols[type] || cmpAll(type));
  function renderCmpPick() {
    parkControls();
    const modal = $("modal"), body = $("modal-body"); modal.hidden = false; document.body.classList.add("modal-open"); body.innerHTML = "";
    const type = state.cmp.type, pit = type === "P";
    const w = el("div", "textmodal colpick");
    const h2 = el("h2", null, `Stats to compare · ${pit ? "pitchers" : "hitters"}`); h2.id = "modal-title"; w.append(h2);
    w.append(el("p", "note", "Tick the stats to show on the Compare grid; fold-out stats sit under their parent with an arrow."));
    const cur = cmpKeys(type);
    const setKeys = (keys) => { state.cmpCols[type] = keys; savePrefs(); };
    const grid = el("div", "colgrid"), seen = new Set();
    for (const grp of (pit ? CARD_P : CARD)) {
      const sec = el("div", "colgroup"); sec.append(el("h4", null, grp.group));
      for (const m of grp.metrics) for (const x of [m, ...((pit ? SUB_P : SUB)[m.key] || [])]) {
        if (seen.has(x.key)) continue; seen.add(x.key);
        const l = el("label", "toggle" + (x === m ? "" : " subt")); const c = el("input"); c.type = "checkbox"; c.checked = cur.has(x.key);
        c.addEventListener("change", () => { const now = cmpKeys(type); if (c.checked) now.add(x.key); else now.delete(x.key); setKeys(cmpAll(type).filter((k) => now.has(k))); renderCompare(); });
        l.append(c, " ", x.label); sec.append(l);
      }
      grid.append(sec);
    }
    w.append(grid);
    const row = el("div", "row");
    const done = el("button", "btn", "Done"); done.type = "button"; done.addEventListener("click", () => closePanel(false));
    const all = el("button", "btn btn-quiet", "Everything"); all.type = "button"; all.addEventListener("click", () => { delete state.cmpCols[type]; savePrefs(); render(); });
    const none = el("button", "btn btn-quiet", "None"); none.type = "button"; none.addEventListener("click", () => { setKeys([]); render(); });
    row.append(done, all, none); w.append(row); body.append(w);
  }
  $("cstats").addEventListener("click", () => { state.panel = "cmpstats"; render(); });

  // what the two toolbar buttons are set to, in one line
  function renderToolSummary() {
    const g = groupFor(state.pos), pit = isPitcherGroup(g), unit = pit ? "IP" : "PA";
    const sortSel = $("sort"), opt = sortSel.options[sortSel.selectedIndex];
    const stats = [customOrder() ? "my order" : opt ? `by ${opt.textContent.replace(/ pctl$/, "")}` : "", `${colsFor(g).length} stats`].filter(Boolean).join(" · ");
    const mob = document.documentElement.dataset.view === "mobile";
    $("statsbtn").textContent = mob ? "Stats" : "Included stats"; $("statsbtn").title = stats;
    $("splitsbtn").textContent = mob ? "Splits" : "Splits & dates";
    const bits = [];
    if (state.mode === "leaderboard") { if (state.lbSplit.hand !== "all") bits.push(`vs ${state.lbSplit.hand}H${pit ? "B" : "P"}`); if (state.lbSplit.venue !== "all") bits.push(state.lbSplit.venue); }
    if (state.mode === "trending") { const t = trendCfg(); bits.push(t.unit === "days" ? `last ${t.days} days` : `last ${t[t.unit]} ${unit}`); bits.push(`${trendMin()}+ ${unit} in span`); }
    else { const w = winIdx(); if (w) bits.push(state.win.days ? `last ${state.win.days} days` : winLabel()); bits.push(`${state.min[g]}+ ${unit}`); }
    if (state.mode === "leaderboard" && lbKey() !== CUR.key) { const ds = histDataset(lbKey()); if (ds && (ds.refPA < 100 || ds.minScale > 1)) bits.push(`(${withDataset(ds, () => effMin(g))}+ ${ds.multi && !ds.each ? "over the span" : "here"})`); }
    const active = state.mode === "leaderboard" ? (state.lbSplit.hand !== "all" || state.lbSplit.venue !== "all" || winRequested()) : state.mode === "trending" ? true : winRequested();
    $("splitsbtn").classList.toggle("on", !!active); $("statsbtn").classList.toggle("on", !customOrder() && state.sort !== "score");
    $("tsum").textContent = [stats, ...bits].join(" · ");
    $("teambtn").textContent = teamLabel(state.teamF); $("teambtn").classList.toggle("on", !!state.teamF); $("teamclear").hidden = !state.teamF;
    if (state.teamF) bits.unshift(state.teamF.kind === "team" ? (TEAM_NAMES[state.teamF.v] || state.teamF.v) : state.teamF.v);
    // the folded bar: what's in effect, in one line
    document.body.classList.toggle("tb-folded", !!state.tbFold);
    $("tbfold").hidden = !state.tbFold;
    const tab = state.pos === "ALL" ? "All hitters" : state.pos === "ALLP" ? "All pitchers" : state.pos;
    const where = state.mode === "leaderboard" && lbKey() !== CUR.key ? (histDataset(lbKey()) || {}).label || "" : "";
    $("tbfoldsum").textContent = [tab, where, stats, ...bits].filter(Boolean).join(" · ");
  }
  $("tbhide").addEventListener("click", () => { state.tbFold = true; savePrefs(); render(); });
  $("teambtn").addEventListener("click", () => openPanel("team"));
  $("teamclear").addEventListener("click", () => { state.teamF = null; state.expanded = null; savePrefs(); render(); });
  // "Team" panel: one league, one division or one team
  function renderTeamPanel() {
    parkControls();
    const modal = $("modal"), body = $("modal-body"); modal.hidden = false; document.body.classList.add("modal-open"); body.innerHTML = "";
    const w = el("div", "textmodal panel teampanel");
    const h2 = el("h2", null, "Team"); h2.id = "modal-title"; w.append(h2);
    const f = state.teamF, is = (kind, v) => !!f && f.kind === kind && f.v === v;
    const set = (kind, v) => { state.teamF = kind ? { kind, v } : null; state.expanded = null; savePrefs(); render(); renderTeamPanel(); };
    const btn = (label, on, fn, cls) => { const b = el("button", "segbtn" + (cls ? " " + cls : ""), label); b.type = "button"; b.setAttribute("aria-pressed", String(on)); b.addEventListener("click", fn); return b; };
    const sec = el("div", "psec"); sec.append(el("h4", null, "League"));
    const seg = el("div", "seg"); seg.setAttribute("role", "group");
    seg.append(btn("All teams", !f, () => set(null)), btn("AL", is("lg", "AL"), () => set("lg", "AL")), btn("NL", is("lg", "NL"), () => set("lg", "NL")));
    sec.append(seg); w.append(sec);
    const sec2 = el("div", "psec"); sec2.append(el("h4", null, "Division and team"));
    const grid = el("div", "teamgrid");
    for (const [div, teams] of Object.entries(DIVS)) {
      const col = el("div", "teamdiv");
      col.append(btn(div, is("div", div), () => set("div", div), "divbtn"));
      const list = el("div", "teamlist");
      for (const t of teams) { const b = btn("", is("team", t), () => set("team", t), "teambtn2"); b.append(el("b", null, t), " ", el("span", null, TEAM_NAMES[t] || "")); list.append(b); }
      col.append(list); grid.append(col);
    }
    sec2.append(grid);
    sec2.append(el("p", "note", "One choice at a time: a league, a division or a team. Free agents are only in All teams."));
    w.append(sec2);
    const row = el("div", "row");
    const done = el("button", "btn", "Done"); done.type = "button"; done.addEventListener("click", () => closePanel(false));
    const cancel = el("button", "btn btn-quiet", "Cancel"); cancel.type = "button"; cancel.title = "Close without keeping these changes"; cancel.addEventListener("click", () => closePanel(true));
    const clear = el("button", "btn btn-quiet", "Clear"); clear.type = "button"; clear.disabled = !f; clear.addEventListener("click", () => set(null));
    row.append(done, cancel, clear); w.append(row); body.append(w);
  }
  $("tbfoldbtn").addEventListener("click", () => { state.tbFold = false; savePrefs(); render(); });
  // the two toolbar panels: "Included stats" (sort + columns) and "Splits & dates" (splits, window, minimum)
  const PARKED = ["sortfield", "daterange", "daysfield", "lastfield", "minfield", "reffield", "lbsplit", "trendnfield", "trendunit", "trendminfield"];
  function parkControls() { const park = $("park"); for (const id of PARKED) { const n = $(id); if (n && n.parentNode !== park) park.append(n); } }
  const PANEL_KEYS = ["sort", "dir", "lb", "cols", "win", "min", "lbSplit", "trend", "pre", "teamF"];
  function openPanel(name) { state.panelSnap = JSON.stringify(Object.fromEntries(PANEL_KEYS.map((k) => [k, state[k]]))); state.panel = name; state.colPick = name === "stats"; render(); }
  function closePanel(cancel) {
    if (cancel && state.panelSnap && (state.panel === "stats" || state.panel === "splits" || state.panel === "team")) { const snap = JSON.parse(state.panelSnap); for (const k of PANEL_KEYS) state[k] = snap[k]; savePrefs(); poolsChanged(); }
    state.panelSnap = null; state.panel = null; state.colPick = false; state.expanded = null; parkControls(); render();
  }
  function renderSplitsPanel() {
    parkControls();
    const modal = $("modal"), body = $("modal-body"); modal.hidden = false; document.body.classList.add("modal-open"); body.innerHTML = "";
    const g = groupFor(state.pos), pit = isPitcherGroup(g), unit = pit ? "IP" : "PA", trending = state.mode === "trending";
    const w = el("div", "textmodal panel");
    const h2 = el("h2", null, "Splits & dates"); h2.id = "modal-title"; w.append(h2);
    if (state.mode === "leaderboard") { const sec = el("div", "psec"); sec.append(el("h4", null, "Splits")); sec.append($("lbsplit")); w.append(sec); }
    if (trending) {
      const sec = el("div", "psec"); sec.append(el("h4", null, "Span")); const row = el("div", "prow"); row.append($("trendnfield"), $("trendunit")); sec.append(row);
      sec.append(el("p", "note", "Each player's most recent plate appearances / innings, or everyone's last N calendar days."));
      const sec2 = el("div", "psec"); sec2.append(el("h4", null, "Minimum")); const row2 = el("div", "prow"); row2.append($("trendminfield")); sec2.append(row2);
      w.append(sec, sec2);
    } else if (lbMulti()) {
      const sec = el("div", "psec"); sec.append(el("h4", null, "Dates")); sec.append(el("p", "note", "A span of seasons is always the whole of each season — pick one season for a date range.")); w.append(sec);
      const sec2 = el("div", "psec"); sec2.append(el("h4", null, "Minimum")); const row2 = el("div", "prow"); row2.append($("minfield")); sec2.append(row2); sec2.append(el("p", "note", `Per season; a combined span multiplies it by the seasons in it.`)); w.append(sec2);
    } else {
      const sec = el("div", "psec"); sec.append(el("h4", null, "Dates"));
      const kinds = el("div", "seg"); kinds.setAttribute("role", "group");
      const cur = state.win.days ? "days" : lastN(state.win) ? "last" : state.win.from || state.win.to ? "range" : "season";
      for (const [v, l] of [["season", "Full season"], ["range", "Date range"], ["days", "Last N days"], ["last", `Last N ${unit}`]]) {
        const b = el("button", "segbtn", l); b.type = "button"; b.setAttribute("aria-pressed", String(cur === v));
        b.addEventListener("click", () => {
          if (v === "season") state.win = { from: "", to: "", last: "" };
          else if (v === "days") { const n = Number(state.win.days) || 30; state.win = { from: daysBack(n), to: "", last: "", days: n }; }
          else if (v === "last") { const n = Number(state.win.last) || (pit ? 30 : 100); state.win = { from: "", to: state.win.to || "", last: String(n) }; }
          else state.win = { from: state.win.from || seasonFirst(), to: state.win.to || "", last: "" };
          state.expanded = null; render();
        });
        kinds.append(b);
      }
      sec.append(kinds);
      const row = el("div", "prow");
      if (cur === "range") row.append($("daterange")); else if (cur === "days") row.append($("daysfield")); else if (cur === "last") row.append($("lastfield"), $("daterange"));
      if (cur !== "season") sec.append(row);
      sec.append(el("p", "note", cur === "days" ? `Everyone's games in the last N days through ${DATA.meta.through}.` : cur === "last" ? `Each player's most recent ${unit === "IP" ? "innings" : "plate appearances"} (through the To date, if set). Every stat and percentile is rebuilt from those games.` : cur === "range" ? "A blank side means the season's start or end. Every stat and percentile is rebuilt from those games." : "Full-season numbers."));
      const sec2 = el("div", "psec"); sec2.append(el("h4", null, "Minimum")); const row2 = el("div", "prow"); row2.append($("minfield"), $("reffield")); sec2.append(row2);
      sec2.append(el("p", "note", `Who is listed. Percentiles are always measured against ${pit ? "pitchers with 300+ batters faced" : "hitters with 300+ PA"} on the season.`));
      w.append(sec, sec2);
    }
    const row = el("div", "row");
    const done = el("button", "btn", "Done"); done.type = "button"; done.addEventListener("click", () => closePanel(false));
    const cancel = el("button", "btn btn-quiet", "Cancel"); cancel.type = "button"; cancel.title = "Close without keeping these changes"; cancel.addEventListener("click", () => closePanel(true));
    const clear = el("button", "btn btn-quiet", "Clear"); clear.type = "button";
    clear.addEventListener("click", () => { if (state.mode === "leaderboard") state.lbSplit = { hand: "all", venue: "all" }; if (!trending) state.win = { from: "", to: "", last: "" }; state.expanded = null; render(); });
    row.append(done, cancel, clear); w.append(row); body.append(w);
    renderDates(); renderMin(); renderRef(); renderLbTools(); renderTrendTools();
  }
  // "Table" panel: how the list is drawn
  function renderTablePanel() {
    parkControls();
    const modal = $("modal"), body = $("modal-body"); modal.hidden = false; document.body.classList.add("modal-open"); body.innerHTML = "";
    const g = groupFor(state.pos), T = state.tbl;
    const w = el("div", "textmodal panel");
    const h2 = el("h2", null, "Table"); h2.id = "modal-title"; w.append(h2);
    const apply = () => { savePrefs(); render(); renderTablePanel(); };
    const toggle = (label, hint, key) => { const l = el("label", "toggle trow"); const c = el("input"); c.type = "checkbox"; c.checked = !!T[key]; c.addEventListener("change", () => { T[key] = c.checked; apply(); }); const t = el("span"); t.append(el("b", null, label)); if (hint) t.append(el("small", null, hint)); l.append(c, t); return l; };
    const sec = el("div", "psec"); sec.append(el("h4", null, "Look"));
    sec.append(toggle("Heat map", "colour every number by its percentile (off = plain numbers, like Savant)", "heat"),
               toggle("Banded rows", "alternate row shading", "band"),
               toggle("Highlight the sorted stat", "shade the column the table is sorted by", "sortHl"));
    const dens = el("div", "prow"); dens.append(el("span", "plbl", "Density"));
    const dseg = el("div", "seg"); for (const [v, l] of [["comfortable", "Comfortable"], ["compact", "Compact"]]) { const b = el("button", "segbtn", l); b.type = "button"; b.setAttribute("aria-pressed", String(T.density === v)); b.addEventListener("click", () => { T.density = v; apply(); }); dseg.append(b); }
    dens.append(dseg); sec.append(dens);
    const nums = el("div", "prow"); nums.append(el("span", "plbl", "Numbers"));
    const nseg = el("div", "seg"); for (const [v, l] of [["auto", "Page default"], ["values", "Values"], ["pct", "Percentiles"]]) { const b = el("button", "segbtn", l); b.type = "button"; b.setAttribute("aria-pressed", String(T.numbers === v)); b.addEventListener("click", () => { T.numbers = v; apply(); }); nseg.append(b); }
    nums.append(nseg); sec.append(nums);
    w.append(sec);
    const sec2 = el("div", "psec"); sec2.append(el("h4", null, "Columns"));
    sec2.append(el("p", "note", "The order of the stats, left to right. ◀ ▶ move a stat; │ puts a line break after it."));
    const orderBox = el("div", "colorder"); const drawOrder = () => {
      orderBox.innerHTML = ""; orderBox.append(el("h4", null, "Column order"));
      const strip = el("div", "orderstrip"), keys = colKeys(g), all = lbOrder(g);
      keys.forEach((k, i) => { const m = all.find((x) => x.key === k); if (!m) return; const chipEl = el("span", "ochip");
        const left = el("button", "omove", "◀"); left.type = "button"; left.disabled = i === 0; left.addEventListener("click", () => { moveColKey(g, k, -1); drawOrder(); renderColhead(); renderRows(); });
        const right = el("button", "omove", "▶"); right.type = "button"; right.disabled = i === keys.length - 1; right.addEventListener("click", () => { moveColKey(g, k, 1); drawOrder(); renderColhead(); renderRows(); });
        const bk = el("button", "obrk" + (hasBreak(g, k) ? " on" : ""), "│"); bk.type = "button"; bk.title = hasBreak(g, k) ? "Remove the line break after this stat" : "Line break after this stat"; bk.addEventListener("click", () => { toggleBreak(g, k); drawOrder(); renderColhead(); renderRows(); });
        chipEl.append(left, el("span", "olbl", SHORT[m.key] || m.label), right, bk); strip.append(chipEl); });
      orderBox.append(strip);
    };
    drawOrder(); sec2.append(orderBox); w.append(sec2);
    const row = el("div", "row"); const done = el("button", "btn", "Done"); done.type = "button"; done.addEventListener("click", () => closePanel(false));
    const reset = el("button", "btn btn-quiet", "Reset to defaults"); reset.type = "button"; reset.addEventListener("click", () => { state.tbl = { heat: false, band: true, sortHl: true, density: "comfortable", numbers: "auto" }; apply(); });
    row.append(done, reset); w.append(row); body.append(w);
  }
  $("tablebtn").addEventListener("click", () => openPanel("table"));
  $("statsbtn").addEventListener("click", () => openPanel("stats"));
  $("splitsbtn").addEventListener("click", () => openPanel("splits"));
  $("listsbtn").addEventListener("click", () => openPanel("lists"));
  $("ddays").addEventListener("change", (e) => { const n = Math.max(0, Math.round(Number(e.target.value) || 0)); state.win = n ? { from: daysBack(n), to: "", last: "", days: n } : { from: "", to: "", last: "" }; state.expanded = null; render(); });
  $("ddays").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });

  /* ---------- wiring ---------- */
  const DRAFT_GROUP = ["draftmode", "rankings", "draft", "eligibility"];
  function readMode() {
    const h = location.hash.replace("#", "");
    const pm = h.match(/^player\/(\d+)$/);
    if (pm) { state.mode = "player"; const id = Number(pm[1]); if (state.x.id !== id) { state.x = { id, type: null, ds: null }; state.cardWin = { from: "", to: "", last: "" }; state.split = { hand: "all", venue: "all" }; } return; }
    if (h.startsWith("fantasy")) { state.mode = "fantasy"; const v = h.split("/")[1]; state.f.view = ["points", "advanced", "whatif", "settings"].includes(v) ? v : "points"; return; }
    state.mode = ["draft", "rankings", "compare", "eligibility", "trending", "leaderboard", "draftmode", "appearance"].includes(h) ? h : h === "explore" ? "player" : "draftmode";
  }
  // the ranking source in effect: the working rankings (Rankings page, or Draft with "My rankings"), a saved set, or none
  function orderSource() {
    if (state.mode === "rankings") return { ranks: state.ranks, tiers: state.tiers, names: state.tierNames, live: true };
    if (state.mode === "draft") {
      if (state.draftOrder === "mine") return { ranks: state.ranks, tiers: state.tiers, names: state.tierNames, live: true };
      if (state.draftOrder.startsWith("set:")) { const s = state.rankSets[state.draftOrder.slice(4)]; if (s) return { ranks: s.ranks || {}, tiers: s.tiers || {}, names: s.tierNames || {}, live: false }; }
    }
    return null;
  }
  const manualOrder = () => !!orderSource();
  // a tab with a saved order of its own: column sorting is off there, the order is the order
  const customOrder = () => { const s = orderSource(); return !!(s && (s.ranks[state.pos] || []).length); };
  window.addEventListener("hashchange", () => { readMode(); state.expanded = null; render(); });
  $("search").addEventListener("input", (e) => { state.q = e.target.value; state.expanded = null; renderRows(); });
  $("sort").addEventListener("change", (e) => { state.sort = e.target.value; state.dir = state.sort === "name" ? "asc" : "desc"; savePrefs(); render(); });
  let minTimer;
  $("min").addEventListener("input", (e) => {
    clearTimeout(minTimer);
    minTimer = setTimeout(() => {
      const v = Math.max(0, Number(e.target.value) || 0);
      state.min[groupFor(state.pos)] = v; state.expanded = null; savePrefs(); render();
    }, 250);
  });
  for (const [id, k] of [["dfrom", "from"], ["dto", "to"]]) $(id).addEventListener("change", (e) => {
    state.win[k] = e.target.value; delete state.win.days; if (k === "from" && e.target.value) state.win.last = ""; if (state.win.from && state.win.to && state.win.from > state.win.to) state.win[k === "from" ? "to" : "from"] = e.target.value;
    state.expanded = null; render();
  });
  $("dclear").addEventListener("click", () => { state.win = { from: "", to: "", last: "" }; render(); });
  $("dlast").addEventListener("change", (e) => { const v = Math.max(0, Math.round(Number(e.target.value) || 0)); state.win.last = v ? String(v) : ""; if (v) state.win.from = ""; state.expanded = null; render(); });
  $("dlast").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
  $("trendn").addEventListener("change", (e) => { const t = trendCfg(); t[t.unit] = Math.max(1, Math.round(Number(e.target.value) || 1)); savePrefs(); state.expanded = null; render(); });
  $("trendmin").addEventListener("change", (e) => { const t = trendCfg(); (t.min || (t.min = {}))[t.unit] = Math.max(0, Math.round(Number(e.target.value) || 0)); savePrefs(); render(); });
  for (const id of ["trendn", "trendmin"]) $(id).addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
  $("cq").addEventListener("input", (e) => { state.cq = e.target.value; renderCompare(); });
  $("cq").addEventListener("keydown", (e) => { if (e.key === "Enter") { const first = $("clist").querySelector("button"); if (first) first.click(); } if (e.key === "Escape") { state.cq = ""; e.target.value = ""; renderCompare(); } });
  $("cclear").addEventListener("click", () => { state.cmp.players = []; savePrefs(); render(); });
  $("gq").addEventListener("focus", ensureIndex);
  $("gq").addEventListener("input", (e) => { state.gq = e.target.value; ensureIndex(); renderGlobalSearch(); });
  $("gq").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { const first = $("glist").querySelector("button"); if (first) first.click(); }
    if (e.key === "Escape") { state.gq = ""; e.target.value = ""; renderGlobalSearch(); }
  });
  document.addEventListener("click", (e) => { if (!$("gsearch").contains(e.target) && state.gq) { state.gq = ""; $("gq").value = ""; renderGlobalSearch(); } if (!$("ctoolbar").contains(e.target) && state.cq) { state.cq = ""; $("cq").value = ""; renderSearchList($("clist"), "", () => {}); } });
  $("ref").addEventListener("change", (e) => { state.ref = e.target.value; state.expanded = null; savePrefs(); render(); });
  $("rankreset").addEventListener("click", () => ask(`Reset ${TAB_LABEL[state.pos] || state.pos}?`, "Back to big-board order, tiers and tier names cleared on this tab.", () => { delete state.ranks[state.pos]; delete state.tiers[state.pos]; delete state.tierNames[state.pos]; save(LS.ranks, state.ranks); save(LS.tiers, state.tiers); save(LS.tierNames, state.tierNames); render(); }));
  $("ranksave").addEventListener("click", saveCurrent);
  $("ranksaveas").addEventListener("click", saveAs);
  $("setpick").addEventListener("change", (e) => { const v = e.target.value; if (v === "new") newList(); else openSet(v.slice(4)); renderSetBar(); });
  $("ranknew").addEventListener("click", newList);
  $("rankrename").addEventListener("click", () => { const c = currentSetName(); if (c) renameSet(c); });
  $("rankdelete").addEventListener("click", () => { const c = currentSetName(); if (c) deleteSet(c); });
  $("rankexport").addEventListener("click", exportSets);
  for (const id of ["rankstars", "draftstars"]) $(id).addEventListener("click", () => { state.starOnly = !state.starOnly; state.page = 1; savePrefs(); render(); });
  $("rankimport").addEventListener("click", importSets);
  $("rankaddtier").addEventListener("click", () => { const b = selBottom(); if (b) { state.selKeys = []; state.selAnchor = null; tierBelow(b); } else addTier(); });
  $("rankedit").addEventListener("click", () => { state.editRanks = !state.editRanks; state.expanded = null; state.tierPick = null; state.selKeys = []; state.selAnchor = null; render(); });
  $("rankmove").addEventListener("click", () => { if (state.selKeys.length) { state.tierPick = true; render(); } });
  $("rankclear").addEventListener("click", () => { state.selKeys = []; state.selAnchor = null; render(); });
  $("rankuntier").addEventListener("click", () => { if (state.selKeys.length) moveSelectionToTier(0); });
  $("draftorder").addEventListener("change", (e) => { state.draftOrder = e.target.value; savePrefs(); render(); });
  const closeModal = () => { if (state.textModal) { state.textModal = null; render(); return; } if (state.panel || state.colPick) { closePanel(true); return; } if (state.tierPick) { state.tierPick = null; render(); return; } if (state.expanded) { state.expanded = null; render(); } };
  $("modal-close").addEventListener("click", closeModal);
  $("modal-back").addEventListener("click", closeModal);
  $("undo").addEventListener("click", undoLast);
  $("reset").addEventListener("click", resetBoard);
  $("showdrafted").addEventListener("change", (e) => { state.showDrafted = e.target.checked; savePrefs(); render(); });
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing) { e.preventDefault(); $("search").focus(); }
    if (e.key === "Escape" && (state.expanded || state.textModal || state.tierPick || state.colPick || state.panel)) closeModal();
  });

  // phone: the column header lives above the scroll box; keep it aligned with the rows sideways (either can be dragged)
  { let syncing = false;
    const pair = (a, b) => a.addEventListener("scroll", () => { if (syncing) return; syncing = true; b.scrollLeft = a.scrollLeft; syncing = false; }, { passive: true });
    pair($("bscroll"), $("colwrap")); pair($("colwrap"), $("bscroll")); }

  // keep the sticky column header just under the sticky toolbar
  const tb = document.querySelector(".toolbar:not(.xtoolbar)"), hd = document.querySelector("header.top");
  const setTb = () => { document.documentElement.style.setProperty("--toolbar-h", tb.hidden ? "0px" : tb.offsetHeight + "px"); document.documentElement.style.setProperty("--header-h", hd.offsetHeight + "px"); };
  if (window.ResizeObserver) { const ro = new ResizeObserver(setTb); ro.observe(tb); ro.observe(hd); } else window.addEventListener("resize", setTb);

  // re-read colors when the theme flips (OS setting or the host's toggle)
  const repaint = () => { readTokens(); colorCache.clear(); render(); };
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", repaint);
  new MutationObserver(repaint).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // "Update data" / "Publish" — available when the page is served by serve.py (local or --phone), which can
  // run the build scripts and push the result to Netlify
  (async function updater() {
    if (!/^https?:$/.test(location.protocol)) return;
    let st;
    try { st = await (await fetch("/api/status", { cache: "no-store" })).json(); } catch { return; }
    if (!st || typeof st.running !== "boolean") return;
    const box = $("updater"), btn = $("upbtn"), pub = $("pubbtn"), link = $("publink"), log = $("uplog"), end = $("upend");
    box.hidden = false; window.DRAFT_LOCAL = true; if (state.mode === "appearance") renderAppearance();
    const y = new Date(); y.setDate(y.getDate() - 1); end.value = y.toISOString().slice(0, 10);
    const last = (s) => s.log[s.log.length - 1] || "";
    const show = (s) => {
      log.classList.toggle("err", !!s.exit);
      if (s.site) { link.hidden = false; link.href = s.site; link.textContent = s.site.replace(/^https?:\/\//, ""); }
      pub.title = s.token ? `Push the current data to your ${s.host || "web"} link` : "Set up publishing first — see the top of publish_github.py";
      log.textContent = s.running ? (last(s) || "Starting…")
        : s.exit ? `${s.job === "publish" ? "Publish" : "Update"} failed — ${last(s)}`
        : s.job === "publish" ? "Published — the link above has the new data"
        : s.job === "update" ? "Updated — reloading…"
        : `Data through ${s.through} (built ${s.built})`;
      btn.disabled = pub.disabled = end.disabled = !!s.running;
    };
    show(st);
    let wasRunning = st.running;
    const poll = async () => {
      try { st = await (await fetch("/api/status", { cache: "no-store" })).json(); } catch { return; }
      show(st);
      if (wasRunning && !st.running) { if (!st.exit && st.job === "update") setTimeout(() => location.reload(), 800); return; }
      wasRunning = st.running;
      if (st.running) setTimeout(poll, 2000);
    };
    if (st.running) poll();
    const start = async (url) => {
      btn.disabled = pub.disabled = true; log.classList.remove("err"); log.textContent = "Starting…";
      const j = await (await fetch(url, { method: "POST" })).json();
      if (!j.ok) { log.classList.add("err"); log.textContent = j.error; btn.disabled = pub.disabled = false; return; }
      wasRunning = true; setTimeout(poll, 1500);
    };
    btn.addEventListener("click", () => start("/api/update?end=" + encodeURIComponent(end.value)));
    pub.addEventListener("click", () => start("/api/publish"));
  })();

  // body.modal-open pins the page (needed on iOS so the card, not the page, takes the scroll); keep the page's place
  // On the phone the card is a page of its own instead: the list hides, the page scrolls to the top, and comes back on close.
  let lockedY = 0;
  const mobileView = () => document.documentElement.dataset.view === "mobile";
  new MutationObserver(() => {
    const open = document.body.classList.contains("modal-open");
    if (open && !document.body.dataset.locked) {
      lockedY = window.scrollY; document.body.dataset.locked = "1";
      if (mobileView()) window.scrollTo(0, 0); else document.body.style.top = `-${lockedY}px`;
    } else if (!open && document.body.dataset.locked) {
      delete document.body.dataset.locked; document.body.style.top = ""; window.scrollTo(0, lockedY);
    }
  }).observe(document.body, { attributes: true, attributeFilter: ["class"] });

  readTokens(); readMode(); ensureSortValid(); migrateTiersToMembers(); render(); setTb();
})();
