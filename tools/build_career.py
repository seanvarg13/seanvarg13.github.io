"""Build hist/career.js: season-by-season traditional stats + career totals for every player in the search
index (MLB Stats API yearByYear + career), with our wOBA / xwOBA (hitters) and FIP / SIERA (pitchers) attached
where a season was built, and where a hitter played each season (every position, games each, from the API's
fielding lines — the season table's Pos column, 8 Oct 2026), and a hitter's FanGraphs wRC+ / BsR / Off / Def / WAR / wOBA per
season from MLB's sabermetrics stat (the season table's FanGraphs columns, 8 Oct 2026), and after those
[bWAR, sprint speed, fly balls]: Baseball-Reference's batting WAR (war_daily_bat.txt), Savant's sprint speed from our season
files, and fly balls + popups from MLB's yearByYearAdvanced for HR/FB (8 Oct 2026); then his pitching WAR that season [FanGraphs,
Baseball-Reference] or null, so a two-way player's fWAR / bWAR are the totals.  Usage: python3 build_career.py"""
import csv, io, json, re, time
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


def ld_hr(y, fresh):
    """{mlbam id: home runs Statcast calls line drives or ground balls} for a season, from Savant's search (one request a season, every such
    homer as a row). HR/FB is Savant's way (Sean, 8 Oct 2026: "Let's do savants version", after a day on FanGraphs' counts): MLB's fly balls +
    popups — Statcast's calls — with these homers added to the fly balls, since every home run is on top of the ratio and a line-drive one
    wasn't under it (Wood 2025: 31 HR, 3 of them liners, 86 fly balls → 31 / 89). Cached in .cache/sabr/ldhr-<y>.json; this season refetched
    after 18 hours. Statcast starts in 2015 — an earlier season gets {}. None when Savant can't be had (the caller adds nothing)."""
    if y < 2015:
        return {}
    f = SABR / f"ldhr-{y}.json"
    if f.exists() and (not fresh or time.time() - f.stat().st_mtime < 18 * 3600):
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    try:
        r = requests.get("https://baseballsavant.mlb.com/statcast_search/csv", headers=UA, timeout=300,
                         params={"all": "true", "hfAB": "home\\.\\.run|", "hfBBT": "line\\.\\.drive|ground\\.\\.ball|", "hfGT": "R|",
                                 "hfSea": f"{y}|", "player_type": "batter", "type": "details", "min_pitches": 0, "min_results": 0})
        r.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))))
    except Exception as e:
        print(f"  Savant line-drive homers {y} unavailable:", e, flush=True)
        try:
            return json.loads(f.read_text()) if f.exists() else None
        except ValueError:
            return None
    out = {}
    for row in rows:
        if row.get("events") == "home_run" and row.get("batter"):
            out[row["batter"]] = out.get(row["batter"], 0) + 1
    SABR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, separators=(",", ":")))
    return out


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


# the season table's other views on a hitter's page (Sean, 8 Oct 2026: "a bar that allows the ability to switch between the stats we currently
# have, a batted ball quality table, a batted ball distribution table, and a plate discipline table"): every MLB hitter-season's numbers from
# data.js and hist/mlb-*.js, [BBE, …SBX_KEYS] by id and season, in hist/career-bb.js — its own file, loaded only when one of those tables is
# picked. The app reads it by SBX_KEYS' order, so append to the end only.
SBX_KEYS = ["ev", "ev90", "maxev", "hh", "brl", "ss", "bs", "evfb", "evld", "evgb",
            "gb", "ld", "fb", "pu", "air", "pull", "pullp", "cent", "oppo", "mixw",
            "swing", "zsw", "osw", "con", "zcon", "ocon", "whf",
            "brfb", "brld",   # barrels per fly ball / line drive, xHR/FB's inputs (8-9 Oct 2026)
            "pullfb",         # Pull FB%: his pulled fly balls over all his balls in play, from the Mix buckets (ctx.mix; Sean, 9-10 Oct 2026)
            "babip", "xbabip", "spd",   # the card's xBABIP tab by season: BABIP, the directional xBABIP, sprint speed (Sean, 9 Oct 2026)
            "sba",                      # steal attempts (SB + CS), the season table's Baserunning view (Sean, 9 Oct 2026)
            "txw",                      # talent xwOBA, the season table's column after xwOBA (Sean, 11 Oct 2026) — talent_season() below
            "gbp",                      # GB Pull%: the share of his grounders pulled (ctx.gbdir), an xBABIP driver (11 Oct 2026)
            "xbabd",                    # the nine drivers' xBABIP — the site's xBABIP since 15 Oct 2026 (xbab_drivers below; "xbabip" stays the model's)
            "pkhr", "pkbab",            # what his parks did to his HR/FB (points) and BABIP (points), ball by ball (build_data.py park_fields; 15 Oct 2026) — the HR / FB and BABIP by season tables' Park columns
            "pa",                       # his PA that season — xwOBA proj. weights his last two seasons' talent by it (app.js projFill; 16 Oct 2026); the file also carries "lg": {season: the talent league's wOBA}
            "txwpk",                    # xwOBA with his parks put back on each piece (Sean, 18 Oct 2026: the site's xwOBA includes the park; "txw" stays the park-neutral one) — talent_of(..., park=True)
            "xslg", "xslgpk",           # xSLG from skills at a neutral park and with his parks (Sean, 23 Oct 2026; xslg_of below, app.js XSLG)
            "xiso", "xisopk"]           # xISO, xSLG less the xBA the same pieces make, neutral / with his parks (Sean, 23 Oct 2026; xiso_of below) — the card's ISO by season


