#!/usr/bin/env python3
"""The career files in buckets, so a player's page downloads his record and not everyone's (Sean, 28 Oct 2026, from the review: item 5).

hist/career.js (every MLB player's season lines, ~4.8 MB), hist/career-bb.js (every hitter's Statcast seasons and every pitcher's nERA /
SIERA / … seasons, ~2.2 MB) and hist/minors.js (every minor-league line, ~15 MB) are each cut into buckets by MLB id:

  hist/c/<id % 128>.js   window.DRAFT_CAREER_C["<b>"] = {keys, pkeys, lg, p: {id: record}, bb: {id: {season: [...]}}, pp: {id: {season: [...]}}}
  hist/m/<id % 128>.js   window.DRAFT_MINORS_C["<b>"] = {id: record}

A player's page asks for his two buckets (~20 KB and ~30 KB gzipped) instead of the three whole files (~5 MB gzipped). The league-wide
reads — the season table's heat pools and league leaders — come from hist/lg/<season>.js (tools/build_lg.cjs, the site's own code run
headless). The whole files are still written and still read by that builder, by the scratch scripts and by anything else that wants them.

Every bucket is written even when it's empty, so a page never asks for a file that isn't there. Run by build_career.py at the end of
main() and season_bb(); or alone:  python3 tools/shard_career.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C_BUCKETS, M_BUCKETS = 128, 128


def load_js(path, prefix):
    raw = open(path, encoding="utf-8").read()
    i = raw.index(prefix) + len(prefix)
    return json.loads(raw[i:].rstrip().rstrip(";"))


def dump(o):
    return json.dumps(o, separators=(",", ":"), ensure_ascii=False)


def write_buckets(folder, var, buckets, n):
    os.makedirs(folder, exist_ok=True)
    for b in range(n):
        path = os.path.join(folder, f"{b}.js")
        body = f"window.{var}=window.{var}||{{}};window.{var}[{json.dumps(str(b))}]={dump(buckets.get(b, {}))};\n"
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if old != body:                                        # an unchanged bucket keeps its mtime, so a publish lists only what moved
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)


def shard(root=HERE, log=print):
    hist = os.path.join(root, "hist")
    career = load_js(os.path.join(hist, "career.js"), "window.DRAFT_CAREER = ")
    bbp = os.path.join(hist, "career-bb.js")
    bb = load_js(bbp, "window.DRAFT_CAREER_BB = ") if os.path.exists(bbp) else {"keys": [], "p": {}, "pkeys": [], "pp": {}, "lg": {}}
    buckets = {}
    for b in range(C_BUCKETS):
        buckets[b] = {"keys": bb.get("keys", []), "pkeys": bb.get("pkeys", []), "lg": bb.get("lg", {}), "p": {}, "bb": {}, "pp": {}}
    for pid, rec in career.items():
        buckets[int(pid) % C_BUCKETS]["p"][pid] = rec
    for pid, rows in (bb.get("p") or {}).items():
        buckets[int(pid) % C_BUCKETS]["bb"][pid] = rows
    for pid, rows in (bb.get("pp") or {}).items():
        buckets[int(pid) % C_BUCKETS]["pp"][pid] = rows
    write_buckets(os.path.join(hist, "c"), "DRAFT_CAREER_C", buckets, C_BUCKETS)
    mp = os.path.join(hist, "minors.js")
    mbuckets = {b: {} for b in range(M_BUCKETS)}
    nm = 0
    if os.path.exists(mp):
        for pid, rec in load_js(mp, "window.DRAFT_MINORS = ").items():
            mbuckets[int(pid) % M_BUCKETS][pid] = rec; nm += 1
    write_buckets(os.path.join(hist, "m"), "DRAFT_MINORS_C", mbuckets, M_BUCKETS)
    sizes = sorted(os.path.getsize(os.path.join(hist, "c", f"{b}.js")) for b in range(C_BUCKETS))
    log(f"OK {len(career)} career records in hist/c/ ({C_BUCKETS} buckets, {sizes[0] / 1e3:.0f}-{sizes[-1] / 1e3:.0f} KB), "
        f"{nm} minors records in hist/m/ ({M_BUCKETS} buckets)")


if __name__ == "__main__":
    shard(sys.argv[1] if len(sys.argv) > 1 else HERE)
