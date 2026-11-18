import numpy as np, pandas as pd, harness as H
WBB, WHBP = 0.69, 0.72   # stand-ins; season weights are fixed by Savant at .7 BB/HBP
a = H.derive(H.tables()); h = a[(a.role == "H") & (a.part == "all")].copy()
B = pd.concat([pd.read_parquet(f"/home/user/statcast/balls_{y}.parquet") for y in range(2015, 2027)])
g = B.groupby(["batter", "season"])
bb = pd.DataFrame({"xcon_sum": g.xw.sum(), "xcon_n": g.xw.count(), "wcon_sum": g.w_num.sum(), "nbip": g.size()}).reset_index().rename(columns={"batter": "id"})
# random halves of balls for the per-ball mean's reliability
B["half"] = np.arange(len(B)) % 2
hb = B[B.xw.notna()].groupby(["batter", "season", "half"]).xw.agg(["mean", "count"]).reset_index()
pv = hb.pivot_table(index=["batter", "season"], columns="half", values=["mean", "count"]).dropna()
pv = pv[(pv["count"][0] >= 40) & (pv["count"][1] >= 40)]
r = np.corrcoef(pv["mean"][0] - pv["mean"][0].groupby(level=1).transform("mean"), pv["mean"][1] - pv["mean"][1].groupby(level=1).transform("mean"))[0, 1]
nh = float(((pv["count"][0] + pv["count"][1]) / 2).mean()); K_XCON = nh * (1 - r) / r
print(f"xcon split-half r={r:.3f}, k50 = {K_XCON:.0f} BIP")
h = h.merge(bb, on=["id", "season"], how="left")
h["xcon"] = h.xcon_sum / h.xcon_n
d = h.wden.clip(lower=1)
h["rk"], h["rbb"], h["rhbp"] = h.K / d, h.BB / d, h.HBP / d
h["rbip"] = (1 - h.rk - h.rbb - h.rhbp).clip(lower=0)
def comp(k, b, p, c): return b * WBB + p * WHBP + (1 - k - b - p).clip(lower=0) * c
L = h[h.PA >= 300].groupby("season").apply(lambda q: pd.Series({c: np.average(q[c].dropna(), weights=q.loc[q[c].dropna().index, "wden"]) for c in ["rk", "rbb", "rhbp", "xcon", "woba"]}))
def lg(c): return h.season.map(L[c])
KS = {"rk": 54, "rbb": 109, "rhbp": 300}
# V0: single season, actual K/BB/HBP + ball model on contact
h["v0"] = comp(h.rk, h.rbb, h.rhbp, h.xcon)
# V1: each component shrunk toward the season league by its own reliability (empirical Bayes)
def shrink(c, n, k): return (h[c] * n + lg(c) * k) / (n + k)
s = {c: shrink(c, h.wden, k) for c, k in KS.items()}; s["xcon"] = (h.xcon.fillna(lg("xcon")) * h.xcon_n.fillna(0) + lg("xcon") * K_XCON) / (h.xcon_n.fillna(0) + K_XCON)
h["v1"] = comp(s["rk"], s["rbb"], s["rhbp"], s["xcon"])
for c in s: h["s_" + c] = s[c]
def M(c): return h[["id", "season"]].assign(value=h[c].values)
for name, c in (("V0 ball model + actual K/BB", "v0"), ("V1 per-component EB shrink", "v1")):
    res = H.predictive(M(c).dropna(), "H", "woba"); H.log(name, "H", {"target": "next wOBA", **res, "same": H.descriptive(M(c).dropna(), "H", "woba")})
    print(f"{name:32s} r={res['r']:.3f}  50/200/400: {res['r_50']:.3f} {res['r_200']:.3f} {res['r_400']:.3f}")
h.to_parquet("/home/user/statcast/hit_feats.parquet")
