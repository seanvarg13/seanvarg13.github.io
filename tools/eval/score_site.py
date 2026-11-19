"""Scores every player-season with the review's models (fit on every development pair) -> hist/talent.js for the site.
Hitters: tal = projected next-season wOBA (season league + centred prediction). Pitchers: ppn = new Pitching+ (100 = league RA9,
each point 1% of runs), ra = projected RA9."""
import numpy as np, pandas as pd, json
def fit_all(df, cols, tcol, wcol, lam):
    X = df[cols].astype(float).fillna(0); dev = df[(df.PA >= 50) & (df[wcol] >= 50) & df[tcol].notna()]
    A = X.loc[dev.index].values; mu, sd = A.mean(0), A.std(0) + 1e-9; Z = np.c_[np.ones(len(A)), (A - mu) / sd]; W = Z.T * dev[wcol].values.astype(float)
    b = np.linalg.solve(W @ Z + lam * np.diag([0] + [1] * len(cols)), W @ dev[tcol].values.astype(float))
    return pd.Series(np.c_[np.ones(len(X)), (X.values - mu) / sd] @ b, index=df.index)
out = {"v": 1, "h": {}, "p": {}}
h = pd.read_parquet("/home/user/statcast/hit_model.parquet")
SK = ["ev90_c", "brl_c", "hh_c", "pullair_c", "gb_c", "pu_c", "whf_c", "zsw_c", "osw_c", "zcon_c", "spd_c"]
h["v"] = fit_all(h, ["s_rkc", "s_rbbc"] + SK + ["w1", "w2", "age_", "age2_", "agey_"], "tgt", "tpa", 30.0)
q = h[h.PA >= np.where(h.season == 2020, 110, 300)]; lg = (q.woba * q.PA).groupby(q.season).sum() / q.PA.groupby(q.season).sum()
for r in h[h.PA >= 1].itertuples():
    out["h"].setdefault(str(int(r.id)), {})[str(int(r.season))] = round(float(lg[r.season] + r.v), 4)
f = pd.read_parquet("/home/user/statcast/pitch_model.parquet")
f["v"] = fit_all(f, ["stuffs", "xwhiffs", "locs", "ks", "bbs", "gbs", "whfs", "csws", "siera_l1", "age_"], "tgtc", "tpa", 10.0)
q = f[(f.ip >= 50) & np.isfinite(f.ra9)]; lr = (q.ra9 * q.ip).groupby(q.season).sum() / q.ip.groupby(q.season).sum()
for r in f[f.PA >= 1].itertuples():
    if not np.isfinite(r.v): continue
    out["p"].setdefault(str(int(r.id)), {})[str(int(r.season))] = [round(float(100 - 100 * r.v / lr[r.season]), 1), round(float(lr[r.season] + r.v), 2)]
open("../../hist/talent.js", "w").write("window.DRAFT_TALENT=" + json.dumps(out, separators=(",", ":")) + ";\n")
print(len(out["h"]), len(out["p"]))
