#!/usr/bin/env python3
"""2027 projections for the Mock Draft (Sean, 2 Oct 2026: "these rankings feel very odd and wrong, maybe use like some sort of 2027
projection system ... fangraphs or zips or oopsy"). Steamer / ZiPS / OOPSY 2027 aren't out in October (they land from November) and
FanGraphs sits behind Cloudflare, so this is the system they're all measured against — Marcel — with two upgrades:

* Marcel's rates: every official category per PA (hitters) or per out (pitchers), the last three seasons weighted 5/4/3
  (pitchers 3/2/1), regressed with 1200 weighted PA (pitchers 600 weighted outs) of the league's rate, then aged (+0.6% a year under
  29, -0.3% a year over, on the good categories; the bad ones the other way).
* Statcast: a hitter's H and TB are pulled halfway to his expected (xBA / xSLG x AB, Savant's, from the fantasy files), the extra-base
  hits scaled to match; a pitcher's ER halfway to his xERA. Luck on balls in play washes out the way it does in the real systems.
* Playing time: Marcel's (0.5 x last + 0.1 x the year before + a base) is famously short on a regular who lost a season to injury
  (Judge, 285 PA in 2026), so an established regular gets at least 85% of his two fullest seasons, and a young everyday player at
  least a full-time share. Caps 700 PA / 200 IP / 72 IP for a reliever.

Writes hist/proj-2027.js: {built, note, hk, pk, hitters: {id: [line]}, pitchers: {id: [line]}} — lines in the fantasy files' own
category order, so the site scores them with any preset. Repo only, run by hand: python3 tools/build_proj27.py
"""
import json, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YEARS = [2026, 2025, 2024]
WH, WP = {2026: 5, 2025: 4, 2024: 3}, {2026: 3, 2025: 2, 2024: 1}
GOOD_H = {"H", "2B", "3B", "HR", "R", "RBI", "BB", "IBB", "HBP", "SB", "TB", "GSHR", "CYC", "GWRBI", "SF"}
BAD_H = {"K", "CS", "GIDP"}
GOOD_P = {"K", "W", "SV", "HD", "QS", "CG", "SHO"}
BAD_P = {"H", "ER", "R", "HR", "BB", "IBB", "HBP", "L", "BS", "WP", "TB"}


def jsobj(path, after="="):
    s = open(os.path.join(ROOT, path), encoding="utf-8").read()
    return json.loads(s[s.index(after) + len(after):].strip().rstrip(";"))


def season_files():
    out = {}
    cur = jsobj("fantasy.js", '"] = ')
    out[cur["season"]] = cur
    for y in YEARS:
        if y in out: continue
        p = f"hist/fantasy-{y}.js"
        if os.path.exists(os.path.join(ROOT, p)): out[y] = jsobj(p, '"] = ')
    return out


def ages():
    d = jsobj("data.js")
    return {(x["type"], str(x["id"])): x.get("age") for x in d["players"]}


EXTRA_P = ("QS", "RW", "RL")   # per-game categories the season line doesn't carry, counted from the game logs


def lines(F, grp):
    keys = F["hk"] if grp == "H" else F["pk"]
    src = F["hitters"] if grp == "H" else F["pitchers"]
    out = {}
    for pid, r in src.items():
        a = r if grp == "H" else r["s"]
        o = {k: (a[i] if i < len(a) and a[i] else 0) for i, k in enumerate(keys)}
        if grp == "P":
            gk = F["gk"]; ix = {k: i for i, k in enumerate(gk)}
            g = lambda row, k: (row[ix[k]] if ix[k] < len(row) and row[ix[k]] else 0)
            games = r.get("g", [])
            o["QS"] = sum(1 for row in games if g(row, "GS") and g(row, "OUTS") >= 18 and g(row, "ER") <= 3)
            o["RW"] = sum(1 for row in games if not g(row, "GS") and g(row, "W"))
            o["RL"] = sum(1 for row in games if not g(row, "GS") and g(row, "L"))
        out[pid] = o
    return out