# Talent xwOBA (Sean, 11 Oct 2026: "an xwoba based purely on their talent ... their batted ball mix, k rate, bb rate, xbabip minus luck and noise,
# and xHR/fb rate"): wOBA rebuilt from expected rates only — xK% (the site's hitter fit), xBB% (chase, zone swing, contact rates, the share of
# pitches he sees in the zone, EV90), his HBP, xHR/FB on his fly balls + popups, the eight-driver xBABIP on the rest (no Noise, no Luck) and
# the directional model's extra bases per hit — each season scaled so its 300+ PA hitters average their real wOBA. app.js's talentOf /
# talentLeague are the same arithmetic on the card's view; keep the two in step. Fitted / tested 2015-26 (scratch twcore.js): next season's
# wOBA r .536 (xwOBA .437, wOBA .479), year to year .663 (xwOBA .539)
TW_XK = (-0.08, {"whf": 0.989, "zsw": -0.212, "osw": -0.272, "strk": 0.523})
# xBB% with intentional walks per 100 PA and fouls per contact (12 Oct 2026, app.js TW_XBB); TW_XBB0 without them for a file that lacks the two
TW_XBB = {"osw": -0.413, "zsw": -0.067, "ocon": 0.017, "zcon": -0.047, "zsn": -0.446, "ev90": 0.011, "ibbr": 1.109, "fcon": 0.177}
TW_XBB0 = {"osw": -0.448, "zsw": -0.030, "ocon": 0.034, "zcon": -0.113, "zsn": -0.539, "ev90": 0.056}
# GB Pull% joined (11 Oct 2026): the share of his grounders pulled, × his grounders' share of his non-HR balls in play like Sprint (app.js XBAB)
# and by batter side (11 Oct 2026; app.js XBAB_GBP): "gbp" is only the sign, TW_XBAB_GBP the weight for his side, a switch hitter 70% lefty
TW_XBAB = {"ld": 3.73, "pu": -3.16, "evgb": 2.05, "gbp": -1, "evld": 1.24, "ldp": 0.29, "spd": 14 * 0.83, "oppo": 0.41, "fb": -0.72}
TW_XBAB_GBP = {"R": -0.61, "L": -1.48, "S": 0.3 * -0.61 + 0.7 * -1.48}
TW_XHRFB = [{"evfb": 0.345, "brfb": 0.394, "brld": 0.219, "pfb": 0.094}, {"evfb": 0.373, "brfb": 0.391, "brld": 0.217},
            {"evfb": 0.779, "brl": 0.738}, {"brl": 1.037, "ev90": 0.499}]
TW_W = {"bb": 0.69, "hbp": 0.72, "s": 0.88, "d": 1.25, "hr": 2.03}
TW_ACT = 0.5   # share of his actual K% / BB% in the talent pieces (app.js TW.act)
TW_USE_EV = False   # since 16 Oct 2026 the barrel fit (TW_XHRFB, the xHR/FB tab's) is the HR piece, as in app.js; True puts exit velocity alone back
TW_HF = (0.096, {"evfb": 1.364, "ev90": 0.822, "pfb": 0.097})   # the HR piece on exit velocity alone (app.js TW_HF), fitted on park-neutral home runs since 15 Oct 2026; XHRFB the fallback
# xSLG from skills (Sean, 23 Oct 2026; app.js XSLG — keep the two in step): the talent pieces as total bases per at-bat, the extra bases half the
# model's (tph re-centred on the league's real bases per non-HR hit) and half the skills fit below; tiers without sprint speed or LD EV follow
TW_XSLG = (0.5, [{"gb": -0.00303, "spd": 0.01555, "evld": 0.00569, "pullp": 0.00199}, {"gb": -0.00261, "evld": 0.00484, "pullp": 0.0018},
                 {"gb": -0.00319, "spd": 0.01432, "pullp": 0.00217}, {"gb": -0.00278, "pullp": 0.00197}])


