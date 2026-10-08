#!/usr/bin/env python3
"""
build_trends.py — league-wide averages by season, for the League Trends page (Sean, 29 Sep 2026: "a page that has league
wide trends by year ... to see how the landscapes change").

Output: hist/trends.js (window.DRAFT_TRENDS), a few KB. Every MLB regular season the site has: 2015-2025 from hist/mlb-YYYY.js,
the current one from data.js + days.js.

Hitting: exact league totals — every hitter's raw counts summed (the per-player × hand × venue rows of a past season, the per-
game rows of this one), then turned into rates, so a league rate is pitches / swings / batted balls pooled, not an average of
player averages. Plate discipline, batted-ball mix, quality of contact (EV90 from every tracked batted ball) and results.

Pitching: by pitch type, from every pitcher's arsenal table (ctx.arsenal): usage share, and velo / IVB / HB / spin / xWhiff
weighted by pitches, Whiff% by swings, GB% by balls in play. Stuff+ isn't here on purpose — it's graded against that season's
own pitch-type averages, so the league's is 100 every year by construction. Sweepers (ST) are only split out of sliders from
2023 on; before that they sit in SL.
"""
import json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
if not (ROOT / "data.js").exists() and (ROOT.parent / "data.js").exists():   # run from tools/ in the repo
    ROOT = ROOT.parent
HIST = ROOT / "hist"
TYPES = ["FF", "SI", "FC", "SL", "ST", "CU", "KC", "SV", "CH", "FS"]           # the pitch types worth a column


def load_js(path):
    s = path.read_text()
    i = s.index("= {") + 2 if "DRAFT_HIST[" in s else s.index("{")
    return json.loads(s[i:s.rindex("}") + 1])


def hitting(rows, F, air_no_pu):
    """rows: lists in HITTER_DAY order (a past season's split rows, or this season's day rows)"""
    I = {k: i for i, k in enumerate(F)}
    T, evs = {}, []
    for r in rows:
        for k, i in I.items():
            if i >= len(r) or k in ("day", "hand", "home"):
                continue
            v = r[i]
            if k in ("evs", "evbk"):   # the day rows' two list fields: exit velocities and their Mix buckets
                if isinstance(v, list):
                    evs.extend(v)
                continue
            if isinstance(v, (int, float)):
                T[k] = T.get(k, 0) + v
    g = lambda k: T.get(k, 0)
    rate = lambda a, b: round(100 * a / b, 1) if b else None
    r3 = lambda a, b: round(a / b, 3) if b else None
    bden = g("bbt") or g("bbe")            # batted balls with a type (every ball in play); older files: tracked ones
    bip = g("bip") or g("bbe")
    air = g("air") if air_no_pu else g("air") - g("puh")
    evs.sort()
    out = {
        "PA": int(g("pa")), "K%": rate(g("k"), g("pa")), "BB%": rate(g("bb"), g("pa")), "HR%": rate(g("hr"), g("pa")) if "hr" in I else None,
        "Swing%": rate(g("sw"), g("pit")), "Z-Swing%": rate(g("zsw"), g("zpit")), "O-Swing%": rate(g("osw"), g("opit")),
        "Z-Contact%": rate(g("zcon"), g("zsw")), "O-Contact%": rate(g("ocon"), g("osw")), "Contact%": rate(g("sw") - g("whf"), g("sw")),
        "Whiff%": rate(g("whf"), g("sw")), "Zone%": rate(g("zpit"), g("pit")), "Strike%": rate(g("strk"), g("pit")),
        "GB%": rate(g("gbh"), bden), "LD%": rate(g("ld"), bden), "FB%": rate(air - g("ld"), bden), "PU%": rate(g("puh"), bden),
        "Pull%": rate(g("pulln"), bden) if "pulln" in I else None, "Oppo%": rate(g("oppn"), bden) if "oppn" in I else None,
        "Pull Air%": rate(g("pullair"), bden),
        "Avg EV": round(g("evsum") / g("evn"), 1) if g("evn") else (round(g("evsum") / g("bbe"), 1) if g("bbe") else None),
        "EV90": round(evs[int(0.9 * (len(evs) - 1))], 1) if evs else None,
        "Hard-Hit%": rate(g("hh"), bip), "Barrel%": rate(g("brl"), bip), "Sweet-Spot%": rate(g("ss"), bip),
        "Bat Speed": round(g("bssum") / g("bsn"), 1) if g("bsn") else None,
        "AVG": r3(g("h"), g("ab")) if "h" in I else None, "SLG": r3(g("tb"), g("ab")) if "tb" in I else None,
        "wOBA": r3(g("wnum"), g("wden")),
        "BABIP": r3(g("h") - g("hr"), bip - g("hr")) if "h" in I and "hr" in I and bip else None,
    }
    return out