def age_adj(age):
    if age is None: return 0.0
    return 0.006 * (29 - age) if age < 29 else -0.003 * (age - 29)


def project_hitters(S, AGE):
    hk = S[YEARS[0]]["hk"]
    L = {y: lines(S[y], "H") for y in YEARS if y in S}
    X = {y: S[y].get("xh", {}) for y in YEARS if y in S}
    # league rates per PA, every hitter pooled, each season weighted like a player's
    lg = {}
    for k in hk:
        num = sum(WH[y] * sum(o[k] for o in L[y].values()) for y in L)
        den = sum(WH[y] * sum(o["PA"] for o in L[y].values()) for y in L)
        lg[k] = num / den if den else 0
    out = {}
    for pid in L[YEARS[0]]:
        seasons = [(y, L[y][pid]) for y in L if pid in L[y] and L[y][pid]["PA"] > 0]
        if not seasons: continue
        age = AGE.get(("H", pid)); age27 = age + 1 if age is not None else None
        den = sum(WH[y] * o["PA"] for y, o in seasons) + 1200
        rate = {k: (sum(WH[y] * o[k] for y, o in seasons) + 1200 * lg[k]) / den for k in hk}
        # Statcast: H and TB halfway to expected over the same seasons
        ab = sum(WH[y] * o["AB"] for y, o in seasons)
        xs = [(y, o, X[y].get(pid)) for y, o in seasons if X[y].get(pid) and X[y][pid][0] is not None and X[y][pid][1] is not None]
        if xs and ab:
            xab = sum(WH[y] * o["AB"] for y, o, _ in xs)
            h_act = sum(WH[y] * o["H"] for y, o, _ in xs) / xab if xab else 0
            tb_act = sum(WH[y] * o["TB"] for y, o, _ in xs) / xab if xab else 0
            h_x = sum(WH[y] * o["AB"] * x[0] for y, o, x in xs) / xab if xab else 0
            tb_x = sum(WH[y] * o["AB"] * x[1] for y, o, x in xs) / xab if xab else 0
            share = xab / ab
            if h_act > 0 and tb_act > h_act:
                fh = 1 + share * 0.5 * (h_x / h_act - 1)
                ftb = 1 + share * 0.5 * (tb_x / tb_act - 1)
                h2, tb2 = rate["H"] * fh, rate["TB"] * ftb
                e, e2 = rate["TB"] - rate["H"], max(0.0, tb2 - h2)
                f = e2 / e if e > 0 else 1
                for k in ("2B", "3B", "HR"): rate[k] *= f
                rate["H"], rate["TB"] = h2, h2 + e2
        a = age_adj(age27)
        for k in hk:
            if k in GOOD_H: rate[k] *= 1 + a
            elif k in BAD_H: rate[k] *= 1 - a
        # playing time
        pa = {y: o["PA"] for y, o in seasons}; g26 = L[YEARS[0]][pid]["G"]
        t = 0.5 * pa.get(2026, 0) + 0.1 * pa.get(2025, 0) + 200
        full = sorted([v for v in pa.values() if v >= 450], reverse=True)
        if len(full) >= 2: t = max(t, 0.85 * (full[0] + full[1]) / 2)
        elif len(full) == 1 and pa.get(2026, 0) >= 450: t = max(t, 0.85 * full[0])
        if g26 >= 50 and pa.get(2026, 0) / max(1, g26) >= 3.8 and (age27 or 30) <= 28: t = max(t, 560)
        if (age27 or 0) >= 35: t *= 0.92
        t = min(700, t)
        o = {k: rate[k] * t for k in hk}; o["PA"] = t
        o["G"] = t / max(3.0, min(4.4, sum(pa.values()) / max(1, sum(L[y][pid]["G"] for y, _ in seasons))))
        out[pid] = [round(o[k], 1) for k in hk]
    return hk, out


