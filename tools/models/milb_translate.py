"""The minors-to-MLB translation behind the card's MLB-equivalent uERA for a minor-league season.

uERA reads four rates a pitcher owns: Whiff%, Strike%, GB% and Popup%. Each runs differently in the minors (the
hitters are worse), so a minor-league line is carried up to the majors one level at a time — A to A+ to AA to AAA to
MLB, chained, since the low levels have too few straight jumps to the majors — before uERA is worked out on it.

Each step is a shift in the rate, fitted on every pitcher who faced 40+ batters at both levels in the same season,
weighted by the harmonic mean of the two BF. The plain difference (his rate up there less his rate down here) is
biased: a pitcher is promoted after a good run, some of it luck, so his lower-level rate overstates him and the drop
looks bigger than the level makes it. So the lower-level rate is first pulled toward that level's league average by
its reliability — the slope of the upper rate on the lower one, which is what a pure shift plus sampling noise gives
— and the shift is measured from there:  shift = hi − (lg_lo + r · (lo − lg_lo)).  A straight regression instead
would squash every pitcher toward average at each of four steps, and a great A-ball line would read as a plain one.

Reads hist/minors.js (build_career.py's output, which carries the rates per line), the level files for each league's
averages, and the MLB seasons (data.js, hist/mlb-*.js). Prints the table that goes in app.js as MILB_X. Nothing in the
daily job runs this; re-run it by hand when the table is stale:
    python3 tools/models/milb_translate.py
"""
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
LV = {"AAA": "AAA", "AA": "AA", "A+": "A+", "A(Adv)": "A+", "A (Adv)": "A+", "A": "A", "A(Full)": "A", "A (Full)": "A"}
FILE = {"AAA": "aaa", "AA": "aa", "A+": "ap", "A": "a", "MLB": "mlb"}
STEPS = [("A", "A+"), ("A+", "AA"), ("AA", "AAA"), ("AAA", "MLB")]
RATES = ["whf", "strk", "gb", "pu"]
MIN_BF = 40


def load(path, prefix):
    raw = path.read_text()
    return json.loads(raw[raw.index(prefix) + len(prefix):].rstrip().rstrip(";"))


def dataset(path):
    raw = path.read_text()
    return json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))


def main():
    lines = defaultdict(dict)                          # (pid, season) -> level -> (bf, {rate: v})
    league = {}                                        # (level, season) -> {rate: BF-weighted average, 40+ BF}
    files = [(lv, int(f.stem.split("-")[1]), dataset(f)) for lv, k in FILE.items()
             for f in sorted((HERE / "hist").glob(f"{k}-20*.js")) if f.stem.count("-") == 1]
    cur = load(HERE / "data.js", "window.DRAFT_DATA = ")
    files.append(("MLB", int(cur["meta"]["season"]), cur))
    for lv, season, ds in files:
        if ds.get("kind") or season < 2021:            # spring / postseason; the minors' own files start in 2021
            continue
        ps = [p for p in ds["players"] if p["type"] == "P" and (p.get("bf") or 0) >= MIN_BF]
        league[(lv, season)] = {k: sum(p["bf"] * p["m"][k] for p in ps if p["m"].get(k) is not None) /
                                   max(1, sum(p["bf"] for p in ps if p["m"].get(k) is not None)) for k in RATES}
        if lv == "MLB":
            for p in ps:
                lines[(str(p["id"]), season)]["MLB"] = (p["bf"], {k: p["m"].get(k) for k in RATES})
    for pid, rec in load(HERE / "hist" / "minors.js", "window.DRAFT_MINORS = ").items():
        bf, adv = defaultdict(int), {}
        for r in rec.get("P", []):
            lv = LV.get(r[1])
            if not lv:
                continue
            if r[2]:
                bf[(r[0], lv)] += r[17] or 0           # the clubs' BF add up …
            else:
                bf[(r[0], lv, "tot")] = r[17] or 0     # … unless the level has its own total line
            if r[-1]:
                adv[(r[0], lv)] = dict(zip(RATES, r[-1][2:6]))
        for (season, lv), a in adv.items():
            lines[(pid, season)][lv] = (bf.get((season, lv, "tot")) or bf.get((season, lv)) or 0, a)
    table, acc = {}, {k: 0.0 for k in RATES}
    shifts = {}
    for lo, hi in STEPS:
        shifts[(lo, hi)] = {}
        for k in RATES:
            pairs = []
            for (pid, season), lvs in lines.items():
                if lo in lvs and hi in lvs and (lo, season) in league:
                    (b0, a0), (b1, a1) = lvs[lo], lvs[hi]
                    if b0 >= MIN_BF and b1 >= MIN_BF and a0.get(k) is not None and a1.get(k) is not None:
                        pairs.append((2 / (1 / b0 + 1 / b1), a0[k], a1[k], league[(lo, season)][k]))
            sw = sum(w for w, *_ in pairs)
            mx, my = (sum(w * x for w, x, _, _ in pairs) / sw, sum(w * y for w, _, y, _ in pairs) / sw)
            r = sum(w * (x - mx) * (y - my) for w, x, y, _ in pairs) / sum(w * (x - mx) ** 2 for w, x, _, _ in pairs)
            shifts[(lo, hi)][k] = sum(w * (y - (lg + r * (x - lg))) for w, x, y, lg in pairs) / sw
            print(f"{lo:>3} -> {hi:<3} {k:<4} n={len(pairs):4d}  reliability {r:.2f}  raw {my - mx:+.2f}  shift {shifts[(lo, hi)][k]:+.2f}")
    for lo, hi in reversed(STEPS):
        acc = {k: acc[k] + shifts[(lo, hi)][k] for k in RATES}
        table[lo] = {k: round(v, 2) for k, v in acc.items()}
    print("MILB_X =", json.dumps(table))


if __name__ == "__main__":
    main()
