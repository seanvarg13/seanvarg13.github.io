#!/usr/bin/env python3
"""The off-season refresh (Sean, 20 Oct 2026: "Ok do 1, 2, 3, 4, 5, and 6" — 6 being the real 2027 projections and ADP for the Mock
Draft, from the systems themselves once they're out). Repo only; run by hand or by the twice-monthly scheduled check (CLAUDE.md §8):

    python3 tools/build_offseason.py check     # what's out for 2027, changing nothing
    python3 tools/build_offseason.py proj      # FanGraphs' Steamer (+ ZiPS once it's out) -> hist/proj-2027.js
    python3 tools/build_offseason.py nfbc      # NFBC's 2027 ADP (its drafts since 1 Oct 2026) -> the "nfbc" source in hist/adp-2027.js
    python3 tools/build_offseason.py espn      # ESPN's 2027 ADP (once its 2027 game is open) -> the "espnadp" source in hist/adp-2027.js
    python3 tools/build_offseason.py moves     # the winter's signings, trades and waiver claims since the season's end -> hist/moves.js

Each step writes only when its source has 2027 data and says so otherwise, leaving the files as they are.

* proj — FanGraphs' projections page names its season in its title ("2027 Projections - Steamer"); until it says 2027 nothing is read.
  The API (/api/projections) answers a Safari user agent with JSON (a bare "Mozilla/5.0" gets Cloudflare's challenge, 20 Oct 2026).
  Every category FanGraphs projects comes from it — the systems averaged per PA / per out when both are out, playing time Steamer's —
  and the ones it doesn't (fielding, ESPN's bonus categories, NP, GF …) are build_proj27.py's Marcel rate times that playing time. A
  player FanGraphs doesn't project keeps Marcel's whole line; one only FanGraphs projects comes in if this season's data.js has him.
* nfbc — NFBC's ADP table (nfc.shgn.com/adp/baseball) is posted from /adp.data.php; from_date = 1 Oct 2026 keeps it to the 2027 draft
  season. Needs 20+ drafts. Rank = his place in NFBC's ADP order; names matched to data.js by name, team breaking a tie.
* espn — ESPN's fantasy API (lm-api-reads.fantasy.espn.com) has no 2027 season until its game opens (late winter); then each player's
  averageDraftPosition, once 150+ players have one.
* moves — MLB's transaction log (statsapi.mlb.com/api/v1/transactions, sportId 1) from the day after data.js's last game: a player of this
  season's data.js signed as a free agent (SFA), traded (TR) or claimed off waivers (CLW) to a club other than the one data.js has him on, his
  latest such move kept; one who elected free agency or was released (DFA / REL) is marked a free agent with no club until a signing. The
  app (hist/moves.js) puts the new club on him — the lists' Tm, his page's bio, the Bullpens, the park what-if's "his new park" — so a
  signed or traded player's team and park follow him over the winter instead of freezing at the season's end (Sean, 28 Oct 2026, item 15
  of the review's picks).
"""
import datetime, json, os, re, sys, unicodedata, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
YEAR = 2027
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
SINCE = "2026-10-01"                                           # the 2027 draft season's first day
TEAM_FIX = {"ARZ": "AZ", "ARI": "AZ", "CHW": "CWS", "KCR": "KC", "SDP": "SD", "SFG": "SF", "TBR": "TB", "WSN": "WSH", "WAS": "WSH", "OAK": "ATH", "LV": "ATH"}
MLB_TEAM = {110: "BAL", 111: "BOS", 147: "NYY", 139: "TB", 141: "TOR", 145: "CWS", 114: "CLE", 116: "DET", 118: "KC", 142: "MIN", 133: "ATH", 117: "HOU", 108: "LAA",
            136: "SEA", 140: "TEX", 144: "ATL", 146: "MIA", 121: "NYM", 143: "PHI", 120: "WSH", 112: "CHC", 113: "CIN", 158: "MIL", 134: "PIT", 138: "STL",
            109: "AZ", 115: "COL", 119: "LAD", 135: "SD", 137: "SF"}   # MLB's team ids (the app's TEAM_ID, inverted)
MOVE_KIND = {"SFA": "signed", "TR": "traded", "CLW": "claimed", "DFA": "free agent", "REL": "released"}
ESPN_TEAM = {1: "BAL", 2: "BOS", 3: "LAA", 4: "CWS", 5: "CLE", 6: "DET", 7: "KC", 8: "MIL", 9: "MIN", 10: "NYY", 11: "ATH", 12: "SEA", 13: "TEX",
             14: "TOR", 15: "ATL", 16: "CHC", 17: "CIN", 18: "HOU", 19: "LAD", 20: "WSH", 21: "NYM", 22: "PHI", 23: "PIT", 24: "STL", 25: "SD",
             26: "SF", 27: "COL", 28: "MIA", 29: "AZ", 30: "TB"}


