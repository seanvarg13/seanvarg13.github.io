// A made-up ESPN fantasy baseball league for testing the League tab (11 Nov 2026) without anyone's real league: eight teams named Team 1-8,
// rosters dealt from this season's data.js in a snake by playing time, a schedule with scores, a draft, ESPN's own field names and numbering.
// Players carry ESPN ids from hist/ids.js where it has them; a few don't, so the page's name match gets exercised too.
//
//   const { league } = require("./league_fixture.cjs"); league({ points: true, auction: true, live: false }) → the JSON ESPN would send
//
// Used by tools/check_site.cjs (its "league" step answers ESPN's API with it) and by hand.
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const read = (f, key) => { const t = fs.readFileSync(path.join(ROOT, f), "utf8"); return JSON.parse(t.slice(t.indexOf("{"), t.lastIndexOf("}") + 1)); };
const TEAMS = [null, "BAL", "BOS", "LAA", "CWS", "CLE", "DET", "KC", "MIL", "MIN", "NYY", "ATH", "SEA", "TEX", "TOR", "ATL", "CHC", "CIN", "HOU", "LAD", "WSH", "NYM", "PHI", "PIT", "STL", "SD", "SF", "COL", "MIA", "AZ", "TB"];
const POS = { SP: 1, C: 2, "1B": 3, "2B": 4, "3B": 5, SS: 6, LF: 7, CF: 8, RF: 9, OF: 8, DH: 10, RP: 11 };
const SLOT = { C: 0, "1B": 1, "2B": 2, "3B": 3, SS: 4, OF: 5, DH: 11, UTIL: 12, P: 13, SP: 14, RP: 15, BE: 16, IL: 17 };

