"""Build hist/career.js: season-by-season traditional stats + career totals for every player in the search
index (MLB Stats API yearByYear + career), with our wOBA / xwOBA (hitters) and FIP / SIERA (pitchers) attached
where a season was built, and where a hitter played each season (every position, games each, from the API's
fielding lines — the season table's Pos column, 8 Oct 2026), and a hitter's FanGraphs wRC+ / BsR / Off / Def / WAR / wOBA per
season from MLB's sabermetrics stat (the season table's FanGraphs columns, 8 Oct 2026), and after those
[bWAR, sprint speed, fly balls]: Baseball-Reference's batting WAR (war_daily_bat.txt), Savant's sprint speed from our season
files, and fly balls + popups from MLB's yearByYearAdvanced for HR/FB (8 Oct 2026); then his pitching WAR that season [FanGraphs,
Baseball-Reference] or null, so a two-way player's fWAR / bWAR are the totals.  Usage: python3 build_career.py"""
import csv, io, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (draft-board career build)"}
HIT = ["gamesPlayed", "plateAppearances", "atBats", "runs", "hits", "doubles", "triples", "homeRuns", "rbi",
       "stolenBases", "baseOnBalls", "strikeOuts", "avg", "obp", "slg", "ops"]
PIT = ["wins", "losses", "era", "gamesPlayed", "gamesStarted", "saves", "inningsPitched", "hits", "homeRuns",
       "baseOnBalls", "strikeOuts", "whip", "strikeoutsPer9Inn"]
HIT_X = ["hitByPitch", "sacFlies"]          # extra counts so combined (MLB + minors) rate stats can be recomputed
PIT_X = ["earnedRuns", "battersFaced"]
CACHE = HERE / ".cache" / "milb_career"
OF_POS = {"LF": "OF", "CF": "OF", "RF": "OF"}          # the site says OF everywhere
SABR = HERE / ".cache" / "sabr"                       # FanGraphs' numbers per season; past seasons don't move, so they're kept


BREF_TEAM = {"ANA": "LAA", "CAL": "LAA", "ARI": "AZ", "OAK": "ATH", "CHW": "CWS", "FLA": "MIA", "KCR": "KC", "MON": "WSH",
             "SDP": "SD", "SFG": "SF", "TBD": "TB", "TBR": "TB", "WSN": "WSH"}   # Baseball-Reference's club codes -> the site's


def bref_war(fresh, kind="bat"):
    """{"pid|year": {"": the season's batting WAR, club: that club's}} from Baseball-Reference's daily WAR file (a row per stint).
    Cached; refetched once a day while the season runs. None when it can't be had (the caller keeps the last build's numbers).
    kind="pitch" reads war_daily_pitch.txt the same way: his pitching WAR (a two-way player's bWAR is both, 8 Oct 2026)."""
    f = SABR / ("bref-war.json" if kind == "bat" else "bref-war-pitch.json")
    if f.exists() and (not fresh or time.time() - f.stat().st_mtime < 18 * 3600):
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    try:
        r = requests.get(f"https://www.baseball-reference.com/data/war_daily_{kind}.txt", headers=UA, timeout=300)
        r.raise_for_status(); text = r.text
    except Exception as e:
        print("  Baseball-Reference WAR unavailable:", e, flush=True)
        try:
            return json.loads(f.read_text()) if f.exists() else None
        except ValueError:
            return None
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        pid, y, w = row.get("mlb_ID"), row.get("year_ID"), row.get("WAR")
        try:
            w = float(w)
        except (TypeError, ValueError):
            continue
        if not pid or not y:
            continue
        d = out.setdefault(f"{pid}|{y}", {}); t = BREF_TEAM.get(row.get("team_ID"), row.get("team_ID"))
        d[""] = d.get("", 0) + w; d[t] = d.get(t, 0) + w
    out = {k: {t: round(v, 2) for t, v in d.items()} for k, d in out.items()}
    if out:
        SABR.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(out, separators=(",", ":")))
    return out or None


