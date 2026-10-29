#!/usr/bin/env python3
"""hist/lineups.js: where each hitter bats and how much he plays, from every box score of the season (Sean, 28 Oct 2026, item 7 of the
review's picks: "lineup slot & PA volume").

Per hitter: games on the active roster (a start, a substitute appearance or a day on the bench — the box score lists all three), starts,
starts by lineup slot, plate appearances (all of them, and those in the games he started), games played (a start or a substitute appearance —
the card's PA per game is his PA over these), starts and roster games against left- and right-handed starting pitchers, and his slot in each of his team's last 15
games (0 = on the roster but didn't start, -1 = not on the roster that day).

    window.DRAFT_LINEUPS = {"season": 2026, "through": "2026-09-27", "g": {"<team id>": games played},
                            "p": {"<MLB id>": {"ar": roster games, "gs": starts, "pa": PA, "sl": [starts in slots 1-9],
                                               "vl": [starts, roster games] vs LHP, "vr": [...] vs RHP, "last": [15 slots], "tm": <team id>,
                                               "pas": PA in the games he started, "gp": games played}}}

Run by cloud_daily.py with each MLB build (non-fatal); each game's box score is kept in .cache/lineups/<season>/<gamePk>.json, so a daily run
fetches only the new games (~2,400 the first time, ~90 s with 24 threads). Standard library only.
"""
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://statsapi.mlb.com/api/v1"
CACHE = os.path.join(ROOT, ".cache", "lineups")
LAST = 15


