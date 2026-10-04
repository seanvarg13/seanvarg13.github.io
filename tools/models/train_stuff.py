#!/usr/bin/env python3
"""The fixed Stuff+ models (Sean, 3 Oct 2026: "base it off all prior years ... retrained at the end of the season").

Trains build_data.py's ten models — whiff per swing, whiff per swing with location, batted-ball type on contact (with and
without location), foul on contact (without location, with it, and with the batter's swing too), damage (wOBA) on a ball in play, and the command pair (swing, called strike | taken) — on every regular season from 2020 (the first with spin axis) through THROUGH
(default: the last finished season — this year's if it's November or later, else last year's), and saves them as
MODEL_DIR/stuff_models.joblib, which the Train Stuff+ models workflow puts on the "models" release and every daily build
downloads. Without that file the build trains on the season plus the two before, as it did until 3 Oct 2026.

Tested before switching (3 Oct 2026): six seasons grade the next season as well as the last two (same-season r with
Whiff% / GB% / PU% .760 / .802 / .657 vs .771 / .798 / .647; next-season identical) and move pitchers less year to year
(Stuff+ r .861 vs .847). The location model lifts the same-season fit with Whiff% from .73-.78 to .86-.89.

    MODEL_DIR=../model-workspace THROUGH=2025 python3 tools/models/train_stuff.py
"""
import os, sys, datetime as dt, json, pathlib
import pandas as pd, joblib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_data as bd  # noqa: E402

FIRST = 2020


def main():
    out_dir = pathlib.Path(os.environ.get("MODEL_DIR") or (HERE.parent.parent.parent / "model-workspace")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today()
    through = int(os.environ.get("THROUGH") or (today.year if today.month >= 11 else today.year - 1))
    years = list(range(FIRST, through + 1))
    bd.log(f"stuff models: training on {years[0]}-{years[-1]}")
    parts = []
    for y in years:
        x = bd.load_prior_season(y)
        bd.log(f"  {y}: {len(x):,} pitches")
        if len(x):
            parts.append(x)
    if not parts:
        bd.log("no data"); sys.exit(1)
    train = pd.concat(parts, ignore_index=True); del parts
    M = bd.train_stuff_models(train)
    if not M:
        bd.log("training failed"); sys.exit(1)
    M["trained"].update({"seasons": f"{years[0]}-{years[-1]}", "by": os.environ.get("TRAINED_BY", "hand"),
                         "python": ".".join(map(str, sys.version_info[:2]))})
    path = out_dir / "stuff_models.joblib"
    joblib.dump(M, path, compress=3)
    bd.log(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB): {json.dumps(M['trained'])}")


if __name__ == "__main__":
    main()
