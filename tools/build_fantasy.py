"""Build the fantasy-points data: official season counting stats (MLB Stats API) for every player on the board,
per-game pitching logs (for points per start / quality starts), and Savant expected stats (xBA / xSLG / xwOBA,
pitcher xERA) for the luck-neutral view. Plus the bonus categories ESPN scores that no season line carries: grand
slams (home runs with the bases loaded, the API's r123 split), cycles (from each hitter's game log), game-winning RBI
(the RBI that put the winners ahead for good, from every game's scoring plays), and fielding (assists, putouts,
outfield assists, double plays).

    python3 build_fantasy.py                 # the current season -> fantasy.js
    python3 build_fantasy.py 2025 2024       # past seasons -> hist/fantasy-YYYY.js (players from hist/mlb-YYYY.js)

Output: window.DRAFT_FANTASY["YYYY"] = {season, through, hk, pk, gk, hitters: {id: [...hk]}, pitchers: {id: {s: [...pk],
g: [[...gk], ...]}}, xh: {id: [xba, xslg, xwoba]}, xp: {id: [xba, xslg, xwoba, xera]}}.  Points themselves are computed
in the browser from whichever scoring preset is chosen, so any ESPN setting works without a rebuild.
"""
import io, json, sys, time
from pathlib import Path
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (draft-board fantasy build)"}
HK = ["G", "PA", "AB", "H", "2B", "3B", "HR", "R", "RBI", "BB", "IBB", "HBP", "K", "SB", "CS", "GIDP", "SF", "SH", "TB", "E",
      "A", "PO", "OFA", "DPT", "GSHR", "CYC", "GWRBI"]
H_API = ["gamesPlayed", "plateAppearances", "atBats", "hits", "doubles", "triples", "homeRuns", "runs", "rbi", "baseOnBalls",
         "intentionalWalks", "hitByPitch", "strikeOuts", "stolenBases", "caughtStealing", "groundIntoDoublePlay", "sacFlies",
         "sacBunts", "totalBases"]
PK = ["G", "GS", "OUTS", "W", "L", "SV", "HD", "BS", "K", "H", "ER", "R", "HR", "BB", "IBB", "HBP", "CG", "SHO", "WP", "BK", "PK", "BF", "AB", "GF", "SVO",
      "TB", "GIDP", "NP"]
P_API = ["gamesPlayed", "gamesStarted", "outs", "wins", "losses", "saves", "holds", "blownSaves", "strikeOuts", "hits", "earnedRuns",
         "runs", "homeRuns", "baseOnBalls", "intentionalWalks", "hitBatsmen", "completeGames", "shutouts", "wildPitches", "balks",
         "pickoffs", "battersFaced", "atBats", "gamesFinished", "saveOpportunities", "totalBases", "groundIntoDoublePlay",
         "numberOfPitches"]
GK = ["date", "GS", "OUTS", "W", "L", "SV", "HD", "BS", "K", "H", "ER", "R", "HR", "BB", "HBP", "CG", "SHO"]
G_API = ["gamesStarted", "outs", "wins", "losses", "saves", "holds", "blownSaves", "strikeOuts", "hits", "earnedRuns", "runs",
         "homeRuns", "baseOnBalls", "hitBatsmen", "completeGames", "shutouts"]


def log(msg):
    print(msg, flush=True)


def load_js(path, prefix):
    raw = path.read_text()
    return json.loads(raw[raw.index(prefix) + len(prefix):].rstrip().rstrip(";"))


def get(url, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=120)
            r.raise_for_status()
            return r.json()
        except Exception as e:                       # noqa: BLE001
            log(f"  retry {i + 1}: {e}")
            time.sleep(3)
    raise SystemExit("MLB Stats API unreachable")


def season_split(splits):
    """The season line: the combined split when a player had several teams, else the single one."""
    if not splits:
        return None
    tot = [s for s in splits if "team" not in s]
    return (tot or splits)[0]["stat"]


def ival(st, k):
    v = st.get(k)
    return int(v) if isinstance(v, (int, float)) else 0


def split_total(splits, k):
    """One number from a situational split: the combined line when there is one, else the teams' lines added up."""
    tot = [s for s in splits if "team" not in s]
    return ival(tot[0]["stat"], k) if tot else sum(ival(s["stat"], k) for s in splits)


