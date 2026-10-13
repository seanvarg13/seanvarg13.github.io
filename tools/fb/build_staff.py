#!/usr/bin/env python3
"""Offensive coordinators by team-season, from each team-season's Wikipedia page (its Staff section, else the infobox's
off_coach; the season in progress reads the club's staff template, which its page transcludes).

    python3 tools/fb/build_staff.py [--out football/data/staff.json] [--seasons 2016-2026] [--refresh 2026]

Wikipedia's API rate-limits shared IPs, so this reads the page source (index.php?action=raw, section 0) one page
a second. A season already in staff.json is kept unless named in --refresh. "de facto" / a blank coordinator
means the head coach ran the offence himself, which is written as pc (play-caller) = the head coach.
"""
import argparse, json, os, re, time, urllib.parse, urllib.request

# nflverse abbreviation -> franchise name by season (relocations and renames)
NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys", "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "KC": "Kansas City Chiefs",
    "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers", "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers", "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}


def page_name(tm, y):
    n = NAMES[tm]
    if tm == "LV" and y <= 2019: n = "Oakland Raiders"
    if tm == "LAC" and y <= 2016: n = "San Diego Chargers"
    if tm == "WAS":
        n = "Washington Redskins" if y <= 2019 else "Washington Football Team" if y <= 2021 else n
    return f"{y} {n} season"


def strip(v):
    v = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^/]*/>", "", v or "")
    v = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\{\{[^}]*\}\}|<[^>]+>|'{2,}", "", v)
    return re.sub(r"\s+", " ", v).strip(" ,;")