def get(path, timeout=120):
    req = urllib.request.Request(API + path, headers={"User-Agent": "seanvarg13.github.io daily update"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def season_of():
    """data.js's season and its last game day."""
    with open(os.path.join(ROOT, "data.js"), encoding="utf-8") as f:
        head = f.read(4000)
    import re
    season = int(re.search(r'"season"\s*:\s*(\d{4})', head).group(1))
    through = re.search(r'"through"\s*:\s*"(\d{4}-\d\d-\d\d)"', head).group(1)
    return season, through


def schedule(season):
    """Every finished regular-season game: (date, gamePk, away team id, home team id), in date order."""
    js = get(f"/schedule?sportId=1&season={season}&gameType=R&fields=dates,date,games,gamePk,status,abstractGameState,codedGameState,teams,away,home,team,id")
    out = []
    for d in js.get("dates", []):
        for g in d.get("games", []):
            st = g.get("status") or {}
            if st.get("abstractGameState") != "Final" or st.get("codedGameState") in ("D", "C"):   # postponed / cancelled
                continue
            t = g.get("teams") or {}
            out.append((d["date"], g["gamePk"], (t.get("away") or {}).get("team", {}).get("id"), (t.get("home") or {}).get("team", {}).get("id")))
    return sorted(out)


def box(pk, folder):
    """One game's lineups, from the cache or the API: per side the starting pitcher, the starters by slot, the substitutes, the bench and
    each batter's plate appearances."""
    f = os.path.join(folder, f"{pk}.json")
    if os.path.exists(f):
        try:
            with open(f) as fh:
                return json.load(fh)
        except ValueError:
            pass
    for attempt in range(3):
        try:
            t = get(f"/game/{pk}/boxscore?fields=teams,away,home,pitchers,bench,players,person,id,battingOrder,gameStatus,isSubstitute,stats,batting,plateAppearances", timeout=40)["teams"]
            break
        except Exception:                                  # noqa: BLE001
            if attempt == 2:
                return None
            import time; time.sleep(2 + 2 * attempt)
    out = {}
    for side in ("away", "home"):
        s = t.get(side) or {}
        st, sub, pa = {}, [], {}
        for v in (s.get("players") or {}).values():
            pid = (v.get("person") or {}).get("id")
            if not pid:
                continue
            bo = v.get("battingOrder")
            n = ((v.get("stats") or {}).get("batting") or {}).get("plateAppearances")
            if n:
                pa[str(pid)] = n
            if bo:
                slot = int(bo) // 100
                if int(bo) % 100 == 0 and not (v.get("gameStatus") or {}).get("isSubstitute") and 1 <= slot <= 9:
                    st[str(pid)] = slot
                else:
                    sub.append(pid)
        out[side[0]] = {"sp": (s.get("pitchers") or [None])[0], "st": st, "sub": sub, "bench": s.get("bench") or [], "pa": pa}
    os.makedirs(folder, exist_ok=True)
    with open(f, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


def hands(pids, folder):
    """{pitcher id: "L" / "R"} for the starting pitchers, cached."""
    f = os.path.join(folder, "hands.json")
    out = {}
    if os.path.exists(f):
        try:
            with open(f) as fh:
                out = json.load(fh)
        except ValueError:
            out = {}
    need = sorted({str(p) for p in pids if p and str(p) not in out})
    for i in range(0, len(need), 100):
        chunk = need[i:i + 100]
        try:
            for p in get(f"/people?personIds={','.join(chunk)}&fields=people,id,pitchHand,code").get("people", []):
                out[str(p["id"])] = ((p.get("pitchHand") or {}).get("code") or "")[:1]
        except Exception as e:                             # noqa: BLE001
            print(f"  hands {chunk[0]}…: {e}", flush=True)
    os.makedirs(folder, exist_ok=True)
    with open(f, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


def build(season, through):
    folder = os.path.join(CACHE, str(season))
    games = schedule(season)
    with ThreadPoolExecutor(max_workers=24) as ex:
        boxes = list(ex.map(lambda g: box(g[1], folder), games))
    missing = sum(1 for b in boxes if b is None)
    if missing > 0.03 * len(games):
        raise RuntimeError(f"{missing} of {len(games)} box scores couldn't be fetched")
    H = hands([b[s]["sp"] for b in boxes if b for s in ("a", "h")], folder)
    P, TG, order = {}, {}, {}                              # per hitter; games per team; each team's games in order (for the last 15)
    def rec(pid):
        r = P.get(pid)
        if r is None:
            r = P[pid] = {"ar": 0, "gs": 0, "pa": 0, "pas": 0, "gp": 0, "sl": [0] * 9, "vl": [0, 0], "vr": [0, 0], "tm": None, "days": {}}
        return r
    for (date, pk, away, home), b in zip(games, boxes):
        if not b:
            continue
        for side, team, other in (("a", away, "h"), ("h", home, "a")):
            TG[str(team)] = TG.get(str(team), 0) + 1
            order.setdefault(str(team), []).append((date, pk))
            s, hand = b[side], H.get(str(b[other]["sp"]), "")
            subs = {str(x) for x in s["sub"]}
            on = set(s["st"]) | subs | {str(x) for x in s["bench"]}
            for pid in on:
                r = rec(pid); r["ar"] += 1; r["pa"] += s["pa"].get(pid, 0); r["tm"] = str(team)
                slot = s["st"].get(pid, 0)
                if slot:
                    r["gs"] += 1; r["sl"][slot - 1] += 1; r["pas"] += s["pa"].get(pid, 0)
                if hand in ("L", "R"):
                    k = "vl" if hand == "L" else "vr"; r[k][1] += 1
                    if slot:
                        r[k][0] += 1
                if slot or pid in subs:
                    r["gp"] += 1
                r["days"][pk] = slot
    out = {}
    for pid, r in P.items():
        if not r["ar"]:
            continue
        last = [r["days"].get(pk, -1) for _, pk in order.get(r["tm"], [])[-LAST:]]
        out[pid] = {"ar": r["ar"], "gs": r["gs"], "pa": r["pa"], "sl": r["sl"], "vl": r["vl"], "vr": r["vr"], "last": last, "tm": int(r["tm"]), "pas": r["pas"], "gp": r["gp"]}
    data = {"season": season, "through": through, "g": TG, "p": out}
    path = os.path.join(ROOT, "hist", "lineups.js")
    body = "window.DRAFT_LINEUPS = " + json.dumps(data, separators=(",", ":")) + ";\n"
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != body:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
    starters = sum(1 for r in out.values() if r["gs"] >= 100)
    print(f"OK {len(out)} hitters ({starters} with 100+ starts), {len(games)} games, {missing} box scores missing -> hist/lineups.js ({len(body) / 1e3:.0f} KB)", flush=True)


def main():
    season, through = season_of()
    build(season, through)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                                 # noqa: BLE001
        print(f"!! build_lineups: {type(e).__name__}: {e}", flush=True)
        sys.exit(1)
