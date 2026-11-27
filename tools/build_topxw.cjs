// All-time top xwOBA seasons for home (Sean, 18 Nov 2026) → hist/topxw.js, from hist/career-bb.js + hist/index.js.
// 300+ PA (110 in 2020); both footings (pk = with his parks, n = park-neutral), top 25 each. Run after build_career.py.
const fs = require("fs"), path = require("path"), R = path.join(__dirname, "..");
global.window = {}; require(R + "/hist/career-bb.js"); require(R + "/hist/index.js");
const c = window.DRAFT_CAREER_BB, K = c.keys, iPA = K.indexOf("pa"), iN = K.indexOf("txw") + 1, iP = K.indexOf("txwpk") + 1;
const who = {}; for (const p of window.DRAFT_INDEX.players) for (const s of p.s) if (s[0] === "mlb-" + s[1] && s[2] === "H") { const w = (who[p.id] = who[p.id] || { n: p.name, t: {}, pa: {} }); w.t[s[1]] = s[5]; w.pa[s[1]] = s[4]; }
const all = [];
for (const [id, ys] of Object.entries(c.p)) for (const [y, r] of Object.entries(ys)) {
  const pa = who[id] && who[id].pa[y]; if (!(pa >= (+y === 2020 ? 110 : 300)) || !who[id]) continue;
  all.push({ id: +id, nm: who[id].n, y: +y, tm: who[id].t[y] || "", pa, n: r[iN], pk: r[iP] != null ? r[iP] : r[iN] });
}
const top = (k) => all.filter((x) => x[k] != null).sort((a, b) => b[k] - a[k]).slice(0, 25).map((x) => [x.id, x.nm, x.y, x.tm, x.pa, +x[k].toFixed(4)]);
// Stuff SIERA (27 Nov 2026): pitchers with an inning per team game (60 in 2020), lowest first
const PK = c.pkeys, iS = PK.indexOf("siera"), iU = PK.indexOf("stuff"), pw = {};
for (const p of window.DRAFT_INDEX.players) for (const s of p.s) if (s[0] === "mlb-" + s[1] && s[2] === "P") { const w = (pw[p.id] = pw[p.id] || { n: p.name, t: {}, ip: {} }); w.t[s[1]] = s[5]; w.ip[s[1]] = s[4]; }
const sp = [];
for (const [id, ys] of Object.entries(c.pp || {})) for (const [y, r] of Object.entries(ys)) {
  const w = pw[id], ip = w && w.ip[y]; if (!(ip >= (+y === 2020 ? 60 : 162)) || r[iS] == null || r[iU] == null) continue;
  sp.push([+id, w.n, +y, w.t[y] || "", ip, +(r[iS] - 0.056 * (r[iU] - 100)).toFixed(2)]);
}
const ss = sp.sort((a, b) => a[5] - b[5]).slice(0, 25);
fs.writeFileSync(R + "/hist/topxw.js", "window.DRAFT_TOPXW = " + JSON.stringify({ pk: top("pk"), n: top("n"), ss }) + ";\n");
