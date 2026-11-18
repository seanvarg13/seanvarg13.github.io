import json, numpy as np, pandas as pd, harness as H
a = H.derive(H.tables()); h = a[a.role == "H"]
full = h[h.part == "all"]
def M(df, col): return df[["id", "season"]].assign(value=df[col].values)
mets = {"prior wOBA": M(full, "woba"), "Savant xwOBA": M(full, "sxwoba"), "Savant xwOBAcon": M(full, "sxcon")}
# Marcel on wOBA: 5/4/3 by wOBA PA, 1200 PA of league, age adjustment
lg = full.groupby("season").apply(lambda d: d.wnum.sum() / d.wden.sum())
rows = []
idx = full.set_index(["id", "season"])
for (pid, y), r in idx.iterrows():
    num = den = 0
    for w, yy in ((5, y), (4, y - 1), (3, y - 2)):
        if (pid, yy) in idx.index:
            q = idx.loc[(pid, yy)]; num += w * q.wnum; den += w * q.wden
    lgv = lg[y]; v = (num + 1200 * lgv) / (den + 1200)
    age = r.age + 1 if pd.notna(r.age) else 29
    v *= 1 + (0.006 * (29 - age) if age < 29 else -0.003 * (age - 29))
    rows.append((pid, y, v))
mets["Marcel"] = pd.DataFrame(rows, columns=["id", "season", "value"])
# current site xwOBA (talent, with his parks) from hist/career-bb.js
t = open("/home/user/seanvarg13.github.io/hist/career-bb.js").read(); cb = json.loads(t[t.index("=") + 1:].strip().rstrip(";"))
k = cb["keys"]; rows = []; rows2 = []
for pid, ys in cb["p"].items():
    for y, v in ys.items():
        d = dict(zip(k, v[1:] if len(v) == len(k) + 1 else v))
        if d.get("txwpk") is not None: rows.append((int(pid), int(y), d["txwpk"]))
mets["site xwOBA (current)"] = pd.DataFrame(rows, columns=["id", "season", "value"])
for name, m in mets.items():
    res = H.predictive(m, "H", "woba")
    rec = H.log(name, "H", {"target": "next wOBA", **res, "same": H.descriptive(m, "H", "woba")})
    print(f"{name:22s} r={res['r']:.3f} n={res['n']}  by PA 50/200/400: {res['r_50']:.3f} {res['r_200']:.3f} {res['r_400']:.3f}  same={rec['same']:.3f}")
# reliability (split halves) for the season stats
hv = h[h.part.isin(["odd", "even"])]
for name, col in (("wOBA", "woba"), ("Savant xwOBA", "sxwoba"), ("Savant xwOBAcon", "sxcon"), ("K%", "k"), ("BB%", "bb"), ("ISO", "iso"), ("BABIP", "babip")):
    rr = H.reliability(hv[["id", "season", "part"]].assign(value=hv[col].values), "H")
    H.log("rel " + name, "H", rr); print(f"rel {name:16s} split r={rr['split_r']:.3f} k50={rr['k50']:.0f} PA")
