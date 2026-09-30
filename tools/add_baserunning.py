"""Fill the card's Base Running numbers (sprint speed, SB, SB attempts, SB%) into already-built MLB files without a
rebuild — build_data.py writes them itself from 30 Sep 2026 on, so this is for files built before that.

    python3 add_baserunning.py                 # data.js and every hist/mlb-YYYY.js (regular seasons)
    python3 add_baserunning.py hist/mlb-2024.js

Sprint speed is Savant's leaderboard (5+ competitive runs, as the build's sprint_speeds()); steals are the MLB Stats
API's season lines. Only hitters' m gets the four keys; nothing else in a file changes."""
import json, re, sys, csv, io
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0"}


def sprint(year: int) -> dict:
    t = requests.get(f"https://baseballsavant.mlb.com/leaderboard/sprint_speed?min_season={year}&max_season={year}"
                     "&position=&team=&min=5&csv=true", headers=UA, timeout=60).content.decode("utf-8-sig")
    return {int(r["player_id"]): float(r["sprint_speed"]) for r in csv.DictReader(io.StringIO(t)) if r.get("sprint_speed")}


def steals(year: int) -> dict:
    js = requests.get(f"https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&season={year}&sportId=1"
                      "&playerPool=ALL&limit=5000", headers=UA, timeout=60).json()
    out = {}
    for sp in js["stats"][0]["splits"]:
        st, pid = sp["stat"], sp["player"]["id"]
        a = out.setdefault(pid, [0, 0])            # a traded player can come back once per club: add them up
        a[0] += int(st.get("stolenBases", 0) or 0); a[1] += int(st.get("caughtStealing", 0) or 0)
    return out


def patch(path: Path):
    txt = path.read_text()
    m = re.search(r"^(.*?= )(\{.*\});?\s*$", txt.splitlines()[-1] if "DRAFT_HIST" in txt else txt, re.S)
    head_lines = txt.splitlines()[:-1] if "DRAFT_HIST" in txt else []
    pre, body = m.group(1), m.group(2)
    d = json.loads(body)
    year = (d.get("meta") or d)["season"]
    spd, sbs = sprint(year), steals(year)
    n = 0
    for p in d["players"]:
        if p["type"] != "H":
            continue
        sb, cs = sbs.get(p["id"], (None, None))
        att = sb + cs if sb is not None else None
        s = spd.get(p["id"])
        p["m"].update({"spd": round(s, 1) if s is not None else None, "sb": sb, "sba": att,
                       "sbp": round(100 * sb / att, 1) if att else None})
        n += 1
    out = pre + json.dumps(d, separators=(",", ":"), ensure_ascii=False) + ";"
    path.write_text("\n".join(head_lines + [out]) + "\n")
    print(f"{path.name}: {year}, {n} hitters, {sum(1 for p in d['players'] if p['type'] == 'H' and p['m']['spd'] is not None)} with sprint speed")


if __name__ == "__main__":
    root = HERE.parent if (HERE.parent / "data.js").exists() else HERE
    files = [Path(a) for a in sys.argv[1:]] or [root / "data.js"] + sorted((root / "hist").glob("mlb-20[0-9][0-9].js"))
    for f in files:
        patch(f)