def fly_balls(st):
    """Fly balls + popups, MLB's batted-ball calls (FanGraphs' HR/FB counts infield flies as fly balls too)."""
    try:
        return sum(int(st.get(k) or 0) for k in ("flyOuts", "flyHits", "popOuts", "popHits"))
    except (TypeError, ValueError):
        return None


def sabr_row(st):
    """[wRC+, BsR, Off, Def, WAR, wOBA] from MLB's sabermetrics stat, which carries FanGraphs' values: Off = batting runs + base
    running, Def = fielding runs + the positional adjustment (Ohtani 2024: 179 / 9.8 / 79.2 / -17.2 / 8.9, FanGraphs to the tenth)."""
    def f(k):
        v = st.get(k)
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None
    w, bat, br, fld, pos, war, wo = (f(k) for k in ("wRcPlus", "batting", "baseRunning", "fielding", "positional", "war", "woba"))
    r = lambda v, d: None if v is None else round(v, d)
    return [r(w, 1), r(br, 2), r(None if bat is None or br is None else bat + br, 2), r(None if fld is None or pos is None else fld + pos, 2),
            r(war, 2), r(wo, 3)]


def _get_json(url, tries=4):
    for attempt in range(tries):
        try:
            return requests.get(url, headers=UA, timeout=90).json()
        except Exception:
            time.sleep(2 + 2 * attempt)
    return None


def sabr_season(y, fresh):
    """{player id: sabr_row} for every MLB hitter that season — one request (a traded season comes as his combined line)."""
    f = SABR / f"hit-{y}.json"
    if f.exists() and not fresh:
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    js = _get_json(f"https://statsapi.mlb.com/api/v1/stats?stats=sabermetrics&group=hitting&season={y}&sportId=1&playerPool=ALL&limit=5000")
    out = {}
    for s in (js or {}).get("stats", []):
        for sp in s.get("splits", []):
            pid = (sp.get("player") or {}).get("id")
            if pid:
                out[str(pid)] = sabr_row(sp.get("stat") or {})
    if out:                                                # a failed fetch isn't cached, so the next run tries again
        SABR.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(out, separators=(",", ":")))
    return out


def sabr_pitch_season(y, fresh):
    """{player id: FanGraphs' pitching WAR} for everyone who pitched that season, MLB's sabermetrics stat (a two-way player's fWAR is
    batting + pitching, as FanGraphs' total is; 8 Oct 2026)."""
    f = SABR / f"pitch-{y}.json"
    if f.exists() and not fresh:
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    js = _get_json(f"https://statsapi.mlb.com/api/v1/stats?stats=sabermetrics&group=pitching&season={y}&sportId=1&playerPool=ALL&limit=5000")
    out = {}
    for s in (js or {}).get("stats", []):
        for sp in s.get("splits", []):
            pid, w = (sp.get("player") or {}).get("id"), (sp.get("stat") or {}).get("war")
            if pid and w is not None:
                try:
                    out[str(pid)] = round(float(w), 2)
                except (TypeError, ValueError):
                    pass
    if out:
        SABR.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(out, separators=(",", ":")))
    return out


def sabr_pitch_clubs(pid, y, teams, fresh):
    """{team code: FanGraphs' pitching WAR} for each club of a traded season he pitched in."""
    f = SABR / "clubs" / f"p{pid}-{y}.json"
    if f.exists() and not fresh:
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    js = _get_json(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=sabermetrics&group=pitching&season={y}")
    if js is None:
        return {}
    out = {}
    for s in js.get("stats", []):
        for sp in s.get("splits", []):
            tid, w = (sp.get("team") or {}).get("id"), (sp.get("stat") or {}).get("war")
            if tid and w is not None:
                out[teams.get(tid, "?")] = round(float(w), 2)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, separators=(",", ":")))
    return out