def _tw_inputs(p):
    m, cx = p.get("m") or {}, p.get("ctx") or {}
    mx = cx.get("mix") or []
    if len(mx) < 8: mx = None
    tot = sum(x or 0 for x in mx) if mx else 0
    fbn = (mx[1] or 0) + (mx[5] or 0) + (mx[6] or 0) + (mx[7] or 0) if mx else 0
    fb3 = (mx[5] or 0) + (mx[6] or 0) + (mx[7] or 0) if mx else 0
    ld3 = (mx[2] or 0) + (mx[3] or 0) + (mx[4] or 0) if mx else 0
    xbt = cx.get("xbt"); xn = sum(z[0] for z in xbt) if xbt else 0
    gd = cx.get("gbdir"); gn = sum(gd) if gd else 0
    return {"m": m, "mx": mx, "fbn": fbn, "pa": p.get("pa") or 0, "ab": p.get("ab") or 0, "hbp": cx.get("HBP"), "hr": cx.get("HR"),
            "pfb": 100 * mx[5] / fb3 if fb3 else None, "ldp": 100 * mx[2] / ld3 if ld3 else None,
            "fbs": fbn / tot if tot else None, "gbs": 100 * xbt[0][0] / xn if xn else m.get("gb"), "gbp": 100 * gd[0] / gn if gn else None, "bats": p.get("bats")}


def talent_league(players, ref_pa):
    H = [p for p in players if p.get("type") == "H"]
    def wavg(rows, key_fn, w_fn):
        s = w = 0.0
        for q in rows:
            v, wt = key_fn(q), w_fn(q)
            if v is None or not wt: continue
            s += v * wt; w += wt
        return s / w if w else None
    L = {"k": {}}
    k20 = [q for q in H if (q.get("pa") or 0) >= 20]
    for k in ("k", "whf", "zsw", "osw", "strk"):
        L["k"][k] = wavg(k20, lambda q: (q.get("m") or {}).get(k), lambda q: q["pa"])
    ref = [q for q in H if (q.get("pa") or 0) >= ref_pa]
    I = [_tw_inputs(q) for q in ref]
    for k in ("bb", "osw", "zsw", "ocon", "zcon", "zsn", "ev90", "ibbr", "fcon", "woba", "xbabip", "ld", "pu", "evgb", "evld", "spd", "oppo", "fb", "gb", "pullp"):
        L[k] = wavg(I, lambda i: i["m"].get(k), lambda i: i["pa"])
    # xSLG's (TW_XSLG): the league's real bases per hit that isn't a home run (park-neutral) and its sacrifice share of PA
    tb = h1 = 0.0
    for i in I:
        m0 = i["m"]
        if m0.get("slg") is None or m0.get("ba") is None or i["hr"] is None or not i["ab"]: continue
        h = m0["ba"] * i["ab"] - i["hr"]
        if h <= 0: continue
        tb += m0["slg"] * i["ab"] - 4 * i["hr"] - (m0.get("pkxb") or 0) * h; h1 += h
    L["tphA"] = tb / h1 if h1 else None
    L["o"] = wavg(I, lambda i: None if i["m"].get("bb") is None else max(0.0, (i["pa"] - i["ab"]) / i["pa"] - i["m"]["bb"] / 100 - (i["hbp"] or 0) / i["pa"]), lambda i: i["pa"])
    L["ldp"] = wavg(I, lambda i: i["ldp"], lambda i: i["pa"])
    L["gbp"] = wavg(I, lambda i: i["gbp"], lambda i: i["pa"])
    F = [i for i in I if i["mx"] and i["hr"] is not None and i["fbn"]]
    hr, fb = sum(i["hr"] for i in F), sum(i["fbn"] for i in F)
    L["hr"] = {"hrfb": 100 * hr / fb if fb else None}
    for k in ("evfb", "brfb", "brld", "pfb", "brl", "ev90"):
        L["hr"][k] = wavg(F, lambda i: i[k] if k == "pfb" else i["m"].get(k), lambda i: i["fbn"])
    L["twh"] = {k: wavg(F, lambda i: i[k] if k == "pfb" else i["m"].get(k), lambda i: i["pa"]) for k in TW_HF[1]}
    L["scale"] = 1.0
    a = b = 0.0
    for i in I:
        t = talent_of(i, L)
        if t is not None and i["m"].get("woba") is not None: a += t * i["pa"]; b += i["m"]["woba"] * i["pa"]
    L["scale"] = b / a if a else None
    # the model's extra bases, PA-weighted (app.js L.tph), then xSLG's scale: its qualifiers' at-bat-weighted xSLG on their real SLG
    tw = tn = 0.0
    for i in I:
        c = {}
        if talent_of(i, L, out=c) is not None: tw += c["tph"] * i["pa"]; tn += i["pa"]
    L["tph"] = tw / tn if tn else None
    a = b = 0.0
    for i in I:
        x = xslg_of(i, L, scaled=False)
        if x is not None and i["m"].get("slg") is not None: a += x * i["ab"]; b += i["m"]["slg"] * i["ab"]
    L["sslg"] = b / a if a else None
    # and xBA's (app.js L.sba), for xISO: its qualifiers' at-bat-weighted xBA from the same pieces on their real BA
    a = b = 0.0
    for i in I:
        x = _xs_parts(i, L)
        if x is not None and i["m"].get("ba") is not None: a += x[1] * i["ab"]; b += i["m"]["ba"] * i["ab"]
    L["sba"] = b / a if a else None
    return L


