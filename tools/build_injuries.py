#!/usr/bin/env python3
"""hist/injuries.js: who is on the injured list today, from MLB's Stats API (Sean, 20 Oct 2026, item 8 of the recommendations: "injured list
badges on rows and cards, from MLB's data"). Every club's 40-man roster carries each player's status — D7 / D10 / D15 / D60 for the 7-, 10-,
15- and 60-day injured lists — and the injury itself as the roster note; the season's transactions give the day he went on the list (the
latest "placed … on the N-day injured list", or the date it was made retroactive to).

    window.DRAFT_IL = {"asOf": "2026-10-20", "p": {"<MLB id>": ["D60", "Bone bruise in left knee.", "2026-08-14"], …}}

Run by cloud_daily.py with each build (a few seconds; non-fatal). The page shows the badges only while the file is fresh (asOf within ten
days), so the list doesn't outlive the season when the builds stop for the winter. Standard library only.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://statsapi.mlb.com/api/v1"
IL = {"D7", "D10", "D15", "D60"}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                                      "November", "December"], 1)}


def get(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "seanvarg13.github.io daily update"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def placed_on(txs):
    """{player id: the day he went on the list} from the season's transactions: the latest placement, retroactive date first."""
    out = {}
    for t in txs:
        desc, pid = t.get("description") or "", (t.get("person") or {}).get("id")
        if not pid or not re.search(r"\bplaced\b.*\binjured list\b", desc, re.I):
            continue
        day = (t.get("effectiveDate") or t.get("date") or "")[:10]
        m = re.search(r"retroactive to (\w+) (\d{1,2}), (\d{4})", desc)
        if m and m.group(1) in MONTHS:
            day = f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"
        if day and day > out.get(pid, ""):
            out[pid] = day
    return out


def main():
    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    season = today.year if today.month >= 2 else today.year - 1
    teams = [t["id"] for t in get(f"/teams?sportId=1&season={season}")["teams"]]
    with ThreadPoolExecutor(max_workers=8) as ex:
        rosters = list(ex.map(lambda tid: get(f"/teams/{tid}/roster?rosterType=40Man&season={season}").get("roster", []), teams))
    hurt = {}
    for roster in rosters:
        for x in roster:
            code, pid = (x.get("status") or {}).get("code"), (x.get("person") or {}).get("id")
            if code in IL and pid:
                hurt[pid] = [code, (x.get("note") or "").strip()]
    since = placed_on(get(f"/transactions?sportId=1&startDate={season}-02-01&endDate={today}").get("transactions", []))
    for pid, v in hurt.items():
        v.append(since.get(pid, ""))
    out = {"asOf": str(today), "season": season, "p": {str(k): v for k, v in sorted(hurt.items())}}
    with open(os.path.join(ROOT, "hist", "injuries.js"), "w") as f:
        f.write("window.DRAFT_IL = " + json.dumps(out, separators=(",", ":")) + ";\n")
    by = {c: sum(1 for v in hurt.values() if v[0] == c) for c in sorted(IL)}
    print(f"hist/injuries.js: {len(hurt)} on the injured list as of {today} ({', '.join(f'{c} {n}' for c, n in by.items() if n)}); "
          f"{sum(1 for v in hurt.values() if v[2])} with the day they went on it")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                                 # noqa: BLE001 — the badges are a nicety; the build goes on without them
        print(f"build_injuries: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
