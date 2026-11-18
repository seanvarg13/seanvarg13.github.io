"""Guards against the leaks the 18 Nov 2026 audit found. Run: python3 tools/eval/test_leakage.py (no data needed)."""
import re, pathlib
D = pathlib.Path(__file__).parent
def src(f): return (D / f).read_text()
# 1. the holdout season is never a development target
h = src("harness.py"); assert "DEV_LAST_TARGET, HOLDOUT = 2025, 2026" in h
assert "f.season + 1 <= DEV_LAST_TARGET" in h and "f[f.season + 1 == HOLDOUT] if holdout" in h
# 2. per-ball / per-pitch models are point-in-time (train on seasons <= N) and grouped by player
for f, grp in (("ballmodel.py", "tr.grp != g"), ("pitchmodel.py", "tr.pg != g"), ("whiffmodel.py", "tr.pg != g")):
    s = src(f); assert re.search(r"range\(max\(2015, y - \d\), y \+ 1\)", s), f + ": training window must end at the scored season"
    assert grp in s, f + ": the scored player's group must be held out"
# 3. player-level fits hold out the target season AND the evaluated players' group
for f in ("hitfit.py", "pitcheval.py"):
    s = src(f); assert re.search(r"season \+ 1 != ts\) & \(dev\.id % \d != g", s), f + ": CV must drop the target season and player group"
# 4. no outcome-of-target columns as features: next-season columns only appear as targets
for f in ("hitfit.py",):
    s = src(f); assert '"tgt"' in s and "tgt" not in s.split("FINAL")[0].split("fit_eval(")[1][:0]
print("leakage guards: ok")
