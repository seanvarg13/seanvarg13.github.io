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


def parse(text):
    f = {}
    for k in ("coach", "off_coach", "def_coach"):
        m = re.search(r"^\|\s*" + k + r"\s*=\s*(.*)$", text, re.M)
        f[k] = m.group(1) if m else ""
    hc, oc_raw = strip(f["coach"]), strip(f["off_coach"])
    # the page's Staff section lists the coordinator even where the infobox leaves him out; several lines = a change mid-season
    lines = re.findall(r"^\*\s*Offensive coordinator(?:\s*/[^–-]*)?\s*[–-]+\s*(.+)$", text, re.M | re.I)
    staffs = [re.sub(r"\(.*?\)", "", strip(x)).strip() for x in lines]
    staffs = [x for x in dict.fromkeys(staffs) if x]
    if staffs and not ("de facto" in oc_raw.lower()):
        oc_raw = " / ".join(staffs)
    facto = "de facto" in oc_raw.lower() or "(none)" in oc_raw.lower() or oc_raw.lower() in ("none", "vacant")
    oc = re.sub(r"\(.*?\)", "", oc_raw).strip()
    # several coordinators in a season ("A (weeks 1-8) B (weeks 9-18)") arrive joined; keep them as written
    hc = re.sub(r"\(.*", "", hc).strip()   # the games list carries the head coach game by game; this is only a label
    out = {"hc": hc or None, "oc": (None if facto and (not oc or oc == hc) else oc or None)}
    if facto or (oc and oc == hc):
        out["pc"] = hc
        out["oc"] = None if (not oc or oc == hc) else oc
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="football/data/staff.json")
    ap.add_argument("--seasons", default="2016-2026")
    ap.add_argument("--refresh", default="")
    a = ap.parse_args()
    lo, hi = map(int, a.seasons.split("-"))
    staff = json.load(open(a.out)) if os.path.exists(a.out) else {}
    fresh = {int(x) for x in a.refresh.split(",") if x}
    for y in range(lo, hi + 1):
        for tm in NAMES:
            key = f"{y}:{tm}"
            if key in staff and y not in fresh:
                continue
            text = fetch(page_name(tm, y))
            time.sleep(1.0)
            if not text:
                print("  no page", key, page_name(tm, y)); continue
            # the season in progress transcludes the club's staff template ({{Detroit Lions staff}}) instead of listing it
            m = re.search(r"\{\{\s*([^{}|]+? staff)\s*\}\}", text)
            if m and not re.search(r"^\*\s*Offensive coordinator", text, re.M | re.I):
                tpl = fetch("Template:" + m.group(1).strip())
                time.sleep(1.0)
                if tpl:
                    text += "\n" + tpl
            staff[key] = parse(text)
            print(key, staff[key], flush=True)
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(staff, open(a.out, "w"), indent=0, sort_keys=True)
    print(len(staff), "team-seasons")


if __name__ == "__main__":
    main()
