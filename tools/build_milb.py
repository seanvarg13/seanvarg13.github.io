"""Build hist/aaa-YYYY.js (+ hist/days-aaa-YYYY.js) for Triple-A seasons from Baseball Savant's minor-league
Statcast search, then refresh hist/index.js so Explore / Compare / player cards can pick the level and year.

Usage:  python3 build_milb.py [2024 2025 ...]        (default: every season in SEASONS not built yet)

Same metrics and constants as the MLB seasons (build_data.py); no bat speed (no bat tracking in the minors) and
no directional xwOBA (that model needs MLB sprint speeds) — xwOBA is Savant's EV + launch-angle number.
"""
import sys, json, time, io, datetime as dt
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
import requests
import build_data as bd
import build_history as bh

HERE = Path(__file__).resolve().parent
OUT = HERE / "hist"
CACHE = HERE / ".cache" / "milb"
# key prefix -> (MLB sportId, short label, long name, source). Triple-A has Statcast (Savant's minors search);
# lower levels only have MLB's Gameday play-by-play (calls, batted-ball type + location; no tracking except FSL parks)
LEVELS = {"aaa": (11, "AAA", "Triple-A", "savant"), "aa": (12, "AA", "Double-A", "feed"),
          "ap": (13, "A+", "High-A", "feed"), "a": (14, "A", "Single-A", "feed")}
SEASONS = {2021: ("05-04", "09-30"), 2022: ("04-05", "09-30"), 2023: ("03-31", "09-26"), 2024: ("03-29", "09-24"),
           2025: ("03-28", "09-23"), 2026: ("03-27", "09-22")}
SPORT, LEVEL, LEVEL_NAME = 11, "AAA", "Triple-A"        # set per build by build_season()
API = "https://statsapi.mlb.com/api/v1"
FEEDS = CACHE / "feeds"


