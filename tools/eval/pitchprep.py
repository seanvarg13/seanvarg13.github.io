"""Per-pitch frame for the pitching models: physical traits (lefties mirrored), location, count, and a denoised target —
count-based expected value in wOBA units (balls in play valued by Savant's per-ball estimate, not the result)."""
import numpy as np, pandas as pd
S = "/home/user/statcast/season"
FB = ("FF", "SI", "FC")
GRP = {"FF": "FB", "SI": "FB", "FC": "CT", "SL": "BR", "ST": "BR", "SV": "BR", "CU": "BR", "KC": "BR", "CS": "BR", "CH": "OS", "FS": "OS", "FO": "OS", "SC": "OS", "KN": "OS"}
def frame(y):
    x = pd.read_parquet(f"{S}/{y}.parquet")
    x = x[x.pitch_type.notna() & x.release_speed.notna() & x.pfx_x.notna() & x.balls.notna()].copy()
    lefty = x.p_throws.eq("L"); sgn = np.where(lefty, -1.0, 1.0)
    x["hb"] = x.pfx_x * sgn * 12; x["ivb"] = x.pfx_z * 12; x["relx"] = x.release_pos_x * sgn
    vyf = -np.sqrt(np.maximum(x.vy0 ** 2 - 2 * x.ay * (50 - 17 / 12), 0)); t = (vyf - x.vy0) / x.ay
    x["vaa"] = -np.degrees(np.arctan((x.vz0 + x.az * t) / vyf)); x["haa"] = -np.degrees(np.arctan((x.vx0 + x.ax * t) / vyf)) * sgn
    x["same"] = (x.stand == x.p_throws).astype(float); x["grp"] = x.pitch_type.map(GRP).fillna("OT")
    # primary fastball per pitcher-season and the gaps to it
    f = x[x.pitch_type.isin(FB)].groupby(["pitcher", "pitch_type"]).size().reset_index(name="n").sort_values("n").drop_duplicates("pitcher", keep="last")
    fm = x.merge(f[["pitcher", "pitch_type"]], on=["pitcher", "pitch_type"]).groupby("pitcher")[["release_speed", "ivb", "hb"]].mean().add_prefix("fb_")
    x = x.join(fm, on="pitcher")
    x["dv"] = x.release_speed - x.fb_release_speed; x["divb"] = x.ivb - x.fb_ivb; x["dhb"] = x.hb - x.fb_hb
    # location (batter-side normalised) and count
    x["px"] = x.plate_x * np.where(x.stand.eq("L"), -1.0, 1.0)
    x["pz"] = (x.plate_z - x.sz_bot) / (x.sz_top - x.sz_bot)
    # target: count values from the season's own PAs, terminal / BIP pitches valued at their outcome or Savant's estimate
    pa = x[x.pa_end & (x.w_den == 1)][["game_pk", "at_bat_number", "w_num"]].rename(columns={"w_num": "final"})
    x = x.merge(pa, on=["game_pk", "at_bat_number"], how="left")
    V = x[x.final.notna()].groupby(["balls", "strikes"]).final.mean().to_dict()
    b, s = x.balls.astype(int), x.strikes.astype(int)
    cur = np.array([V.get((i, j), np.nan) for i, j in zip(b, s)])
    nb = np.array([V.get((min(i + 1, 3), j), np.nan) for i, j in zip(b, s)]); ns = np.array([V.get((i, min(j + 1, 2)), np.nan) for i, j in zip(b, s)])
    d = x.description.fillna("")
    val = np.where(d.isin(["ball", "blocked_ball", "pitchout"]), nb, np.where(d.isin(["called_strike", "swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"]), ns, np.where(d.isin(["foul", "foul_bunt"]) & (s < 2), ns, cur)))
    # terminal outcomes
    ev = x.ev_cls
    val = np.where(ev.eq("K"), 0.0, val); val = np.where(ev.isin(["BB", "HBP"]), x.w_num, val)
    bip = x.bip & x.pa_end
    est = x.estimated_woba_using_speedangle
    val = np.where(bip, np.where(est.notna(), est, np.nan), val)
    x["xrv"] = val - cur          # wOBA units; positive = good for the hitter
    keep = ["pitcher", "batter", "season", "game_pk", "pitch_type", "grp", "p_throws", "stand", "same", "release_speed", "ivb", "hb", "release_spin_rate", "release_extension",
            "relx", "release_pos_z", "vaa", "haa", "dv", "divb", "dhb", "px", "pz", "balls", "strikes", "xrv", "whiff", "swing", "called", "in_zone"]
    x = x[keep]; x = x[np.isfinite(x.xrv)]
    x.to_parquet(f"/home/user/statcast/pitch_{y}.parquet"); return y, len(x), float(x.xrv.mean())
if __name__ == "__main__":
    import sys
    for y in map(int, sys.argv[1:]): print(frame(y), flush=True)
