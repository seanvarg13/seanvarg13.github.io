"""Player-season tables (full season and odd/even game halves) for hitters and pitchers, from the season parquet files
and MLB's official lines (runs, earned runs, outs). One row per player x season x part (part = all | odd | even)."""
import json, sys, numpy as np, pandas as pd
SEAS, API, SAV, OUT = "/home/user/statcast/season", "/home/user/statcast/api", "/home/user/statcast/sav", "/home/user/statcast/tables"
def agg(x, key):
    pa = x[x.pa_end]; bip = x[x.bip]; bbe = bip[bip.launch_speed.notna()]
    g = lambda d: d.groupby(key)
    t = pd.DataFrame({
        "PA": g(pa).size(), "wden": g(pa).w_den.sum(), "wnum": g(pa).w_num.sum(),
        "K": g(pa[pa.ev_cls == "K"]).size(), "BB": g(pa[pa.ev_cls == "BB"]).size(), "IBB": g(pa[pa.ev_cls == "IBB"]).size(),
        "HBP": g(pa[pa.ev_cls == "HBP"]).size(), "1B": g(pa[pa.ev_cls == "1B"]).size(), "2B": g(pa[pa.ev_cls == "2B"]).size(),
        "3B": g(pa[pa.ev_cls == "3B"]).size(), "HR": g(pa[pa.ev_cls == "HR"]).size(), "SF": g(pa[pa.ev_cls == "SF"]).size(),
        "SH": g(pa[pa.ev_cls == "SH"]).size(),
        # Savant's xwOBA: their per-ball estimate on balls in play, the actual value otherwise (their bookkeeping)
        "sx_num": g(pa).apply(lambda d: np.where(d.bip & d.estimated_woba_using_speedangle.notna(), d.estimated_woba_using_speedangle, d.woba_value.fillna(0)).sum()),
        "sx_den": g(pa).woba_denom.sum(),
        "BIP": g(bip).size(), "BBE": g(bbe).size(),
        "sxc": g(bip).estimated_woba_using_speedangle.sum(), "sxc_n": g(bip).estimated_woba_using_speedangle.count(),
        "wcon": g(bip).woba_value.sum(),
        "ev_sum": g(bbe).launch_speed.sum(), "ev90": g(bbe).launch_speed.quantile(0.9), "evmax": g(bbe).launch_speed.max(),
        "hh": g(bbe[bbe.launch_speed >= 95]).size(), "brl": g(bbe[bbe.launch_speed_angle == 6]).size(),
        "ss": g(bbe[bbe.launch_angle.between(8, 32)]).size(), "la_sd": g(bbe).launch_angle.std(), "la_mean": g(bbe).launch_angle.mean(),
        "GB": g(bip[bip.bb_type == "ground_ball"]).size(), "LD": g(bip[bip.bb_type == "line_drive"]).size(),
        "FB": g(bip[bip.bb_type == "fly_ball"]).size(), "PU": g(bip[bip.bb_type == "popup"]).size(),
        "pull_air": g(bip[bip.bb_type.isin(["line_drive", "fly_ball"]) & (bip.pull_ang > 16)]).size(),
        "pull": g(bip[bip.pull_ang > 16]).size(), "oppo": g(bip[bip.pull_ang < -16]).size(),
        "pit": g(x).size(), "sw": g(x).swing.sum(), "whf": g(x).whiff.sum(), "foul": g(x).foul.sum(), "cs": g(x).called.sum(),
        "zpit": g(x).in_zone.sum(), "zsw": g(x[x.in_zone]).swing.sum(), "zwhf": g(x[x.in_zone]).whiff.sum(),
        "osw": g(x[~x.in_zone & x.zone.notna()]).swing.sum(), "owhf": g(x[~x.in_zone & x.zone.notna()]).whiff.sum(),
        "opit": g(x[~x.in_zone & x.zone.notna()]).size(),
        "bat_speed": g(x[x.bat_speed.notna()]).bat_speed.mean(),
        "games": g(x).game_pk.nunique(),
    }).fillna({c: 0 for c in ["K","BB","IBB","HBP","1B","2B","3B","HR","SF","SH","BIP","BBE","hh","brl","ss","GB","LD","FB","PU","pull_air","pull","oppo","zsw","zwhf","osw","owhf","opit"]})
    return t
def season(y):
    x = pd.read_parquet(f"{SEAS}/{y}.parquet")
    # game parity per player (odd/even appearances in date order) for split halves
    out = []
    for role, pid in (("H", "batter"), ("P", "pitcher")):
        g = x[[pid, "game_pk", "game_date"]].drop_duplicates([pid, "game_pk"]).sort_values([pid, "game_date", "game_pk"])
        g["half"] = g.groupby(pid).cumcount() % 2
        xx = x.merge(g[[pid, "game_pk", "half"]], on=[pid, "game_pk"])
        for part, d in (("all", xx), ("odd", xx[xx.half == 0]), ("even", xx[xx.half == 1])):
            t = agg(d, pid); t["part"] = part; t["role"] = role; t["season"] = y; t.index.name = "id"
            if role == "H":
                hand = d.groupby(pid).stand.agg(lambda s: "S" if s.nunique() > 1 else s.iloc[0]); t["bats"] = hand
                t["age"] = d.groupby(pid).age_bat.max()
                home = d[d.inning_topbot == "Bot"].groupby(pid).home_team.agg(lambda s: s.mode().iloc[0]) if len(d) else None
            else:
                t["throws"] = d.groupby(pid).p_throws.first(); t["age"] = d.groupby(pid).age_pit.max()
                t["gs"] = d[d.inning == 1].groupby(pid).game_pk.nunique()
            out.append(t.reset_index())
    T = pd.concat(out, ignore_index=True)
    sp = pd.read_csv(f"{SAV}/sprint{y}.csv", encoding="utf-8-sig")[["player_id", "sprint_speed"]].rename(columns={"player_id": "id"})
    T = T.merge(sp, on="id", how="left")
    for role, f in (("H", "h"), ("P", "p")):
        s = json.load(open(f"{API}/{f}{y}.json"))["stats"][0]["splits"]
        api = pd.DataFrame([{"id": r["player"]["id"], "R_" + role: r["stat"].get("runs"), "ER_" + role: r["stat"].get("earnedRuns"),
                             "outs_" + role: r["stat"].get("outs"), "team_" + role: (r.get("team") or {}).get("abbreviation")} for r in s])
        T = T.merge(api, on="id", how="left")
    T.to_parquet(f"{OUT}/{y}.parquet")
    return y, len(T)
if __name__ == "__main__":
    import os; os.makedirs(OUT, exist_ok=True)
    for y in map(int, sys.argv[1:]): print(season(y), flush=True)