def xbab_drivers(i, L):
    """the nine drivers' xBABIP (app.js xbabDrivers): the league's model xBABIP moved by each driver against the league, or None"""
    if L.get("xbabip") is None: return None
    m, xbab, n = i["m"], L["xbabip"], 0
    for k, v in TW_XBAB.items():
        his = i[k] if k in ("ldp", "gbp") else m.get(k)
        lg = L.get(k); g = i["gbs"] if k in ("spd", "gbp") else 100
        if his is None or lg is None or g is None: continue
        if k == "gbp": v = TW_XBAB_GBP.get(i["bats"], -0.95)
        xbab += v * (his - lg) * g / 100 / 1000; n += 1
    return xbab if n else None


def talent_of(i, L, park=False, out=None):
    """his raw talent wOBA (times L['scale'] once that is set), or None; park=True puts his parks' residual back on every piece (app.js talentCore's
    rawPk — the site's xwOBA since 18 Oct 2026), None when the season carries no park numbers. out, a dict, gets the park-neutral pieces (xslg_of)"""
    m = i["m"]
    if not i["mx"] or not i["pa"] or not i["ab"] or m.get("dxba") is None or m.get("dxslg") is None or L.get("xbabip") is None \
            or L["hr"]["hrfb"] is None or L.get("scale") is None or i["fbs"] is None:
        return None
    c, w = TW_XK
    if any(m.get(k) is None or L["k"].get(k) is None for k in w) or L["k"].get("k") is None: return None
    xk = L["k"]["k"] + c + sum(w[k] * (m[k] - L["k"][k]) for k in w)
    xb = TW_XBB if all(m.get(k) is not None and L.get(k) is not None for k in ("ibbr", "fcon")) else TW_XBB0
    xbb = L["bb"] + sum(v * (m[k] - L[k]) for k, v in xb.items() if m.get(k) is not None and L.get(k) is not None)
    # half his actual K% / BB%, half the expected rate (app.js TW.act): the blend forecast next season's K%, BB% and wOBA better than either alone
    # — the actual halves park-neutral (15 Oct 2026, app.js talentCore): less his parks' effect on them (m.pkk / pkbb, build_data.py from hist/parks.js)
    if m.get("k") is not None: xk = TW_ACT * (m["k"] - (m.get("pkk") or 0)) + (1 - TW_ACT) * xk
    if m.get("bb") is not None: xbb = TW_ACT * (m["bb"] - (m.get("pkbb") or 0)) + (1 - TW_ACT) * xbb
    hbp = (i["hbp"] or 0) / i["pa"]
    bx = {"evfb": m.get("evfb"), "brfb": m.get("brfb"), "brld": m.get("brld"), "pfb": i["pfb"], "brl": m.get("brl"), "ev90": m.get("ev90")}
    twh = L.get("twh") or {}
    if TW_USE_EV and all(bx[k] is not None and twh.get(k) is not None for k in TW_HF[1]):
        xhf = max(0.0, L["hr"]["hrfb"] + TW_HF[0] + sum(v * (bx[k] - twh[k]) for k, v in TW_HF[1].items()))
    else:
        fit = next((f for f in TW_XHRFB if all(bx[k] is not None and L["hr"].get(k) is not None for k in f)), None)
        if fit is None: return None
        xhf = max(0.0, L["hr"]["hrfb"] + sum(v * (bx[k] - L["hr"][k]) for k, v in fit.items()))
    hrb = xhf / 100 * i["fbs"]
    xbab = xbab_drivers(i, L)
    if xbab is None: return None
    bip = max(0.0, 1 - xk / 100 - xbb / 100 - hbp); xhr = hrb * bip * i["pa"]
    tph = min(1.7, max(1.0, (m["dxslg"] * i["ab"] - 4 * xhr) / max(1.0, m["dxba"] * i["ab"] - xhr)))
    vh = TW_W["s"] + (tph - 1) * (TW_W["d"] - TW_W["s"])
    raw = TW_W["bb"] * xbb / 100 + TW_W["hbp"] * hbp + bip * (hrb * TW_W["hr"] + (1 - hrb) * xbab * vh)
    if out is not None: out.update(xk=xk, xbb=xbb, hbp=hbp, xhf=xhf, xbab=xbab, tph=tph)
    if park:
        # the same skills in the parks he hit in (Sean, 18 Oct 2026: "for Hunter Goodman and other say Rockies players I want to see their park
        # factor included in their xwOBA since it does impact their production and will next year too"): K%, BB%, xHR/FB, xBABIP and bases per
        # hit each moved by his parks' residual on it (m.pkk / pkbb / pkhr / pkbab / pkxb), the pieces put back together the same way
        if all(m.get(k) is None for k in ("pkhr", "pkbab", "pkxb", "pkk", "pkbb")): return None
        g = lambda k: m.get(k) or 0
        xk, xbb, xhf, xbab, tph = xk + g("pkk"), xbb + g("pkbb"), xhf + g("pkhr"), xbab + g("pkbab") / 1000, tph + g("pkxb")
        bip = max(0.0, 1 - xk / 100 - xbb / 100 - hbp); hrb = xhf / 100 * i["fbs"]
        vh = TW_W["s"] + (tph - 1) * (TW_W["d"] - TW_W["s"])
        raw = TW_W["bb"] * xbb / 100 + TW_W["hbp"] * hbp + bip * (hrb * TW_W["hr"] + (1 - hrb) * xbab * vh)
    return raw * L["scale"]


