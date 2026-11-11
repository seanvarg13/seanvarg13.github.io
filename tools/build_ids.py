#!/usr/bin/env python3
"""hist/ids.js: the player-ID crosswalk the League tab reads (Sean, 11 Nov 2026: "an ability to connect to fantasy leagues"). A connected
league's rosters come in the platform's own player ids; the site's players are MLB's (MLBAM). Smart Fantasy Baseball's Player ID map — a
public Google sheet, smartfantasybaseball.com/PLAYERIDMAPCSV, every MLB player and most prospects with their MLB, ESPN, Fantrax, Yahoo,
CBS ... ids — gives the pairs:

    window.DRAFT_IDS = {"asOf": "2026-11-11", "espn": {"<ESPN id>": <MLB id>, …}, "ftx": {"<Fantrax id>": <MLB id>, …}}

A league player the map doesn't know (a fresh call-up) is matched by name and club in the page. An id that two rows give to different
MLB players is left out. Run by cloud_daily.py with the MLB build (non-fatal; the sheet is fetched again only when the file is a week old)
and by hand: python3 tools/build_ids.py [--force]. Standard library only.
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "hist", "ids.js")
URL = "https://www.smartfantasybaseball.com/PLAYERIDMAPCSV"


def fresh(days=7):
    """the file's asOf within `days`: nothing to fetch"""
    try:
        txt = open(OUT, encoding="utf-8").read()
        j = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        return (dt.date.today() - dt.date.fromisoformat(j["asOf"])).days < days
    except (OSError, ValueError, KeyError):
        return False


def main():
    if "--force" not in sys.argv and fresh():
        print("ids: hist/ids.js is under a week old — kept")
        return
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"})
    with urllib.request.urlopen(req, timeout=120) as r:
        rows = list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))
    maps = {"espn": {}, "ftx": {}}
    bad = {"espn": set(), "ftx": set()}
    for row in rows:
        mlb = (row.get("MLBID") or "").strip()
        if not mlb.isdigit():
            continue
        for key, col in (("espn", "ESPNID"), ("ftx", "FANTRAXID")):
            pid = (row.get(col) or "").strip().strip("*")   # Fantrax ids come wrapped in asterisks
            if not pid:
                continue
            had = maps[key].get(pid)
            if had is not None and had != int(mlb):
                bad[key].add(pid)
            maps[key][pid] = int(mlb)
    for key in maps:
        for pid in bad[key]:
            maps[key].pop(pid, None)
    if len(maps["espn"]) < 1000:
        sys.exit(f"ids: only {len(maps['espn'])} ESPN ids in the sheet — not writing")
    out = {"asOf": dt.date.today().isoformat(), "src": "Smart Fantasy Baseball's Player ID map", **maps}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.DRAFT_IDS = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print(f"ids: wrote hist/ids.js — {len(maps['espn'])} ESPN ids, {len(maps['ftx'])} Fantrax ids"
          + (f" (left out as ambiguous: {len(bad['espn'])} ESPN, {len(bad['ftx'])} Fantrax)" if bad["espn"] or bad["ftx"] else ""))


if __name__ == "__main__":
    main()
