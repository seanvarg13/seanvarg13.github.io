"""Per-batted-ball expected wOBA value, point-in-time and grouped by player: the prediction for a ball in season N comes
from a model trained on seasons <= N on batters outside the ball's own player group (3 groups by id)."""
import sys, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
S = "/home/user/statcast/season"; SAV = "/home/user/statcast/sav"
FEATS = ["launch_speed", "launch_angle", "pull_ang", "aspray", "standR", "sprint", "post23"]
def load(y):
    x = pd.read_parquet(f"{S}/{y}.parquet", columns=["batter", "bip", "pa_end", "ev_cls", "w_num", "w_den", "launch_speed", "launch_angle", "pull_ang", "spray", "stand", "season"])
    b = x[x.bip & x.pa_end & (x.w_den == 1)].copy()
    sp = pd.read_csv(f"{SAV}/sprint{y}.csv", encoding="utf-8-sig")[["player_id", "sprint_speed"]]
    b = b.merge(sp.rename(columns={"player_id": "batter", "sprint_speed": "sprint"}), on="batter", how="left")
    b["aspray"] = b.spray.abs(); b["standR"] = (b.stand == "R").astype(float); b["post23"] = float(y >= 2023)
    b["grp"] = b.batter % 3
    return b
if __name__ == "__main__":
    last = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    D = {y: load(y) for y in range(2015, last + 1)}
    for y in range(2015, last + 1):
        tr = pd.concat([D[z] for z in range(max(2015, y - 4), y + 1)])   # rolling 5 seasons up to and including N
        tr = tr[tr.launch_speed.notna() & tr.launch_angle.notna()]
        out = D[y].copy(); out["xw"] = np.nan
        for g in range(3):
            t = tr[tr.grp != g]
            if len(t) > 400000: t = t.sample(400000, random_state=g)
            m = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, max_leaf_nodes=48, min_samples_leaf=200, l2_regularization=1.0)
            m.fit(t[FEATS], t.w_num)
            sel = (out.grp == g) & out.launch_speed.notna() & out.launch_angle.notna()
            out.loc[sel, "xw"] = m.predict(out.loc[sel, FEATS])
        out[["batter", "season", "w_num", "xw", "launch_speed", "launch_angle", "pull_ang", "post23"]].to_parquet(f"/home/user/statcast/balls_{y}.parquet")
        print(y, len(out), round(out.xw.mean(), 4), round(out.w_num.mean(), 4), flush=True)
