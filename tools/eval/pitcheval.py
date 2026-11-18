import numpy as np, pandas as pd, harness as H
G = pd.concat([pd.read_parquet(f"/home/user/statcast/pgrade_{y}.parquet") for y in range(2015, 2027)])
# location value relative to the league's average for that pitch group and count that season
G["l_rel"] = G.l_pred - G.groupby(["season", "grp", "balls", "strikes"]).l_pred.transform("mean")
gm = G[["pitcher", "season", "game_pk"]].drop_duplicates().sort_values(["pitcher", "season", "game_pk"])
gm["half"] = gm.groupby(["pitcher", "season"]).cumcount() % 2
G = G.merge(gm, on=["pitcher", "season", "game_pk"])
def agg(d):
    a = d.groupby(["pitcher", "season"]).agg(n=("s_pred", "size"), s=("s_pred", "mean"), l=("l_rel", "mean")).reset_index()
    for c, nm in (("s", "stuff"), ("l", "loc")):
        q = a[a.n >= 500]; mu = q.groupby("season")[c].apply(lambda v: np.average(v, weights=q.loc[v.index, "n"])); sd = q.groupby("season")[c].std()
        a[nm] = 100 - 10 * (a[c] - a.season.map(mu)) / a.season.map(sd)
    return a.rename(columns={"pitcher": "id"})
A = agg(G)
halves = pd.concat([agg(G[G.half == h]).assign(part=p) for h, p in ((0, "odd"), (1, "even"))])
for nm in ("stuff", "loc"):
    rr = H.reliability(halves[["id", "season", "part"]].assign(value=halves[nm].values), "P"); H.log("rel new " + nm, "P", rr)
    print(f"rel new {nm}: split r={rr['split_r']:.3f} k50={rr['k50']:.0f} BF")
# Pitching+: weights fit within CV (leave target season out, pitcher groups) on next-season RA9
a = H.derive(H.tables()); f = a[(a.role == "P") & (a.part == "all")][["id", "season", "PA", "kbb"]].merge(A, on=["id", "season"], how="left")
tg = a[(a.role == "P") & (a.part == "all")][["id", "season", "ra9", "PA"]].rename(columns={"ra9": "tgt", "PA": "tpa"}); tg["season"] -= 1
f = f.merge(tg, on=["id", "season"], how="left")
f["tgt"] = f.tgt.where(np.isfinite(f.tgt.astype(float))); f["tgtc"] = f.tgt - f.groupby("season").tgt.transform("mean")
def ridge_cv(cols, lam=10.0):
    pred = pd.Series(np.nan, index=f.index)
    dev = f[(f.PA >= 50) & (f.tpa >= 50) & f.tgt.notna() & (f.season + 1 <= 2025) & f[cols].notna().all(1)]
    for ts in sorted(dev.season.unique() + 1):
        for g in range(3):
            tr = dev[(dev.season + 1 != ts) & (dev.id % 3 != g)]; te = f[(f.season + 1 == ts) & (f.id % 3 == g) & f[cols].notna().all(1)]
            A_ = tr[cols].values.astype(float); mu, sd = A_.mean(0), A_.std(0); Z = np.c_[np.ones(len(A_)), (A_ - mu) / sd]; W = Z.T * tr.tpa.values
            b = np.linalg.solve(W @ Z + lam * np.diag([0] + [1] * len(cols)), W @ tr.tgtc.values)
            pred.loc[te.index] = np.c_[np.ones(len(te)), (te[cols].values.astype(float) - mu) / sd] @ b
    return pred
for nm, cols in (("new Stuff+", ["stuff"]), ("new Location+", ["loc"]), ("new Pitching+ (stuff+loc)", ["stuff", "loc"]), ("new Pitching+ + K-BB%", ["stuff", "loc", "kbb"])):
    p = ridge_cv(cols); m = f[["id", "season"]].assign(value=-p.values).dropna()   # minus: higher = better pitcher
    for tgt in ("ra9", "era", "kbb", "xfip", "siera"):
        sign = 1 if tgt == "kbb" else -1
        r = H.predictive(m, "P", tgt, sign=sign); H.log(nm, "P", {"target": "next " + tgt, **r})
        print(f"{nm:28s} next {tgt:6s} r={abs(r['r']):.3f}  BF 50/200/500: {abs(r['r_50']):.3f} {abs(r['r_200']):.3f} {abs(r['r_500']):.3f}")
f.assign(pplus=-ridge_cv(["stuff", "loc"])).to_parquet("/home/user/statcast/pitch_model.parquet"); A.to_parquet("/home/user/statcast/pitch_grades.parquet")
