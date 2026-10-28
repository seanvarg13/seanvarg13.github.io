#!/usr/bin/env python3
"""hist/alerts.js: in-season arsenal alerts (Sean, 28 Oct 2026, item 10 of the review's picks: "in-season arsenal alerts — new pitch 5%+ in the
last 30 days, usage swing 10+, velo +1 on Movers' pitchers and the card").

From this season's arsenal day file (hist/ars-<season>.js: pitcher × day × hand × venue × pitch type, with each type's pitches and its velocity
sum) and data.js's game days: for every pitcher, his last 30 days against the season before them —

  new    a pitch type at 5%+ of his pitches in the window (20+ thrown) that was under 2% before (100+ pitches before)
  gone   a type at 5%+ before, under 1% in the window (100+ pitches in it)
  use    a type whose share moved 10+ points (20+ thrown in the window, 100+ pitches on each side)
  velo   his primary fastball (four-seam / sinker / cutter, whichever he throws most) 1.0+ mph faster or slower (30+ of it on each side)

    window.DRAFT_ALERTS = {"season": 2026, "through": "2026-09-27", "days": 30, "from": "2026-08-29",
                           "p": {"<MLB id>": {"n0": pitches before, "n1": pitches in the window, "fb": [type, velo before, velo in the window],
                                              "al": [["new", "ST", 12.4], ["gone", "CH", 6.1], ["use", "SL", 22.3, 35.0], ["velo", "FF", 95.1, 96.4]]}}}

Run by cloud_daily.py with each MLB build (a few seconds; non-fatal). Standard library only.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN = 30
FASTBALLS = ("FF", "SI", "FC")


def load_js(path, prefix_re):
    raw = open(path, encoding="utf-8").read()
    m = re.search(prefix_re, raw)
    if not m:
        raise ValueError(f"{os.path.basename(path)}: no data found")
    return json.loads(raw[m.end():].rstrip().rstrip(";"))


def main():
    head = open(os.path.join(ROOT, "data.js"), encoding="utf-8").read(400000)
    season = int(re.search(r'"season"\s*:\s*(\d{4})', head).group(1))
    through = re.search(r'"through"\s*:\s*"(\d{4}-\d\d-\d\d)"', head).group(1)
    days = json.loads(re.search(r'"days"\s*:\s*(\[[^\]]*\])', head).group(1))
    fields = json.loads(re.search(r'"arsDayFields"\s*:\s*(\[[^\]]*\])', head).group(1))
    I = {f: i for i, f in enumerate(fields)}                      # "gs" twice: the started flag is the first, the sum the second — neither is read here
    ars = load_js(os.path.join(ROOT, "hist", f"ars-{season}.js"), r'window\.DRAFT_ARS\["mlb-%d"\]\s*=\s*' % season)
    last = len(days) - 1
    cut = max(0, last - (WIN - 1))                                  # the window: the last WIN game days, by day index
    out = {}
    for key, rows in ars.items():
        if not key.startswith("P"):
            continue
        pid = key[1:]
        before, within = {}, {}                                     # type -> [pitches, velo sum]
        for r in rows:
            side = within if r[I["day"]] >= cut else before
            t = side.setdefault(r[I["pt"]], [0, 0.0])
            t[0] += r[I["n"]]; t[1] += r[I["velo"]]
        n0, n1 = sum(t[0] for t in before.values()), sum(t[0] for t in within.values())
        if not n1:
            continue
        use0 = lambda pt: 100 * before.get(pt, [0, 0])[0] / n0 if n0 else 0.0
        use1 = lambda pt: 100 * within.get(pt, [0, 0])[0] / n1
        al = []
        types = sorted(set(before) | set(within), key=lambda pt: -(within.get(pt, [0, 0])[0] + before.get(pt, [0, 0])[0]))
        for pt in types:
            w, b = within.get(pt, [0, 0]), before.get(pt, [0, 0])
            if n0 >= 100 and w[0] >= 20 and use1(pt) >= 5 and use0(pt) < 2:
                al.append(["new", pt, round(use1(pt), 1)])
            elif n0 >= 100 and n1 >= 100 and use0(pt) >= 5 and use1(pt) < 1:
                al.append(["gone", pt, round(use0(pt), 1)])
            elif n0 >= 100 and n1 >= 100 and w[0] >= 20 and abs(use1(pt) - use0(pt)) >= 10:
                al.append(["use", pt, round(use0(pt), 1), round(use1(pt), 1)])
        fb = None
        fbs = [pt for pt in FASTBALLS if pt in before or pt in within]
        if fbs:
            main_fb = max(fbs, key=lambda pt: within.get(pt, [0, 0])[0] + before.get(pt, [0, 0])[0])
            w, b = within.get(main_fb, [0, 0]), before.get(main_fb, [0, 0])
            if w[0] >= 30 and b[0] >= 30:
                v0, v1 = b[1] / b[0], w[1] / w[0]
                fb = [main_fb, round(v0, 1), round(v1, 1)]
                if abs(v1 - v0) >= 1.0:
                    al.append(["velo", main_fb, round(v0, 1), round(v1, 1)])
        out[pid] = {"n0": n0, "n1": n1, "fb": fb, "al": al}
    data = {"season": season, "through": through, "days": WIN, "from": days[cut], "p": out}
    path = os.path.join(ROOT, "hist", "alerts.js")
    body = "window.DRAFT_ALERTS = " + json.dumps(data, separators=(",", ":")) + ";\n"
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != body:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
    flagged = sum(1 for r in out.values() if r["al"])
    print(f"OK {len(out)} pitchers with pitches in the last {WIN} game days ({days[cut]} on), {flagged} with an alert -> hist/alerts.js ({len(body) / 1e3:.0f} KB)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                                         # noqa: BLE001
        print(f"!! build_alerts: {type(e).__name__}: {e}", flush=True)
        sys.exit(1)