def grand_slams(ids, season):
    out = {}
    for i in range(0, len(ids), 80):
        chunk = ids[i:i + 80]
        url = ("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, chunk)) +
               f"&hydrate=stats(group=[hitting],type=[statSplits],sitCodes=[r123],season={season})")
        for p in get(url).get("people", []):
            for s in p.get("stats", []):
                n = split_total([sp for sp in s["splits"] if sp.get("split", {}).get("code") == "r123"], "homeRuns")
                if n:
                    out[p["id"]] = n
    log(f"  grand slams: {sum(out.values())} by {len(out)} hitters")
    return out


def cycles(ids, season):
    out = {}
    for i in range(0, len(ids), 60):
        chunk = ids[i:i + 60]
        url = ("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, chunk)) +
               f"&hydrate=stats(group=[hitting],type=[gameLog],season={season})")
        for p in get(url).get("people", []):
            for s in p.get("stats", []):
                for sp in s["splits"]:
                    if sp.get("gameType", "R") != "R":
                        continue
                    st = sp["stat"]
                    d, t, hr = ival(st, "doubles"), ival(st, "triples"), ival(st, "homeRuns")
                    if d and t and hr and ival(st, "hits") - d - t - hr > 0:
                        out[p["id"]] = out.get(p["id"], 0) + 1
    log(f"  cycles: {sum(out.values())}")
    return out


def game_winning_rbi(season, through):
    """ESPN's GWRBI: in every game won, the RBI that gave the winners the lead they never gave back. Walks each final
    game's scoring plays (the schedule hydrates them, ten days a request) and credits the batter on the last play that
    put the winners ahead, when that play drove in a run (not a wild pitch or an error)."""
    out, day = {}, pd.Timestamp(f"{season}-03-01")
    dated = len(str(through)) == 10 and str(through)[:4] == str(season) and str(through)[4] == "-"
    last = pd.Timestamp(through) if dated else pd.Timestamp(f"{season}-11-30")
    while day <= last:
        end = min(day + pd.Timedelta(days=9), last)
        url = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&gameType=R&startDate={day.date()}&endDate={end.date()}"
               "&hydrate=scoringplays")
        for d in get(url).get("dates", []):
            for g in d.get("games", []):
                if g.get("status", {}).get("abstractGameState") != "Final":
                    continue
                a, h = g["teams"]["away"].get("score"), g["teams"]["home"].get("score")
                if a is None or h is None or a == h:
                    continue
                home_won, ahead, go = h > a, False, None
                for sp in g.get("scoringPlays", []):
                    r = sp.get("result", {})
                    w, l = (r.get("homeScore", 0), r.get("awayScore", 0)) if home_won else (r.get("awayScore", 0), r.get("homeScore", 0))
                    if w > l and not ahead and (sp.get("about", {}).get("halfInning") == "bottom") == home_won:
                        go = sp
                    ahead = w > l
                if go and go.get("result", {}).get("rbi", 0) > 0:
                    b = go.get("matchup", {}).get("batter", {}).get("id")
                    if b:
                        out[b] = out.get(b, 0) + 1
        day = end + pd.Timedelta(days=1)
    log(f"  game-winning RBI: {sum(out.values())}")
    return out


def savant_expected(kind, season):
    url = f"https://baseballsavant.mlb.com/leaderboard/expected_statistics?type={kind}&year={season}&position=&team=&min=1&csv=true"
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text.lstrip("﻿"))).set_index("player_id")
    cols = ["est_ba", "est_slg", "est_woba"] + (["xera"] if kind == "pitcher" else [])
    out = {}
    for pid, row in df.iterrows():
        vals = [None if pd.isna(row[c]) else round(float(row[c]), 3) for c in cols]
        out[str(int(pid))] = vals
    log(f"  savant expected ({kind}): {len(out)}")
    return out


