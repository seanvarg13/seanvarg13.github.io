# Architecture review (Phase 0)

Read-only map of the site as of 18 Nov 2026. Detailed per-area maps, constant tables and line references are in
`docs/review/A_pipeline.md` (data pipeline), `B_models.md` (trained models), `C_hitting.md` (hitting build-up),
`D_pitching.md` (pitching metrics), `E_fantasy.md` (fantasy layer), `F_engineering.md` (build/publish/browser).

## Data sources and ingestion
- **Statcast pitch data** (pybaseball month pulls; Savant `statcast_search/csv` day pulls for spring/post), 2015-2026,
  regular season. Cached on the runner between runs (`~/.pybaseball`, `.cache/savant`).
- **MLB Stats API**: names, teams, positions, official lines, game logs, box scores (lineups), transactions, injuries,
  sabermetrics (FanGraphs wRC+/WAR), postseason lines (fetched in the browser).
- **Savant leaderboards**: batted-ball (Air%, Pull Air%), bat tracking, expected stats, sprint speed.
- **Other**: Baseball-Reference WAR files, FanGraphs fly-ball counts (removed), Lahman award votes, Smart Fantasy
  Baseball ID map, FanGraphs Steamer/ZiPS, NFBC/ESPN ADP.
- **Daily**: `.github/workflows/daily.yml` → `tools/cloud_daily.py` (gate `whats_new.py`, build, restamp, page check, commit to `main`).

## Feature engineering (tools/build_data.py)
Pitch flags (swing/whiff/zone/count states/bunts), PA rows with corrected wOBA bookkeeping, per-game day rows
(`days-h.js`, `days-p.js`), per-player season metrics, league constants per dataset (`consts`: lgERA, FIP constant,
SIERA shift, batted-ball-type wOBA values, wOBA scale), Mix buckets, park fields (from `hist/parks.js`), nERA.

## Models
| Model | Where | Inputs | Target | Algorithm | Training window | Validation |
|---|---|---|---|---|---|---|
| Directional xwOBA / xBA / xSLG | `tools/models/model3.py`, `model_bs.py`; release assets | EV, LA, sprint, pull & spray angle, side | era-neutral wOBA / hit / bases per BBE | HistGradientBoostingRegressor | 2015-2026, 3-yr recency half-life | random 10% early stopping; no season holdout; scored in-sample |
| Stuff+ family (whiff, bb type, foul, damage, location/swing/command variants) | `build_data.py` (`train_stuff_models`), `tools/models/train_stuff.py`; release asset `stuff_models.joblib` | pitch traits, release, VAA/HAA, FB deltas, usage/depth; location & count for loc/command | P(whiff\|swing), P(type\|contact), P(foul), damage | HistGradientBoosting | 2020-last season, two parity folds | random-row early stopping; season graded by opposite-parity fold (includes future seasons) |
| Park outcome models | `tools/build_parks.py` → `hist/parks.js` | EV, LA, pull, side (+venue, season) | out/1B/2B/3B/HR | HistGradientBoostingClassifier | 2015-2026 | in-sample cells, shrunk |
| Talent xwOBA (hitters) | `app.js` (`talentCore` etc.), mirrored in `build_career.py` | half actual / half fitted K%, BB%; HBP; xHR/FB (EV fit); 9-driver xBABIP; model extra bases; GB lean; parks | wOBA scale | hand-fitted linear pieces + linear weights | constants fit on 2015-2026 | scratch backtests, in-sample |
| Pitcher metrics (nERA, uERA, xK%, xBB%, Command+, Pitching+, xnERA, Rating) | `app.js` | rates, model expected rates, strike rates | ERA scale / rates | linear fits (ridge) + formulas | 2015/2020-2026 | scratch backtests, in-sample |
| Marcel 2027 / Steamer | `build_proj27.py`, `build_offseason.py` | official lines | counting stats | Marcel weights; Steamer import | 2024-2026 | none |

## Model output → fantasy values
Scoring presets (`FCATS`, `fPts`) turn official or projected lines into points. Rankings default to Steamer 2027
points (`projPts`), else xwOBA / nERA regressed by 80 IP. Mock draft: ADP = weighted median of published lists,
value over replacement under the room's scoring/roster (`mkVOR`), auction $ from Sean's league price curve by ADP rank.

## How the site uses it
Static GitHub Pages; the browser loads `data.js` + lazily the hist/day files and computes every pool, percentile and
model number in `app.js`; a service worker caches versioned files; `build.json` reload picks up publishes.

## Do Location+ and Pitching+ exist and work?
- **Location+** no longer exists as a displayed metric for seasons/levels with count-state rates. Its slot (`m.sloc`)
  now holds **Command+** (from actual Strike%, 1st-pitch and 3-ball strike rates via `XBBF`, app.js ~1314-1318).
  The build still computes the location-model numbers (`location_delta`, `pitching_grade`), kept as `m.sloc0`/`m.pitch0`
  and used inside the K%/BB% fits, `hist/similar.js` and `lgRatesP`. Older files / Double-A and below still show the
  location-model Pitching+, so the column means two things.
- **Pitching+** = Stuff+ + Command+ − 100 (per pitch: that pitch's Stuff+ plus the pitcher's single Command+ offset).
  It works (no broken paths found), but it is not a model output and half of it is an actual-outcome proxy.

## Artifacts, caches and constants
Model artifacts: release `models` (`v3_dir/ba/slg.joblib`, `stuff_models.joblib`, `versions.json`). Cached data: pybaseball
cache, `.cache/savant`, `.cache/milb`, `.cache/sabr`, `.cache/lineups`. Hardcoded constants with provenance are tabled in
the area files (league weights, PULL_LINE 16°, REF_MIN 300, XKH, TW_XBB, XBAB, TW_HF, TW_GB, XHRFB, UKF/UBB, XBBF, XKM,
CMD_K 150, KREL/KCONV, park k values, Marcel weights, price curve). Most fitted constants cite scratch scripts that are
not in the repo, so they can't be reproduced from it.
