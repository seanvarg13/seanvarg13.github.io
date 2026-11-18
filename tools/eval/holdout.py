"""The one look at the 2025 -> 2026 holdout. Models are fit on every development pair (targets <= 2025) and score 2025."""
import numpy as np, pandas as pd, harness as H, json
def fit_score(df, cols, tcol, wcol, lam):
    X = df[cols].astype(float).fillna(0); dev = df[(df.PA >= 50) & (df[wcol] >= 50) & df[tcol].notna() & (df.season + 1 <= 2025)]
    A = X.loc[dev.index].values; mu, sd = A.mean(0), A.std(0) + 1e-9; Z = np.c_[np.ones(len(A)), (A - mu) / sd]; W = Z.T * dev[wcol].values.astype(float)
    b = np.linalg.solve(W @ Z + lam * np.diag([0] + [1] * len(cols)), W @ dev[tcol].values.astype(float))
    te = df[df.season == 2025]; return te[["id", "season"]].assign(value=np.c_[np.ones(len(te)), (X.loc[te.index].values - mu) / sd] @ b)
R = {}
# hitters
h = pd.read_parquet("/home/user/statcast/hit_model.parquet")
SK = ["ev90_c", "brl_c", "hh_c", "pullair_c", "gb_c", "pu_c", "whf_c", "zsw_c", "osw_c", "zcon_c", "spd_c"]
new_h = fit_score(h, ["s_rkc", "s_rbbc"] + SK + ["w1", "w2", "age_", "age2_", "agey_"], "tgt", "tpa", 30.0)
exec(open("bench_h.py").read().split("for name, m in mets.items()")[0])
mets["NEW talent xwOBA"] = new_h
print("HITTERS: 2025 -> 2026 wOBA (holdout)")
for name, m in mets.items():
    r = H.predictive(m, "H", "woba", holdout=True); H.log("HOLDOUT " + name, "H", {"target": "2026 wOBA", **r}); R["H " + name] = r
    print(f"  {name:24s} r={r['r']:.3f} n={r['n']}  PA 50/200/400: {r['r_50']:.3f} {r['r_200']:.3f} {r['r_400']:.3f}")
# pitchers
f = pd.read_parquet("/home/user/statcast/pitch_model.parquet")
cols = ["stuffs", "xwhiffs", "locs", "ks", "bbs", "gbs", "whfs", "csws", "siera_l1", "age_"]
new_p = fit_score(f, cols, "tgtc", "tpa", 10.0); new_p["value"] *= -1
new_s = fit_score(f, ["stuffs", "xwhiffs", "locs"], "tgtc", "tpa", 10.0); new_s["value"] *= -1
exec(open("bench_p.py").read().split("for tgt, sgn in")[0])
mets["NEW Pitching+ (full)"] = (new_p, 1); mets["NEW Pitching+ (stuff/loc only)"] = (new_s, 1)
print("PITCHERS: 2025 -> 2026 (holdout), |r|")
for name, (m, s) in mets.items():
    row = []
    for tgt, sg in (("ra9", 1), ("era", 1), ("kbb", -1), ("k", -1), ("bb", 1), ("xfip", 1), ("siera", 1)):
        r = H.predictive(m.dropna(), "P", tgt, holdout=True, sign=s * sg); H.log("HOLDOUT " + name, "P", {"target": "2026 " + tgt, **r}); row.append(f"{tgt} {abs(r['r']):.3f}")
    print(f"  {name:30s} " + "  ".join(row))
