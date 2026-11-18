"""Consolidate the per-day Statcast parquet files into one file per season with the derived columns every
model and benchmark uses. Bookkeeping is FanGraphs-style wOBA: reached on error / fielder's choice / strikeout-reached
count as outs (0), intentional walks, sacrifice bunts, catcher's interference and truncated PAs leave both the numerator
and the denominator. Linear weights are the season's own (Savant's per-event woba_value, which are FanGraphs Guts)."""
import sys, glob, numpy as np, pandas as pd
DAYS, OUT = "/home/user/statcast/days", "/home/user/statcast/season"
SW = {"swinging_strike","swinging_strike_blocked","foul","foul_tip","hit_into_play","foul_bunt","missed_bunt","bunt_foul_tip"}
WH = {"swinging_strike","swinging_strike_blocked","foul_tip","missed_bunt"}
FOUL = {"foul","foul_bunt"}
BUNT_D = {"foul_bunt","missed_bunt","bunt_foul_tip"}
EV_CLASS = {"single":"1B","double":"2B","triple":"3B","home_run":"HR","walk":"BB","intent_walk":"IBB","hit_by_pitch":"HBP",
            "strikeout":"K","strikeout_double_play":"K","sac_fly":"SF","sac_fly_double_play":"SF","sac_bunt":"SH",
            "sac_bunt_double_play":"SH","catcher_interf":"CI","truncated_pa":"TR","field_error":"ROE"}
def season(y):
    fs = sorted(glob.glob(f"{DAYS}/{y}-*.parquet"))
    x = pd.concat([pd.read_parquet(f) for f in fs if pd.read_parquet(f).shape[0]], ignore_index=True)
    for c in ["stand","p_throws","home_team","away_team","inning_topbot","pitch_type","type","description","events","bb_type",
              "if_fielding_alignment","of_fielding_alignment","game_date"]:
        x[c] = x[c].astype("object").where(x[c].notna(), None)
    x["season"] = np.int16(y)
    x = x.sort_values(["game_pk","at_bat_number","pitch_number"]).reset_index(drop=True)
    # duplicates (Savant occasionally repeats a pitch row)
    x = x.drop_duplicates(["game_pk","at_bat_number","pitch_number"], keep="first").reset_index(drop=True)
    ev = x["events"].fillna("")
    cls = ev.map(EV_CLASS); cls = cls.where(cls.notna(), pd.Series(np.where(ev.ne(""), "OUT", ""), index=ev.index))
    x["ev_cls"] = cls
    x["pa_end"] = ev.ne("") & cls.ne("TR")
    # season linear weights from Savant's own values
    w = {}
    for k, e in [("1B","single"),("2B","double"),("3B","triple"),("HR","home_run"),("BB","walk"),("HBP","hit_by_pitch")]:
        v = x.loc[ev.eq(e), "woba_value"].dropna()
        w[k] = float(v.round(3).mode().iloc[0])
    x["w_num"] = cls.map(w).fillna(0.0).astype("float32")
    x["w_den"] = (x["pa_end"] & ~cls.isin(["IBB","SH","CI"])).astype("int8")
    d = x["description"].fillna("")
    x["swing"] = d.isin(SW); x["whiff"] = d.isin(WH); x["foul"] = d.isin(FOUL); x["called"] = d.eq("called_strike")
    x["bunt_att"] = d.isin(BUNT_D) | cls.eq("SH")
    x["in_zone"] = x["zone"].between(1, 9).fillna(False).astype(bool)
    x["bip"] = x["type"].eq("X")
    # spray and handedness-normalised pull angle (positive = pulled); Savant's park-centred field coordinates
    sp = np.degrees(np.arctan2(x["hc_x"].astype("float64") - 125.42, 198.27 - x["hc_y"].astype("float64")))
    x["spray"] = sp.astype("float32")
    x["pull_ang"] = np.where(x["stand"].eq("R"), -sp, sp).astype("float32")
    x.to_parquet(f"{OUT}/{y}.parquet", compression="zstd")
    return y, len(x), w
if __name__ == "__main__":
    for y in map(int, sys.argv[1:]):
        print(season(y), flush=True)