def build(season, current):
    if current:
        data = load_js(HERE / "data.js", "window.DRAFT_DATA = ")
        players, through = data["players"], data["meta"]["through"]
    else:
        ds = load_js(HERE / "hist" / f"mlb-{season}.js", f'window.DRAFT_HIST["mlb-{season}"] = ')
        players, through = ds["players"], f"{season} season"
    hit_ids = sorted({p["id"] for p in players if p["type"] == "H"})
    pit_ids = sorted({p["id"] for p in players if p["type"] == "P"})
    ids = sorted(set(hit_ids) | set(pit_ids))
    log(f"{season}: {len(hit_ids)} hitters, {len(pit_ids)} pitchers")

    hitters, pitchers = {}, {}
    for i in range(0, len(ids), 80):
        chunk = ids[i:i + 80]
        url = ("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, chunk)) +
               f"&hydrate=stats(group=[hitting,pitching,fielding],type=[season],season={season})")
        for p in get(url).get("people", []):
            fld = [0, 0, 0, 0, 0]                          # errors, assists, putouts, outfield assists, double plays
            for s in p.get("stats", []):
                grp = s["group"]["displayName"]
                if grp == "fielding":
                    for sp in s["splits"]:
                        if "team" in sp or len(s["splits"]) == 1:
                            st = sp["stat"]
                            fld[0] += ival(st, "errors"); fld[1] += ival(st, "assists"); fld[2] += ival(st, "putOuts")
                            fld[4] += ival(st, "doublePlays")
                            if (st.get("position") or sp.get("position") or {}).get("type") == "Outfielder":
                                fld[3] += ival(st, "assists")
            for s in p.get("stats", []):
                grp = s["group"]["displayName"]
                st = season_split(s["splits"])
                if not st:
                    continue
                if grp == "hitting" and p["id"] in hit_ids:
                    hitters[str(p["id"])] = [ival(st, k) for k in H_API] + fld + [0, 0, 0]
                elif grp == "pitching" and p["id"] in pit_ids:
                    pitchers[str(p["id"])] = {"s": [ival(st, k) for k in P_API], "g": []}
        log(f"  season stats {min(i + 80, len(ids))}/{len(ids)}")

    for i in range(0, len(pit_ids), 60):
        chunk = pit_ids[i:i + 60]
        url = ("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, chunk)) +
               f"&hydrate=stats(group=[pitching],type=[gameLog],season={season})")
        for p in get(url).get("people", []):
            rec = pitchers.get(str(p["id"]))
            if not rec:
                continue
            for s in p.get("stats", []):
                if s["group"]["displayName"] != "pitching":
                    continue
                rows = []
                for sp in s["splits"]:
                    if sp.get("gameType", "R") != "R":
                        continue
                    st = sp["stat"]
                    rows.append([int(sp["date"].replace("-", ""))] + [ival(st, k) for k in G_API])
                rec["g"] = sorted(rows)
        log(f"  game logs {min(i + 60, len(pit_ids))}/{len(pit_ids)}")

    # the bonus categories, each best-effort: an API hiccup costs that column, not the build
    for col, fn in (("GSHR", lambda: grand_slams(hit_ids, season)), ("CYC", lambda: cycles(hit_ids, season)),
                    ("GWRBI", lambda: game_winning_rbi(season, through))):
        try:
            got = fn()
        except (Exception, SystemExit) as e:          # noqa: BLE001
            log(f"  !! {col} skipped: {e}")
            continue
        j = HK.index(col)
        for pid, n in got.items():
            if str(pid) in hitters:
                hitters[str(pid)][j] = n

    xh = savant_expected("batter", season)
    xp = savant_expected("pitcher", season)
    out = {"season": season, "through": through, "hk": HK, "pk": PK, "gk": GK,
           "hitters": hitters, "pitchers": pitchers,
           "xh": {k: v for k, v in xh.items() if k in hitters}, "xp": {k: v for k, v in xp.items() if k in pitchers}}
    path = HERE / ("fantasy.js" if current else f"hist/fantasy-{season}.js")
    path.write_text(f'window.DRAFT_FANTASY = window.DRAFT_FANTASY || {{}};\nwindow.DRAFT_FANTASY["{season}"] = '
                    + json.dumps(out, separators=(",", ":")) + ";\n")
    log(f"OK {season}: {len(hitters)} hitters, {len(pitchers)} pitchers -> {path.relative_to(HERE)} ({path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    cur = load_js(HERE / "data.js", "window.DRAFT_DATA = ")["meta"]["season"]
    years = [int(a) for a in sys.argv[1:]] or [cur]
    for y in years:
        build(y, y == cur)
