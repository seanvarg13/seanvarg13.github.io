"""Build hist/similar.js: every qualified MLB player-season 2015-now, for the card's "Similar" line across seasons.

Sean, 1 Oct 2026: "make it so it does player and year ... it doesn't have to be a player from that same year". The card matches
a player-season on style and skill (app.js `SIM`) against every season, so each season's qualifiers are ranked within their own
season here — a percentile per stat, ties at half, the way the site ranks — and written out with his hand and, for a pitcher, his
pitch mix. A few hundred KB, loaded only when a card draws its Similar line.

Qualifiers: hitters with 300+ PA, pitchers with 150+ BF (2020's 60-game season: 110 PA / 60 BF). Reads hist/mlb-YYYY.js and
data.js; a few seconds. Runs after build_data.py in the daily job (cloud_daily.py) and after a rescore.
    python3 build_similar.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "hist" / "similar.js"
# the stats behind each half of the match (app.js SIM reads them in this order); a pitcher's uERA lives in the browser, so the
# luck-neutral ERA stands in for it here
KEYS = {"H": {"style": ["air", "gb", "pu", "pull", "osw", "zsw", "whf", "k", "bb"],
              "skill": ["xwoba_dir", "ev", "brl", "hh", "ev90", "bs", "zcon"]},
        "P": {"style": ["gb", "pu", "zone", "osw", "swing", "fbv", "ext"],
              "skill": ["stuff", "whf", "strk", "kbb", "nera"]}}
LOWER = {"k", "bb", "osw", "whf", "pu"}            # hitters: lower is better (only the direction of the rank; a gap is a gap)
LOWER_P = {"nera"}


def dataset(path):
    raw = path.read_text()
    return json.loads(raw[raw.index("= {") + 2:].rstrip().rstrip(";"))


def ranks(vals, ref=None):
    """Percentile of each value among the reference values (default: the non-null ones themselves), ties at half; None stays None."""
    have = sorted(v for v in (vals if ref is None else ref) if v is not None)
    n = len(have)
    if not n:
        return [None] * len(vals)
    out = []
    for v in vals:
        if v is None:
            out.append(None)
            continue
        lo = sum(1 for x in have if x < v)
        eq = sum(1 for x in have if x == v)
        out.append(round(100 * (lo + eq / 2) / n))
    return out


def main():
    files = [(int(f.stem.split("-")[1]), f) for f in sorted((HERE / "hist").glob("mlb-20??.js"))]
    cur = dataset(HERE / "data.js")
    season = int(cur["meta"]["season"])
    files = [(y, f) for y, f in files if y != season]
    out = {"keys": {t: k["style"] + k["skill"] for t, k in KEYS.items()}, "nstyle": {t: len(k["style"]) for t, k in KEYS.items()},
           "H": [], "P": []}
    for year, src in files + [(season, None)]:
        ds = cur if src is None else dataset(src)
        short = year == 2020
        for t in ("H", "P"):
            size, floor = ("pa", 110 if short else 300) if t == "H" else ("bf", 60 if short else 150)
            # qualifiers are the matches; a player under the line (100+ PA / 50+ BF) is ranked against them too, so his own card
            # can still be matched from (Judge's 285-PA 2026) — the q flag says which is which
            low = (40 if short else 100) if t == "H" else (20 if short else 50)
            ps = [p for p in ds["players"] if p["type"] == t and (p.get(size) or 0) >= low]
            q = [(p.get(size) or 0) >= floor for p in ps]
            keys = out["keys"][t]
            cols = []
            for k in keys:
                lower = (k in LOWER) if t == "H" else (k in LOWER_P)
                v = [p["m"].get(k) for p in ps]
                v = [None if x is None else (-x if lower else x) for x in v]
                cols.append(ranks(v, [x for x, ok in zip(v, q) if ok]))
            for i, p in enumerate(ps):
                ctx = p.get("ctx") or {}
                hand = (p.get("throws") if t == "P" else p.get("bats")) or ""
                if t == "P":                                   # a starter and a reliever pitch differently: the role rides with the hand
                    hand += "-SP" if (ctx.get("GS") or 0) * 2 >= (ctx.get("G") or 1) else "-RP"
                row = [p["id"], year, p["name"], p.get("team") or "", hand, 1 if q[i] else 0]
                if t == "P":
                    ars = (p.get("ctx") or {}).get("arsenal") or []
                    tot = sum(r[1] or 0 for r in ars)
                    row.append({r[0]: round(100 * (r[1] or 0) / tot) for r in ars if tot and 100 * (r[1] or 0) / tot >= 3})
                row.append([-1 if c[i] is None else c[i] for c in cols])
                out[t].append(row)
    OUT.write_text("window.DRAFT_SIMILAR = " + json.dumps(out, separators=(",", ":"), ensure_ascii=False) + ";\n")
    print(f"hist/similar.js: {len(out['H'])} hitter-seasons, {len(out['P'])} pitcher-seasons, {OUT.stat().st_size / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