def xslg_of(i, L, park=False, scaled=True):
    """his xSLG from skills (app.js talentCore's xs / talentOf's xslgN, xslgPk), or None: the talent pieces as total bases per at-bat, the extra
    bases half the model's tph re-centred on the league's real bases per non-HR hit and half TW_XSLG's skills fit; park=True moves every piece by
    his parks' residual as talent_of does"""
    x = _xs_parts(i, L, park)
    if x is None: return None
    if not scaled: return x[0]
    return x[0] * L["sslg"] if L.get("sslg") else None


def xiso_of(i, L, park=False):
    """his xISO (app.js talentOf's xiso): xSLG less the xBA the same pieces make — hits per at-bat (app.js baRaw), scaled by L['sba'] — or None"""
    x = _xs_parts(i, L, park)
    if x is None or not L.get("sslg") or not L.get("sba"): return None
    return x[0] * L["sslg"] - x[1] * L["sba"]


def _xs_parts(i, L, park=False):
    """(total bases, hits) per at-bat from the talent pieces, unscaled (app.js slgRaw, baRaw), or None"""
    m, c = i["m"], {}
    if L.get("tph") is None or L.get("tphA") is None or talent_of(i, L, out=c) is None: return None
    tier = next((T for T in TW_XSLG[1] if all(m.get(k) is not None and L.get(k) is not None for k in T)), None)
    if tier is None: return None
    sk = L["tphA"] + sum(v * (m[k] - L[k]) for k, v in tier.items())
    tm = min(1.8, max(1.0, L["tphA"] + c["tph"] - L["tph"]))   # a hit is a base at least
    tx = min(1.8, max(1.0, TW_XSLG[0] * tm + (1 - TW_XSLG[0]) * sk))
    hbp = c["hbp"]; o = max(0.0, (i["pa"] - i["ab"]) / i["pa"] - (m["bb"] / 100 if m.get("bb") is not None else c["xbb"] / 100) - hbp)
    xk, xbb, xhf, xbab = c["xk"], c["xbb"], c["xhf"], c["xbab"]
    if park:
        if all(m.get(k) is None for k in ("pkhr", "pkbab", "pkxb", "pkk", "pkbb")): return None
        g = lambda k: m.get(k) or 0
        xk, xbb, xhf, xbab, tx = xk + g("pkk"), xbb + g("pkbb"), xhf + g("pkhr"), xbab + g("pkbab") / 1000, tx + g("pkxb")
    bip = max(0.0, 1 - xk / 100 - xbb / 100 - hbp); hrb = xhf / 100 * i["fbs"]; ab = 1 - xbb / 100 - hbp - o
    if ab <= 0: return None
    return bip * (4 * hrb + (1 - hrb) * xbab * tx) / ab, bip * (hrb + (1 - hrb) * xbab) / ab


# a pitcher's season numbers for his season table (Sean, 9 Oct 2026: "ERA, FIP, nERA, and SIERA ... k%, bb%, popup%, gb% ... whiff% and xBB%"):
# nERA, SIERA, Popup% and the three strike rates xBB% is built from (the app runs XBBF on them), under "pkeys" / "pp" in the same file
SBP_KEYS = ["nera", "siera", "pu", "strk", "fstrk", "b3strk"]


