"""Player-level talent model: ridge on season-centred skill features predicting next-season wOBA.
CV: leave one target season out AND hold out the evaluated players' id group (5 groups) — no row of the evaluated
player and no row whose target season is the evaluated one is in the fit. Holdout pair (2025 -> 2026) untouched here."""
import numpy as np, pandas as pd, harness as H
h = pd.read_parquet("/home/user/statcast/hit_feats.parquet")
d = h.BBE.clip(lower=1)
h["ev90_"] = h.ev90; h["brl_"] = h.brl / d; h["hh_"] = h.hh / d; h["ss_"] = h.ss / d; h["lasd_"] = h.la_sd
h["pullair_"] = h.pull_air / h.BIP.clip(lower=1); h["gb_"] = h.GB / h.BIP.clip(lower=1); h["pu_"] = h.PU / h.BIP.clip(lower=1)
h["whf_"] = h.whf / h.sw.clip(lower=1); h["zsw_"] = h.zsw / h.zpit.clip(lower=1); h["osw_"] = h.osw / h.opit.clip(lower=1)
h["zcon_"] = 1 - h.zwhf / h.zsw.clip(lower=1); h["spd_"] = h.sprint_speed
h["iso_"] = h.iso; h["babip_"] = h.babip
BASE = ["v1", "s_rk", "s_rbb", "s_xcon"]
SKILL = ["ev90_", "brl_", "hh_", "ss_", "lasd_", "pullair_", "gb_", "pu_", "whf_", "zsw_", "osw_", "zcon_", "spd_"]
# season-centre every feature (PA-weighted, 300+ PA league) so eras don't read as skill
for c in BASE + SKILL + ["woba"]:
    m = h[h.PA >= 300].groupby("season").apply(lambda q: np.average(q[c].dropna(), weights=q.loc[q[c].dropna().index, "PA"]) if q[c].notna().any() else np.nan)
    h[c + "c"] = h[c] - h.season.map(m)
# prior seasons (N-1, N-2) of the composite and the PA behind them
P = h[["id", "season", "v1c", "PA"]]
for lag in (1, 2):
    q = P.copy(); q["season"] += lag; h = h.merge(q.rename(columns={"v1c": f"v1c_l{lag}", "PA": f"pa_l{lag}"}), on=["id", "season"], how="left")
for lag in (1, 2):
    h[f"v1c_l{lag}"] = h[f"v1c_l{lag}"].fillna(0); h[f"pa_l{lag}"] = h[f"pa_l{lag}"].fillna(0)
    h[f"w{lag}"] = h[f"v1c_l{lag}"] * h[f"pa_l{lag}"] / 600          # a prior season counts by its sample
h["age_"] = (h.age.fillna(28) - 28); h["age2_"] = h.age_.clip(lower=0) ** 2; h["agey_"] = h.age_.clip(upper=0) ** 2
tg = h[["id", "season", "wobac", "PA"]].rename(columns={"wobac": "tgt", "PA": "tpa"}); tg["season"] -= 1
X = h.merge(tg, on=["id", "season"], how="left")
def fit_eval(cols, name, lam=30.0):
    pred = pd.Series(np.nan, index=X.index)
    dev = X[(X.PA >= 50) & X.tgt.notna() & (X.tpa >= 50) & (X.season + 1 <= 2025)]
    for ts in sorted(dev.season.unique() + 1):
        for g in range(5):
            tr = dev[(dev.season + 1 != ts) & (dev.id % 5 != g)]
            te = X[(X.season + 1 == ts) & (X.id % 5 == g)]
            A = tr[cols].astype(float).fillna(0).values; w = tr.tpa.values.astype(float); y = tr.tgt.values
            mu, sd = A.mean(0), A.std(0) + 1e-9; Z = (A - mu) / sd
            Zb = np.c_[np.ones(len(Z)), Z]; W = Zb.T * w
            beta = np.linalg.solve(W @ Zb + lam * np.diag([0] + [1] * len(cols)), W @ y)
            pred.loc[te.index] = np.c_[np.ones(len(te)), (te[cols].astype(float).fillna(0).values - mu) / sd] @ beta
    m = X[["id", "season"]].assign(value=pred.values).dropna()
    res = H.predictive(m, "H", "woba"); H.log(name, "H", {"target": "next wOBA", "cols": cols, **res})
    print(f"{name:40s} r={res['r']:.3f}  50/200/400: {res['r_50']:.3f} {res['r_200']:.3f} {res['r_400']:.3f}")
    return pred
