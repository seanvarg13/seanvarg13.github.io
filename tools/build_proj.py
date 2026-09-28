#!/usr/bin/env python3
"""
build_proj.py — next season's projected lines for every hitter and pitcher (Sean, 28 Sep 2026: a projections page for
the 2027 draft).

Output: proj.js next to index.html (window.DRAFT_PROJ). Counting stats only, every category the fantasy presets can
score, so the page puts points on them with whatever preset is chosen and nothing here needs a rebuild when the scoring
changes.

How (a Marcel-style projection, tuned and checked on past seasons — see the numbers below):
  * each rate is per plate appearance (hitters) or per batter faced (pitchers), the last three seasons weighted 5 / 4 / 3,
    with some league-average playing time added so a thin record leans on the league (hitters 1800 PA, pitchers 1000 BF
    for the skill rates, 60 BF for the role stats — wins, saves, holds, starts — which follow the role, not the pitcher);
  * hitters' age: +0.6% a year under 29, −0.3% a year over (strikeouts the other way);
  * the process stats pull the result: a quarter of hits and total bases from the directional xBA / xSLG, and runs, RBI
    and home runs moved by the square root of his xwOBA / wOBA; pitchers' strikeouts 30% uK%, walks 50% uBB%, earned runs
    75% luck-neutral ERA;
  * playing time from a least-squares fit: last season's workload, the most in three, age, starter share and how good he
    is (better players keep their jobs); players who didn't play the next year included as zeros.
Checked on 2025 and 2026 from fits on 2017-2024: points per PA error .106 → .093 (last season alone vs this), r .50 →
.54; pitchers' points per batter .194 → .180, r .65 → .68; playing time beats Marcel's 0.5·PA + 0.1·PA + 200.

Inputs: hist/fantasy-lines.js (official lines, 2015 on), fantasy.js (this season's), data.js and hist/mlb-YYYY.js (the
process stats). Run after build_fantasy.py; cheap (a few seconds).
"""
import datetime as dt, json, math, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE if (HERE / "data.js").exists() else HERE.parent       # draft-site/ on the Mac, the repo root in the cloud

def js_obj(path):
    """the object the file's last `window.X = {…}` or `window.X["key"] = {…}` assigns"""
    s = (ROOT / path).read_text(); k = s.rfind("] = {")
    k = k if k >= 0 else s.index(" = {")
    return json.loads(s[s.index("{", k):].rstrip().rstrip(";"))

UKF = dict(whf=0.898, strk=0.887, zone=0.051, osw=-0.097, swing=-0.523, zcon=-0.160)     # app.js UKF / UBB, league-relative
UBB = dict(strk=-1.008, zone=0.214, osw=0.093, swing=-0.045, zcon=-0.104, whf=0.062)
W3 = (5, 4, 3)
H_R, P_R, P_ROLE_R = 1800, 1000, 60
H_ROLE = set()
P_ROLE = {"W", "L", "SV", "HD", "GS", "QS", "G", "BS", "SVO", "GF", "CG", "SHO", "NH", "PG", "RW", "RL"}
# playing time (least squares on 2016-2023 → next season, 0 if he didn't play; checked on 2025-26): the last seasons'
# workload, the most he's had in three, age, starter share, and how good he is (ESPN-standard points per PA / BF at the
# projected rates) — better players keep their jobs. Hitters: error 170 → 162 PA against the two-season fit.
PA_FIT = dict(c=133.796, pa0=0.962, pa1=0.026, pa2=0.002, peak=0.05, g0=-1.856, age=-11.812, q=694.059)
BF_FIT = dict(c=-47.352, bf0=0.488, bf1=-0.013, peak=0.101, age30=-10.501, gs=120.695, q=158.484)