def sabr_clubs(pid, y, teams, fresh):
    """{team code: sabr_row} for each club of a traded season (the player's own sabermetrics split by team)."""
    f = SABR / "clubs" / f"{pid}-{y}.json"
    if f.exists() and not fresh:
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    js = _get_json(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=sabermetrics&group=hitting&season={y}")
    if js is None:
        return {}
    out = {}
    for s in js.get("stats", []):
        for sp in s.get("splits", []):
            tid = (sp.get("team") or {}).get("id")
            if tid:
                out[teams.get(tid, "?")] = sabr_row(sp.get("stat") or {})
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, separators=(",", ":")))
    return out


def pos_string(games):
    """{pos: games} -> "OF:97,3B:45,DH:4,2B:3", most games first (the app splits it; a row reads by fixed index)."""
    return ",".join(f"{k}:{g}" for k, g in sorted(games.items(), key=lambda kv: (-kv[1], kv[0])) if g > 0)


def fielding_splits(stats):
    """(split, raw position, games) for every fielding yearByYear row with games — DH is a position there too."""
    for s in stats:
        if s["group"]["displayName"] == "fielding" and s["type"]["displayName"] == "yearByYear":
            for sp in s["splits"]:
                pos = (sp.get("position") or {}).get("abbreviation"); g = (sp.get("stat") or {}).get("games") or 0
                if pos and g:
                    yield sp, pos, int(g)


def mlb_positions(stats):
    """{season: "OF:97,3B:45,DH:4,2B:3"}: every position he played that MLB season, games each, most first, LF / CF / RF
    folded into OF. A traded season has a row per club for each position and a combined row (no team) only for a
    position he played with both clubs, so the combined row wins and the clubs' rows are summed otherwise."""
    comb, club = {}, {}
    for sp, raw, g in fielding_splits(stats):
        if ((sp.get("sport") or {}).get("abbreviation") or "MLB") != "MLB":
            continue
        try:
            y = int(str(sp["season"]).split(".")[0])
        except (ValueError, KeyError):
            continue
        d = comb if "team" not in sp else club
        d[(y, raw)] = d.get((y, raw), 0) + g
    games = {}
    for (y, raw), g in {**club, **comb}.items():          # the combined row replaces the clubs' for the same position
        fold = OF_POS.get(raw, raw); games.setdefault(y, {}); games[y][fold] = games[y].get(fold, 0) + g
    return {y: pos_string(d) for y, d in games.items()}


def minors_positions(stats):
    """{(season, level, team name): "SS:57,OF:36"} per club line in the minors (the API's combined rows are left out —
    the table lists each club's own line)."""
    games = {}
    for sp, raw, g in fielding_splits(stats):
        lvl = (sp.get("sport") or {}).get("abbreviation") or "?"
        if lvl == "MLB" or "team" not in sp:
            continue
        try:
            season = int(str(sp["season"]).split(".")[0])
        except (ValueError, KeyError):
            continue
        k = (season, lvl, sp["team"].get("name") or ""); d = games.setdefault(k, {}); fold = OF_POS.get(raw, raw)
        d[fold] = d.get(fold, 0) + g
    return {k: pos_string(d) for k, d in games.items()}


def minors(pid, fresh):
    """Minor-league year-by-year lines for one player (every level, plus the API's combined 'Minors' line for a
    season spent at several). Cached; refreshed for players active this season."""
    f = CACHE / f"{pid}.json"
    if f.exists() and not fresh:
        try:
            cached = json.loads(f.read_text())
            if "pos" in cached:                                # a cache written before the positions (8 Oct 2026) is fetched once more
                return cached
        except ValueError:
            pass
    url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=yearByYear&group=hitting,pitching,fielding&leagueListId=milb_all"
    out = {"H": [], "P": [], "pos": {}}                   # pos: "season|level|team" -> where he played (hitters' rows take it after our numbers)
    for attempt in range(3):
        try:
            js = requests.get(url, headers=UA, timeout=60).json(); break
        except Exception:
            time.sleep(2); js = {}
    for s in js.get("stats", []):
        grp = s["group"]["displayName"]; t = "H" if grp == "hitting" else "P"
        if grp == "fielding":
            continue
        keys = (HIT + HIT_X) if t == "H" else (PIT + PIT_X)
        for sp in s["splits"]:
            st = sp["stat"]; lvl = sp.get("sport", {}).get("abbreviation") or "?"
            if lvl == "MLB":
                continue
            team = sp.get("team", {}).get("name") or ""
            try:
                season = int(str(sp["season"]).split(".")[0])      # the API has the odd "2018.1" for a split stint
            except (ValueError, KeyError):
                continue
            out[t].append([season, lvl, team] + [num(st.get(k)) for k in keys])
    out["pos"] = {"|".join(map(str, k)): v for k, v in minors_positions(js.get("stats", [])).items()}
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, separators=(",", ":")))
    return out