def fetch(title):
    url = "https://en.wikipedia.org/w/index.php?" + urllib.parse.urlencode({"title": title, "action": "raw"})
    req = urllib.request.Request(url, headers={"User-Agent": "SeansSiteFootball/1.0 (personal fantasy site; one request a second)"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return None


# the offence's staff: the head coach block (but its defensive assistants) and every offensive coach. Past seasons list the
# final staff in {{NFL final staff |Head Coaches= … |Offensive Coaches= … |Defensive Coaches=}}; the season in progress, the
# club's template (;Head coaches / ;Offensive coaches / ;Defensive coaches)
NOT_OFF = re.compile(r"defens|special teams|linebacker|secondary|safet|cornerback|defensive|strength|conditioning|nickel|pass rush", re.I)


def staff_block(text):
    for pat in (r"\|\s*(?:Head Coaches|head_coach(?:es)?)\s*=(.*?)\|\s*(?:Defensive Coaches|defensive(?:_coaches)?)\s*=",
                r";\s*Head coach(?:es)?\b(.*?);\s*Defensive coach", r"'''\s*Head coach(?:es)?\s*'''(.*?)'''\s*Defensive coach"):
        m = re.search(pat, text, re.S | re.I)
        if m:
            return m.group(1)
    return ""


def offense(text):
    out = []
    for line in re.findall(r"^\*\s*(.+)$", staff_block(text), re.M):
        line = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^/]*/>", "", line)
        parts = re.split(r"\s+[–—]\s+|\s+-\s+", line, maxsplit=1)
        if len(parts) < 2:
            continue
        role, who = strip(parts[0]), parts[1]
        if not role or NOT_OFF.search(role):
            continue
        links = re.findall(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", who)
        names = links or [x for x in re.split(r",| and ", re.sub(r"\(.*?\)", "", strip(who))) if x.strip()]
        for n in names:
            n = re.sub(r"\s*\(.*?\)", "", n).strip(" ,;")
            if n and len(n) < 40 and n.lower() not in ("vacant", "none", "tba", "tbd"):
                out.append([role, n])
    return out


def parse(text):
    f = {}
    for k in ("coach", "off_coach", "def_coach"):
        m = re.search(r"^\|[ \t]*" + k + r"[ \t]*=[ \t]*(.*)$", text, re.M)   # [ \t], not \s: a blank field mustn't swallow the next line
        f[k] = m.group(1) if m else ""
    hc, oc_raw = strip(f["coach"]), strip(f["off_coach"])
    # the page's Staff section lists the coordinator even where the infobox leaves him out; several lines = a change mid-season
    lines = re.findall(r"^\*\s*Offensive coordinator(?:\s*/[^–-]*)?\s*[–-]+\s*(.+)$", text, re.M | re.I)
    staffs = [re.sub(r"\(.*?\)", "", strip(x)).strip() for x in lines]
    staffs = [x for x in dict.fromkeys(staffs) if x]
    if staffs and not ("de facto" in oc_raw.lower()):
        oc_raw = " / ".join(staffs)
    facto = "de facto" in oc_raw.lower() or "(none)" in oc_raw.lower() or oc_raw.lower() in ("none", "vacant")
    oc = re.sub(r"\(.*?\)", "", oc_raw).split(";")[0].strip()   # "Ken Dorsey; fired after Week 10"
    if oc.lower() in ("vacant", "none"):
        oc = ""
    # several coordinators in a season ("A (weeks 1-8) B (weeks 9-18)") arrive joined; keep them as written
    hc = re.sub(r"\(.*", "", hc).strip()   # the games list carries the head coach game by game; this is only a label
    out = {"hc": hc or None, "oc": (None if facto and (not oc or oc == hc) else oc or None), "off": offense(text)}
    if facto or (oc and oc == hc):
        out["pc"] = hc
        out["oc"] = None if (not oc or oc == hc) else oc
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="football/data/staff.json")
    ap.add_argument("--seasons", default="2016-2026")
    ap.add_argument("--refresh", default="")
    ap.add_argument("--cache", default=".cache/fb/wiki", help="the raw pages, so a re-parse needs no requests")
    ap.add_argument("--reparse", action="store_true", help="parse every season again (from the cache where it has the page)")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    lo, hi = map(int, a.seasons.split("-"))
    staff = json.load(open(a.out)) if os.path.exists(a.out) else {}
    fresh = {int(x) for x in a.refresh.split(",") if x}
    for y in range(lo, hi + 1):
        for tm in NAMES:
            key = f"{y}:{tm}"
            if key in staff and y not in fresh and not a.reparse:
                continue
            cp = os.path.join(a.cache, f"{y}-{tm}.txt")
            text = None
            if os.path.exists(cp) and y not in fresh:
                text = open(cp, encoding="utf-8").read()
            else:
                text = fetch(page_name(tm, y))
                time.sleep(1.0)
                if not text:
                    print("  no page", key, page_name(tm, y)); continue
                # the season in progress transcludes the club's staff template ({{Detroit Lions staff}}) instead of listing it
                m = re.search(r"\{\{\s*([^{}|]+? staff)\s*\}\}", text)
                if m and not staff_block(text):
                    tpl = fetch("Template:" + m.group(1).strip())
                    time.sleep(1.0)
                    if tpl:
                        text += "\n" + tpl
                open(cp, "w", encoding="utf-8").write(text)
            staff[key] = parse(text)
            print(key, staff[key]["hc"], "/", staff[key]["oc"], "·", len(staff[key]["off"]), "offensive coaches", flush=True)
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(canon(staff), open(a.out, "w"), indent=0, sort_keys=True)
    print(len(staff), "team-seasons")


def canon(staff):
    """One spelling per coach: "T. J. Paganetti" / "T.J. Paganetti", "DeNarius" / "Denarius" fold to the commoner one, so his
    history isn't split. Jr. / Sr. stay apart (Tony Sparano and Tony Sparano Jr. are father and son)."""
    from collections import Counter
    seen = Counter()
    for v in staff.values():
        for _, n in v.get("off") or []:
            seen[n] += 1
        for k in ("hc", "oc", "pc"):
            for n in (v.get(k) or "").split(" / "):
                if n: seen[n] += 1
    key = lambda n: re.sub(r"[^a-z]", "", n.lower())
    best = {}
    for n, c in seen.most_common():
        best.setdefault(key(n), n)
    fix = lambda n: best.get(key(n), n)
    for v in staff.values():
        v["off"] = [[r, fix(n)] for r, n in v.get("off") or []]
        for k in ("hc", "oc", "pc"):
            if v.get(k):
                v[k] = " / ".join(fix(n) for n in v[k].split(" / "))
    return staff


if __name__ == "__main__":
    main()
