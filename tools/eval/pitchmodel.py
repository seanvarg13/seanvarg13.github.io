"""Stuff+ and Location+ pitch models. Point-in-time (a season's pitches are graded by a model trained on that season and
the two before) and grouped by pitcher (3 groups by id: a pitcher's pitches are graded by a model that never saw him).
Stuff: physical traits only (no location, no count). Location: where it crossed + count + pitch group + platoon (no traits)."""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
STUFF = ["release_speed", "ivb", "hb", "release_spin_rate", "release_extension", "relx", "release_pos_z", "vaa", "haa", "dv", "divb", "dhb", "same", "g_FB", "g_CT", "g_BR", "g_OS"]
LOC = ["px", "pz", "balls", "strikes", "same", "g_FB", "g_CT", "g_BR", "g_OS"]
def load(y):
    x = pd.read_parquet(f"/home/user/statcast/pitch_{y}.parquet")
    for g in ("FB", "CT", "BR", "OS"): x["g_" + g] = (x.grp == g).astype(float)
    x["pg"] = x.pitcher % 3; return x
D = {y: load(y) for y in range(2015, 2027)}
for y in range(2015, 2027):
    tr = pd.concat([D[z] for z in range(max(2015, y - 2), y + 1)])
    out = D[y]; out["s_pred"] = np.nan; out["l_pred"] = np.nan
    for g in range(3):
        t = tr[tr.pg != g]; t = t.sample(min(len(t), 500000), random_state=g)
        for col, feats in (("s_pred", STUFF), ("l_pred", LOC)):
            tt = t.dropna(subset=["px", "pz"]) if col == "l_pred" else t
            m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.08, max_leaf_nodes=63, min_samples_leaf=500)
            m.fit(tt[feats], tt.xrv)
            sel = out.pg == g
            out.loc[sel, col] = m.predict(out.loc[sel, feats])
    out[["pitcher", "season", "game_pk", "grp", "pitch_type", "balls", "strikes", "xrv", "s_pred", "l_pred", "px", "pz"]].to_parquet(f"/home/user/statcast/pgrade_{y}.parquet")
    print(y, flush=True)
