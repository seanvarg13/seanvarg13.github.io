"""Build hist/mlb-YYYY.js for past MLB seasons (Explore page) plus hist/index.js.

Usage:  python3 build_history.py [2015 2016 ...]      (default: 2015-2025; skips seasons already built)
        python3 build_history.py spring 2026 2025     -> hist/mlb-YYYY-spring.js (+ days-YYYY-spring.js): spring training
        python3 build_history.py post 2025 2024       -> hist/mlb-YYYY-post.js   (+ days-YYYY-post.js):   postseason

Reuses build_data.py season by season: same metrics, same directional xwOBA model, same FIP / SIERA
constants (derived per season). Rows are per player x handedness x venue (no date dimension), so the
card's vs-LHP/RHP and home/away splits work for past seasons; date windows do not.
"""
import sys, json, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
import build_data as bd

HERE = Path(__file__).resolve().parent
OUT = HERE / "hist"
SEASONS = {   # regular-season bounds (Statcast game_type "R" is applied on top)
    2015: ("2015-04-05", "2015-10-05"), 2016: ("2016-04-03", "2016-10-03"), 2017: ("2017-04-02", "2017-10-02"),
    2018: ("2018-03-29", "2018-10-01"), 2019: ("2019-03-20", "2019-09-30"), 2020: ("2020-07-23", "2020-09-28"),
    2021: ("2021-04-01", "2021-10-04"), 2022: ("2022-04-07", "2022-10-06"), 2023: ("2023-03-30", "2023-10-02"),
    2024: ("2024-03-20", "2024-10-01"), 2025: ("2025-03-18", "2025-09-30"), 2026: ("2026-03-26", "2026-09-27"),
}
# the other game types around a season: spring training before opening day, the postseason after the last regular day
KINDS = {
    "reg":    {"types": {"R"}, "suffix": "", "label": "MLB", "floor": (20, 20)},
    "spring": {"types": {"S"}, "suffix": "-spring", "label": "MLB spring training", "floor": (10, 10)},
    "post":   {"types": {"F", "D", "L", "W"}, "suffix": "-post", "label": "MLB postseason", "floor": (5, 5)},
}


def kind_dates(year, kind):
    start, end = SEASONS[year]
    if kind == "spring":
        return f"{year}-02-15", str((dt.date.fromisoformat(start) - dt.timedelta(days=1)))
    if kind == "post":
        return str(dt.date.fromisoformat(end) + dt.timedelta(days=1)), f"{year}-11-10"
    return start, end


def season_age(birth, season):
    if not birth:
        return None
    b = dt.date.fromisoformat(birth)
    mid = dt.date(season, 7, 1)
    return mid.year - b.year - ((mid.month, mid.day) < (b.month, b.day))


