"""Directional xwOBA v3 — Savant's inputs (EV, launch angle, sprint speed) plus where the ball went
(pull angle, spray angle, batter hand), with the seasons weighted by recency.

Why v3: v2 weighted 2015-2025 equally, so more than half its training came from the shift era. The
2023 shift ban changed what a pulled ground ball is worth, and v2 mis-priced exactly the balls the
"xwOBA ignores direction" argument is about. Scoring 2026 with a fit through 2025:

    v2 recipe (all seasons equal)   RMSE 0.3640  R2 0.5948  level 1.0245
    recency 3y half-life + capacity RMSE 0.3588  R2 0.6063  level 0.9991   <- this file
    Savant xwOBAcon                 RMSE 0.4246  R2 0.4486  level 0.9921

"level" is mean prediction / actual league wOBA on contact: v2 ran 2.5% hot, which is why the site
had to re-anchor it per season. Trains straight off the local pybaseball cache — no network.
"""
import time, numpy as np, pandas as pd, joblib
from sklearn.ensemble import HistGradientBoostingRegressor
import pybaseball as pb
pb.cache.enable()

SP = "/Users/seanvargas/Desktop/Fantasy Baseball/model-workspace/"   # pa_all.parquet lives here (was a session scratchpad)
OUT = "/Users/seanvargas/Desktop/Fantasy Baseball/model-workspace/v3_dir.joblib"
HALF_LIFE, ANCHOR = 3.0, 2026          # a season 3 years back counts half as much
ZERO_NUM = {"field_error", "fielders_choice", "fielders_choice_out"}
EXCLUDE = {"sac_bunt", "truncated_pa", "catcher_interf", "intent_walk"}
FEATS = ["launch_speed", "launch_angle", "sprint_speed", "pull_angle", "spray_angle", "stand_R"]
t0 = time.time()
def log(*a): print(f"[{round(time.time()-t0):4d}s]", *a, flush=True)

d = pd.read_parquet(SP + "pa_all.parquet")      # every regular-season PA 2015-2026, from the cache
num = pd.to_numeric(d.woba_value, errors="coerce").fillna(0.0)
den = pd.to_numeric(d.woba_denom, errors="coerce").fillna(0.0)
ev = d.events
num = num.where(~ev.isin(ZERO_NUM), 0.0); den = den.where(~ev.isin(ZERO_NUM), 1.0)
num = num.where(~ev.isin(EXCLUDE), 0.0);  den = den.where(~ev.isin(EXCLUDE), 0.0)
d["wnum"], d["wden"] = num, den
spray = np.degrees(np.arctan2(d.hc_x - 125.42, 198.27 - d.hc_y))
d["spray_angle"] = spray
d["pull_angle"] = np.where(d.stand.eq("R"), -spray, spray)     # + = pull side, either hand
d["stand_R"] = d.stand.eq("R").astype(float)
sp = []
for y in range(2015, 2027):
    t = pb.statcast_sprint_speed(y, min_opp=5)[["player_id", "sprint_speed"]].rename(columns={"player_id": "batter"})
    t["game_year"] = y; sp.append(t)
sp = pd.concat(sp).drop_duplicates(["batter", "game_year"])
d["game_year"] = d.game_year.astype(int); d["batter"] = d.batter.astype(int)
d = d.merge(sp, on=["batter", "game_year"], how="left")

bbe = d[d.type.eq("X") & d.launch_speed.notna() & d.launch_angle.notna() & (d.wden > 0)].copy()
mu = bbe.groupby("game_year").wnum.mean()                      # league wOBA on contact, by season
bbe["y"] = bbe.wnum / bbe.game_year.map(mu)                    # era-neutral target: damage vs that season's average
w = np.exp(np.log(0.5) * (ANCHOR - bbe.game_year) / HALF_LIFE)
log(f"BBE {len(bbe):,}  coords {100*bbe.hc_x.notna().mean():.1f}%  sprint {100*bbe.sprint_speed.notna().mean():.1f}%")
log("league wOBAcon by season:\n" + mu.round(4).to_string())

m = HistGradientBoostingRegressor(max_iter=1200, learning_rate=0.04, max_leaf_nodes=63,
                                  min_samples_leaf=150, l2_regularization=1.0, early_stopping=True,
                                  validation_fraction=0.1, random_state=0)
m.fit(bbe[FEATS], bbe["y"], sample_weight=w.values)
log(f"fit in {m.n_iter_} iterations")
joblib.dump(m, OUT)
p26 = m.predict(bbe[bbe.game_year == 2026][FEATS]) * mu[2026]
a26 = bbe[bbe.game_year == 2026].wnum
log(f"2026 in-sample level {p26.mean()/a26.mean():.4f}  (predicted {p26.mean():.4f} vs actual {a26.mean():.4f})")
log("saved " + OUT)