def season_bb():
    out, pout, lgs = {}, {}, {}
    files = [HERE / "data.js"] + sorted((HERE / "hist").glob("mlb-*.js"))
    for f in files:
        raw = f.read_text(); ds = json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))
        if ds.get("kind"):
            continue                                       # spring / postseason files are not season lines
        y = int(ds["meta"]["season"] if "meta" in ds else ds["season"])
        TL = talent_league(ds["players"], ds.get("refPA") or (ds.get("meta") or {}).get("refMinPA") or 300)
        if TL.get("woba") is not None: lgs[str(y)] = round(TL["woba"], 4)   # the season's talent league (its 300+ PA hitters' wOBA), what each season's talent is measured against
        for p in ds["players"]:
            r = lambda v, d=1: None if v is None or v != v else round(float(v), d)
            if p.get("type") == "P":
                pm = p.get("m") or {}
                pout.setdefault(str(p["id"]), {})[str(y)] = [r(pm.get(k), 2 if k in ("nera", "siera") else 1) for k in SBP_KEYS]
                continue
            if p.get("type") != "H":
                continue
            m, cx = p.get("m") or {}, p.get("ctx") or {}
            mx = cx.get("mix") or []
            fbs = sum(x or 0 for x in mx) if len(mx) >= 8 else 0      # every ball in the mix (MIX_COLS order: gb, pu, ld p/c/o, fb p/c/o, x)
            ti = _tw_inputs(p); tw = talent_of(ti, TL); xd = xbab_drivers(ti, TL); twp = talent_of(ti, TL, park=True); xs, xsp = xslg_of(ti, TL), xslg_of(ti, TL, park=True); xi, xip = xiso_of(ti, TL), xiso_of(ti, TL, park=True)
            gd = cx.get("gbdir"); gn = sum(gd) if gd else 0
            val = lambda k: (100 * mx[5] / fbs if fbs else None) if k == "pullfb" else tw if k == "txw" else twp if k == "txwpk" else xd if k == "xbabd" else xs if k == "xslg" else xsp if k == "xslgpk" else xi if k == "xiso" else xip if k == "xisopk" else (100 * gd[0] / gn if gn else None) if k == "gbp" else p.get("pa") if k == "pa" else m.get(k)
            out.setdefault(str(p["id"]), {})[str(y)] = [cx.get("BBE")] + [(int(val(k)) if val(k) is not None else None) if k == "pa" else r(val(k), 3 if k in ("mixw", "babip", "xbabip", "txw", "xbabd", "txwpk", "xslg", "xslgpk", "xiso", "xisopk") else 1) for k in SBX_KEYS]
    path = HERE / "hist" / "career-bb.js"
    path.write_text("window.DRAFT_CAREER_BB = " + json.dumps({"keys": SBX_KEYS, "p": out, "pkeys": SBP_KEYS, "pp": pout, "lg": lgs}, separators=(",", ":")) + ";\n")
    print(f"OK {len(out)} hitters' batted-ball / discipline seasons, {len(pout)} pitchers' -> {path.name} ({path.stat().st_size / 1e6:.1f} MB)", flush=True)
    shard()


# The Triple-A talent file (hist/aaa-tw.js) and the transaction log that kept rehab stints out of it went with the next-season
# projection (Sean, 25 Oct 2026: "get rid of the next season xwoba projection everywhere").