def get(url, data=None, headers=None, timeout=90):
    h = {"User-Agent": UA, **(headers or {})}
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def jsobj(path):
    s = open(os.path.join(ROOT, path), encoding="utf-8").read()
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def write_js(path, var, doc):
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
        f.write(f"window.{var} = " + json.dumps(doc, separators=(",", ":")) + ";\n")


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def roster():
    """data.js's players: (type, id) -> name / team, and name -> [(type, id, team)]"""
    d = jsobj("data.js"); by = {}
    for p in d["players"]:
        by.setdefault(norm(p["name"]), []).append((p["type"], str(p["id"]), p.get("team")))
    return d, by


def match(by, name, team, want):
    """our (type, id) for a list's name: the type it should be (H / P / None for either), team breaking a tie"""
    c = [x for x in by.get(norm(name), []) if want is None or x[0] == want]
    if len(c) > 1 and team: c = [x for x in c if x[2] == TEAM_FIX.get(team, team)] or c
    return c[0][:2] if c else None


# ---------------------------------------------------------------------------------------------------------------- projections
def fg_season(system):
    try: html = get(f"https://www.fangraphs.com/projections?type={system}&stats=bat&pos=all&team=0&players=0&lg=all")
    except Exception as e: return None, f"{system}: couldn't reach FanGraphs ({type(e).__name__})"
    m = re.search(r"<title[^>]*>\s*(\d{4}) Projections", html)
    return (int(m.group(1)) if m else None), None


def fg_rows(system, stats):
    rows = json.loads(get(f"https://www.fangraphs.com/api/projections?type={system}&stats={stats}&pos=all&team=0&players=0&lg=all",
                          headers={"Accept": "application/json"}))
    return {str(r["xMLBAMID"]): r for r in rows if r.get("xMLBAMID")}


def proj(dry=False):
    out = {}
    for s in ("steamer", "zips"):
        y, err = fg_season(s)
        print(f"FanGraphs {s}: {err or (f'{y} projections' if y else 'no season in the page title')}")
        if y == YEAR: out[s] = {"H": fg_rows(s, "bat"), "P": fg_rows(s, "pit")}
    if not out:
        print(f"no {YEAR} projections yet — hist/proj-{YEAR}.js left as it is"); return False
    if dry: return True
    import build_proj27 as bp                                   # Marcel, for what FanGraphs doesn't project
    S, AGE = bp.season_files(), bp.ages()
    hk, MH = bp.project_hitters(S, AGE)
    pk, MP = bp.project_pitchers(S, AGE)
    d, _ = roster(); have = {(p["type"], str(p["id"])) for p in d["players"]}
    systems = list(out); pt = "steamer" if "steamer" in out else systems[0]
    # FanGraphs' columns for our categories (hitters per PA, pitchers per out); TB from the hits
    FH = {"G": "G", "PA": "PA", "AB": "AB", "H": "H", "2B": "2B", "3B": "3B", "HR": "HR", "R": "R", "RBI": "RBI", "BB": "BB", "IBB": "IBB",
          "HBP": "HBP", "K": "SO", "SB": "SB", "CS": "CS", "GIDP": "GDP", "SF": "SF", "SH": "SH"}
    FP = {"G": "G", "GS": "GS", "W": "W", "L": "L", "SV": "SV", "HD": "HLD", "BS": "BS", "K": "SO", "H": "H", "ER": "ER", "R": "R", "HR": "HR",
          "BB": "BB", "IBB": "IBB", "HBP": "HBP", "BF": "TBF", "QS": "QS"}
    num = lambda r, k: float(r.get(k) or 0)

    def line(t, pid):
        keys, fmap, marcel = (hk, FH, MH) if t == "H" else (pk, FP, MP)
        rows = [out[s][t][pid] for s in systems if pid in out[s][t]]
        base = marcel.get(pid)
        if not rows: return base                                # FanGraphs doesn't project him: Marcel's whole line
        lead = out[pt][t].get(pid) or rows[0]
        if t == "H":
            n = num(lead, "PA")
            if n <= 0: return base
            per = lambda r: max(num(r, "PA"), 1e-9)
        else:
            n = 3 * num(lead, "IP")
            if n <= 0: return base
            per = lambda r: max(3 * num(r, "IP"), 1e-9)
        mden = (base[keys.index("PA")] if t == "H" else base[keys.index("OUTS")]) if base else 0
        o = []
        for k in keys:
            if k in ("PA", "OUTS"): v = n
            elif k in ("G", "GS"): v = num(lead, fmap[k])       # games are playing time, Steamer's
            elif k == "TB" and t == "H":
                v = sum(num(r, "1B") + 2 * num(r, "2B") + 3 * num(r, "3B") + 4 * num(r, "HR") for r in rows) / sum(per(r) for r in rows) * n
            elif k in fmap and any(r.get(fmap[k]) is not None for r in rows):
                rs = [r for r in rows if r.get(fmap[k]) is not None]
                v = sum(num(r, fmap[k]) / per(r) for r in rs) / len(rs) * n
            elif base and mden: v = base[keys.index(k)] / mden * n   # Marcel's rate, FanGraphs' playing time
            else: v = 0.0
            o.append(round(v, 1))
        return o

    H, P = {}, {}
    for t, dst, marcel in (("H", H, MH), ("P", P, MP)):
        ids = set(marcel) | {pid for s in systems for pid in out[s][t] if (t, pid) in have}
        for pid in sorted(ids):
            l = line(t, pid)
            if l: dst[pid] = l
    doc = {"built": datetime.date.today().isoformat(), "season": YEAR, "systems": systems,
           "note": f"{' + '.join(s.title() if s != 'zips' else 'ZiPS' for s in systems)} {YEAR} (FanGraphs) for every category they project, "
                   f"playing time {pt.title()}'s; Marcel (tools/build_proj27.py) fills the rest and the players they don't project; tools/build_offseason.py",
           "hk": hk, "pk": pk, "hitters": H, "pitchers": P}
    write_js(f"hist/proj-{YEAR}.js", "DRAFT_PROJ27", doc)
    print(f"wrote hist/proj-{YEAR}.js from {', '.join(systems)}: {len(H)} hitters, {len(P)} pitchers")
    return True