def savant_day(day: str) -> pd.DataFrame:
    """One day of Triple-A pitches from Savant (cached as CSV under .cache/milb)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{LEVEL.lower()}-{day}.csv"
    if f.exists():
        return pd.read_csv(f, low_memory=False) if f.stat().st_size > 5 else pd.DataFrame()
    url = ("https://baseballsavant.mlb.com/statcast-search-minors/csv?all=true&hfGT=R%7C&player_type=batter"
           f"&hfSea={day[:4]}%7C&game_date_gt={day}&game_date_lt={day}&group_by=name&min_pitches=0&min_results=0"
           "&min_pas=0&sort_col=pitches&player_event_sort=api_p_release_speed&sort_order=desc&type=details&minors=true")
    for attempt in range(4):
        try:
            r = requests.get(url, headers=bd.UA, timeout=180)
            txt = r.text.lstrip("\ufeff")
            ok = txt.startswith('"pitch_type"') or txt.startswith("pitch_type")
            if r.status_code == 200 and (ok or txt.strip() == ""):
                f.write_text(txt if ok else "")
                return pd.read_csv(io.StringIO(txt), low_memory=False) if ok and txt.count("\n") > 1 else pd.DataFrame()
            bd.log(f"    {day}: http {r.status_code}, retrying"); time.sleep(3 * (attempt + 1))
        except Exception as e:
            bd.log(f"    {day}: {type(e).__name__}, retrying"); time.sleep(3 * (attempt + 1))
    bd.log(f"    {day}: giving up"); return pd.DataFrame()


def load_milb(start: str, end: str) -> pd.DataFrame:
    days = [str(x.date()) for x in pd.date_range(start, end)]
    out = []
    with ThreadPoolExecutor(max_workers=4) as ex:          # Savant takes ~20 s per day-file; a few in flight at once
        for n, d in enumerate(ex.map(savant_day, days), 1):
            if len(d):
                out.append(d[[c for c in bd.COLS if c in d.columns]])
            if n % 20 == 0 or n == len(days):
                bd.log(f"  savant {days[n - 1]} — {sum(len(x) for x in out):,} pitches so far")
    d = pd.concat(out, ignore_index=True)
    # Savant's minors search also carries the Statcast-equipped Florida State League parks: keep this level's games only
    year = start[:4]
    sched = requests.get(f"{API}/schedule?sportId={SPORT}&season={year}&gameType=R&startDate={year}-03-01&endDate={year}-10-15",
                         headers=bd.UA, timeout=120).json()
    pks = {g["gamePk"] for x in sched.get("dates", []) for g in x.get("games", [])}
    d = d[(d["game_type"] == "R") & d["game_pk"].isin(pks)].copy()
    d["game_date"] = pd.to_datetime(d["game_date"])
    for c in ["launch_speed", "launch_angle", "launch_speed_angle", "zone", "hc_x", "hc_y", "woba_value", "woba_denom",
              "estimated_woba_using_speedangle", "bat_speed", "release_speed", "release_extension", "outs_when_up"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    bd.log(f"  {len(d):,} pitches, {d.game_date.min().date()} .. {d.game_date.max().date()}, {d.game_pk.nunique()} games")
    return d


# Gameday descriptions -> Statcast description strings
DESC = {"Ball": "ball", "Ball In Dirt": "blocked_ball", "Intent Ball": "intent_ball", "Automatic Ball": "automatic_ball",
        "Pitchout": "pitchout", "Hit By Pitch": "hit_by_pitch", "Called Strike": "called_strike", "Automatic Strike": "automatic_strike",
        "Swinging Strike": "swinging_strike", "Swinging Strike (Blocked)": "swinging_strike_blocked", "Foul": "foul",
        "Foul Tip": "foul_tip", "Foul Bunt": "foul_bunt", "Missed Bunt": "missed_bunt", "Foul Pitchout": "foul_pitchout",
        "Swinging Pitchout": "swinging_pitchout", "Bunt Foul Tip": "bunt_foul_tip",
        "In play, out(s)": "hit_into_play", "In play, no out": "hit_into_play", "In play, run(s)": "hit_into_play"}
WOBA_W = {"walk": 0.69, "hit_by_pitch": 0.72, "single": 0.88, "double": 1.25, "triple": 1.58, "home_run": 2.03}
_XW = None


def xwoba_lookup():
    """Savant's EV x launch-angle xwOBA as a grid, learned from the cached Triple-A pitch files (it is the same
    function of EV/LA at any level); used for the few lower-level parks that report exit velocity."""
    global _XW
    if _XW is not None:
        return _XW
    f = CACHE / "xwoba_grid.npy"
    if f.exists():
        _XW = np.load(f); return _XW
    frames = []
    for c in sorted(CACHE.glob("aaa-*.csv")):
        if c.stat().st_size < 100:
            continue
        frames.append(pd.read_csv(c, usecols=["launch_speed", "launch_angle", "estimated_woba_using_speedangle"], low_memory=False).dropna())
    d = pd.concat(frames, ignore_index=True)
    ev = d.launch_speed.round().clip(20, 125).astype(int); la = d.launch_angle.round().clip(-90, 90).astype(int)
    grid = np.full((126, 181), np.nan)
    g = d.groupby([ev, la])["estimated_woba_using_speedangle"].mean()
    for (e, a), v in g.items():
        grid[e, a + 90] = v
    filled = grid.copy()                                  # empty cells take the nearest filled neighbours
    for e in range(126):
        for a in range(181):
            if np.isnan(filled[e, a]):
                for w in (1, 2, 3, 5, 8):
                    blk = grid[max(0, e - w):e + w + 1, max(0, a - w):a + w + 1]
                    if np.isfinite(blk).any():
                        filled[e, a] = np.nanmean(blk); break
    _XW = np.nan_to_num(filled, nan=0.0); np.save(f, _XW)
    bd.log(f"  xwOBA grid from {len(d):,} Triple-A batted balls")
    return _XW


def barrel(ev, la):
    if pd.isna(ev) or pd.isna(la) or ev < 98:
        return False
    lo = max(8.0, 26.0 - (ev - 98.0)); hi = min(50.0, 30.0 + (ev - 98.0) * 1.1)
    return lo <= la <= hi


def feed_game(pk: int, game_date: str) -> pd.DataFrame:
    """One minor-league game's pitches from the Gameday play-by-play, as Statcast-shaped rows (cached)."""
    FEEDS.mkdir(parents=True, exist_ok=True)
    f = FEEDS / f"{pk}.csv.gz"
    if f.exists():
        try:
            if f.stat().st_size <= 60:
                return pd.DataFrame()
            d = pd.read_csv(f, low_memory=False)
            if "des" not in d.columns:                    # files cached before the play text was kept: no bunt flag (only EV means care)
                d["des"] = ""
            return d
        except Exception:                                 # a corrupt cached file: fetch it again
            f.unlink(missing_ok=True)
    js = {}
    for attempt in range(4):
        try:
            r = requests.get(f"{API}/game/{pk}/playByPlay", headers=bd.UA, timeout=60)
            if r.status_code == 200:
                js = r.json(); break
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    rows, outs, prev_half = [], 0, None
    for play in js.get("allPlays", []):
        about, res, mu = play.get("about", {}), play.get("result", {}), play.get("matchup", {})
        half = (about.get("inning"), about.get("halfInning"))
        if half != prev_half:
            outs, prev_half = 0, half
        ev_type = res.get("eventType")
        pitches = [e for e in play.get("playEvents", []) if e.get("isPitch")]
        if not pitches and ev_type == "intent_walk":            # no-pitch intentional walk: one stand-in row
            pitches = [{"details": {"description": "Intent Ball", "isBall": True}}]
        for i, e in enumerate(pitches):
            det = e.get("details", {}); hd = e.get("hitData") or {}; pdt = e.get("pitchData") or {}
            desc = DESC.get(det.get("description", ""))
            if desc is None:
                desc = "hit_into_play" if det.get("isInPlay") else ("ball" if det.get("isBall") else "called_strike")
            typ = "X" if det.get("isInPlay") else ("B" if det.get("isBall") else "S")
            ev = ev_type if i == len(pitches) - 1 else None
            ls, la = hd.get("launchSpeed"), hd.get("launchAngle")
            co = hd.get("coordinates") or {}
            rows.append({
                "game_date": game_date, "game_type": "R", "game_pk": pk,
                "batter": (mu.get("batter") or {}).get("id"), "pitcher": (mu.get("pitcher") or {}).get("id"),
                "stand": (mu.get("batSide") or {}).get("code"), "p_throws": (mu.get("pitchHand") or {}).get("code"),
                "description": desc, "zone": pdt.get("zone"), "type": typ, "events": ev,
                "launch_speed": ls, "launch_angle": la, "launch_speed_angle": 6 if (typ == "X" and barrel(ls, la)) else None,
                "bb_type": hd.get("trajectory") if typ == "X" else None,
                "hc_x": co.get("coordX"), "hc_y": co.get("coordY"),
                "inning": about.get("inning"), "inning_topbot": "Top" if about.get("halfInning") == "top" else "Bot",
                "at_bat_number": about.get("atBatIndex", 0) + 1, "outs_when_up": outs,
                "woba_value": (WOBA_W.get(ev, 0.0) if ev else None), "woba_denom": (1 if ev else None),
                "estimated_woba_using_speedangle": None, "bat_speed": None,
                "pitch_type": (det.get("type") or {}).get("code"), "release_speed": pdt.get("startSpeed"),
                "release_extension": pdt.get("extension"), "des": res.get("description", "") if ev else "",
            })
        outs = (play.get("count") or {}).get("outs", outs)
    d = pd.DataFrame(rows, columns=bd.COLS)
    if len(d):
        ev = pd.to_numeric(d["launch_speed"], errors="coerce"); la = pd.to_numeric(d["launch_angle"], errors="coerce")
        ok = (d["type"] == "X") & ev.notna() & la.notna()
        if ok.any():
            grid = xwoba_lookup()
            d.loc[ok, "estimated_woba_using_speedangle"] = grid[ev[ok].round().clip(20, 125).astype(int).values,
                                                                 (la[ok].round().clip(-90, 90).astype(int) + 90).values]
    d.to_csv(f, index=False, compression="gzip")
    return d