def num(v):
    if v in (None, "", "-.--", ".---"):
        return None
    try:
        return float(v) if "." in str(v) else int(v)
    except ValueError:
        return v


def load_js(path, prefix):
    raw = path.read_text()
    return json.loads(raw[raw.index(prefix) + len(prefix):].rstrip().rstrip(";"))


def main():
    idx = load_js(HERE / "hist" / "index.js", "window.DRAFT_INDEX = ")
    ids = [e["id"] for e in idx["players"]]
    teams = {t["id"]: t["abbreviation"] for y in range(2000, 2027)
             for t in requests.get(f"https://statsapi.mlb.com/api/v1/teams?sportId=1&season={y}", headers=UA, timeout=60).json()["teams"]}
    # our advanced numbers per player-season
    ours = {}
    cur = load_js(HERE / "data.js", "window.DRAFT_DATA = ")
    for p in cur["players"]:
        ours[(p["id"], cur["meta"]["season"], p["type"])] = p["m"]
    for f in sorted((HERE / "hist").glob("mlb-*.js")):
        raw = f.read_text(); ds = json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))
        if ds.get("kind"):
            continue                                       # spring / postseason files are not season lines
        for p in ds["players"]:
            ours[(p["id"], ds["season"], p["type"])] = p["m"]
    # minor-league level seasons we've built: keyed by the API's level names
    LVL = {"aaa": ["AAA"], "aa": ["AA"], "ap": ["A+", "A(Adv)"], "a": ["A", "A(Full)"]}
    ours_m = {}
    for lv, names in LVL.items():
        for f in sorted((HERE / "hist").glob(f"{lv}-*.js")):
            raw = f.read_text(); ds = json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))
            for p in ds["players"]:
                for nm in names:
                    ours_m[(p["id"], ds["season"], p["type"], nm)] = p["m"]

    out = {}
    now = int(cur["meta"]["season"])
    sabr = {}                                              # season -> {player id: [wRC+, BsR, Off, Def, WAR, wOBA]}, fetched on first use
    def sabr_for(y):
        if y not in sabr:
            sabr[y] = sabr_season(y, fresh=y >= now)
        return sabr[y]
    # Baseball-Reference's WAR; when the file can't be fetched, the last build's numbers carry over
    bw = bref_war(fresh=True)
    if bw is None:
        bw = {}
        try:
            prev = load_js(HERE / "hist" / "career.js", "window.DRAFT_CAREER = ")
            for pid, rec in prev.items():
                for r in rec.get("H", []):
                    if len(r) > 23 and isinstance(r[23], list) and r[23][0] is not None:
                        bw.setdefault(f"{pid}|{r[0]}", {})[""] = r[23][0]
                for r in rec.get("HT", []):
                    if len(r) > 21 and isinstance(r[21], list) and r[21][0] is not None:
                        bw.setdefault(f"{pid}|{r[0]}", {})[r[1]] = r[21][0]
        except Exception as e:
            print("  no earlier career.js to carry bWAR from:", e, flush=True)
    # pitching WAR, so a hitter who also pitched carries both (Sean, 8 Oct 2026: "for bwar and fwar include all war so like include both pitching and
    # hitting for ohtani"): Baseball-Reference's per stint, FanGraphs' per season (and per club for a traded season, below)
    bwp = bref_war(fresh=True, kind="pitch") or {}
    sabr_p = {}
    def sabr_p_for(y):
        if y not in sabr_p:
            sabr_p[y] = sabr_pitch_season(y, fresh=y >= now)
        return sabr_p[y]
    def pw_for(pid, y, club=""):                           # [FanGraphs, Baseball-Reference] pitching WAR, or None if he didn't pitch
        b = bwp.get(f"{pid}|{y}", {}).get(club)
        f = sabr_p_for(y).get(str(pid)) if not club else None
        return None if b is None and f is None else [f, b]
    ht_ext = {}                                            # (pid, season, club) -> [bWAR, None, fly balls], appended to HT rows after their FanGraphs numbers
    for i in range(0, len(ids), 80):
        chunk = ids[i:i + 80]
        url = ("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, chunk)) +
               "&hydrate=stats(group=[hitting,pitching,fielding],type=[yearByYear,career,yearByYearAdvanced])")
        for attempt in range(3):
            try:
                js = requests.get(url, headers=UA, timeout=90).json(); break
            except Exception as e:
                print("  retry", e); time.sleep(3)
        for p in js.get("people", []):
            rec = {}
            pos_by = mlb_positions(p.get("stats", []))         # where he played each season, for the hitting rows
            fb_by = {}                                         # (season, club or TOT) -> fly balls + popups, for HR/FB
            for s in p.get("stats", []):
                if s["group"]["displayName"] == "hitting" and s["type"]["displayName"] == "yearByYearAdvanced":
                    for sp in s["splits"]:
                        if (sp.get("sport") or {}).get("id", 1) != 1:
                            continue
                        fb_by[(int(sp["season"]), teams.get(sp["team"]["id"], "?") if sp.get("team") else "TOT")] = fly_balls(sp.get("stat") or {})
            for s in p.get("stats", []):
                grp, typ = s["group"]["displayName"], s["type"]["displayName"]
                if grp == "fielding" or typ == "yearByYearAdvanced":
                    continue
                keys = HIT if grp == "hitting" else PIT
                t = "H" if grp == "hitting" else "P"
                if typ == "career":
                    st = s["splits"][0]["stat"] if s["splits"] else {}
                    rec[t + "C"] = [num(st.get(k)) for k in keys]
                elif typ == "yearByYear":
                    rows = []
                    for sp in s["splits"]:
                        if "team" not in sp and sp.get("numTeams", 1) > 1:
                            pass                                   # combined line for a multi-team season
                        elif "team" not in sp:
                            pass
                        season = int(sp["season"]); st = sp["stat"]
                        team = teams.get(sp.get("team", {}).get("id"), "TOT" if "team" not in sp else "?")
                        rows.append([season, team] + [num(st.get(k)) for k in keys] + [num(st.get(k)) for k in (HIT_X if t == "H" else PIT_X)])
                    # keep one line per season: the combined line when a player had several teams
                    by = {}
                    for r in rows:
                        if r[0] not in by or r[1] == "TOT":
                            by[r[0]] = r
                    # and, beside them, each club's own line in a season with a combined one (the card's Season Stats
                    # opens a two-club year to show them); a separate key, so older copies of the page still read rows
                    multi = {k for k, r in by.items() if r[1] == "TOT"}
                    clubs = [list(r) for r in rows if r[0] in multi and r[1] != "TOT"]
                    if clubs:
                        rec[t + "T"] = sorted(clubs, key=lambda r: (r[0], r[1]))
                        if t == "H":
                            for r in clubs:
                                ht_ext[(str(p["id"]), r[0], r[1])] = [bw.get(f"{p['id']}|{r[0]}", {}).get(r[1]), None, fb_by.get((r[0], r[1]))]
                    rows = [by[k] for k in sorted(by)]
                    for r in rows:
                        m = ours.get((p["id"], r[0], t))
                        r.append(None if not m else ([m.get("woba"), m.get("xwoba_dir", m.get("xwoba"))] if t == "H"   # the site's xwOBA is the directional model (8 Oct 2026)
                                                     else [m.get("fip"), m.get("siera"), m.get("k"), m.get("bb"), m.get("kbb"), m.get("whf"), m.get("strk"),
                                                           m.get("gb"), m.get("pu")]))   # appended: the card's simple season table shows GB% / Popup%
                        if t == "H":
                            r.append(pos_by.get(r[0], ""))     # then where he played — the app reads a row by fixed index (8 Oct 2026)
                            r.append(sabr_for(r[0]).get(str(p["id"])))   # then FanGraphs' wRC+ / BsR / Off / Def / WAR / wOBA (or null)
                            r.append([bw.get(f"{p['id']}|{r[0]}", {}).get(""), (m or {}).get("spd"), fb_by.get((r[0], r[1]))])   # then bWAR, sprint speed, fly balls
                            r.append(pw_for(p["id"], r[0]))   # then his pitching WAR [FanGraphs, B-Ref] that season, or null
                    rec[t] = rows
            if rec:
                out[str(p["id"])] = rec
        print(f"  {min(i + 80, len(ids))}/{len(ids)}", flush=True)
    # a traded season's clubs get their own FanGraphs numbers, appended to the HT rows (threaded; past seasons cached)
    tr = sorted({(pid, r[0]) for pid, rec in out.items() for r in rec.get("HT", [])})
    with ThreadPoolExecutor(max_workers=8) as ex:
        for (pid, y), clubs in zip(tr, ex.map(lambda a: sabr_clubs(a[0], a[1], teams, fresh=a[1] >= now), tr)):
            for r in out[pid]["HT"]:
                if r[0] == y:
                    r.append(clubs.get(r[1]))
                    r.append(ht_ext.get((pid, r[0], r[1]), [None, None, None]))   # then the club's bWAR and fly balls
                    pw = pw_for(pid, r[0], r[1])                    # then the club's pitching WAR [FanGraphs, B-Ref], or null
                    if pw is not None:
                        pw[0] = sabr_pitch_clubs(pid, y, teams, fresh=y >= now).get(r[1])
                    r.append(pw)
    print(f"  FanGraphs numbers: {len(sabr)} seasons, {len(tr)} traded seasons split by club", flush=True)
    # minor-league lines: threaded, cached; players on this season's board are refreshed every run
    current = {p["id"] for p in cur["players"]}
    todo = [(pid, pid in current) for pid in ids]
    done = 0
    milb = {}
    def with_adv(pid, t, rows, pos):
        out_rows = []
        for r in rows:
            m = ours_m.get((pid, r[0], t, r[1]))
            adv = None if not m else ([m.get("woba"), m.get("xwoba_dir", m.get("xwoba")), m.get("whf")] if t == "H" else [m.get("fip"), m.get("siera"), m.get("whf"), m.get("strk"),
                                                                                                      m.get("gb"), m.get("pu")])   # appended: GB% / Popup% for the minors' season table
            out_rows.append(list(r) + [adv] + ([pos.get("|".join(map(str, r[:3])), "")] if t == "H" else []))   # then where he played (a cache written before 8 Oct 2026 has none)
        return out_rows
    with ThreadPoolExecutor(max_workers=8) as ex:
        for pid, res in zip([t[0] for t in todo], ex.map(lambda t: minors(*t), todo)):
            rec = {}
            if res.get("H"): rec["H"] = with_adv(pid, "H", res["H"], res.get("pos") or {})
            if res.get("P"): rec["P"] = with_adv(pid, "P", res["P"], {})
            if rec: milb[str(pid)] = rec
            done += 1
            if done % 500 == 0:
                print(f"  minors {done}/{len(todo)}", flush=True)
    mpath = HERE / "hist" / "minors.js"          # separate file: only fetched when a card switches to MiLB / All levels
    mpath.write_text("window.DRAFT_MINORS = " + json.dumps(milb, separators=(",", ":")) + ";\n")
    print(f"OK {len(milb)} players with minor-league lines -> {mpath.name} ({mpath.stat().st_size / 1e6:.1f} MB)")
    path = HERE / "hist" / "career.js"
    path.write_text("window.DRAFT_CAREER = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print(f"OK {len(out)} players -> {path.name} ({path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