def pitching(players, F):
    I = {k: i for i, k in enumerate(F)}
    S = {}
    for p in players:
        a = p.get("type") == "P" and (p.get("ctx") or {}).get("arsenal")
        if not a:
            continue
        for r in a:
            t = r[I["pt"]]
            if t not in TYPES:
                t = None
            n = r[I["n"]] or 0
            for key in ([t] if t else []) + ["ALL"]:
                s = S.setdefault(key, {"n": 0})
                s["n"] += n
                for k, w in (("velo", n), ("ivb", n), ("hb", n), ("spin", n), ("xwhf", n)):
                    v = r[I[k]] if k in I else None
                    if v is not None and w:
                        s[k + "_s"] = s.get(k + "_s", 0) + v * w; s[k + "_w"] = s.get(k + "_w", 0) + w
                sw, bip = r[I["sw"]] or 0, r[I["bip"]] or 0
                if r[I["whf"]] is not None and sw:
                    s["whf_s"] = s.get("whf_s", 0) + r[I["whf"]] * sw; s["whf_w"] = s.get("whf_w", 0) + sw
                if r[I["gb"]] is not None and bip:
                    s["gb_s"] = s.get("gb_s", 0) + r[I["gb"]] * bip; s["gb_w"] = s.get("gb_w", 0) + bip
    tot = S.get("ALL", {}).get("n", 0)
    out = {}
    for t, s in S.items():
        m = lambda k, d=1: round(s[k + "_s"] / s[k + "_w"], d) if s.get(k + "_w") else None
        out[t] = {"use": round(100 * s["n"] / tot, 1) if tot and t != "ALL" else None, "n": s["n"],
                  "velo": m("velo"), "ivb": m("ivb"), "hb": m("hb"), "spin": m("spin", 0), "whf": m("whf"), "xwhf": m("xwhf"), "gb": m("gb")}
    return out


def main():
    years = {}
    cur = load_js(ROOT / "data.js")
    meta = cur["meta"]
    FH, FA = meta["dayFields"]["H"], meta.get("arsenalFields")
    for f in sorted(HIST.glob("mlb-*.js")):
        m = re.fullmatch(r"mlb-(\d{4})\.js", f.name)
        if not m or int(m.group(1)) >= meta["season"]:
            continue
        d = load_js(f)
        rows = [r for k, rs in (d.get("rows") or {}).items() if k.startswith("H") for r in rs]
        if not rows:
            continue
        # a past season's rows start player × hand × venue, then the same fields as the current season's day rows
        years[int(m.group(1))] = {"H": hitting(rows, FH, d.get("airNoPU")), "T": pitching(d["players"], FA) if FA else {},
                                  "lgERA": (d.get("consts") or {}).get("lgERA")}
    days = ROOT / "days.js"
    if days.exists():
        dd = load_js(days)
        rows = [r for k, rs in dd.items() if k.startswith("H") for r in rs]
        years[meta["season"]] = {"H": hitting(rows, FH, cur["meta"].get("airNoPU", True) if "airNoPU" in cur["meta"] else True),
                                 "T": pitching(cur["players"], FA) if FA else {}, "lgERA": (meta.get("consts") or {}).get("lgERA")}
    out = {"built": meta.get("built"), "through": meta.get("through"), "season": meta["season"], "types": TYPES,
           "years": {str(y): years[y] for y in sorted(years)}}
    (HIST / "trends.js").write_text("window.DRAFT_TRENDS = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print(f"hist/trends.js: {len(years)} seasons ({min(years)}-{max(years)})")


if __name__ == "__main__":
    main()