# How many of his club's games a pitcher spent on the active roster each season (Sean, 14 Oct 2026: "for the pitchers 162 game average make
# the calculations based on how many days they were on the active roster and pro rate those stats to if they were on it for 162 days"): every
# regular-season box score lists the whole active staff, the pitchers who pitched and the bullpen who didn't, so a pitcher's count is the games
# his name is on those lists; a full season on the roster is 162, so the season table's 162 Game Avg scales his career by 162 over the sum.
# Box scores list the full staff from 2009 (2008 and earlier carry ~10 names a side), so a season whose median team-game lists under 11
# pitchers is left out (None, and the app counts that season as a full one). One slim box-score request a game, threaded; a finished season is
# cached in .cache/sabr/act-<y>.json as {pid: games}, and this season keeps its per-game lists in act-<y>-games.json so a daily run fetches only
# the new games. None when the API can't be had.
ACT_FROM = 2009
def active_season(y, fresh):
    f, fg = SABR / f"act-{y}.json", SABR / f"act-{y}-games.json"
    if f.exists() and not fresh:
        try:
            d = json.loads(f.read_text()); return d.get("p") if d.get("ok") else None
        except ValueError:
            pass
    try:
        js = requests.get("https://statsapi.mlb.com/api/v1/schedule", headers=UA, timeout=120,
                          params={"sportId": 1, "season": y, "gameType": "R", "fields": "dates,games,gamePk,status,abstractGameState,codedGameState"}).json()
    except Exception as e:
        print(f"  schedule {y} unavailable:", e, flush=True); return None
    pks = sorted({g["gamePk"] for d in js.get("dates", []) for g in d.get("games", [])
                  if (g.get("status") or {}).get("abstractGameState") == "Final" and (g.get("status") or {}).get("codedGameState") not in ("D", "C")})
    games = {}
    if fg.exists():
        try:
            games = json.loads(fg.read_text())
        except ValueError:
            games = {}
    def box(pk):
        for attempt in range(3):
            try:
                t = requests.get(f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore", headers=UA, timeout=30,
                                 params={"fields": "teams,away,home,pitchers,bullpen"}).json()["teams"]
                return [sorted(set(t[s].get("pitchers", []) + t[s].get("bullpen", []))) for s in ("away", "home")]
            except Exception:
                time.sleep(2 + 2 * attempt)
        return None
    todo = [pk for pk in pks if str(pk) not in games]
    with ThreadPoolExecutor(max_workers=24) as ex:
        for pk, b in zip(todo, ex.map(box, todo)):
            if b is not None:
                games[str(pk)] = b
    SABR.mkdir(parents=True, exist_ok=True)
    if fresh:
        fg.write_text(json.dumps(games, separators=(",", ":")))
    sides = sorted(len(s) for b in games.values() for s in b)
    ok = bool(sides) and sides[len(sides) // 2] >= 11 and len(games) >= 0.97 * len(pks)
    out = {}
    for b in games.values():
        for s in b:
            for pid in s:
                out[str(pid)] = out.get(str(pid), 0) + 1
    if not fresh and len(games) >= 0.97 * len(pks):
        f.write_text(json.dumps({"ok": ok, "p": out}, separators=(",", ":")))
    print(f"  active rosters {y}: {len(games)} of {len(pks)} games, median staff {sides[len(sides) // 2] if sides else 0}{'' if ok else ' (left out)'}", flush=True)
    return out if ok else None


def main():
    season_bb()
    idx = load_js(HERE / "hist" / "index.js", "window.DRAFT_INDEX = ")
    ids = [e["id"] for e in idx["players"]]
    teams = {t["id"]: t["abbreviation"] for y in range(2000, 2027)
             for t in requests.get(f"https://statsapi.mlb.com/api/v1/teams?sportId=1&season={y}", headers=UA, timeout=60).json()["teams"]}
    # our advanced numbers per player-season
    ours = {}
    # each dataset's directional xwOBA scale, as the site's dirInfo() takes it (the season's PA-weighted wOBA over its PA-weighted raw
    # model value, 20+ hitters, the model actually on): the card's bars show xwoba_dir × this, so the season table does too (Sean,
    # 9 Oct 2026: Bellinger 2019 read .431 in the table against .442 on the bars)
    xsc = {}
    def dir_scale(players):
        w = d = 0.0; n = same = 0
        for q in players:
            mq = q.get("m") or {}; pa = q.get("pa") or 0
            if q.get("type") != "H" or not pa or mq.get("woba") is None or mq.get("xwoba_dir") is None: continue
            w += mq["woba"] * pa; d += mq["xwoba_dir"] * pa; n += 1
            if abs(mq["xwoba_dir"] - mq["woba"]) < 0.0006: same += 1
        return w / d if n >= 20 and d > 0 and same < 0.9 * n else None
    def xw_of(mq, key):
        x = mq.get("xwoba_dir")
        if x is None: return mq.get("xwoba")
        sc = xsc.get(key)
        return round(x * sc, 3) if sc else x
    cur = load_js(HERE / "data.js", "window.DRAFT_DATA = ")
    xsc[("mlb", cur["meta"]["season"])] = dir_scale(cur["players"])
    for p in cur["players"]:
        ours[(p["id"], cur["meta"]["season"], p["type"])] = p["m"]
    for f in sorted((HERE / "hist").glob("mlb-*.js")):
        raw = f.read_text(); ds = json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))
        if ds.get("kind"):
            continue                                       # spring / postseason files are not season lines
        xsc[("mlb", ds["season"])] = dir_scale(ds["players"])
        for p in ds["players"]:
            ours[(p["id"], ds["season"], p["type"])] = p["m"]
    # minor-league level seasons we've built: keyed by the API's level names
    LVL = {"aaa": ["AAA"], "aa": ["AA"], "ap": ["A+", "A(Adv)"], "a": ["A", "A(Full)"]}
    ours_m = {}
    for lv, names in LVL.items():
        for f in sorted((HERE / "hist").glob(f"{lv}-*.js")):
            if not f.stem[len(lv) + 1:].isdigit():           # a season file only (14 Oct 2026)
                continue
            raw = f.read_text(); ds = json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))
            for nm in names:
                xsc[(nm, ds["season"])] = dir_scale(ds["players"])
            for p in ds["players"]:
                for nm in names:
                    ours_m[(p["id"], ds["season"], p["type"], nm)] = p["m"]

    out = {}
    now = int(cur["meta"]["season"])
    ldhr = {}                                              # season -> {player id: line-drive / ground-ball homers}, fetched on first use
    def ld_for(y):
        if y not in ldhr:
            ldhr[y] = ld_hr(y, fresh=y >= now) or {}
        return ldhr[y]
    def fb_for(pid, y, club, fb_by):
        """a traded season's club: MLB's club fly balls plus its share (by fly balls) of his non-fly homers"""
        m, tot, n = fb_by.get((y, club)), fb_by.get((y, "TOT")), ld_for(y).get(str(pid), 0)
        return m if m is None or not tot or not n else round(m + n * m / tot)
    def fb_season(pid, y, team, fb_by):
        """his season's fly balls + popups (MLB's, Statcast's calls) plus his line-drive / ground-ball homers"""
        m = fb_by.get((y, team))
        return None if m is None else m + ld_for(y).get(str(pid), 0)
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
    bwp = bref_war(fresh=True, kind="pitch")
    if bwp is None:                                        # as with bWAR above: the last build's pitching bWAR carries over
        bwp = {}
        try:
            prev = load_js(HERE / "hist" / "career.js", "window.DRAFT_CAREER = ")
            ip, ipt = 2 + len(PIT) + len(PIT_X) + 2, 2 + len(PIT) + len(PIT_X)   # a pitcher's row: ours, a blank, then [fWAR, bWAR]; a club row: [fWAR, bWAR]
            for pid, rec in prev.items():
                for key, i, club in (("P", ip, False), ("PT", ipt, True), ("H", 24, False), ("HT", 22, True)):
                    for r in rec.get(key, []):
                        if len(r) > i and isinstance(r[i], list) and r[i][1] is not None:
                            bwp.setdefault(f"{pid}|{r[0]}", {})[r[1] if club else ""] = r[i][1]
        except Exception as e:
            print("  no earlier career.js to carry pitching bWAR from:", e, flush=True)
    sabr_p = {}
    def sabr_p_for(y):
        if y not in sabr_p:
            sabr_p[y] = sabr_pitch_season(y, fresh=y >= now)
        return sabr_p[y]
    def pw_for(pid, y, club=""):                           # [FanGraphs, Baseball-Reference] pitching WAR, or None if he didn't pitch
        b = bwp.get(f"{pid}|{y}", {}).get(club)
        f = sabr_p_for(y).get(str(pid)) if not club else None
        return None if b is None and f is None else [f, b]
    act = {}
    def act_for(pid, y):                                   # team games on the active roster that season, or None (before 2009 / unavailable)
        if y < ACT_FROM: return None
        if y not in act:
            act[y] = active_season(y, fresh=y >= now) or {}
        return act[y].get(str(pid))
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
                                ht_ext[(str(p["id"]), r[0], r[1])] = [bw.get(f"{p['id']}|{r[0]}", {}).get(r[1]), None, fb_for(p["id"], r[0], r[1], fb_by)]
                    rows = [by[k] for k in sorted(by)]
                    for r in rows:
                        m = ours.get((p["id"], r[0], t))
                        r.append(None if not m else ([m.get("woba"), xw_of(m, ("mlb", r[0]))] if t == "H"   # the site's xwOBA is the directional model (8 Oct 2026)
                                                     else [m.get("fip"), m.get("siera"), m.get("k"), m.get("bb"), m.get("kbb"), m.get("whf"), m.get("strk"),
                                                           m.get("gb"), m.get("pu")]))   # appended: the card's simple season table shows GB% / Popup%
                        if t == "H":
                            r.append(pos_by.get(r[0], ""))     # then where he played — the app reads a row by fixed index (8 Oct 2026)
                            r.append(sabr_for(r[0]).get(str(p["id"])))   # then FanGraphs' wRC+ / BsR / Off / Def / WAR / wOBA (or null)
                            r.append([bw.get(f"{p['id']}|{r[0]}", {}).get(""), (m or {}).get("spd"), fb_season(p["id"], r[0], r[1], fb_by)])   # then bWAR, sprint speed, fly balls
                            r.append(pw_for(p["id"], r[0]))   # then his pitching WAR [FanGraphs, B-Ref] that season, or null
                        else:
                            r.append("")                       # a pitcher's row: a blank where a hitter's positions sit, so the index matches,
                            r.append(pw_for(p["id"], r[0]))    # then his pitching WAR [FanGraphs, B-Ref] (Sean, 14 Oct 2026: fWAR / bWAR on the pitchers' table)
                            r.append(act_for(p["id"], r[0]))   # then the team games he was on the active roster, for the 162 Game Avg (14 Oct 2026)
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
    # a pitcher's traded season: each club's pitching WAR [FanGraphs, B-Ref], appended to the PT rows after ER / BF (14 Oct 2026)
    trp = sorted({(pid, r[0]) for pid, rec in out.items() for r in rec.get("PT", [])})
    with ThreadPoolExecutor(max_workers=8) as ex:
        for (pid, y), clubs in zip(trp, ex.map(lambda a: sabr_pitch_clubs(a[0], a[1], teams, fresh=a[1] >= now), trp)):
            for r in out[pid]["PT"]:
                if r[0] == y:
                    b = bwp.get(f"{pid}|{y}", {}).get(r[1])
                    f = clubs.get(r[1])
                    r.append(None if b is None and f is None else [f, b])
    print(f"  FanGraphs numbers: {len(sabr)} seasons, {len(tr)} traded seasons split by club, {len(trp)} traded pitching seasons", flush=True)
    # minor-league lines: threaded, cached; players on this season's board are refreshed every run
    current = {p["id"] for p in cur["players"]}
    todo = [(pid, pid in current) for pid in ids]
    done = 0
    milb = {}
    def with_adv(pid, t, rows, pos):
        out_rows = []
        for r in rows:
            m = ours_m.get((pid, r[0], t, r[1]))
            adv = None if not m else ([m.get("woba"), xw_of(m, (r[1], r[0])), m.get("whf")] if t == "H" else [m.get("fip"), m.get("siera"), m.get("whf"), m.get("strk"),
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
    shard()


def shard():
    """The three whole files cut into per-id buckets (hist/c/, hist/m/; tools/shard_career.py) — what a player's page reads since 28 Oct 2026.
    Non-fatal: the whole files are written either way, and the page falls back to them."""
    try:
        import sys
        if str(HERE / "tools") not in sys.path:
            sys.path.insert(0, str(HERE / "tools"))
        import shard_career
        shard_career.shard(str(HERE))
    except Exception as e:                                 # noqa: BLE001
        print(f"!! shard_career: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    import sys
    season_bb() if sys.argv[1:] == ["bb"] else main()
