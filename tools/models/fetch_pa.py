"""Every regular-season plate appearance 2015-now (the pitch that ended it), the columns the directional models train on,
as pa_all.parquet in MODEL_DIR — what the Mac keeps in model-workspace/, rebuilt from Statcast for the cloud retrain
(.github/workflows/retrain.yml). One parquet per season is kept beside it, so a rerun only fetches what's missing; the
current season is always fetched again (it grows every day).
"""
import os, sys, time, datetime as dt, pandas as pd, pybaseball as pb
pb.cache.enable()
OUT = os.environ.get("MODEL_DIR", "/Users/seanvargas/Desktop/Fantasy Baseball/model-workspace/")
COLS = ["game_date", "game_year", "game_pk", "batter", "pitcher", "stand", "p_throws", "type", "events", "bb_type",
        "launch_speed", "launch_angle", "hc_x", "hc_y", "woba_value", "woba_denom", "game_type"]
def pull(a, b, tries=5):
    """Savant now and then answers with an error page instead of a CSV (30 Sep 2026: the first cloud retrain died on one in
    August 2021), so every request is tried again after a growing pause, one at a time on the last tries."""
    for k in range(tries):
        try:
            return pb.statcast(start_dt=str(a.date()), end_dt=str(b.date()), verbose=False, parallel=k < 2)
        except Exception as ex:                                   # noqa: BLE001 — a bad page, a timeout: wait and ask again
            print(f"  {a.date()}..{b.date()}: {type(ex).__name__}, retry {k + 1}", flush=True)
            time.sleep(15 * (k + 1))
    raise RuntimeError(f"Savant kept failing for {a.date()}..{b.date()}")
def month(s, e):
    try:
        return pull(s, e)
    except RuntimeError:                                          # a month that won't come whole: a week at a time
        parts = [pull(a, min(a + pd.Timedelta(days=6), e)) for a in pd.date_range(s, e, freq="7D")]
        parts = [p for p in parts if p is not None and len(p)]
        return pd.concat(parts, ignore_index=True) if parts else None

last = int(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today().year
parts = []
for y in range(2015, last + 1):
    f = os.path.join(OUT, f"pa_{y}.parquet")
    if not os.path.exists(f) or y == last:
        chunks = []
        for s in pd.date_range(f"{y}-03-01", f"{y}-11-30", freq="MS"):
            e = min(s + pd.offsets.MonthEnd(0), pd.Timestamp(dt.date.today()))
            if s > e: continue
            x = month(s, e)
            if x is None or not len(x): continue
            x = x[x["events"].notna() & x["game_type"].eq("R")]
            chunks.append(x[[c for c in COLS if c in x.columns]])
            print(y, s.date(), len(x), flush=True)
        pd.concat(chunks, ignore_index=True).drop_duplicates().to_parquet(f)
    d = pd.read_parquet(f); parts.append(d); print(y, len(d), "PA", flush=True)
pd.concat(parts, ignore_index=True).to_parquet(os.path.join(OUT, "pa_all.parquet"))
print("pa_all.parquet", sum(map(len, parts)), "PA", flush=True)
