"""Build hist/career.js: season-by-season traditional stats + career totals for every player in the search
index (MLB Stats API yearByYear + career), with our wOBA / xwOBA (hitters) and FIP / SIERA (pitchers) attached
where a season was built.  Usage: python3 build_career.py"""
import json, time
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


def minors(pid, fresh):
    """Minor-league year-by-year lines for one player (every level, plus the API's combined 'Minors' line for a
    season spent at several). Cached; refreshed for players active this season."""
    f = CACHE / f"{pid}.json"
    if f.exists() and not fresh:
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=yearByYear&group=hitting,pitching&leagueListId=milb_all"
    out = {"H": [], "P": []}
    for attempt in range(3):
        try:
            js = requests.get(url, headers=UA, timeout=60).json(); break
        except Exception:
            time.sleep(2); js = {}
    for s in js.get("stats", []):
        grp = s["group"]["displayName"]; t = "H" if grp == "hitting" else "P"
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
    for i in range(0, len(ids), 80):
        chunk = ids[i:i + 80]
        url = ("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, chunk)) +
               "&hydrate=stats(group=[hitting,pitching],type=[yearByYear,career])")
        for attempt in range(3):
            try:
                js = requests.get(url, headers=UA, timeout=90).json(); break
            except Exception as e:
                print("  retry", e); time.sleep(3)
        for p in js.get("people", []):
            rec = {}
            for s in p.get("stats", []):
                grp, typ = s["group"]["displayName"], s["type"]["displayName"]
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
                    rows = [by[k] for k in sorted(by)]
                    for r in rows:
                        m = ours.get((p["id"], r[0], t))
                        r.append(None if not m else ([m.get("woba"), m.get("xwoba")] if t == "H"
                                                     else [m.get("fip"), m.get("siera"), m.get("k"), m.get("bb"), m.get("kbb"), m.get("whf"), m.get("strk"),
                                                           m.get("gb"), m.get("pu")]))   # appended: the card's simple season table shows GB% / Popup%
                    rec[t] = rows
            if rec:
                out[str(p["id"])] = rec
        print(f"  {min(i + 80, len(ids))}/{len(ids)}", flush=True)
    # minor-league lines: threaded, cached; players on this season's board are refreshed every run
    current = {p["id"] for p in cur["players"]}
    todo = [(pid, pid in current) for pid in ids]
    done = 0
    milb = {}
    def with_adv(pid, t, rows):
        out_rows = []
        for r in rows:
            m = ours_m.get((pid, r[0], t, r[1]))
            adv = None if not m else ([m.get("woba"), m.get("xwoba"), m.get("whf")] if t == "H" else [m.get("fip"), m.get("siera"), m.get("whf"), m.get("strk")])
            out_rows.append(list(r) + [adv])
        return out_rows
    with ThreadPoolExecutor(max_workers=8) as ex:
        for pid, res in zip([t[0] for t in todo], ex.map(lambda t: minors(*t), todo)):
            rec = {}
            if res.get("H"): rec["H"] = with_adv(pid, "H", res["H"])
            if res.get("P"): rec["P"] = with_adv(pid, "P", res["P"])
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