def build_season(year: int, kind: str = "reg"):
    start, end = kind_dates(year, kind)
    K = KINDS[kind]
    bd.SEASON, bd.SEASON_START, bd._SPRINT = year, start, None
    bd.GAME_TYPES = set(K["types"])
    bd.API_GAME_TYPE = {"reg": "R", "spring": "S", "post": "P"}[kind]
    bd.MIN_PA_HITTER, bd.MIN_BF_PITCHER = K["floor"]
    bd.log(f"=== {year} {kind} ===")
    d = bd.pitch_flags(bd.load_statcast(end))
    if not len(d):
        bd.log(f"  no {kind} games for {year}"); return
    if set(K["types"]) == {"R"}:                     # Stuff / Pitching grades for a regular season, trained on it and the two before
        d = bd.add_stuff(d, bd.load_prior_seasons(year))
    hit, pit = bd.hitter_metrics(d), bd.pitcher_metrics(d)
    bd.log(f"  {len(hit)} batters, {len(pit)} pitchers")

    # one row per player x hand x venue: run the per-day packer with a single constant "day"
    d2 = d.copy(); d2["game_date"] = "S"
    rows_h, rows_p = bd.daily(d2, {"S": 0})
    # and real per-day rows (hand x venue x day) so the card's custom date range works for this season too
    days_list = sorted(d["game_date"].astype(str).str[:10].unique())
    days = {day: i for i, day in enumerate(days_list)}
    daily_h, daily_p = bd.daily(d, days)

    # Air% / Pull Air% from Statcast flags (Savant's leaderboard is only used for the current season)
    g = d[d["bbt"]].groupby("batter")
    sav = pd.DataFrame({"Air_pct": 100 * g["air"].mean(), "PullAir_pct": 100 * g["pullair"].mean()})

    hit_ids = hit[hit.PA >= bd.MIN_PA_HITTER].index
    pit_ids = pit[pit.BF >= bd.MIN_BF_PITCHER].index
    people = bd.mlb_people(sorted(set(hit_ids) | set(pit_ids)), game_logs=False)
    for pid, info in people.items():
        info["team"] = info.get("seasonTeam") or info["team"]
        info["age"] = season_age(info.get("birth"), year) or info["age"]

    empty = pd.Series(dtype=float)
    hitters = bd.build_hitters(hit, sav, people, rows_h, empty, empty)
    consts = bd.league_constants(pit[pit.BF >= bd.MIN_BF_PITCHER], people)
    pitchers = bd.build_pitchers(pit, people, rows_p, consts)
    # season GS on every pitcher row (rows are hand x venue splits; games are not split-able)
    for q in pitchers:
        for r in rows_p.get(q["id"], []):
            r[bd.PITCHER_DAY.index("gs")] = q["ctx"]["GS"]

    n_games = d["game_pk"].nunique()
    ref_pa = max(50 if kind == "reg" else 20, int(round(bd.REF_MIN_PA * n_games / 2430 / 10) * 10))   # 2430 = a full 162-game slate
    key = f"mlb-{year}{K['suffix']}"
    ds = {
        "key": key, "label": f"{year} {K['label']}", "season": year, "level": "MLB", "kind": kind if kind != "reg" else "", "hist": True, "airNoPU": True,
        "games": int(n_games), "refPA": ref_pa, "consts": consts, "days": days_list, "daysFile": f"days-{year}{K['suffix']}.js",
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
    dpath = OUT / f"days-{year}{K['suffix']}.js"
    dpath.write_text(f'window.DRAFT_HIST_DAYS = window.DRAFT_HIST_DAYS || {{}};\nwindow.DRAFT_HIST_DAYS["{key}"] = '
                     + json.dumps(daily, separators=(",", ":")) + ";\n")
    bd.log(f"OK {year} {kind}: {len(hitters)} hitters, {len(pitchers)} pitchers, refPA {ref_pa} -> {path.name} "
           f"({path.stat().st_size / 1e6:.1f} MB) + {dpath.name} ({dpath.stat().st_size / 1e6:.1f} MB)")


def build_index():
    """hist/index.js: every player across the current season and all built seasons, for the Explore search."""
    players = {}
    def add(pid, name, team, type_, key, season, sample, role):
        e = players.setdefault(pid, {"id": pid, "name": name, "s": []})
        e["s"].append([key, season, type_, role, sample, team])
    raw = (HERE / "data.js").read_text().strip()
    cur = json.loads(raw[raw.index("{"):-1])
    curkey = f"mlb-{cur['meta']['season']}"
    for p in cur["players"]:
        add(p["id"], p["name"], p["team"], p["type"], curkey, cur["meta"]["season"],
            p["pa"] if p["type"] == "H" else round(p["ip"], 1), p["primary"])
    files = sorted(OUT.glob("mlb-*.js")) + [f for lv in ("aaa", "aa", "ap", "a") for f in sorted(OUT.glob(f"{lv}-*.js"))]   # MLB, then each minor-league level
    for f in files:
        raw = f.read_text(); ds = json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))
        for p in ds["players"]:
            add(p["id"], p["name"], p["team"], p["type"], ds["key"], ds["season"],
                p["pa"] if p["type"] == "H" else round(p["ip"], 1), p["primary"])
    order = ["mlb", "aaa", "aa", "ap", "a"]
    lvl = lambda key: order.index(key.split("-")[0]) if key.split("-")[0] in order else 9
    kind = lambda key: {"post": 1, "spring": 2}.get(key.split("-")[2] if key.count("-") >= 2 else "", 0)
    for e in players.values():
        e["s"].sort(key=lambda x: (-x[1], x[2], lvl(x[0]), kind(x[0])))
    seasons = [f"mlb-{cur['meta']['season']}"] + sorted((f.stem for f in OUT.glob("mlb-*.js")), key=lambda k: (-int(k.split("-")[1]), kind(k)))
    for lv in ("aaa", "aa", "ap", "a"):
        seasons += sorted((f.stem for f in OUT.glob(f"{lv}-*.js")), reverse=True)
    idx = {"seasons": list(dict.fromkeys(seasons)), "players": sorted(players.values(), key=lambda e: e["name"])}
    (OUT / "index.js").write_text("window.DRAFT_INDEX = " + json.dumps(idx, separators=(",", ":")) + ";\n")
    bd.log(f"index: {len(idx['players'])} players, seasons {idx['seasons']}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "index"]
    kind = next((a for a in args if a in KINDS), "reg"); args = [a for a in args if a not in KINDS]
    years = [] if "index" in sys.argv else ([int(a) for a in args] or [y for y in SEASONS if y < 2026 and not (OUT / f"mlb-{y}.js").exists()])
    for y in years:
        try:
            build_season(y, kind)
        except Exception as e:                       # keep going; the index covers whatever was built
            bd.log(f"!! {y} failed: {type(e).__name__}: {str(e)[:120]}")
    build_index()
