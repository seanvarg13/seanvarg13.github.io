# Audit (Phase 1)

Findings consolidated from six area reviews (`docs/review/*.md` hold quotes and details). **Checked** = I confirmed it
in the code myself; the rest are the reviewers' reading, marked as such.

## Critical
1. **Every model number is in-sample in time; backtests in CLAUDE.md are optimistic.** Checked.
   - `tools/models/model3.py:63` fits xwOBA/xBA/xSLG on 2015-2026 and every season is rescored with that fit.
   - `tools/build_data.py:769` grades season Y with the opposite-parity fold, so 2022 is scored by models trained on
     2021, 2023 and 2025 (future data).
   - `tools/build_parks.py:161-163` pools Y-2..Y and borrows the nearest (future) seasons when short; the park cell
     models are trained on all balls 2015-2026.
   - Hitting/pitching constants (XKH, TW_XBB, XBAB, TW_HF, TW_GB, UKF, UBB, XKM, XBBF) were fit on 2015/2020-2026 and the
     quoted correlations were measured on those same seasons; term choices were made on the full set.
   - *Why:* any "predicts next season at r = …" figure on the site or in CLAUDE.md is inflated by an unknown amount.
   - *Fix:* point-in-time scoring (models and constants fit on seasons < Y), grouped holdouts, one locked holdout season.

## High
2. **"Expected" stats contain actual outcomes.**
   - Hitters' xwOBA uses half the actual K% and BB% (app.js 8316 `act: 0.5`, 8428; checked); xBB% takes the actual IBB rate.
   - Pitchers' Command+ / Pitching+ use actual strike rates (3-ball Strike% ≈ walk avoidance).
   - xK% (`XKM`) is a same-season fit on actual whiff, CSW and foul rates; xnERA's walks come from actual strike rates
     (reviewer D).
   - *Fix:* keep these as descriptive stats; build the talent metrics on expected/process inputs only and test them out of sample.
3. **Pitch models can memorize pitchers** (reviewer B, suspected).
   - The inputs include gaps to his own fastball, usage and arsenal depth, and early stopping uses random rows, so the
     same pitcher is on both sides.
   - CLAUDE.md's note that a retrain moved each pitcher's expected whiff 20-30% toward his actual is consistent with this.
   - *Fix:* group CV and early stopping by pitcher.
4. **Pitching+ and the Location+ slot mean different things by file** (reviewers B, D).
   - On files with count-state rates the slot is Command+; on older files it is the location model.
   - *Fix:* one definition, documented.
5. **Players with no 2026 line get no Marcel 2027 projection** (`build_proj27.py:87,143`; checked). They drop out of the
   Mock draft / Rankings projection.
6. **Publishing can go unchecked** (`cloud_daily.py:119`; checked): a crashed page check (exit code not 0/1) publishes anyway.

## Medium
- League anchors (xwOBA scale, xBABIP level, HR/FB level, xLevel, xneraShift) come from the same season's actual
  results. Fine for description; noisy early in a season; `xneraShift` depends on the listed pool (reviewers C, D).
- nERA mixes batters-faced and wOBA-denominator PA counts; intentional walks are treated differently in xwOBA and
  wOBA; untracked balls in play leave xwOBA but stay in wOBA (reviewer A).
- The fallback stuff-model trainer fits on the season it grades (`build_data.py:743-746`, reviewer B).
- Park models score their own training balls (`build_parks.py:109,190`, reviewer B).
- Ohtani's pitching value is measured against zero in `mkVOR` (app.js ~13684); his two halves are summed in the Mock
  draft and the League tab but are separate rows in Rankings (reviewer E).
- `mkVOR` fills replacement slots greedily in a fixed position order (reviewer E, suspected).
- Marcel inconsistencies: playing time doesn't use 5/4/3; role-based caps come from 2026 alone; aging applied to W/SV/HD
  (reviewer E).
- Hitters' xPts scale runs and RBI by xwOBA/wOBA, partly actual results (reviewer E).
- Stale caches: `mkPool`'s key ignores the ADP / projection files' arrival; `lgProjCache` ignores the league's scoring (reviewer E).
- Service worker: overlapping trims skip retiring old day files (`sw.js:37`); bad values can publish since the page check
  tests drawing, not values (reviewer F).

## Low
- `TW_WIN_ON = false` (app.js 8343; checked): window regression is off, while CLAUDE.md's 12 Nov entry says it is on.
- Rankings without Steamer use raw xwOBA, so tiny samples can lead (`boardProj`).
- Duplicate `gs` key in the arsenal day fields (handled, fragile).
- AB counted two ways for bunters; the spray formula is duplicated; the HR/FB piece centres fly-ball-weighted and PA-weighted means differently.
- Silent `catch` blocks on MLB API calls; the service worker evicts in insertion order; index.html fetch has no timeout.

## Tests missing
None of these have tests today: the stat math (unit tests), app ↔ build_career parity, temporal ordering (no
model/constant trained on a season ≥ the one it scores in a backtest), grouped CV, a data-sanity diff before publish,
service-worker trims, `whats_new.py`, a `pack_hist` round-trip.
