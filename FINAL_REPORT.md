# Final report — full review, 18 Nov 2026

Companion files: `ARCHITECTURE_REVIEW.md` (map), `AUDIT.md` (findings), `docs/review/*` (per-area detail),
`tools/eval/*` (harness, models, tests), `docs/review/results.jsonl` (every logged run).

## 1. Top findings and what was fixed
| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Every model number on the site is in-sample in time (xwOBA model fit on 2015-26 then rescored; Stuff+ graded by a fold trained on later seasons; park factors borrow future seasons; hand-fit constants fit and tested on the same seasons). CLAUDE.md's backtest r values are optimistic. | Critical | Documented; new models in `tools/eval` are point-in-time and player-grouped. Site models not yet replaced (see §5). |
| 2 | "Expected" stats contain actual outcomes (half of K%/BB% in xwOBA; actual strike rates in Command+/Pitching+; actual whiff/foul in xK%). | High | Documented; the new metrics separate stuff-only from results-informed versions. |
| 3 | Pitch models can memorize pitchers (pitcher-identifying inputs, random-row early stopping). | High | New pitch models grade each pitcher with a model that never saw him. |
| 4 | Location+ no longer exists for current seasons; its slot holds Command+, and older files still show the location model. | High | Documented; new Location+ rebuilt (§3). |
| 5 | Players with no 2026 line had no 2027 Marcel projection. | High | **Fixed** (PR #909): 852 hitters / 1194 pitchers projected, was 662 / 868. |
| 6 | A crashed page check published unchecked. | High | **Fixed** (PR #909). |
| — | Medium/low items (Ohtani VOR vs zero, Marcel inconsistencies, stale caches, service-worker trims, nERA PA mix …) | Med/Low | Listed in AUDIT.md, not yet fixed. |

## 2. Evaluation harness (`tools/eval`)
- **Data**: every regular-season pitch 2015-2026 from Savant (`fetch_all.py`, 8.0M pitches), MLB official lines (runs, ER, outs),
  Savant sprint speed and expected stats. `prep.py` → season files with FanGraphs-style wOBA bookkeeping; `tables.py` → player-season
  tables, full season and odd/even game halves.
- **Protocol** (`harness.py`): features in N vs outcome in N+1, both seasons ≥ 50 PA/BF, every season centred, weighted by N+1 sample;
  r overall and by N-season sample bucket. Reliability: odd/even game halves, k50 = sample where reliability = .5. Same-season r is secondary.
- **Leakage controls**: development pairs end at N+1 = 2025; the 2025→2026 holdout was scored once (`holdout.py`). Per-ball and per-pitch
  models are point-in-time (trained on seasons ≤ N) and grouped (the scored player's id group is held out). Player-level fits hold out the
  target season and the player's group. `test_leakage.py` guards these.
- **Survivorship**: pairs need 50+ PA/BF in both seasons; every metric is compared on the same pairs, so rankings are fair, absolute r is
  conditional on a player returning.

## 3. Models
**Hitting — true-talent xwOBA** (`hitfit.py`): ridge on season-centred skills, fit within CV to next-season wOBA:
K% and BB% (each empirically shrunk by its own reliability: K 54 PA, BB 109 PA), EV90, barrel%, hard-hit%, pulled-air%, GB%, PU%, whiff%,
zone swing, chase, zone contact, sprint, last two seasons' composite (weighted by their PA), age curve.
- Ablation (dev r, full model .570): drop EV group .537, drop prior seasons .547, drop K/BB .563, drop age .564, drop sprint .565,
  drop discipline .566, drop direction/type .566; ball-by-ball contact model and launch-angle consistency add **nothing** (.570 without) and
  were removed. Gradient boosting on the same inputs: .502 — the linear model is kept.
- **Paredes**: the new model rates him ~.315 against .33-.36 actual; his edge repeats but no tested input (pulled FB share, HR rate, park
  factor, actual-wOBA history, past residual) captured it. Known limitation.

**Pitching** (`pitchprep.py`, `pitchmodel.py`, `whiffmodel.py`, `pitcheval.py`): per-pitch target = count-based expected value in wOBA units
(balls in play at Savant's per-ball estimate, not the result).
- **Stuff+**: physical traits only (velo, IVB, HB, spin, extension, release, VAA/HAA, gaps to primary fastball, platoon), 100 = season mean,
  10 = 1 SD. Reliability k50 ≈ 13 BF.
- **xWhiff** (stuff-only whiff per swing): the stronger stuff signal (next K% r .522).
- **Location+**: location + count + pitch group, relative to the count/type average; k50 ≈ 75 BF; adds little to next season (r .06 RA9).
- **Pitching+**: ridge fit on next-season RA9 of shrunk Stuff+, xWhiff, Location+ (stuff-only version) plus K%, BB%, GB%, whiff, CSW,
  prior SIERA, age (full version). Adding the plate-discipline/results rates on top of stuff adds a lot (RA9 r .249 → .342).

## 4. Results — development (LOSO) and the untouched 2025→2026 holdout
Hitters, next-season wOBA, r:
| Metric | Dev pairs | **Holdout 2026** |
|---|---|---|
| Prior wOBA | .457 | .331 |
| Savant xwOBA | .503 | .428 |
| Savant xwOBAcon | .401 | .354 |
| Marcel | .528 | .425 |
| Site xwOBA (current; in-sample constants) | .536 | .443 |
| **New talent xwOBA** | **.570** | **.479** |

Pitchers, |r| with next season:
| Metric | Dev RA9 | Dev K-BB% | **Holdout RA9** | **Holdout K-BB%** | Holdout SIERA |
|---|---|---|---|---|---|
| Prior ERA | .173 | .226 | .147 | .173 | — |
| FIP | .251 | .352 | .210 | .299 | .318 |
| xFIP | .290 | .412 | .264 | .427 | .464 |
| SIERA | .323 | .513 | .270 | .489 | .499 |
| K-BB% | .310 | .553 | .246 | .498 | .476 |
| Site nERA (current) | .302 | .445 | .261 | .411 | .432 |
| Site Stuff+ (current)* | .264 | .419 | .323 | .529 | .568 |
| New Pitching+ (stuff/location only) | .249 | .469 | .213 | .497 | .466 |
| **New Pitching+ (full)** | **.348** | **.564** | .294 | .538 | .552 |

\* The current Stuff+'s 2025 grades come from the odd-season fold trained on 2020/22/24/**26**, i.e. it saw 2026 pitches — its holdout row is
contaminated by the very leak in finding 1 and is not a fair comparison. On development pairs (less contaminated) the new Pitching+ beats it
clearly; on the holdout the new model beats every clean benchmark.

## 5. Known limitations
- **Not wired into the site yet.** The new metrics live in `tools/eval`; replacing the site's xwOBA / Stuff+ / Pitching+ needs a build step
  (pitch-level scoring in the daily pipeline) and app.js display changes. Left for approval because it changes every number Sean sees.
- Paredes-type hitters are under-rated (above).
- Statcast bunt flag not kept (no `des`), so bunt hits sit in the contact data; RA9/ERA have no game-half splits (season-only reliability).
- The holdout is one season (416 hitters, ~470 pitchers): ±.04 on r.
- Stuff+ uses 2015-19 TrackMan and 2020+ Hawk-Eye without system-specific calibration (season centring absorbs level shifts only).

## 6. Next steps (ranked)
1. Wire new talent xwOBA and Pitching+ into the build (`build_data.py` scoring step + app.js), keeping the old ones beside them.
2. Retire the even/odd stuff folds for point-in-time models; same for the directional xwOBA model and park factors.
3. Fix the medium AUDIT items (Ohtani VOR, Marcel playing time/role, caches, service worker, data-sanity diff before publish).
4. Pitch-type-level Stuff+ by batter hand on the site; stabilization curves on the cards' tooltips.
5. More Paredes-type investigation (spray × launch interaction at the player level).
