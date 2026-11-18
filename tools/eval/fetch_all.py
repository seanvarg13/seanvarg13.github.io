"""Every regular-season pitch 2015-2026 from Baseball Savant's statcast_search CSV, one slim parquet per day.
Run: python3 fetch_all.py <outdir>. Re-runnable: days already saved are skipped."""
import subprocess, io, sys, os, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, numpy as np
OUT = sys.argv[1]
SPAN = {y: (f"{y}-03-15", f"{y}-10-06") for y in range(2015, 2027)}
SPAN[2020] = ("2020-07-20", "2020-09-30")
F32 = ["release_speed","release_pos_x","release_pos_z","release_extension","release_spin_rate","spin_axis","pfx_x","pfx_z",
       "plate_x","plate_z","vx0","vy0","vz0","ax","ay","az","sz_top","sz_bot","arm_angle","hc_x","hc_y","launch_speed",
       "launch_angle","hit_distance_sc","estimated_woba_using_speedangle","estimated_ba_using_speedangle",
       "estimated_slg_using_speedangle","woba_value","woba_denom","babip_value","iso_value","delta_run_exp",
       "delta_pitcher_run_exp","bat_speed","swing_length","attack_angle","attack_direction","swing_path_tilt"]
I32 = ["game_pk","at_bat_number","pitch_number","batter","pitcher","inning","outs_when_up","balls","strikes","zone",
       "fielder_2","hit_location","launch_speed_angle","bat_score","post_bat_score","n_thruorder_pitcher","age_bat","age_pit"]
STR = ["game_date","stand","p_throws","home_team","away_team","inning_topbot","pitch_type","type","description","events",
       "bb_type","if_fielding_alignment","of_fielding_alignment","game_type"]
RUN = ["on_1b","on_2b","on_3b"]
def day(d):
    f = f"{OUT}/{d}.parquet"
    if os.path.exists(f): return
    url = ("https://baseballsavant.mlb.com/statcast_search/csv?all=true&hfGT=R%7C"
           f"&game_date_gt={d}&game_date_lt={d}&type=details")
    for t in range(5):
        try:
            raw = subprocess.run(["curl", "-sSf", "--max-time", "240", url], capture_output=True, check=True).stdout
            break
        except Exception:
            time.sleep(6 * (t + 1))
    else:
        print("FAIL", d, flush=True); return
    if len(raw) < 1000:
        pd.DataFrame().to_parquet(f); return
    x = pd.read_csv(io.BytesIO(raw), low_memory=False)
    x.columns = [c.lstrip("﻿") for c in x.columns]
    x = x[x["game_type"] == "R"]
    out = pd.DataFrame(index=x.index)
    for c in F32:
        out[c] = pd.to_numeric(x[c], errors="coerce").astype("float32") if c in x else np.float32(np.nan)
    for c in I32:
        out[c] = pd.to_numeric(x[c], errors="coerce").astype("Int32") if c in x else pd.array([pd.NA] * len(x), dtype="Int32")
    for c in STR:
        out[c] = x[c].astype("string") if c in x else pd.array([pd.NA] * len(x), dtype="string")
    for c in RUN:
        out[c] = x[c].notna() if c in x else False
    out.reset_index(drop=True).to_parquet(f, compression="zstd")
days = []
for y, (a, b) in SPAN.items():
    d = dt.date.fromisoformat(a); e = dt.date.fromisoformat(b)
    while d <= e: days.append(d.isoformat()); d += dt.timedelta(days=1)
with ThreadPoolExecutor(8) as ex: list(ex.map(day, days))
print("DONE", len(days), flush=True)
