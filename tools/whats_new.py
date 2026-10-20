#!/usr/bin/env python3
"""What has finished since the site's last build: the morning run's question (Sean, 20 Oct 2026). Through the postseason the
morning run rebuilt the regular season, the four minor-league levels and every file on top of them each day, twice on most
days, with no new game in any of them. It republished the same numbers each time, and every publish reloads his phone.

Each dataset the daily run builds carries the last game day it holds ("through"): data.js for the MLB regular season,
hist/mlb-<y>-post.js, hist/mlb-<y>-spring.js and hist/<aaa|aa|ap|a>-<y>.js. Its step has something to do only when MLB's
schedule shows a game of that kind final after that date and no later than the last day to build (yesterday, New York).

  python3 tools/whats_new.py [--end YYYY-MM-DD] [--json]

prints the steps worth running, comma-separated (mlb, spring, post, minors), or nothing at all; --json prints the dates
found too. Standard library only: the workflow's gate runs it before Python is set up. When MLB's API can't be reached it
answers "everything", the old behaviour, rather than skip a day.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://statsapi.mlb.com/api/v1"
LEVELS = {"aaa": 11, "aa": 12, "ap": 13, "a": 14}        # build_milb.py's LEVELS: key -> MLB sportId
POST = "F,D,L,W"                                         # wild card, division series, LCS, World Series (build_history's KINDS)


BUILT = {}                                               # file -> its "built" stamp (UTC), read alongside "through"


def through_of(rel):
    """The last game day a built file holds, or None when there is no file (or it carries no date)."""
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r'"through":\s*"(\d{4}-\d\d-\d\d)"', txt)
    b = re.search(r'"built":\s*"(\d{4}-\d\d-\d\d \d\d:\d\d)"', txt)
    if b:
        BUILT[rel] = b.group(1)
    return m.group(1) if m else None


def last_built():
    """The latest build stamp ("YYYY-MM-DD HH:MM", UTC) among the files a check read, or ""."""
    return max(BUILT.values(), default="")


def day_after(d):
    return str(dt.date.fromisoformat(d) + dt.timedelta(days=1))


def finals(sport, types, start, end):
    """The days from start to end (inclusive) with a game of these types final, from MLB's schedule."""
    if start > end:
        return []
    u = f"{API}/schedule?sportId={sport}&gameType={types}&startDate={start}&endDate={end}"
    req = urllib.request.Request(u, headers={"User-Agent": "seanvarg13.github.io daily update"})
    with urllib.request.urlopen(req, timeout=60) as r:
        js = json.load(r)
    kinds = set(types.split(","))
    return sorted({d["date"] for d in js.get("dates", []) for g in d.get("games", [])
                   if (g.get("status") or {}).get("codedGameState") in ("F", "O") and g.get("gameType") in kinds})


def check(end):
    """{step: [days with new games]} for every step the daily run knows, plus each file's "through"."""
    y, mon = end[:4], int(end[5:7])
    seen, new = {}, {}

    def since(rel, fallback):
        t = through_of(rel)
        seen[rel] = t
        return day_after(t) if t else fallback

    new["mlb"] = finals(1, "R", since("data.js", f"{y}-03-01"), end)
    # spring training and the postseason are rebuilt in their months only, as cloud_daily.py always has
    new["spring"] = finals(1, "S", since(f"hist/mlb-{y}-spring.js", f"{y}-02-15"), end) if mon in (2, 3) else []
    new["post"] = finals(1, POST, since(f"hist/mlb-{y}-post.js", f"{y}-09-01"), end) if mon in (9, 10, 11) else []
    new["minors"] = {lv: days for lv, sport in LEVELS.items()
                     if (days := finals(sport, "R", since(f"hist/{lv}-{y}.js", f"{y}-03-01"), end))}
    return {"end": end, "through": seen, "new": new}


def steps(res):
    """The steps a check calls for, in the order the daily run takes them."""
    n = res["new"]
    return [s for s in ("mlb", "spring", "post", "minors") if n[s]]


def describe(res):
    n = res["new"]
    bits = []
    for s in ("mlb", "spring", "post"):
        if n[s]:
            bits.append(f"{s} ({n[s][0]}{' … ' + n[s][-1] if len(n[s]) > 1 else ''})")
    for lv, days in n["minors"].items():
        bits.append(f"{lv} ({days[0]}{' … ' + days[-1] if len(days) > 1 else ''})")
    return "new games: " + ", ".join(bits) if bits else f"nothing new through {res['end']}"


def yesterday():
    return str(dt.datetime.now(ZoneInfo("America/New_York")).date() - dt.timedelta(days=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", help="last day to build (default: yesterday, New York time)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    end = a.end or yesterday()
    try:
        res = check(end)
    except Exception as e:                                # noqa: BLE001 — no answer from MLB: build as the run always did
        print(f"whats_new: MLB's schedule didn't answer ({type(e).__name__}: {e}); building everything", file=sys.stderr)
        print(json.dumps({"end": end, "error": str(e), "steps": ["mlb", "minors"]}) if a.json else "mlb,minors")
        return
    print(json.dumps(dict(res, steps=steps(res))) if a.json else ",".join(steps(res)))
    print("whats_new: " + describe(res), file=sys.stderr)


if __name__ == "__main__":
    main()
