"""Park factors for the site (15 Oct 2026; Sean: "add a stadium impact that accounts for all stadium related impacts to their woba like hr to fb
impact babip impact elevation environment etc ... I'd like the xwoba to be stadium adjusted ... but I'd also like it to be stadium neutral"):
hist/parks.js — per venue x season x batter side, the park's residual on what happened given the contact.

  * Every regular-season plate appearance 2015-now from pybaseball's Statcast cache (~/.pybaseball/cache; the Mac has every day since 2015,
    the retrain workflow's fetch_pa.py fills a cloud one).
  * A park-blind outcome model — out / single / double / triple / home run from exit velocity, launch angle, pull angle and batter side
    (HistGradientBoostingClassifier on every tracked ball in play, every park pooled) — scores every ball; a venue-season-side's residual is
    its mean (actual − expected) per unit: home runs per fly ball + popup (points), non-HR hits per non-HR ball in play (BABIP points), bases per
    non-HR hit, each centred on that season's league (the ball changes year to year; a park factor is relative).
  * K% and BB% per PA against the batter's and the pitcher's own season rate away from the park (plus the league's), both sides pooled.
  * A venue is a park in one configuration (BREAKS: Truist 2017, Globe Life Field 2020, Steinbrenner Field 2025, Sutter Health Park 2025,
    Buffalo 2020 / the three-park 2021 / the renovated Rogers Centre 2023, Camden's left field 2022-24 and 2025, loanDepot's fences 2020,
    Tal's Hill gone 2017, Comerica's fences 2023, Chase's humidor 2018); a season's factor pools the venue's seasons Y-2..Y (the nearest three
    when fewer exist), shrunk by n / (n + k) with k from the variance decomposition (the per-unit noise over the spread of the true park effects —
    about 120 fly balls, 1,200 balls in play, 220 hits, 700 PA for K%, 2,900 for BB%).
  * The app (parkExposure) and build_data.py (park_fields) weight a hitter's parks by his fly balls / balls in play / hits / PA there, by the side
    he hit from; the talent xwOBA takes the K% / BB% halves less that, and the xwOBA tab's Stadium row is the whole effect on his actual wOBA.
  * Ball by ball (Sean, later the same day: "what would a 98 mph line drive x launch angle do in a neutral stadium ... for all of the ones in
    history in coors or t mobile etc I want them to be adjusted to neutral"): a second, park-aware outcome model (the same inputs plus the season
    and the venue as a category) beside a park-blind one with the season; each tracked ball's park effect is aware(ball, its park) − blind(ball)
    on P(HR), P(non-HR hit) and expected non-HR bases, averaged into "cells" per venue × batter side × Mix bucket (the build's: GB, PU, LD and
    FB each pulled / straightaway / the other way) × exit-velocity band (<85, 85-92, 92-97, 97-102, 102-106, 106+, plus the bucket's all-band
    mean for a ball with no exit velocity), a cell's deviation from its bucket's mean shrunk by n / (n + 60), and each season's mean cell value
    per typed ball in play ("centre") taken off every ball so that neutral is that season's league-average park. build_data.py (park_cells) gives
    every ball in play its cell's three numbers, sums them per day (pkh / pkb / pkx) and park_fields turns a season's sums into his HR/FB, BABIP
    and bases per hit less the same balls at a neutral park (m.pkhr / pkbab / pkxb); the app does the same for a window. Coors turns a 97-106 mph
    fly ball into a homer 7 points more often than a neutral park, Oracle 6-8 less; Fenway makes a 92-102 mph fly ball a hit ~.10 more often
    (the Monster); T-Mobile takes ~.03 off every fly ball's hit chance. The venue-mean factors above stay for K% / BB% (per PA, no ball to score).

Cross-checked against Savant's 3-year park factors (2026, by side): HR r .81, BACON r .79, SO r .83, BB r .61, 2B r .76 — a different method
(theirs is home vs away totals; this is given the contact), so the levels differ while the parks line up.

Usage: python3 build_parks.py            (writes hist/parks.js; ~10 minutes — the three model fits are most of it)
       python3 build_parks.py --from 2015 --through 2026
"""
import argparse, collections, datetime, glob, json, os, sys, time
from pathlib import Path
import numpy as np, pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "hist" / "parks.js"
CODES = ["ATH", "ATL", "AZ", "BAL", "BOS", "CHC", "CIN", "CLE", "COL", "CWS", "DET", "HOU", "KC", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY", "PHI", "PIT", "SD", "SEA", "SF", "STL", "TB", "TEX", "TOR", "WSH"]
ALIAS = {"OAK": "ATH"}
# a venue: the park in one configuration — [from, to, key] per team code; a season outside every range is the code itself
VENUE = {"ATH": [[2015, 2024, "OAK"], [2025, 9999, "ATH"]], "ATL": [[2015, 2016, "ATL1"], [2017, 9999, "ATL"]], "TEX": [[2015, 2019, "TEX1"], [2020, 9999, "TEX"]],
         "TB": [[2015, 2024, "TB"], [2025, 2025, "TB25"], [2026, 9999, "TB"]], "TOR": [[2015, 2019, "TOR"], [2020, 2020, "TOR20"], [2021, 2021, "TOR21"], [2022, 2022, "TOR"], [2023, 9999, "TOR23"]],
         "BAL": [[2015, 2021, "BAL"], [2022, 2024, "BAL22"], [2025, 9999, "BAL25"]], "MIA": [[2015, 2019, "MIA"], [2020, 9999, "MIA20"]], "HOU": [[2015, 2016, "HOU"], [2017, 9999, "HOU17"]],
         "DET": [[2015, 2022, "DET"], [2023, 9999, "DET23"]], "AZ": [[2015, 2017, "AZ"], [2018, 9999, "AZ18"]]}
NAMES = {"ATH": "Sutter Health Park", "OAK": "Oakland Coliseum", "ATL": "Truist Park", "ATL1": "Turner Field", "AZ": "Chase Field (pre-humidor)", "AZ18": "Chase Field", "BAL": "Camden Yards", "BAL22": "Camden Yards (deep left field, 2022-24)", "BAL25": "Camden Yards",
         "BOS": "Fenway Park", "CHC": "Wrigley Field", "CIN": "Great American Ball Park", "CLE": "Progressive Field", "COL": "Coors Field", "CWS": "Rate Field", "DET": "Comerica Park (pre-2023 fences)", "DET23": "Comerica Park", "HOU": "Minute Maid Park (Tal's Hill)", "HOU17": "Daikin Park",
         "KC": "Kauffman Stadium", "LAA": "Angel Stadium", "LAD": "Dodger Stadium", "MIA": "Marlins Park (pre-2020 fences)", "MIA20": "loanDepot park", "MIL": "American Family Field", "MIN": "Target Field", "NYM": "Citi Field", "NYY": "Yankee Stadium", "PHI": "Citizens Bank Park", "PIT": "PNC Park",
         "SD": "Petco Park", "SEA": "T-Mobile Park", "SF": "Oracle Park", "STL": "Busch Stadium", "TB": "Tropicana Field", "TB25": "Steinbrenner Field", "TEX": "Globe Life Field", "TEX1": "Globe Life Park", "TOR": "Rogers Centre", "TOR20": "Sahlen Field (Buffalo)", "TOR21": "TD Ballpark / Sahlen Field / Rogers Centre", "TOR23": "Rogers Centre", "WSH": "Nationals Park"}
COLS = ["game_date", "game_type", "game_pk", "at_bat_number", "batter", "pitcher", "stand", "home_team", "events", "description", "bb_type", "launch_speed", "launch_angle", "hc_x", "hc_y"]
COMP = {"hr": ("s_hr", "n_fb", 100), "bab": ("s_nhh", "n_nh", 1000), "xb": ("s_b", "n_hit", 1), "k": ("s_k", "n_pa", 100), "bb": ("s_bb", "n_pa", 100)}
Q = {"hr": "q_hr", "bab": "q_nhh", "xb": "q_b", "k": "q_k", "bb": "q_bb"}


def venue(code, y):
    for a, b, v in VENUE.get(code, []):
        if a <= y <= b:
            return v
    return code


def load(y0, y1):
    """one row per PA from the cache: the PA-ending pitch of every regular-season plate appearance"""
    by = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.expanduser("~/.pybaseball/cache/get_statcast*.parquet"))):
        names = pq.read_schema(f).names; cols = [c for c in COLS if c in names]
        t = pq.read_table(f, columns=cols)
        if not t.num_rows or "events" not in cols:
            continue
        d = t.to_pandas(); d = d[d.game_type.eq("R") & d.events.notna()]
        if not len(d):
            continue
        d["y"] = pd.to_datetime(d.game_date).dt.year
        d = d[(d.y >= y0) & (d.y <= y1)]
        for y, g in d.groupby("y"):
            by[y].append(g)
    parts = []
    for y, L in sorted(by.items()):
        d = pd.concat(L, ignore_index=True).drop_duplicates(["game_pk", "at_bat_number"])
        parts.append(d[~d.events.isin(["truncated_pa"])]); print("  ", y, len(parts[-1]), "PA", flush=True)
    return pd.concat(parts, ignore_index=True)