function league(o = {}) {
  const D = read("data.js"), ids = read("hist/ids.js"), espnOf = new Map(Object.entries(ids.espn).map(([e, m]) => [m, +e]));
  const season = D.meta.season, N = 8, H = D.players.filter((p) => p.type === "H" && p.team !== "FA").sort((a, b) => (b.pa || 0) - (a.pa || 0)).slice(0, N * 12);
  const P = D.players.filter((p) => p.type === "P" && p.team !== "FA").sort((a, b) => (b.ip || 0) - (a.ip || 0)).slice(0, N * 9);
  const deal = (xs) => { const out = Array.from({ length: N }, () => []); xs.forEach((p, i) => { const r = Math.floor(i / N), k = i % N; out[r % 2 ? N - 1 - k : k].push(p); }); return out; };
  const hs = deal(H), ps = deal(P);
  let fake = 9100000;
  const entry = (p, slot, k) => {
    const pos = p.type === "P" ? (p.primary === "RP" ? "RP" : "SP") : Object.keys(p.pos || {}).sort((a, b) => p.pos[b] - p.pos[a])[0] || "DH";
    // every seventh player without his ESPN id: the page has to find him by name and club
    const eid = k % 7 === 3 ? fake++ : espnOf.get(p.id) || fake++;
    const elig = p.type === "P" ? [13, pos === "SP" ? 14 : 15, 16, 17] : [...new Set(Object.keys(p.pos || {}).map((x) => (["LF", "CF", "RF"].includes(x) ? 5 : SLOT[x])).filter((x) => x != null)), 12, 16, 17];
    return { acquisitionType: "DRAFT", injuryStatus: k % 11 === 5 ? "TEN_DAY_DL" : "NORMAL", lineupSlotId: SLOT[slot], playerId: eid,
      playerPoolEntry: { id: eid, player: { id: eid, fullName: p.name, proTeamId: Math.max(0, TEAMS.indexOf(p.team)), defaultPositionId: POS[pos] || 10, eligibleSlots: elig, injuryStatus: k % 11 === 5 ? "TEN_DAY_DL" : "ACTIVE" } } };
  };
  const hitSlots = ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "UTIL", "BE", "BE", "BE"], pitSlots = ["P", "P", "P", "P", "P", "P", "P", "BE", "BE"];
  const teams = Array.from({ length: N }, (_, i) => {
    const roster = [...hs[i].map((p, k) => entry(p, hitSlots[k] || "BE", k)), ...ps[i].map((p, k) => entry(p, pitSlots[k] || "BE", k + 20))];
    const w = 12 - i, l = 8 + i, pf = 9000 - i * 180;
    const vals = { 20: 820 - i * 15, 5: 230 - i * 6, 21: 800 - i * 14, 23: 90 + i * 5, 2: 0.262 - i * 0.002, 53: 85 - i * 2, 57: 60 + (i % 3) * 8, 48: 1450 - i * 20, 47: 3.6 + i * 0.07, 41: 1.18 + i * 0.012 };
    return { id: i + 1, name: `Team ${i + 1}`, abbrev: `T${i + 1}`, playoffSeed: i + 1, rankCalculatedFinal: [2, 1, 3, 4, 5, 6, 7, 8][i], rankFinal: 0, points: 0,
      record: { overall: { wins: o.points === false ? w * 10 : w, losses: o.points === false ? l * 10 : l, ties: o.points === false ? 12 : 0, pointsFor: o.points === false ? 0 : pf, pointsAgainst: o.points === false ? 0 : 8400 + i * 40, gamesBack: i * 1.5, percentage: w / (w + l) } },
      valuesByStat: vals, roster: { entries: roster } };
  });
  const schedule = [];
  let gid = 1;
  for (let per = 1; per <= 20; per++) for (let k = 0; k < N / 2; k++) {
    const a = (k + per) % N, b = (N - 1 - k + per) % N; if (a === b) continue;
    const pa = 420 + ((a * 37 + per * 11) % 90) - a * 6, pb = 420 + ((b * 29 + per * 7) % 90) - b * 6;
    schedule.push({ id: gid++, matchupPeriodId: per, playoffTierType: "NONE", winner: pa > pb ? "HOME" : pa < pb ? "AWAY" : "TIE",
      home: { teamId: a + 1, totalPoints: o.points === false ? 0 : pa, cumulativeScore: { wins: 6, losses: 4, ties: 0 } }, away: { teamId: b + 1, totalPoints: o.points === false ? 0 : pb, cumulativeScore: { wins: 4, losses: 6, ties: 0 } } });
  }
  schedule.push({ id: gid++, matchupPeriodId: 21, playoffTierType: "WINNERS_BRACKET", winner: "AWAY", home: { teamId: 1, totalPoints: 880.5, cumulativeScore: { wins: 5, losses: 6, ties: 1 } }, away: { teamId: 2, totalPoints: 902, cumulativeScore: { wins: 6, losses: 5, ties: 1 } } });
  // the draft: the rosters in the order they were dealt, a price falling with the pick
  const picks = [];
  const rounds = Math.max(...teams.map((t) => t.roster.entries.length));
  for (let r = 0; r < rounds; r++) for (let k = 0; k < N; k++) {
    const ti = r % 2 ? N - 1 - k : k, e = teams[ti].roster.entries[r]; if (!e) continue;
    picks.push({ overallPickNumber: picks.length + 1, roundId: r + 1, roundPickNumber: k + 1, teamId: ti + 1, playerId: e.playerId, bidAmount: o.auction ? Math.max(1, 60 - Math.floor(picks.length / 3)) : 0, keeper: picks.length === 5 });
  }
  const live = !!o.live, shown = live ? picks.slice(0, 37) : picks;
  const items = o.points === false
    ? [20, 5, 21, 23, 2, 53, 57, 48, 47, 41].map((id) => ({ statId: id, points: 1, isReverseItem: id === 47 || id === 41 }))
    : [[8, 1], [20, 1], [21, 1], [23, 1], [10, 1], [27, -1], [34, 1], [53, 2], [54, -2], [60, 2], [57, 5], [45, -2], [37, -1], [48, 1], [39, -1], [31, 10]].map(([id, pts]) => ({ statId: id, points: pts, isReverseItem: false }));
  return {
    gameId: 2, id: 424242, seasonId: season, segmentId: 0, scoringPeriodId: 188,
    draftDetail: { drafted: !live, inProgress: live, picks: shown },
    settings: { name: "Test League", size: N, isPublic: true,
      scoringSettings: { scoringType: o.points === false ? "H2H_CATEGORY" : "H2H_POINTS", scoringItems: items },
      draftSettings: { type: o.auction ? "AUCTION" : "SNAKE", auctionBudget: o.auction ? 260 : 0, date: Date.parse(season + "-03-22T23:00:00Z") },
      rosterSettings: { lineupSlotCounts: { 0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 3, 12: 1, 13: 7, 16: 5, 17: 2 } },
      scheduleSettings: { matchupPeriodCount: 20, playoffTeamCount: 4 }, acquisitionSettings: { isUsingAcquisitionBudget: false } },
    status: { currentMatchupPeriod: 21, finalScoringPeriod: 187, latestScoringPeriod: live ? 1 : 188, isActive: true },
    teams, schedule,
  };
}
module.exports = { league };
if (require.main === module) process.stdout.write(JSON.stringify(league({ points: !process.argv.includes("--cats"), auction: process.argv.includes("--auction"), live: process.argv.includes("--live") })));