# ---------------------------------------------------------------------------------------------------------------- ADP
def adp_update(key, source, ranks):
    doc = jsobj(f"hist/adp-{YEAR}.js")
    doc["sources"] = [s for s in doc["sources"] if s["key"] != key] + [source]
    for r in doc["ranks"].values(): r.pop(key, None)
    for k, v in ranks.items(): doc["ranks"].setdefault(k, {})[key] = v
    doc["ranks"] = {k: v for k, v in doc["ranks"].items() if v}
    doc["built"] = datetime.date.today().isoformat()
    write_js(f"hist/adp-{YEAR}.js", "DRAFT_ADP27", doc)


def nfbc(dry=False):
    to = datetime.date.today().isoformat()
    try:
        html = get("https://nfc.shgn.com/adp.data.php", data={"team_id": 0, "time_period": "", "from_date": SINCE, "to_date": to, "num_teams": 0,
                   "draft_type": 0, "sport": "baseball", "position": "", "league_teams": 0, "as_board": ""},
                   headers={"X-Requested-With": "XMLHttpRequest", "Referer": "https://nfc.shgn.com/adp/baseball"})
    except Exception as e:
        print(f"NFBC: couldn't reach it ({type(e).__name__})"); return False
    rows = []
    for tr in re.findall(r"<tr\b.*?</tr>", html, re.S):
        name = re.search(r"class='PlayerLinkV'[^>]*>([^<]+)<", tr)
        if not name: continue
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        team = re.sub(r"<[^>]+>", "", tds[2]).strip() if len(tds) > 2 else ""
        pos = re.sub(r"<[^>]+>", "", tds[3]).strip() if len(tds) > 3 else ""
        adp = re.search(r'sort-value="([\d.]+)"', tr)
        drafts = [int(x) for x in re.findall(r"<td>(\d+)</td>", tr)]
        if adp: rows.append((name.group(1).strip(), team, pos, float(adp.group(1)), max(drafts) if drafts else 0))
    n = max((r[4] for r in rows), default=0)
    print(f"NFBC: {len(rows)} players, {n} drafts since {SINCE}")
    if n < 20: print(f"  not enough {YEAR} drafts yet — hist/adp-{YEAR}.js left as it is"); return False
    if dry: return True
    _, by = roster(); ranks = {}; miss = 0
    for i, (nm, team, pos, adp, _) in enumerate(sorted(rows, key=lambda r: r[3])):
        ps = [p.strip() for p in pos.split(",")]
        want = "P" if ps and all(p in ("P", "SP", "RP") for p in ps) else "H"     # a two-way player (UT, P) ranks as the hitter, as the file keys him
        m = match(by, nm, team, want)
        if m: ranks[m[0] + m[1]] = i + 1
        else: miss += 1
    adp_update("nfbc", {"key": "nfbc", "name": f"NFBC · {YEAR} ADP, {n} drafts since {SINCE}", "url": "https://nfc.shgn.com/adp/baseball",
                        "date": to, "kind": "overall", "weight": 2}, ranks)
    print(f"  wrote the nfbc source: {len(ranks)} players matched, {miss} not on this season's site (prospects, players who missed {YEAR - 1})")
    return True