fit_eval(["v1c"], "ridge: V1 only (calibration check)")
fit_eval(["s_rkc", "s_rbbc", "s_xconc"], "ridge: shrunk K/BB/xcon")
fit_eval(["s_rkc", "s_rbbc", "s_xconc"] + [s + "c" for s in SKILL], "ridge: + contact & discipline skills")
p = fit_eval(["s_rkc", "s_rbbc", "s_xconc"] + [s + "c" for s in SKILL] + ["w1", "w2", "age_", "age2_", "agey_"], "ridge: + prior 2 seasons + age")
X["talent"] = p; X.to_parquet("/home/user/statcast/hit_model.parquet")
from sklearn.ensemble import HistGradientBoostingRegressor
FULL = ["s_rkc", "s_rbbc", "s_xconc"] + [s + "c" for s in SKILL] + ["w1", "w2", "age_", "age2_", "agey_"]
def fit_gbm(cols, name):
    pred = pd.Series(np.nan, index=X.index)
    dev = X[(X.PA >= 50) & X.tgt.notna() & (X.tpa >= 50) & (X.season + 1 <= 2025)]
    for ts in sorted(dev.season.unique() + 1):
        for g in range(5):
            tr = dev[(dev.season + 1 != ts) & (dev.id % 5 != g)]; te = X[(X.season + 1 == ts) & (X.id % 5 == g)]
            m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.03, max_leaf_nodes=15, min_samples_leaf=40)
            m.fit(tr[cols].astype(float), tr.tgt, sample_weight=tr.tpa.astype(float))
            pred.loc[te.index] = m.predict(te[cols].astype(float))
    res = H.predictive(X[["id", "season"]].assign(value=pred.values).dropna(), "H", "woba"); H.log(name, "H", {"target": "next wOBA", **res})
    print(f"{name:40s} r={res['r']:.3f}  50/200/400: {res['r_50']:.3f} {res['r_200']:.3f} {res['r_400']:.3f}")
fit_gbm(FULL, "GBM: full feature set")
GROUPS = {"K/BB": ["s_rkc", "s_rbbc"], "ball model xcon": ["s_xconc"], "EV (ev90/brl/hh)": ["ev90_c", "brl_c", "hh_c"],
          "launch (ss/lasd)": ["ss_c", "lasd_c"], "direction/type (pullair/gb/pu)": ["pullair_c", "gb_c", "pu_c"],
          "discipline (whf/zsw/osw/zcon)": ["whf_c", "zsw_c", "osw_c", "zcon_c"], "sprint": ["spd_c"], "prior seasons": ["w1", "w2"], "age": ["age_", "age2_", "agey_"]}
for gname, gcols in GROUPS.items():
    fit_eval([c for c in FULL if c not in gcols], "ablation: drop " + gname)
FINAL = [c for c in FULL if c not in ("s_xconc", "ss_c", "lasd_c")]
pf = fit_eval(FINAL, "FINAL hitting talent (ridge, no ball model)")
X["talent"] = pf
L = h[h.PA >= 300].groupby("season").apply(lambda q: np.average(q.woba, weights=q.PA))
X["talent_woba"] = X.talent + X.season.map(L)
X.to_parquet("/home/user/statcast/hit_model.parquet")
q = X[X.id == 670623][["season", "PA", "woba", "sxwoba", "talent_woba"]]
q = q.merge(X[["id","season","woba"]].assign(season=lambda d: d.season - 1).rename(columns={"woba": "next_woba"}).loc[lambda d: d.id == 670623].drop(columns="id"), on="season", how="left")
print("Paredes:\n", q.round(3).to_string(index=False))
# pulled fly balls / home-run skill (Paredes check)
Bq = B.copy() if 'B' in dir() else None