def project_pitchers(S, AGE):
    pk = S[YEARS[0]]["pk"] + [k for k in EXTRA_P if k not in S[YEARS[0]]["pk"]]
    L = {y: lines(S[y], "P") for y in YEARS if y in S}
    X = {y: S[y].get("xp", {}) for y in YEARS if y in S}
    role_of = lambda o: "SP" if o["GS"] * 2 >= max(1, o["G"]) else "RP"
    lg = {}
    for role in ("SP", "RP"):
        lg[role] = {}
        for k in pk:
            num = sum(WP[y] * sum(o[k] for o in L[y].values() if role_of(o) == role) for y in L)
            den = sum(WP[y] * sum(o["OUTS"] for o in L[y].values() if role_of(o) == role) for y in L)
            lg[role][k] = num / den if den else 0
    out = {}
    for pid in L[YEARS[0]]:
        seasons = [(y, L[y][pid]) for y in L if pid in L[y] and L[y][pid]["OUTS"] > 0]
        if not seasons: continue
        last = L[YEARS[0]][pid]; role = role_of(last)
        age = AGE.get(("P", pid)); age27 = age + 1 if age is not None else None
        den = sum(WP[y] * o["OUTS"] for y, o in seasons) + 600
        rate = {k: (sum(WP[y] * o[k] for y, o in seasons) + 600 * lg[role][k]) / den for k in pk}
        # Statcast: ER halfway to xERA over the seasons that have it
        xs = [(y, o, X[y].get(pid)) for y, o in seasons if X[y].get(pid) and len(X[y][pid]) > 3 and X[y][pid][3] is not None]
        if xs:
            xo = sum(WP[y] * o["OUTS"] for y, o, _ in xs)
            er_x = sum(WP[y] * o["OUTS"] / 27 * x[3] for y, o, x in xs) / xo if xo else 0
            er_a = sum(WP[y] * o["ER"] for y, o, _ in xs) / xo if xo else 0
            share = xo / max(1, sum(WP[y] * o["OUTS"] for y, o in seasons))
            if er_a > 0: rate["ER"] *= 1 + share * 0.5 * (er_x / er_a - 1)
        a = age_adj(age27)
        for k in pk:
            if k in GOOD_P: rate[k] *= 1 + a
            elif k in BAD_P: rate[k] *= 1 - a
        ip = {y: o["OUTS"] / 3 for y, o in seasons}
        if role == "SP":
            t = 0.5 * ip.get(2026, 0) + 0.1 * ip.get(2025, 0) + 60
            full = sorted([v for v in ip.values() if v >= 120], reverse=True)
            if len(full) >= 2: t = max(t, 0.85 * (full[0] + full[1]) / 2)
            if last["GS"] >= 12 and (age27 or 30) <= 29: t = max(t, 140)
            t = min(200, t)
        else:
            t = min(72, 0.5 * ip.get(2026, 0) + 0.1 * ip.get(2025, 0) + 25)
        outs = t * 3
        o = {k: rate[k] * outs for k in pk}; o["OUTS"] = outs
        out[pid] = [round(o[k], 1) for k in pk]
    return pk, out


def main():
    S, AGE = season_files(), ages()
    hk, H = project_hitters(S, AGE)
    pk, P = project_pitchers(S, AGE)
    doc = {"built": datetime.date.today().isoformat(), "season": 2027,
           "note": "Marcel 5/4/3 (pitchers 3/2/1) + Statcast H/TB/ER + regular-season playing time; tools/build_proj27.py",
           "hk": hk, "pk": pk, "hitters": H, "pitchers": P}
    path = os.path.join(ROOT, "hist", "proj-2027.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.DRAFT_PROJ27 = " + json.dumps(doc, separators=(",", ":")) + ";\n")
    print(f"wrote {path}: {len(H)} hitters, {len(P)} pitchers")


if __name__ == "__main__":
    main()
