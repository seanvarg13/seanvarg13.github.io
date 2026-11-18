import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
STUFF = ["release_speed", "ivb", "hb", "release_spin_rate", "release_extension", "relx", "release_pos_z", "vaa", "haa", "dv", "divb", "dhb", "same", "g_FB", "g_CT", "g_BR", "g_OS"]
def load(y):
    x = pd.read_parquet(f"/home/user/statcast/pitch_{y}.parquet"); x = x[x.swing]
    for g in ("FB", "CT", "BR", "OS"): x["g_" + g] = (x.grp == g).astype(float)
    x["pg"] = x.pitcher % 3; return x
D = {y: load(y) for y in range(2015, 2027)}
rows = []
for y in range(2015, 2027):
    tr = pd.concat([D[z] for z in range(max(2015, y - 2), y + 1)]); out = D[y]; out["pw"] = np.nan
    for g in range(3):
        t = tr[tr.pg != g]; t = t.sample(min(len(t), 500000), random_state=g)
        m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=63, min_samples_leaf=500).fit(t[STUFF], t.whiff)
        sel = out.pg == g; out.loc[sel, "pw"] = m.predict_proba(out.loc[sel, STUFF])[:, 1]
    rows.append(out.groupby("pitcher").agg(nsw=("pw", "size"), xwhiff=("pw", "mean")).reset_index().assign(season=y)); print(y, flush=True)
pd.concat(rows).rename(columns={"pitcher": "id"}).to_parquet("/home/user/statcast/xwhiff.parquet")