def residuals(D):
    D["code"] = D.home_team.astype(str).replace(ALIAS)
    D["ven"] = [venue(c, y) for c, y in zip(D.code, D.y)]
    ev = D.events
    D["bip"] = D.description.eq("hit_into_play")
    D["hr"] = ev.eq("home_run"); D["s1"] = ev.eq("single"); D["s2"] = ev.eq("double"); D["s3"] = ev.eq("triple")
    D["nhh"] = D.s1 | D.s2 | D.s3; D["bases"] = D.s1 * 1 + D.s2 * 2 + D.s3 * 3
    D["k"] = ev.isin(["strikeout", "strikeout_double_play"]); D["bb"] = ev.isin(["walk", "intent_walk"])
    D["fbpu"] = D.bip & D.bb_type.isin(["fly_ball", "popup"]); D["pa"] = True
    ls, la = pd.to_numeric(D.launch_speed, errors="coerce"), pd.to_numeric(D.launch_angle, errors="coerce")
    hx, hy = pd.to_numeric(D.hc_x, errors="coerce"), pd.to_numeric(D.hc_y, errors="coerce")
    spray = np.degrees(np.arctan2(hx - 125.42, 198.27 - hy))
    D["pull"] = np.where(D.stand.eq("R"), -spray, spray)
    D["trk"] = D.bip & ls.notna() & la.notna() & hx.notna() & hy.notna() & ~ev.isin(["sac_bunt", "sac_bunt_double_play"])
    D["ev"], D["la"] = ls, la
    T = D[D.trk]
    X = np.column_stack([T.ev.values, T.la.values, T.pull.values, T.stand.eq("R").values.astype(float)])
    yv = np.where(T.hr, 4, np.where(T.s3, 3, np.where(T.s2, 2, np.where(T.s1, 1, 0))))
    clf = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.1, max_leaf_nodes=63, min_samples_leaf=200, l2_regularization=1.0, random_state=0)
    clf.fit(X, yv); P = clf.predict_proba(X)
    print("  outcome model:", clf.n_iter_, "rounds; expected", P.mean(0).round(4), "actual", (np.bincount(yv, minlength=5) / len(yv)).round(4), flush=True)
    for i in range(5):
        D.loc[T.index, f"p{i}"] = P[:, i]
    D["r_hr"] = np.where(D.trk, D.hr.astype(float) - D.p4.fillna(0), 0.0)
    D["r_nhh"] = np.where(D.trk, D.nhh.astype(float) - (D.p1.fillna(0) + D.p2.fillna(0) + D.p3.fillna(0)), 0.0)
    D["r_b"] = np.where(D.trk, D.bases.astype(float) - (D.p1.fillna(0) + 2 * D.p2.fillna(0) + 3 * D.p3.fillna(0)), 0.0)
    D["t_fb"] = D.trk & D.fbpu; D["t_nh"] = D.trk & ~D.hr; D["t_hit"] = D.trk & D.nhh
    for stat in ("k", "bb"):   # expected per PA: the batter's rate away from this venue + the pitcher's − the league's
        for who in ("batter", "pitcher"):
            tot = D.groupby([who, "y"])[stat].agg(["sum", "size"]).rename(columns={"sum": "S", "size": "N"})
            atv = D.groupby([who, "y", "ven"])[stat].agg(["sum", "size"]).rename(columns={"sum": "s", "size": "n"})
            j = atv.join(tot, on=[who, "y"]); lgy = D.groupby("y")[stat].mean()
            ex = (j.S - j.s) / (j.N - j.n); ex = ex.where((j.N - j.n) >= 40, j.index.get_level_values("y").map(lgy).values)
            D = D.merge(ex.rename(f"x_{stat}_{who}").reset_index(), on=[who, "y", "ven"], how="left")
        D[f"x_{stat}"] = (D[f"x_{stat}_batter"] + D[f"x_{stat}_pitcher"] - D.y.map(D.groupby("y")[stat].mean())).clip(0, 1)
        D[f"r_{stat}"] = D[stat].astype(float) - D[f"x_{stat}"]
    for c in ("r_hr", "r_nhh", "r_b", "r_k", "r_bb"):
        D["q" + c[1:]] = D[c] ** 2
    g = D.groupby(["ven", "y", "stand"])
    R = g.agg(n_fb=("t_fb", "sum"), s_hr=("r_hr", "sum"), n_nh=("t_nh", "sum"), s_nhh=("r_nhh", "sum"), n_hit=("t_hit", "sum"), s_b=("r_b", "sum"),
              n_pa=("pa", "sum"), s_k=("r_k", "sum"), s_bb=("r_bb", "sum"), q_hr=("q_hr", "sum"), q_nhh=("q_nhh", "sum"), q_b=("q_b", "sum"), q_k=("q_k", "sum"), q_bb=("q_bb", "sum")).reset_index()
    for num, den in (("s_hr", "n_fb"), ("s_nhh", "n_nh"), ("s_b", "n_hit"), ("s_k", "n_pa"), ("s_bb", "n_pa")):   # centred on the season's league per side
        lg = R.groupby(["y", "stand"]).apply(lambda q: q[num].sum() / max(1, q[den].sum())).rename("lg").reset_index()
        R = R.merge(lg, on=["y", "stand"], how="left"); R[num] = R[num] - R["lg"] * R[den]; R = R.drop(columns=["lg"])
    KB = R.groupby(["ven", "y"]).agg(s_k=("s_k", "sum"), s_bb=("s_bb", "sum"), n_pa=("n_pa", "sum"), q_k=("q_k", "sum"), q_bb=("q_bb", "sum")).reset_index()
    R = R.drop(columns=["s_k", "s_bb", "n_pa", "q_k", "q_bb"]).merge(KB, on=["ven", "y"], how="left")   # K / BB: both sides pooled
    return R


