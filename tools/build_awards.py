#!/usr/bin/env python3
"""hist/awards.js — every MVP / Cy Young / Rookie of the Year vote finish, keyed by MLB id (Sean, 10 Oct 2026: "show like mvp-1,
mvp-8, cya-1, cya-5, roy-1, roy-4 ... and bold any award they won or came in first for").

MLB's own record (people/<id>/awards, read in the browser) has the winners only, so the placings come from the Lahman database
(SABR, sabr.org/lahman-database — AwardsSharePlayers.csv, every player who got a vote, points won), mapped to MLB ids by name and
birth date against the Stats API's season rosters. Placing = competition rank by points within award × year × league (a tie shares
the better place). Repo only, run by hand once SABR publishes the year's update (each January):

    python3 tools/build_awards.py            # 1990 on
    python3 tools/build_awards.py 1980       # from another year

Writes window.DRAFT_VOTES = {"<mlb id>": {"<year>": [["MVP", 1], ["CYA", 5]]}}.
"""
import csv, io, json, os, re, sys, unicodedata, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOX = "y1prhc795jk8zvmelfd3jq7tl389y6cd"                     # SABR's comma-delimited folder on Box
FILES = {"AwardsSharePlayers.csv": "f_2084271782061", "People.csv": "f_2084263017537"}   # the 2025 release
CODE = {"Most Valuable Player": "MVP", "Cy Young Award": "CYA", "Rookie of the Year": "ROY"}
CACHE = os.path.join(ROOT, ".cache", "awards")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def box_file(name):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name)
    if not os.path.exists(p):
        url = f"https://sabr.box.com/index.php?rm=box_download_shared_file&shared_name={BOX}&file_id={FILES[name]}"
        open(p, "wb").write(get(url))
    return list(csv.DictReader(io.StringIO(open(p, encoding="utf-8-sig").read())))


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s.replace(" jr", "").replace(" sr", ""))


def roster(y):
    p = os.path.join(CACHE, f"players-{y}.json")
    if not os.path.exists(p):
        u = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={y}&fields=people,id,fullName,lastName,firstName,useName,birthDate"
        open(p, "wb").write(get(u))
    return json.load(open(p)).get("people", [])


def main():
    since = int(sys.argv[1]) if len(sys.argv) > 1 else 1990
    shares = [r for r in box_file("AwardsSharePlayers.csv") if int(r["yearID"]) >= since and r["awardID"] in CODE]
    people = {r["playerID"]: r for r in box_file("People.csv")}
    years = sorted({int(r["yearID"]) for r in shares})
    # MLB ids by birth date, then by last name inside a birth date
    by_birth = {}
    for y in range(years[0] - 1, years[-1] + 1):
        for m in roster(y):
            if m.get("birthDate"):
                by_birth.setdefault(m["birthDate"], {})[m["id"]] = m
    ids, miss = {}, []
    for pid in {r["playerID"] for r in shares}:
        pe = people.get(pid)
        if not pe or not pe["birthYear"]:
            miss.append(pid); continue
        bd = f"{int(pe['birthYear']):04d}-{int(pe['birthMonth']):02d}-{int(pe['birthDay']):02d}"
        cand = list(by_birth.get(bd, {}).values())
        last = norm(pe["nameLast"])
        hit = [m for m in cand if norm(m.get("lastName")) == last] or [m for m in cand if last and last in norm(m.get("fullName"))]
        if len(hit) > 1:
            first = norm(pe["nameFirst"])[:3]
            hit = [m for m in hit if norm(m.get("useName") or m.get("firstName")).startswith(first)] or hit[:1]
        if not hit and len(cand) == 1:
            hit = cand
        if hit:
            ids[pid] = hit[0]["id"]
        else:
            miss.append(pid)
    groups = {}
    for r in shares:
        groups.setdefault((r["awardID"], r["yearID"], r["lgID"]), []).append(r)
    out = {}
    for (aw, y, lg), rs in groups.items():
        pts = sorted((float(r["pointsWon"] or 0) for r in rs), reverse=True)
        for r in rs:
            if r["playerID"] not in ids:
                continue
            place = 1 + sum(1 for v in pts if v > float(r["pointsWon"] or 0))
            out.setdefault(str(ids[r["playerID"]]), {}).setdefault(y, []).append([CODE[aw], place])
    order = list(CODE.values())
    for d in out.values():
        for l in d.values():
            l.sort(key=lambda x: order.index(x[0]))
    path = os.path.join(ROOT, "hist", "awards.js")
    with open(path, "w") as f:
        f.write(f"/* MVP / Cy Young / Rookie of the Year vote finishes {years[0]}-{years[-1]}, from the Lahman database (SABR); tools/build_awards.py */\n")
        f.write("window.DRAFT_VOTES = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print(f"{len(out)} players, {sum(len(v) for d in out.values() for v in d.values())} finishes, {years[0]}-{years[-1]}; "
          f"unmatched {len(miss)}: {', '.join(sorted(miss)[:30])}")


if __name__ == "__main__":
    main()
