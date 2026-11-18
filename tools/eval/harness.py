"""Evaluation harness. Every metric is a table (id, season, value). Predictive validity: value in season N against the
outcome in N+1, weighted by the N+1 sample, overall and by N-season sample bucket. Reliability: odd/even game halves,
Spearman-Brown, and the sample where reliability = .5 (k). Descriptive fit: same-season r (secondary).
Development pairs end with N+1 = 2025; the 2025 -> 2026 pair is the holdout and is only touched by holdout=True."""
import json, os, glob, datetime, numpy as np, pandas as pd
T = "/home/user/statcast/tables"; LOG = "/home/user/statcast/results.jsonl"
DEV_LAST_TARGET, HOLDOUT = 2025, 2026
_cache = {}
def tables():
    if "t" not in _cache:
        _cache["t"] = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{T}/*.parquet"))], ignore_index=True)
    return _cache["t"]
def lg_consts(a):
    """league constants per season from all pitchers (FIP constant, HR/FB)"""
    p = a[(a.role == "P") & (a.part == "all")]
    out = {}
    for y, d in p.groupby("season"):
        ip = d.outs_P.sum() / 3; era = 9 * d.ER_P.sum() / ip
        fipc = era - (13 * d.HR.sum() + 3 * (d.BB.sum() + d.HBP.sum()) - 2 * d.K.sum()) / ip
        out[y] = {"fipc": fipc, "hrfb": d.HR.sum() / (d.FB.sum() + d.PU.sum()), "ra9": 9 * d.R_P.sum() / ip, "era": era}
    return out
def derive(t):
    t = t.copy(); C = lg_consts(t)
    t["woba"] = t.wnum / t.wden; t["sxwoba"] = t.sx_num / t.sx_den; t["sxcon"] = t.sxc / t.sxc_n
    t["k"] = t.K / t.PA; t["bb"] = (t.BB) / t.PA; t["kbb"] = t.k - t.bb
    ab = t.PA - t.BB - t.IBB - t.HBP - t.SF - t.SH
    h = t["1B"] + t["2B"] + t["3B"] + t.HR
    t["iso"] = (t["2B"] + 2 * t["3B"] + 3 * t.HR) / ab
    t["babip"] = (h - t.HR) / (ab - t.K - t.HR + t.SF)
    ip = t.outs_P / 3
    fipc = t.season.map(lambda y: C[y]["fipc"]); hrfb = t.season.map(lambda y: C[y]["hrfb"])
    t["ip"] = ip; t["era"] = 9 * t.ER_P / ip; t["ra9"] = 9 * t.R_P / ip
    t["fip"] = (13 * t.HR + 3 * (t.BB + t.HBP) - 2 * t.K) / ip + fipc
    t["xfip"] = (13 * (t.FB + t.PU) * hrfb + 3 * (t.BB + t.HBP) - 2 * t.K) / ip + fipc
    so, bb, ng = t.K / t.PA, t.BB / t.PA, (t.GB - t.FB - t.PU) / t.PA
    t["siera"] = 6.145 - 16.986*so + 11.434*bb - 1.858*ng + 7.653*so**2 - np.sign(ng)*6.664*ng**2 + 10.130*so*ng - 5.195*bb*ng
    return t
def wcorr(x, y, w):
    m = np.isfinite(x) & np.isfinite(y) & np.isfinite(w); x, y, w = x[m], y[m], w[m]
    if len(x) < 20: return np.nan, len(x)
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    c = np.average((x - mx) * (y - my), weights=w)
    return c / np.sqrt(np.average((x - mx) ** 2, weights=w) * np.average((y - my) ** 2, weights=w)), len(x)
BUCKETS = {"H": [(50, 200), (200, 400), (400, 9999)], "P": [(50, 200), (200, 500), (500, 9999)]}
def predictive(metric, role, target, holdout=False, min_feat=50, min_tgt=50, sign=1):
    """metric: DataFrame id, season, value (season N). Returns dict of weighted r with the N+1 target."""
    a = derive(tables()); a = a[(a.part == "all") & (a.role == role)]
    tg = a[["id", "season", target, "PA"]].rename(columns={target: "tgt", "PA": "tpa"}); tg["season"] -= 1
    f = a[["id", "season", "PA"]].merge(metric, on=["id", "season"]).merge(tg, on=["id", "season"])
    f = f[(f.PA >= min_feat) & (f.tpa >= min_tgt)]
    f = f[f.season + 1 == HOLDOUT] if holdout else f[f.season + 1 <= DEV_LAST_TARGET]
    # centre each season so era shifts don't count as skill
    for c in ("value", "tgt"): f[c] = f[c] - f.groupby("season")[c].transform(lambda s: np.average(s.dropna(), weights=f.loc[s.dropna().index, "tpa"]) if s.notna().sum() else np.nan)
    r, n = wcorr(sign * f.value.values, f.tgt.values, f.tpa.values.astype(float))
    out = {"r": r, "n": n}
    for lo, hi in BUCKETS[role]:
        g = f[(f.PA >= lo) & (f.PA < hi)]
        out[f"r_{lo}"] = wcorr(sign * g.value.values, g.tgt.values, g.tpa.values.astype(float))[0]
    return out
def reliability(metric_halves, role, min_half=50):
    """metric_halves: DataFrame id, season, part in {odd, even}, value. Split-half r -> Spearman-Brown, k = n(1-r)/r"""
    a = tables(); a = a[(a.role == role) & (a.part.isin(["odd", "even"]))][["id", "season", "part", "PA"]]
    m = a.merge(metric_halves, on=["id", "season", "part"])
    m = m[m.season + 1 <= DEV_LAST_TARGET + 1 - 1]
    w = m.pivot_table(index=["id", "season"], columns="part", values=["value", "PA"])
    w = w.dropna(); w = w[(w["PA"]["odd"] >= min_half) & (w["PA"]["even"] >= min_half)]
    w = w.reset_index()
    vo, ve = w["value"]["odd"], w["value"]["even"]
    so = vo - vo.groupby(w["season"]).transform("mean"); se = ve - ve.groupby(w["season"]).transform("mean")
    r, n = wcorr(so.values, se.values, np.minimum(w["PA"]["odd"], w["PA"]["even"]).values.astype(float))
    nh = float(np.mean((w["PA"]["odd"] + w["PA"]["even"]) / 2))
    return {"split_r": r, "n_half": nh, "k50": nh * (1 - r) / r if r > 0 else np.inf, "full_rel": 2 * r / (1 + r)}
def descriptive(metric, role, target):
    a = derive(tables()); a = a[(a.part == "all") & (a.role == role)]
    f = a[["id", "season", "PA", target]].merge(metric, on=["id", "season"]); f = f[(f.PA >= 300) & (f.season <= DEV_LAST_TARGET)]
    for c in ("value", target): f[c] = f[c] - f.groupby("season")[c].transform("mean")
    return wcorr(f.value.values, f[target].values, f.PA.values.astype(float))[0]
def log(name, role, res):
    rec = {"at": datetime.datetime.utcnow().isoformat(timespec="seconds"), "name": name, "role": role, **{k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in res.items()}}
    open(LOG, "a").write(json.dumps(rec, default=float) + "\n"); return rec
