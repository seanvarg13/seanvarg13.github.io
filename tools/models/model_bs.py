"""Directional xBA and xSLG — the same recipe as v3_dir (model3.py), two more targets.

v3_dir predicts the wOBA numerator a batted ball is worth. xBA and xSLG need the other two
things a ball can be worth: whether it goes for a hit, and how many bases. Same features
(EV, launch angle, sprint speed, pull angle, spray angle, batter hand), same 3-year recency
half-life, same era-neutral target (divide by the season's league rate, multiply back when
scoring), so a pulled fly ball is priced by the shift rules in force now.
"""
import time, numpy as np, pandas as pd, joblib
from sklearn.ensemble import HistGradientBoostingRegressor
import pybaseball as pb
pb.cache.enable()

SP = "/Users/seanvargas/Desktop/Fantasy Baseball/model-workspace/"   # pa_all.parquet lives here (was a session scratchpad)
OUTD = "/Users/seanvargas/Desktop/Fantasy Baseball/model-workspace/"
HALF_LIFE, ANCHOR = 3.0, 2026
HITS = {"single": 1.0, "double": 2.0, "triple": 3.0, "home_run": 4.0}
FEATS = ["launch_speed", "launch_angle", "sprint_speed", "pull_angle", "spray_angle", "stand_R"]
t0 = time.time()
def log(*a): print(f"[{round(time.time()-t0):4d}s]", *a, flush=True)

d = pd.read_parquet(SP + "pa_all.parquet")
ev = d.events
d["tb"] = ev.map(HITS).fillna(0.0)
d["is_hit"] = ev.isin(HITS).astype(float)
spray = np.degrees(np.arctan2(d.hc_x - 125.42, 198.27 - d.hc_y))
d["spray_angle"] = spray
d["pull_angle"] = np.where(d.stand.eq("R"), -spray, spray)
d["stand_R"] = d.stand.eq("R").astype(float)
sp = []
for y in range(2015, 2027):
    t = pb.statcast_sprint_speed(y, min_opp=5)[["player_id", "sprint_speed"]].rename(columns={"player_id": "batter"})
    t["game_year"] = y; sp.append(t)
sp = pd.concat(sp).drop_duplicates(["batter", "game_year"])
d["game_year"] = d.game_year.astype(int); d["batter"] = d.batter.astype(int)
d = d.merge(sp, on=["batter", "game_year"], how="left")

# every tracked ball in play that counts as an at-bat (sacrifices are out of both xBA and xSLG)
bbe = d[d.type.eq("X") & d.launch_speed.notna() & d.launch_angle.notna()
        & ~ev.isin(["sac_fly", "sac_bunt", "sac_fly_double_play", "sac_bunt_double_play",
                    "catcher_interf", "truncated_pa"])].copy()
w = np.exp(np.log(0.5) * (ANCHOR - bbe.game_year) / HALF_LIFE).values
log(f"BBE {len(bbe):,}  coords {100*bbe.hc_x.notna().mean():.1f}%  sprint {100*bbe.sprint_speed.notna().mean():.1f}%")

for name, col in [("ba", "is_hit"), ("slg", "tb")]:
    mu = bbe.groupby("game_year")[col].mean()
    log(f"league {name.upper()} on contact by season:\n" + mu.round(4).to_string())
    y = bbe[col] / bbe.game_year.map(mu)
    m = HistGradientBoostingRegressor(max_iter=1200, learning_rate=0.04, max_leaf_nodes=63,
                                      min_samples_leaf=150, l2_regularization=1.0, early_stopping=True,
                                      validation_fraction=0.1, random_state=0)
    m.fit(bbe[FEATS], y, sample_weight=w)
    out = OUTD + f"v3_{name}.joblib"
    joblib.dump(m, out)
    p26 = m.predict(bbe[bbe.game_year == 2026][FEATS]) * mu[2026]
    a26 = bbe[bbe.game_year == 2026][col]
    log(f"{name}: fit in {m.n_iter_} iters · 2026 in-sample level {p26.mean()/a26.mean():.4f} "
        f"(predicted {p26.mean():.4f} vs actual {a26.mean():.4f}) -> {out}")
