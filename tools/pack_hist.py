#!/usr/bin/env python3
"""Keep the published site under GitHub Pages' 1 GB (Sean, 20 Oct 2026, item 3 of the recommendations). A finished season's day and
arsenal files — hist/days-<season>.js, hist/ars-<season>.js and their minors / postseason / spring siblings, ~920 MB of the site's
1.27 GB — are stored gzipped as hist/<name>.js.gz, which app.js fetches and unzips in the browser (ensureScript). Nothing reads them
but the site, and they change only when a season is rescored.

The current season's stay plain: they're rebuilt every morning in season, and git keeps a day's change to a plain file as a small
delta where a gzipped one is a whole new blob. When data.js moves on to the next season, the first publish packs the old one.

    python3 tools/pack_hist.py [--season YYYY] [--check]

packs every plain day / arsenal file of a season before this one (data.js's, or --season) and removes it, so the build map lists one
form of each. A plain file beside a .gz is the newer one (a rescore or a patch wrote it) and replaces it — so to change a packed file,
write the plain .js and the next publish packs it. cloud_daily.restamp() runs this first, so every publish and every merge does; the
Mac's publisher packs into its deploy folder the same way. Standard library only; the bytes are deterministic (gzip level 6, mtime 0),
so packing the same content twice changes nothing.
"""
import argparse
import gzip
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r"^(?:days|ars)-(?:(?:aaa|aa|ap|a)-)?(\d{4})(?:-(?:post|spring))?\.js$")   # days-2025.js, ars-aaa-2024.js, days-2025-post.js
LEVEL = 6                                                # gzip's default: level 9 is ~5% smaller and four times slower


def season_of(root=ROOT):
    """The season data.js is building (its meta.season), or None."""
    try:
        with open(os.path.join(root, "data.js"), encoding="utf-8") as f:
            m = re.search(r'"season":\s*(\d{4})', f.read(4000))
        return int(m.group(1)) if m else None
    except OSError:
        return None


def finished(name, season):
    """True for a day / arsenal file of a season before `season`."""
    m = PAT.match(name)
    return bool(m and season and int(m.group(1)) < season)


def gz_file(src, dst):
    with open(src, "rb") as f:
        data = gzip.compress(f.read(), compresslevel=LEVEL, mtime=0)
    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dst)
    return len(data)


def pack(root=ROOT, season=None, dry=False, log=print):
    """Gzip every finished season's plain day / arsenal file under root/hist and remove the plain copy. Returns the names packed."""
    season = season or season_of(root)
    hist = os.path.join(root, "hist")
    if not season or not os.path.isdir(hist):
        return []
    done, before, after = [], 0, 0
    for n in sorted(os.listdir(hist)):
        if not finished(n, season):
            continue
        src = os.path.join(hist, n)
        before += os.path.getsize(src)
        done.append(n)
        if dry:
            continue
        after += gz_file(src, src + ".gz")
        os.remove(src)
    if done:
        log(f"pack_hist: {'would pack' if dry else 'packed'} {len(done)} file{'' if len(done) == 1 else 's'} of seasons before {season}"
            + ("" if dry else f" ({before / 1e6:.0f} MB -> {after / 1e6:.0f} MB)") + ": " + ", ".join(done[:6]) + (" …" if len(done) > 6 else ""))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, help="the current season (default: data.js's)")
    ap.add_argument("--check", action="store_true", help="say what would be packed, change nothing")
    a = ap.parse_args()
    s = a.season or season_of()
    if not s:
        sys.exit("pack_hist: no season (data.js missing?) — pass --season")
    if not pack(season=s, dry=a.check):
        print(f"pack_hist: nothing to pack (every day / arsenal file of a season before {s} is packed already)")


if __name__ == "__main__":
    main()