def main():
    D = js_obj("data.js")
    season = int(D["meta"]["season"])
    years = [season - 2, season - 1, season]
    L = js_obj("hist/fantasy-lines.js")
    hk, pk = L["hk"], L["pk"]
    F = js_obj("fantasy.js")
    lines = {}                                                       # (type, id, year) -> dict
    for y in years:
        if y == season:
            fh, fp = F["hitters"], F["pitchers"]
            for pid, a in fh.items(): lines[("H", pid, y)] = dict(zip(F["hk"], a))
            for pid, r in fp.items():
                o = dict(zip(F["pk"], r["s"]))
                qs = 0
                for g in r["g"]:
                    x = dict(zip(F["gk"], g))
                    if x.get("GS") and (x.get("OUTS") or 0) >= 18 and (x.get("ER") or 0) <= 3: qs += 1
                o["QS"] = qs; lines[("P", pid, y)] = o
        elif str(y) in L["years"]:
            Y = L["years"][str(y)]
            for pid, a in Y["hitters"].items(): lines[("H", pid, y)] = dict(zip(hk, a))
            for pid, a in Y["pitchers"].items(): lines[("P", pid, y)] = dict(zip(pk, a))
    # process stats and names per season
    proc = {}
    for y in years:
        ds = D if y == season else js_obj(f"hist/mlb-{y}.js")
        for p in ds["players"]:
            proc[(p["type"], str(p["id"]), y)] = p
    def lg_means(y, typ, keys, wkey):
        s, n = {}, {}
        for (t, pid, yy), p in proc.items():
            if t != typ or yy != y or (p.get(wkey) or 0) < 20: continue
            for k in keys:
                v = p["m"].get(k)
                if v is None: continue
                s[k] = s.get(k, 0) + v * p[wkey]; n[k] = n.get(k, 0) + p[wkey]
        return {k: s[k] / n[k] for k in s}
    for (t, pid, y), o in lines.items():                            # process-based lines
        p = proc.get((t, pid, y)); m = p["m"] if p else {}
        if t == "H":
            ab = o.get("AB") or 0
            o["xH"] = m["dxba"] * ab if m.get("dxba") is not None else o.get("H", 0)
            o["xTB"] = m["dxslg"] * ab if m.get("dxslg") is not None else o.get("TB", 0)
            o["_xwr"] = min(2, max(0.5, m["xwd"] / m["woba"])) if m.get("xwd") and m.get("woba") else (min(2, max(0.5, m["xwoba"] / m["woba"])) if m.get("xwoba") and m.get("woba") else 1)
        else:
            bf, outs = o.get("BF") or 0, o.get("OUTS") or 0
            Lg = LG.setdefault(y, lg_means(y, "P", set(UKF) | set(UBB) | {"k", "bb"}, "bf"))
            if all(m.get(k) is not None for k in UKF) and "k" in Lg:
                uk = Lg["k"] + 0.061 + sum(w * (m[k] - Lg[k]) for k, w in UKF.items())
                ub = Lg["bb"] - 0.068 + sum(w * (m[k] - Lg[k]) for k, w in UBB.items())
                o["xK"], o["xBB"] = uk / 100 * bf, ub / 100 * bf
            else: o["xK"], o["xBB"] = o.get("K", 0), o.get("BB", 0)
            o["xER"] = m["nera"] / 27 * outs if m.get("nera") is not None else o.get("ER", 0)
    # league rates per season
    def lg_rate(t, y, keys, den):
        tot = {k: 0.0 for k in keys}; d = 0.0
        for (tt, pid, yy), o in lines.items():
            if tt != t or yy != y: continue
            d += o.get(den) or 0
            for k in keys: tot[k] += o.get(k) or 0
        return {k: tot[k] / d for k in keys} if d else {}
    HC = [k for k in hk if k not in ("G", "PA")] + ["xH", "xTB"]
    PC = [k for k in pk if k not in ("BF",)] + ["xK", "xBB", "xER"]
    lgH = lg_rate("H", season, HC, "PA"); lgP = lg_rate("P", season, PC, "BF")
    out_h, out_p = {}, {}
    ids = {(t, pid) for (t, pid, y) in lines if y >= season - 1}
    for t, pid in sorted(ids):
        recs = [lines.get((t, pid, season - k)) for k in range(3)]
        p0 = proc.get((t, pid, season)) or proc.get((t, pid, season - 1))
        if not p0: continue
        age = (p0.get("age") or 28) + (1 if (t, pid, season) in proc else 2)
        if t == "H":
            den = sum(w * (r.get("PA") or 0) for w, r in zip(W3, recs) if r)
            if not den: continue
            rate = {k: (sum(w * (r.get(k) or 0) for w, r in zip(W3, recs) if r) + H_R * lgH[k]) / (den + H_R) for k in HC}
            f = 1 + (0.006 * (29 - age) if age < 29 else -0.003 * (age - 29))
            for k in ("H", "2B", "3B", "HR", "R", "RBI", "BB", "SB", "TB", "xH", "xTB", "GSHR", "GWRBI"): rate[k] = rate.get(k, 0) * f
            rate["K"] /= f
            rate["H"] = 0.75 * rate["H"] + 0.25 * rate["xH"]; rate["TB"] = 0.75 * rate["TB"] + 0.25 * rate["xTB"]
            xw = sum(w * (r.get("PA") or 0) * r.get("_xwr", 1) for w, r in zip(W3, recs) if r) / den
            for k in ("R", "RBI", "HR"): rate[k] *= math.sqrt(xw)
            r0, r1, r2 = recs
            g = lambda r, k: (r or {}).get(k, 0) or 0
            q = rate["TB"] + rate["R"] + rate["RBI"] + rate["SB"] + rate["BB"] - rate["K"]
            f_ = PA_FIT
            pa = max(0, f_["c"] + f_["pa0"] * g(r0, "PA") + f_["pa1"] * g(r1, "PA") + f_["pa2"] * g(r2, "PA") + f_["peak"] * max(g(r, "PA") for r in recs)
                     + f_["g0"] * g(r0, "G") + f_["age"] * (age - 1) + f_["q"] * q)
            if not r0: pa *= 0.6                                    # missed this season: less of a claim on a job
            pa = min(pa, 700)
            line = {k: round(rate[k] * pa, 1) for k in HC if not k.startswith("x")}
            line["PA"] = round(pa); line["G"] = round(min(162, pa / 4.1))
            out_h[pid] = {"n": p0["name"], "t": p0.get("team", ""), "pos": p0.get("pos", ""), "age": age, "l": line}
        else:
            den = sum(w * (r.get("BF") or 0) for w, r in zip(W3, recs) if r)
            if not den: continue
            rate = {k: (sum(w * (r.get(k) or 0) for w, r in zip(W3, recs) if r) + (P_ROLE_R if k in P_ROLE else P_R) * lgP[k]) / (den + (P_ROLE_R if k in P_ROLE else P_R)) for k in PC}
            rate["K"] = 0.7 * rate["K"] + 0.3 * rate["xK"]; rate["BB"] = 0.5 * rate["BB"] + 0.5 * rate["xBB"]; rate["ER"] = 0.25 * rate["ER"] + 0.75 * rate["xER"]
            r0, r1 = recs[0], recs[1]; last = r0 or r1
            gs = (last.get("GS") or 0) / max(1, last.get("G") or 1)
            g = lambda r, k: (r or {}).get(k, 0) or 0
            q = rate["OUTS"] + 2 * rate["W"] - 2 * rate["L"] + 2 * rate["HD"] + 5 * rate["SV"] - 2 * rate["ER"] - rate["H"] + rate["K"] - rate["BB"]
            f_ = BF_FIT
            bf = max(0, f_["c"] + f_["bf0"] * g(r0, "BF") + f_["bf1"] * g(r1, "BF") + f_["peak"] * max(g(r, "BF") for r in recs)
                     + f_["age30"] * max(0, age - 30) + f_["gs"] * gs + f_["q"] * q)
            if not r0: bf *= 0.6
            bf = min(bf, 820)                                       # about 200 innings
            line = {k: round(rate[k] * bf, 1) for k in PC if not k.startswith("x")}
            line["BF"] = round(bf)
            out_p[pid] = {"n": p0["name"], "t": p0.get("team", ""), "pos": p0.get("pos", "") or p0.get("primary", ""), "age": age, "l": line}
    meta = {"season": season + 1, "from": years, "built": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            "note": "Three seasons weighted 5/4/3, regressed to the league, age-adjusted, pulled toward the process stats (xBA / xSLG / xwOBA; uK% / uBB% / luck-neutral ERA); playing time from the last two seasons."}
    (ROOT / "proj.js").write_text("window.DRAFT_PROJ = " + json.dumps({"meta": meta, "hitters": out_h, "pitchers": out_p}, separators=(",", ":")) + ";\n")
    print(f"proj.js: {len(out_h)} hitters, {len(out_p)} pitchers for {season + 1}")

LG = {}
if __name__ == "__main__":
    main()