def shrinkage(R):
    K = {}
    for c, (num, den, sc) in COMP.items():
        sub = R[R[den] >= (300 if c in ("hr", "xb") else 800)].copy(); sub["r"] = sub[num] / sub[den]
        if c in ("k", "bb"):
            sub = sub.drop_duplicates(["ven", "y"])
        noise = sub[Q[c]] / sub[den] ** 2
        v_obs, v_noise = sub.r.var(), noise.mean(); vt = max(1e-12, v_obs - v_noise)
        v1 = sub[Q[c]].sum() / sub[den].sum()
        K[c] = v1 / vt
        print(f"  {c}: spread of park effects {np.sqrt(vt) * sc:.2f} (noise {np.sqrt(v_noise) * sc:.2f}), k = {K[c]:.0f} units", flush=True)
    return K


def pooled(R, K, ven, y, side, c):
    num, den, sc = COMP[c]
    sub = R[(R.ven == ven) & (R.stand == (side if c not in ("k", "bb") else "R"))]
    if c in ("k", "bb"):
        sub = sub.drop_duplicates(["ven", "y"])
    avail = sorted(sub.y.unique())
    if not avail:
        return None
    win = [z for z in avail if y - 2 <= z <= y]
    if len(win) < 3:
        rest = sorted([z for z in avail if z not in win], key=lambda z: (abs(z - y), z)); win = sorted(win + rest[:3 - len(win)])
    q = sub[sub.y.isin(win)]; n = q[den].sum(); s = q[num].sum()
    if not n:
        return None
    return round(float(s / n * n / (n + K[c]) * sc), 3 if c == "xb" else 2)