def load_feed(year: int, start: str, end: str) -> pd.DataFrame:
    sched = requests.get(f"{API}/schedule?sportId={SPORT}&season={year}&gameType=R&startDate={start}&endDate={end}",
                         headers=bd.UA, timeout=120).json()
    games = sorted({(g["gamePk"], x["date"]) for x in sched.get("dates", []) for g in x.get("games", [])
                    if (g.get("status") or {}).get("codedGameState") in ("F", "O") and g.get("gameType") == "R"})
    bd.log(f"  {len(games)} {LEVEL_NAME} games on the schedule")
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for n, d in enumerate(ex.map(lambda g: feed_game(*g), games), 1):
            if len(d):
                out.append(d)
            if n % 250 == 0 or n == len(games):
                bd.log(f"  gameday {n}/{len(games)} — {sum(len(x) for x in out):,} pitches")
    d = pd.concat(out, ignore_index=True)
    d["game_date"] = pd.to_datetime(d["game_date"])
    for c in ["launch_speed", "launch_angle", "launch_speed_angle", "zone", "hc_x", "hc_y", "woba_value", "woba_denom",
              "estimated_woba_using_speedangle", "bat_speed", "release_speed", "release_extension", "outs_when_up"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    bip = d["type"] == "X"
    tracked = float(d.loc[bip, "launch_speed"].notna().mean()) if bip.any() else 0.0
    bd.log(f"  {len(d):,} pitches, {d.game_date.min().date()} .. {d.game_date.max().date()}, {d.game_pk.nunique()} games, EV on {100 * tracked:.0f}% of balls in play")
    return d


def milb_people(ids, year: int) -> dict:
    """The build_data.mlb_people record, but from the Triple-A season: club, AB / IP / ERA / ER, positions, ER by game."""
    ids = [int(i) for i in ids]
    teams = requests.get(f"{API}/teams?sportId={SPORT}&season={year}", headers=bd.UA, timeout=60).json()["teams"]
    abbr = {t["id"]: t["abbreviation"] for t in teams}
    basics = {}
    for i in range(0, len(ids), 100):
        js = requests.get(f"{API}/people?personIds={','.join(map(str, ids[i:i + 100]))}", headers=bd.UA, timeout=60).json()
        for p in js.get("people", []):
            basics[p["id"]] = p

    def get(url):
        for attempt in range(3):
            try:
                return requests.get(url, headers=bd.UA, timeout=60).json()
            except Exception:
                time.sleep(2)
        return {}

    def one(pid):
        js = get(f"{API}/people/{pid}/stats?stats=season&group=hitting,pitching,fielding&season={year}&sportId={SPORT}")
        pos_games, ab, ip, era, er, season_team, pitched = {}, None, None, None, None, None, False
        for s in js.get("stats", []):
            grp = s["group"]["displayName"]; splits = s.get("splits", [])
            if grp in ("hitting", "pitching"):
                for x in splits:
                    if "team" in x:
                        season_team = abbr.get(x["team"].get("id"), season_team)
                tot = [x for x in splits if "team" not in x] or splits[:1]
                if tot:
                    st = tot[0]["stat"]
                    if grp == "hitting":
                        ab = st.get("atBats")
                    else:
                        pitched = True
                        ip = bd.innings_to_float(st.get("inningsPitched"))
                        era = float(st["era"]) if st.get("era") not in (None, "-.--") else None
                        er = st.get("earnedRuns")
            else:
                for sp in splits:
                    code = sp.get("position", {}).get("abbreviation")
                    if code in ("LF", "CF", "RF"):
                        code = "OF"
                    if not code or code in ("P", "TWP"):
                        continue
                    pos_games[code] = pos_games.get(code, 0) + int(sp["stat"].get("games", 0))
        games = []
        if pitched:
            gl = get(f"{API}/people/{pid}/stats?stats=gameLog&group=pitching&season={year}&sportId={SPORT}")
            for s in gl.get("stats", []):
                games = [(x["date"], 1 if x.get("isHome") else 0, int(x["stat"].get("earnedRuns", 0)))
                         for x in s.get("splits", []) if x.get("gameType", "R") == "R"]
        p = basics.get(pid, {})
        prim = p.get("primaryPosition", {}).get("abbreviation", "")
        if prim in ("LF", "CF", "RF"):
            prim = "OF"
        if prim in ("TWP", "P", ""):
            prim = "DH"
        return pid, {"name": p.get("fullName", str(pid)), "team": season_team or "FA", "primary": prim, "pos": pos_games,
                     "age": bh.season_age(p.get("birthDate"), year), "ab": ab, "ip": ip, "era": era, "er": er,
                     "games": games, "seasonTeam": season_team, "birth": p.get("birthDate")}

    people = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for n, (pid, info) in enumerate(ex.map(one, ids), 1):
            people[pid] = info
            if n % 200 == 0:
                bd.log(f"  mlb api ({LEVEL_NAME}): {n}/{len(ids)}")
    return people


def build_season(year: int, level: str = "aaa"):
    global SPORT, LEVEL, LEVEL_NAME
    SPORT, LEVEL, LEVEL_NAME, source = LEVELS[level]
    start, end = f"{year}-{SEASONS[year][0]}", f"{year}-{SEASONS[year][1]}"
    bd.SEASON, bd.SEASON_START = year, start
    bd.directional_xwoba = lambda p, tracked, num, den: num.astype(float).copy()   # no sprint speeds in the minors
    bd.log(f"=== {year} {LEVEL_NAME} ===")
    d = bd.pitch_flags(load_milb(start, end) if source == "savant" else load_feed(year, start, end))
    tracked = float(d.loc[d["bip"], "launch_speed"].notna().mean()) if d["bip"].any() else 0.0
    hit, pit = bd.hitter_metrics(d), bd.pitcher_metrics(d)
    bd.log(f"  {len(hit)} batters, {len(pit)} pitchers")
    d2 = d.copy(); d2["game_date"] = "S"
    rows_h, rows_p = bd.daily(d2, {"S": 0})
    days_list = sorted(d["game_date"].astype(str).str[:10].unique())
    days = {day: i for i, day in enumerate(days_list)}
    daily_h, daily_p = bd.daily(d, days)
    g = d[d["bbt"]].groupby("batter")
    sav = pd.DataFrame({"Air_pct": 100 * g["air"].mean(), "PullAir_pct": 100 * g["pullair"].mean()})
    floor = getattr(bd, "CONST_MIN_BF", 20)                  # the minors keep a real floor: MLB ships everyone, not them
    hit_ids = hit[hit.PA >= max(bd.MIN_PA_HITTER, floor)].index
    pit_ids = pit[pit.BF >= max(bd.MIN_BF_PITCHER, floor)].index
    people = milb_people(sorted(set(hit_ids) | set(pit_ids)), year)
    empty = pd.Series(dtype=float)
    hitters = bd.build_hitters(hit, sav, people, rows_h, empty, empty)
    if tracked < 0.05:                                      # nothing tracked: an "xwOBA" would just be K/BB outcomes
        for h in hitters:
            h["m"]["xwoba"] = None
    consts = bd.league_constants(pit[pit.BF >= floor], people)
    pitchers = bd.build_pitchers(pit, people, rows_p, consts)
    for q in pitchers:
        for r in rows_p.get(q["id"], []):
            r[bd.PITCHER_DAY.index("gs")] = q["ctx"]["GS"]
    n_games = d["game_pk"].nunique()
    ref_pa = max(50, int(round(bd.REF_MIN_PA * n_games / 2430 / 10) * 10))
    key = f"{level}-{year}"
    ds = {
        "key": key, "label": f"{year} {LEVEL_NAME}", "season": year, "level": LEVEL, "levelName": LEVEL_NAME,
        "hist": True, "airNoPU": True, "daysFile": f"days-{key}.js",
        "tracked": round(tracked, 3), "noStatcast": tracked < 0.5,        # no EV / zone data: hitters rank by wOBA, no xwOBA
        "games": int(n_games), "refPA": ref_pa, "consts": consts, "days": days_list,
        "through": str(d.game_date.max())[:10], "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "players": hitters + pitchers,
        "rows": {**{f"H{k}": v for k, v in rows_h.items() if any(h["id"] == k for h in hitters)},
                 **{f"P{k}": v for k, v in rows_p.items() if any(q["id"] == k for q in pitchers)}},
    }
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{key}.js"
    path.write_text(f'window.DRAFT_HIST = window.DRAFT_HIST || {{}};\nwindow.DRAFT_HIST["{key}"] = '
                    + json.dumps(ds, separators=(",", ":")) + ";\n")
    hid = {h["id"] for h in hitters}; pid = {q["id"] for q in pitchers}
    daily = {**{f"H{k}": v for k, v in daily_h.items() if k in hid}, **{f"P{k}": v for k, v in daily_p.items() if k in pid}}
    # earned runs by game for the card's ERA inside a date range (same shape as days.js)
    for q in pitchers:
        er = [(days[g[0]], g[1], g[2]) for g in people[q["id"]]["games"] if g[0] in days]
        if er:
            daily[f"P{q['id']}:er"] = er
    dpath = OUT / f"days-{key}.js"
    dpath.write_text(f'window.DRAFT_HIST_DAYS = window.DRAFT_HIST_DAYS || {{}};\nwindow.DRAFT_HIST_DAYS["{key}"] = '
                     + json.dumps(daily, separators=(",", ":")) + ";\n")
    bd.log(f"OK {year} {LEVEL_NAME}: {len(hitters)} hitters, {len(pitchers)} pitchers, refPA {ref_pa}, EV on {100 * tracked:.0f}% of BIP -> {path.name} "
           f"({path.stat().st_size / 1e6:.1f} MB) + {dpath.name} ({dpath.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    # python3 build_milb.py [aaa|aa|ap|a ...] [2026 2025 ...]   — default: Triple-A, every season not built yet
    levels = [a for a in sys.argv[1:] if a in LEVELS] or ["aaa"]
    years = [int(a) for a in sys.argv[1:] if a.isdigit()]
    if "index" not in sys.argv:
        for level in levels:
            ys = years or [y for y in SEASONS if y >= (2022 if level == "aaa" else 2021) and not (OUT / f"{level}-{y}.js").exists()]
            for y in ys:
                try:
                    build_season(y, level)
                except Exception as e:
                    import traceback; traceback.print_exc()
                    bd.log(f"!! {level} {y} failed: {type(e).__name__}: {str(e)[:160]}")
    bh.build_index()
