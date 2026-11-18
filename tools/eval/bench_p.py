import numpy as np, pandas as pd, harness as H
a = H.derive(H.tables()); p = a[(a.role == "P")]; full = p[p.part == "all"]
sv = pd.read_parquet("/home/user/statcast/sitevals.parquet"); sv = sv[sv.role == "P"]
def M(df, col): return df[["id", "season"]].assign(value=df[col].values)
mets = {"prior ERA": (M(full, "era"), -1), "prior RA9": (M(full, "ra9"), -1), "FIP": (M(full, "fip"), -1), "xFIP": (M(full, "xfip"), -1),
        "SIERA": (M(full, "siera"), -1), "K-BB%": (M(full, "kbb"), 1), "site Stuff+ (current)": (M(sv, "stuff"), 1), "site nERA (current)": (M(sv, "nera"), -1)}
for tgt, sgn in (("ra9", 1), ("era", 1), ("kbb", -1), ("k", -1), ("bb", 1), ("xfip", 1), ("siera", 1)):
    print("target next", tgt)
    for name, (m, s) in mets.items():
        r = H.predictive(m.dropna(), "P", tgt, sign=s * sgn)
        H.log(name, "P", {"target": "next " + tgt, **r})
        print(f"  {name:24s} r={r['r']:.3f} n={r['n']}  BF 50/200/500: {r['r_50']:.3f} {r['r_200']:.3f} {r['r_500']:.3f}")
hv = p[p.part.isin(["odd", "even"])]
for name, col in (("ERA", "era"), ("RA9", "ra9"), ("FIP", "fip"), ("xFIP", "xfip"), ("SIERA", "siera"), ("K-BB%", "kbb"), ("K%", "k"), ("BB%", "bb")):
    hh = hv.copy()
    if col in ("era", "ra9"): continue   # official runs are season-only; no game halves
    rr = H.reliability(hh[["id", "season", "part"]].assign(value=hh[col].values), "P"); H.log("rel " + name, "P", rr)
    print(f"rel {name:8s} split r={rr['split_r']:.3f} k50={rr['k50']:.0f} BF")