BUCKETS = ["gb", "pu", "ld_p", "ld_c", "ld_o", "fb_p", "fb_c", "fb_o"]   # build_data.py's MIX_COLS order (without the no-direction "x")
EDGES = [85, 92, 97, 102, 106]
K_CELL = 60


def cells(D):
    """per venue x side x Mix bucket x EV band: the park-aware model's chance of a HR, of a non-HR hit and its non-HR bases on that kind of ball at
    that park, less the park-blind model's (the league-average park for that ball) — {ven: {side: {bucket index: [[dhr, dhit, dbases] x 6 bands, all]}}}"""
    kw = dict(max_iter=300, learning_rate=0.1, max_leaf_nodes=63, min_samples_leaf=200, l2_regularization=1.0, random_state=0)
    bt = D.bb_type.fillna("")
    kind = np.select([bt.eq("ground_ball"), bt.eq("popup"), bt.eq("line_drive"), bt.eq("fly_ball")], ["gb", "pu", "ld", "fb"], "")
    pull = D.pull.to_numpy(dtype=float)
    dirn = np.where(pull > 16, "p", np.where(pull < -16, "o", np.where(np.isnan(pull), "x", "c")))
    mixb = np.where(np.isin(kind, ["ld", "fb"]), np.char.add(np.char.add(kind.astype(str), "_"), dirn.astype(str)), kind)
    bk = pd.Series(mixb).map({b: i for i, b in enumerate(BUCKETS)}).fillna(-1).astype(int).to_numpy()
    T = D[D.trk & (bk >= 0)]; bkT = bk[(D.trk & (bk >= 0)).to_numpy()]
    vens = sorted(D.ven.unique()); VI = {v: i for i, v in enumerate(vens)}
    X0 = np.column_stack([T.ev.values, T.la.values, T.pull.values, T.stand.eq("R").values.astype(float), T.y.values.astype(float)])
    Xa = np.column_stack([X0, T.ven.map(VI).values.astype(float)])
    yv = np.where(T.hr, 4, np.where(T.s3, 3, np.where(T.s2, 2, np.where(T.s1, 1, 0))))
    c0 = HistGradientBoostingClassifier(**kw).fit(X0, yv); print("  park-blind model:", c0.n_iter_, "rounds", flush=True)
    ca = HistGradientBoostingClassifier(categorical_features=[5], **kw).fit(Xa, yv); print("  park-aware model:", ca.n_iter_, "rounds", flush=True)
    P0, Pa = c0.predict_proba(X0), ca.predict_proba(Xa)
    F = pd.DataFrame({"ven": T.ven.values, "stand": T.stand.values, "bk": bkT, "band": np.searchsorted(EDGES, T.ev.values, side="right"),
                      "dhr": Pa[:, 4] - P0[:, 4], "dhit": Pa[:, 1:4].sum(1) - P0[:, 1:4].sum(1), "db": (Pa[:, 1] + 2 * Pa[:, 2] + 3 * Pa[:, 3]) - (P0[:, 1] + 2 * P0[:, 2] + 3 * P0[:, 3])})
    C = F.groupby(["ven", "stand", "bk", "band"]).agg(n=("dhr", "size"), dhr=("dhr", "mean"), dhit=("dhit", "mean"), db=("db", "mean")).reset_index()
    A = F.groupby(["ven", "stand", "bk"]).agg(dhr=("dhr", "mean"), dhit=("dhit", "mean"), db=("db", "mean")).reset_index()
    C = C.merge(A.rename(columns={"dhr": "ahr", "dhit": "ahit", "db": "ab"}), on=["ven", "stand", "bk"], how="left")
    for c, a in (("dhr", "ahr"), ("dhit", "ahit"), ("db", "ab")):
        C[c] = C[a] + (C[c] - C[a]) * C.n / (C.n + K_CELL)
    out = {}
    for r in C.itertuples():
        out.setdefault(r.ven, {}).setdefault(r.stand, {}).setdefault(str(int(r.bk)), [None] * 7)[int(r.band)] = [round(float(r.dhr), 4), round(float(r.dhit), 4), round(float(r.db), 4)]
    for r in A.itertuples():
        out.setdefault(r.ven, {}).setdefault(r.stand, {}).setdefault(str(int(r.bk)), [None] * 7)[6] = [round(float(r.dhr), 4), round(float(r.dhit), 4), round(float(r.db), 4)]
    # the centre: per season, the mean cell value per typed ball in play (every ball in play the build gives a cell — tracked by its band, untracked
    # by its bucket's all-band mean), so that "neutral" is that season's league-average park and a season's effects sum to zero
    look = {}
    for ven, S in out.items():
        for side, Bk in S.items():
            for bk, L in Bk.items():
                for i, v in enumerate(L):
                    if v: look[(ven, side, int(bk), i)] = v
    ok = D.bip & (bk >= 0)
    allb = pd.DataFrame({"y": D.y[ok].values, "ven": D.ven[ok].values, "stand": D.stand[ok].values, "bk": bk[ok.to_numpy()],
                         "band": np.where(D.ev[ok].notna(), np.searchsorted(EDGES, D.ev[ok].fillna(0).values, side="right"), 6)})
    vals = np.array([look.get((v, s, int(b), int(d)), (0.0, 0.0, 0.0)) for v, s, b, d in zip(allb.ven, allb.stand, allb.bk, allb.band)])
    cen = {}
    for y in sorted(allb.y.unique()):
        m = (allb.y == y).to_numpy(); cen[str(int(y))] = [round(float(x), 5) for x in vals[m].mean(0)]
    return out, cen


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--from", dest="y0", type=int, default=2015); ap.add_argument("--through", dest="y1", type=int, default=datetime.date.today().year)
    a = ap.parse_args(); t0 = time.time()
    print("loading the cache…", flush=True)
    D = load(a.y0, a.y1)
    print(f"{len(D)} PA, {int(D.description.eq('hit_into_play').sum())} balls in play, {time.time() - t0:.0f}s", flush=True)
    R = residuals(D); K = shrinkage(R)
    F = {}
    for ven in sorted(R.ven.unique()):
        for y in sorted(R[R.ven == ven].y.unique()):
            F.setdefault(ven, {})[str(int(y))] = {side: [pooled(R, K, ven, int(y), side, c) for c in COMP] for side in ("L", "R")}
    C, cen = cells(D)
    out = {"v": 2, "built": datetime.date.today().isoformat(), "keys": list(COMP), "codes": CODES, "venue": VENUE, "names": NAMES, "f": F,
           "edges": EDGES, "buckets": BUCKETS, "cellKeys": ["dhr", "dhit", "dbases"], "cells": C, "centre": cen}
    OUT.write_text("window.DRAFT_PARKS = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(F)} venues) in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