def espn(dry=False):
    flt = json.dumps({"players": {"limit": 600, "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "STANDARD"}}})
    try:
        d = json.loads(get(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/flb/seasons/{YEAR}/segments/0/leaguedefaults/3?view=kona_player_info",
                           headers={"X-Fantasy-Filter": flt, "Accept": "application/json"}))
    except Exception as e:
        print(f"ESPN: no {YEAR} game yet ({type(e).__name__})"); return False
    ps = [(x["player"], (x["player"].get("ownership") or {}).get("averageDraftPosition") or 0) for x in d.get("players", [])]
    ps = [(p, a) for p, a in ps if 0 < a < 500]
    print(f"ESPN: {len(ps)} players with an average draft position")
    if len(ps) < 150 or min(a for _, a in ps) > 5: print(f"  no real {YEAR} ADP yet — hist/adp-{YEAR}.js left as it is"); return False
    if dry: return True
    _, by = roster(); ranks = {}
    for i, (p, a) in enumerate(sorted(ps, key=lambda z: z[1])):
        want = "P" if p.get("defaultPositionId") in (1, 11) else "H"
        m = match(by, p.get("fullName"), ESPN_TEAM.get(p.get("proTeamId")), want)
        if m: ranks[m[0] + m[1]] = i + 1
    adp_update("espnadp", {"key": "espnadp", "name": f"ESPN · {YEAR} ADP (its own drafts)", "url": "https://fantasy.espn.com/baseball/livedraftresults",
                           "date": datetime.date.today().isoformat(), "kind": "overall", "weight": 2}, ranks)
    print(f"  wrote the espnadp source: {len(ranks)} players matched")
    return True


# ---------------------------------------------------------------------------------------------------------------- winter moves
def moves(dry=False):
    d, _ = roster(); since = (datetime.date.fromisoformat(d["meta"]["through"]) + datetime.timedelta(days=1)).isoformat()
    today = datetime.date.today().isoformat()
    have = {}; team0 = {}
    for p in d["players"]: have.setdefault(str(p["id"]), set()).add(p["type"]); team0[str(p["id"])] = p.get("team")
    try:
        t = json.loads(get(f"https://statsapi.mlb.com/api/v1/transactions?sportId=1&startDate={since}&endDate={today}")).get("transactions", [])
    except Exception as e:
        print(f"moves: couldn't reach MLB's transactions ({type(e).__name__})"); return False
    out = {}
    for x in sorted(t, key=lambda x: (x.get("date") or "", x.get("id") or 0)):
        code = x.get("typeCode"); pid = str((x.get("person") or {}).get("id") or "")
        if code not in MOVE_KIND or pid not in have: continue
        to = MLB_TEAM.get((x.get("toTeam") or {}).get("id"))
        if code in ("SFA", "TR", "CLW") and not to: continue
        if code in ("SFA", "TR", "CLW") and to == team0.get(pid) and pid not in out: continue   # re-signed by his own club, or claimed back: not a move
        desc = x.get("description") or ""
        kind = MOVE_KIND[code] + (" (minors deal)" if code == "SFA" and "minor league" in desc.lower() else "")
        out[pid] = {"tm": to if code in ("SFA", "TR", "CLW") else None, "kind": kind, "date": x.get("date"), "from": team0.get(pid), "desc": desc[:140]}
    out = {k: v for k, v in out.items() if v["tm"] != team0.get(k)}   # a free agent who re-signed with his club is back where data.js has him
    path = "hist/moves.js"; old = None
    try: old = jsobj(path)
    except Exception: pass
    n_old = len((old or {}).get("p") or {})
    print(f"moves: {len(out)} players of {d['meta']['season']}'s data.js moved since {since} ({sum(1 for v in out.values() if v['tm'])} to a new club, {sum(1 for v in out.values() if not v['tm'])} free agents / released)"
          + (f"; hist/moves.js has {n_old} as of {old.get('asOf')}" if old else "; no hist/moves.js yet"))
    if dry: return bool(out) and (not old or old.get("asOf") != today or n_old != len(out))
    write_js(path, "DRAFT_MOVES", {"asOf": today, "since": since, "season": d["meta"]["season"], "p": out})
    print(f"wrote {path}"); return True


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "check"
    if what == "check":
        proj(dry=True); nfbc(dry=True); espn(dry=True); moves(dry=True)
    elif what in ("proj", "nfbc", "espn", "moves"):
        globals()[what]()
    else:
        sys.exit(__doc__)
