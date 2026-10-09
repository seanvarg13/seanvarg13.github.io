# Sean's Site — how it is built, where the numbers come from, and how to change it

Live: **https://seanvarg13.github.io/** · repo: `seanvarg13/seanvarg13.github.io`

A fantasy-baseball site Sean built for himself: percentile cards for every hitter and pitcher, leaderboards,
a draft board, a fantasy-points page, and a Baseball-Savant-style player page. He reads it on his phone from
the hosted copy, so **anything that is not published does not exist for him**.

This file is for whoever picks the work up. Read it before changing anything.

---

## 1. The one thing to understand first

This repo is **two things at once**:

1. **The published site.** `index.html`, `app.js`, `styles.css`, `data.js`, `days.js`, `fantasy.js`, `hist/*.js`
   at the repo root are what GitHub Pages serves. They are *build output* mirrored from a Mac.
2. **A mirror of the build scripts**, under `tools/`. Those are the real source of the data pipeline.

**The daily update is moving to GitHub Actions** so it runs whether or not the Mac is on:
`.github/workflows/daily.yml` runs `tools/cloud_daily.py` at 4:45 New York time — the same build scripts from
`tools/`, the same steps as the Mac's `daily_update.py`, published as a plain commit on top of `main` (never a
force-push), with the download caches kept between runs. GitHub starts scheduled runs late on busy mornings (hours, sometimes), so the workflow has backup times
through the morning and each scheduled run only goes if it is past 4:40 in New York and `data.js` isn't through
yesterday yet. **That still wasn't enough** (27-28 Sep 2026: no scheduled run started before 10 am), so the real trigger is an
**outside timer**: cron-job.org POSTs a `workflow_dispatch` with `auto=1` at 4:45 New York time (Sean's fine-grained token,
Actions read/write on this repo only, lives there, not here); `auto=1` makes a manual run ask the same "already live?"
question as a scheduled one. A Claude routine ("Site daily update kick", 4:50) checks and kicks it too; GitHub's schedule stays as the last backup. **The stale-checkout guard** (8 Oct 2026): a run's checkout is main as it was when the run began, so a `tools/` script merged mid-run used to be ignored and its old output published (4 Oct's data.js, 7-8 Oct's career.js); `cloud_daily.py` now adopts main's copy of every build script before each step (`adopt_main_tools`, compile-checked) and, before each publish, re-runs every step of the run whose script or an import (`DEPS`: build_history → build_data, build_milb → both) changed on main after it ran — from the first stale step on, twice at most. `tools/cloud.json` is the switch: `{"daily": true}` =
the cloud publishes and the Mac's job and publisher stand down (they read the file from `main`); `false` = the Mac
publishes and the schedule does nothing (a manual run still works: Actions → Daily update → Run workflow, with
optional `steps`, `rescore` years and `dry`). The directional models are not in the repo: the Mac's publisher
uploads `model-workspace/*.joblib` and `versions.json` (the Python + package versions they were pickled with) to the
repo's **`models` release**, which the workflow downloads and pins against. **Retraining can run in the cloud too**
(30 Sep 2026): Actions → Retrain models (`.github/workflows/retrain.yml`) fetches every regular-season PA 2015-now
(`tools/models/fetch_pa.py`, past seasons cached), trains `model3.py` / `model_bs.py` under the release's pinned versions
(`MODEL_DIR`, `ANCHOR`, and `MONO=1` for the "harder is never worse" constraint on exit velocity — tried 30 Sep 2026 and put
back the same evening: same-season r vs wOBA .818 against the old models' .854, next season a tie; the workflow's `restore`
input takes a `models-prev-<date>` tag, puts those models back and rescores, no training), keeps the replaced
files on a `models-prev-<date>` release, uploads the new ones with `versions.json` saying `trained.by: github-actions`,
and then, in the same job, rescores every past season and postseason and rebuilds this one (`cloud_daily.py --rescore …`, then `--steps mlb`) — its own concurrency group, since a scheduled backup arriving in the daily group cancelled a queued retrain (30 Sep 2026). The Mac's publisher (`upload_models`) no longer
pushes an older model back over a newer one on the release — it fetches the newer one instead (its own kept in
`model-workspace/prev-<time>/`) and only sends `versions.json` with a model of its own.

**The switch is on (25 Sep 2026)**: a dry run and a real run matched the Mac's build (same players, same league
constants, 99.5% of values identical — the rest Statcast corrections the Mac's cache predates), so GitHub Actions
publishes every morning and the Mac's job stands down. The Mac setup below is still how the models are retrained and
uploaded, and the fallback if the switch is ever set back to `false`.

### The round trip — how an edit you make here actually takes effect

```
    this repo (main)                     Sean's Mac
    tools/build_data.py    --pull-->     draft-site/build_data.py     (sync_tools.py, before every build)
                                              |
                                              | build_data.py / build_milb.py / ... write data.js, days.js, hist/
                                              v
    root *.js, index.html  <--push--     draft-site-deploy/           (publish_github.py, force-push to main)
    tools/*                <--push--     the same scripts, mirrored back
```

* `tools/sync_tools.py` runs **first** in the daily job and again at the top of every publish. It compares the
  repo's copy of each script with the Mac's, using `.tools-mirror.json` (the git blob sha of every file as of
  the last publish) as the base for a three-way decision:
  * repo == local → nothing to do
  * local == last published → **the repo moved on, so the repo's copy is adopted on the Mac**
  * repo == last published → the Mac moved on, keep it; the next publish pushes it
  * both moved → **keep the Mac's file**, drop the repo's copy in `logs/tools-conflicts/` and say so loudly
* A pulled `.py` must `compile()` before it is installed, and whatever it replaces is kept in
  `logs/tools-backup/<timestamp>/`. A broken edit pushed from here cannot take the 5:30 job down.
* It only ever touches the exact paths in `FILES` at the top of `tools/sync_tools.py`. Adding a script to the
  mirror means adding a line there.

**So: to change the data pipeline, edit the file under `tools/` and push it to `main`.** It is picked up at the
next daily run or the next publish. To change the *site*, see the warning below.

### Editing the front end from here

`app.js`, `styles.css` and `themes.js` at the repo root **round-trip like the scripts** (they are in `FILES` in
`tools/sync_tools.py`): the published copies are byte-for-byte the Mac's `draft-site/` copies, so an edit merged to
`main` here is adopted on the Mac at the next sync and published back unchanged. Same three-way rules, backups
and conflict handling as the scripts; a `.js`/`.css` must be text and at least half the local file's size.

`index.html` does **not** round-trip — the published one is stamped (`?v=` hashes, `DRAFT_BUILD`), so it never
equals the Mac's template. Keep anything the page needs out of it: fonts, for one, are loaded by `themes.js`.
The stamps in the repo's `index.html`/`build.json` are rewritten by every publish; when merging here, recompute
them from the files (sha1 of the contents, first 10 hex) so the live page picks the change up at once.

Caveats: an edit lands on the Mac at its next sync (the 5:30 job, or the top of any publish), and a publish
started in the minutes between a merge here and that sync can still force-push the old copy back — check `main`
after a Mac publish if a change seems to have gone missing. If the Mac and the repo both changed a file since the
last publish, the Mac keeps its copy and the repo's lands in `logs/tools-conflicts/`.

---

## 2. Where things live

### On Sean's Mac — `~/Desktop/Fantasy Baseball/`

| path | what |
|---|---|
| `draft-site/` | the working tree: source, build scripts, generated data, `logs/`, `.cache/` |
| `draft-site-deploy/` | the git clone that is pushed to this repo — **generated, never edit** |
| `model-workspace/` | the trained models (`v3_dir.joblib`, `v3_ba.joblib`, `v3_slg.joblib`), their training scripts, and `pa_all.parquet` (every regular-season PA 2015-2026, ~30 MB) |
| `~/.pybaseball/cache` | pybaseball's Statcast day cache (large; only new days download) |
| `~/.github_token` | the publish token. Never in the repo, never printed. `~/.netlify_token` for the fallback |
| `~/Library/LaunchAgents/com.seanvargas.draftboard.plist` | the 5:30 am schedule |

### In this repo

| path | what |
|---|---|
| `index.html` | page shell; loads `defaults.js`, `themes.js`, `data.js`, `app.js` in that order |
| `app.js` | the whole front end, one IIFE, ~4,100 lines |
| `styles.css` | light + dark, every scheme |
| `themes.js` | colour schemes and fonts; sets scheme tokens on `<html>` before first paint |
| `defaults.js` | the site-wide Appearance default, written by `serve.py` |
| `data.js` | **generated** — `window.DRAFT_DATA`, the current season |
| `days.js` | **generated** — `window.DRAFT_DAYS`, per-game rows for splits and date windows (~14 MB, loaded on demand) |
| `fantasy.js` | **generated** — official counting stats + game logs for the fantasy pages |
| `hist/` | **generated** — one file per past season/level, plus `index.js` (search index), `career.js`, `minors.js` |
| `build.json` | `{build, at}` — the running page polls it and reloads itself when the id moves |
| `manifest.json`, `icons/` | home-screen web app |
| `tools/` | the mirrored build scripts (see §5) |
| `docs/site-README.md` | the long-form manual Sean wrote the site against — more UI detail than this file |

---

## 3. The data: where every number comes from

### Sources

| source | what is taken | how |
|---|---|---|
| **Statcast (pitch level)** | every pitch: `description`, `zone`, `type`, `bb_type`, `launch_speed`, `launch_angle`, `hc_x/hc_y`, `release_speed`, `release_extension`, `bat_speed`, `woba_value`, `woba_denom`, `events`, `stand`, `p_throws`, `inning_topbot` | `pybaseball.statcast()` month by month, cached in `~/.pybaseball`. Spring/postseason go straight at Savant's `statcast_search/csv` day by day (pybaseball clips those dates), cached under `draft-site/.cache/savant` |
| **Savant batted-ball leaderboard** | `air_rate`, `pull_air_rate` → **Air%** and **Pull Air%** as Savant reports them | `leaderboard/batted-ball?type=batter&year=…&csv=true` |
| **Savant bat-tracking leaderboard** | `avg_bat_speed` | `leaderboard/bat-tracking?…&csv=true` |
| **Savant expected stats** | `est_woba`, `est_ba`, `est_slg` → Statcast's xwOBA/xBA/xSLG; not shown any more, only the stand-in for xBA/xSLG on a past season not yet rescored | `leaderboard/expected_statistics?type=batter&year=…&csv=true` |
| **Savant sprint speed** | `sprint_speed`, a feature of all three directional models | `pybaseball.statcast_sprint_speed(min_opp=5)` |
| **MLB Stats API** | names, teams, positions, games by position, official AB/IP/ERA/earned runs, per-game logs, bio + draft (`people/<id>?hydrate=draft`), minor-league lines | `statsapi.mlb.com/api/v1/...` |
| **Savant minors search** | Triple-A Statcast; AA/A+/A come from Gameday play-by-play (calls, batted-ball type and location, the zone rebuilt from Gameday's pitch plot, no tracking outside FSL parks) | `build_milb.py`, cached under `.cache/milb` |

Everything is fetched anonymously — no API keys anywhere in this pipeline.

### The build scripts

| script | writes | notes |
|---|---|---|
| `build_data.py [--end DATE]` | `data.js`, `days.js` | the current season. Every MLB player who played ships (`MIN_PA_HITTER` / `MIN_BF_PITCHER` = 1, since 24 Sep 2026 — a 12-BF start had left River Ryan off the site); league constants still come from 20+ BF (`CONST_MIN_BF`), and the minors keep a 20 floor. ~1-2 min on a warm cache. All the knobs (`SEASON`, `GAME_TYPES`, `DEFAULT_MIN`, `REF_MIN_PA`, `PULL_LINE`, metric lists, card layout, score weights) are constants at the top |
| `build_history.py [years…]` | `hist/mlb-YYYY.js` (+ days) | re-runs `build_data.py` season by season for 2015-2025. `build_history.py index` rebuilds `hist/index.js` (the search index). `spring 2026 2025` / `post 2025 2024` build those game types as their own datasets — but the site is regular
season only now: `indexReady()` in `app.js` drops them from the index, so nothing offers them. Rows are player × handedness × venue — no date dimension, so past seasons have splits but not date windows |
| `build_milb.py [aaa|aa|ap|a] [year]` | `hist/<level>-YYYY.js` | Triple-A has real Statcast; lower levels have batted-ball type and location, and the zone from Gameday's pitch plot (`plot_zone`). **No bat speed** in the minors; the directional models run with sprint speed blank (Triple-A only scores — nothing else is tracked) |
| `build_fantasy.py [years…]` | `fantasy.js`, `hist/fantasy-YYYY.js` | official counting stats + per-game logs for hitters (`hg`/`hgk`, with fielding and GWRBI per game) and pitchers (`gk`), home / away on both — the Fantasy Leaderboard / Trending sum these for any date range and split + Savant expected stats, plus ESPN's bonus categories: grand slams (the API's bases-loaded `r123` split), cycles (hitter game logs), game-winning RBI (the schedule's scoring plays: the RBI that put the winners ahead for good), fielding A / PO / OFA / DPT, pitcher TB / GIDP / pitches. Points are computed in the browser from the chosen scoring preset (`FCATS` in `app.js` lists every category), so an ESPN setting change needs no rebuild |
| `build_fantasy.py lines [years…]` | `hist/fantasy-lines.js` | every past season's official lines (2015 on, no game logs) for the card's Fantasy ▸ By season table; static, rebuilt by hand when a season ends |
| `build_career.py` | `hist/career.js`, `hist/minors.js` | season-by-season + career tables on every card. Reads the search index, so run it **after** `build_history.py index` |
| `build_similar.py` | `hist/similar.js` | every qualified MLB player-season 2015-now ranked within its season (+ under-the-line players ranked against them), hand / role and pitch mix — the cards' cross-season Similar line. Seconds; after `build_data.py` and after a rescore, non-fatal |
| `build_trends.py` | `hist/trends.js` | League Trends: every MLB season's league totals (hitting rates pooled over every pitch / swing / batted ball from `hist/mlb-YYYY.js` rows + this season's `days.js`) and per pitch type from each pitcher's `ctx.arsenal` (usage, velo, IVB, HB, spin, Whiff%, xWhiff, GB%). A few seconds; runs after `build_data.py` (and after a rescore), non-fatal |
| `serve.py` | — | local server on :8787 with an "Update data" button; `--phone` binds to the LAN |

### Shapes

* `data.js` → `{meta, players}`. `meta` carries `season, through, built, hitterMetrics, pitcherMetrics, defaultMin,
  refMinPA, days, dayFields, pullLine, hitterWeights, pitcherWeights, hitterCard, hitterSub, pitcherCard,
  pitcherSub, consts, scoreNote` — i.e. **the card layout and the league constants ship with the data**, so adding
  a stat is usually a change in `build_data.py`'s constants plus a label in `app.js`.
* A player is `{id, name, team, type: "H"|"P", primary, pos, age, pa|bf, ab|ip, m: {…every metric…}, ctx: {…}}`.
* `days.js` → `window.DRAFT_DAYS["H592450"] = [[…], …]`, one array per game day, fields named by
  `meta.dayFields.H` / `.P` (`HITTER_DAY` / `PITCHER_DAY` in `build_data.py`). Splits, date windows and the
  rolling chart all sum these rows. **Appending a field is safe; reordering breaks every older `hist/` file.**
* `meta.consts` (the `K()` accessor in `app.js`) = `{lgERA, fipC, sieraShift, bbw:{gb,ld,fb,pu,ut}, lgwOBA,
  wobaScale: 1.25, pa9, wbb, whbp}` — derived per dataset, so a past season uses its own.

---

## 4. Stat definitions

Rates are on the pitch/PA populations you would expect; what follows is only what is non-obvious.

**wOBA bookkeeping.** Statcast's `woba_value`/`woba_denom` are corrected first: reached-on-error, fielder's choice
and FC-out get numerator 0 and denominator 1; sac bunts, truncated PAs, catcher's interference and intentional
walks are dropped from both. Everything downstream (wOBA, xwOBA, the directional models, nERA) uses the corrected
pair.

**Air% / Pull Air%.** Taken from Savant's batted-ball leaderboard so they match the site Sean compares against.
The pipeline also computes its own from the stringer's `bb_type` + `hc_x/hc_y`: spray angle is
`degrees(atan2(hc_x − 125.42, 198.27 − hc_y))`, flipped for right-handed hitters to give **pull angle**, and a
ball is "pulled" beyond `PULL_LINE = 16°` (16 matches Savant's Pull Air% best). Card **Air%** excludes popups;
Savant's "air" includes them.

**Barrel% / Hard-Hit% / Sweet-Spot% / bat speed / Avg EV.** Barrels are `launch_speed_angle == 6`. Hard-hit is
EV ≥ 95. Sweet-spot is 9-31° full credit and 8° / 32° half credit (the rounded edges). Avg EV and EV90 skip
bunts, as Savant's do. Bat speed averages **competitive swings** — everything at or above the hitter's own 10th
percentile swing speed, which is Savant's roughly-hardest-90% rule.

**xwOBA is the directional model, and only that** (Sean, 24 Sep 2026: "get rid of statcast xwoba completely").
Everywhere the site says xwOBA, xBA or xSLG — the headline, the rank, the leaderboards, the cards, the player page,
the rolling chart, the fantasy xPts — it means Sean's model (`xwd` / `dxba` / `dxslg` in `app.js`; the old
Statcast/Directional toggle and the `xws` column are gone). The build still carries Savant's `est_woba`/`est_ba`/
`est_slg`, but only as the stand-in for xBA/xSLG on a past season not yet rescored for them.

* Savant's xwOBA prices a batted ball by exit velocity and launch angle (plus sprint speed on weak contact) and
  is deliberately blind to *direction*. That under-prices a pulled fly ball and over-prices a hard ball hit the
  other way, which is exactly the effect Sean's hitting model is about — and why it was dropped.
* **dxwOBA** (`model-workspace/v3_dir.joblib`, trained by `tools/models/model3.py`) is a
  `HistGradientBoostingRegressor(max_iter=1200, learning_rate=0.04, max_leaf_nodes=63, min_samples_leaf=150,
  l2_regularization=1.0, early_stopping=True, validation_fraction=0.1)` over
  `[launch_speed, launch_angle, sprint_speed, pull_angle, spray_angle, stand_R]`, trained on every regular-season
  batted ball 2015-2026 with a **3-year recency half-life** (`exp(ln0.5·(2026−year)/3)`) — because the 2023 shift
  ban changed what a pulled grounder is worth and an equally-weighted fit is more than half shift-era. The target
  is **era-neutral**: the wOBA value divided by that season's league wOBA on contact, multiplied back by the
  current season's when scoring. Scoring 2026 off a fit through 2025: RMSE 0.3588, R² 0.606, level 0.999
  (Savant's xwOBAcon: RMSE 0.4246, R² 0.449).
* **dxBA / dxSLG** (`v3_ba.joblib`, `v3_slg.joblib`, `tools/models/model_bs.py`) are the same recipe against two
  more targets — whether the ball is a hit, and how many bases. Sacrifices are out of the BBE set. Calibration:
  dxBA level 0.998, dxSLG level 1.002; league dxBA .228 vs real BA .2272 / xBA .2293, dxSLG .3691 vs SLG .3650.
* In all three, only **tracked** balls in play are scored; an untracked one keeps its real result, and a
  strikeout/walk/HBP keeps its actual wOBA value. Per-PA contributions are summed into the day rows
  (`dnum`, `dbsum`, `dssum`) so splits and date windows re-derive them.
* Retraining needs `model-workspace/pa_all.parquet` and takes a couple of minutes; it is **not** part of the
  daily job, and the `.joblib` files are not in this repo (too large, and nothing here can run them).

**uK% / uBB% / uERA** (pitchers, computed in `app.js`, not in the build):
* **uK%** (`UKF` / `rateFit`, Sean 28 Sep 2026) = the league's K% moved by his Whiff% (+0.90 a point), Strike% (+0.89),
  Swing% (−0.52), Z-Contact% (−0.16), Chase% (−0.10) and Zone% (+0.05), each against the dataset's league rate
  (`lgRatesP`), fitted over every 100+ BF pitcher-season 2015-2026: 2.00 K% points from a 300+ BF pitcher's real K% vs
  2.21 for the old `−26.975 + 0.933·Whiff% + 0.409·Strike%` (`UK`, kept as the last fallback), same error fitted and
  unseen, weights steady across seasons. CSW% added nothing and muddled the weights; levels without Chase% / Z-Contact%
  use a four-rate fit. **uBB%** (`UBB` / `uBBFrom`, Sean 28 Sep 2026) = the league's BB% moved by his Strike%, Zone%, Chase%, Swing%,
  Z-Contact% and Whiff% each against the dataset's league rate (`lgRatesP`), a straight-line fit over every 100+ BF
  pitcher-season 2015-2026 (−1.01 BB% per Strike% point, +0.21 Zone%, +0.09 Chase%, −0.05 Swing%, −0.10 Z-Contact%,
  +0.06 Whiff%): 1.46 BB% points from a pitcher's real BB% vs 1.73 for the old walk-rate-at-his-Strike%-percentile, and
  better on next season's BB% than his own BB%. Strike% bands and a tree model did no better. Levels without Chase% /
  Z-Contact% use a four-rate fit, then Strike% alone. **Starters and relievers have their own weights for both** (Sean, 3 Oct 2026: the
  walk estimates "all overshooting", then "two separate models, one for sps and one for rps"): `UKF` / `UBB` lead with a `role: "SP"` and a
  `role: "RP"` fit (every 100+ BF pitcher-season 2021-2026 by his role that season, BF-weighted, centred on each season's 20+ BF league
  rates), the pooled fit last as the fallback; `rateFit` takes the role, `V()` carries `role: p.primary`, `impliedKBB` reads `pv.role ||
  pv.primary` (the game log's per-game rows and `stuffUeraCore`'s copy carry it too). At the same rates a reliever walks ~0.7 BB% more and
  strikes out a little less per whiff; the pooled fit had every regular starter ~0.3 BB% high (the 20 best control starters a point high)
  and relievers ~0.5 low. Leave-one-season-out 2024-26: starters' uBB% bias +0.21 / +0.30 / +0.32 → −0.07 / +0.04 / +0.06, error 0.92 /
  1.04 / 0.98 → 0.90 / 1.02 / 0.94; relievers' bias −0.5 → −0.1; uK% bias halved for both. The remaining compression (the lowest-walk
  starters still ~0.8 high, the wildest ~1.2 low) is the fit regressing the extremes, as an expectation should; curvature terms, CSW% /
  SwStr% and a tree model did no better. **Then the full fits, the same evening** (Sean: "get it as accurate as humanly and AIly possible
  ... use all years 2020-2026"): the role fits at the front of `UKF` / `UBB` now use the six rates plus CSW%, SwStr%, GB%, Popup%, FB velo,
  extension, Stuff+, Whiff+, Location+ and, uncentred (`raw`), the arsenal's location-aware xWhiff over his swings (`xwl`), fastball share
  (`fb`), pitch types thrown 5%+ (`ntypes`) and age — `arsenalExtras(p, t)` builds those from the season's arsenal (`xwl` from the day rows'
  `stnl` / `stwl` in a window), `V()` carries them as `ex`, `rateFit` leaves `raw` keys uncentred, `impliedKBB` merges `pv.ex` into the rates,
  `lgRatesP` carries the extra league rates. Ridge (λ 3), BF-weighted, every 100+ BF pitcher-season 2020-2026 with a Stuff+ grade, centred on
  each season's 20+ BF league; Pitching+ left out (= Stuff+ + Location+ − 100, it split the fit into ±2 offsetting weights). The six-rate
  role fits are next in line, the pooled 2015-2026 fits last, for a level or file without grades. Held out season by season 2021-2026:
  starters' K% error 1.55 → 1.37 and BB% 0.95 → 0.91, relievers' K% 2.33 → 2.13 and BB% 1.42 → 1.37; EV / HH / Brl% and a tree model added
  nothing. Inside Stuff uERA / Pitching uERA the model's whiff rate replaces his and SwStr% / CSW% move with it (`stuffUeraCore`), so the full
  fit sees one consistent set of expected rates. Wheeler 2026 reads K% 28.6 / BB% 7.1 against 29.9 / 7.3 (the six-rate fit: 26.3 / 8.5).
  **Plus the count-state rates, later that night** (Sean, on Wheeler 2025 reading 5 K% low and 2 BB% high: "is there anyway to improve the
  fit of both? ... without blending actual stats"): `pitch_flags` builds, from `balls` / `strikes`, the first pitch of a PA and whether it
  was a strike (`fp` / `fps`), three-ball pitches and the strikes among them (`b3` / `b3s`), two-strike pitches and their swings, whiffs and
  in-zone pitches (`s2` / `s2sw` / `s2wh` / `s2z`); `pitcher_metrics` turns them into `FStrk_pct`, `B3Strk_pct`, `S2Whf_pct`, `S2Sw_pct`,
  `S2Zone_pct` → `m.fstrk / b3strk / s2whf / s2sw / s2zone`, and `PITCHER_DAY` carries the eight sums so `V()` re-derives them in a window.
  Pitch-level process like Strike%, never the plate appearance's result. The front fits in `UKF` / `UBB` add the five (same recipe:
  ridge, by role, 2020-2026); held out season by season starters' K% error 1.37 → 1.12 and BB% 0.91 → 0.54, relievers' 2.13 → 1.75 and
  1.37 → 0.93; Wheeler 2025 reads 32.8 / 5.9 against 33.3 / 5.6. Tested and left out as too close to the result: the share of pitches thrown
  ahead / behind and the share of PAs reaching two strikes (they'd take starters to 0.83 / 0.38 — Sean can have them if he wants them).
  Files built before the fields fall through to the full fit without them, then the six-rate role fits, then the pooled ones; every
  season needs a rescore to carry them (dispatched 3 Oct 2026).
  **pERA and the projected rates (Sean, 3 Oct 2026: "take stuff+ and pitching+ and come up with one thing that projects a pitchers whiff
  rate gb% pu% by pitch and overall ... and also a pERA stat that shows players who maybe got fewer ks and more walks ... than they should have
  ... avoid biasing it too much where it isnt going to be applicable to next year")**: a pitcher's **next season** from this season's pitches.
  `NKF` / `NBB` are the full fits' inputs fitted to the *following* season's K% and BB% (pairs 2020 → 21 … 2025 → 26 with 100+ BF both years,
  by role, ridge λ 5, weighted by the smaller sample, each rate against its own season's league; process only — his actual K% / BB% as inputs
  were left out), trimmed to what held when each input was dropped in turn: the two-strike rates (whiffs, swings, zone) are **noise for next
  year's K%** (a sixth of his pitches) and are out; first-pitch and three-ball strike rates stay for BB% only. `nextKBB(pv)` runs them. Held
  out by target season: starters' next K% error 2.55 (his own K% 2.81, the same-season fit 2.83), BB% 1.27 (1.41 / 1.44); relievers' 3.42
  (4.00 / 3.82) and 1.86 (2.20 / 2.15). **Per pitch** (`PPITCH` / `projPitch` / `projRates`): each pitch's stuff-only and location-aware
  chances blended by what carried over to the same pitch type's rate the next season (pitcher × type with 100+ both years, 2020-26):
  whiff = .009 + .389 xWhiff + .584 xWhiff·loc, GB = 3.16 + .616 xGB + .306 xGB·loc, PU = .25 + .680 xPU + .274 xPU·loc — the spots carry
  the whiffs, stuff the batted balls, and the pitch's own last-year rate added nothing on top. Next-season error per pitch: whiff 5.6 points
  (its actual rate 6.3), GB 7.6 (8.9), PU 3.5 (4.0). Overall = whiffs by swings, GB / PU by balls in play (`stuffRates` / `pitchRates`
  through the same blend — day-row sums in a window). **pERA** = `stuffUeraCore(…, cal = null, next = true)`: `nextKBB`'s K% / BB% on the
  projected GB / PU mix through `underlyingERA`. Backtest 2021 → 22 … 2025 → 26, 100+ IP both years: next season's ERA r .439 / mean abs
  error .72 against ERA .267 / .96, FIP .355, SIERA .394, nERA .388. History: the lucky side regressed as advertised (Manoah '22, Gonsolin
  '22, Hendricks, Lauer '22, Matz '21, Abbott '25 …); the unlucky side is mixed (Cease '23 → '24 came back, Pfaadt / Bradley didn't) — the
  stat says what the pitches deserve, not that the pitches hold. In `app.js`: pool stats and sorted lists `pera nk nbb nwhf ngb npu` (lower
  negated like uERA; `NEXT_KEYS`), `statsFor` for an unlisted player, `metricValue`, sort keys, `SIDE_P` / `LB_EXTRA_P` columns pERA · pK% ·
  pBB% · pWhiff% · pGB% · pPU% (Stats panel group **Next season**; the Advanced column set carries pERA), `VS_P`, the glossary, and a **pERA
  card tab** (`BTABS_P` after Pitching+, `renderNextTab`: Pitch / Use / pWhiff / pGB / pPU each over this season's actual, All pitches, then
  the uERA box titled pERA — Exp = next season, Act = this one — and the projected mix). The keys are `n*` because `pwhf` / `pbb` are
  Pitching+'s halves. **Pitching uERA is this season's again** (it read next season's for an evening, PR #276); uERA / Stuff uERA /
  Pitching uERA are same-season reads, pERA is the forward one. A file without an arsenal has no pERA ("–").
* **uERA** (`underlyingERA`) puts those two rates on the balls he actually allowed: his ground-ball and popup
  shares stand, the air balls left over are split into line drives and fly balls at the *population's* ratio, and
  every ball in play is then worth the league's average wOBA for its type (`consts.bbw`). The resulting wOBA is
  put on the ERA scale as `lgERA + (xw − lgwOBA) / wobaScale · pa9`. So a high line-drive rate never punishes
  him, but putting the ball in the air does.

**xK%** (hitters; `XKH` / `xKFrom` / `lgRatesH` in `app.js`; Sean, 28 Sep 2026) = the league's K% moved by his Whiff% (+0.99 a
point), Z-Swing% (−0.21), O-Swing% (−0.27) and the strike rate of the pitches he sees (`strk`, +0.52), each against the
dataset's league rate (hitters with 20+ PA, PA-weighted), fitted over every 100+ PA hitter-season 2015-2026: 1.72 K% points
from a 300+ PA hitter's real K%, the same on unseen seasons. Z- / O-Contact added nothing once Whiff% is in, and per-pitch
swinging / called strike rates did worse. **Unlike uBB%, it does not beat his own K% at next season's** (2.76 vs 2.60
points; the two averaged 2.55) — it says what his swings and misses imply, not a forecast. Added to `V()` for every view;
a Leaderboard / Compare column (`LB_EXTRA_H`), the Spreadsheet Stats Plate Discipline table, and the hitter card's
Contact section right under K% (`PCT_COLS_H`; Sean, 28 Sep 2026).

**xwOBAcon** (hitters; set in `V()` beside `xk`; Sean, 28 Sep 2026) = (xwOBA × PA − wBB × BB) / BBE, his xwOBA on contact —
a Leaderboard / Compare column (`LB_EXTRA_H`). **pxwOBA** (xwOBA with his strikeouts moved to his xK%) was built the same day and
**removed everywhere on 30 Sep 2026** (Sean: "that stat is not needed"; it forecast no better than xwOBA) — saved column lists,
sorts and comparison picks drop `pxw` on load. Don't bring it back unasked.

**Arsenal Opt.** (pitchers; `arsenalOpt` / `aoptBase` in `app.js`; Sean, 28 Sep 2026: "how much the pitcher optimizes their
arsenal %s to throw pitches that ... get more swing and miss"): his pitches' xWhiff averaged by his real usage, minus the
same pitches averaged at a typical mix (the league's share of each pitch type among pitchers who throw it 3%+, scaled to his
arsenal), in whiff-per-swing points; pitches under 3% use ignored. Checked 2024-26: real Whiff% ≈ typical-mix xWhiff + ~1.0 ×
Arsenal Opt. (weight .94-1.06), and his real Whiff% tracks the mix-weighted xWhiff (r .77) far better than the typical-mix
one (.64). Full season only (`V()` sets `aopt` when no window / split). On the Stuff tab (with its percentile), a Leaderboard
column (`LB_EXTRA_P`) and a sortable Stuff+ board column (the pitcher's value on each of his rows). A whiff-only lens: a
sinkerballer leaning on his sinker for grounders reads negative by design.

**MLB-equivalent uERA** (the minors' rows in Season Stats, `milbU` / `MILB_X` in `app.js`): the level's Whiff%,
Strike%, GB% and Popup% shifted up to the majors by a fixed table per level, then uERA against that season's MLB pool.
The table comes from `tools/models/milb_translate.py` (same-season pairs at two levels, 2021 on, reliability-corrected
shifts, chained to MLB); re-run it by hand and paste the printed `MILB_X` when it goes stale.

**Mix wOBA** (`mixw`, hitters; built in `pitch_flags()` / `build_hitters`, re-derived from `mixsum` / `mixn` day
fields in a window): the average over his balls in play (bunts out) of the dataset's wOBA for each ball's bucket (GB,
PU, and LD / FB each pulled, straightaway or oppo — ground balls are one bucket on purpose: by direction they tracked
handedness and speed, not the mix). Per ball in play — walks and strikeouts don't enter it (Sean,
26 Sep 2026). Past seasons get it when rebuilt.

**Stuff+** (`add_stuff` / `stuff_grade` in `build_data.py`, `stuffFrom` in `app.js`; Sean, 26 Sep 2026): each pitch
graded on its traits alone — velocity, spin rate and axis, induced vertical / horizontal break (lefties mirrored), release
height and side, extension, arm angle, batter side, and velocity / break gaps to his primary fastball — plus, in the whiff
model only, **arsenal depth**: this pitch's usage and how many pitch types he throws 5%+ of the time that season (`use`,
`depth`, `STUFF_WHIFF_ONLY`; Sean, 27 Sep 2026 — first-half xWhiff → second-half Whiff% .655 → .679 on 2026; 10%+ .665,
"effective number" .674; command habits — zone / edge rate, location spread — tested and left out, they predicted worse);
**no location, no count**. **Since 2 Oct 2026** (Sean, after Kyle Bland's pitch-model thread: "add all of it in"; backtested
on 2025 / 2026 halves and 2024→25 / 2025→26 seasons, models trained only on earlier years): the **pitcher's hand** (`lefty` — the same
mirrored pitch gets ~2 more whiffs / 100 swings and ~3 more grounders / 100 BIP from a lefty) and **location-neutral VAA / HAA**
(`approach_angles`: the angle left after the plate height / side it crossed at, per pitch type) are inputs to every model, and two
models join: **foul** (P(foul | contact)) and **damage** (wOBA on a ball in play, regression). Batted-ball+ prices contact at
`STUFF_DMG` = half damage, half the GB / PU / air mix, and adds `kF` ERA per foul% point (contact per pitch × `STUFF_FOUL_RV` 0.085
runs × pitches per nine); `stuff_parts` in the build = `stuffParts` in `app.js`. Next-season r: runs saved per 100 pitches .40 →
.49, xwOBA allowed .44 → .53, K-BB% .45 → .56. Tested and left out: ball / called-strike chances (better within a season, worse
the next — command), seam-shifted-wake proxies, release point vs his fastball, grading vs all pitches. New sums: day fields
`stf / std / stbf / stbd`, arsenal-day `f / d`, `ctx.arsenal` `xfoul / xdmg`, `consts.stuff` `lgF / kF / lgD / dmg` and two more
numbers on each `types` entry; files built before them grade on whiff + type alone. Same day: `COLS` gained `home_team` — the
season being built had been graded without its park adjustment (only the training seasons had it).
**Fixed models + Pitching+ / Location+ (Sean, 3 Oct 2026: "add in the location aspect ... base it off all prior years ... the fixed
model", then "whiff+, bb+ and location+ ... feeds into pitching plus ... a separate model from the stuff plus, but still have both
predict whiff% and gb% and pu%")**: `tools/models/train_stuff.py` trains all the models (whiff, batted-ball type, foul, damage, whiff / batted-ball type again **with location**, and since the
same day the two command models below — eight in all) on 2020 (the first season with spin axis) through the last finished season and
saves `model-workspace/stuff_models.joblib`; `.github/workflows/train_stuff.yml` runs it under the release's pinned versions (16 Nov,
and by hand), keeps the replaced file on a `stuff-prev-<date>` release, uploads to the `models` release and rescores everything; the
daily workflow downloads it with the directional models and `add_stuff` → `load_stuff_models` grades with it (`_grade_stuff`;
`train_stuff_models` is the fallback when the file is missing — the old season-plus-two training). Build scripts pass `prior` as a
function so the training seasons aren't loaded unless needed; the minors / spring / postseason callers load only the reference season
when the file exists. Tested: 2020-25 grades 2026 as well as 2024-25 (same-season r Whiff / GB / PU .760 / .802 / .657 vs .771 /
.798 / .647, next season identical) and Stuff+ moves less year to year (r .861 vs .847). **Two families, both predicting Whiff% /
GB% / PU%**: Stuff+ = Whiff+ + Batted-ball+ − 100 from the stuff-only models (unchanged); **Pitching+** = the same from the
location-aware pair (`location_features`: lz = height as a share of the batter's zone, lx = side, + away from the batter — never
seen by the stuff models); **Location+** = Pitching+ − Stuff+ + 100. A location-aware chance is P(whiff | swing) / P(type | contact)
*at that spot* (over every pitch a ball in the dirt reads 80% whiff), so each is carried **with the stuff-only chance on the same
pitches**: swings `st_nl / st_wl / st_ws` (+ the type's `st_bwl / st_bws`), balls in play `st_nb / st_gl / st_pl / st_gs / st_ps` (+
`st_bgl / st_bpl / st_bgs / st_bps`); day fields `stnl stwl stws stbwl stbws stnb stgl stpl stgs stps stbgl stbpl stbgs stbps`,
arsenal-day `nl wl ws nb gl pl gs ps`, `ctx.arsenal` `xwhfl locp xgbl xpul pitp whfpl bbpl` (null under 5 swings / balls in play),
`consts.stuff` `lgWL lgWS lgGL lgPL lgGS lgPS` and `types[pt][6..11]`. `location_delta` (= `locDelta`) prices what location adds:
whiffs at kW over his swings, the GB / PU / air mix at kB over his balls in play; `pitching_grade` / `pitchingFrom` add it to the
Stuff+ halves → `m.pitch / pwhf / pbb / sloc` (card Stuff section: Stuff+, Whiff+, Batted-ball+, **Pitching+, Location+**, velo,
extension — `PITCHER_CARD` + `PCT_COLS_P`; Leaderboard columns in `LB_EXTRA_P`; Stuff tab and Stuff+ board columns Pitching+ /
Whiff+·loc / BB+·loc / Loc+ / xWhiff·loc / xGB·loc / xPU·loc, re-based against type like the stuff ones; `stuffPlusLoc` is the one
call for a summed row — V() and the game log). **Pitching uERA** (`puera`, Sean the same day: "give pitching plus a uERA") = Stuff uERA
with the Pitching+ rates — `pitchRates` (day sums `_stnl / _stwl` over swings, `_stnb / _stgl / _stpl` over balls in play in a window;
the arsenal's `xwhfl` by swings and `xgbl / xpul` by balls in play otherwise) through `stuffUeraCore`; pool stats, a Leaderboard /
Compare column (`LB_EXTRA_P`), `VS_P`, and a uERA box (`pitchUERA`). **Pitching+ is its own card tab** (Sean, 3 Oct 2026: "on a separate tab ... as
stuff+"): `BTABS_P` has `pitching` after `stuff`, and `renderStuffTab(p, st, g, "pitching")` draws the same table for the location
family (Pitching+, its halves, Location+, xWhiff / xGB / xPU) with Pitching uERA under it; the Stuff tab keeps the stuff-only
columns, Stuff uERA and Arsenal Opt. 2026: xWhiff·loc vs Whiff% r .847 (xWhiff .740); Location+ 100 ± 4. Tested the same
day and left out: the count (nothing on top of location), a run-value regressor in place of the component build (FanGraphs' recipe:
next-period r runs .50 → .39, K-BB .58 → .49), the primary fastball's own xWhiff as an input for the secondaries (+.005-.01).
`COLS` / `STUFF_TRAIN` / build_milb's `TRACK` carry `sz_top` / `sz_bot` for the location. **Park-adjusted** (Sean, 29 Sep 2026; `park_offsets` / `STUFF_PARK`): before grading, each pitch's
velocity, ride, run and spin are taken back to a neutral park — a two-way fixed-effects fit (pitch = his own pitch-type average that
season + the park × pitch type offset, alternated four times so home staffs don't bias their park), shrunk by n / (n + 400) and
centred per type. Found 29 Sep 2026: Coors takes ~2.4-2.9" of four-seam ride, Tampa / Miami / Houston / San Diego add ~0.5-1.1",
Rogers Centre ~0; on Jul-Aug 2026 the adjustment roughly halved each park's home − away gap in the model's whiff / ground-ball
chances. Only the model's inputs move — the arsenal table's velo / IVB / HB / spin stay as measured (`stuff_features(d, park=False)`).
Needs `home_team` (kept in `STUFF_TRAIN`); a frame without it (some minors data) grades unadjusted. Past seasons pick it up when
rescored. `HistGradientBoostingClassifier`s are **trained at every build** on this season plus the two before (`STUFF_YEARS`;
tested 26 Sep 2026 on 2026: a third season helped slightly, a fourth to sixth or recency weights added nothing) (no model
file): P(whiff | swing) and P(ground ball / popup / air ball | contact). They combine on uERA's weights: a Whiff% point is
0.933 K% points (`UK`), each K removes a ball in play worth the league BIP value (`kW` ≈ 0.10 ERA per point); a ball in
play is worth the league wOBA of its type, air balls at the league's line-drive share (`kB` ≈ 0.20 ERA per .010).
**Stuff+ = 100 + % of runs saved** = Whiff+ + Batted-ball+ − 100, **graded against pitch type only** (Sean, 27 Sep 2026:
"vs all pitches" removed everywhere): every pitch's baseline is the league's mean chances for its own type (`st_bw/bg/bp`,
day fields `stbw/stbg/stbp`, `stuff_grade_type` / `stuffFrom`), so 100 = an average four-seamer for a four-seamer and his
grade is his pitches' type-relative grades averaged by use — the Stuff tab's All pitches row and the headline are the same
number. Files built before that lack the baselines and grade against all pitches until rebuilt. **Strike+ and a location-aware
Pitching+ / Location+ were built and dropped the same day** (Sean: "i just dont know what the new ones are adding") — the
strike model mostly restated the Strike% already on the card; don't bring them back unasked. Whiffs carry more weight because their spread
is bigger (SD 8.4 vs 4.9 in 2026). Checks on 2026 with a 2025 fit: whiff AUC .64; pitcher xWhiff vs actual Whiff% r .67,
xGB vs GB% r .75; Stuff+ half-to-half r .91 (actual Whiff% .72). Day rows carry `stn/stw/stg/stp` so windows and splits
re-derive it; `ctx.arsenal` holds the per-pitch table (`meta.arsenalFields`); with a window or split the Stuff tab's table re-sums `hist/ars-<season>.js` instead (`arsenal_daily` / `arsenalView`: pitcher × day × hand × venue × pitch type, started flag included, ~8 MB, loaded only then — Sean, 26 Sep 2026). A failure in the step costs only the grades.
**The minors get Stuff+ too** (Sean, 27 Sep 2026): Triple-A, and Single-A's Florida State League parks (Gameday has no
tracking, so `fsl_tracking` in `build_milb.py` matches Savant's minors-search rows on game / PA / pitch number — the same
cached day files Triple-A reads). `add_milb_stuff` trains the models on that MLB season and the two before and passes the
MLB season as `ref` to `add_stuff`, so league means and each pitch type's baseline are MLB's: a minors Stuff+ is graded
against MLB pitches of its type. Past seasons (MLB or minors) get Stuff+ when rebuilt — the workflow's `rescore` input
takes years for MLB and `aaa-2025` / `a-2024` tokens for the minors. MLB 2015-2019 have no spin axis or arm angle, so
their grades are rougher. **Stuff uERA** (Stuff tab, `stuffUERA` in `app.js`): uERA with xWhiff / xGB / xPU in place of
his real Whiff% / GB% / PU%; walks and every rate but Whiff% from his actual numbers (the stuff model can't see strikes). It's also a
Leaderboard column (`suera`, `LB_EXTRA_P`; pool stats in `pool()` / `statsFor`, rates from `stuffRates`: day-row sums in a
window, the arsenal otherwise).

**Command models, xBB%, Pitching uBB% and Command+ — built and REMOVED the same evening (Sean, 3 Oct 2026: "get rid of the command models
entirely i dont want them, go back to what the bb% estimates were before"; earlier that evening: "would there be any way to incorporate a pitchers command and
ability to generate chases, stay in the zone and throw strikes and avoid balls in the model", "improve like the whiff gb pu models and
also be accurate towards like walk rates? i want to be able to make the pitching uera bb% more accurate", "ok yeah try that")**: two
more models in `train_stuff_models` (so the fixed file holds eight) — **swing**: P(swing) from the pitch's traits (the whiff model's
inputs) plus its spot (`lx` / `lz`), how far outside the zone it crossed (`edge`, feet; the plate's half-width plus a ball's radius,
the batter's own top and bottom) and the count (`balls` / `strikes`); **call**: P(called strike | taken) from type, spot, edge, count,
batter side and hand (`command_features`, `STUFF_CMD`, model keys `swing` / `call`, columns `scols` / `ccols`; pitchouts, intentional
balls and bunts out of the training). Per pitch (`_grade_stuff`): strike chance = P(swing) + (1 − P(swing)) · P(called), chase chance =
P(swing) out of the zone, swing-and-miss chance = P(swing) × the location whiff chance — summed as `st_cn / st_cs / st_ck / st_co /
st_cso / st_ci / st_csi / st_cwi / st_cw` (graded pitches, swing chances, strike chances, out-of-zone pitches and their swing chances,
in-zone pitches, their swing and swing-and-miss chances, swing-and-miss chances on every pitch), day fields `stcn … stcw`, arsenal-day
`cn cs ck co cso stk osz` (the last two: strikes and out-of-zone swings that happened on the graded pitches), `ctx.arsenal` `xstk stk
xchs chs` (per pitch type: xStrike% vs Strike%, xChase% vs Chase%), and on each pitcher `m.xstrk / xswing / xosw / xzcon / xwhfa` —
the Strike%, Swing%, Chase%, Z-Contact% and Whiff% his pitches deserved where he threw them (`build_pitchers`; a window or split
re-derives them in `V()`). `COLS` / `STUFF_TRAIN` carry `balls` / `strikes` (and `zone` for training); `build_milb.py` gives every
Gameday pitch the count it came in (the feed's count is the state after it), so Triple-A and the FSL parks get them too. In `app.js`:
**xBB%** (`xBBFrom`, `XBB_MAP`) = the uBB% fit run on those expected rates instead of his actual ones, each against the league's
expected rate (`lgRatesP` carries both; Zone% is his own); **Pitching uBB%** (`pubb`, `CMD_BLEND` 0.4) = 0.6 uBB% + 0.4 xBB%, the walk
rate inside Pitching uERA (`stuffUeraCore` / `impliedKBB` take a `bbX`; the pool's `puera`, `statsFor` and the tab's `pitchUERA` pass
`V(p).m.pubb`); **Command+** (`cmd`) = 100 + 100 · kBB · (lgBB − xBB) / lgERA with kBB = (wBB − lgB) / 100 / wobaScale · pa9 — a walk
priced against a ball in play on uERA's scale, 1 point = 1% of runs like Stuff+ (`cmdFill`, set on every `V()` for pitchers). All five
are `SIDE_P` / `LB_EXTRA_P` columns (Stats panel group "Command"; Command+ in the Stuff column set), Command+ in the Pitching+ tab's
sub-head. **xStrike% / xChase% were columns too, for an hour** (Leaderboard, the Pitching+ tab's pairs, the Stuff+ board) and came off
at Sean's say the same evening ("they look way too inaccurate" — the fixed models read a couple of points under this season's actual rates,
which the fit's league centring absorbs but a side-by-side pair doesn't); the rates stay on `m` / the arsenal / the day rows for xBB%.
**The app no longer reads any of it**: uERA and Pitching uERA both walk at the actual-rate uBB% as before, `impliedKBB` / `stuffUeraCore`
have no walk override, there is no xBB% / Pitching uBB% / Command+ column or Stats group, and saved column lists / sorts drop `xstrk xosw cmd
xbb pubb` on load. The build side (the two models in the fixed file, the `st_c*` sums, day fields, arsenal-day fields, `ctx.arsenal` `xstk stk
xchs chs`, `m.xstrk …`) is still there and inert — strip it at a future retrain if the file size matters. Don't bring any of it back unasked. **Backtest** (scratch `cmd.py`, models fitted on the two seasons before, 300+ BF, r / mean abs error in BB% points):
same season, xBB% alone .713 / 1.19 (2024), .625 / 1.28 (2025), .712 / 1.15 (2026) vs uBB% .833 / .93, .744 / 1.00, .802 / .98;
next season (2024 → 25, 2025 → 26) xBB% .561 / 1.29, .564 / 1.25 vs uBB% .603 / 1.27, .502 / 1.42 and his own BB% .558 / 1.40,
.563 / 1.43; the 0.6 / 0.4 blend .609 / 1.23, .558 / 1.29 next season at .816 / .735 / .799 same season (a half-and-half blend .606 /
1.23, .566 / 1.27 at .804 / .724 / .791 — the 0.4 weight keeps more of the same-season fit). Refitting uBB%'s weights on the expected
rates, or on both sets, did no better. The expected rates track the actual same-season (Strike% r .85-.88, Swing% .80-.82, Chase%
.73-.75, Z-Contact% .74-.82, Whiff% .76-.84); expected Strike% predicted next season's Strike% better than actual in 2025 → 26 (.685 vs
.603) and worse in 2024 → 25 (.651 vs .695). **For K% the expected rates added nothing** (uK% from them: same-season r .67 vs .90) and
a refit on both sets matched the site's uK%, so uK% is unchanged. Files built before the fields show "–" for the five columns and no
xStrike / xChase pairs, and Pitching uERA walks at uBB% there (`pubb` null → `impliedKBB`'s own).

**The expected whiff rate inside Stuff uERA / Pitching uERA is calibrated (Sean, 3 Oct 2026: Pitching uERA "gets close on the whiff rate ... but
it undershoots the k% very often")**: the models' expected Whiff% is compressed (its spread across 300+ BF pitchers is ~80% of the real
one — a tree model leans to the middle) and on a season the fixed models never saw it can sit off level (2026 read 2.6 points hot, so every
K% ran 2.6 high and the bottom-20 K% 5.8 high). uK% was fitted on real Whiff%, so `pool()` (`calOf`) centres the expected rate on the pool's
real league Whiff% and stretches it by the ratio of spreads (`sorted.calS` for the stuff rates, `sorted.calP` for the location ones; the
pool's 300+ BF pitchers, 20 needed) before `stuffUeraCore` hands it to `impliedKBB` — `statsFor`, the Stuff / Pitching+ tabs' boxes use the
same. Tested 2024-26 on 300+ BF pitchers: Pitching uERA's K% error 1.93 / 1.95 / 3.14 → 1.82 / 1.85 / 2.00 points, bias +0.25 / +0.23 /
+2.63 → −0.1, the top-20 K% undershoot 3.0-3.5 → 2.4-2.7 (what's left is the model's own compression beyond a linear stretch), next
season's K% r .72 / .66 vs .71 / .62 for uERA's own uK%; Stuff uERA the same shape. The displayed xWhiff pairs stay the models' raw numbers;
only the K estimate changes. Tested the same evening and declined by Sean: blending actual and expected Whiff% (0.3 / 0.7 beat either for
next season's Whiff%, r .77 vs .74 / .76; his gap over the model repeats at r .29) — "no dont do actual and expected blend"; an expected
swinging-strike rate (expected swing × expected whiff per swing) in place of the per-swing model — worse everywhere (same-season K% r .70 vs
.77, next-season Whiff% .68 vs .76), the swing model adds noise. His own K% stays the best forecast of next season's K% (r .75 / .67).

**Model candidates tested and left out, 3 Oct 2026** (Sean: "do all that but park factors for directional xwoba"; scratch `bt8.py` /
`dxw.py` / `framing.py`, every candidate scored on 2025 and 2026 same-season halves and 2025 → 2026 / 2024 → 2025 next-season):
*Stuff+* — seam-shifted wake done properly (the axis the movement implies against the measured axis, and movement per rpm),
the closest sibling pitch (movement + velo distance, its velo gap), monotonic velo / extension, batter quality (the batters' shrunk
whiff rates, scored faced or neutral): all within ±.01 of the current model. *Pitching+* — count-relative location with the distance
to the zone's edge (better same-season, worse next, the command pattern again), location consistency (nothing), batter quality
(+.02 same-season whiff and +.014 forward on 2026 halves, +.006 / +.009 next-season 2026, but −.009 forward on 2025 halves and
−.002 on 2024 → 2025, GB / PU a point lower throughout — not robust). *Directional xwOBA* — bat speed, swing length, attack angle,
direction and tilt (2024-25 fit, scored on 2026: RMSE .3589 vs .3600 for the same two seasons without them, hitter-level r .899 vs
.895, with one fewer training season), a weak / hard contact split for sprint speed (R² +.001); the calibration table by EV × LA ×
direction found hard fly balls to centre over-priced in 2025 (100-105 mph, 25-40°: predicted .661, actual .526, n 1,542 — the ball
and the season, not a feature; the per-season anchor absorbs most of it). *uBB%* — catchers' framing out of Strike% (a called-strike
model's residual per catcher-season, shrunk, credited by the pitches he caught): adjusted Strike% predicts next season's BB% at
r −.474 vs −.486 raw. None of it ships; don't re-run them unasked. What did ship is a display setting: **Table format ▸ Regress small
samples** (`state.tbl.shrink`, `shrinkM` / `priorMeans` in `V()`, `viewKey` carries `:rg`): in a window or split every listed rate is
pulled toward the reference pool's full-season average with w = n / (n + 120), n = PA or batters faced in the window. Off by default.

**BABIP luck** (hitters; `babip_stats` in `build_data.py`, `babipFrom` in `app.js`, day field `wbh`; Sean, 27 Sep 2026):
BABIP = non-HR hits / non-HR balls in play (Statcast's, so sac bunts count — a heavy bunter reads ~.005 under the
official figure); xBABIP = the directional xBA's expected hits less his HR, over the same balls; **BABIP luck** = his hits in
play above expected × the wOBA value of his own average hit in play, in wOBA points; **BIP reliance** = % of his wOBA
numerator from hits in play (how much a BABIP swing moves him; league ~30-90%, middle 58%). They live in the hitter card's
**BABIP bottom tab** (`renderBabipTab`; Sean, 27 Sep 2026: "a separate tab of its own") — not the percentile box, whose
height is locked (a BABIP section there made it scroll). Left: luck, Exp / Act / Diff for BABIP, AVG, SLG, wOBA on the card's
dates and splits, hits over expected, wOBA at expected BABIP. Right: reliance, where his wOBA comes from (official line,
linear weights `LW`), what a ±.030 BABIP swing does, and BABIP by season (`fantasy.js` + `hist/fantasy-lines.js`).
BABIP / xBABIP are leaderboard / Compare columns. Luck and
reliance are coloured as risk (hib false). Also: `mixsum` used to be truncated to an int in the day rows,
so every window / split Mix wOBA read far too low (full-season values were right) — fixed 27 Sep 2026; past seasons need a
rebuild to pick it up.

**Mix ERA** (`mixERA`): the ERA his batted-ball distribution *alone* is worth — same league-value-per-type
machinery, but K% and BB% held at the pool's, so it is the mix and nothing else. ~4.15 is average, lower is
better.

**Luck-neutral ERA / nERA** (`neutral_era` in `build_data.py`): every ball in play takes the league's average
wOBA for its batted-ball type, strikeouts/walks/HBP stay as they were, result put on the ERA scale the same way.
BABIP and HR/FB luck wash out while a ground-ball profile keeps its value. (uERA is nERA *on top of*
process-implied K and BB.)

**WSGP** (`wsgpFrom`): the flat average of his Whiff%, Strike%, GB% and Popup% **percentiles** — the four rates a
pitcher owns before a ball is fielded. Percentiles are against whichever pool is in effect, so a split, a date
range or a past season re-ranks him within that pool.

**FIP / SIERA.** FIP uses a constant re-derived per dataset so the population averages its own ERA (official
earned runs over Statcast innings). SIERA is Swartz's 2011 form shifted by `sieraShift` for the same reason.

**Hitter rank** is the wOBA percentile blend: `brl 40.5, zcon 16.9, ocon 17.2, ev 11.6, zmo 9.0, osw 4.5,
pull 0.2` over percentiles (already flipped so 100 = best). **Pitcher rank (Rating)** is `PITCHER_SCORE_WEIGHTS` in `build_data.py`, shipped as `meta.pitcherWeights`: **Whiff% 55, Strike% 30, Mix wOBA 15** over percentiles (Sean's own call a few minutes after the 50 / 20 / 20 / 10 below; the pool
ranks Mix wOBA before the score and `placeIn` does too, and the card's Skills section is those three) (Sean, 4 Oct 2026: "the four skills in order of importance, ability to get Ks, avoid walks, get gbs,
and get popups" — process, not outcomes; 50 / 50 Whiff% / Strike% before). Backtest 2020-26 against next season's ESPN points per inning,
starters 100+ IP both years (relievers 40+): the old score r .51 / .47, this one .56 / .49; K% / BB% in place of Whiff% / Strike% would
be .61 but they're outcomes; SwStr% ≈ Whiff% (kept Whiff%); Chase% adds nothing to Strike% for next year's walks (r −.03 on what Strike%
leaves) and gets weight 0 in every best grid; Stuff+ and pK%−pBB% together would reach .66 but Sean wanted the plain four skills. `data.js`
was patched by hand the same day so the Rating changed before the next build.

**Percentile pools.** Hitters are always ranked against hitters with **300+ PA** (`REF_MIN_PA`), pro-rated inside
a date window or split; the Min PA box only controls who is *listed*. Pitchers use the Min IP pool. Percentiles
count ties at half (`insertPct`), and lower-is-better metrics are stored negated in the sorted arrays.

**Fallbacks.** Below Triple-A there is no directional xwOBA (nothing tracked to score), so there the hitters' headline and
rank are wOBA and the player page has no xwOBA row. Triple-A has it since 30 Sep 2026 (sprint speed blank). The directional
xBA/xSLG models do run in the minors (with sprint speed missing); where nothing is tracked (AA, `tracked < 5%`) they
fall back to BA/SLG (`PCT_FALL` in `app.js`). Past MLB seasons whose `hist/` file predates the xBA/xSLG rescore show
Statcast's xBA/xSLG under those names until it runs (their xwOBA is already directional); the minors never show
Statcast's.

---

## 5. `tools/` — what is mirrored

| file | on the Mac |
|---|---|
| `tools/build_data.py`, `build_history.py`, `build_milb.py`, `build_fantasy.py`, `build_career.py`, `build_trends.py` | `draft-site/` |
| `tools/daily_update.py` | the 5:30 job |
| `tools/publish.py` | mirrors the site into `draft-site-deploy` and stamps cache-busting versions; also the Netlify uploader |
| `tools/publish_github.py` | the publisher in use — commits and force-pushes `main` |
| `tools/sync_tools.py` | the round trip described in §1 (scripts, `CLAUDE.md`, and the root `app.js` / `styles.css` / `themes.js`) |
| `tools/serve.py` | local dev server |
| `tools/install_schedule.sh` | installs/removes the launchd agent |
| `tools/models/model3.py`, `model_bs.py` | the directional models' training scripts, in `model-workspace/` |
| `tools/models/milb_translate.py` | fits `MILB_X` (the minors-to-MLB rate shifts) from `hist/`; repo only, run by hand |
| `tools/build_proj27.py` | the Mock Draft's 2027 projections → `hist/proj-2027.js`; repo only, run by hand |
| `tools/add_baserunning.py` | fills the Base Running numbers into already-built `data.js` / `hist/mlb-YYYY.js`; repo only, run by hand |

Not mirrored, on purpose: `github_site.json` / `netlify_site.json` (account config), `~/.github_token`,
`.cache/`, `logs/`, `*.joblib`, `pa_all.parquet`.

---

## 6. The schedule, and how publishing works

**`tools/daily_update.py`, every morning at 4:45** so the site is live by 5:30 (launchd agent
`com.seanvargas.draftboard`, installed by `install_schedule.sh`, whose `HOUR`/`MINUTE` set it; if the Mac is asleep it
runs at the next wake). Changing the time needs `bash install_schedule.sh` run once on the Mac — syncing the script
alone does not re-register the agent. In order:

1. `sync_tools.py` — adopt anything edited in this repo
2. `build_data.py --end <yesterday>` (MLB)
3. **publish** — so the site is current early rather than stale all morning
4. `build_milb.py aaa <year>`, then `aa ap a <year>`
5. `build_fantasy.py`, `build_history.py index`, `build_career.py`
6. **publish again**

`caffeinate` holds the Mac awake for the run. Log: `draft-site/logs/daily-<date>.log`, symlinked as
`logs/daily.log`, 30 days kept. MLB alone is ~25 min; the minors add an hour or more. Off days are cheap.

**`tools/publish_github.py`** (`python3 publish_github.py`):
1. `sync_tools.pull()` — so this push does not put an old script back over a fresh edit here
2. `publish.sync()` — copies the site files into `draft-site-deploy`, mirrors `tools/` + `CLAUDE.md` +
   `docs/site-README.md`, then **stamps** every asset reference in `index.html` with `?v=<sha1 of contents>` and
   writes `build.json`. The running page polls `build.json`; when the build id moves it reloads itself, which is
   how a phone's home-screen app picks up a publish instead of sitting on a week-old copy.
3. one commit, **force-pushed** to `main`, then waits for the Pages build and prints `LIVE <url>`

The history is **squashed to a single orphan commit on the first publish of each month** (and whenever the local
repo passes 1 GB), so `main`'s history is rewritten routinely and is not worth treating as a record. A merge
commit made here survives only as *content* — which is enough, because the content is mirrored back to the Mac.
`.nojekyll` is written on every publish. Netlify (`publish.py`) is the fallback when there is no GitHub token and
is deploy-limited.

---

## 7. Conventions Sean expects

* **Publish after every change.** On the Mac that is `python3 publish_github.py`; from a chat working on GitHub it
  is merging to `main` (with the stamps recomputed). He checks on his phone against the hosted copy; an
  unpublished change is invisible to him. Sean's main chat now works from GitHub, not the Mac.
* **Changes apply to mobile and desktop** unless he names one. `:root[data-view="mobile"]` overrides live at the
  end of `styles.css`. Position-sticky breaks on iOS under clipped ancestors — do not reach for it.
* **The player page's box height is locked.** "the height is perfect now, don't ever change unless i absolutely
  specify." Since the page became a card (§8) it takes the card's height (`sizePPage()`'s `#modal-body` branch); the
  `#xboard` branch below only runs if the page is ever drawn outside the modal again. `sizePPage()` sets `--ppage-top` from the page's offset **in the document** (`rect.top + scrollY`),
  not the viewport — measuring the viewport while the page is scrolled reads smaller every render and the boxes
  grow ~84px each time. That bug has been fixed twice; do not reintroduce it.
* Code style: dense, comment *why* not *what*, prose comments in Sean's voice, no ceremony. `app.js` is one IIFE
  with no build step, no framework, no dependencies. Keep it that way.
* The site must work offline-ish and load fast on a phone: `days.js` and `hist/*` load on demand only.
* `README.md` (→ `docs/site-README.md` here) is the long-form manual and is kept up to date with real changes.
  It is deliberately **not** served by the site.

---

## 8. Open to-dos and known issues

* **Historical rescore — scheduled.** Sean said go (25 Sep 2026). `daily_update.py` now ends with a self-checking
  step: after the final publish it rebuilds every past MLB season whose `hist/mlb-YYYY.js` has no numeric `dxba`
  (`build_history.py <years>`, then `build_career.py`, then publishes). ~2 hours the first time, a no-op after.
  Until it has run, those seasons show Statcast's xBA/xSLG under the site's names. The minors have no directional
  xwOBA, so their lists lead with wOBA.
* **The percentile sections have no run values, fielding (OAA), sprint speed or spin.** Not in this data.
  Acknowledged gap, not a bug.
* **The player page is a popup card** (Sean, 24 Sep 2026: "identical in every measure"): `renderExplore()` opens his
  card in the site's one `#modal` via `showPageCard()`, with classes `pagecard` (no ×) and `pagebg` (white with interlocking square double spirals, each chained into the next, whole chains alternating navy and light blue — two masks, `--swirl-a` / `--swirl-b`, Sean 26 Sep 2026; since 27 Sep drawn by `buildSwirl()` in `app.js` as an SVG in `--swirl-img` with each navy / light-blue hand-off faded through the mid colour, colours from the theme, the masks the fallback —
  pattern — Sean, 26 Sep 2026: "I don't really like the slant design" — masked in the theme's colours, instead of the dimmed list). Same element, classes and
  `playerView()` as a card off a list, so a change to one is a change to the other.
* **One lifted look** (Sean, 28 Sep 2026, from cron-job.org's screenshot): every card, panel, dropdown, button and tile that
  stands off the page has square corners (Sean, 28 Sep 2026 evening: "hard and not soft" — every radius in `styles.css` is 0
  but true circles, 50%) and a plain navy border, **no shadow** (Sean: "instead of the shadows just do a border"): 2px on
  cards, panels and dropdowns (`--lift-line`), 1px on buttons and tiles (`--lift-edge`); `--lift-card` / `--lift-menu` /
  `--lift-btn` are `none` (the block near the end of `styles.css`). The soft all-round shadow of that morning is gone, and so is every other drop / offset shadow in the stylesheet
  (`--shadow` is `none`; Sean: "eliminate the shadow stuff and just do regular borders") — only thin rings round bubbles /
  headshots and inset marker lines are left. Don't add shadows back unasked. A down-right shadow
  and a bevel were tried the same afternoon and dropped — Sean: the morning's version "looks better". Don't bring the
  bevel back unasked. Also from that pass: the card's × is a navy button like the rest, Star is outlined (secondary) while
  Filters stays solid, 6px between the card's band and its first section, the phone's card tabs are one sideways-sliding row
  (faded at the right edge, the picked tab scrolled into view in `renderBelow`), and dark mode darkens the swirl and the
  white ground under it.
* **The minimal pass** (Sean, 28 Sep 2026: "I like the minimalistic look", then "do all of them"): the list toolbar wraps
  onto a second line instead of scrolling off the edge; the list's foot is one line (the colour scale, then Colour key ·
  Stat glossary · How this page works as links that open in the text window, then the layout switch — `renderChrome`'s
  notes); the pager is plain numbers with only the current page filled navy; the pattern behind pages runs at 20%, both
  layers; borders are 2px navy for the outer card and 1px inside it; the sorted column's values are bold, not boxed. The
  block at the end of `styles.css`.
* **The minimal pass, second round** (Sean, 29 Sep 2026: "do all of those changes"): the block at the very end of
  `styles.css` plus a few `app.js` changes. No stylesheet capitals or wide tracking anywhere (`text-transform` /
  `letter-spacing` forced off site-wide), semibold buttons and headings; the swirl at 8% with Appearance ▸ Background pattern
  (per device, `draft2027.pattern`, class `nopattern` on `<html>`); the header's pages are plain words, current one underlined,
  and a **More** menu (made in `app.js`, a third `NAV_GROUPS` entry, filled in `renderChrome`) holds Appearance, Colour key,
  Stat glossary, How this page works and the layout switch — nothing sits under the lists any more; the list toolbar is
  position + **Filters** (typing in its minimum box redraws the list, not the panel — `state.keepPop`, so the cursor stays; one dropdown, `GRP_TABS` as tabs across its top — Filters · Stats · Splits · Dates · Table
  format, the last used opens first; since 30 Sep 2026 one fixed size, `#pop.grppop` + `--pop-top` from `placePop`, tabs and
  the `popfoot` buttons pinned, the middle scrolling; minimum beside Sort by; One / Multiple seasons first in the season row so
  it never moves; the column order a drag-and-arrows list, `.olist`); desktop rows ~38px, a
  phone's second line just the team. Card: bottom tabs Compare · Season Stats · Stuff
  (pitchers) · Game Logs · Fantasy · Mix (hitters) / More (nERA, uERA; members as a small row under the strip) — Spreadsheet
  Stats, Rolling and the hitters' BABIP tab were taken off the strip (Sean, 30 Sep 2026; their renderers are still in `app.js`); Poor / Average / Great only on the first chart (`pctSvg`'s `scale`); section names in the charts as written, not
  capitals; plain initials, a ▾ on the season picker, a plain ×. Home opens on one line (no title, search or buttons).
  **Taken back the same night** (Sean, 30 Sep 2026: "why'd you get rid of the light blue ... and not actual buttons"): the
  pager's pale-blue strip and the card's tabs as centred outlined buttons (picked one light blue) stay — don't flatten them
  again unasked; the Stats / More members are a centred row of the same buttons.
* **The minimal pass, third round** (Sean, 29 Sep 2026): list rows' second line is his positions · PA (team and hand in the
  name's tooltip); rate cells drop the % (the header carries it, `colLab`); the Leaderboard opens on 8 stats (`LB_SLIM`, set once
  over any saved list via `state.lb.slim`, which also stops the old column migrations re-adding theirs); the card's stat line is
  PA · G / IP · G / GS (`sampleParts`); no "Every page" tiles on home; Rankings' list bar shares the toolbar's row (its own row
  on a phone); Fantasy's positions are one pill beside Hitters / Pitchers and its search sits in the Filters fold; panel section
  names are small grey labels.
* **The minimal pass, fourth round** (Sean, 30 Sep 2026: "ok to all of those changes"): no initials tile when there's no
  headshot (an empty tile of the same size); the card's "full season" note only shows when a filter is on; **on a desktop the
  card's percentile box stops at its charts** (`sizePPage`: `min(natural, the old fill-the-card height)`), so the tab strip sits
  right under them — Sean approved closing that gap, the card itself keeps its size; every heading inside the card's tabs
  (`.rollname`, `.secname`, `.cgroup`) in the title's type; the Leaderboard / Trending have no summary line beside Filters
  (`#tsum` hidden); a row's season only shows in a span of seasons; Per page lives in Filters ▸ Order and minimum
  (`perPageField`; Fantasy keeps its pager's); Fantasy's note is just its "More about these numbers" link until opened; "Games
  through …" moved from the desktop header (`.stamp` hidden) to the foot of the More menu; the sorted column (`.hot`, Fantasy's
  `.fsorted`) was a light tint of its percentile colour with navy digits (undone 30 Sep 2026 evening: full colour again).
* **The minimal pass, fifth round** (Sean, 30 Sep 2026: "do all of those"): the card's Star is a ☆ / ★ right after the name
  (`.staricon`, the panel unchanged); the season picker sits under the name as "2026 ▾ MLB" (`.ptitle.pinline`, "Percentiles"
  dropped; no title column / row of its own); cards open on Season Stats and Compare is the strip's last tab (`pbtabReset` puts a
  saved Compare back to Stats once per visit); the list toolbar is one button — the position picker is the Filters dropdown's
  first tab (`GRP_TABS` starts with `positions`; the button reads "SS · Filters" when a position is picked); the pager has no « /
  »; no "Rank" / "Rk" over the rank numbers; Fantasy's four page buttons are one pill (`.fpage`); Compare moved from the header
  into the Leaderboards menu (the header is Home · Fantasy · Leaderboards · More); the credit line under every page and the home
  page's data note are at the end of the Stat glossary (`.gcredit`; `creditLine` is gone); Game Logs have no group-label row
  (`tr.ggrp` hidden, the rules between groups stay). A toolbar dropdown closes on a page change. Later that night: the card's Filters button sits at the end of the PA · G line (`.hstrip`, which must stay
  `overflow: visible` — the desktop Filters panel hangs out of it), and the band's bottom rule is navy (`--rule`).
* **The minimal pass, sixth round** (Sean, 30 Sep 2026: "I like everything but 3-5"): the card's info line drops the season (the
  picker says it); **Filters is dressed as the Hitting / Pitching switch** (a one-button `.seg`, `.phfilt`, pressed while open) and a
  two-way player's switch moves beside it at the end of the PA · G line (on a phone that line runs under the ×, `margin-right: -44px`),
  so the band is a row shorter; **Share** was a small link beside the star (removed in the eighth round); the
  page behind a popup card was hidden while it was up and **shown again the same night** (Sean: "i actually dont want the stuff
  disappearing behind the player card") — don't hide it again unasked; **tapping a bar opens a note** under it (`statPop`: the glossary line, the league middle from the pool's sorted list, last
  season's value and percentile); ▲ / ▼ after a value for a 5+ point percentile move on last season were tried and **dropped the same
  night** (Sean: "get rid of the up and down arrows") — the tap note still gives last season. A pinned section name on a phone (`.secstick`) was tried and taken
  back the same night (Sean didn't like the headers staying) — don't bring it back unasked. Not done at his say: the headshot frame, a narrower label
  column, darker middle bubbles, swiping between players.
* **The minimal pass, seventh round** (Sean, 30 Sep 2026: "I like these all except don't do 1 yet"): **thin frames** — the list
  card, popup card, its tabs' box, home cards, the header and band rules at 1px (`--lift-line` too); **section rules** under the
  percentile charts' and the card tabs' headings a thin grey (`--secrule`; `svsecrule` is a 1px rect); **recent players** — the
  header search, tapped empty, lists the last 5 cards opened (`noteRecent` in `playerView`, `draft2027.recent`, per device);
  **press and hold a column name** on the lists for its note (`holdNote` / `colNote`: glossary + the pool's middle; a tap still
  sorts); **filter chips** on the card — each filter in effect (dates, hand, home / away, SP / RP) a chip with its own × in `.mrank`;
  **swipe down to close** a popup card on a phone (from the band, or anywhere once scrolled to the top; closes only — swiping between
  players was declined); **home** is the leaders card plus Your players only once something is starred; the leaders card links to the
  Leaderboard, and each list's name (xwOBA → / Stuff+ → / uERA →) opens its full list — hitters by xwOBA, the Stuff+ board, pitchers by
  uERA (Sean: "from the home page I can access the leaderboard"). **Taken back within the
  hour** (Sean: "go back to the old leaderboards table format and old format for all tables"): one-line list rows (Pos / PA
  columns), Show more instead of page numbers, one-line home rows and Game Logs' last-10 view — the lists have two-line rows and
  numbered pages again, Fantasy its pagers, Game Logs every game. Don't bring those back unasked. Idea 1 (the info line up on
  the season line) is only in the Card Header Comparison artifact, not built.
* **Desktop lists without the white card** (Sean, 30 Sep 2026: on the Stuff+ board "get rid of the outer box, it feels
  pointless", then on the Leaderboard "stick the filters button into the blue bar ... make the leaderboard itself bigger and get
  rid of the outer white stuff"): on a desktop the **Leaderboard and Trending** have no white card round the list — Filters (`#tbtns`)
  moves into the pager's blue bar (`seatFilters`, called from `renderPager` and put back in the toolbar before the bar is cleared,
  on a phone and on every other page; `body.filtbar`), the toolbar row hides unless it carries a note, and the table takes the room.
  The **Stuff+ board, League Trends, Call-up Watch and Weekly Planner** lose both the white card and the board's own frame
  (`#pitchboard`): their filters sit on the ground over the table. Rankings, Draft board, Fantasy, Eligibility and every phone
  layout keep the card. **Centred** (Sean, 30 Sep 2026): the Leaderboard / Trending table sits with equal space under the header
  and above the bottom — on a desktop 18px each (the empty toolbar row and the card's bottom padding go), on a phone the two 10px
  gaps plus the home-bar strip split evenly (`margin-top: 10px + inset / 2`, no bottom margin).
  **Phones too** (Sean, the same evening: "keep that and actually apply it to mobile"): Filters in the blue bar and no white card on
  a phone's Leaderboard / Trending, 10px round the table. In the bar, Filters keeps the toolbar's look — white, thin light-blue
  outline, light blue while open or in effect (`#pagertop .tbtns .tbtn`), not the pager's navy page button.
* **The minimal pass, eighth round** (Sean, 30 Sep 2026: "i like all of these, instead of 5 lets actually get rid of the share"):
  **Rankings and the Draft board** get the Leaderboard's treatment (`inBarModes`, the `body.filtbar` rules name them; the toolbar
  row stays while Rankings' list bar is in it), **Eligibility** loses its white card; **Fantasy's Leaderboard / Trending** keep
  only the page pill and Filters, seated in the pager's blue bar (`box._fbar`, put back by `renderFTable` after every redraw) —
  scoring, season, Hitters / Pitchers and position are the Filters fold's first row (`.fsetup`), What if keeps them on its bar;
  the **Stuff+ board family** wears the Leaderboard's pale header; the card's **level shows only when it says something**
  (`lvWorth` in `pageTitle`: a year with other levels, a minors season or a postseason one — "2026 ▾" alone otherwise); **Share is
  gone**; **idea 1**: team, positions, bats and age ride on the season line (`.mlinein`, "age" dropped), a row saved; the pager's
  numbers only show with more than one page (they already did); the **Filters dropdown's foot** is one "Clear" link (`popFoot`;
  changes apply as made, × closes); the **home page's data line** is small and grey.
* **Desktop card scrolls as one** (Sean, 30 Sep 2026: the tab strip "always visible at the bottom ... i dont like that"): the
  percentile box on a desktop card is its charts' full height (`sizePPage`'s `#modal-body` branch sets the natural height, no cap),
  so it never scrolls on its own and the tab strip sits under the last section, reached by scrolling the card like a phone's.
  This supersedes the locked-height / fill-the-card rule for the popup card and the player page on a desktop.
* **Desktop rows drawn like a phone's** (Sean, 30 Sep 2026: "on the phone i see the row separator on the red highlighted cell,
  and the player name cell looks slightly different"): on a desktop the sorted column's fill (`.hot`) stops at its row (margin
  −3px, the row's padding, instead of −8px), so each row's rule runs through the red; the rank and name cells fill the row's height
  with the phone's thin `--hair` rule down the name's right side (the box-shadow divider went); Fantasy's `td.fsorted` clips its
  fill to the padding box (no white side borders) so its rules show too. A scaled-up desktop type size was tried for a minute and
  dropped — it was the rules and the name cell he meant, not the sizes.
* **Second recommendations pass, 1 Oct 2026** (Sean: "2, 3, 4, and 7"): **Similar** — under the percentile charts, the five qualifiers most like
  him **in style and in skill both** (`similarRow` / `SIM`, Sean the same day: "similar players both stylistically and skill wise"): the
  average of two mean percentile gaps — style (hitters: Air%, GB%, PU%, Pull Air%, Chase%, Z-Swing%, Whiff%, K%, BB%, plus his batting side;
  pitchers: GB%, PU%, Zone%, Chase%, Swing%, FB velo, extension, his pitch mix from `ctx.arsenal` counted as two stats, plus his hand) and
  skill (hitters: xwOBA, EV, Brl%, HH%, EV90, bat speed, Z-Contact%; pitchers: Stuff+, Whiff%, Strike%, K-BB%, uERA); same pool / view /
  split; a name's tooltip gives both matches; it opens his card the way this one was opened. **Across seasons** (Sean, the same day: "player
  and year ... it doesn't have to be a player from that same year"): a full-season MLB card matches against every qualified player-season
  2015-now from **`hist/similar.js`** (`tools/build_similar.py`, run after `build_data.py` / a rescore by `cloud_daily.py` and
  `daily_update.py`, mirrored by `sync_tools.py`: each season's 300+ PA / 150+ BF qualifiers ranked within their own season, plus anyone
  100+ PA / 50+ BF ranked against them so his own card can be matched from, a qualified flag, hand with a pitcher's -SP / -RP role, the
  pitch mix) — `similarAcross` in `app.js`; each player once (his closest season), shown "Name 'YY", a tap opens that season (as a popup when tapped inside one); hand +8 and
  role +15 go straight onto the style gap. A window, split, minors / spring / October card or an unlisted season keeps the same-season match. **Call-up Watch** hitters get MLB wOBA and MLB K% (his line + `MILB_EQ`'s shift), and untracked
  levels show "–" for EV / Brl% / HH% instead of 0.0. **Team search** — a team code or name ("NYY", "Dodgers") in the header search lists
  this season's roster first, hitters then pitchers by playing time (`searchHits`), then any name matches. **A phone's pager drops its
  "1–25 of 534"** (`.pcount`), leaving the bar to Filters, Season / Recent and the pages.
* **Recommendations pass, 1 Oct 2026** (Sean: "do 2, 3, 4, 5, 6, 7, 8"): **Trending folded into the Leaderboard** — a Season / Recent
  switch beside Filters in the blue bar (`recentSwitch`, seated by `seatFilters`; `#trending` still works), the same on Fantasy's
  Leaderboard (Season / Recent beside the page pill, which no longer lists Trending), and both Trending entries are gone from the menus
  (Leaderboards: Leaderboard · Stuff+ · League Trends · Call-up Watch · Compare). **"vs MLB" on a minors card** (**removed the same day** — Sean: "get rid of the mlb mode", a .384 AAA wOBA beside a 39th MLB percentile read as wrong; don't bring it back unasked; `MILB_EQ` stays for Call-up Watch) — a `vs AA | vs MLB`
  switch after Filters (`.vsmlb`, `draft2027.vsmlb` per device): each card stat plus its level's shift (`MILB_EQ`, every card stat for
  hitters and pitchers, from `card_shifts()` in `tools/models/milb_translate.py` — the same reliability-corrected same-season pairs as
  `MILB_X`, chained to MLB; re-run and paste when stale) placed among that season's MLB qualifiers (`mlbEqFor` in `renderPctPanel`); a stat
  a level doesn't carry has no shift (no bubble); values shown are his own. **Off-season** (`offSeason()`, 1 Nov – 15 Mar New York
  time): home leads with a "<next year> draft prep" card (Rankings · Draft board · Eligibility) and the Weekly Planner leaves the Fantasy
  menu; the daily workflow's scheduled / `auto=1` runs stand down 15 Nov – 14 Feb (a plain manual run still builds). **Call-up Watch**
  hitters have Z-Con%. The card's Fantasy tab has no "Edit scoring" link. The card's filter chips hide while the Filters panel is open.
  **Found and fixed:** `hist/aaa-2022.js` had 409 hitters with a wOBA over 1 — Savant's 2022 minors rows leave `woba_denom` blank on about
  half the plate appearances (the value is there), so wOBA was divided by a fraction of his PAs; `load_milb` now gives every counting PA its
  denominator (and its value from the event, `WOBA_W`, when blank) and logs "wOBA bookkeeping repaired …" — rebuilt with `rescore: aaa-2022`.
* **Savant's percentile bars, centred** (Sean, 1 Oct 2026: "make it baseballsavant style and go back to the length we previously
  had. But now center them"): `pctSvg` is the 9 am 30 Sep drawing again — 20px bar, 10 / 50 / 90 ticks, dashed rules, Poor / Average
  / Great over the first chart, Savant's bubble, labels and values in `--svtext`, a 2px light-blue rule under each section name (the
  end-of-file `:root:root:root:root .svpct` rules) — at its old length on every screen (the phone's 1 Oct widening is undone), with
  the rows' block (dashed label column through the value) moved 20 left so it sits 40 in from each side (`IND`, `pctLabelW` guards a
  label wider than its column). Section names stay where they were. This supersedes the "studio look" notes below.
* **The band's facts row** (Sean, 1 Oct 2026: option C of the Card Header Rows page): the season line is "2026 ▾ · team · positions";
  under it one row of small grey labels over values in the name's face — HT, WT, B/T, AGE (`.hbio`, from `bio()`, refilled by
  `fillBio` when MLB's record arrives; B/T falls back to the hand the data carries), then PA · G or IP · G / GS (`renderStrip` /
  `fact`), Filters at the end. On a phone the bio facts are a line of their own above the playing time.
  **The season line** (Sean, 1 Oct 2026: "his stats that year like their avg obp and slugging %"): a row of its own under the facts,
  his official line for the card's season (`seasonLine`, `hist/career.js` — the TOT row for a traded player): AVG / OBP / SLG / OPS
  (Sean: just the slash line and OPS), or uERA (the card's) / ERA / K% / BB% / SV (K and BB over batters faced; W-L and WHIP dropped, Sean 1 Oct 2026),
  and the playing time is PA or IP alone (no G / GS); MLB regular seasons only, the full season whatever the card's filters (`.hstats`).
  **On a phone** (Sean, 1 Oct 2026: the four ragged rows "just looks so weird"): name, season line, then HT / WT / B/T / AGE with
  Filters pushed right beside the headshot; under them one row across the band (`.hrow`, moved there in `renderPlate`) — the playing
  time and the season line spread edge to edge over a thin rule. **A desktop** (Sean, 1 Oct 2026): first row HT / WT / B/T / AGE
  and Filters, second row PA or IP then the season line (the playing-time fact moved into `.hstats`).
  Same day: Swing Decisions back at the top of the right column (`PCT_COLS_H`), and `pctSvg`'s `top` is −2, not −12 — at the title's
  size the section names were sliced off at the top.
* **The card's line and Fantasy tab follow its filters** (Sean, 2 Oct 2026: "when i filter by a given date range the player stats on
  his header update and on the fantasy tab ... points/game and points per pa update"): `fViewLine(p)` sums the season's game logs
  (`fGamesOf` / `fWindow` / `fSum`, the same as Spreadsheet Stats' Standard row) for the card's dates, hand, home / away and SP / RP.
  `seasonLine` shows that line's AVG / OBP / SLG / OPS (pitchers: ERA, K%, BB%, SV over those games; uERA is the view's already),
  and `renderFantasyTab` scores it — points, per game, per PA, games, per start / relief — with the view's name in the sub-head and no
  season ranks. Last three MLB seasons only (where the fantasy files have game logs); an older season's line hides under a filter.
  The By season table's row for the card's season is that filtered line too (marked with the view, e.g. "2026 · May 1 – Sep 27"), and
  the table has **PA/G** behind PA, the Total row carrying PA and PA/G (Sean, 2 Oct 2026).
* **1 Oct 2026** (Sean): **Base Running is off the card** (`PCT_COLS_H`; Sprint Speed / SB / SB Att. / SB% stay Leaderboard / Compare
  columns and in the data); **a phone's percentile bars run wider** — `pctSvg` sits 8 in from each side instead of 20 and gives the
  labels 6 of indent instead of 40 (`SM` / `IND`), ~37% more bar at 390px wide; the bars and bubbles themselves are unchanged (he
  decided against going back to the Savant ones). Height / weight placement is open: four options in the Card Header Rows artifact.
* **Card layout, ninth pass** (Sean, 30 Sep 2026): a hitter's **Swing Decisions** sat under Batted-Ball Quality in the left (back on the right since 1 Oct 2026)
  column (`PCT_COLS_H`), so the two columns are even on a desktop (a phone's stacked order is unchanged); the first section
  heading starts right under the band on a desktop too (`pctSvg`'s `top` is −12 whenever there's no sample line); the card's
  season line ends with his **height and weight** (`htWt`, from `bio()` — MLB's people record, filled in when it arrives,
  `.mlinein[data-bio]`); the Fantasy tab lost its points-by-category table (tiles, then By season with points / per game /
  per PA); a pitcher's strip has **uERA** where More was and no nERA (`BTABS_P`; `renderLuckBox` stays in `app.js`); on a phone
  the tab row says Stats, the tabs are tighter, and when the row fits it sits centred with no fade (`.btabs.fits`, measured in
  `renderBelow`), else it slides as before.
* **Minors: Triple-A xwOBA and Double-A zones** (Sean, 30 Sep 2026: "AAA doesnt have xWOBA just xba and xslg", and TJStats' Double-A
  card): `build_milb.py` no longer stubs the directional xwOBA — Triple-A scores it with sprint speed blank (as xBA / xSLG always
  did), and Call-up Watch ranks Triple-A hitters by it (`xw` column). Below Triple-A the zone comes from Gameday's pitch plot
  (`plot_zone`, 96% in / out agreement with Statcast on Triple-A), so Zone%, Z-Swing%, O-Swing%, Z- / O-Contact% and the rates
  built on them exist there; the card notes say so. TJBat+ is TJStats' own, not built. Past seasons pick both up when rebuilt
  (`rescore` with `aaa-2025` / `aa-2024` … tokens). **`cloud_daily.py` publishes only the files its run wrote** (mtime since
  start) — it used to put back every `hist/` file from its checkout, which would undo a second run rebuilding them alongside.
* **Base Running** (hitter card until 1 Oct 2026, when it came off the card; Sean, 30 Sep 2026): Sprint Speed (Savant's, ft/s, 5+
  competitive runs — `sprint_speeds()`, the model's own feature), SB, SB Att. (SB + CS) and SB% (none without an attempt), official
  from the MLB Stats API's season line (`mlb_people` → `baserunning()` in `build_data.py`, `m.spd / sb / sba / sbp`). Percentiles like
  any card stat (300+ PA pool); also Leaderboard / Compare columns (`LB_EXTRA_H`, `SIDE_H`; `int: true` prints the counts whole).
  **Full season only** — a date window or split has no rows for them, so the section drops out. Files built before 30 Sep 2026 got
  them from `tools/add_baserunning.py` (Savant's sprint leaderboard + the Stats API's season lines, patched into `data.js` and
  `hist/mlb-YYYY.js` without a rebuild; rerun it if a file rebuilt by older code loses them). The minors have none
  (`build_milb.py` blanks `sprint_speeds`, and its people carry no steals).
* **Phone header is one line** (Sean, 28 Sep 2026): site name, search and a ☰ Menu button (`.navtog`, made in `app.js`
  because `index.html` doesn't round-trip); the page buttons (`.modes`) open under it in a two-column grid and close on a
  pick, a page change or a tap elsewhere. Desktop keeps its single row. The swirl pattern behind cards and list pages
  runs at 20% since the minimal pass (45% before; it competed with them).
* **days.js is warmed in the background** (Sean, 28 Sep 2026: faster filters on a phone): ~4 s after the site settles it is
  `fetch`ed into the browser cache (not run) so the first date range or split parses from cache instead of downloading
  ~5 MB; skipped under data saver. Splitting it by player doesn't work — a card in a window or split is ranked against the
  whole pool in that window — and a columnar repack saved only ~8%. The phone's Menu panel shows the "through" date.
* **Stylesheet cleanups are checked by computed style**, not by eye: the scratch harness records every element's computed
  style in ~45 states (phone / desktop, light / dark, every page and card tab) and a cleanup must leave all of them identical.
* **A phone's list rows slide sideways under the frozen rank and name**; those two run the row's full height (over its
  padding, the block at the end of `styles.css`) so the sorted column's fill, stretched over the padding too, slides under
  them — before, it poked out above and below the name as red bars (Sean's phone screenshot, 30 Sep 2026). The frozen Rk /
  Player header cells keep a solid `--surface-2` ground (the pale-header rule had made them see-through, so column names ran
  under "Player" and read on top of it).
* **iPhone home bar** (Sean's 17, 30 Sep 2026): on a phone the standing list card and the popup card stop
  `env(safe-area-inset-bottom)` above the bottom (index.html's `viewport-fit=cover` makes it non-zero), other pages get it as
  body padding, and the credit line is hidden on the standing-card pages (it would sit in that strip). Headless tests report
  0 for it — check with the rule's env() swapped for 34px.
* **A phone card only moves up and down** (Sean, 28 Sep 2026: "scroll it left and right for no reason"): `.cardscroll` clips
  sideways overflow, doesn't bounce, and takes `touch-action: pan-y pinch-zoom`; the tab row, stat strip and tables are
  scrollers of their own and still slide. Keep anything wide inside its own `overflow-x: auto` box.
* **Closing a card keeps the list's place** (`listAt` / `noteList()` in `render()`; the Fantasy table's rows call `noteList()`
  themselves, since they open the card with `renderModal()` and skip the render that would note it — fixed 28 Sep 2026): the rows' scroll, sideways scroll and page scroll are
  noted while no card is up and put back when one closes — on a phone the list is redrawn under the card and started over.
* **The list pages share the pattern** (Sean, 26 Sep 2026): Leaderboard, Trending, Rankings, Draft board, Fantasy,
  Eligibility and Compare put the same white + spiral pattern behind the page (`body[data-mode=…]::before` / `::after`, fixed) and
  gather `main.wrap` — filters, table, notes — into one white card with a plain navy border (no shadow). The table / boards inside keep their own navy frame (a
  single-frame version, inner borders dropped, was tried the same evening and Sean didn't like it). Taking the white card away (the pattern straight behind buttons, table and notes) was tried on
  28 Sep 2026 and undone within the hour — Sean agreed the card looks better; don't remove it unasked.
  The card **stands still** (Sean: "I don't want the white box itself to scroll at all"): it fills the screen from under
  the header to an 18px gap (10px on the phone), the page never scrolls, and only the rows' box (`.board-scroll`, Fantasy
  `.fscroll`) moves — filters, pager and column header frozen above it. On the phone, Fantasy keeps the page scroll (its
  filters would leave the table no room).
* **Stuff+ leaderboard** (Leaderboards ▸ Stuff+ — named "Pitch Stuff+" until 28 Sep 2026, `#pitches`, `renderPitchBoard` in `app.js`; Sean, 27 Sep 2026):
  every pitcher's pitches as their own rows from `ctx.arsenal`, graded against their own type (Stuff+ / Whiff+ / BB+),
  filtered by pitch type, hand, SP / RP and a pitch minimum, every column sortable, a name opens his card on the Stuff tab.
  Full season only. The section and the menu entry are made in `app.js` (`pitchBoardEl`) because `index.html` doesn't
  round-trip. Its standing-card CSS is the `[data-mode="pitches"]` block at the end of `styles.css`.
* **League Trends** (Leaderboards ▸ League Trends, `#trends`, `renderTrends` in `app.js`; Sean, 29 Sep 2026: "league wide
  trends by year ... to see how the landscapes change"): reads `hist/trends.js` (`build_trends.py`) on demand. Hitting: pick a
  group (plate discipline / batted balls / quality of contact / results), a row per season, each column coloured by the
  season's rank among them (red highest, blue lowest — no good / bad); pitching: pick a stat, a column per pitch type. Tapping a
  column header draws it as a line above the table (`trendChart`, plain SVG, the part season hollow). Drawn in the Stuff+ board's
  section (`#pitchboard`) and standing-card CSS (every `[data-mode="pitches"]` rule also names `trends`). No Stuff+ by pitch: it's
  graded against each season's own type average, so the league is 100 every year. Savant has since relabelled old sweepers, so
  ST exists (small) before 2023.
* **Weekly Planner** (Fantasy ▸ Weekly Planner, `#planner`, `renderPlanner` / `pwSchedule` in `app.js`; Sean, 29 Sep 2026): the
  Monday–Sunday week (‹ Prev / Next ›, `pw.off` weeks from this one, New York time) fetched **live from the MLB Stats API in the
  browser** (`schedule?sportId=1&gameType=R&…&hydrate=probablePitcher,team` — it sends `Access-Control-Allow-Origin: *`; nothing is
  built), cached per week in memory. Starred players (`state.stars`, keys type+id) or everyone. Three tables: two-start pitchers
  (everyone), pitchers (probable starts, or a reliever's club games × his relief-appearance rate), hitters (club games and the
  opposing probable starters' hands from `throws`). Projected points = starts × points per start / games × points per game (this
  season's `fantasy.js` under the current preset). Team codes match the site's (the API's abbreviations: AZ, ATH, CWS, WSH…).
  Probables appear a few days ahead, so a later week fills in as it nears. Same `#pitchboard` standing card as the Stuff+ board.
* **Call-up Watch** (Leaderboards ▸ Call-up Watch, `#callups`, `renderCallups` / `cuRows` in `app.js`; Sean, 29 Sep 2026): this
  season's minor leaguers at one level (`hist/<aaa|aa|ap|a>-<season>.js`, loaded on demand). Pitchers ranked by **MLB-equivalent
  uERA** — the level's Whiff% / Strike% / GB% / PU% shifted by `MILB_X` and placed in this season's MLB SP or RP pool (`placeIn`),
  the same number as Season Stats' minors rows — as a chip coloured by that MLB percentile, with minors Stuff+ (tracked levels
  only), K%, BB%, Whiff%, Strike%, GB%, FB velo, ERA; hitters by wOBA (no directional xwOBA in the minors) with K%, BB%, Whiff%,
  Chase%, EV, EV90, Brl%, HH%. Filters: side, level, SP / RP, age, minimum BF / PA, "no MLB time yet" (an id with an MLB line
  this season is tagged MLB). A name opens his card on that level's season (`state.x.ds`). Same `#pitchboard` section and
  standing-card CSS as the Stuff+ board (the `[data-mode="pitches"]` rules name `trends` and `callups` too).
* **Game Logs tab** (pitcher card, `renderGamesTab` / `gameLog` / `gamePitches` in `app.js`; Sean, 29 Sep 2026: "his stuff+ by
  start/relief appearance"): every appearance of the card's season from the day rows (days.js, or `hist/days-<season>.js`),
  whatever the card's dates or splits — Stuff+ that day (`stuffFrom` on the day's `stn…stbp`) against his season, a dot chart
  of it (starts filled, relief hollow), a log, oldest first, in three blocks under group labels with a rule
  between (Sean, 29 Sep 2026): **Stuff** (date, Stuff+, Δ) · **Start results** (IP, ER, K%, BB%, **uERA** — that day's rates through
  `impliedKBB` / `underlyingERA` on its balls in play, the one heat-mapped result, a chip coloured by its percentile among the
  season's pitchers like Season Stats' uERA; raw K / BB, K-BB% and the luck column dropped) · **Underlying** (Whiff%, Strike%, GB%,
  PU% — Zone% / Chase% dropped; Sean, 29 Sep 2026), no text colouring, group labels centred on the Leaderboard pager strip's pale blue (light blue at 24% on white) over the pale
  grey column-name row, the whole log — and the pitch and luck tables under it (`.gframe`) — in the Leaderboard table's thin navy frame; the Season row frozen at the log's foot (sticky bottom), grey and bold. The tab is called **Game Logs** (key `games`) — the date pinned, opening
  scrolled to the picked (latest) game; the rest scrolls sideways on a phone, the picked game's rates as box-score tiles over his season, and
  **BIP luck**: the day's wOBA on each batted-ball type (`wgb/wld/wfb/wpu` over `gb/ld/fbt/pu`) against the league's value
  for the type (`consts.bbw`), in runs (÷ `wobaScale`), + = unlucky. Tapping a game shows each pitch that day graded against
  its type beside his season, every metric the arsenal file carries (Stuff+ / Whiff+ / BB+, use, velo, IVB, HB, spin, xWhiff /
  Whiff%, xGB / GB%, xPU / PU%; counts in the tooltips; `hist/ars-<season>.js`; under 5 of a pitch isn't graded) and the luck by type.
* **Hitter Game Logs tab** (hitter card, first of `BTABS_H`, `renderHitGamesTab` / `hitGameLog` in `app.js`; Sean, 29 Sep 2026):
  every game of the card's season from the day rows (via `gameDays`), oldest first, in the pitchers' dress — **Game** (date,
  xwOBA as a chip coloured against the season's 300+ PA hitters' xwOBA) · **Results** (PA, H, HR, BB, K, wOBA, luck = (wOBA −
  xwOBA) runs, + = the results beat the contact) · **Contact** (EV, max EV, barrels, HH%) · **Discipline** (Whiff%, Chase%), Season row
  frozen at the foot. Tap a game: tiles over his season, every tracked ball's exit velocity (the day rows' `evs` lists), and
  its luck with BABIP vs xBABIP. `state.hGameDay` is the picked game.
* **Postseason game logs** (Sean, 30 Sep 2026): both Game Logs tabs sit in `renderGameLogs`, which puts a Regular season /
  Postseason switch (spring training taken off the same day) over the log for the game types he has that year (`gameKinds`, from the index entry's
  `e.k` — the index's `seasons` list drops spring / post, so don't check it). The card stays on its season; the log reads that
  game type's dataset and day file (`hist/days-<year>-post.js` …), chips ranked against that year's regular season (`kindPool`).
  `state.glKind` resets when a new player's card opens. Spring / October files built before `hr` / `dbsum` were appended to the
  day rows show HR as "–" until rebuilt (`rescore` with `post-2025` / `spring-2025` tokens); spring has no directional xwOBA.
* **xwOBA − wOBA** (`xwdiff`, hitters; Sean, 27 Sep 2026): a Leaderboard / Trending column (added once to saved column sets
  via `state.lb.xwdAdded`), signed (+ = unlucky). `LB_EXTRA_H` lists the hitter stats that are columns without being on
  the card (xwdiff, babip, xbabip, bluck, brel); `fmt()` prints `sign: true` metrics as +.024 / −.018.
* **Spreadsheet Stats tab follows the card's filters** (Sean, 28 Sep 2026: "like fangraphs", then "a separate tab from season
  stats"): `renderViewStats` shows the card's view (dates, hand, home / away, SP / RP) as FanGraphs-style Standard / Advanced /
  Batted Ball / Plate Discipline tables (`VS_H` / `VS_P`), the full season's row under it when a filter is on; Season Stats
  stays the season-by-season table. Standard
  is the official box score summed game by game (`fGamesOf` / `fWindow` / `fSum`, last three MLB seasons only; a hand split
  shares games out by the day's pitch data, so estimates); the rest is `V(p).m` plus the pool's uERA / Stuff uERA.
* **The home page is a dashboard** (`renderHome`, Sean, 28 Sep 2026: "a legit home page"): a hero card (games through / updated,
  a player search, the most-used pages; a name anywhere on it pops his card up over the home page — `openCard` sets
  `state.expanded`, and `renderModal`'s `listMode` includes home — Sean, 28 Sep 2026), then cards for starred players and the season's
  xwOBA / Stuff+ / uERA leaders, and every page as tiles (`HOME_SECS` + `SHORT` blurbs). Only data.js is
  used so it opens fast; it sits on the swirl pattern like the list pages (CSS `.hub.home`).
* **Draft Mode is gone** (Sean, 28 Sep 2026: "serves no purpose anymore with the homepage"): `renderHub`, its menu entry
  (also stripped in `app.js` for the Mac's template) and its home tile; `#draftmode` lands on the home page. The Fantasy
  menu's group key is still `draftmode` (index.html's `#modesel`), but it's never a page.
* **Rankings and the Draft board list everyone** (Sean, 28 Sep 2026: "see everyone who can get drafted"): `noMin()` makes
  `effMin` 0 there and hides the Min box / Minimum section; percentiles still rank against the 300+ PA / BF pool.
* **Stuff+ table header is pinned on both axes** (28 Sep 2026): Fantasy-table rules (`.ftable th.n/.who { top: auto }`, a flex
  `th.who`, the phone's unstuck header) had let rows slide up past it; the `:root:root .pbtable` block at the end of
  `styles.css` pins the whole header and gives # (44px) and Pitcher their own sticky spots. The `.pbtable` is also an `.ftable`,
  so a Fantasy-table change can reach it — check both.
* **Appearance is a settings list** (Sean, 28 Sep 2026: "make it look cleaner"): `renderAppearance` builds one `.aset` row per
  setting (name + note left, control right; stacked on a phone), scheme swatches (banner with "Sean's Site" + four colour
  dots, blurb as a tooltip), the page on the pattern like the lists. The font name is `.ffname` — `.fhead` is taken by the
  Fantasy table's floating header.
* **Fantasy, calmer** (Sean, 28 Sep 2026: "funky and somewhat overwhelming"): dates / window, hand, home / away, the points basis
  and the minimum fold behind a Filters button with a one-line summary (`fFilterSummary`); only the sorted column and Trend / Δ
  are heat-coloured; the note is two lines with "More about these numbers"; "Edit scoring" dropped (the Scoring settings tab
  does it); `#fboard` has no frame of its own, the table has the 1px one; the phone's page tabs are a 2×2 grid.
* **Leaderboard colouring follows Fantasy's** (Sean, 28 Sep 2026: "give the table this same formatting color wise"): with the
  colour scale off (the default), only the column you sort by is filled edge to edge (xwOBA − wOBA was too, until Sean said not to) with their
  percentile colour (`.hot`, stretched over the row's padding), the rest plain; the heat-off / sorted-tint rules skip `.hot`.
  Trending rows had no headline percentile (`placeIn` only covered the listed stats) — the pool now keeps a sorted list for
  the headline too.
* **Leaderboard / Trending / Rankings / Draft board wear Fantasy's controls** (Sean, 28 Sep 2026): the toolbar buttons are
  Fantasy's tabs — white with a thin light-blue outline, filled light blue while open or in effect, 34px (Fantasy's Filters
  button too; solid light blue and then a navy outline were tried the same evening), the header row thin (~24px on desktop), and `#colhead` is Fantasy's pale header — small grey labels, the sorted one
  in blue, a light-blue rule under it. The Stuff+ board keeps its navy header.
* **Card tables in the same dress** (Sean, 28 Sep 2026): every table in a card's bottom tabs has the pale header; in
  Spreadsheet Stats a stat his card ranks is filled with its percentile colour (`pctOf` in `renderViewStats`, from the pool's
  `st.pct`), like the Stuff table's grades. The card's bottom tabs are outlined white with the picked one light blue; the
  Filters button on the band stays navy (a light-blue one vanishes on the light-blue band).
* **The card's header band wears the Leaderboard's colours** (Sean, 28 Sep 2026): `.mplate` is the pager strip's pale blue
  (light blue at 24% on white) with a 2px light-blue rule instead of the solid band and navy rule; Star and Filters are the
  Leaderboard's outlined buttons (Filters filled light blue while open).
* **The card's band text follows the scheme** (Sean, 30 Sep 2026, on Titans: white text on the pale band): `.phead` remaps
  `--accent-2-ink` / `--accent-2-dim` / `--band-ink` / `--tab-ink` to `--ink` / `--ink-2`, since the band is pale now in every
  scheme; Star / Filters text is `--ink`. Carolina (whose accent-2-ink is its ink) is unchanged.
* **Don't restyle the percentile bars unasked**: a Leaderboard-table version of them was tried and taken back the same
  evening (Sean, 28 Sep 2026: "i didnt want you to touch any of the percentile bar metrics"). **Restyled at his request on
  30 Sep 2026** from the Percentile Bar Studio page (seven concepts; he picked the Savant bar as drawn there, "precisely"):
  `pctSvg` draws a 17px bar on a faint track (`--pctrack`), no 10/50/90 ticks, no dashed rules between rows, no Poor / Average /
  Great row, a 23px bubble with a white ring (navy digits from 38 to 62); section names in the condensed face, grey, over a 2px
  navy rule (since the same evening in the card title's type: 600 navy, 24px / 19px on a phone, like `.pthd`); labels bold navy, values plain (`.svval`). Same row pitch, so the box height is unchanged. **Taken back the same evening** (Sean: "back to the baseballsavant style percentile bars they just look better"): `pctSvg`
  is Savant's again — 20px bar, 10/50/90 ticks, dashed rules, Poor / Average / Great on the first chart — keeping only the
  section names in the title's type and the bubble digits centred by `dy`. Don't restyle them again unasked. **And back again, adjusted** (Sean, later that evening: "go back one update ... make it so the height of them is the same
  as these savant ones and make the circle text always white"): the studio bar once more, but 20px tall like Savant's and white
  digits in every bubble (no navy middle). **Final (Sean, the same night: "never mind just keep the savant ones ... make the bubbles for them the savant
  style too"):** Savant's bars and Savant's bubbles (r 10, 2px ring, white digits), exactly as before the studio page; only the
  section names in the title's type and the digits centred by `dy` differ. Leave them. **Reset (Sean, that night: "equal to whatever it was at 9am this morning"):** `pctSvg` is byte-for-byte the 9 am
  version (main at 89710a8) — bars, bubble, and its digits at `y: 1` in Savant's Roboto Condensed (a 100 at 10px, `.c3`); only
  the section names keep the title's type. `themes.js` loads Roboto Condensed 700 for those digits alone. Leave all of it. **Then, the same night, the studio look at Savant's size** (Sean: "the percentile bar style you gave me again but ...
  the same height as the savant style and ... the bubble ... font style height and fit exactly the same"): `pctSvg` is the 9 am
  code minus the 10 / 50 / 90 ticks, the dashed rules and the Poor / Average / Great row; labels bold navy, values plain
  (`.svval`), a faint track, a navy rule under each section name. The 20px bar and the bubble (r 10, 2px ring, white Roboto
  Condensed digits at `y: 1`, a 100 at 10px) are Savant's, untouched.
* **Type and ground** (Sean, 30 Sep 2026, same page): the whole site is **Barlow Condensed** (`--display`: headings, names, big
  numbers) + **Source Sans 3** (`--body`: everything else), loaded by `themes.js` (`F.studio`, the only font); Roboto
  Condensed is gone. **The swirl is gone**: `nopattern` is always on and the Appearance row is removed; pages sit on
  `--ground`, a pale tint of the scheme's `--accent-2` (pale Carolina blue on the default scheme). Don't bring the swirl back unasked.
* **No bold** (Sean, 30 Sep 2026, after the Font Studio page — he kept Barlow Condensed + Source Sans 3): one rule at the very end
  of `styles.css` sets every element to weight 400 except the percentile bubbles' digits (`.svnum`, Savant's Roboto Condensed 700).
  Bold was brought back for an hour (all but the card's stat names and the lists' numbers) and dropped again — Sean: "keep
  everything unbolded ... more minimalistic". Don't reintroduce bold unasked.
* **Heat maps share the bars' scale** (Sean, 30 Sep 2026: "the darkest red isn't dark anymore"): `pctStyle` takes its colour from
  `savantStyle` (Savant's #3661ad / #b4cfd1 / #d82129 in Lab), so a table cell and a bar at the same percentile match, and the
  sorted column (`.hot`, Fantasy's `.fsorted`) is its full colour again — the light tint from the fourth minimal pass is gone.
* **Projections and Buy low / Sell high were built and removed the same day** (Sean, 28 Sep 2026: "I don't need those") —
  the pages, the home cards, `tools/build_proj.py` and `proj.js` are gone. Don't bring them back unasked.
* **Starts / relief split** (Sean, 26 Sep 2026): a pitcher who both started and relieved (`ctx.GS > 0` and `G > GS`)
  gets a third split on his card, `state.split.role` = all / sp / rp. `V()` keeps the day rows whose `gs` flag matches,
  earned runs follow the same days, and a past season reads its day-by-day file for it (`byDay` in `histDataset`).
* `hist/` files built before a field was appended to `HITTER_DAY`/`PITCHER_DAY` lack it; `app.js` checks
  `indexOf(...) < 0` before using one. Keep doing that.
* **Fantasy Leaderboard / Trending** (Sean, 26 Sep 2026): the header menu is now just "Fantasy". Points total, per game (hitters' Pts/PA right beside Pts/G in every basis; on the card's Fantasy tab a points-per-PA tile, Per PA column and By season Pts/PA, the tile and the By season column heat-coloured against this season's qualified hitters — Sean, 29 Sep 2026: the card, not the leaderboard),
  per AB / PA, per start / relief app / IP, per week (weeks he played in); dates, vs LHP / RHP, home / away; expected
  points — hitters xPts (H / TB from dxBA / dxSLG, R and RBI × xwOBA/wOBA), pitchers nPts (luck-neutral) and uPts
  (uK / uBB / uERA). **The card's Fantasy tab works for any season** (Sean, 30 Sep 2026): a season without game logs — an
  older card, or a player with no 2026 games — is scored from his official line in `hist/fantasy-lines.js` (`fromLine` in
  `renderFantasyTab`: points, per game, per PA, categories and By season; no ranks, per-start tiles or game log; per PA coloured
  against this season's qualified hitters). Hand splits share each game's official line out by that day's Statcast rows (`fDayShares`), so
  vs L + vs R = the whole. See `docs/site-README.md` § Fantasy points.
* **Saved settings sync through a secret gist** (Sean, 26 Sep 2026): fantasy presets, stars, drafted, rankings, tiers
  and ranking sets (`SYNC_KEYS` in `app.js`) — Appearance ▸ Sync across devices, a gist-only GitHub key per device.
  Anything new that should follow him between devices goes in `SYNC_KEYS`; per-device UI state and Appearance don't.
* **Spring training Stuff+** (Sean, 29 Sep 2026): `build_history.py spring <year>` grades spring pitches with the last three MLB
  seasons' models against the last MLB season's pitch types (like the minors; `ref=`), park-adjusted within spring. Spring
  tracking is near-complete (2026: 1,039 of 1,045 pitchers have velocity). `cloud_daily.py` rebuilds and publishes this spring's
  file every morning through February and March, and `rescore` takes `spring-2026` tokens. The site stays regular season only,
  except the Stuff+ board's **Games: Spring training** option (`pb.src`, `springKey`: next year's spring once built, else this
  one's), which reads `hist/mlb-<year>-spring.js`; a name opens his spring card as the list popup (`state.cardDs` = the spring key; `renderModal` keeps it only on that board). EV-based stats are thinner there.

* **Taken back the same day** (Sean, 30 Sep 2026: "we won't show anything postseason related except game logs and then for spring
  let's just show nothing"): the card title offers regular seasons only (`pageTitle` reads `entry.s`, not `e.k`; a saved
  `state.cardDs` on a spring / PS key falls back to its regular season in `renderModal`), the Stuff+ board has no Games pill
  (`pb.src` is forced to the season), and Game Logs' switch is Regular season / Postseason only. The builds, `kindPool` and the
  rest of the machinery below stay, so bringing either back is a UI change. Don't show spring training anywhere unasked.
* **Postseason and spring on the cards** (Sean, 30 Sep 2026: "a dropdown on the MLB and say PS and spring training ST"): the
  card title's level dropdown (`pageTitle`) offers **MLB PS** / **MLB ST** beside MLB for any year he has them — `indexReady()`
  keeps each player's spring / postseason seasons aside in `e.k` instead of dropping them, `KIND_TAG` gives the short labels.
  Those percentiles are **against that year's regular-season qualifiers** (full season, same hand / venue split): `pool()` hands a
  spring / postseason dataset to `kindPool`, which takes the regular season's reference arrays (`regularOf`) and places every
  spring / October line among them; the dataset's `consts` are the regular season's too. A card waits for the regular season's
  file before ranking. Build: `build_history.py post <year>` grades postseason Stuff+ on that year's regular season and the two
  before; `cloud_daily.py` rebuilds this year's postseason every morning Sep–Nov (the minors step's index then offers it), and a
  `rescore` run now rebuilds the index too (`post-2026` / `spring-2027` tokens).

* **Leaderboard spans of seasons** (Filters ▸ Season and level: Season [from] to [to], then **Combined** — one line per player,
  every season in the span summed from rows — or **Each season** — every player-season its own line with a Year column;
  `lbKey` / `multiKey` / `multiDataset`). Combined players carry no season numbers of their own, so `dirInfo()` for a span asks
  its member seasons — before 30 Sep 2026 a combined span quietly led with wOBA instead of xwOBA. The season row wraps on a phone
  (`#lbseason`). Since 30 Sep 2026 a **Multiple seasons** button turns the span on / off (on from the latest season it starts two
  seasons back); the "to" pill and Combined / Each season only show while it's on. The pager, search and column ticks redraw the rows
  through `inListView` (`renderRows` / `renderColhead` step into the Leaderboard's dataset and split themselves) — they used to fall
  back to this season, so page 2 of a span showed 2026. `multiDataset` waits for the search index (which seasons are built): a span
  built before it arrived knew only 2026 and was cached that way (fixed 30 Sep 2026). Each season's directional xwOBA keeps **its
  own season's scale** in a span (`dirFor(p)`: an each-season player uses `p.src`'s `dirInfo`; a combined line's rows have `dnum`
  scaled part by part and the span's scale is 1) — one averaged scale had shown Gary Sánchez 2016 at .407 in a span vs .422 on his
  card (Sean, 30 Sep 2026). The name line carries the season (`.yr`: a player-season's year, a combined
  player's own seasons in the span), so the Year column is no longer automatic (only when ticked in Table).
* **Fantasy points as list columns** (Sean, 1 Oct 2026: "on the fantasy rankings and draft board ... points per game and points per
  PA"): Pts / Pts/G / Pts/PA (hitters) and Pts / Pts/G / Pts/IP / Pts/GS (pitchers) in every list page's Filters ▸ Stats, their own "Fantasy points" group in `renderColPick` (`FANT_H` /
  `FANT_P`, in `LB_EXTRA_H` / `_P`), shown as values, sortable. `fantFill` puts them on `V(p).m` from the official season line
  (`fantasy.js` / `hist/fantasy-<y>.js`, loaded by `colsFor` when a points column is ticked) under the current preset; `fsave` bumps
  `fantGen` and clears the pools so a scoring change re-scores. Full season of the last three MLB seasons only (a window, split,
  span or minors season reads "–").
* **Mock Draft** (Fantasy ▸ Mock Draft, `#mock`, `renderMock` and the `mk*` block before `NAV_GROUPS` in `app.js`; Sean, 2 Oct 2026:
  "practice mock drafts ... snake and auction ... function very very similar to espns ... allow pausing"): a draft room against computer
  teams on the Stuff+ board's standing card (every `[data-mode="planner"]` CSS rule also names `mock`; the room's own block is at the end
  of `styles.css`). Setup: snake / auction, 4-16 teams, your slot (or random), seconds per pick, or cap / nomination / bid seconds, AI
  speed, roster spots per slot (C, 1B, 2B, 3B, SS, 2B/SS, 1B/3B, OF, UTIL, SP, RP, P, Bench). Room: clock + Pause / End, player list
  (search, position pills, sort by ADP / your Proj / $, Draft or Nominate, ☆ queue), My team (slots filled by a bipartite matching,
  `mkAssign`), Board, Picks, Queue; auction panel with +$1 / +$5 / custom bids. At zero you get your queue's first player who fits, else
  the best available. Computer teams pick by ADP with noise and roster need (`mkAiChoice`), nominate from the top values and bid up to a
  private price around the player's $ (`mkTick`). Settings `draft2027.mock`, the draft in progress `draft2027.mockdraft` (comes back
  paused; leaving the page pauses it). **The 2027 ADP** (`mkPool`): the site's projection — 2024-26 official lines (`fantasy.js` +
  `hist/fantasy-lines.js`) under ESPN standard scoring, weighted .5 / .3 / .2, regressed toward the league rate, playing time weighted
  .6 / .25 / .15, aged — ranked by value over replacement (10 teams, default roster), then the **median** with the early 2027 lists in
  **`hist/adp-2027.js`** (hand-built 2 Oct 2026 from ESPN's top 50, Yahoo's top 25, CBS's position ranks and RotoWire's first 2027
  draft by position; keyed type+id — Ohtani the hitter and pitcher share an MLB id; position lists are placed where that position's
  n-th player falls in the projection). Those lists are category-based. Refresh the file when ESPN publishes 2027 ADP (its API had no
  2027 season on 2 Oct). The
  Proj column (and the final standings) use the **Scoring** picked at setup from the saved Fantasy presets (`mkScoring`, `mkSet.scoring`).
  **Default roster** (Sean, 2 Oct 2026, his league): C, 1B, 2B, 3B, SS, 2B/SS, 1B/3B, 4 OF, 2 UTIL, 8 P, no SP / RP, 4 bench (25); a saved roster
  that still equals the old ESPN default (`MK_OLDDEF`) moves to it on load, one he changed stays. The setup's reset link says Default.
  Same day: the draft slot is a row of buttons (Random, 1…N); a **Timer** button in the room's top bar changes the pick / nomination /
  bid clocks, the AI speed and the scoring mid-draft (a running clock longer than the new length is cut to it).
  **Later that day** (Sean: a 60-second countdown, sound alerts, "auction values ... very low for the top players"): the room opens on
  a one-minute countdown (`status: "pre"`, `mk.pre`; Start now skips it; no Draft / Nominate buttons until it ends — `mkGo`). Sounds
  are Web Audio tones (`mkSnd`, no files; the context opens on a tap — Start draft or any press in the room — as iOS needs): a chime at
  the start, a two-tone alert whenever you go on the clock or have to nominate, a tick in each of the last three seconds of every bid,
  of your own pick / nomination clock and of the countdown (`mkTicks`), a gavel when a player sells (a brighter one when you win him),
  a soft click for other picks; 🔊 / 🔇 in the top bar (`mkSet.sound`). Auction $ re-priced: replacement is the best player left
  after the **starters** are filled (benches out — `mkVOR(..., false)`); ESPN's 2026 values were tried as the curve the same day.
  **Final (Sean, 2 Oct 2026: "make the rankings based on the 2027 rankings and then do the $ auction values ... based on what my drafts
  experience was like ... ohtani should be the only crazy player, then maybe 1 or 2 above 60/70 and the rest of the tippity top tier
  guys ... 50-70")**: the **ADP is the 2027 lists' median** (`mkPool`) — the projection is no longer a vote; it only places players
  no list names, never ahead of the listed ones at their rank (+60). CBS / RotoWire DH lists are matched against **DH-only** hitters
  (matched against every hitter, RotoWire's DH #3 Yandy Díaz came out ADP 3). **$ = the price for his ADP rank** (`mkDollars`) on
  `MK_PRICE`: Sean's league's 2026 auction (`MK_MKT`, every price paid, 14 × $200 × 25, 191 of 350 at $1-2) with its top 26 smoothed
  (`MK_TOP`: 104, 76, 70, 67, 65 … 32; Ohtani $102 in a 14 × $200 room at Sean's ask). `mkCurve` maps the top ranks rank for rank (the stars are the same few in any room), deeper
  ranks at the same fraction of the pool, then shares the money over $1 a spot to the room's teams × cap: 14 × $200 gives Ohtani $102,
  Witt $75, then $69-50 for the next ten; 10 × $260 Ohtani $130. The $ column is the computer teams' market too (`mkMarket`), so
  what you see is what the room thinks. Proj stays the site's projection under your scoring.
  **Computer bidding** (Sean, 2 Oct 2026: "make the actual auction behave similarly" to his league): a team's price = the $ for his
  ADP × the room's mood on that lot (one draw for every team, `exp(0.22 · tier · gauss)` held to 1 − .3 tier … 1 + .35 tier, tier .4 for ADP 1 rising to 1 by ADP 2 × teams — a superstar swings least — Sean: "make it so the auction is random so it doesnt
  go exactly based on auction values adp every time") × 0.8 × inflation (`mkInflation`: money left vs what the best open players are worth) × its style (`MK_STYLES` / `mkStyleMul`:
  stars-and-scrubs, balanced, bargain, early spender, pitching- / hitting-heavy) × noise (σ 0.2) × its money per open spot; half for a
  player who'd only fill the bench. Stars are nominated first (any of the top 8 open), later a mix of the top 15 and $1 fliers; bids jump $3-10 while far under a
  price, then go up $1.
  **⏩ Skip** (Sean, 2 Oct 2026: "if I know I don't want a player I can fast forward through his bidding process"): beside Bid in the
  auction panel, `mkSkip` lets the computer teams bid the lot out at once with the clock's own logic (`mkBidders` / `mkAiRaise`, shared
  with `mkTick`) and sells him; a bid of yours that's still high stands until someone tops it.
  **On a phone** (Sean, 2 Oct 2026: the list "is only taking up 35% of the screen"): one frame instead of two, the clock bar and the
  list's search / sort / positions a line each (positions slide sideways), tighter rows, no bid-history line — the rows get ~61% of the
  screen between lots and ~46% while one is up for bid (they had ~33%). The block after the minimal passes' at the end of `styles.css`.
  **2027 projections drive the rankings** (Sean, 2 Oct 2026: "these rankings feel very odd and wrong, maybe use like some sort of 2027
  projection system ... fangraphs or zips or oopsy"): Steamer / ZiPS / OOPSY 2027 aren't published in October and FanGraphs is behind
  Cloudflare from the cloud, so **`tools/build_proj27.py` → `hist/proj-2027.js`** (repo only, run by hand; rerun after the season's
  last fantasy build) projects every official category: Marcel (2024-26 weighted 5 / 4 / 3, pitchers 3 / 2 / 1, regressed with 1200
  weighted PA / 600 weighted outs of the league rate, aged +0.6% a year under 29 / −0.3% over), a hitter's H and TB halfway to
  Savant's xBA / xSLG × AB (extra-base hits scaled to match), a pitcher's ER halfway to xERA, QS / RW / RL counted from 2026's game logs,
  and playing time that keeps a regular's lost season from sinking him (≥ 85% of his two fullest seasons; a young everyday player ≥ 560
  PA, a young starter ≥ 140 IP; caps 700 PA / 200 IP / 72 IP relief). `mkPool` scores those lines with the room's preset (`mine`, the
  Proj column) and **the ADP is value over replacement under the room's own scoring, teams and roster** (`mk.set`, else `mkSet`) —
  every team in a league drafts for the same scoring. The early expert lists (`hist/adp-2027.js`) are no longer read (category-based,
  which is what read odd); the $ curve is unchanged and follows the new order. ESPN standard, 14 × $200, Sean's roster: Soto $98,
  Misiorowski $72, Ohtani (hitter) $66, Skubal $63 … — eight P slots a team make aces valuable. Swap in Steamer / ZiPS when they're out
  (November) by writing the same file shape.
  **Ohtani is one player** (Sean, 2 Oct 2026: "ohtani should be valued as a pitcher and hitter thats why he should be $98 value guy and
  the rest are not too close"): `mkPool` folds a two-way player's pitcher entry into his hitter entry (points summed, `x.two` keeps the
  pitching part, the room tags him "DH + P"); he fills one hitter slot. 14 × $200: Ohtani $98, Soto $72, Misiorowski $66, Skubal $63.
  **Steady bid panel** (Sean, 2 Oct 2026: the bid and Skip buttons "dont move when new bids are made" and a new bid shouldn't reset
  the typed bid): `mkDrawLive` refreshes the panel in place (`w._refresh`, same lot) instead of rebuilding it; the price, high bidder and
  +$ buttons have fixed widths with tabular digits and the bid history its own line; the typed bid is kept in `mkUI.cust` per lot (and
  its focus) across full redraws, cleared once it's placed; Enter in the box bids. **Teams tab** (same day: "see the current budget and
  max bid for every team"): a side / phone tab listing every team's money left, max bid ($1 kept for each other open spot), spots left
  and projected points, the high bidder marked; a name opens that team's roster.
  **Cards pop up in the room** (Sean, 2 Oct 2026: "when i click on a player let it give a pop up window that i can exit ... similar
  players ... just another pop up window"): `renderModal`'s `listMode` includes `mock`, so a name opens the popup card over the draft
  (the clock keeps running); and on every popup page a cross-season Similar name opens that season's card as the popup (`state.cardDs`,
  the hist file loaded first — a placeholder `p0` shows "Loading 2019 season…") instead of going to `#player`. × goes back to the page.
  **Default roster has two UTIL** (Sean, 2 Oct 2026; `MK_OLDDEF` lists both earlier defaults so a saved copy of either moves up).
  **Louder** (Sean, 2 Oct 2026: "make the auction or pick sounds much louder"): `mkAudio` builds a compressor + 2.5× master gain once,
  every cue is a square tone with a triangle an octave under at 3-4× the old level (`mkSnd`'s `two`), your-turn plays twice, and on an
  iPhone `navigator.audioSession.type = "playback"` puts the sounds on the media channel (louder, and not silenced by the mute switch).
* **Positions shown are where he played that season** (`playedLabel`: positions with a tenth of his games, most first, up to three;
  SP / RP by that season's starts and relief), on the Leaderboard, Trending and cards; next year's fantasy eligibility (`posLabel`)
  only on Rankings, the Draft board, Eligibility and Fantasy (`posShown`; Sean, 30 Sep 2026).

* **The "xyz layout" (Sean, 3 Oct 2026: "save the current site so i can go back to it if i want, call it xyz layout")**: the site as
  it stood that afternoon is the branch **`xyz-layout`** (a tag could not be pushed through the proxy) and a live copy at **`/xyz/`** — `xyz/index.html` (with `<base href="/">`
  so it reads the live `data.js`, `days.js`, `hist/` and `build.json`) plus its own `app.js`, `styles.css`, `themes.js`,
  `defaults.js`. It is frozen: the daily build and `sync_tools` don't touch `xyz/` (a Mac publish that mirrors the whole deploy
  folder could drop it — the branch is the real backup). The redesign that replaced it is below.

* **Header and Leaderboard column tabs** (Sean, 3 Oct 2026, after a full redesign prototype he liked but didn't take: "keep the
  current site design and format as is ... introduce some of the functionality"): the header is **Home · Leaders · Stuff+ · Fantasy**
  (`pitchBoardEl` puts the Stuff+ link in the header and moves Fantasy after it; `NAV_GROUPS`'s leaderboard group is labelled Leaders
  and no longer claims `pitches`; More is a quiet ⋯ at the end with the same menu); the Leaderboard / Recent have **column-set tabs**
  — Hitters / Pitchers, then Standard · Advanced · Batted ball · Plate discipline (· Stuff for pitchers) — `LB_SETS` / `renderLbTabs`
  (called from `renderColheadIn`), the row `#lbtabs` between the pager bar and `#bscroll`; a tab writes the same column list as
  Filters ▸ Stats (`setColKeys`), a list matching no tab shows a Custom tab that opens Filters ▸ Stats, and `state.lb.tabs` moves a
  never-customised `LB_SLIM` list to Standard once. `LB_SETS` sits by `LB_SLIM` at the top because that migration runs at load.
  Cards stay popups; the rows keep scrolling inside the standing card. The prototype itself is a Claude artifact, not in the repo.
  **Then, the same day** (Sean, on the Stuff+ board: "i like this look for this page ... make the leaderboards page like this too, so now
  everybody is on the one page and it scrolls"): the Leaderboard / Recent list **everyone** (`onePage()` makes `pageWindow` one page, so
  no page numbers), the filter row (Filters, Season / Recent, the count "267 hitters · 2026 · 300+ PA" at the right) sits on the ground
  with no blue bar, the column tabs + rows' box are the one framed table, and a note (`.lbnote`, in `#notes` from `renderChrome`) sits
  under it — the block at the end of `styles.css`. Rankings / Draft board keep their pager.
  **And again** (Sean, the same hour: "get all of this stuff to be in the upper area where filters is ... separate the filters to be
  their own individual buttons ... for like standard advanced etc make that one button of itself ... dates has the capability to filter
  by like most recent PAs or days"): on the Leaderboard / Recent the one Filters button is **six** — Position · Filters · Stats · Splits ·
  Dates · Table format (`renderToolButtons` under `onePage()`, each opening the same dropdown on its tab; `placePop` anchors to the open
  tab's button; Dates says the window in effect, `datesLabel`); the Hitters / Pitchers switch and the column sets ride in that same row
  (`renderLbTabs` is called from `renderPager` and puts `#lbtabs` before the count), the sets as **one pill** (`pillSelect`, "Standard ▾",
  Custom when the list matches none — tapping Custom opens Filters ▸ Stats); the rows' box is the whole framed table. The **Dates tab**'s
  Last N days / Last N PA show the number box and nothing else (one-tap presets were tried and taken out the same hour at Sean's say), and the listing minimum inside a
  window is **`listMin`** — Last N lists anyone with ¾ of N, a date range / last N days scales the Min box by the window's share of the
  season's game days (a full-season 300 had listed nobody over 30 days); Recent keeps its own "at least" box. The count line says the
  window's minimum ("292 hitters · 2026 · 49+ PA in the window").
  **Then** (Sean, the same hour, from a screenshot of the Position dropdown): the dropdown shows **no tab row** on the Leaderboard /
  Recent (`popBody` skips `grpTabs()` under `onePage()`, class `notabs`) since the buttons are the tabs; the **Season / Recent switch is
  gone** from the bar (`seatFilters` removes it everywhere — the Dates presets cover a recent window; `#trending` still works by hash);
  the **Hitters / Pitchers switch is gone** (the Position button has them). The row is the six buttons, the Standard ▾ pill, the count.
  **Same hour**: the **Min PA / IP box rides in that row** too (Sean: "add in the min PA box to that top area instead of one of the
  filter pop up boxes ... for pitchers ofc make it innings"): `renderPager` keeps `#minfield` in `#pagertop` across redraws (it parks
  it rather than removing it, and never moves it when it's already after the buttons, so typing keeps the cursor), `parkControls`
  leaves it there, and the Filters panel's Order and minimum row has no Min box or Per page on the Leaderboard; the label is Min IP for
  pitchers (`renderMin` / `sampleLabel`). The Stats panel lists the **Pitching+ family as its own group** — Pitching+, Whiff+ (loc),
  Batted-ball+ (loc), Location+, Pitching uERA — whatever the card's data carries (Sean: "i dont see any of the pitching+ stats").
* **Command (Sean, 3 Oct 2026)**: see §4 — two more models (swing, called strike) give every pitch a strike chance and a chase chance
  from where it was thrown and the count; **xBB%** is the walk rate those spots deserve, **Pitching uBB%** (0.6 uBB% + 0.4 xBB%) is what
  Pitching uERA walked, **Command+** was xBB% as a share of runs against the league. **All of it came off the site the same evening**
  (Sean: xStrike / xChase "way too inaccurate", then "get rid of the command models entirely"): both uERAs walk at the old uBB% again and
  no column remains; the build's sums are inert. Don't bring any of it back unasked. Needs the models retrained (Actions → Train Stuff+ models) and every
  season rescored; a file built before the fields reads "–" and keeps the old Pitching uERA walks.

* **Home, 3 Oct 2026** (Sean: "not make it the starred players ... leaderboard for both xwoba and pitching uERA and then also add a
  trending for hitters of last 100 PAs and then last 50 IP for pitchers by pitching uERA", then "get rid of Sean's Site on it too",
  "make the leaderboard have the same column headers format as the stuff+ table"): `renderHome` draws two cards — **leaders**
  (xwOBA, 300+ PA; Pitching uERA, 100+ IP, `puOf` from the pool's stats) and **Trending** (xwOBA over each hitter's last 100 PA, 75+ in
  the window; Pitching uERA over each pitcher's last 50 IP, 37.5+) from the day rows through `withWindow`, "Loading game-by-game
  data…" until `ensureDays()` has days.js, then it redraws itself; each list's name opens the Leaderboard with that position, sort and
  window. No starred-players card. The header's **wordmark is hidden** (`header.top .wordmark { display: none }`) — Home is in the nav.
  The Leaderboard's column names wear the Stuff+ table's header format (11px, 8px above and below; the end of `styles.css`), and the
  rows' box has a 1px navy outline. **The home lists fill the screen** (Sean, the same hour: a desktop had the bottom third blank): a
  phone shows five rows a list, a desktop as many as its height holds (`N` in `renderHome`, 5-15, 50px a row under a 310px allowance).
  The Stuff+ table has the same navy outline and the Leaderboard's rows are as tall as its (46px, `min-height: 45px` on `.row-main`;
  Sean, the same hour). A list row's second line leads with the **team** (`.teaml`, Sean: "add the team in like the stuff+ table has").

* **The format pass, 3 Oct 2026** (Sean picked items 1-8 and 10-15 of a recommendations list; **9, a stat strip under the card's
  band, was mocked up and declined** — "oh no dont do that"; don't bring it back unasked). The block at the end of `styles.css`
  ("the format pass"): **one frame** — every table, card and popup in a 1px outline of `--frame` (navy; `#4d6ea3` in dark mode, where
  the navy vanished); **one table skin** — the Fantasy page, the Stuff+ board, the Leaderboard and every card table (Season Stats,
  Game Logs, Stuff, Fantasy, uERA) have 11px grey column names on the pale ground over a grey hairline (the 2px light-blue rule is
  gone), 13px tabular cells, 46px rows (the card's own rules carry `#modal`, so the skin's do too); the Leaderboard's cells at 13px;
  a ▾ / ▴ on the sorted column name (`#colhead .h[aria-sort]::after`); **fewer blues** — button, pill, segment and card-tab outlines
  are grey (`--line-soft`), light blue only while active or open, the home lists' links in `--ink-2`; the phone's Leaderboard filter
  row is one sideways-sliding line; Similar is plain names with dots between; the home lists' team line 11px and value 13.5px. In
  `app.js`: the Stuff+ board's rate cells drop the % (the headers say Use% / xWhiff% / xGB% / xPU% / …·loc%) and **colour only the
  sorted + column** (`pb.heat`, a "Colour: sorted / all" pill); the pitchers' headline column is **Rating** (was "Score"; the tooltip
  carries `scoreNote.P`); **Table format left the Leaderboard's row for the ⋯ menu** (`renderChrome`, `placePop` hangs it under the
  first button); home has a third card, **Last game day** (the latest day in `meta.days`: the best xwOBA games with 3+ PA from
  `hitGameLog`, the best starts by Stuff+ with 3+ IP from `gameLog`), the three cards side by side from 1180px (`.hgrid`, names 13px there).
  **Table headers are navy with white text** (Sean, the same evening: "make the tables headers be navy and white text"): the block
  after the format pass in `styles.css` — `#colhead`, `.ftable th`, the Stuff+ board, every card table and the game log (whose own rule
  carries `:is(#modal, #xboard)`, so the override does too); the sorted column name is light blue on the navy.
  **Then** (Sean, the same evening): **no ▾ on the sorted column name** — the Leaderboard's header row keeps the two-line height it had
  with it (13px above and below, ~40px); and the **card's tables are compact again** (12.5px cells, 5px padding, ~30px rows, the navy
  header 6px above and below) — Sean: "way too big for what is needed for the player card". The 46px rows stay on the lists.

* **One Pitching+, the whiff check, Skills first (Sean, 4 Oct 2026: "get rid of stuff+ and pitching+ being separate and just have one
  pitching+ stat that basically alerts pitchers that are getting more whiffs than their stuff and command would indicate and are likely to
  regress next year ... and then also an indicator for the other case ... on the pitcher player cards make the first section called Skills
  and then add in gb% and popup% and mix woba and yeah change mix era to mix woba")**: **Pitching+ is the one grade shown** — the card's
  Stuff section is Pitching+ · Whiff+ · Batted-ball+ · Location+ · velo · extension (`PITCHER_CARD` / `PITCHER_SUB["pitch"]` in the build,
  `PCT_COLS_P`; `data.js` patched by hand), the Stuff tab is gone (`BTABS_P`: Pitching+ · pERA · Game Logs · uERA), the header link and the
  board (`#pitches`) say Pitching+ and the board's columns are the location family only (`pb.sort` falls back to `pitp`), Game Logs grade
  each outing and each pitch of a day by Pitching+ (`gameLog` reads `stuffPlusLoc(g).pitch`; `gamePitches` adds `locDelta` on the day's
  `nl / wl / … / ps` sums via `withTypeBase`; `seasonPitches` reads `pitp / whfpl / bbpl / xwhfl …`), home's last-game-day list is "Pitching+
  that start", Similar's skill list uses `pitch`, the Leaderboard column set is **Pitching+** (`LB_SETS`), and saved lists / sorts drop
  `stuff swhf sbb suera aopt` on load. Stuff+ is still **built** (the models, day sums, `m.stuff / swhf / sbb`, Stuff uERA and Arsenal Opt.
  in `app.js`) — it's inside Pitching+ and the Pitching+ tab's sub-head says "stuff alone N" — just not a card metric, column or tab. Don't
  bring the separate Stuff+ views back unasked. **The whiff check** (`renderWhiffCheck` / `wgapVerdict` under the Pitching+ tab's table, and
  the column **Whiff vs proj.** `wgap` in `SIDE_P` / `LB_EXTRA_P` / `NEXT_KEYS`, pool stat + percentiles, lower = better, signed): his
  Whiff% minus `projRates(p).xw` (pWhiff%, the next-season projection that never sees his actual rate). History 2020-26, 300+ BF both
  years (scratch `wgap.py`): 2-4 over → 76% lost whiffs next year, −2.0 (K% −2.2); 4+ over → 96%, −3.7 (K% −3.5); 2-4 under → 82% gained,
  +1.8 (K% +1.3); within 2 → coin flip; slope −.67 (two thirds of the gap comes back); r with next year's whiff change −.45. Verdicts:
  ≥ +2 "Likely to regress", ≤ −2 "Likely to improve", else "In line", each with its history line. Kyle Bradish 2025 (34.8% on 126 BF vs a
  25.8% projection) → 23.6% in 2026, and his 2026 card reads "Likely to improve · −3.7". **Skills** is the card's first section: Whiff%,
  Strike%, GB%, Popup%, **Mix wOBA** (`mixw` for pitchers: `mixWOBA` in `app.js`, the league's wOBA per ball in play for his mix with the
  air balls split at the pool's line-drive share, lower = better; pool stat + `statsFor` + `metricValue` + sort, the hitters' `m.mixw`
  untouched); Batted Ball is GB% · Popup% · Mix wOBA and Mix ERA is a column only (still in `PITCHER_CARD`'s Batted ball group for the pool).
  The glossary's `mixw` entry covers both sides.

* **pERA, Pitching uERA and the Game Logs tabs off the cards (Sean, 4 Oct 2026: "Get rid of pERA and pitching+ uERA I simply just want
  expected whiffs GBs and pus. And no need for game logs on pitcher or hitter player cards")**: `BTABS_P` is Pitching+ · uERA, `BTABS_H` is
  Mix; the Pitching+ tab shows the table (xWhiff / xGB / xPU against actual, per pitch and in all) and the whiff check, no uERA box under it;
  the Leaderboard's Projected group is pWhiff% · pGB% · pPU% · Whiff vs proj. (`NEXT_KEYS`); `RETIRED_P` (`stuff swhf sbb suera aopt puera
  pera nk nbb`) keeps those keys out of the Sort by list, `LB_EXTRA_P` / `LB_SETS` / `VS_P` no longer name them, and saved lists drop them on
  load. Home's leader and trending lists are **uERA** (`puOf` reads `st.uera`). Everything is still computed (`renderNextTab`,
  `renderGameLogs`, `pitchUERA`, the pool's `pera / nk / nbb / puera`) — a UI change brings any of it back; don't, unasked.

* **Expected = the Pitching+ model's own numbers (Sean, 4 Oct 2026, Ian Seymour's card: "his expected whiffs are 26.9 not 25.1")**: the
  whiff check and the xWhiff% / xGB% / xPU% columns (`nwhf / ngb / npu`, group "Expected (Pitching+)") read `projRates(p)` = `pitchRates(p)`,
  the location-aware model's rates on his swings / balls in play — the same numbers as the Pitching+ tab's All pitches row. The two-model
  next-season blend (`PPITCH` / `projPitch`, still in the per-pitch `renderNextTab`) had read a point or two off the table and confused the
  page. The whiff check's history is on this gap (scratch `wgap2.py`): 2-4 over → 77% lost whiffs, −2.2 (K% −2.3); 4+ → 100%, −3.9 (K%
  −4.6); 2+ under → 73% gained, +1.5 (K% +0.9); within 2 → −0.7, the league's drift. The models themselves are unchanged (the fixed file
  trained through 2025); Seymour's four-seam reads 23.0 expected / 26.0 actual, his changeup 35.4 / 38.4.

* **nERA where uERA was (Sean, 4 Oct 2026: "get rid of uERA and just go with a luck neutral ERA called nERA and place that on the player
  card where uERA was")**: the band's season line reads nERA (the view's `V(p).m.nera` under a filter, `p.m.nera` otherwise), the card's tab
  strip is Pitching+ · nERA (`renderLuckBox`; `BTABS_P`), Season Stats' last column is **nERA** (the season's own, chipped by its percentile
  among that season's pitchers — `uera(season)` now returns `V(q).m.nera` / `pct.nera`; a minors line shows its level's own through `milbN`,
  the MLB-equivalent uERA column is gone from there, `milbU` stays for Call-up Watch), home's pitcher lists are nERA (`puOf`), the Standard
  column set ends in nERA, `uera` is in `RETIRED_P` and dropped from saved lists, Similar's skill list uses `nera`, and `uera` left
  `PITCHER_CARD`'s Expected & contact (uK% / uBB% / u(K-BB%) stay as columns). uERA is still computed everywhere underneath. **The overnight
  cloud build regenerated `data.js` from a checkout older than the day's PRs** (its `--steps mlb` ran last in a rescore job started at 20:45),
  which put the 50 / 50 weights and the old card layout back on the live site for a few minutes; `data.js` was re-patched by hand. A rescore
  run's final MLB build uses the `tools/` it started with — merge `tools/` changes before dispatching one, or re-patch `data.js` after.

* **xRating (Sean, 4 Oct 2026: "an xRating, that has the same weights but uses xwhiff, strike%, and then the expected mix woba from
  pitching+")**: `meta.pitcherWeights` over the percentiles of the Pitching+ model's expected Whiff% (`nwhf`), his Strike% and **xMix wOBA**
  (`nmix` = `mixOfShares(xg, xp, sorted)`: the Mix wOBA his expected GB% / PU% imply, air balls at the pool's line-drive share, lower =
  better) — pool stat `xrat` + percentiles + sorted (the pool's `PK` block and `statsFor`; the key map `X = { whf: "nwhf", mixw: "nmix" }`
  so a weights change in the build carries over), columns xRating / xMix wOBA (`SIDE_P` / `LB_EXTRA_P` / `NEXT_KEYS`), a "Rating N ·
  xRating N" line on the Pitching+ tab above the whiff check (`.xrating`; names a gap of 8+). Backtest 2015-26 starters, 15+ GS
  (scratch `xrat.py`): next season's points per start r .52 vs the Rating's .54 (same season .66 vs .73), year to year .79 vs .73, and
  Rating − xRating predicts next year's Rating change at slope −.44 (half the gap closes). Bubic 2025: Rating 84, xRating 67 → 2026
  Rating 56. The Rating itself is unchanged.

* **As a starter, and xRating beside the Rating (Sean, 4 Oct 2026: "pitchers are relievers in year 1 and then become starters in year 2
  ... is there a way to basically translate that ... And in the tables put xRating right next to rating")**: a reliever's Pitching+ tab
  carries an **As a starter** line (`renderAsStarter` / `AS_SP` / `asStarter`): his xWhiff, Pitching+ and FB velo moved by the
  reliever-to-starter effect from history — every RP → SP pair 2015-26 (102) against RP → RP (1,724), scratch `role.py`: the next-season fit
  for the movers minus the fit for the stayers, at his value (xWhiff 3.47 − .19x, Pitching+ 27.17 − .32x, Stuff+ 27.29 − .32x, velo
  15.30 − .17x — a −0.9 whiff point, −4 to −7 Pitching+ and −0.6 mph for a typical reliever, more the better his reliever numbers; Strike% goes the
  other way, +0.4 to +0.5 (`role3.py`: Zone% +0.7, first-pitch strikes +1.0, three-ball strikes +3.0, Chase% flat, BB% −1.1 — a starter
  paces himself; `strk: [1.38, −.015]` in `AS_SP`, on the line and in the starter xRating); Location+ doesn't move; the mix barely does and is carried for completeness — `role2.py`: xGB% 4.42 − .120x ≈ −0.8, xPU% +0.1, xMix wOBA
  .0629 − .167x ≈ +.001, shown on the line and in the starter xRating) — and his **xRating among starters** (the translated xWhiff, his Strike% and expected mix placed in
  the SP pool). Bubic 2024: xWhiff 27.7 → 25.9 (2025 actual 25.1), Pitching+ 106 → 100 (actual 96.5), xRating 86 → 77 among starters.
  The reverse (SP → RP: +1.3 whiff, +6.5 Pitching+, +1.1 mph) isn't shown. **xRating is the first column** of every pitcher column set
  (`LB_SETS`, right after the Rating headline) and `state.lb.xratFront` moves it to the front of saved lists once.

* **The SP / RP split on the Pitching+ tab (Sean, 4 Oct 2026: "make it so the pitching+ stuff and xwhiff xgb and xpu work for the RP and sp
  splits for guys who did both")**: it always was wired (`arsenalView` filters the arsenal day rows by the started flag) but had been
  broken since the location family shipped — `meta.arsDayFields` carries **`gs` twice** (the started flag at index 3 and the stuff-only
  ground-ball chance sum `gs` in `nl wl ws nb gl pl gs ps`), `Object.fromEntries` keeps the later index, so the role filter compared a
  probability sum with 0 / 1 ("As SP" read "No graded pitches", "As RP" summed a few dozen pitches). `arsenalView` now reads the flag at
  `ARS_F.indexOf("gs")` (`gsI`); the sums still use the later `gs` for the chance. Don't rename either field — every `hist/ars-*.js`
  carries the list. Under a role split the tab's head, table, xWhiff / xGB / xPU pairs, the whiff check and the Rating · xRating line all
  follow (the day rows' sums in `V()`, the pool in that split).

* **xSkills (Sean, 4 Oct 2026: "below skills can you put xSkills which is their xwhiff, strike%, and expected mix woba")**: the pitcher
  card's second section (`PCT_COLS_P`), xWhiff% · Strike% · xMix wOBA — the xRating's inputs, ranked off the pool's `nwhf` / `nmix` stats
  (their percentiles come from the pool's PK block, so a window or split re-ranks them like everything else).

* **All as SP (Sean, 4 Oct 2026: "for pitchers who did a bit of both SP and RP can you normalize their RP xWhiff and xgb and xpu for them as a
  starter if the filter is on starter. So again still show all their innings but just show it as they were a starter")**: a fourth Role option
  for `bothRoles(p)` pitchers, `state.split.role = "spn"`. `roleOf` returns it; `roleFilt` (−1 / 1 / 0 for the day filter — spn keeps every
  day), `roleNorm` and `roleWord` ("all innings as SP") sit beside it, and the two game-log filters (`fViewLine`, the Fantasy tab) treat it as
  all. `V()` sums, beside the raw day rows, `tN.stwl / stgl / stpl` with the relief days' sums (`gs` flag 0) moved by `spNorm(k, sum, n)` =
  `(1 + b)·sum + a·n / 100` from `AS_SP`'s xwl / xgb / xpu — and hands those to `_stwl / _stgl / _stpl`, so `pitchRates` → `projRates` →
  nwhf / ngb / npu / nmix / xrat / wgap (the pool's PK block, `statsFor`, xSkills, the whiff check, the Rating · xRating line) all read the
  normalized rates; `stuffPlusLoc` keeps the raw sums, so Pitching+ / Location+ don't move. `arsenalView` does the same per pitch type
  (`wlN / glN / plN` beside `wl / gl / pl`; `locDelta` prices the raw spots), so the Pitching+ table's xWhiff / xGB / xPU per pitch and the
  All pitches row match. A `.spnorm` note under the tab says what moved. Under the mode the whole pool is normalized the same way (every
  pitcher's relief days), which is the reference the percentiles want. Montero 2026 (25 GS of 32 G): xWhiff 22.4 → 22.3, xGB 41.0 → 40.9.

* **Zone & Chase is the walk formula (Sean, 4 Oct 2026: "replace strike % zone % and chase % with the stats in that formula with a 0.82 r^2")**:
  the pitcher card's Zone & Chase section is BB% · Strike% · **1st-pitch Strike%** · **3-ball Strike%** (`PCT_COLS_P`; `fstrk` / `b3strk`, built
  since 3 Oct 2026, now card metrics through `PITCHER_CARD`'s Zone & chase group — `data.js` patched by hand — so the pool ranks them; labels in
  `OUTCOME_LABEL_P`, glossary entries, `SHORT`, the Stats panel's Discipline group). Why (scratch `bbstrk.js`, every 100+ BF pitcher-season
  2020-26, BF-weighted): BB% on Strike% alone R² .58 (error 1.67 points); on Strike% + first-pitch + three-ball strike rates R² .82 (1.09). At
  the same Strike% a higher-whiff pitcher walks more (+0.12 BB% per Whiff% point: Strike% counts whiffs and fouls, which bunch in two-strike
  counts, and PAs that don't end on contact run to three balls — K% and BB% are uncorrelated raw, r .28 at fixed Strike%); the residual's
  correlation with three-ball strike rate is −.70, with Zone% / Chase% / Swing% under .06. The "walks beyond Strike%" residual repeats year to
  year at r .49 (half skill, half noise); three-ball strike rate itself at .39. Zone% / Chase% stay fold-outs under Strike% (`PITCHER_SUB`) and
  columns. Files built before the count-state fields show "–" for the two bars.
  **xBB% (Sean, the same hour: "below bb% add xBB%")**: the formula itself as a card metric right under BB% — `xBBFormula(m)` / `XBBF`
  (61.762 − 0.545·Strike% − 0.026·1st-pitch Strike% − 0.229·3-ball Strike%, the pooled BF-weighted fit; the SP / RP fits were within 0.1 of
  it), set on `V(p).m` for every pitcher view like the hitters' xK%, key **`xbbf`** (`xbb` was the command models' walk rate and the
  saved-list migration still drops that key), a `SIDE_P` def (lower = better) so the pool ranks it, glossary / `OUTCOME_LABEL_P` / `SHORT` /
  Stats-panel Discipline entries. Misiorowski 2025: 11.0 actual vs 7.9 expected; 2026: 6.6 vs 5.4. Null without the count-state fields.
  **Then the columns rebalanced (Sean, the same hour: "put that section on the right side ... get rid of the stuff models ... just make it
  fastball velo and extension ... put results below xSkills")**: `PCT_COLS_P` left = Skills · xSkills · Results · Swing & Miss, right = Zone &
  Chase · Batted Ball · Stuff (Fastball velo, Extension only — Pitching+ / Whiff+ / Batted-ball+ / Location+ live on the Pitching+ tab and
  stay columns). Ten rows a column. **xSkills is xWhiff% · xBB% · xMix wOBA** (Sean, the same hour: "replace strike% with xBB%") — the
  xRating's own inputs are unchanged (Strike%, as the Rating).
  **xK% (Sean, the same evening: "an xK% in the xSkills and base the whiff% in the model on their xWhiff%")**: the K% formula (scratch
  `bbstrk.js` / `kconv*.js`: K% = −26.03 + 0.583·Whiff% + 0.552·Strike% + 0.367·2-strike Whiff% − 0.174·2-strike Swing%, every 100+ BF
  pitcher-season 2020-26, BF-weighted, R² .80 / error 2.4 against Whiff% alone .71 / 2.8) run with **the Pitching+ model's expected whiff
  rate** (`projRates(p).xw`) in place of his and his two-strike whiff rate scaled by the same ratio; Strike% and the two-strike swing rate
  his own — `xKFormula(m, xw)` / `XKF`, key **`xkf`** (the hitters' xK% is `xk`), computed where `nwhf` is (the pool's PK block, `statsFor`'s
  `nx`) since it needs `projRates`, so it's in `NEXT_KEYS` (Stats group "Expected (Pitching+)", the sort-key path), a `SIDE_P` def, labels /
  glossary / `SHORT`, and **xSkills is xWhiff% · xK% · xBB% · xMix wOBA** (eleven rows on the left, ten on the right). What the K% residual
  is: it correlates with called strikes / Strike% / Zone% (+.34), two-strike zone rate (+.26) and two-strike whiff rate (+.19), walks −.24 — a
  whiff is a strikeout only with two strikes; it repeats year to year at r .49 (odd / even game days within 2026: .19, so a single season is
  half noise), a career BF-weighted version at .52, and it regresses at exactly K%'s own rate (next K% = 4.4 + .77·K% − .04·gap), so it is a
  **trait, not a regression flag** — Wheeler +2 to +3 every year (Strike% 64-67, two-strike whiffs ≥ his overall, two-strike zone 42-47%),
  Hunter Brown / Skenes / Cole / Misiorowski +2 to +3 career; Wandy Peralta −3.7, Grant Holmes −3.0, Sánchez −2.4, Valdez −1.9, Webb −1.6
  (sinker / contact pitchers who pitch to contact once ahead). A process-only model of the gap (two-strike zone, FB share, chase, Z-Contact,
  best-pitch gap, zone, count strikes, velo) reaches r .45 same-season / .36 next and misses Wheeler and Webb entirely — their trait is in
  sequencing / called third strikes the build doesn't keep. Candidate fields for a later build: two-strike called-strike rate, two-strike foul
  rate, put-away pitch share. Sasaki 2026: K% 23.6, xK% 29.1 (xWhiff 34.4 vs 29.7 actual; two-strike whiffs 25.5 under his overall).
  **Then the most accurate version (Sean, the same evening: "make it so xK% is whatever formula gives you the most accurate version", "make
  xskills just use xk, xbb, and mix xwoba", "make the weight for xskills 55%/35%/10%")**: `XKM` / `xKModel(m, xw, xws)` — scratch `xkfit.js`,
  every 100+ BF pitcher-season 2020-26, each input centred on its season's 100+ BF league, ridge λ 3, held out season by season (300+ BF
  scored). With his actual whiff rates the best same-season fit (all rates + stuff, rmse 1.43) is uK% in all but name and forecasts next
  year's K% no better than his own K% (3.61 vs 3.55); with the whiff side **expected** — `projRates(p).xw` (location-aware, over swings) and
  `stuffRates(p).xw` (stuff-only), no actual Whiff% / CSW% / SwStr% / two-strike whiff — plus Strike%, Swing%, Z-Contact%, Zone%, Chase%,
  first-pitch / three-ball strike rates, two-strike swing and zone rates, FB velo, extension, Pitching+ and Location+ it reads 1.95 same-season
  and **3.40 next season, the only version that beats his own K% at next year's** (the 4-stat xWhiff form 3.75, Whiff% alone 3.62); SP / RP
  fits were no better than pooled. Three tiers (full → without the stuff grades → `xw strk swing zcon zone osw` for the minors) through
  `rateFit(…, "k", XKM, L)` with `L = lgRatesP()` (now carrying `pitch`) plus `lgXw()` — the dataset's BF-weighted expected whiff rates over
  every 20+ BF pitcher, cached per `viewKey`. Centring on the league is what takes the 2026 model's hot calibration out (Sasaki 29.1 → 26.3).
  **xSkills is xK% · xBB% · xMix wOBA** and the **xRating is their percentiles at 55 / 35 / 10** (`XRW`; the pool's xrat block, `statsFor`,
  the `.xrating` line and glossary say so; the Rating keeps `meta.pitcherWeights`). `renderAsStarter` re-runs xK% / xBB% on the translated
  inputs (both whiff rates by `xwl`'s effect, Strike%, `fstrk` +1.0 / `b3strk` +3.0 from role3.py as plain shifts in `AS_SP`, velo,
  Pitching+) for the starter xRating and shows them on the line. 2026: Sasaki K% 23.6 / xK% 26.3, Wheeler 29.9 / 27.9, Webb 25.7 / 30.0,
  Devin Williams 28.3 / 33.3.
  **And then same-season accuracy over forecasting (Sean, minutes later: "i dont care as much about its ability to predict future seasons, i
  want the highest correlation for current season. My goal is to find guys that are true underperformers and weed out guys that are true
  overperformers or frauds")**: `XKM` is the actual-rate fit — Whiff%, CSW%, SwStr%, two-strike Whiff%, Strike%, Swing%, Z-Contact%, Zone%,
  Chase%, first-pitch / three-ball strike rates, two-strike swing and zone rates, GB%, PU%, FB velo, extension, Pitching+, Location+, Stuff+
  and both expected whiff rates (small weights), pooled, centred on the season's league, ridge λ 3: held out season by season rmse 1.42 /
  mean error 1.12 on 300+ BF pitchers, in-sample r .954 (the expected-whiff version 1.95, Whiff% alone 2.36; by-role fits no better). Tiers
  without the stuff grades (1.54) and the six basic rates (1.99). So K% − xK% is pure conversion now — and it repeats (Wheeler over, Webb
  under, every year), so the glossary says it's what he does, not what he'll stop doing; the whiff check stays the luck read. The As-a-starter
  line moves his actual whiff rates by the `xwl` effect too (`wr`) so the starter xK% is consistent. 2026: Sasaki 25.0, Wheeler 28.7, Webb
  27.9, Devin Williams 29.3.
  **Significance (Sean: "figure out the statistical significance of guys like tyler phillips, roki sasaki, skeens, wheeler, jacob webb";
  scratch `sig.js`)**: a season's K% − xK% gap has variance ≈ 0.76 + 763 / BF (sd 1.8 at 300 BF, 1.4 at 600), the 0.76 being the spread of true
  conversion talent (sd 0.87; 0.82 from the year-to-year covariance), so one season is about ¼ talent. Career gaps weighted by 1 / noise, with
  z: Hunter Brown +2.5 (4.6), Skenes +2.5 (4.0, p < .001), Mason Miller +2.6 (2.8), Cade Smith +2.2 (2.3); Wandy Peralta −2.7 (−3.9), Phillips
  −2.5 (−2.9, p .004), Webb −2.1 (−2.6, p .008), Valdez −1.2 (−2.9), Sánchez −1.2 (−2.4); Wheeler +0.4 (z 1.0 — his over-performance against
  Whiff% alone is fully explained by the fit's called strikes / two-strike rates), Cole +0.3, Sasaki −1.1 (z −1.0, two seasons; his 2026 halves
  split 32 / 26 on whiffs — noise), Misiorowski +0.1, Warren −0.7. Shrunk talent (gap × 0.76 / (0.76 + SE²)): Brown +1.8, Skenes +1.6, Peralta
  −1.6, Phillips −1.2, Webb −1.1, Sasaki −0.4.
  **Foul% — the mechanism (Sean, 4 Oct 2026: "do not use career differences. There has to be something that can explain this kind of like
  how with bb% there were more specific things that explained bb% compared to just strike %")**: scratch `mech.js` / `mech2.js` correlated
  the fit's leftover K% with everything the build carries that wasn't in it (per-pitch foul, in-play and called-strike rates from the day
  rows, two-strike pitch share, pitches / PA, HBP, fastball / breaking / offspeed share, best-pitch whiff and its gap over his average,
  fastball whiff, pitch-mix entropy, pitch count): only **foul rate** (+.43) and its mirror the in-play rate (−.42) move it; called strikes
  −.01, the arsenal shape under .14. Contact that goes foul keeps the strikeout alive, a ball in play ends the PA. With Foul% in the fit,
  held out season by season: rmse 1.42 → **0.63** (mean error 0.50; foul share of contact 0.61, two-strike share alone 1.02), and the named
  gaps vanish — Skenes 2026 +3.1 → +0.9 (foul 21.0% vs league 18.3), Webb 2025 −3.7 → +0.3 (17.6), Phillips 2025 −4.2 → +0.2 (13.7), Wandy
  Peralta 2025 −3.5 → −0.6, Valdez / Sánchez to ~0; Mason Miller stays +3 (hitters can't foul off 103). Foul% repeats year to year at r .56
  (Strike% .59, in-play rate .75) and runs with Swing% (.75), Zone% (.48), fastball share (.27), breaking share (−.22). **Shipped**: the build's
  `pitcher_metrics` flags `foul = strike & ~whiff & ~bip & ~cs` → `Foul_pct` → `m.foul`; `data.js` and `hist/mlb-2020…2025.js` patched
  from their day rows (scratch `patchfoul.js`: strk − cs − whf − bip over pit); `V()` re-derives it in a window / split; `lgRatesP` carries
  it; `XKM` leads with the two Foul% tiers (full, no-stuff) and keeps the three without it for older files; **Foul%** is a `SIDE_P` metric
  (Leaderboard column, Stats ▸ Discipline, glossary), not on the card. 2026 cards: Skenes K% 28.1 / xK% 27.2, Webb 25.7 / 26.3, Phillips
  18.8 / 19.3, Sasaki 23.6 / 24.6, Wheeler 29.9 / 29.7. The career-gap significance numbers above are of the pre-Foul% fit and are history.
  **Strikes section, no xSkills, Mix xwOBA (Sean, 4 Oct 2026: "a player card section that shows called strikes, whiffs, and then foul strikes
  ... the way that that k% model does", "get rid of the xskills section and just put the three things under xskills under skills", "for xmix
  woba call it mix xwoba")**: `PITCHER_CARD` gains a **Strikes** group — `cstr` **Called Strike%** (called strikes per pitch; the build's
  `CStr_pct` = CS / Pitches, `V()` from `t.cs / t.pit`, and `csw − swstr` on a file built before it), `swstr` SwStr%, `foul` Foul% — the
  three strikes that keep a plate appearance alive, as xK% reads them (`data.js` patched; Foul% left `SIDE_P` for the card). `PCT_COLS_P`:
  left = **Skills** (Whiff%, Strike%, Mix wOBA, xK%, xBB%, Mix xwOBA) · Swing & Miss (11 rows), right = Zone & Chase · Results ·
  Batted Ball · Stuff (12). **Then no Strikes section** (Sean, the same hour: "dont add a new section just add the called strikes, whiffs,
  and foul strike thing to the swing and miss section and also add xk% to that too"): **Swing & Miss** is K% · xK% · Whiff% · Called Strike% ·
  SwStr% · Foul% (the three defs live in the build's Swing & miss group; `data.js` re-patched), 12 rows a column. **Then Skills is xK% ·
  xBB% · Mix xwOBA alone** (Sean, the same hour, from a screenshot: "get rid of the top 3") — Whiff%, Strike% and Mix wOBA still show in Swing &
  Miss, Zone & Chase and Batted Ball; 9 rows left, 12 right. **Then Mix wOBA, not Mix xwOBA** (Sean, a minute later: "keep it to xK%, xBB%, and mix woba"):
  Skills = xK% · xBB% · Mix wOBA; Mix xwOBA stays a column and the xRating's third input.
* **Rating on the expected rates, xRating on the stuff (Sean, 4 Oct 2026: "make rating xK%, xBB%, and mix woba", "xrating xK% but if possible
  using their stuff expected whiff rates and stuff expected foul rates ... use xBB% as standard and the use mix xwoba based on their stuff")**:
  `PITCHER_SCORE_WEIGHTS` / `meta.pitcherWeights` = **xK% 55, xBB% 35, Mix wOBA 10** (`data.js` + `scoreNote.P` patched; the Whiff% 55 /
  Strike% 30 / Mix wOBA 15 Rating lasted the day). xK% isn't on `m`, so `pool()` ranks it before the score (`pjs0` / `srs0`, re-used by the PK
  block) and `placeIn` places it first (`xk0`). **Stuff xK%** (`xks`, `xKStuff(m, xw, xws, xf)`): the same K% fit with the whiff side
  expected — the Pitching+ model's xWhiff for Whiff%, swings × xWhiff for SwStr%, called strikes + that for CSW%, two-strike whiffs scaled, and
  Foul% = the contact left (swings × (1 − xWhiff)) × the stuff model's foul chance on contact (`foulChance(p)`: `_stf / _stn` day sums in a
  window — `V()` now carries `_stf` — else the arsenal's `xfoul` by pitches); the expected whiff and foul levels are centred on the league's
  actual ones first (`lgXw()` now also carries `xfp`, the league's expected fouls per pitch) since the fixed models read 2026 ~2 points hot.
  Scratch `xks.js`, 300+ BF 2020-26: same-season r .87 with K% (xK% .99, Whiff% .87), next season's K% rmse 3.39 vs his own 3.55 and xK%'s
  3.55, and K% − Stuff xK% predicts next year's K% change at r −.36 (K% − xK%: −.07) — the forward read. **xRating = Stuff xK% 55, xBB% 35,
  Mix xwOBA 10** (`XRW`); the `.xrating` line, glossary (`xks`, `xrat`), `renderAsStarter` (Stuff xK% on the translated inputs), `NEXT_KEYS`,
  `SIDE_P` / `LB_EXTRA_P` column "Stuff xK%", the sort-key path. Note `patchfoul.js` re-serialised `data.js`, so its numbers are plain JSON
  (55, not 55.0) — match loosely when patching. **The centring came out an hour later** (Sean, on Skenes's card: "the model says his expected
  whiff% is 29.1% not 26.1%"): `xKStuff` takes the expected whiff and foul rates as the site shows them, so on a season the fixed models read
  hot every Stuff xK% sits ~2 points above K% (2026); the xRating is percentiles and is unchanged by it. `lgXw().xfp` is unused now.

* **Expected fouls with location (Sean, 4 Oct 2026: "factor in the sequencing location and count for expected foul balls to see if that improves
  it accuracy wise", then "ok do it")**: a ninth model in the fixed file, **`foul_loc`** = P(foul | contact) from the pitch's traits plus where it
  crossed (`lcols`, the location whiff model's inputs), trained in `train_stuff_models` beside the stuff-only foul model (which Stuff+ /
  Batted-ball+ keep). Backtest (scratch `foulseq.py`, models on 2020-24, 300+ BF pitchers, foul per contact): stuff only r .754 / .692 (2025 /
  2026), + location .787 / .740, + count .779 / .727, + count + the pitch before (type, velo change, spot moved, what it did, pitch number)
  .782 / .729, sequencing alone .755 / .709; next season (2025 → 26) .667 → .689 (his own rate .704); the residual repeats at r .33 instead of
  .39. **Count and sequencing add nothing on top of location and aren't shipped.** Skenes 2026: actual 56.9 (95th), stuff 52.4 (75th), with
  location 54.1 (86th) — about 40% of his gap; Wheeler matches percentile for percentile either way; Mason Miller 2026 (57.2 actual vs 54
  expected under every version) is what no pitch-level model gets. The chance is P(foul | contact) *at that spot*, so like the location whiff
  chance it's carried over the pitches actually contacted with the stuff-only chance on the same pitches: `st_nf / st_fl / st_fs`, day fields
  **`stnf stfl stfs`** (appended), arsenal-day `nf fl fs` (appended), `ctx.arsenal` **`xfoull`** (null under 5 contacted), `consts.stuff`
  `lgFL / lgFS`. `foulChance(p)` in `app.js` reads `_stfl / _stnf` (V() carries them) else the arsenal's `xfoull` weighted by each pitch's
  contact (`sw × (1 − whf)`), and falls back to the stuff-only `_stf / _stn` / `xfoul` on a file built before it — so **Pitching+ xK%** (the
  column and card label for `xks` since the same day; the key is unchanged) and the xRating move only once the models are retrained (Actions →
  Train Stuff+ models, dispatched 4 Oct 2026 with the rescore) and every season rescored. Until then the live numbers are the stuff-only ones.
* **The card, 4 Oct 2026 (Sean: "keep the skills section, for swing and miss just show k% and xk%, for zone and chase just show bb% and xbb% and
  call it walk avoidance, keep batted ball, no need to show results, (and also i dont care about saves showing on the header show k-bb% there),
  under stuff show instead the pitching+ xk%, show their regular xbb%, and show their pitching+ mix xwoba, and you can keep fastball velocity and
  also show their pitching+ as well")**: `PCT_COLS_P` left = Skills (xK% · xBB% · Mix wOBA) · Swing & Miss (K% · xK%) · **Walk Avoidance** (BB% ·
  xBB%); right = Batted Ball (GB% · Popup% · Mix wOBA) · **Stuff** (Pitching+ xK% · xBB% · **Pitching+ Mix xwOBA** · Fastball Velo · Pitching+) —
  the xRating's three inputs with his velo and grade, the stuff-side read of Skills. Results, Whiff%, Called Strike% / SwStr% / Foul%, Strike%,
  the count-state strike rates and Extension are off the card (still columns). The band's season line is nERA · ERA · K% · BB% · **K-BB%** (SV
  gone), in a window too (`seasonLine`). `OUTCOME_LABEL_P` labels `xks` "Pitching+ xK%" and `nmix` "Pitching+ Mix xwOBA" on the card (the
  column says Mix xwOBA).
* **x(K-BB)% (Sean, 4 Oct 2026: "under skills can you add in x(K-BB)% above mix woba, and also add x(K-BB)% to the leaderboards")**: `xkbb` =
  xK% − xBB% (both fits on his process), computed where xK% is (the pool's `PK` block, `statsFor`), in `NEXT_KEYS` (so the sort-key path and
  the Stats panel's Expected group carry it), a `SIDE_P` def (higher is better), labels / `SHORT` / glossary; Skills = xK% · xBB% · **x(K-BB)%** ·
  Mix wOBA; the Standard and Advanced pitcher column sets carry it after K-BB% / nERA, and `state.lb.xkbbAdd` slots it after K-BB% in a saved
  pitcher list once (so a saved Standard list stays Standard).
* **Rating = x(K-BB)% 80 / Mix wOBA 20 (Sean, 4 Oct 2026: "how does a weighting of x(k-bb)% and mix woba trend with ... points per start or ip",
  then "switch it to this instead and make it the most optimal weighting of the two")**: scratch `kbbrate.py` — every 100+ BF pitcher-season
  2020-26, ESPN standard points, percentiles within season × role, starters 15+ GS by points per start and per inning, relievers 40+ IP by
  points per inning, same season and next (368 / 460 pairs). The 55 / 35 / 10 Rating: SP pts/start r .791 / .563, RP pts/IP .664 / .468;
  x(K-BB)% 80 / Mix 20: .796 / .578 and .689 / .483 (SP pts/IP .817 / .568 → .830 / .589) — ahead in every cut, and 80 / 20 is the best split
  of the two on the mean of all six (85 / 15 a hair behind, 70 / 30 and 90 / 10 both worse). Why: x(K-BB)% weights xK% and xBB% by their own
  spreads (~75 / 25), and the free xK% / xBB% / Mix grid wanted 70-80 / 10-15 / 10-15 — xBB% alone is only r .46 / .25 with points. The gains
  are second-decimal; relievers' last-year points still beat any process rating at next year's (.64, saves and holds are role).
  `PITCHER_SCORE_WEIGHTS` / `meta.pitcherWeights` = `{xkbb: 80, mixw: 20}` (`data.js` + `scoreNote.P` patched); `pool()` ranks x(K-BB)% before
  the score (`xk0s` → `pct.xkbb`) and `placeIn` does too (`xkbb0`). **The xRating keeps the Rating's shape**: `XRW = {xkbbs: 80, nmix: 20}` with
  **`xkbbs` = Pitching+ x(K-BB)%** (Pitching+ xK% − xBB%; PK block, `statsFor`, `NEXT_KEYS`, `SIDE_P` column, glossary; `renderAsStarter`
  places it in the SP pool from the translated xK% and xBB%), so the Rating · xRating line compares like with like. Skenes 2026: Rating 86 ·
  xRating 69 (was 83 · 67); Wheeler 92 · 92; Misiorowski 96 · 91.
* **Results section (Sean, 4 Oct 2026: "add results section that goes up top that has the x(K-bb)% mix woba, and then his rating", then minutes
  later "get rid of results and in skills show just x(k-bb)%, mix woba and rating")**: then "for skills could you instead do xk%, xbb%, and x(k-bb)%"): the
  pitcher card opens on **Skills** — xK% · xBB% · x(K-BB)% (`PCT_COLS_P`; left = Skills · Swing & Miss · Walk Avoidance, right = Batted Ball ·
  Stuff, 7 / 7 rows). The Rating row (`RATING_M`, key `rating`) stayed wired but is off the card. **Stuff is Pitching+ xK% · xBB% · Pitching+
  Mix xwOBA** (Sean, the same night: "under stuff get rid of fastball velo and pitching+ and add in xRating", then "get rid of x(K-BB)% in skills,
  get rid of xrating in stuff, and add a rating section at the end with rating and xrating"): **Skills = xK% · xBB%**, and a **Rating** section
  closes the right column — Rating · xRating, both bubbles the number itself (`rating` via `RATING_M`; `xrat` gets `int: true` on the card).
  **Then (Sean, minutes later: "under skills add in mix woba", "move stuff to below skills and call it Expected Skills", "ok in skills only show
  x(K-BB)% and mix woba, and in xSkills only show the x(K-BB)% and mix xwoba for that too. And maybe in the pitching+ tab show the breakdown of
  the xK% and then obviously include the xBB% there too")**: left = **Skills** (x(K-BB)% · Mix wOBA — the Rating's inputs) · **xSkills**
  (Pitching+ x(K-BB)% · Mix xwOBA — the xRating's, labelled "x(K-BB)%" / "Mix xwOBA" on the card via `OUTCOME_LABEL_P`) · Swing & Miss (K% ·
  xK%); right = Walk Avoidance (BB% · xBB%) · Batted Ball · Rating (Rating · xRating). 6 / 7 rows. The **xK% breakdown** (`renderXkBreakdown`,
  `.xkbd`, on the Pitching+ tab under the Rating · xRating line): K% · xK% · Pitching+ xK% and xBB% in a line, then a table of the strike rates
  the K% fit reads — Whiff%, SwStr%, CSW%, 2-strike Whiff%, Foul% — actual beside what the stuff and spots say (the same substitutions as
  `xKStuff`), with the gap; xBB% is one number because the walk formula has no stuff side. The Rating row is special-cased in `renderPctPanel` (`RATING_M`, key `rating`, not a column): its value
  is `st.score` and, since the Rating is already a percentile blend, the bubble is the number itself (the tap note's league middle is 50);
  `OUTCOME_LABEL_P` / glossary carry `rating`.
* **Expected fouls with the batter's swing (Sean, 4 Oct 2026: "i just really want his and other players foul ball data to be accurate because it
  clearly is missing something since he clearly gets a lot of foul balls", then "ok implement this new foul ball model")**: Skenes's Pitching+ xK%
  sat 2-4 points under his xK% every year and the whole gap was fouls (actual foul per contact 59.7 / 55.1 / 57.3 against the stuff model's
  ~52-53; the whiff substitution nets to zero). A tenth model in the fixed file, **`foul_sw`** = P(foul | contact) from the pitch's traits, its
  spot and the **batter's swing** on it — `STUFF_SWING`: bat speed, swing length, attack angle / direction, swing-path tilt and the intercept
  point (bat tracking, 2024 on; `COLS` / `STUFF_TRAIN` carry them, `swing_features`), trained on the contact that has bat tracking (`fwcols` =
  the location model's inputs + the seven). Backtest (scratch `fetch2.py` re-reads 2024-26 from pybaseball's cache with the columns,
  `foulsw.py` scores each season with models trained on the other two; 300+ BF, foul per contact): location .741 / .773 / .734 (2026 / 2025
  / 2024) → **.766 / .787 / .762**, swing alone .737 / .753 / .726, and the spread of expected rates widens toward the real one (sd 2.6-2.8 →
  2.9-3.1 against 3.5). Skenes: 2024 59.3 actual, 52.8 → 56.0; 2025 54.3, 53.8 → 54.3; 2026 56.9, 54.1 → 55.1. Sasaki 2025 44.8: 52.0 → 47.2;
  Mason Miller 2025 61.2: 57.2 → 60.5; Phillips 2025 39.9: 45.8 → 44.8. It credits a pitcher for the defensive swings his pitches draw, which
  is a step closer to results than the whiff model — by Sean's choice. Per pitch, `_grade_stuff` grades a contacted pitch with a tracked
  swing by this model and the rest by the location model, so seasons before 2024 read the location number: `st_fw` (over `st_nf`), day field
  **`stfw`** (appended), arsenal-day `fw`, `ctx.arsenal` **`xfoulw`**, `consts.stuff` `lgFW`. `foulChance(p)` in `app.js` prefers `_stfw` /
  `xfoulw`, then the location pair, then stuff-only. Needs Train Stuff+ models + a rescore (queued behind the location one, 4 Oct 2026).
  Estimate before it lands (scratch, the backtest models on the 2026 SP pool): Skenes Pitching+ xK% 24.8 → ~26.5, xRating 69 → ~74.
 `nmix`'s label is **Mix xwOBA** everywhere (lower is better, as before). 2026 Skenes: Called 13.5 (6th pct),
  SwStr 14.4 (87th), Foul 21.0 (91st).

* **xK% and xBB% tabs (Sean, 4 Oct 2026: "a tab that shows the same expected strikeout percentile bars that we had before when we showed
  everything with like the formulas. and then also have that tab show the like pitching+ expected k stuff too and make that percentile bars as
  well", "a tab for expected bb% as well that has all those same percentile bars")**: `BTABS_P` is Pitching+ · **xK%** · **xBB%** · nERA. Both
  draw the card's percentile bars (`pctColumns` — the section drawing factored out of `renderPctPanel`, which keeps the ResizeObserver reset and
  the Similar row; `renderPctTab` wraps it with a note, `.pcttab`). **xK%** (`XK_COLS_P`): Strikeouts (K% · xK% · Pitching+ xK%), Strikes — actual
  (Whiff%, Called Strike%, SwStr%, CSW%, 2-strike Whiff%, Foul%), Strikes — Pitching+ expected (xWhiff%, **xSwStr% · xCSW% · x2-strike Whiff% ·
  xFoul%** — new pool stats `nswstr / ncsw / ns2whf / nfoul` from `xkParts`, the one place the Pitching+ xK% substitutions live now; `xKStuff`
  and `renderXkBreakdown` read it too; in `NEXT_KEYS`, the PK block, `statsFor`, `SIDE_P`, `SHORT`, the glossary), then Plate (Strike%, Swing%,
  Zone%, Chase%, Z-Contact%), Counts (1st-pitch / 3-ball Strike%, 2-strike Swing% / Zone% — `s2whf / s2sw / s2zone` got `SIDE_P` defs so the pool
  ranks them) and Stuff (velo, extension, Pitching+, Location+). **xBB%** (`XBB_COLS_P`): Walks (BB% · xBB% · uBB%), The formula (Strike%,
  1st-pitch, 3-ball), Zone & Chase, Whiffs. The sort-key path reads any `NEXT_KEYS` member off the pool's stats now.

* **Expected Called Strike% (Sean, 4 Oct 2026: "is the expected called strikes not a stable thing in the stuff/pitching model", then "ok we can add
  it to everything, and thus itll be added to the xk% calculation from pitching+")**: `ncstr` = the command models' called-strike chance per pitch
  (P(take) × P(called | taken) from the pitch's traits, spot and count — the build's `xstrk − xswing` for a season, the day rows' `stck − stcs`
  over `stcn` in a window via `m.xcraw`), **centred on the league's actual called-strike rate** (`xCalled(m)`; `lgRatesP` carries `cstr` and the
  raw `xcstr`), set on `V(p).m` beside `xbbf`. Why it's worth having (300+ BF pitchers 2023-26): same-season r with actual .68-.73, year to year
  .72-.74 against actual's .58-.65, forecasts next year's actual at .43-.55; the residual (framing, umpires, sequencing) repeats at .37-.53. The
  fixed models read 2025-26 ~0.5-0.8 points hot, which is what made xStrike% look wrong beside Strike% on 3 Oct — the centring takes that out.
  **It is inside Pitching+ xK%**: `xkParts` uses it for CSW% (expected called + expected swinging strikes) in place of his actual called-strike
  rate, so `xks` → `xkbbs` → the xRating move with it (Skenes 2026 Pitching+ xK% 26.7 with the location foul model's rescore in). A `SIDE_P` def
  (percentiles from the pool like any `m` stat, a Leaderboard column), a bar on the xK% tab after xWhiff%, a Called Strike% row in the Pitching+
  tab's breakdown, labels / `SHORT` / glossary. Files without the command sums (built before 3 Oct 2026) fall back to his actual rate. The
  expected swing rate stays unused for SwStr% (tested 3 Oct 2026: expected swing × expected whiff was worse everywhere).

* **The card regrouped, Raw / Stuff, Filters as a window (Sean, 4 Oct 2026, from Skubal's card: "a top one with skills that shows xk% and xbb%
  ... swing and miss ... walk avoidance ... batted ball ... a rating one with the rating, x(k-bb)%, and mix woba ... a switch for either raw or
  stuff and then the stuff one shows all the same stuff but based on the stuff models"; approved from a mockup, then "keep the stuff models
  expected stuff to just x...", and the Filters box "a pop up window that just has a clear button ... hit x in the right or click outside of it
  to exit ... doesn't ... shift down the player card")**: `PCT_COLS_P` (Raw) = Skills (xK% · xBB%) · Swing & Miss (K% · xK%) · Walk Avoidance
  (BB% · xBB%) | Batted Ball (GB% · Popup% · Mix wOBA) · Rating (Rating · x(K-BB)% · Mix wOBA); `PCT_COLS_PS` (Stuff) = the same sections off
  the Pitching+ models — Pitching+ xK%, xBB%, xGB% / xPU% / Mix xwOBA, xRating / Pitching+ x(K-BB)% / Mix xwOBA — labelled plain xK% / x(K-BB)%
  (`STUFF_LABELS`). `state.cardSide` (per device, `cardSide` in prefs), `sideSwitch()`: beside Filters on both — a desktop's horizontal, a
  phone's **vertical** (`.phside.vert`, Raw over Stuff; Sean, the same hour: "vertical so raw is on top and stuff is below and that way it can
  just exist next to it"), **to the left of Filters, each button the size of the Filters button** (Sean, minutes later, then 5 Oct 2026: "each of raw and stuff to be as
  big, so technically it should be twice as tall"; `playerHead` copies the Filters segment's width and the Filters button's height onto each
  button in a rAF, so real fonts match too; the row bottom-aligns beside the taller switch, so Filters is level with Stuff and Raw sits above (Sean, 5 Oct 2026) — the mobile `.phside.vert` rules at the end of
  `styles.css`). **Filters is a window** (`.phmodal` transparent backdrop + `.phwin.pop`, appended to `document.body` by `playerHead`,
  removed at the top of every `render`) **in the Leaderboard dropdown's dress** (Sean: "the same format as the filters button is on like the
  leaderboards"): hung under the Filters button (`place`, like `placePop` — a phone's spans the screen 8px in, re-placed on resize via
  `ov._place`), the small `.pop-close` × top right, the same `.phgrid` in a `.pop-body` (date inputs get a hair border so an empty iOS one shows),
  the split warning / days note, and a `.popfoot` with one "Clear" link (full season, every split); a tap anywhere else or Escape closes it (the
  document handlers test `.phmodal` / `.phwin`, on a phone too); nothing is put in the plate, so the card never shifts — `.phfilt.phpop` and
  its CSS are unused. xSkills is gone as a section (Stuff mode's
  Rating is it). **The xK% tab pairs the rates side by side** (Sean, same hour: "every stat that is being compared next to each other ... horizontally"):
  left column **Actual** (K%, xK%, Whiff%, Called Strike%, SwStr%, CSW%, 2-strike Whiff%, Foul%), right column **Pitching+ expected** (K%, Pitching+
  xK%, xWhiff%, xCalled Strike%, …) row for row — K% heads both so they align, and `pctColumns(…, { scaleAll: true })` puts the Poor / Average /
  Great scale on both charts (`pctChart`'s third argument) since the scale row is what had offset them; Plate under the left, Counts and Stuff
  under the right. A phone stacks the two.
* **No 2-strike Whiff% in xK% (Sean, 5 Oct 2026: "Cade Cavalli is a case where last year his whiffs were high but his xk% was low simply
  because his 2 strike whiff was low but then this year that flipped because his skill of getting whiffs translated")**: `XKM`'s five tiers are
  refit without `s2whf` (scratch `xkrefit.js`, same recipe — every 100+ BF pitcher-season 2020-26 centred on its season's league, ridge λ 3,
  pooled); 2-strike Swing% and Zone% stay. A whiff with two strikes is the strikeout itself, so it was a result in the fit and a season's run
  of them read as skill. Held out season by season: same-season rmse 0.63 → 1.04, next season's K% 3.57 → 3.49. Cavalli 2025 K% − xK% +0.1 →
  −1.6 (2026 K% 28.3, xK% 27.7), Wheeler 2025 0.0 → +1.9, Jacob Webb 2026 −0.7 → −1.9, Skenes 2026 xK% 27.0 / Pitching+ xK% 27.3. Pitching+
  xK% moves with it (`xkParts` still computes the scaled two-strike rate, unused by the fit); the xK% tab's pairs and the Pitching+ tab's
  breakdown no longer show 2-strike Whiff% (`s2whf` / `ns2whf` stay pool stats and columns). The Rating and xRating follow.
* **xK% off the card, Whiff% in its place (Sean, 5 Oct 2026: "completely eliminate the xK% and just translate it to whiff% and so the stuff
  xK% just becomes stuff xWhiff% or I guess the pitching+ one", "in swing and miss k%, whiff%, called strike%, and foul%", "in the walk
  avoidance show bb% xbb% and then show the inputs to xbb% below xbb%", then "not show called strikes. So just whiff% and fouls")**:
  `PCT_COLS_P` (Raw) = Skills (Whiff% · xBB%) · Swing & Miss (K% · Whiff% · Foul%) · Batted Ball | Walk Avoidance (BB% · xBB% · Strike% ·
  1st-pitch Strike% · 3-ball Strike%) · Rating (Rating · x(K-BB)% · Mix wOBA); `PCT_COLS_PS` (Stuff) the same with the Pitching+ model's
  xWhiff% (`nwhf`) and xFoul% (`nfoul`), labelled plain "xWhiff%" / "xFoul%" (`STUFF_LABELS`). Walk Avoidance moved to the right column so
  the columns stay level (8 / 8). The card tab `xk` is titled **Whiff%** and its pairs drop the K% fits (Actual: K%, Whiff%, Called Strike%,
  SwStr%, CSW%, Foul% against the Pitching+ expected ones); the Pitching+ tab's breakdown is headed "Strikes" (K% · Whiff% vs xWhiff% · xBB%).
  xK% / Pitching+ xK% are still computed — the Rating runs on x(K-BB)% 80 / Mix wOBA 20 and the xRating on Pitching+ x(K-BB)% as before,
  both Rating sections still show x(K-BB)% — and stay Leaderboard columns. If Sean wants the Rating itself rebuilt on Whiff%, that is a
  separate change.
* **xK% back, and xK% − Whiff% (Sean, 5 Oct 2026, an hour later: "go back to showing the xK% on the skills area and also add it to swing and
  miss too ... K%, xK%, and then add in whiff too, and add in xK%- whiff% as a stat too. I'll use that to identify guys that maybe could k more
  next year. And then go back to the xk% tab that has all of the k% inputs")**: `PCT_COLS_P` = Skills (xK% · xBB%) · **Swing & Miss (K% · xK% ·
  Whiff% · xK% − Whiff%)** · Batted Ball | Walk Avoidance · Rating; `PCT_COLS_PS` the same with Pitching+ xK%, xWhiff% and Pitching+ xK% −
  xWhiff%. **`xkw`** = xK% − Whiff% and **`xkws`** = Pitching+ xK% − xWhiff% (the pool's PK block, `statsFor`, `NEXT_KEYS`, `SIDE_P` defs with
  `sign: true`, `SHORT` / `OUTCOME_LABEL_P` / `STUFF_LABELS` / glossary; higher = converts beyond his whiffs). The xK% tab is back as it was
  (K% fits in both columns) and the Pitching+ breakdown is headed "xK% breakdown" again. Why the gap (scratch `conv.js`, K% beyond the K% his
  Whiff% alone implies, 2020-26): year to year r .47 / .53 / .57 at 200 / 300 / 500+ BF, about half of it carries (next K% = 0.75 × Whiff% +
  0.6 × gap); talent sd 1.65 K% points against noise sd 2.3 at 300 BF, so one 300-BF season is a third talent; Foul% is the piece that explains
  it best (r .47) and persists best, called strikes and Strike% next, two-strike whiffs no better forward than anything. Career gaps: Pivetta
  +4.1, Sale +4.0, Joe Ryan +3.8, Cole +3.8, Wheeler +3.6 every year; Tyler Anderson −4.2, Montgomery −3.4, Corbin / Gibson −2.5. For finding
  breakouts, a whiff-based gap beats xK% − K% (r with next year's K% change .30 vs .20; 39-46% of the 4+ point jumpers flagged vs 23%).
  Cavalli 2025: Whiff% 27.9, xK% 19.9, gap −8.
* **Raw / Stuff as one dropdown, the two-way switch in Filters, minors Walk Avoidance (Sean, 5 Oct 2026: "put the hitting and pitching button
  in the filters box so that you can eliminate that weird empty space gap ... make it one singular button ... the same style as like the mlb/aaa/AA
  button thing is and also how the year is ... add the walk avoidance percentile bars for the minor leagues too")**: Raw / Stuff was a
  `titleSelect` ("Raw ▾", the season picker's dress) for an hour, then **a button in the Filters button's own dress, right beside it**
  (Sean: "make it look exactly like the filters button"): `.segbtn.small.phfilt.phsidebtn` in a `.seg.phfiltseg.phsideseg`, appended to
  `.phtog` after Filters, the pick list hung under it by `ddList` — to the right of Filters on both layouts — `sideSwitch()` is unused; the
  vertical two-button switch had made the phone's bio row twice as tall and left a blank over the bio. A two-way player's Hitting / Pitching
  `.seg` is taken off the plate in `playerHead` and put at the top of the Filters window (`.phtwo`, captioned). **Minors**: Triple-A already
  showed Walk Avoidance in full; Double-A and below read no 1st-pitch / 3-ball strike rates (so no xBB%) because `load_feed`'s per-game cache
  (`.cache/milb/feeds/<pk>.csv.gz`) was written before the count was kept (3 Oct 2026) and was reused as long as it had a zone — it now refetches
  a game whose file has no `balls` column. A rescore of `aa-2026 ap-2026 a-2026` was dispatched after the merge (every game of those levels is
  fetched again, so it takes a while); older feed-level seasons pick it up when rescored.
* **2-strike Whiff% back in xK%, and the gap is Whiff% − xK% (Sean, 5 Oct 2026: "do the formula that uses two strike whiff for xk%. And make
  the formula actually whiff% - xK% instead of the other way around")**: `XKM` is the morning's fit again (the five tiers with `s2whf`, held-out
  same-season rmse 0.63), the xK% tab's pairs and the Pitching+ breakdown show 2-strike Whiff% / x2-strike Whiff% again, and `xkw` = **Whiff%
  − xK%** (`xkws` = xWhiff% − Pitching+ xK%), labels, glossary and `SHORT` flipped with it; both are in `LB_EXTRA_P` (the Stats panel offered them but `lbOrder` draws only the extras it names, so the ticked column never showed — Sean, 5 Oct 2026) — high on a high Whiff% is the breakout shape
  (Cavalli 2025: +9.7; his 2026 card reads −0.1 on the Raw side, +3.7 on the Stuff side). The refit without it (`xkrefit.js`) is history; the
  glossary says xK% is the same-season read and Whiff% − xK% the forward one.

* **No xK% on the card; Whiff% with a fold-out, and Control (Sean, 5 Oct 2026: "no xK% at all. Let's just use whiff rate ... show K%, then whiff
  rate. Then below Whiff rate have a drop down with overall whiff rate, 2 strike whiff rate, foul%, and called strike percentage ... in skills
  show whiff rate and ... an average of their strike percentile and their 3 ball strike percentile ... walk avoidance ... bb%, strike%, and 3 ball
  strike %")**: `PCT_COLS_P` = Skills (Whiff% · **Control**) · Swing & Miss (K% · Whiff% ▸ 2-strike Whiff%, Foul%, Called Strike%) · Batted Ball |
  Walk Avoidance (BB% · Strike% · 3-ball Strike%) · Rating; `PCT_COLS_PS` the same on the Pitching+ expected rates (xWhiff% ▸ x2-strike Whiff%,
  xFoul%, xCalled Strike%). **Control** (`ctrl`, `CTRL_M`) = the mean of his Strike% and 3-ball Strike% percentiles, a 0-100 number whose
  bubble is itself like the Rating's — on the pool's stats (`ctrlOf` in `pool()`) and `placeIn`'s return; a card row only, not a column.
  **Fold-outs in the Savant bars**: a `PCT_COLS_*` entry may be `{ k, sub: [...] }` — `rowsOf` in `pctColumns` draws the parent with ▸ / ▾
  before its name (`r.fold`, `state.open["card:<k>"]`) and, open, its sub rows after it (`r.sub`, `.svsub` lighter); in `pctSvg` tapping the
  name toggles, the bar still opens the note; `specKeys` flattens a spec for Compare and the column picker. xK% / Whiff% − xK% stay columns and
  (PR #334). **Then** (Sean, minutes later: "no need to show called strikes actually. And we can get rid of the xk% and xbb% tabs"): the fold-out is
  2-strike Whiff% · Foul% (xFoul% on the Stuff side) and `BTABS_P` is Pitching+ · nERA — `renderPctTab`, `XK_COLS_P` / `XBB_COLS_P` and the
  `pick === "xk" / "xbb"` branches stay in `app.js`, unreachable; a saved `pbtab` of xk / xbb falls back to Stats.
* **The helmet ground and the Raya dress — built and taken back the same day (5 Oct 2026)**: the Ohio State helmet ground (a silver page
  ground with buckeye-leaf stickers drawn by a `buildHelmet()`, then the real white round stickers, then no stickers; Appearance ▸ Background)
  and the Raya dress from the Raya Dress Mock page (no frames or fills, weight-300 type, tracked uppercase labels, one accent, the sorted
  column coloured as ink — PRs #337-#341) are **gone**: Sean, after an iPhone recording of the Leaderboard dragging, "go back to the previous
  layout and theme and format". `styles.css`, `themes.js` and the look of `app.js` are the fold-out state of PR #336 again (the no-bold 400
  rule, the navy table headers, the frames, the pale ground). Two things found along the way stay fixed: never `position: relative` body's
  children wholesale (the helmet block did, which unpinned the sticky header and dropped every fixed dropdown into the page flow), and a
  sticky name cell inherits the row's background, so a selected row's must be opaque. Don't bring the stickers, the swirl or the dress back
  unasked.
  **The real slowness was JavaScript** (Sean's iPhone recording: the pitchers' Leaderboard drew, froze ~2.5 s and drew again) — kept:
  `ensureScript`'s onload emptied the value and pool caches for *every* lazy file, so the search index arriving a few seconds after the
  Leaderboard threw the pool away and recomputed it (~1.2 s on a desktop, 3-4 s on a phone). It now keeps the caches for files that carry
  no values (`hist/index.js`, `career`, `similar`, `minors`, `trends`, `adp-` / `proj-`, `fantasy-lines`); day rows, seasons, levels,
  arsenal and fantasy files still clear them. `fitNameCol` measured every row's team line with a computed style + `offsetWidth` (a forced
  layout per row) — it measures off the canvas now, and `textWidth` sets the canvas font only when it changes; `xKModel` merges the league
  rates once per view (`xKLeague`) instead of per pitcher. Profile (scratch `prof.js`, CDP sampling): the Leaderboard render 1.74 s → 1.20 s
  on a desktop, once instead of twice; what's left is `pool()` itself (~0.7 s: `placeIn` for every listed pitcher under the reference
  minimum, the PK block's fits — the xK% / expected-rate work of 4 Oct), the next thing to cut if a phone still drags.
  **And the day file** (Sean, the same hour: "it is still dragging, why is that happening now if it didn't happen this morning"): `days.js`
  is 24 MB since the 4 Oct rescore (the location / swing foul sums and command sums on every day row; 14 MB before), Home's Trending card
  runs it on every fresh load, parsing it blocks a phone's main thread for seconds, and its arrival emptied every value and pool cache — so a
  list opened in that window drew, froze while the file parsed and the pool recomputed, and drew again. Every publish today also reloaded his
  phone through `build.json`, so he hit that cold path over and over where the morning's page had been warm. Now: `ensureDays`' onload drops
  only the **provisional** caches — values, pools and ranks computed under a window / split / combined span (`provisional.val / pool / rank`,
  marked in `V()`, `pool()` and the rank cache; the pool and rank keys carry `daysReady()` only when `needsRows()`), a full-season value or
  pool being the same with or without the day rows — and Home asks for the file 1.2 s after it paints, on idle, and only while still on Home.
  Trimming `days.js` itself (the inert command sums `stcn…stcw` are a third of each pitcher row) is the next lever.

* **Reset to yesterday 11am (Sean, 5 Oct 2026: first "factory reset everything to how it was at 7:10am this morning" — done for ten
  minutes as main at b435851 — then "scratch that, can you bring it back to yesterday at 11am")**: `app.js`, `styles.css`, `themes.js`
  and `defaults.js` are byte-for-byte main at 20be21a (the 4 Oct 10:34 data build; the last front-end merge before 11am EDT was PR #291 at
  7:16): the card of that morning — Swing & Miss / Zone & Chase / Batted Ball / Stuff, tabs Season Stats · Pitching+ · nERA · Fantasy ·
  Compare, the band's SV — and the **Rating is Whiff% 55 / Strike% 30 / Mix wOBA 15 again**: `data.js`'s `pitcherWeights` / `scoreNote.P`
  patched back (the old app.js can't rank `xkbb`, so the x(K-BB)% 80 / Mix wOBA 20 weights would have broken the score) and
  `PITCHER_SCORE_WEIGHTS` in `tools/build_data.py` set to match so the morning build keeps it. Everything else of 4-5 Oct in this file after
  PR #291 (xK% on the card, x(K-BB)%, Stuff xK%, the Raw / Stuff switch, the Filters window, fold-outs, Control, the xK% / xBB% tabs, the
  helmet, the dress, the speed fixes) is **history on the site** — still in git, and the build-side additions (foul models, day fields,
  the extra card-group defs in `PITCHER_CARD`) stay since the old app.js ignores fields it doesn't name. Re-apply any of it only when asked.

* **The lag, found and fixed on the 11am-yesterday front end (Sean, 5 Oct 2026: "It's still super laggy can you fix that, what caused that?")**:
  with the front end put back to Saturday 11am and still dragging, the cause had to be in the data and the page's own habits, and a
  4×-throttled headless profile (scratch `tl.js` / `prof12.js` / `profhome.js`) showed exactly where: (1) `ensureScript` emptied every value /
  pool / rank cache when **any** lazy file landed, so the search index arriving ~3 s after the pitchers' Leaderboard made the page recompute
  the whole pool and redraw — a 3.3 s freeze on a phone right after the 4 s first draw; (2) **Home parses `days.js`** (24 MB since the
  2-4 Oct rescores: 18 → 24 MB from the location / swing-foul / command sums — every float is already 2 dp, so the size is the field
  count, not precision) on every cold load for its Trending card, and the **Last game day** card then ran a full game log for every one of
  ~1,300 players to find one day — 5.4 s blocked; (3) in `pool()`, `impliedKBB` / `nextKBB` copied the whole metric object (`Object.assign`)
  for every rate fit, four times per pitcher, which was most of the pool's time; (4) `fitNameCol` forced a layout per row. And every publish
  reloads his phone through `build.json`, so each of the day's ~15 publishes put him on that cold path — the "it didn't lag this morning"
  was a warm page. Fixed in `app.js` (same patches as PRs #342 / #345, re-applied to this version, plus the home card): `ensureScript`
  keeps the caches for value-free files (`index`, `career`, `similar`, `minors`, `trends`, `adp-` / `proj-`, `fantasy-lines`);
  `days.js` arriving drops only the **provisional** caches (values / pools / ranks computed under a window or split before it was in —
  `provisional.val / pool / rank`, the pool and rank keys carry `daysReady()` only under `needsRows()`); Home asks for the file 1.2 s after
  it paints, on idle, only while still on Home; `gameLog(p, onlyDay)` / `hitGameLog(p, onlyDay)` and the last-game-day card first checks
  who has a row that day; `rateFit(m, lg, fits, L, role, ex)` reads the arsenal inputs beside `m` instead of copying it (`impliedKBB`,
  `nextKBB`, `uBBFrom` pass `ex`); `fitNameCol` measures the team line on the canvas and `textWidth` sets the font once. Headless at 4×
  CPU: Leaderboard first draw 4.1 → 3.6 s, the second freeze 3.3 → 0.3 s, Home's day-file freeze 5.4 → 1.7 s; desktop Leaderboard render
  1.44 → 0.84 s (pool 0.94 → 0.34 s). Every one of the 539 listed pitchers' rows (Rating, xRating, nERA, uK%, uBB%, xWhiff%, Mix …) is
  byte-identical before and after. What's left is the first draw itself (700 rows built and laid out, ~0.8 s desktop) and the 24 MB parse
  (~1 s on a phone, once per publish) — the next levers are drawing the rows in chunks and trimming the inert command sums (`stcn…stcw`,
  1.5 MB) and the rest of the day fields the site doesn't read.

* **A phone's Leaderboard pages again, and the pool places on demand (Sean, 5 Oct 2026: "So on mobile maybe we add back in the pages
  aspect?")**: `phonePages()` = `onePage()` on a phone — `pageWindow` pages at `state.pageSize || 25` there (a desktop still lists everyone),
  the page numbers sit on a line of their own under the filter row (`.pnavrow`, inserted after `#pagertop` by `renderPager`, removed on each
  redraw; CSS at the end of `styles.css`), the count reads "1–25 of 193", and Filters ▸ Order carries Per page on a phone. The six buttons,
  the Standard pill and the Min box are unchanged. **Lazy placement**: `pool()` used to run `placeIn` for every listed-under-reference player
  and the whole tail up front (~650 pitchers, a third of the pool's time); `res.stats.get` now places one the first time anyone asks and keeps
  it — nothing iterates the map (checked), `rankIn` already fell back to `placeIn`. Headless at 4× CPU, phone view, pitchers' Leaderboard
  first draw 3.4 → 1.3 s; desktop render 0.84 → ~0.6 s; all 539 rows byte-identical again.

* **The morning's pitcher card is back on the fast front end (Sean, 5 Oct 2026: "With the page currently can you make the player card back to
  how it was for pitchers most recently with the available stats and whatnot now")**: `app.js` is PR #345's (the PR #336 card — Skills:
  Whiff% · Control, Swing & Miss: K% · Whiff% ▸ 2-strike Whiff% / Foul%, Batted Ball, Walk Avoidance: BB% · Strike% · 3-ball Strike%, Rating:
  Rating · x(K-BB)% · Mix wOBA, the Raw ▾ / Stuff dropdown, the Filters window, tabs Pitching+ · nERA, K-BB% on the band — plus that PR's
  cache guard, provisional caches, Home deferral, canvas `fitNameCol` and `xKLeague`) with the rest of today's work re-applied on top:
  copy-free `rateFit(…, ex)`, `gameLog` / `hitGameLog(p, onlyDay)`, `phonePages()` and the `.pnavrow`, lazy `stats.get` placement.
  `styles.css` is PR #336's (the card's fold-out / window / switch rules) plus the phone pager block. The **Rating is x(K-BB)% 80 / Mix wOBA
  20 again** (this app.js ranks `xkbb` before the score): `data.js`'s `pitcherWeights` / `scoreNote.P` and `PITCHER_SCORE_WEIGHTS` in
  `tools/build_data.py` put back. The two "reset" entries above are history as of this one; the lag entries still describe the live code.
  Headless phone view at 4× CPU: pitchers' Leaderboard first draw ~2.0 s (the xK% fits in the PK block are heavier than yesterday-11am's
  pool), 25 rows a page, no script errors; Skenes's card draws every section with bubbles and the Raw ▾ switch.

* **Raya type, lines and spacing (Sean, 5 Oct 2026: "make it so the site has the raya font size and font and their line widths and their
  spacing as well")**: the Raya Dress Mock's typography on the site as it stands, not the dress — the block at the end of `styles.css`
  ("Raya type, lines and spacing"): every element at weight 300 (`themes.js` loads Barlow Condensed 300 and Source Sans 3 300 now) with the
  numbers (`.pct .score .hchip b .hval td .svval …`) at 400 so they read; names and headings 300 with 0.01em tracking; the small labels — nav
  words, column names, section names, buttons, tabs, pills, the band's bio labels, the Min / Standard pills — Source Sans 3 11px, tracked
  0.14em, uppercase (the one place the no-capitals rule is reversed); the bars' section names 11px tracked 0.16em; a list row's name 16px in
  the condensed face over an 11px tracked team line; the band's fact values 18px over 10px tracked labels. **Lines**: one hairline
  (`--raya-hair`, ink at 12%) between rows, under the column names, under the card tabs' headings and the phone band's row. **Spacing**: nav
  gap 22px and 6px / 2px padding, column names 10px above and below, card tabs 14px apart, buttons 8px side padding and 30px tall, the
  Leaderboard's filter row 10px / 12px. Kept as they were: the frames, the navy table headers (their words now tracked), the sorted column's
  fill, the light-blue accent, the pale ground. The dress's own colours / frame removal / `hotInk` stay out — don't bring them back unasked.

## 9. Things only Sean can do

Nothing in this repo runs. Ask him to run these on the Mac, and to publish afterwards:

```
python3 build_data.py --end YYYY-MM-DD    # rebuild today's numbers
python3 build_history.py 2024 2023        # rebuild past seasons
python3 build_history.py index            # search index (run build_career.py after)
python3 sync_tools.py --dry               # show what this repo would change on the Mac
python3 publish_github.py                 # publish
tail -f logs/daily.log                    # watch the 5:30 job
```

If a script edited here does not seem to have taken effect, have him check the top of `logs/daily.log` for the
`sync_tools:` lines — "updated …" means it was adopted, "keeping the local one" means the Mac's copy had also
changed and the repo's copy is sitting in `logs/tools-conflicts/`.

* **The Raya dress is back, as a test (Sean, 5 Oct 2026: "can you go back to the raya theme as a test for now and ill see how i like
  that since itll not be slow now")**: `styles.css` is PR #341's (241c65d — the PR #336 card rules, the `:root.helmet` silver ground
  `#d4d7dc` / `#1b1e23` dark with the stickers disabled, and the full "The Raya dress" block: weight 300 with the numbers at 400, tracked
  uppercase labels, hairlines for frames, buttons as words, one accent `--raya`, the header on paper) plus the phone pager's `.pnavrow`
  rules (page numbers as plain words, the current one in `--raya`); `app.js` carries the dress patch again (`hotInk` paints the sorted
  column's digits in the percentile colour instead of filling the cell, `buildHelmet()` sets `helmet` + `nopattern` on `<html>` in place
  of `buildSwirl`) on top of the fast front end with the morning's pitcher card. This supersedes the "Raya type, lines and spacing" entry
  (PR #352) and the "built and taken back" note's don't-bring-back line for the dress — Sean asked for it. The old look is one revert away:
  `styles.css` / `app.js` from PR #352's merge (or PR #351's for the look without the Raya type). The slowness that made him drop it on
  the 5th was the JavaScript, not the dress (the lag entries above).

* **Back to the prior format (Sean, 5 Oct 2026, minutes after the dress went live: "go back to the prior format with the prior font and
  spacing and line width")**: `app.js`, `styles.css`, `themes.js` and `defaults.js` are PR #351's merge (7649174) byte for byte — the fast
  front end with the morning's pitcher card and the phone pager, weight-400 Barlow Condensed / Source Sans 3, the frames, the navy table
  headers, the pale ground, no Raya type block and no dress. The two entries above (Raya type, PR #352; the dress test, PR #353) are
  history. Don't bring the dress or the Raya type back unasked.

* **K% / BB% drivers tab (Sean, 5 Oct 2026: "a tab for each pitcher that has this table that shows share of what is the variance and what is
  explained and then gives the players metric for that stat with a heatmap based on how it impacts the k%/bb%")**: `BTABS_P` is Pitching+ ·
  **K% / BB%** · nERA (`renderDriversTab`, `DRIVERS` in `app.js`; CSS `.drivers` at the end of `styles.css`). Two tables from scratch
  `kbb_lmg.js` — every 100+ BF pitcher-season 2020-26 (3,397), each stat centred on its season's BF-weighted league, BF-weighted OLS, each
  stat's share of R² by the LMG / Shapley decomposition (the R² gain averaged over every order of entry, so Whiff% and 2-strike Whiff% split
  their common ground fairly): **K%** (R² .962, rmse 1.03) Whiff% 40.1 · 2-strike Whiff% 36.2 · Foul% 7.3 · Chase% 4.8 · Called Strike% 4.3 ·
  2-strike Zone% 1.3 · Zone% 1.1 · 2-strike Swing% 1.0; **BB%** (R² .849, rmse 0.99) 3-ball Strike% 29.6 · Strike% 20.5 · Swing% 8.6 · 1st-pitch
  Strike% 8.2 · Zone% 7.1 · Chase% 5.8 · Whiff% 2.8 · Z-Contact% 2.3. Columns: share of variance, share of what's explained (share / R²),
  His (the view's `V(p).m`), League (`lgRatesP()`), Effect = weight × (his − league) in K% / BB% points (two decimals for BB%), the His and
  Effect cells painted by his percentile on that stat among the pool's reference list (`pl.ref`, oriented by the weight's sign × the target's
  good direction, so red = pushes K% up / BB% down); a "The fit" row (R², his actual, the league, the league + every effect = what the fit says)
  and a head line "K% 28.1 · the fit says 26.6 (+1.5)". Same-season fits, so the two-strike / three-ball rates sit close to the outcome; the
  note says Whiff% and Strike% are what carry forward. A file without a stat shows "–" and no effect for that row.
* **Walk Avoidance under Swing & Miss (Sean, 5 Oct 2026: "put walk avoidance below swing and miss and in front of batted ball")**: `PCT_COLS_P` /
  `PCT_COLS_PS` left = Skills · Swing & Miss · Walk Avoidance, right = Batted Ball · Rating (a phone stacks them in that order).
* **The K% / BB% tab's Stuff side (Sean, 5 Oct 2026: "when it switches between raw and stuff could you make the stuff be based on his pitching+
  expectations")**: under Raw ▾ / Stuff (`stuffSide()`), `renderDriversTab` swaps the whiff-side inputs for the Pitching+ models' expected rates
  (`XK`: whf → `nwhf`, s2whf → `ns2whf`, foul → `nfoul` from the pool's stats, cstr → `ncstr` on `m`), labelled xWhiff% / x2-strike Whiff% /
  xFoul% / xCalled Strike%; Strike%, the count-state rates, Zone%, Chase%, Swing% and Z-Contact% stay his own. Each expected rate is set
  against the pool's **own expected league** (BF-weighted over `pl.ref`), not the actual one, since the fixed models read a season they never saw
  a point or two off; the percentile colour ranks him on the expected rate among the pool. The head says "— on the Pitching+ expected rates"
  and a note explains. Skenes 2026: Raw fit 26.6, Stuff fit 23.5 against K% 28.1.
* **The K% / BB% tab on the fits' full inputs (Sean, 5 Oct 2026: "is this not the same as the xk% we had yesterday", "can it include all of the
  same inputs")**: the rows are now **xK%'s own 23 inputs** (`XKM`: Whiff%, CSW%, SwStr%, 2-strike Whiff%, Foul%, Strike%, Swing%, Z-Contact%,
  Zone%, Chase%, 1st-pitch / 3-ball Strike%, 2-strike Swing% / Zone%, GB%, PU%, FB velo, extension, Pitching+, Location+, Stuff+, both expected
  whiff rates) and **uBB%'s 24** (`UBB`, by his role — the raw inputs xwl / fastball share / pitch types / age shown against the pool's mean, a
  Constant row carrying the fit's constant plus what those means are worth) at the site's own weights, so the last cell of each table **is** the
  card's xK% (Stuff side: Pitching+ xK%, via `xkParts`' expected whiffs / CSW% / SwStr% / 2-strike whiffs / fouls, labelled x…) and uBB%
  (`st.xkf / xks / ubb`); `pickFit` chooses the tier `rateFit` would, so an older file gets the tier it carries. The shares are by sampled
  Shapley (3,000 orders, scratch `kbb_full.js`, every 100+ BF pitcher-season 2020-26 with an arsenal, centred per season, BF-weighted): K% R² .976
  — 2-strike Whiff% 13.2 · CSW% 13.1 · Whiff% 10.4 · SwStr% 9.6 · Z-Contact% 7.4 · Foul% 7.2 · xWhiff% 6.6 · Pitching+ 6.0 · Stuff+ 5.9 ·
  stuff xWhiff% 5.7 · velo 2.6 · the rest under 2; BB% R² .875 — 3-ball Strike% 25.7 · Strike% 16.1 · Swing% 8.9 · 1st-pitch 6.3 · Zone% 5.7 ·
  Chase% 5.1 · the rest under 3. Near-duplicates (CSW% / SwStr% / Whiff%) share the credit, which is what the LMG split is for. `DRIVERS` /
  `DRV_LABEL` / `DRV_XLAB`; the BB% table is the same on both sides (uBB% has no expected side). The eight-input fits of the first version are
  history. Skenes 2026: K% 28.1 · xK% 27.2 / Pitching+ xK% 27.5; BB% 6.9 · uBB% 7.0.
* **Strikeout composite, Rating and xRating on it (Sean, 5 Oct 2026: "under skills have instead whiff do an average percentile of whiff two strike
  whiff and foul balls and then make rating be about that and then xrating be the same thing just with the stuff models driving whiffs and fouls")**:
  **Strikeout** (`kskl`, `KSKL_M`) = his Whiff%, 2-strike Whiff% and Foul% percentiles averaged, a 0-100 number whose bubble is itself like Control —
  built in `pool()` as `pct.kskl` (with `pct.ctrl`) before the score, on each stats entry (`s.kskl`, `s.pct.kskl / ctrl`) and in `placeIn`;
  **xStrikeout** (`ksklx`, `KSKLX_M`) = the same on the Pitching+ expected rates (`nwhf / ns2whf / nfoul` percentiles), set after the PK block.
  **Rating = Strikeout 60 / Control 20 / Mix wOBA 20** (`PITCHER_SCORE_WEIGHTS` / `meta.pitcherWeights` / `scoreNote.P`, `data.js` patched by hand) —
  the 60 / 20 / 20 keeps the old 80 / 20 skills-vs-mix split with the K side and the walk side at roughly x(K-BB)%'s own 75 / 25 (not backtested
  against points; `kbbrate.py` can be re-run on it). **xRating = xStrikeout 60 / Control 20 / Mix xwOBA 20** (`XRW`; `renderAsStarter`'s starter
  xRating places the translated xWhiff%, the scaled x2-strike Whiff%, his xFoul%, the translated Strike% / 3-ball Strike% and the mix in the SP pool).
  Card: Skills = Strikeout · Control (Stuff side xStrikeout · Control); the Rating section is Rating · Mix wOBA (xRating · Mix xwOBA) — x(K-BB)% /
  Pitching+ x(K-BB)% are no longer Rating inputs and left the section (still columns, still computed). The Rating · xRating line, glossary (`rating`,
  `xrat`, `kskl`, `ksklx`) updated. Next-season test behind the choice (scratch `nextk.js`, pairs 2020→26, 100+ BF both years, held out by year):
  Whiff% + Foul% + Called Strike% forecasts next K% as well as K% itself (r .681 vs .683); 2-strike Whiff% adds nothing forward (.643 → .644) but
  Sean chose it for the skill read; Strike% + 3-ball Strike% .516 vs BB% alone .545. Skenes 2026: Strikeout 84 · Control 74 · Rating 82 · xRating 70.
* **Results, not Rating; no K% / BB% in the skill sections (Sean, 5 Oct 2026: "have the rating section become results and just have k%, bb%, and
  k-bb%. And then in swing and miss get rid of k% and in walk avoidance add in first pitch strike %. Also eliminate bb% from walk avoidance")**:
  `PCT_COLS_P` / `PCT_COLS_PS` left = Skills (Strikeout / xStrikeout · Control) · Swing & Miss (Whiff% / xWhiff% ▸ 2-strike Whiff%, Foul%) · Walk
  Avoidance (Strike% · 1st-pitch Strike% · 3-ball Strike%); right = Batted Ball · **Results** (K% · BB% · K-BB%, his actual outcomes on both sides).
  The Rating and xRating left the card's bars (the Pitching+ tab's Rating · xRating line and the Leaderboard columns still carry them).
* **The Raya type and the mock's bars (Sean, 5 Oct 2026, from a phone screenshot of the Raya Dress Mock: "give the site this exact font, this font
  size, the raya spacing as well ... make the percentile bars and sections on the player page and card look precisely like this, even give the
  percentile bubble this exact look")**: PR #352's "Raya type, lines and spacing" block is back at the end of `styles.css` (weight 300 with the
  numbers at 400, the small labels 11px tracked uppercase, hairlines, Raya's gaps; `themes.js` loads the 300 weights again) — the dress itself
  (frames off, silver ground, `hotInk`) stays out. **`pctSvg` is the mock's `.sec` / `.bar` / `.trk` / `.bub`** (artifact "Raya Dress Mock"): a section
  is 14px over an 11px tracked-uppercase grey name, 10px, 30px rows, 8px under; a row is a 112px left-aligned label (100 on a phone, `W < 700`),
  a 44px (40) right-aligned value at weight 400, 10px gaps, a 20px flat track (`--raya-pctrack` #eceef2 / #2e333b dark) to 14px short of the
  right edge, the fill to his percentile, a 22px bubble centred on it (circle r 10 + 2px `--surface` ring, white Roboto Condensed 700 10.5px
  digits); no 10 / 50 / 90 ticks, no dashed rules; Poor / Average / Great a 10px tracked grey line on the track's span above the first section
  (`scale`). The SVG carries class `raya`; the "The Raya mock's bars" CSS block at the end of `styles.css` holds its type and colours (the
  site-wide no-capitals rule needs `!important` on the tracking / uppercase). The sample line, fold-outs (▸ / ▾ on the name) and the tap note are
  unchanged. Savant's drawing before this is PR #360's `pctSvg`. The "don't restyle the bars unasked" rule stands; this was asked.
* **Swing & Miss flat (Sean, 6 Oct 2026: "make it so swing and miss shows all three without a drop down")**: Whiff% · 2-strike Whiff% · Foul% as
  three plain rows (xWhiff% · x2-strike Whiff% · xFoul% on the Stuff side); the fold-out machinery stays in `pctColumns` / `pctSvg`, unused.
* **Stuff+ back, Pitching+ and the xRating off the site (Sean, 6 Oct 2026: "get rid of pitching+ entirely and just go back to stuff+ and let's not
  even do an xrating or a stuff filter on the player card at all, lets just have a stuff+ tab that shows expected whiff rates and gb% and pop up%
  for the pitchers stuff")**: the header link, the board (`#pitches`: Stuff+ / Whiff+ / BB+ / xWhiff% / xGB% / xPU%, `pb.sort` falls back to
  `stuffp`), the Leaderboard's column set (**Stuff+**: Stuff+ · Whiff+ · Batted-ball+ · velo · extension; `LB_SETS`), the Stats panel group, home's
  "Stuff+ that start" (`gameLog`'s `st` is the stuff-only grade again) and Similar's skill list (`stuff`) are the stuff-only family. **No xRating
  column** (out of every column set and `LB_EXTRA_P`; `xrat`, the Pitching+ family `pitch / pwhf / pbb / sloc`, `xks / xkbbs / xkws` and the
  expected (Pitching+) columns `nwhf ngb npu nmix wgap nswstr ncsw ns2whf nfoul ncstr` are in `RETIRED_P` and dropped from saved lists on load;
  the `xratFront` migration is gone). **The card**: `BTABS_P` = Stuff+ · K% / BB% · nERA, the Raw / Stuff dropdown is gone (`stuffSide()` is
  false; `PCT_COLS_PS` stays for the record), and the **Stuff+ tab** is `renderStuffTab(p, st, g)` in stuff mode — the arsenal table (Stuff+ /
  Whiff+ / BB+ against type, xWhiff / xGB / xPU over actual, All pitches) and nothing under it (`EXTRAS = false` turns off Arsenal Opt. and
  Stuff uERA; the whiff check, Rating · xRating line and xK% breakdown were Pitching+'s). Still computed underneath: Pitching+, xRating, the
  expected rates (the K% / BB% tab's K% rows still list Pitching+ / Location+ / the expected whiff rates, since they are xK%'s inputs).
* **The card's bars tidied, the sections reshaped, Rating = nERA (Sean, 6 Oct 2026, from Gavin Williams's card: "the percentile bar goes a
  little bit too far to the right ... make the percentile in the bubble centered ... the actual metric centered on the bar and ... the metric name
  centered ... all the font color ... black ... skills section instead just k-bb% and then mix wOBA and make the rating just be their nERA ...
  get rid of the results section and put k% back at the top of swing and miss and bb% at the top of walk avoidance ... call walk avoidance
  command ... after k% and bb% ... a line break")**: `pctSvg` ends the track 30px short of the right edge (`RM`, was the mock's 14, so a 100
  bubble sits inside the card), puts the label / value at the row's centre (`y: cy` — `.svpct text` is `dominant-baseline: middle`, the mock's
  baseline offset had sat them 5px low) and the bubble's digits at `y: 0.5`; a spec entry **`"|"`** is a line break — `rowsOf` makes a
  `{ gap: true }` row, `pctSvg` leaves 12px (`BRK`), `specKeys` and the classic meters skip it, a group drops leading / trailing breaks. Type on the
  bars is black (`--raya-pctink` #000, #f2f3f5 dark; the block at the end of `styles.css`). `PCT_COLS_P` = Skills (K-BB% · Mix wOBA) · Swing & Miss
  (K% | Whiff% · 2-strike Whiff% · Foul%) | **Command** (BB% | Strike% · 1st-pitch · 3-ball) · Batted Ball; no Results. **Rating = the nERA
  percentile** (`PITCHER_SCORE_WEIGHTS` / `meta.pitcherWeights` `{nera: 100}`, `data.js` patched, `scoreNote.P`, glossary); Strikeout / Control /
  xStrikeout stay computed (`kskl / ctrl / ksklx` on the pool's stats) but are off the card.
* **The Raya type off again, the mock's bars kept (Sean, 6 Oct 2026: "keep the percentile bars how they are currently but go back to the old
  spacing and font and everything format wise before I had you go back to the raya one just now")**: the "Raya type, lines and spacing" block is
  out of `styles.css` once more (PR #351's weight-400 type, buttons, nav, column names and hairlines); the two bar blocks at the end ("The Raya
  mock's bars", the black type) stay, and `themes.js` keeps loading the 300 weights so the bars' light labels and section names draw the same.
* **Back to PR #359 with the new bars (Sean, 6 Oct 2026: "I meant this version [PR #359] but with the current bars look and that's the only
  thing to keep from current")**: `app.js`, `styles.css`, `data.js` and `tools/build_data.py` are PR #359's merge (778258a — Skills = Strikeout ·
  Control, Swing & Miss K% · Whiff% ▸ 2-strike / Foul%, Walk Avoidance BB% · Strike% · 3-ball, Batted Ball, Rating = Rating · Mix wOBA; the
  Rating Strikeout 60 / Control 20 / Mix wOBA 20 and the xRating on the stuff models; the Raw / Stuff dropdown; tabs Pitching+ · K% / BB% · nERA;
  the Pitching+ header link, board and column sets; the pre-Raya type and format) with **`pctSvg` and the two bar CSS blocks from PRs #361 /
  #364** on top (the mock's geometry, the track ending 30px short, centred text, black type, "|" breaks supported but unused) and `themes.js`
  keeping the 300 weights loaded. Everything of PRs #360-#365 beyond the bars (Results, Command, K-BB% Skills, Rating = nERA, Stuff+ in place of
  Pitching+, the flat Swing & Miss, the Raya type) is history. The entries above for those PRs describe code that is no longer live.
* **PR #366 undone (Sean, 6 Oct 2026, minutes later: "No sorry the formatting of that not the site")**: he meant PR #359's *format* (the pre-Raya
  type) with the current site, which is what PR #365 already was — `app.js`, `styles.css`, `themes.js`, `data.js` and `tools/build_data.py` are PR
  #365's merge (7011960) again: Skills = K-BB% · Mix wOBA, Swing & Miss K% | Whiff% · 2-strike Whiff% · Foul%, Command BB% | Strike% · 1st-pitch ·
  3-ball, Batted Ball, Rating = nERA, Stuff+ in place of Pitching+, no xRating or Raw / Stuff switch, the mock's bars, the pre-Raya format. The
  entry above (PR #366) is history.
* **No Raya anywhere (Sean, 6 Oct 2026: "I don't want any of the raya stuff back here anymore")**: the card's bars keep only the geometry he liked
  (the flat 20px track ending 30px short, the fill to his percentile, the 22px bubble with its ring and Roboto Condensed digits, label / value / bubble
  centred on the row, the line breaks); their type is the site's own again — section names in the title face (`--display`, 19px, `y: 28`, 14 over /
  10 under), labels and values in `--body` at 400, no tracking, no capitals, black — the "the card's bars" block at the end of `styles.css`;
  `themes.js` loads the 400+ weights only. Nothing Raya is left in the stylesheet or the font list. Don't bring any of it back unasked.
* **Savant's bars back, the content kept, nERA as the pitchers' headline (Sean, 6 Oct 2026: "make it formatting wise what it was at 6pm today.
  And then keep the content what it is now, and also make the nERA show their actual nERA not their percentile and also make it default to sort by
  the lowest nERA")**: 6pm New York was the site between PR #354 (18:38) and #355 — the pre-Raya format with Savant's bars — so `pctSvg` is PR
  #359's Savant drawing again (ticks, dashed rules, Poor / Average / Great, the section names in the title type), with the "|" line breaks kept
  as 12px of air (`r.gap`), and the bar CSS blocks are gone from `styles.css`; the sections stay as PR #364 left them (Skills K-BB% · Mix wOBA,
  Swing & Miss K% | …, Command BB% | …, Batted Ball). **The pitchers' headline column is his nERA itself** (`nv.toFixed(2)`, coloured by its
  percentile, the column / Sort by option "nERA"; `val()` sorts the `score` key by the value, lowest first on the default "desc" — the percentile
  had tied every under-minimum pitcher at 100), and `nera` left the Standard / Advanced column sets (`state.lb.neraHead` drops it from a saved
  list once). The Rating (score) is still the nERA percentile underneath.
* **Expected fouls on the Stuff+ tab and board (Sean, 6 Oct 2026: "add expected fouls to stuff+")**: an **xFoul** pair after xPU — the foul
  model's share of contact that goes foul for each pitch (`xFoulOf`: the swing-aware `xfoulw`, else the location `xfoull`, else the stuff-only
  `xfoul`) over his actual fouls per contact; All pitches weights the chances by each pitch's contacted swings (`sw × (1 − whf)`). The build now
  counts the fouls that happened on the contacted pitches — `fo` in the per-pitcher × type sums, **`foul`** appended to `STUFF_ARSENAL` (fouls per
  contact, null under 5 contacted) and **`fo`** appended to `ARS_DAY`, so `arsenalView` carries `xfoul / xfoull / xfoulw / foul` in a window or
  split. Until a build carries them, the per-pitch actual reads "–" and the All pitches actual falls back to his season's Foul% ÷ (Swing% × contact
  share) from the card's own rates (Jax 2026: 51.3% expected / 47.3% actual; four-seam 67.0% expected, sinker 49, changeup 45, sweeper 46). The
  Stuff+ board has the same **xFoul%** column (`xfoul`, sortable).
* **Foul% of contact on the card (Sean, 6 Oct 2026: "show on the swing and miss section the fouls at that percentile and not on the like 15% or
  21% scale")**: `fpc` = Foul% ÷ (Swing% × (1 − Whiff%)), the share of his contact that goes foul (`foulPerContact`, set on `V(p).m` beside `xbbf`
  for every pitcher view, so a window / split re-derives it), a `SIDE_P` def (the pool ranks it; `LB_EXTRA_P` so it draws as a column; Stats ▸
  Discipline), glossary / `SHORT` / `OUTCOME_LABEL_P` "Foul% of contact". Swing & Miss is K% | Whiff% · 2-strike Whiff% · **Foul% of contact**
  (`PCT_COLS_P`); the per-pitch `foul` stays a column and the Stuff side's `nfoul` is unchanged. League ~51%; Jax 2026 47.3 (14th), Henderson 59.1
  (99th). Why it's the scale that matters (scratch `kconv3.js`, every 100+ BF pitcher-season 2020-26): K% beyond what Whiff% alone implies
  (K% = −0.8 + 0.926·Whiff%) correlates with fouls per contact at r .57 and Called Strike% at .33; the two together fit it at r .81 (gap = −40.7 +
  0.51·foul/contact + 0.90·Called Strike%), that prediction repeats year to year at .57 (the gap itself .47) and forecasts next year's gap at .45;
  the predicted-low third runs 2.0 under this year and 1.3 under the next (72% still under), the high third 2.6 over → 1.4 over (70%).
* **Called Strike% in Swing & Miss (Sean, 6 Oct 2026: "add called strikes to the whiff or swing and miss section")**: `PCT_COLS_P` Swing & Miss =
  K% | Whiff% · 2-strike Whiff% · **Called Strike%** · Foul% of contact (`cstr`, already a card metric in the build's Swing & miss group);
  `PCT_COLS_PS` carries `ncstr` in the same spot. The four whiff-to-strikeout dials in one place: fouls per contact (+0.5 K% a point), called
  strikes (+0.8), two-strike finishing (+0.36 per point of 2-strike Whiff% over overall) and BB% (−0.35) — together 85% of a season's K% beyond
  what Whiff% implies (scratch `kconv4.js`; deGrom 2021 +7.3 actual / +6.8 fit, Pérez 2026 +0.1 / −0.7).
* **Pitching+ back, the Raw / Stuff switch back, the Stuff side on the Pitching+ models, xnERA (Sean, 6 Oct 2026: "make stuff+ back into pitching+
  with the addition of the location and command thing. And then can we add back the raw vs stuff button ... for the swing and miss stuff you use all
  the expected whiff expected two strike whiff expected called strikes and expected fouls from the pitching+ model, and also use expected batted ball
  stuff from it too ... an XK% too and then use that to come up with a k-bb% and a mix xwoba that lets you create a stuff nERA and just call that
  xnERA. And put that next to nERA on the leaderboard and then also with the stuff vs raw button when stuff is selected in the header replace nERA
  with xnERA")**: PR #363 reversed except the xRating — the header link, the board (`#pitches`: Pitching+ / Whiff+ / BB+ / Loc+ / xWhiff·loc /
  xGB·loc / xPU·loc / xFoul, `pb.sort` falls back to `pitp`), the Leaderboard column set **Pitching+** (`pitch pwhf pbb sloc nwhf ngb npu fbv ext`),
  the Stats panel group, home's "Pitching+ that start", Similar's skill list (`pitch`), `BTABS_P` = Pitching+ · K% / BB% · nERA (the Pitching+ tab's
  table now carries the xFoul pair too; the Rating · xRating line and As a starter stay off — `xr = null`, `asSP = null`); `RETIRED_P` / the saved-list
  migration are `suera aopt puera pera nk nbb uera xrat stuff swhf sbb`. **Raw ▾ / Stuff** (`stuffSide()`, the `.phsidebtn` dropdown in `playerHead`) is
  back; **`PCT_COLS_PS`** = Skills (x(K-BB)% = `xkbbs` · Mix xwOBA) · Swing & Miss (**xK%** = `xks` | xWhiff% · x2-strike Whiff% · xCalled Strike% ·
  **xFoul% of contact**) | Command (**xBB%** | Strike% · 1st-pitch · 3-ball, his own) · Batted Ball (xGB% · xPU% · Mix xwOBA). New pool stats (the PK
  block, `statsFor`, `NEXT_KEYS`, `SIDE_P`, `LB_EXTRA_P`, labels / `SHORT` / `STUFF_LABELS` / glossary): **`nfpc`** = `foulChance(p)`, the foul models'
  share of contact going foul (the Stuff side of `fpc`); **`xnera`** = `expectedNERA(pv, xks, xbbf, nmix)` — nERA's bookkeeping (`underlyingERA`'s:
  BB × wBB + HBP × wHBP + BIP × the per-ball wOBA, on the ERA scale) with Pitching+ xK%, xBB% and Mix xwOBA in place of his K%, BB% and mix — **centred**
  so the pool's BF-weighted xnERA averages its nERA (`sorted.xneraShift`; raw it sat 0.52 under for everyone on 2026, the fixed models reading the season
  ~2 K% points hot), lower = better (negated in the sorted list like `nmix`). 2026 starters: r .78 with nERA, sd .51 vs .67. **Leaderboard**: `xnera` is
  the first column of the Standard and Advanced pitcher sets, right after the nERA headline (`state.lb.xneraFront` moves it to the front of saved lists
  once). **Header**: `seasonLine` shows xnERA (the pool's `st.xnera`) in nERA's place while the Stuff side is on, in a window too. Jax 2026: nERA 3.65,
  xnERA 3.68; Skubal 2.82 / 2.25; Sánchez 2.85 / 2.85; Glasnow 2.79 / 3.27.
* **No K% / BB% tab (Sean, 6 Oct 2026: "get rid of the k% /bb% tab on the pitcher card as well")**: `BTABS_P` = Pitching+ · nERA; `renderDriversTab`
  and `DRIVERS` stay in `app.js`, unreachable; a saved `pbtab` of drivers falls back to Stats.
* **The Stuff+ / Pitching+ models retrained with 2026 in (Sean, 6 Oct 2026: "train it on 2026 then to get that to be better ... This way we aren't
  inflating things")**: Actions → Train Stuff+ models dispatched with `through=2026` (run 37429519220; the workflow's default through is the last
  finished season, i.e. 2025 until November). Why: the fixed models trained through 2025 read 2026 hot — the league's Pitching+ xK% 25.2 against
  K% 21.8, xWhiff% 27.5 against 24.6, x(K-BB)% 16.8 against 13.4 (193 listed pitchers) — so an expected value sat ~3 points above the same actual
  value and a pitcher's Stuff-side percentile ran 10 points under his Raw one at the same number (Messick: K-BB% 19.3 = 84th, Pitching+ x(K-BB)%
  19.6 = 75th). Training on 2020-26 puts the 2026 level on the actual; the compression (expected spread ~77-81% of the real one) stays — a tree
  model regresses to the middle. The `xneraShift` centring stays in place (it goes to ~0 on a season the models have seen). Every season and the
  postseasons are rescored by the same run.
* **Whiffs to strikeouts on the Pitching+ tab (Sean, 6 Oct 2026: "that table you've given me with whiff %, called strike %, and foul % can you add
  that ... to the pitching+ tab. And then make it so when you switch between raw and stuff the stuff shows what's expected ... an overall row and for
  each aspect I'd also like to see the +/- impact on the k-to-whiff gap")**: `renderKConv(p, st, R0, stuff)` under the Pitching+ tab's arsenal table
  (before the whiff check; CSS `.kconv` at the end of `styles.css`): a row per pitch (15+ thrown) — Use, Whiff%, Called Strike% (per pitch), Fouls
  per contact, **Δ called** = .779 × his share of pitches × (the pitch's rate − league), **Δ fouls** = .569 × its share of his contact × (rate −
  league), so the pitch rows add to the All pitches row (his season rates: `m.whf / cstr / fpc`); then the four-dial summary — fouls, called strikes,
  **two-strike finishing** (.357 × (2-strike Whiff% − Whiff%)), **walks** (−.348 × (BB% − league)), the four together, and the actual gap K% − (−0.8 +
  0.926·Whiff%) (`KCONV` / `kImplied`, scratch `kconv4.js`: the four explain 85% of the gap 2020-26). Δ cells heat-coloured (`pctStyle` at 50 + 12·Δ).
  **The Stuff side** reads the Pitching+ models: per pitch `xwhfl`, `xcstr` + the league's actual − expected called-strike offset (`xCalled`'s
  centring), `xFoulOf`; overall `st.nwhf / m.ncstr / st.nfpc / st.ns2whf / m.xbbf` and `st.xks` against the K% its xWhiff% implies. League rates from
  `lgRatesP()` (20+ BF, so BB% reads 8.9 there). **Build**: the arsenal row gains **`cstr`** (called strikes per pitch, %) and **`xcstr`** (the command
  models' called-strike chance per pitch, `(ck − cs) / cn`, null under 5), appended to `STUFF_ARSENAL`; `ARS_DAY` gains **`cst`** (called strikes that
  happened) so `arsenalView` carries both in a window / split. Until a build carries them the per-pitch Called / Foul columns and their Δs read "–"
  and only the overall row is filled (the retrain run of 07:25 UTC started before this merge, so its rescore carries `foul` but not `cstr` / `xcstr`;
  the next daily build carries all three for 2026, past seasons at the next rescore). Skenes 2026: fouls +3.5, called −2.1, two-strike −0.2, walks
  +0.7 → +2.0 against an actual +2.8; Imanaga 2026: +0.6 / −2.0 / −1.5 / +1.3 → −1.7 against −2.4.
* **Spring tab (Sean, 6 Oct 2026: "a tab about pitching+ but for spring training. As a way to get earlier indicators on arsenal and stuff and
  pitching+ changes", then "go ahead")**: a pitcher card's strip is Pitching+ · **Spring** · nERA while a spring the card can speak to is built —
  next year's `hist/mlb-<y>-spring.js` once it exists, else this year's, on a regular-season MLB card of that year or the one before
  (`springFor`; `indexReady()` now keeps the built spring / postseason keys in `ix.kinds`, which `springKey` reads too). `renderSpringTab`:
  a head line (BF · pitches · G, then what moved from last season to camp — FB velo ±0.5+, Stuff+ / Pitching+ ±3+, a **new** pitch (5+
  spring pitches, under 2% the year before), a **dropped** one (5%+ the year before, gone from 40+ spring pitches), a usage swing of 8+
  points) and a table in the Pitching+ tab's dress: per pitch, rows Spring 'YY · 'YY−1 season · Δ · 'YY season (once that regular season
  is built — so a March read can be checked in October), columns Use, Velo, IVB, HB, Spin, Stuff+, Pitching+ (each against its own type in
  its own file's league — `relOf` on the spring file's own `consts`), xWhiff / xGB / xPU (location-aware where the file has them), the
  actual Whiff / GB / PU dimmed with the swing / ball-in-play counts in the tooltip, Pitches; the Δ row coloured where a direction is a
  verdict (velo, the grades, the expected rates). All pitches = the card's own grades and his season rates. Full spring vs full season,
  whatever the card's filters. CSS `.springbox` at the end of `styles.css`. The **Pitching+ board's Games: Spring training pill is back**
  (`pb.src`, the forcing line is gone). Why only the physical columns matter (2026, 67 pitchers 60+ spring BF vs 200+ regular BF, spring →
  season r): FB velo .87, Stuff+ .64, GB% .60, Whiff% .40, Strike% .39 — a median spring is 27 BF / ~110 pitches. The 2026 spring file
  predates the location models (17-field arsenal rows), so Pitching+ reads "–" there until a `spring-2026` rescore (dispatched after the
  6 Oct retrain finished); next spring's file is built with them from the first morning.
* **The 2026 retrain landed (run 37429519220, 6 Oct 2026, 10:27 UTC; every season and the postseasons rescored)** — and it only half fixed
  the level: over the league's swings (20+ BF pitchers, from the arsenal rows) the location whiff model reads 2026 at 27.2 against an
  actual 25.1 (+2.0; it was +3.1 trained through 2025), the stuff-only one 25.8 (+0.7), xGB·loc 44.0 vs 42.4; and on the training seasons
  it runs **cold early and hot late** — 2020 −1.2, 2021 −1.1, 2022-25 within ±0.3, 2026 +2.0. The models have no season input, so a
  2026 pitch that looks like a 2022 pitch is priced at 2022's whiff rate while hitters whiffed less on it this year (whatever the cause —
  the ball, the ABS challenge zone, hitters adapting). The compression (expected sd ~0.8 of the real) is as before, so a Stuff-side
  percentile still sits under the Raw one at the same number (Messick K-BB% 84th vs Pitching+ x(K-BB)% 73rd; Skenes 90 / 81). Options
  not taken yet: a season feature in `train_stuff.py` (a new season scores at the last one's level), or centring the displayed expected
  rates on the season's actual league (`xneraShift` / `xCalled` already do this for xnERA and called strikes; Sean declined it for xWhiff on
  4 Oct).
* **Strikeout profile (Sean, 6 Oct 2026: "identifies the pitchers k archetype and why they are like this and what the true skill is and what's
  noise")**: `renderKArchetype(p, st, g)` at the top of the Pitching+ tab's lower half (before Whiffs to strikeouts; CSS `.karch`). The archetype
  name from his whiff percentile and the gap between his K% and what Whiff% alone implies (`kImplied`): 75th+ whiffs → "Pure swing-and-miss" /
  "Swing-and-miss, and finishes" (gap ≥ +1.5) / "Swing-and-miss that leaks strikeouts" (≤ −1.5); 40-75th → the biggest dial names it ("Foul-ball
  finisher", "Called-strike collector", "Two-strike closer", "Strike-thrower"; negative: "Balls in play, not fouls", "No called strikes", "Can't
  finish with two strikes", "Walks eat his strikeouts"; else "Average whiffs, average conversion"); under 40th → "Pitch-to-contact" with the same
  qualifiers; "· chase-driven" (Chase% 70th+) or "in the zone" (Zone% 70th+), "velocity" (85th+). A why line (K% and whiff percentiles, the gap,
  every dial beyond ±0.5 with his rate vs the league's), then the table: Whiff% (0.926 K% a point), 2-strike finishing (2-strike Whiff% − Whiff%,
  ranked among the pool's reference list), Called Strike%, Foul% of contact, BB% (`KCONV` weights) and K% — His, League, Pct, Effect, **Skill**
  (league + w × (his − league)), **Noise** ((1 − w) × (his − league)), **Repeats** (w = BF / (BF + k)). `KREL` k from every consecutive pair of
  100+ BF pitcher-seasons 2020-26 (scratch `karch.js`: talent variance = the between-season covariance, noise = c / BF): K% 128, Whiff% 97,
  2-strike finishing 818, Called Strike% 171, Foul% of contact 198, BB% 261 — so at 300 BF Whiff% is 76% skill, fouls 60%, called strikes 64%,
  walks 54%, two-strike finishing 27%. The note gives his skill K% (K% shrunk on its own k) and the dials' sum. On the Stuff side the same table
  reads the Pitching+ expected rates with an Actual column and Act − exp (what the models don't see) in place of Skill / Noise. Skenes 2026:
  "Swing-and-miss, and finishes · chase-driven, velocity", K% 28.1, skill K% 27.2, fouls +3.5 (78% skill at 712 BF), called strikes −2.1;
  Henderson: "Foul-ball finisher", fouls +4.6 of which +2.8 is noise at 371 BF; Phillips: "Balls in play, not fouls"; Imanaga: "Swing-and-miss
  that leaks strikeouts" (called strikes −2.0, two-strike finishing −1.3, 3rd percentile but 46% skill).
* **The strikeout profile and the dials in the minors (Sean, 6 Oct 2026: "add these functionalities to the minor league pitchers too")**: every
  level carries the inputs (Gameday gives calls, swings, fouls, the count), so a Triple-A / FSL card's Pitching+ tab already drew both under its
  arsenal table; Double-A and below returned at "no arsenal". `renderStuffTab` now shows, with no arsenal rows, a level note plus `renderKArchetype`
  and `renderKConv(p, st, [], …)`, and `renderKConv` draws the four-dial summary alone when it gets no rows (a note says the league is the level's
  20+ BF pitchers and the weights are MLB's). The profile's note on a minors card says the skill / noise split uses MLB's reliability, so Skill is an
  upper bound there. DeBerry (AA 2026): "Average whiffs, average conversion", two-strike finishing +1.9 of which +3.1 is noise at 582 BF.
* **Every minors season 2021-26 carries the count-state / called-strike / foul fields (6 Oct 2026)**: two rescore runs (37466634801: aaa-2022..2025
  + aa / ap / a-2025; 37481424671: aa / ap / a 2021-2024, every Gameday feed refetched for the count) put `cstr / foul / s2whf / fstrk / b3strk` on every
  pitcher in every `hist/<aaa|aa|ap|a>-YYYY.js`, so the minors' Swing & Miss / Command bars, the strikeout profile and the four dials read on past seasons too.
* **Claude rankings (Sean, 6 Oct 2026: "a ranking of starting pitchers for 2027 using both last years knowledge as well as player history
  including both majors and minors ... make sure ian seymour and didier fuentes are included as starters ... a separate page under fantasy and
  call it claude rankings, and for each player add a comments section", then "also factor in like the pitching+ model and maybe even anyone that
  performed well down the stretch")**: Fantasy ▸ **Claude rankings** (`#claude`, `renderClaude` in `app.js`, the Stuff+ board's standing card —
  every `[data-mode="mock"]` CSS rule also names `claude`; `.cltable` rules at the end of `styles.css`) reads **`hist/claude-2027.js`**
  (`window.DRAFT_CLAUDE27`, 110 starters, hand-built — not part of any build): a row per pitcher (tier, projected ESPN points, per start, starts,
  the 2026 line, the Aug 1-on nERA / K%), tap a row for his comment (56 hand-written for the top of the list plus Seymour, Fuentes, Meyer, Sheehan,
  Ohtani, Glasnow, Sasaki, Pepiot; the rest built from the same numbers — archetype, dials, stretch run, flaws, 2024-25 and minors lines), a name
  opens his card; search, Total points / Per start order, Show all comments. **How it was built** (scratch `scrape.js` → `assemble.js` → `rank.js`
  → `comments.js` + `claude27.js`): the site's own Leaderboard scraped headless for every pitcher's 2024 / 2025 / 2026 and Aug 1-on 2026 pool
  numbers (nERA, xnERA, xK%, Pitching+ family, called strikes, fouls per contact …), starts-only ESPN points per start from the fantasy files,
  the Marcel projection (`hist/proj-2027.js`), and the minors files. Points per start = 40% history (2026 / 25 / 24 at .5 / .3 / .2 by starts,
  regressed with 12 starts of league) + 40% 2026 process (xnERA .45, nERA .25, Pitching+ x(K-BB)% .30, the Aug 1-on nERA .30 where 25+ IP — the
  pts/start-per-nERA scale is a fit over 2026 starters, 26.23 − 4.10·nERA; shrunk by BF toward his history) + 20% Marcel; age 34+ −0.25 a year,
  ≤ 25 +0.25; no 2026 season (Pepiot, Berríos, Priester) −0.5 and 80% of the starts; starts = 95% of max(Marcel GS, .75 / .25 of 2026 / 2025 GS),
  cap 32; total = per start × starts; tiers at 375 / 330 / 298 / 272 / 250. Seymour and Fuentes are ranked as starters (27 GS) with the
  reliever-to-starter translation (`AS_SP`: a whiff point, half a run) — Fuentes' per-start value is a judgment call (11.4) since the formula's
  shrink toward league on 300 relief BF was too hard on stuff that reads top-15. Rebuild by hand after the season's last build (re-run the four
  scripts) or when Sean asks; the comments are prose and date quickly.
  **Scored under his own preset (Sean, minutes later: "I have a scoring saved in fantasy ... make it based on that scoring")**: each row carries
  his projected per-start stat line (`line`: starts-only 2024-26 game logs weighted .5 / .3 / .2 — every `gk` field plus QS / NH; a synthetic
  line from his rates for a pitcher without ten starts) and that line's ESPN points (`espn`); `renderClaude` scores the line with `fPts` under
  `fpreset()` and scales it by `pps / espn`, so the ranking's process adjustments carry into any scoring, re-ranks, and a **Scoring** pill on the
  bar switches the Fantasy preset (the same `fstore.current` the Fantasy page uses). The stored `pps` / `pts` / `rk` are the ESPN-standard ones.
* **The warm pass (Sean, 6 Oct 2026, after a Clutch Time screenshot — "my site has a rigid thin feel to it" — then "convert the site to the
  formatting and theme that you believe for the use case would be most optimal, easiest to understand and view and use, and most functional.
  All the power to you here")**: the look, not the layout — every page keeps its structure, columns, bars and numbers. **This supersedes the
  earlier "don't bring back unasked" rules on bold, rounded corners, air-instead-of-borders and the pale-blue ground; Sean asked.** The block
  at the very end of `styles.css` ("The warm pass", every selector prefixed with six `:root` so it wins over every earlier pass — delete the
  block and the `warm` scheme to go back) plus a **`warm` colour scheme in `themes.js`** (the scheme sets its tokens inline on `<html>`, which
  beat a stylesheet override — so the pass's colours live there: an off-white ground `#f3f2ee`, surfaces `#fbfaf7`, ink `#141414`, hairlines
  `#e4e2db`, every accent / rule / band / button token the ink or the hairline; dark `#15161a` / `#1d1e23` / `#f2f1ec` / `#2f3036`). It is the
  **default scheme** (`DEFAULTS.scheme`, `defaults.js`) and `themes.js` moves every device to it once (`draft2027.warm1`, the saved scheme
  cleared); a scheme picked after that stays, and the UNC / Titans / … schemes are still in Appearance. **What it does**: type is the hierarchy
  — names, headings, the sorted number and the band's values 700 in the condensed face (list names 19px, the card title 34px / 27px phone), body
  500, labels 600 (the site-wide "no bold" rule is overridden); small labels (column names, the bars' section names, the card's facts, home's
  section lines) are 11px grey tracked uppercase — the one reversal of the no-capitals rule; **no navy header bars or frames** — table headers
  are the surface with a hairline under them, the outer page card and the boards have hairline borders and 16-20px corners, the dropdowns and
  the Filters window 16px with a soft shadow, the popup card 24px; **pills** — every button, tab, pill and pager number is a 36px+ hairline
  pill, the pressed one filled ink with ground-coloured text; the header sits on the ground with a hairline, the pages as plain words with the
  current one underlined, the search a pill; list rows 56px with a hairline between; **the sorted column** keeps its fill on a desktop (8px
  corners, 4px in from the row) and on a phone shows **bold coloured digits on a clear ground** — `paint()` now sets `--heat` to the cell's
  colour and the phone rule reads it; **the percentile bars** keep Savant's geometry but lose the 10 / 50 / 90 ticks and dashed rules (`.svtick`
  / `.svdash` hidden), the track and fill get 2.5-3px `rx`, labels in the ink at 600, values 700 condensed, section names the small grey label.
  `themes.js` loads Barlow Condensed 800 too. **Found and fixed the same hour**: since the nERA-headline change (6 Oct, PR #367) the pitchers'
  headline cell's paint / `hot` / `sorted` code sat inside a mid-line `//` comment, so the nERA column was never coloured or marked sorted; the
  comment is on its own lines now. Headless phone + desktop, light + dark: Leaderboard, home, a card, the Pitching+ board, Fantasy, Claude
  rankings, the Filters window — no script errors. Mocks of the direction (a literal Clutch Time take, then "now vs warmer" for the Leaderboard
  and the card) are the "Clutch Time Mock" canvas, not in the repo.
* **Standard rows on the card; three pages gone; the scroll fixed (Sean, 6 Oct 2026: "the leaderboard isnt allowing me to scroll at all ·
  you can eliminate the league trends, call up watch and compare · get rid of the savant bars and classic bars and just make the website
  standard whatever you feel is easiest on the eyes and easiest to understand when immediately looking at the player card")**: (1) the warm
  pass had put `overflow: hidden` on the rows' scrollers (`#bscroll` / `.board-scroll` / `.pbscroll` / `.fscroll`) for the rounded corners,
  which froze every list — they keep the radius and lose the overflow rule; never set overflow on a scroller for its corners. (2) **League
  Trends, Call-up Watch and Compare are off the menus and routes** (`pitchBoardEl` no longer adds their entries and removes a Compare one,
  `NAV_GROUPS`'s Leaders group is `leaderboard · trending`, `readMode` sends `#trends` / `#callups` / `#compare` home, `BTABS` has no Compare
  tab); `renderTrends`, `renderCallups`, the Compare page and the card's compare branch stay in `app.js`, unreachable. (3) **The card's
  percentile sections are plain HTML rows** — `pctRows(groups, head)` in place of both `pctSvg` (Savant's charts) and the classic meters:
  a `Percentile · Value` head on the first column, each section a small grey tracked name over a hairline, each row = the stat name (600),
  a 10px rounded track filled to his percentile in Savant's colour, the percentile as a 24px coloured pill at the end of the track
  (`pctStyle`), and his value bold in the condensed face at the right; fold-outs (▸ / ▾ on the name), "|" line breaks and the tap note
  (`statPop` — the host carries `.svchart`) as before; no ticks, bubbles or Poor / Average / Great. CSS `.pctstd / .prowhead / .psec /
  .prow / .ptrk / .pfill / .ppct / .pval` at the end of `styles.css`. The Appearance switch "Percentile bars" is gone and `state.bars` is
  unused (`paintBar` is one scale); `pctSvg` / `pctChart` / `meterRow` stay for the record. Every earlier bar note in this file (Savant's
  bars, the studio bar, the mock's bars, "don't restyle the bars unasked") is history as of this entry.
* **The Pitching+ tab, simplified; softer edges (Sean, 6 Oct 2026: "the rest of the tables look a bit busy/hard to understand", "if you think the
  player cards should have softer edges thats great too ... make the entire site layout in the most optimal and easy to understand fashion")**:
  under the arsenal table the tab now shows only the **strikeout profile** in a plain form — the archetype as the heading, one line that adds up
  ("K% 30.0 — the whiffs alone say 28.6, the rest is +1.4"), and five rows in the card's dress (Whiff%, 2-strike finishing, Called Strike%, Foul%
  of contact, BB%: his rate vs the league and percentile under the name, the K%-point effect as a coloured pill, "mostly skill / half skill /
  mostly noise" from `KREL` at his BF), then the whiff check. The **xK% breakdown** table and the **Whiffs to strikeouts** tables (per-pitch Δ
  called / Δ fouls, the four-dial summary) are off the tab (`renderXkBreakdown`, `renderKConv` stay in `app.js`, as does the profile's old
  seven-column table — replaced inside `renderKArchetype`; CSS `.ksum / .krows / .krow / .kpill`). Softer edges: the card's tab boxes, tables and
  the Stuff+ grades get 8-14px corners, headshots are round. **NPB**: asked whether the site could carry Japanese-league data (Imai, Murakami) —
  no: the MLB Stats API lists Nippon Professional Baseball as sport 31 but serves no teams, schedule or player lines for it (checked 6 Oct 2026),
  Statcast has nothing, and NPB's Hawk-Eye data isn't public; their MLB seasons are on the site like anyone's.
* **xCalled on the Pitching+ tab (Sean, 6 Oct 2026: "add expected called strikes to the pitching+ tab as well")**: an **xCalled** pair after xFoul in
  `renderStuffTab`'s Pitching+ table — the command models' called-strike chance per pitch (the arsenal's `xcstr`, `arsenalView`'s in a window /
  split) plus `xCalled`'s league centring (`lgRatesP().cstr − .xcstr`, the models read the newest season a little hot) over his actual called
  strikes per pitch (`cstr`); All pitches = `m.ncstr` over `m.cstr`. Sale 2026: slider 15.7 expected / 17.6 actual, sinker 25.4 / 26.3, all
  16.9 / 17.4; Imanaga: splitter 7.6 / 6.7, all 14.0 / 13.6 — the model expects a splitter-heavy mix to collect few called strikes, so his gap
  to Sale is the arsenal's design, not sequencing luck. Files built before 6 Oct 2026 read "–" per pitch.
* **Savant's bars back, Skills = Whiff% · xBB%, a plain Leaders link, home's 2027 starters, the K% equation (Sean, 6 Oct 2026: "can you go
  back to these percentile bars. and then for the skills can you make that be whiff% and then make it some sort of xBB% based on their strike
  rate first strike rate third strike rate", "redesign the layout of the website the home page ... the site header", "i still want to see the
  table that shows how each input contributes to their k% ... easier to understand than before")**: `pctColumns` draws `pctChart` (the Savant
  charts in the warm pass's dress — the plain `pctRows` of PR #385 stay in `app.js`, unused); `PCT_COLS_P` Skills = **Whiff% · xBB%** (`xbbf`, the
  Strike% / 1st-pitch / 3-ball fit) and `PCT_COLS_PS` xWhiff% · xBB%. **Header**: the Leaderboards menu had one entry left, so `pitchBoardEl` hides
  `#lbsel` and puts a plain **Leaders** link to `#leaderboard` in its place (Home · Leaders · Pitching+ · Fantasy ▾ · ⋯). **Home**: a **2027
  starters** card between the leaders and Trending — the Claude rankings' top rows scored under the current fantasy preset (`fPts(wP, r.line) ·
  pps / espn · GS`), a name opens his card, "Claude rankings →" opens the page. **Pitching+ tab**: `renderKArchetype` is an equation, not a
  table — "K% 30.0 = 28.6 from whiffs alone (31.7%) + 1.4 from how they turn into strikeouts", then one row per dial (fouls on contact, called
  strikes, finishing with two strikes, walks: his rate · league · percentile, a ± pill in K% points coloured by its sign, and "mostly skill /
  half skill / mostly noise" from `KREL` at his BF), a **The four dials** total and an **Everything else** remainder (sequencing, luck), and the
  skill-K% note (`.ksum / .krow / .khead / .ktot / .krest`). The `.rollhd` gets 1px of left padding — the tracked small caps' first letter was
  clipped by the box.
* **The K% build-up, no scale row, no prose (Sean, 6 Oct 2026: "get rid of the poor average great label for the percentile bars", "show
  their whiff %, then show what k% that whiff translates to, then show the process of how each component adds or subtracts to their k rate until
  it lands at the ultimate k rate ... i like the column that says repeats or noise or skill", "i dont think we need any of that wording below")**:
  `pctColumns` draws every chart with `scale = false` (the Poor / Average / Great row is gone; `pctSvg` still takes the flag). The Pitching+ tab's
  strikeout profile (`renderKArchetype`) is a **running K% table**: columns Step · K% pts · K% · Repeats? — Whiff% first (his rate, league,
  percentile, "→ a 28.6 K% on whiffs alone", the running K% = `kImplied`), then each dial (fouls on contact, called strikes, two-strike finishing,
  walks) as a signed coloured pill moving the running K%, then Everything else (the gap the four don't explain) and the final row K% = his K%
  with the whole gap as its pill; the Repeats? word from `KREL` at his BF. The sum line, the skill-K% note, the whiff check (`renderWhiffCheck`
  stays in `app.js`) and the "Pitching+ is Stuff+'s twin" note are off the tab. On the Stuff side the first row is the expected Whiff% and the
  last xK%, with his actual K% in the sub-line. CSS `.krun / .kstart / .krest / .ktot` at the end of `styles.css`; a phone wraps the sub-lines.
* **No line breaks on the card (Sean, 6 Oct 2026: "get rid of the line break for k% and the rest of its area and bb% and its area")**: the `"|"`
  entries left `PCT_COLS_P` / `PCT_COLS_PS` — Swing & Miss is K% · Whiff% · 2-strike Whiff% · Called Strike% · Foul% of contact and Command BB% ·
  Strike% · 1st-pitch · 3-ball in one run each; the break machinery stays in `rowsOf` / `pctSvg`, unused.
* **The proposed layout, built (Sean, 6 Oct 2026, from the "Proposed" boards on the Clutch Time Mock canvas: "Implement both of those they
  look good")**: **Leaderboard** — the six filter buttons are one control row: a **Hitters · SP · RP** segment (`.posseg` in `renderToolButtons`
  under `onePage()`; Hitters tapped again opens the Position tab for a sub-position and reads it, e.g. "SS"; SP / RP through `togglePos`), one
  **Filters** button (its dropdown shows the tab row again — Position · Filters · Stats · Splits · Dates · Table format — `popBody` no longer skips
  `grpTabs()`), the **Standard ▾** pill and a **Season ▾** pill (`lbSeasonPill`: the same pick as the Filters tab's Season row; a span reads
  "2024–26 ▾" and opens that tab); the count and the Min PA / IP box sit on a quiet second line (`.lbbreak` flex break in `renderPager`; a phone
  wraps the row instead of scrolling it). **Result / Process bands** over the column names (`#colband`, a second grid with the header's template,
  drawn in `renderColheadIn`; `RESULT_KEYS` says which columns are outcomes, every contiguous run gets one word; the Result band's rule is ink).
  The **headline cell** (`.score.hero`) is the value in its percentile colour over a small percentile pill (`.ppill`), not a filled cell; the
  other sorted columns keep their fill. **Card** — the bio is plain words on the season line ("2026 ▾ · LAD · SP · LHP · 29 · 6'3" 240";
  `.hbio.inline`, `fillBio` writes text for it, refilled when MLB's record arrives), the band's numbers are **four tiles** with their percentiles
  (`bandTiles`: a pitcher's nERA with ERA beside it (xnERA on the Stuff side), K%, BB%, K-BB% with IP; a hitter's xwOBA with wOBA, AVG, OBP, SLG
  with OPS and PA; a level without the official line gets K% / BB% / Brl% from the card's own rates), and **Filters / Raw ▾ sit on a row under
  the tiles** (`.phctl`) with the view's name at the right ("Full season" or the window / split). The `.hstrip` facts row, the `.hrow` and the
  `.hstats` line are gone from the band (`seasonLine` still builds the line; the tiles read it). `finish()` keeps the tiles and the control row
  out of `.phleft` so they span the band (desktop grid areas `left right / tiles / ctl`). The Arsenal YoY tab on the mock is **not built** —
  Sean asked to wait on the year-over-year arsenal comparison. CSS: the block "the proposed layout, built" at the end of `styles.css`.
* **A phone's Leaderboard starts higher (Sean, 6 Oct 2026, from a phone screenshot: "how far down the leaderboard starts")**: under `phonePages()`
  the Min PA / IP box rides on the control row after the Standard ▾ and Season ▾ pills (no `.lbbreak` on a phone), the count "1–25 of 539" shares
  the `.pnavrow` line with the page numbers (count left, pages right), the Result / Process band row (`#colband`) is hidden on a phone and the
  column-name row is a little shorter — the first row sits ~190px higher. A desktop is unchanged.
* **Tighter still on a phone (Sean, 6 Oct 2026: the table "takes up like 55% of the page")**: the phone's control row is one sideways-sliding line
  again (segment · Filters · Standard ▾ · Season ▾ · Min, 32px tall), the count / page-number line is 28px, the column-name row shorter and the
  page's top margin 6px — the first row sits ~120px under the site header and a 390 × 844 phone shows twelve rows. Desktop unchanged.
* **A narrower name column on a phone (Sean, 6 Oct 2026: "lower the size of the player name column so I can see a bit more")**: on a phone
  `fitNameCol` holds the name column to 124-150px (a longer name ellipsises), the name is 16px, the rank column 24px (the two `--rankw` setters),
  the stat columns 42px and the column names 10px with light tracking — four stat columns show beside the name at 390px instead of two and a half.
  Desktop unchanged.
* **A phone's controls fold into Filters; the header aligned; names fit (Sean, 6 Oct 2026: "move the hitters rp sp custom and year into the
  filters button instead also the column headers are misaligned also could we make the default width what it is in the second screenshot and
  figure a way to fit the names in there")**: under `phonePages()` the control row is **one Filters button** ("Hitters · Filters", "SP · Filters" —
  `posBtnLabel`) and the Min box; the Hitters / SP / RP choice is the dropdown's Position tab, the **Standard ▾ pill sits at the top of its Stats
  tab** (`lbSetPill`, factored out of `renderLbTabs`; `.lbpills` in `popBody`) and the season is the Filters tab's own Season row (a season pill
  there was tried and dropped as a duplicate). **The misalignment**: the rows' grid gave the name track `minmax(--namew, 1fr)`, so a row with a long
  name grew its track past the header's 150px and every column name sat left of its column (Pete Crow-Armstrong's page: header 150 / row 176).
  On a phone the name track is a fixed `var(--namew)` (150px, `fitNameCol` lo = hi = 150), `.who` clips, and `renderRowsIn` steps a name that
  doesn't fit down to 14px then 12.5px (`.name` is `display: block` so it measures and ellipsises) — Pete Crow-Armstrong fits at 12.5px. Desktop
  keeps the six-button row and the stretching name column.
* **Rating = Whiff% 50 / xBB% 50; the Leaderboard is part of the page (Sean, 6 Oct 2026: "add back a ranking stat for pitchers that is the
  average percentile of their skills thing so whiff and xbb", "we don't need to make it so the leaderboard is like a separate window on the
  page")**: `PITCHER_SCORE_WEIGHTS` / `meta.pitcherWeights` = `{whf: 50, xbbf: 50}` (`data.js` + `scoreNote.P` patched, `tools/build_data.py`) —
  the two Skills percentiles averaged (xBB% is on `m`, so the pool has its percentile before the score). **Rating is a column**: a `SIDE_P` def
  `rating` read off the pool's stats (`metricValue` → `st.score`, the row's percentile `st.scorePct`, the sort key in `val`), first in `LB_EXTRA_P`
  and the Standard / Advanced pitcher sets (`state.lb.ratingFront` moves it to the front of a saved list once), a Result band; and the first row of
  the card's **Skills** (`PCT_COLS_P` / `_PS`: Rating · Whiff% · xBB%, the bubble the number itself via `RATING_M`). The pitchers' **headline nERA
  cell is coloured by nERA's own percentile** (`st.pct.nera`), not the Rating's. **No standing card on the Leaderboard / Recent** (both views): the
  block at the end of `styles.css` lets the html / body and `main.wrap` scroll, the rows' box has no height, frame, radius or ground of its own
  (rows sit on the page ground, alternate rows on the surface), and the column names stick under the site header (`.colwrap` sticky at
  `--header-h`). Rankings, the Draft board and Fantasy keep their standing card. This supersedes the "stands still" rule of 26 Sep for those two
  pages. Beware once more: a `//` comment appended to a line that continues with code swallows the code — use `/* */` mid-line.
* **One page with Show more, the filters frozen, no window (Sean, 6 Oct 2026: "could you just make it one big page with a show more option / And I
  don't like how ... the filters stuff scrolls away plus make them freeze paned too", then "I like how you've handled the highlighted or sorted
  column as is now")**: PR #395's page-scrolling Leaderboard is undone — the control row, the count and the column names are fixed again and only
  the rows' box (`#bscroll`) scrolls, as every other list — but **frameless**: `#bscroll` / `.board-scroll` have no border, radius or own ground,
  the column names sit on the page ground (`#colhead` / `.colwrap`), the rows alternate ground / surface (the block "the Leaderboard without the
  window dress" at the end of `styles.css`). On a phone the page numbers are gone: `pageWindow` under `phonePages()` returns a cumulative window
  (`end` = the first `state.page` pages, `more` while there are more), `renderRowsIn` appends a **Show more · 25 of 539** pill (`.showmore`) under
  the rows (`state.page++` then `renderRows()`, the scroll kept), and the `.pnavrow` line holds only the count ("25 of 539"). The pill is
  `position: sticky; left: 0` with `width: min(100%, 100vw − 24px)`, so it stays centred in the visible part of the sideways-scrolling rows box.
  The sorted column's fill and the headline's value-over-pill are unchanged. Desktop still lists everyone.
* **No window on a phone, banded thinner rows, a shorter name column (Sean, 6 Oct 2026, from a screenshot: "It still looks like it's a window
  ... the 50 of 223 can be moved up and we can eliminate that unnecessary gap ... make it so the rows are banded ... make them thinner a bit and
  make the player column much less long")**: the block at the end of `styles.css` — on a phone the Leaderboard / Recent `main.wrap` has no
  hairline, radius, surface or side padding (the warm pass's `!important` card rule needed a six-root mobile override), the count line sits
  right over the column names (no `.pnavrow` margin, `#colhead` padding 0, the `.h` cells 6px) and the header cells have no surface ground;
  **bands** on both layouts — every even `#rows > .row`'s `.row-main` (the rows are `li.row` wrappers, so `nth-child` goes on the `li`) is
  ink at 4% on the ground (`color-mix`), the surface tint of the hour before was invisible, and the hairline between rows is gone (the bands
  are the rules); rows **44px on a phone, 50 on a desktop** (`box-sizing: border-box` — without it the 4px padding made 52 — and the
  value-over-pill headline cell loses its padding / border on a phone, which had set the row at 52); the phone's **name column is 116px**
  (`fitNameCol` lo = hi = 116, the grid's `--namew` default, a 22px rank column), the name 15px stepping down to 13 then 11.5px in
  `renderRowsIn` before it ellipsises, the team line 9.5px.
* **Page numbers back on a phone, on the count line (Sean, 6 Oct 2026: "actually do the pages and put it in the upper gap on the right, but
  don't make it super space taking up")**: the Show more pill of PR #396 is gone (`pageWindow` pages a phone at 25 again, `renderRowsIn` appends
  nothing, `.showmore` CSS removed); `renderPager`'s `.pnavrow` holds the count at the left ("1–25 of 193") and the page numbers at the right
  (‹ 1 2 … 8 ›) as 22px pills on a 22px line (the block at the end of `styles.css`), so the rows start where they did.
* **Rating off the card; the sorted nERA is the value alone (Sean, 6 Oct 2026: "get rid of rating on the player card and when nera is sorted on
  make it show the stat as big and red like the other columns dont have like the percentile thing below it")**: `PCT_COLS_P` / `_PS` Skills =
  Whiff% · xBB% (xWhiff% · xBB%) — the Rating stays a Leaderboard column and the pool's score; the headline cell keeps `.hero` (the value in its
  percentile colour, big) but appends no `.ppill`. Found alongside: the `sorted` / `brk` classes on that cell had sat behind a mid-line `//`
  comment since PR #390 — the third time; it's a `/* */` now.
* **Card and Leaderboard tidy, 6 Oct 2026 (Sean, from two phone screenshots: "get rid of rating on the player card and when nera is sorted on
  make it show the stat as big and red like the other columns dont have like the percentile thing below it"; the tiles "just keep the lower text
  to be the percentile of the metric and that's it"; "make the avg and obp be color mapped in the same way"; "put the bio stuff below the year
  on its own line"; "get rid of the order by here that'll simply be determined by what the user selects to sort ... put the page number stuff on
  the same level as the sp filters button is and then add the 1-50 of 233 onto that same level"; "in the area where the order by was put the min
  IP filter in there")**: `PCT_COLS_P` / `_PS` Skills = Whiff% · xBB% (xWhiff% · xBB%), the Rating a column and the pool's score only; the sorted
  headline cell keeps `.hero` (the value big in its percentile colour) and appends no `.ppill` — and the `sorted` / `brk` classes on it had sat
  behind a mid-line `//` since PR #390 (the third time; `/* */` now). **Tiles**: the line under the number is the ordinal percentile alone (no ERA /
  wOBA / OPS / PA / IP), so they're ~30px shorter; **AVG and OBP are coloured** — `slashPct(g, idx, v)` places the official value among the pool's
  300+ PA hitters' `hist/career.js` TOT lines that season (AVG idx 14, OBP 15; cached per season / pool; 20+ needed), since neither is a card
  metric. **Bio**: team · positions · B/T · age · height weight are a `.hbioline` under the year inside the title (`.mlinein` + `.hbio.inline`
  moved there), not on the season line. **Filters panel**: the Leaderboard's Filters tab has no Sort by (the column tapped sorts; the headline
  is the default) and the section is "Minimum" with the Min PA / IP box and Per page — `renderPager` keeps no Min box in the top row
  (`mfKeep` null) and the Filters panel's `minNode` no longer skips `onePage()`. **A phone's bar** is Filters · "1–25 of 193" · ‹ 1 2 … 8 › on
  one line (`.pnav.inbar`, 24px pills pushed right; the `.pnavrow` is gone), so the first row sits another ~20px higher. Desktop: the count line
  under the controls now carries only the count.
* **The K% build-up in five plain columns (Sean, 6 Oct 2026, from Yamamoto's card: "the significant amount of words makes it tougher for me to
  understand, maybe instead just show the stat and the league avg then the impact to k% and then the updated k%")**: `renderKArchetype`'s table
  (`.krows.kfive`) is Step · His · Lg · ± K% · K% — Whiff% (→ the K% whiffs alone imply), Fouls / contact, Called Strike%, 2-strike Whiff% (the
  rate itself, its effect still on the gap over his overall), BB%, Everything else, K% (his against the league's, the pill the whole gap) — no
  sub-lines, percentiles or Repeats? column; the one-line explanations are the rows' tooltips. The Stuff side prefixes x. CSS at the end of
  `styles.css`; the archetype heading is unchanged.
* **Two-strike finishing as the gap (Sean, 6 Oct 2026: "do like the gap one ... their 2 strike whiff minus their actual whiff")**: the K% table's
  row is **2-strike finishing** — His = 2-strike Whiff% − Whiff%, signed (Misiorowski −0.6), Lg the league's gap (−0.7) — in place of the raw
  two-strike rate; `num(v, sgn)` prints that row signed.
* **The His column coloured (Sean, 6 Oct 2026: "On the his column can you heat map those stats in the same way the +/- K is")**: each His cell of
  the K% table is a pill in his percentile colour on that stat among the pool (`pct.whf / fpc / cstr / bb / k`, the two-strike gap's place among
  the reference list; `num(v, sgn, pc)`, `.knum.khis`); the Lg column stays plain. The `.kstart .kpill` blank-pill rule now skips `.khis`.
* **A subtotal row (Sean, 6 Oct 2026: "add a row above everything else and basically just make it the subtotal of the four process oriented
  inputs to the k whiff gap")**: **The four together** (`.krow.ksub`) — the fouls, called strikes, two-strike finishing and walks pills summed,
  with the running K% at that point — sits between BB% and Everything else; Misiorowski +4.8 of a +4.2 gap, so Everything else reads −0.7.
* **± K% pills coloured by sign (Sean, 6 Oct 2026, Schlittler's two-strike finishing: "why is the +0.4 in the light blue color if his finishing
  is above league avg")**: they had been coloured on the percentile scale at 50 + 12 × the effect, and Savant's middle is a pale teal, so a small
  plus read as a minus. `signStyle(v)` in `renderKArchetype`: neutral grey at 0, red deepening with a plus and blue with a minus, full at ±2.5
  K% points (white digits past ~±1.1). Everything else keeps its flat grey pill (the `.krest` rule); the His pills stay on the percentile scale.
* **The subtotal row, tinted and without a running K% (Sean, 6 Oct 2026: "not show the k% there since it is directly above ... make the row color
  different so it clearly stands out as a subtotal")**: `.krow.ksub` carries only the four-dial pill (its K% cell is blank — the BB% row above
  already shows it) on a grey band (ink at 6% on the surface, 8px corners, bled 10px into the table's padding).
* **LHP / RHP in the bio, IP for nERA on the band (Sean, 6 Oct 2026: "change the bio for pitchers to just show LHP or RHP instead of B/T L/R",
  "instead of nERA show IP and don't make IP heat mapped at all")**: `fillBio`'s inline branch prints a pitcher's hand as LHP / RHP (MLB's
  `throws`, else the data's) and no B/T; hitters keep B/T. `bandTiles`' first pitcher tile is **IP** (the official line's, else `fmtIP` of the
  view's innings — so a window / split reads its own), no colour and no percentile under it; K% · BB% · K-BB% follow as before. nERA (xnERA on the
  Stuff side) left the band — it's still the headline of the Leaderboard and the card's nERA tab; `seasonLine` still builds it.
  **Then two lines** (Sean, minutes later: "put their age and height and weight on the line right below that first line where team position and
  throwing arm is"): the `.hbioline` reads team · positions · LHP / RHP (a hitter's B/T) and, under it, age · height weight as a block `.hbio2`
  inside the inline bio (`fillBio`; CSS at the end of `styles.css`) — "MIL · SP · RHP" over "24 · 6'4\" 197".
* **The ± K% pills go white sooner on the red side (Sean, 6 Oct 2026: the ink "on the dark ish red" was hard to read; then "don't make all red heat
  maps white text")**: `signStyle` switches to white digits at t > 0.25 for a plus (about +0.6 K% and up) and keeps 0.45 for a minus; the faintest
  reds and the His pills keep `pctStyle`'s own contrast rule. An all-red-is-white version lasted a few minutes (PR #409).
  **Then the scale itself (Sean, from Wheeler's card: "I'm still seeing the black on dark red that I can't really read")**: `pctStyle` picks its
  ink by luminance — white on any fill under 0.35 (the mid reds from about the 70th percentile up, the blues from about the 30th down), dark on
  the pale ends and the teal middle. By contrast ratio alone dark ink had won on the mid reds (a 5.8 : 3.1 margin at the 75th), which is what he
  couldn't read. Every heat-mapped cell, tile and pill shares the scale, so the Leaderboard's sorted column changes with it.
* **Filters / Raw in the band's top-right corner (Sean, 6 Oct 2026: "move filters and raw vs stuff up above the boxes ... so that we can move the
  header border up", then "put the filters and raw stuff buttons in that blank space in the top right")**: the `.phctl` row is a **column of two
  26px buttons** (Filters ▾ over Raw ▾, the same width) in the empty corner beside his year and bio lines — on a phone absolutely placed
  (`right: 12px; top: 50px`, under the ×; the year / bio block takes 100px of right padding and an 80px minimum height so the tiles clear it),
  on a desktop the grid's `right` area (`left right / tiles tiles`, 34px down); the view's name shows under them only when a filter is on
  ("Full season" is gone). The tiles follow, so the band ends right under them: 224 → 191px on a phone, 252 → 206 on a desktop. The
  above-the-tiles row of the hour before (PR #412) is history. The block at the end of `styles.css`.
* **The K% table's last rows pared (Sean, 6 Oct 2026: "in the everything else row only show the 1.6 don't show the k% and then in the k% row
  only show the last two columns of the final +/- and the final k%")**: Everything else carries only its pill (its K% cell blank like the
  subtotal's), and the K% row's His / Lg cells are emptied after the row is built (`.knum.kblank`) so it reads just the whole gap and his K%.
* **No tiles; the old facts row back at the band's foot (Sean, 6 Oct 2026: "let's get rid of the boxes and put the stats that we had before back at
  the bottom of the header and do it in the same format they were there in")**: `playerHead` builds a `.hrow` from the strip's PA / IP fact and the
  season line's facts (nERA · ERA · K% · BB% · K-BB%, or AVG · OBP · SLG · OPS) — small tracked labels over condensed numbers, spread across the
  band under a hairline on a phone, left-aligned with 28px gaps on a desktop (grid `left right / row row`; `finish()` keeps it out of `.phleft`
  like the tiles were) — and `bandTiles` is no longer called (it stays in `app.js`). The corner Filters / Raw column and the two-line bio stay.
  Band 191 → 166px on a phone, 206 → 174 on a desktop. CSS at the end of `styles.css` (the phone's old `.hrow` rule's −46px margin is undone).
* **The Titans palette (Sean, 6 Oct 2026: "make the websites main color palette or theme the Tennessee titans color scheme")**: the `titans`
  scheme in `themes.js` is rebuilt in the warm pass's full token shape — light: a cool silver ground `#eef1f5`, surfaces `#fbfcfe`, Titans navy
  `#0c2340` for type, buttons and the pressed pill, Titans blue `#4b92db` as `accent-2` (active fills, the band's blue), hairlines `#d6dde8`,
  the red `#c8102e` stripe-line under the band; dark: `#0b1628` / `#112138` / `#edf3fa`, buttons Titans blue with navy ink. It also sets the warm
  pass's own tokens (`ground line-soft frame secrule accent-ink band-ink svtext svrule pctrack`), which `styles.css`'s warm block hard-codes to its
  off-white values and a scheme must override inline. It is the **default scheme** (`DEFAULTS.scheme`, `defaults.js`) and `themes.js` moves every
  device to it once (`draft2027.titans1`, the saved scheme cleared), as the warm pass did; Warm, UNC and the rest stay in Appearance. The
  percentile colours are Savant's and unchanged.
  **The white jersey (Sean, minutes later: "do it kind of like the titans white jerseys where white is the main color, the light blue is
  secondary, and the red is tertiary")**: the `titans` light tokens are white first — ground, surfaces, band and pop `#ffffff`, `surface-2`
  `#f3f6fa`, hairlines `#dde4ed` — with Titans light blue `#4b92db` as `accent`, `accent-2`, `btn` and `tab-fill` (every pressed pill, button
  and active fill, white text on it) and the red `#c8102e` only as the stripe under the band; type stays navy. The warm block's pressed-control
  rules (`.btn.on`, the page pills, `.btab.on`, the Hitters / SP / RP segment …) filled with `var(--ink)` and so stayed navy; they read
  `var(--btn, var(--ink))` / `var(--btn-ink, var(--ground))` now, the same colours on Warm. Dark mode is the navy one above.
* **The less-slop pass (Sean, 6 Oct 2026, from the Less Slop Mock canvas: "Do you have any recommendations for making this look less like AI
  slop", then "go with those recommendations ... keep the current percentile bars and ... make it so the navy blue is the titans light blue")**:
  the block at the end of `styles.css` plus three separator changes in `app.js`. (1) **Labels**: no tracked uppercase anywhere — column names,
  facts, the bars' section names, panel labels are sentence case at normal tracking (column names 12px / 600, fact labels 11px, section names
  15px bold ink in the body face — `.svsecname` included). (2) **Controls**: 4px corners on every button, pill, tab and page number, 6px on
  cards, menus and the popup card (the 999px / 16-24px of the warm pass are gone); the Leaderboard's Hitters / SP / RP is one segmented control
  outlined in light blue, the picked one filled. (3) **Light-blue bands with the red stripe** (`--band2` = `--accent-2`): the site header (nav
  words white, the current page underlined white, the search white-edged), the Leaderboard's column-name row (white names, the sorted one
  underlined in ink; the Result / Process band row is hidden) and the card's band (white name / year / bio / facts, the Filters and Raw buttons
  white-outlined on it). (4) **Rows**: names 15px / 600 in the body face, the team line 12px ink-2, no banding (a hairline between rows),
  numbers right-aligned in tabular figures; the sorted nERA keeps its big condensed colour. (5) **Commas, not interpuncts**: "MIL, SP, RHP" /
  "Age 24, 6-4, 197" on the card (`fillBio`, the `.mline`), "MIL, SP, 174.2 IP" on the rows (the `::before` separators), "SP filters (1)" on a
  phone's button. (6) **Facts** as a six-column grid with hairline dividers on the band. The percentile bars are untouched. Dark mode keeps
  the Titans dark tokens; the bands read `--accent-2` there too.
* **Quieter rows, the bands kept (Sean, 6 Oct 2026: "the font and spacing or lack thereof just feels very busy to me, and also
  please keep the banded rows")**: the less-slop pass's two no-banding rules are gone (the even rows are ink at 4% on the ground again,
  no hairline between rows), and the block at the end of `styles.css` ("quieter rows") calms the Leaderboard's type: names 15px / 500
  (14.5 on a phone) in the body face, the team line one 11.5px muted line ("HOU, DH, OF, 691 PA" — `display: block` with inline children
  and no right margin, so the commas sit tight; it ellipsises instead of wrapping), the numbers 13px / 400 with 10px of right padding,
  the sorted headline 18px / 700, column names 11.5px / 500, the rank muted at 11px, rows 52px on a desktop / 48 on a phone. The
  light-blue bands, the red stripe, the 4px controls and the comma separators of the less-slop pass stay.
* **Names over values, Carolina blue, IP / PA for the rank, two-line names (Sean, 6 Oct 2026: "make it so the column headers are in line
  with the values", "change the blue to a bit of a lighter shade like maybe the unc blue", "get rid of the ranking ... put innings pitched
  there and then have the player column just be their name with their first name on the first row and last name on the second row")**:
  (1) the Leaderboard's column names and value cells are both **centred** with no side padding (the names had been right-aligned against the
  cell's padding while the digits sat centred); the Player name stays left (`.h.left`). (2) The `titans` scheme's blue is **Carolina blue
  `#7bafd4`** in place of Titans' `#4b92db` — accent, accent-2 (the bands), buttons, tab fill, the wash — light and dark; white type on it as
  before, type stays navy. (3) **On the Leaderboard / Recent** (`onePage()`) the line under the name is **"SP · 174.2 IP"** — positions, a thin light middle
  dot (`\00a0\00b7\00a0`, weight 300 at 70%, the Leaderboard-only `::before` at the end of `styles.css`), playing time; the team is the
  name's tooltip (Sean, from his screenshot: "go back to this with the rank and then only have under the player name the position and the
  IP/PA ... like 'SP • 134.1 IP' but make the dot obviously thinner"). Two versions lasted an hour each before it: the rank column replaced by
  his IP / PA with the name split first over last, then on one line — both undone; Rankings / Draft board keep the team first. A sorted-column
  fill Savant's way (every sorted column a full-height coloured cell at the ordinary digit size) was built the same hour and **not shipped** —
  Sean: "scratch that I like how it currently is" (the big coloured headline value).
* **The phone band tightened (Sean, 6 Oct 2026, from Sale's card: "make it so the bottom stats on the header are more spaced out and center
  aligned ... put the raw stuff button next to the filters button and ... move the bottom stats up and make the header's height a bit
  less")**: on a phone Filters ▾ and Raw ▾ sit side by side (84px each) on the year's line, right of the year (`.phctl` absolute at top 28px,
  `.pthd` padded 180px on the right; the bio lines run full width under them), the year block has no minimum height, and the facts row runs
  into the plate's 58px right padding (`margin-right: −46px`) so it spans the band, each fact centred in an equal share — `grid-auto-flow:
  column` with `1fr` auto columns on both layouts, so five hitter facts or six pitcher facts split evenly (a desktop's five had left a blank
  sixth). Band 174 → 165px on a 390px phone. The block at the end of `styles.css`.
* **Filters over Raw in the corner, lower (Sean, 7 Oct 2026: "put the filters button where the raw stuff button is and then put the raw stuff
  button below the filters button and move them both down slightly so they aren't directly hugging the exit button")**: on a phone `.phctl` is a
  column again at the band's right edge (Filters ▾ over Raw ▾, 84px each), 48px down from the plate's top so there is air under the ×; the year /
  bio block keeps 96px of right padding and an 84px minimum height so the facts row clears Raw. The side-by-side row of the entry above is history.
* **The sorted column's name lit, red-ruled, every sorted column bold (Sean, 7 Oct 2026: "make the navy underline on the highlighted column be red
  and maybe make it highlight the whole box of the stat that is being highlighted and bold the text of that stat ... make them all bold just like
  nERA does")**: `#colhead .h[aria-sort]` / `.sorted` is white at 22% on the blue band, bold, with a 3px `--stripe-line` red rule (the ink rule of
  the less-slop pass is overridden); `.pct.hot` / `.score.hot` (and `.sorted`) digits are 700 on both layouts — the quieter-rows 400 had taken the
  bold off every sorted column but the headline. The block at the end of `styles.css`.
* **Filters and Raw: white, black type, a red square outline (Sean, 7 Oct 2026: after a preview with light-blue text, "black text on the white
  button with a red border for raw and filters"; "hard edges not soft")**: the card's two corner buttons on both layouts — `#ffffff` ground,
  `#111111` type at 600, a 1.5px `--stripe-line` red border, no radius (the inner `.segbtn` of the Raw `.seg` has no border of its own). The block
  at the end of `styles.css`.
* **The level picker beside the year on a phone (Sean, 7 Oct 2026, Brandyn Garcia's card: "players who played at multiple levels and show the
  level on the card have it go below the year, make it right next to the year")**: the phone's `.pthd` no longer wraps and carries no right padding
  of its own (the corner buttons start below it; the bio lines keep the 96px), and the level select's `.tsl` is 20px against the year's 27 so
  "2026 ▾ MLB ▾" fits before the buttons at 390px. The block at the end of `styles.css`.
* **The list stays put under a card on a phone (Sean, 7 Oct 2026: "when I'm on the leaderboard and select a player card the leaderboard jumps
  back to the top while I'm on the player card and then when I exit it jumps back to where I was")**: the phone rule that shows the page under a
  popup card (`body.modal-open.cardpop main { display: block }`, undoing the plain modal's `display: none`) had turned the list pages' flex
  standing card into a block, so the rows' box grew to every row (no scroll position to keep) and sprang back on close. Those pages
  (Leaderboard / Recent / Rankings / Draft board / Pitching+ board / Claude rankings / Mock / Planner) keep `main.wrap` as flex under a card
  (the rule right after it in `styles.css`), and `render()` puts the noted list scroll back when a card opens as well as when it closes, so
  nothing moves either way. Headless: the rows' box reads 498 before, under and after a card.
* **A shorter phone band (Sean, 7 Oct 2026: "get rid of the lines that separate the stats at the bottom of the players header ... move that part up
  a bit and clear more header space ... move the raw and filters buttons back up vertically a bit if necessary")**: no rule over the facts row and
  no dividers between the facts, the row 2px under the bio, the corner buttons at 36px from the plate's top, the year / bio block 68px at least,
  8px of bottom padding. Band 182 → 152px on a 390px phone. The block at the end of `styles.css`.
* **The facts' top rule back; Raw / Stuff inside Filters (Sean, 7 Oct 2026: "put back the border on top of the stats we don't need the one in
  between them, and let's move raw vs stuff to the filters buttons")**: the phone's facts row has its hairline over it again (no dividers); the
  corner holds **Filters alone** — `playerHead` no longer builds the Raw ▾ dropdown, it builds a Raw / Stuff `.seg` (`sideSeg`) and puts it at the
  top of the Filters window under a "Raw / Stuff" caption (`.phtwo.phside2`, after a two-way player's Hitting / Pitching switch), the pressed side
  filled with `--btn`. Picking a side still sets `state.cardSide` and re-renders. Both layouts.
* **The filter chips under the Filters button (Sean, 7 Oct 2026, Devers's last-100-PA card: "that filter description box below the filter button
  not where it is now")**: `playerHead` moves the `.mrank` chip row (`.fchip` ×) into the `.phctl` corner under Filters (`.mrank.inctl`,
  right-aligned, the chips white with a red outline like the button) instead of leaving it as a row over the facts; the small `.phview` name
  only shows for a view with no chips. Both layouts.
* **The facts' dividers back; the bio's second line is height · weight · age (Sean, 7 Oct 2026: "make it so the lines in between the stats at the
  bottom come back and get rid of their age saying age just have it be their age and have the age come after height and weight and have a • in
  between")**: the phone's facts have their hairline dividers again (the top rule stayed), and `fillBio`'s second line reads "6-4 · 195 · 36" —
  a thin middle dot between, no "Age" word, the age last. A star removal / age-beside-the-name version was started and withdrawn the same hour.
* **Dots through the whole bio, both lines one size (Sean, 7 Oct 2026: "between any part of the bio that is different have a • between instead of a
  comma. And have the second row be the same size font as the first")**: the card's bio reads "PHI · SP · RHP" over "6-4 · 195 · 36" — `mline`
  and `fillBio` join with a thin middle dot, not a comma (the Leaderboard rows keep their commas), and `.hbio2` inherits the first line's size and
  weight (13px / 500; 12px on a phone). The block at the end of `styles.css`.
* **Filters as a word, not a button (Sean, 7 Oct 2026: "making the filters thing not a button anymore but just it says filters with the arrow in
  white and then brings the drop down box for them")**: the card's corner Filters control is plain white "Filters ▾" text on the band (14px / 600,
  no ground, border or shadow; underlined while the window is open) — the block at the end of `styles.css` on the `.phfiltseg` / `.phfilt`
  rules; the window it opens and the chips under it (white, red outline) are unchanged. Both layouts.
* **No note under the Mix tab's table (Sean, 7 Oct 2026, from Lowe's card: "I don't need all this text here at the bottom")**: `renderMixTab`'s
  "Each bar: where his share …" paragraph is gone; the table and the Mix wOBA row are unchanged.
* **Bigger Filters, Raw ▾ as a word beside it, one bio colour, red card tabs (Sean, 7 Oct 2026: "make the filters word be bigger and also take
  the stuff and raw out of filters and do the same thing with it, also make the rhp and b/t r/l the same color as the other bio stuff";
  "make the bottom page tabs/buttons be red text bold like in the leaderboard red bold text and give it a red outline for the button too")**:
  the corner's Filters ▾ is 17px; **Raw ▾ / Stuff ▾** is a white word under it again (`playerHead`: `.phsidebtn` in a `.seg.phfiltseg.phsideseg`,
  the pick list hung by `ddList` — the Filters window no longer holds a Raw / Stuff segment; the `.phside2` CSS is unused); every part of the
  bio (`.mlinein`, `.hbio.inline`, `.hbio2`) is `--onband-dim` at 400; the card's tab strip (`.btabs .btab`) is white with red (`--stripe-line`)
  bold text and a 1.5px red square outline, the picked tab filled red with white text. The block at the end of `styles.css`.
* **The card's tabs blue (Sean, 7 Oct 2026: "make the tab buttons at the bottom blue with bold white text with a red outline")**: `.btabs .btab` is
  the scheme's light blue (`--accent-2`) with bold white text and the 1.5px red square outline; the picked tab is filled navy (`--ink`) so it still
  reads as picked. The block at the end of `styles.css` (the red-text version of the entry above lasted minutes).
* **Filters 21px, Raw ▾ under it on both layouts, the bio solid white (Sean, 7 Oct 2026: "make it so filters is bigger text and again but the raw
  stuff button below it and then make the bio stuff not translucent white")**: the corner's Filters ▾ is 21px (`!important` — the warm pass's
  14px button rule had held it) over a 16px Raw ▾ (`.phtog` is a right-aligned column on a desktop too), and every bio line is `#ffffff`, not
  `--onband-dim`. The block at the end of `styles.css`.
* **The card's tabs in the lit column name's dress (Sean, 7 Oct 2026, from a crop of the Leaderboard's sorted column name: "make the tab buttons
  look like this but obviously extend the red outline all the way around")**: `.btabs .btab` is the blue band with bold white text and a 3px red
  (`--stripe-line`) outline on every side; the picked tab carries the same 22% white wash the lit column name does (`color-mix`). The navy-picked
  version of the entry above is history. The block at the end of `styles.css`.
* **Raw ▾ at Filters' size; "Age 36 · 6-4 · 195" (Sean, 7 Oct 2026: "for pitchers make the raw button the same size as filters", "put the players
  age before their height and weight and add in the word Age again")**: the corner's Raw ▾ is 21px like Filters ▾, and `fillBio`'s second line
  leads with "Age N" before height · weight.
* **Filters ▾ and Raw ▾ both 16px (Sean, 7 Oct 2026: "make the filters and raw buttons the size that the raw button was prior to me asking you to
  change its size")**: the corner's two words share the 16px Raw ▾ had before PR #440. The block at the end of `styles.css`.
* **The card's tabs plain again (Sean, 7 Oct 2026: "make the bottom buttons at the player page card back to just the navy outline white color with
  navy text and no bold")**: `.btabs .btab` is white with a 1px navy (`--ink`) outline, 4px corners and navy text at weight 400; the picked tab is
  the scheme's light-blue button fill with white text. The weight needed an id-anchored rule (`:is(#modal, #xboard) .btabs .btab`) because the
  warm pass's 600-weight control rule carries `#colhead .h` inside its `:is()`, which gives the whole rule id specificity. The blue / red-outlined
  tabs of the entries above are history. The block at the end of `styles.css`.
* **The sorted column on a desktop is the value in its colour (Sean, 7 Oct 2026: "on desktop version ... the highlighted column shows the stat
  in red and not this heat map thingy", "basically what desktop currently does for nERA")**: every sorted column on a desktop's Leaderboard /
  Recent draws like the nERA headline — a clear ground, the value 19px bold in the condensed face in its percentile colour (`--heat`, which
  `paint()` sets on every cell) — instead of the filled cell with its 8px corners; the phone had this since the warm pass. The block at the end
  of `styles.css`.
* **The frozen Rk / Player header cells opaque again (Sean, 7 Oct 2026, scrolled sideways on a desktop: "Year" slid under "Player")**: the
  light-blue band pass had made every column-name cell transparent, so the sliding names drew through the two sticky ones. They carry the band
  colour (`--band2`) and `z-index: 3` now — the block at the end of `styles.css`.
* **Home, design A (Sean, 7 Oct 2026, from the Home Page Designs canvas — five mocks, three desktop and two phone: "I like design A")**: `renderHome`
  leads with **Last game day** as one full-width card (`.hcard.hlead`, `.hbig` rows: a round headshot, the name 20px in the condensed face, a line of
  what he did that day — team · H-AB · HR · BB · K · barrels · max EV for a hitter, team · IP · ER · K · BB · whiff% for a start — and the value 26px in
  its percentile colour: xwOBA against the season's 300+ PA hitters, Pitching+ against the 100+ IP pitchers' season grades, `heat` → `--heat` + class
  `heat`), five rows a side (four on a phone), then three compact cards in the `.hgrid`: **2026 leaders** (5 by xwOBA over 4 by nERA, stacked),
  **Trending** (last 100 PA / last 50 IP, the same shape) and **2027 starters** (9 rows); the compact lists' values are 17px condensed and coloured the
  same way. The `two()` side-by-side columns are only in the lead card now. CSS at the end of `styles.css`; the lead rows need `grid-area: auto` on
  the name / value because the `.hlist` rules pin `.hval` to a grid area the lead rows don't have.
* **Movers in place of the 2027 starters on home (Sean, 7 Oct 2026: "instead of the Claude rankings could you add the movers thing that you have in
  C")**: the third compact card is **Movers** — the biggest percentile jumps over the last 30 days (`win30`: from = the last game day − 29) against
  the full season; hitters by xwOBA (75+ PA in the window, placed among the window's 75+ PA hitters; the season percentile among the 300+ PA pool),
  pitchers by nERA (20+ IP in the window among the window's 20+ IP pitchers; the season one among 100+ IP), five and four rows sorted by the gain,
  each a "was → now" pair of pills (`.hpill`, the now pill in its percentile colour) with "team · his window number over N PA / IP" under the name
  (`.hmovers`); "Leaderboard →" opens the Leaderboard on that window. The 2027 starters card is gone from home (the Claude rankings page is still
  under Fantasy). The card waits for days.js like Trending does.
* **Every home list in the lead card's dress, four a list (Sean, 7 Oct 2026: "make all of the tables in this format where it shows the player
  headshot", "show the top 4 for each, instead of the current 5 for hitters one and 3 for pitchers")**: `list()` and the Movers' `mlist` build
  `.hbig` rows like the lead card's — headshot, the name in the condensed face, team (and the window line) under it, the value or the "was → now"
  pills at the right — so no `.hlist` is drawn on home any more (its CSS stays); `NH = NP = 4` for the leaders, Trending and Movers (the lead card
  keeps five / four). CSS at the end of `styles.css`.
* **The band tidied, the star feature off the site (Sean, 7 Oct 2026, from Reynolds's card: "5 is good with me and 3 and 4 as well and also get rid
  of the star feature across the site that's not needed anymore")**: the filter chip under Filters is quiet — white, a thin `--onband-line` edge, ink
  text, a muted × (`.phctl .mrank.inctl .fchip`); on a phone Filters ▾ / Raw ▾ sit level with the × (`.phctl` at `top: 8px; right: 52px`, the × at
  8px / 8px) and the headshot is 60px (was 74); **no stars** — `playerHead` removes the card's ☆ / ★, the lists draw no row star, `#rankstars` /
  `#draftstars` are hidden with `state.starOnly` false, the Weekly Planner is always Everyone (its Starred / Everyone pill is gone, `pw.scope` forced
  to `all`), and `.staricon` / `.rowstar` are `display: none`. `state.stars` and `SYNC_KEYS`' `stars` stay (saved data, harmless). The block at the end
  of `styles.css`.
* **The Pitching+ board in the Leaderboard's dress (Sean, 7 Oct 2026: "make the pitching+ table look exactly like the leaderboards one")**: the
  block at the end of `styles.css`, every selector anchored on `#pitchboard` (the warm pass's `:is()` rules carry `#colhead` / `#bscroll`, so a
  class-only rule loses to them whatever its root count): the column names on the blue band (`--band2`, white, 11.5px / 500, 40px tall) with the
  sorted one lit (white at 22%, bold, the 3px red rule) like `#colhead`; rows 52px (48 on a phone) banded ink-at-4% on the ground with no cell
  rules, no frame or radius round the rows' box, no divider after the sticky Pitcher column; names 15px / 500 in the body face over the muted
  "PHI · RP · LHP" line; numbers 13px / 400 tabular; the **sorted + column** draws like a Leaderboard's sorted column — the value 19px bold
  condensed in its percentile colour on a clear ground (`plus()` in `renderPitchBoard` gives the sorted cell class `hot` and `--heat` instead
  of a fill; "Colour: all" still fills the other + cells), and `td.plus` loses the softer-edges 8px radius there (it had turned the banded cells
  into pills).
* **The Pitching+ model's five fixes (Sean, 7 Oct 2026, after "are there any improvements that can be made to the pitching+ model": "Ok do all
  of that"; scratch `pmodel.js` on the season files 2020-26)**: (1) **the season's level** — the fixed models have no season input and read a whole
  year hot or cold (2026 +2.1 whiff points / +1.6 GB even trained through it, 2020-21 −1.1): `xLevel()` in `app.js` is the league's actual −
  expected gap per dataset on the same pitches (20+ BF pitchers' arsenal rows, swing- / ball-in-play- / contact-weighted, 2,000+ needed; both
  families, GB / PU and the foul chance too), and `pitchRates` / `stuffRates` / `foulChance` are wrappers that put it on the raw sums
  (`pitchRatesRaw` …), `xAdj(r)` puts it on an arsenal row — the board, the Pitching+ tab's rows and `seasonPitches` go through it — so every
  expected rate shown, and everything downstream (nwhf / ngb / npu / nmix / xks / xnERA / xStrikeout / the Stuff side of the card), sits on the
  season's actual league; the grades (Pitching+ / Stuff+ / Location+) cancel the level by construction and don't move. Wheeler 2026 xWhiff 30.7 →
  28.7 against 30.9. The build side: `stuff_features` now carries **`season`** (year − 2020) and **`relsd`** (release-point spread per pitcher ×
  season × pitch type, feet) in every model, so after the next retrain the level follows the year itself (an unseen season scores at the last
  one's). (2) **Location+ shrunk by pitches** — per pitch, `LOC_K` 70: the location delta × n / (n + 70) in `xAdj` (and the board / tab / season
  rows), since a pitch's Pitching+ repeated year to year at r .66 on 5-50 pitches against Stuff+'s .89 (the spots were the noise; .92 at 400+);
  the pitcher's grade is untouched. Alvarado's cutter (365) Loc+ 114 → 112. (3) **The fair whiff gap** — `wgap` (Whiff vs exp., a column again
  via `LB_EXTRA_P`) is his Whiff% minus the expected rate stretched to the real spread (`sorted.calP`'s centre and ratio — expected sd was 0.80
  of actual every season, so the top whiff pitchers always read "over"); `xe(i)` in the pool's PK block, `xe0` in `statsFor`. (4) **A blended
  forecast** — **`pjwhf`** Proj. Whiff% = the average of his actual and that stretched expected rate (next season r .76-.81 vs .74-.76 for
  either alone, 2021-26 pairs): `NEXT_KEYS`, `SIDE_P`, `LB_EXTRA_P`, `SHORT`, glossary. (5) **New inputs for the next retrain** — besides
  `season` / `relsd`, `seq_features` → `STUFF_SEQ` (`pv_same`, `pv_dvelo`, `pv_dloc`: the pitch before in the plate appearance — same type, the
  velo gap, how far the spot moved) in the **location family only** (`lcols` / `lbcols`: whiff_loc, bb_loc, foul_loc; Stuff+ stays the pitch
  alone); `pitch_number` joins `COLS`, `game_pk` / `at_bat_number` / `pitch_number` join `STUFF_TRAIN`; NaN on a PA's first pitch or a frame
  without the numbering (the minors). Catcher framing was left out — the catcher's id isn't in the frames. The whole training path was run on a
  synthetic 16,000-pitch frame here (scratch `synth_train.py`): every model trains with the new columns and a frame without `pitch_number`
  still scores. **Needs Actions → Train Stuff+ models with `through=2026`** then the rescore it runs — dispatched after the 2020-25 rescore of
  the same day (which carries the per-pitch `cstr` / `xcstr` to past seasons for the xCalled pairs). Until it lands the app-side four are live
  and the models are the 6 Oct ones.
* **EV by batted-ball type; FB% and LD% in Air%'s place (Sean, 7 Oct 2026: "in batted ball quality could we add a percentile bar that shows avg
  ev on fly balls, avg ev on line drives, and avg ev on gbs", "in batted ball distribution replace air % with two bars one for fly ball % and one
  for line drive %"; asked with Aranda in mind — "did arandas ev by batted ball type change at all? or did he just get lucky and hit a ton of LDs
  last year")**: **build** — `pitch_flags` splits the EV-eligible balls (tracked, no bunt) by the stringer's type into `evfbs / evfbn / evlds /
  evldn / evgbs / evgbn` (sums and counts), `hitter_metrics` → `EV_FB / EV_LD / EV_GB`, `HITTER_METRICS` **`evfb / evld / evgb`** ("EV on FB / LD /
  GB", so they're Leaderboard columns too), `HITTER_CARD`'s Batted-ball quality group carries them after Avg EV, and the six sums are appended to
  `HITTER_DAY` (the day aggregation guards a frame without the flags; `pack` keeps the sums' decimals) so a window / split re-derives them. **App** —
  `V()` re-derives `evfb / evld / evgb` from the day sums (null on a file built before them); `PCT_COLS_H` Batted-Ball Quality = Avg EV · **EV on
  FB · EV on LD · EV on GB** · Barrel% · Bat Speed · Hard-Hit% · 90th% EV · Max EV, and Batted-Ball Distribution = **FB% · LD%** · Popup% · GB% ·
  Pull Air% · Mix wOBA — `BB_DIST` (the group the app draws "everywhere", which is also what puts the keys in the pool's metric list: the Air%
  fold-out that had held FB% / LD% is deleted at load, so without this the two rows silently drew nothing) is FB% / LD% / Popup% / GB% / Pull Air%;
  Air% stays a Leaderboard column; labels (`OUTCOME_LABEL`, `SHORT`), glossary (`evfb / evld / evgb / fb / ld`), `NEEDS_EV`. Until a build
  carries the sums the three EV rows don't draw (a key with no value is skipped) — a `steps=mlb` run was dispatched after the merge for 2026,
  past seasons at the next rescore. **Why LD% is the noise** (scratch `aranda.js`, 300+ PA hitters, consecutive seasons 2021-26, n 994): year to year
  LD% r .33 against FB% .72, GB% .74, Avg EV .78, EV90 .89, Brl% .79, HH% .80, BABIP .39, wOBA .46; the top-20 LD% hitters each season drop ~3.5-4.5
  LD points the next year (29.5 → 26 against a 24 league) and ~.02 of wOBA. Aranda: 2025 LD% 30.5 (99th), BABIP .409 / xBABIP .382, wOBA .386, EV
  93.0 (94th), HH% 54.1 (96th), EV90 106.9; 2026 LD% 27.5 (still 92nd), BABIP .340 / xBABIP .323, wOBA .349, EV 91.1 (84th), HH% 45.9 (80th),
  EV90 104.0 (47th) — the line-drive rate came down as it does, and the contact itself got softer with it. EV by type for 2025 needs the rescore.
* **EV allowed by batted-ball type on the pitcher card (Sean, 7 Oct 2026: "Can you add the gb fb and LD exit velo to the batted ball section")**:
  the hitters' EV on FB / LD / GB from the pitcher's side. **Build**: `pitch_flags`' six sums serve both sides; `pitcher_metrics` → `EV_FB /
  EV_LD / EV_GB` (nan on a frame without the flags); `build_pitchers` → `m.evfb / evld / evgb` (a column the frame lacks reads None);
  `PITCHER_CARD`'s Batted ball group carries the three (lower is better for a pitcher — the defs ride in `meta.pitcherCard`, so the card needs
  the new `data.js` before the rows draw); `PITCHER_DAY` gains `evfbs evfbn evlds evldn evgbs evgbn` (appended, the day agg guarded) so a window /
  split re-derives them. **App**: the pitcher `V()` branch re-derives the three from the day sums (null on a file built before them);
  `PCT_COLS_P` Batted Ball = GB% · Popup% · Mix wOBA · **EV on GB · EV on FB · EV on LD**, and `PCT_COLS_PS` the same three actual rows after
  xGB% / xPU% / Mix xwOBA (no model prices exit velocity, so the Stuff side shows his own, like Command's strike rates); the glossary entries read on
  both sides. Checked on a synthetic Statcast frame through `pitch_flags` → `pitcher_metrics` → `daily` → `build_pitchers` (scratch `synth_pev.py`:
  the day rows re-derive the season numbers, a frame without the flags still builds) and headless on Wheeler's card with a hand-patched `data.js`
  (both sides draw the rows; a window drops them without error until `days.js` carries the sums). `steps=mlb` dispatched after the merge; past
  seasons at the next rescore. The card's right column runs 10 rows to the left's 7 now.
* **EV by batted-ball type moves to the Mix tab; Air% back; the Mix tab is a table (Sean, 8 Oct 2026: "go back to not having avg ev by batted
  ball type and also just have air % / But in the batted ball mix section let's add those in there / make the batted ball mix tab be a table where it
  shows the batted ball types in the way it does now and sorts them or orders them by wOBA and then have the players percentage of batted balls that
  are that type in one column and then their avg EV in another and for each of them have them be heat mapped but don't do like a circle one just make
  the text bolded and heat mapped color wise")**: the two card entries above are history on the cards — `PCT_COLS_H` Batted-Ball Quality is Avg EV ·
  Barrel% · Bat Speed · Hard-Hit% · 90th% EV · Max EV and Distribution is Air% · Popup% · GB% · Pull Air% · Mix wOBA again (`BB_DIST` and the build's
  `HITTER_CARD` groups as before 7 Oct), and the pitcher card's Batted Ball is GB% · Popup% · Mix wOBA (`PCT_COLS_P` / `_PS`); `evfb / evld / evgb`
  stay built and stay Leaderboard columns on both sides (`HITTER_METRICS`, `PITCHER_CARD`'s Batted ball group). **The Mix tab** (`renderMixTab`) is a
  table in the card-table dress (`table.ubt.mixt`; CSS at the end of `styles.css`): a row per bucket, dearest first — Lg wOBA (the dataset's value
  for that kind of ball), **Share** (his balls in play in it) and **Avg EV** (his exit velocity on them) — the share and the EV in bold type coloured
  by his percentile among the pool's qualifiers (`pctStyle(pct).bg` as the text colour, no chips, bars or bubbles; the share's direction by the
  bucket's value against the league's per-ball wOBA, as the bars had it; EV higher = better; an EV on under 5 balls stays uncoloured, the pool's
  reference needs 20), then the Mix wOBA foot row (value coloured by its percentile, the ordinal beside it). **Build**: `pitch_flags` gives every
  ball its Mix bucket as a code (`mixc`, the `MIX_COLS` index, −1 outside the mix), `hitter_metrics` → `MXS<i> / MXN<i>` (EV sum and tracked
  balls per bucket), `build_hitters` → **`ctx.mixev`** = `[[n, avg EV] | null]` in `MIX_COLS` order, and `HITTER_DAY` gains **`evbk`** — a list
  beside `evs` with each exit velocity's bucket (~0.5 MB on days.js, against 16 sum fields at ~5 MB) — so `V()` re-derives `ctx.mixev` in a window or
  split (`hasBk`; the sums skip the list field, as does `build_trends.py`). A file built before it reads "–" in the EV column (a window on this
  season until the next build, past seasons until a rescore). Checked on a synthetic frame (scratch `synth_mix.py`: the day rows re-derive
  `ctx.mixev`, a frame without `mixc` still builds) and headless on Aranda's card with a hand-patched `data.js` (scratch `patch_mixev.py` / `mix.js`:
  the table, the colours, the window's "–", Wheeler's three Batted Ball rows). `steps=mlb` dispatched after the merge. The 7 Oct Savant pull for
  Aranda stands (2025 EV on LD 96.5 / FB 94.3 / GB 91.0; 2026 95.8 / 92.6 / 86.7).
* **The bars Mix tab back, with Avg EV by type under it (Sean, 8 Oct 2026, an hour later: "go back to the prior percentile bar batted ball mix
  table / And then below it can you just show avg ev by FB LD and GB")**: `renderMixTab` is the grid of the day before again (bucket · percentile
  bar · share · Lg wOBA chip, dearest first, the Mix wOBA line) and under a divider an **Avg EV** block — Fly balls · Line drives · Ground balls,
  each his percentile bar among the pool's qualifiers (`st.pct.evfb / evld / evgb`, else placed among `pl.ref`), his EV and the league's mean
  (`.mv.lg`) — from `m.evfb / evld / evgb` (a window or split re-derives them from the day sums; no block on a file built before 7 Oct 2026).
  The table of PR #453 and its CSS are gone; its build side (`mixc`, `ctx.mixev`, the day rows' `evbk` list, ~0.5 MB) stays built and unread —
  strip it at a future trim of `days.js`. Aranda 2026: FB 92.6 (54th) · LD 95.8 (79th) · GB 86.7 (62nd) against 92.1 / 93.9 / 86.0.
* **His page from the lists; the Baseball-Reference band and season table (Sean, 8 Oct 2026, from the Player Page Designs canvas — "that is perfect
  implement that", "make it so the bottom tabs at each player card page are still there at the bottom")**: a name on the Leaderboard / Recent, Rankings,
  the Draft board, the Pitching+ board, Fantasy, home and the Claude rankings goes to **his page** (`openPlayer(p, { ds, win, split, tab })` →
  `#player/<id>`, the list's window and split carried over) instead of popping a card up; `markBack()` notes the list page, its scroll and its rows'
  box, and the page's **‹ Back to leaderboard** button (`goBack`; `backRestore` is read at the end of `render()`) puts the list back exactly as it was
  left. The page (`playerView` with `page: true`, drawn straight into `#xboard` — no modal, no frame; `showPageCard` is unused) is **`pageHead`**: the
  site's band full width with B-Ref's bio — the photo in a tile, the name, Position(s) (`POS_WORD`), Bats • Throws (only the hands the data knows),
  height and weight with the metric in brackets, Born with the age (MLB's record carries `born / city / debut / full / nick` now; `bio()` sets `false`
  when the fetch fails, so the page stops saying Loading), Team (a link that filters the Leaderboard by his team), a **More bio, draft info ▾** fold
  (full name, nickname, birthplace, drafted, debut; `bioMore`), the controls on the band's top line (Back, the season picker, Filters ▾ / Raw ▾ —
  `filtersTog` / `filtersWindow`, pulled out of `playerHead` so both bands share them; the window hangs under whichever Filters button is on screen —
  and the filter chips, `viewChips`), and the **Summary** line at the band's foot (`summaryBlock`: this season and his career — hitters wOBA · xwOBA |
  PA · AB · H · HR | R · RBI · SB | BA · OBP · SLG · OPS, pitchers nERA · ERA | W · L · G · GS · IP | H · HR · BB · K | WHIP · K% · BB% · K-BB%; the band
  says the full season whatever the card's filters; a phone drops the `.pbx` columns; a career nERA isn't built, so it reads "–"). Then
  **`seasonBlock`**, B-Ref's Standard batting / pitching table in the site's dress (`.sbt`: gridlines, the column names on the light-blue band, Season /
  Age / Team frozen at the left with a heavier rule, the current season tinted, **bold = his career best in that column** (100+ PA / BF seasons — the
  site has no league leaders or All-Star flags, so not B-Ref's bold / ★), the totals N Yrs · 162 Game Avg (a pitcher's per 162 team games, 60 for 2020)
  · each club (a traded year's clubs from career.js's HT / PT rows) · each league (`AL_TEAMS`) in grey-banded groups; an **In Split** row under the
  current season when a date filter or split is on — the official line from the fantasy game logs (`fViewLine`) with the view's wOBA / xwOBA (pitchers:
  FIP, Whiff%, Strike%, GB% from `V(p).m`); **Show minors** interleaves the minor-league lines with a Lev column (`sbMinors`); a phone shows the last
  three seasons until **All N seasons ▾** (`sbAll`, sticky inside the wide cell); Glossary opens the glossary), the percentile bars (`.ppage.pageflow`,
  natural height, the page's width) and the tabs (`BTABS` is Fantasy alone — Season Stats is the table now — and the strip opens closed). **A phone's
  band condenses** once scrolled (`condensedBar` → `.phcond`, a fixed bar `condSync` shows while `.pagehead` is off the top; the site header is static
  on a phone's player page): Back · the year · Filters ▾, the name, position • bats • throws, this season's wOBA · xwOBA · BA · OBP · SLG · OPS
  (pitchers nERA · ERA · K% · BB% · K-BB%). `hist/career.js` carries the **directional xwOBA** per season now (`build_career.py` writes `xwoba_dir`;
  the file was patched in place the same day — 7,367 rows). Still popups: the Mock Draft room and the Pitching+ board's spring cards (`renderModal`).
  Not built (B-Ref has them): the Postseason switch over the table and the Standard / Advanced column-set pills — per-season site stats beyond what
  career.js carries would need the season files. CSS: the block at the end of `styles.css` (six roots, over every earlier pass).
* **Back only from a list (Sean, 8 Oct 2026, from Eldridge's page after a search: "could you get rid of the home button ... i just want the back to the
  leaderboard button if i selected the player while on a leaderboard page")**: `markBack()` notes a list page only (`BACK_MODES`: Leaderboard / Recent,
  Rankings, Draft board, Pitching+ board, Fantasy, Claude rankings, Planner, Eligibility) and clears `backAt` otherwise; the header search clears it too,
  and `backButton` draws nothing without one — no "‹ Home" on a searched page or one opened from home.
* **EV by batted-ball type vs xwOBAcon (Sean, 8 Oct 2026: "which one correlates best with xWOBACON")**: 300+ PA hitter-seasons 2023-26 (1,123; the
  seasons that carry `evfb / evld / evgb`), xwOBAcon = (xwOBA × PA − wBB × BB) / BBE: **EV on fly balls r .775** (next season's xwOBAcon .660), Avg EV .687
  (.577), EV on line drives .581 (.537), EV on ground balls .247 (.209); EV90 .716, Hard-Hit% .725, Barrel% .865. The three together add nothing over FB
  EV alone (R² .600 → .602); FB EV repeats year to year at r .755 (LD .683, GB .652, Avg EV .787).
* **The desktop's condensed band, the bars at their old width, no controls row without a Back (Sean, 8 Oct 2026: "i want the desktop version to
  have the same condensed header when i scroll down", "the percentile bars got longer than they were prior to this change, can you revert them back
  to the same size", "now that you got rid of the home button this blank space is not needed. Keep it for when the back to the leaderboard is
  needed but thats it")**: `condensedBar` draws on both layouts — a desktop's is one row (`.phcond.desk`: Back, the name over the position line,
  the season's six tiles, the year and Filters / Raw at the right) pinned under the sticky site header (`condSync` sets its `top` from
  `header.top`'s bottom; z-index 15 so the nav menus open over it), a phone's is the three-line bar as before at the top of the screen;
  `condAsk` runs on scroll and resize, and `playerView` calls `condSync()` right after appending the bar so a Filters window opened from the bar
  finds it shown — `place` hangs the window under the whole bar (`bt.closest(".phcond")`), not the button inside it. **The bars' box is the popup
  card's 860px again**, centred (`#xboard .ppage.pageflow { width: min(100%, var(--pbox-w)) }` — the full-width page had stretched each chart
  from 406 to 547px at 1300 wide). **No Back → no row**: `pageHead` gives the plate `nobk` when `backAt` is null on a desktop, and the controls
  (the year, Filters / Raw, the filter chips) sit absolutely in the band's top-right corner over its empty side, the photo and bio starting at the
  top (band 367 → 321px); a phone keeps the row, since its year and Filters are the row's two ends, now one line (the popup era's 96px right
  padding and 68px minimum on `.ptitle.pinline` are cleared under `.pbctl`). **A page opened from anywhere starts at the top**: `render()` scrolls
  to 0 when the player page's key (`state.x` type + id + ds, `pageKey`) differs from the last render's, not only on `pageOpened` — the search,
  a Similar name and the boards set the hash directly, and a page opened while scrolled down (the page used to be a popup) opened scrolled.
  **The Summary's first pair heat-mapped** (Sean, the same hour, from a crop of the Mix tab's Lg wOBA chips: "heat map these two like this"): wOBA
  and xwOBA (a pitcher's nERA, and xnERA on the Stuff side) on both the season and the Career rows are `.uchip.pbchip` pills — `paintBar` in the
  percentile colour among the **full season's** pool (`full(() => pool(g))`, `insertPct` on `pl.sorted.woba / xwd / nera / xnera`; the career value
  placed in the same pool, so a career .318 reads 43rd among this season's 300+ PA hitters), white digits with the Mix tab's faint shadow, the
  ordinal in the tooltip; a career nERA isn't built, so that cell stays "–".
* **EV on fly balls in Avg EV's place on the hitter bars (Sean, 8 Oct 2026: "on the hitter percentile bars then can we swap avg ev with fly ball
  ev")**: `PCT_COLS_H` Batted-Ball Quality = **EV on FB** · Barrel% · Bat Speed · Hard-Hit% · 90th% EV · Max EV (`evfb`, ranked by the pool since
  `meta.hitterMetrics` carries it; a file built before 7 Oct 2026 has no value, so the row is skipped there). Avg EV stays a Leaderboard column
  and in the build's card group; LD / GB EV stay on the Mix tab. The pick follows the finding above: FB EV tracks xwOBAcon at r .78 against Avg
  EV's .69 and repeats year to year nearly as well (.76 vs .79).
* **The condensed bar: a Career row, the pills, position codes (Sean, 8 Oct 2026, from Kurtz's desktop bar: "add one more row and have it be their
  career stats, and then heat map the woba and xwoba here", "make their position be the labels of like 1B, OF, DH, 2B, SS, etc")**: `condensedBar`'s
  tiles are the Summary block's own cells — a row-label tile first (the year over "Career", `.pctile.lab`), then per stat the label, the season's
  value and his career's (`.pcc`), the wOBA / xwOBA (nERA / xnERA) pills cloned over as `.pcchip` (a career nERA isn't built, so that cell is "–");
  every value row a fixed height (22px desktop / 18px phone) so pills and plain numbers line up; `.pctiles.two` adds the label column. The position
  line reads the codes (`playedLabel`: "DH, 1B • Bats: Left"), not the words. Both layouts; the desktop bar ~60 → ~82px, the phone's 141 → ~160.
* **The season table at B-Ref's dimensions, a Playoffs tab, the club rows folded (Sean, 8 Oct 2026, beside Trout's B-Ref page: "make it so the
  table fits on the entire page easily like this baseball reference one does ... the same dimensions as theirs does cause i like how theirs fits
  cleanly", "add in the postseason and regular season ability thing", "for the bottom of our table could you make only the career and 162 game avg
  ones show and then make the others show with a drop down arrow")**: `.sbt` is its own width (`width: auto`, the `.sbscroll` frame `max-content`
  hugging it, a phone's still the screen's width and scrolling), 13px cells 5px of padding wide and 28px tall, 12.5px column names 30px tall — the
  block at the end of `styles.css`. **Regular Season / Playoffs** (`sbKind`, `.sbtabs` / `.sbtab` on the table's top edge): the Playoffs view reads
  **`postLines(p)`** — MLB's official postseason lines fetched in the browser like the bio (`people/<id>/stats?stats=yearByYear&gameType=P&group=
  hitting|pitching`, `PSTATS` by type+id: null while loading, false on a failure, a traded October's clubs combined as TOT through `sbCombine`;
  `TEAM_BY_ID` inverts `TEAM_ID` for the codes) — the official columns only (no wOBA / xwOBA, FIP or the site's rates), an N Yrs row, no 162-game
  average, club rows, In Split row, bolding or minors; "Loading his postseason games…" / "No postseason games." / "Couldn't load…" notes. **The
  fold** (`sbMore`, `tr.sbmore`): under 162 Game Avg a "▸ By team and league" row; the per-club and per-league rows (and their grey gaps) draw only
  once it's opened. Headless with the Stats API mocked; the live call works like `bio()`'s (same host, CORS open).
* **The season table boxy like B-Ref, the column names centred, the totals rows on the band (Sean, 8 Oct 2026: "can you make it boxy like
  baseball reference and also center each column header and make the bottom totals rows blue as well")**: the block at the end of `styles.css` —
  the `.sbscroll` frame and the Regular Season / Playoffs tabs have square corners and a firmer edge (ink at 22%), the gridlines are ink at 16%,
  every column name is centred (Season / Age / Team included — `th.l` too), the frozen Team column ends in a 2px ink rule, and every totals row
  (`tr.tot`: N Yrs, 162 Game Avg, and the club / league rows under the fold) sits on the light-blue band (`--band2`) in bold white type with
  white separators, a 2px ink rule over the first; the grey gap rows are 6px of surface. Both layouts.
* **A phone's tabs in B-Ref's dress, every season on a phone, a Pos column (Sean, 8 Oct 2026, beside Trout's B-Ref page: "make the regular
  season and playoff button look like this", "get rid of the show all 8 seasons thing just make it show all seasons by default", "add a column
  to the end that shows all the positions they played that year")**: the phone's Regular Season / Playoffs tabs are a full-width strip in the
  table's frame (surface-2, the picked tab a 44px block in the button blue with white 16px type, the other plain words — the block at the end
  of `styles.css`); a phone lists every season (`sbAll`, the "All N seasons ▾" row and the `tr.sball` rules are gone); and the table ends in
  **Pos** — a hitter's every position that season, most games first, the games in the tooltip (OF for LF / CF / RF, DH included), a pitcher's
  SP / RP by his starts and relief outings (`posOf`; the totals and In Split rows blank, "–" where nothing is known). **Build**:
  `build_career.py` hydrates the API's `fielding` group too — `mlb_positions` turns its yearByYear rows into "OF:97,3B:45,DH:4,2B:3" per
  season (a traded year has a row per club per position and a combined row only for a position he played with both clubs: the combined row
  wins, the clubs' rows are summed otherwise) and appends it to every hitting row **after our numbers**; `minors()` fetches fielding with the
  minors lines, `minors_positions` keys them by season / level / club, `with_adv` appends them to the minors' hitting rows, and a per-player
  cache without the field is fetched once more. `rawLines` reads a row by **fixed index** now (season, team, the keys, two extra counts, our
  numbers, positions), so a field appended at the end moves nothing; `postLines` asks for `hitting,fielding` and folds the October positions
  the same way. Both files were patched in place the same day (scratch `patch_pos.py`: 17,039 of 17,073 MLB hitting rows and 51,112 of
  67,528 minors rows — the rest are pitchers' batting lines or seasons with no games in the field; career.js 3.3 → 3.5 MB, minors.js
  13.9 → 14.6 MB).
* **The hitters' season table is FanGraphs' dashboard (Sean, 8 Oct 2026, from Ohtani's FanGraphs table: "make it so these are the stats that the
  table shows, and include the line breaks as well")**: `SB_H` = G · PA · HR · R · RBI · SB | BB% · K% · ISO · BABIP | AVG · OBP · SLG · wOBA · xwOBA ·
  wRC+ | BsR | Off · Def · WAR, then Pos — a 2px rule after each group (`SB_BRK`, the group's last column `.ge`; the block at the end of `styles.css`).
  BB% / K% / ISO / BABIP come from the official counts (`sbVal`; the 162 Game Avg row takes its rates from the unscaled total, `l.rc`). **wRC+, BsR,
  Off, Def, WAR are FanGraphs' own**, served by MLB's Stats API `sabermetrics` stat (Off = batting + baseRunning, Def = fielding + positional; Ohtani
  2024 179 / 9.8 / 79.2 / −17.2 / 8.9, FanGraphs to the tenth — a few older seasons sit a tenth or a wRC+ point off FanGraphs' current page).
  `build_career.py` fetches one league-wide request per season (`sabr_season`, `stats?stats=sabermetrics&group=hitting&season=Y&playerPool=ALL`)
  and, for each traded season, the player's own split by club (`sabr_clubs`), cached in `.cache/sabr/` with the current season refetched every run;
  it appends `[wRC+, BsR, Off, Def, WAR, wOBA]` to every hitting row after the positions and to every `HT` club row. `rawLines` / the club parse
  read it as `c.sab`; `sbCombine` sums the runs and WAR and PA-weights wRC+ (a piece with PA but no numbers blanks the total). **wOBA** is the
  site's where the season is built, FanGraphs' before 2015 (`sbWoba`). Playoffs, minors and In Split rows show "–" for the FanGraphs five (the
  Playoffs view drops them). `hist/career.js` patched in place the same day (scratch `patch_sab.py`: every hitting row, all 2,677 club rows;
  3.5 → ~4 MB). Pitchers' table unchanged. Same hour: **Avg EV back on the hitter bars** in EV on FB's place (Sean: "swap fb EV with regular avg EV").
* **fWAR / bWAR first, wOBA / xwOBA and Sprint heat-mapped, HR/FB, % signs; the overnight build's stale checkout (Sean, 8 Oct 2026: "get rid of
  off and def and bsr ... war first ... label it as fWAR and then add in baseball references war ... bWAR", "put wOBA and xwOBA first and heat
  map them", "before babip and after iso ... hr/fb", "sprint speed where bsr was and heat map it ... stolen bases ... after sprint speed", "make
  the line breaks extend to the headers too", "for walk and k percentages ... add in the %")**: `SB_H` = fWAR | bWAR | wOBA xwOBA | G PA HR R RBI
  | BB% K% ISO HR/FB BABIP | AVG OBP SLG wRC+ | Sprint SB | Pos (WAR first and wOBA / xwOBA right after it, each its own group, since both were
  asked to lead); Off / Def / BsR are gone (still in `sab`). **wOBA, xwOBA and Sprint are pills** (`.sbchip`, `paintBar`) placed among that
  season's qualified hitters (300+ PA, 110 in 2020) from the career record (`sbPool(y)`); the totals rows among every qualified season 2015 on
  (`sbPool(0)`). Every rate in the season table (both sides) prints its % sign (`sbFmt`). The group rules run through the blue header and the
  totals rows in the ink. **Build**: `build_career.py` appends `[bWAR, sprint speed, fly balls]` to every hitting row after `sab` (index 23) and
  every `HT` club row (index 21) — bWAR from Baseball-Reference's `war_daily_bat.txt` summed per stint (`bref_war`, cached a day, `BREF_TEAM` maps
  its club codes; if it can't be fetched the last career.js's numbers carry over), sprint speed from our season files' `m.spd`, fly balls +
  popups from MLB's `yearByYearAdvanced` (hydrated with the people call; HR/FB = HR / that, so a sum reads right — a few points above FanGraphs'
  BIS-counted HR/FB). `sbCombine` adds bWAR and fly balls and PA-weights sprint; the 162 Game Avg scales bWAR. The Playoffs view drops fWAR /
  bWAR / wRC+ / Sprint / HR/FB. **The Summary's career wOBA / xwOBA had read `sab` (153.747 / 2.745)**: `summaryBlock` read the row's last
  field, which stopped being our numbers once fields were appended; it reads the fixed index (`2 + RAW_H.length + 2`) now. **And the overnight
  cloud build (a9a3e6e) ran the pre-#462 `build_career.py`** — its checkout predated the merge — and rewrote career.js / minors.js without the
  positions or the FanGraphs numbers, which is why wRC+ and WAR went blank on the live site; both files were patched back (scratch
  `patch_ext.py`: positions and `sab` from PR #463's files, 2026 refetched, then the new field: bWAR 17,057 of 17,073 rows, every 2015+
  qualified season's sprint speed, fly balls on every row). The next daily run uses the new script.
* **OPS in the table, the WARs after SB; the cloud build's guard (Sean, 8 Oct 2026: "add ops after slg and before wrc+ and also put both fwar and bwar
  after sb and only have a line break before fWAR and one after bWAR not in between the two", "yeah add the guard to the cloud build")**: `SB_H` = wOBA
  xwOBA | G PA HR R RBI | BB% K% ISO HR/FB BABIP | AVG OBP SLG OPS wRC+ | Sprint SB | fWAR bWAR | Pos (the Playoffs view: … | AVG OBP SLG OPS | SB |
  Pos). The guard is in §1: `adopt_main_tools` / `RAN` / `DEPS` in `tools/cloud_daily.py`, tested on a scratch repo (a step built with V1 of a
  script, V2 merged before the publish → the step re-ran with V2 and main got V2's output).
* **The season table's heat map fills the cell (Sean, 8 Oct 2026: "switch it over so the heat map is just the fill color of the entire cell and not
  this like circle thing")**: wOBA / xwOBA / Sprint cells are painted whole (`td.sbheat`, `pctStyle`'s fill and ink set `!important` inline so the
  totals rows' band colour gives way), bold; the `.sbchip` pills and their CSS are gone. The percentile is the cell's tooltip.
* **The condensed bar takes over from the Summary block (Sean, 8 Oct 2026: "the condensed version of the header shows up once i get to this
  point of scrolling ... so that the header doesn't show up over the table ... make it so the header is the same height as that part too ...
  desktop as well as mobile")**: `condSync` shows `.phcond` once the band's Summary block (`.pbsum`) reaches the top — its top at the sticky site
  header's bottom on a desktop, the screen's top on a phone — instead of once the whole band is gone, and sets the bar's height to the Summary
  block's top → the band's foot (desktop ~105px, phone ~91), so the bar's bottom lands where the band's was and never covers the table. A phone's
  bar is one line — ‹ Back (when there's a list), the name, the year, Filters — over the season / career tiles (the position line is dropped
  there; a desktop keeps it under the name). CSS: the block at the end of `styles.css`.
* **A phone's player band tidied (Sean, 8 Oct 2026, from Jo Adell's page: "make the positions just be the abbreviations and then put the filters and
  year on the right side and then get rid of that top space ... fix the head shot and the wOBA and xwoba glitches")**: on a phone the bio's position
  line reads the codes (`playedLabel`: "Positions: OF, DH"; a desktop keeps the words); with no Back the controls row is gone — `pageHead` gives the
  plate `nobkm` and puts `.pbctl` (the year over Filters, a pitcher's Raw ▾ under that) floated right at the top of `.pbtext`, which is block flow
  there so the name and bio wrap round it; the headshot fills its 96 × 128 tile (a 10-root phone card rule had held every band `.mug` at 60px, so
  the photo sat as a stamp at the tile's foot); the Summary's wOBA / xwOBA (nERA / xnERA) pills sit in 1.35fr columns at 13.5px with no minimum
  width (they had been 48px pills in 38px columns, running into each other and into PA), and `.pbmain` / `.pbsum` stretch the band's width. With
  a Back the row stays (Back left, year and Filters right). The block at the end of `styles.css`.
* **Barrel% by batted-ball type on the Mix tab (Sean, 8 Oct 2026: "on the mix tab can you add barrel rate by each category too so fb, ld, and gb")**:
  under the Avg EV block a **Barrel%** block — Fly balls · Line drives · Ground balls, his percentile bar, his rate and the league's (`typeBlock` in
  `renderMixTab`, which now draws both blocks). **Build**: `pitch_flags` counts the barrels among each type's EV-eligible balls (`brfb / brld /
  brgb`, over `evfbn / evldn / evgbn`), `hitter_metrics` → `BRL_FB / BRL_LD / BRL_GB`, `HITTER_METRICS` **`brfb / brld / brgb`** (so the pool ranks
  them and they're Leaderboard columns), and the three counts are appended to `HITTER_DAY` after `evbk` so a window re-derives them in `V()`. A
  ground-ball barrel needs a grounder at 8°+ of launch, so that row reads near zero for everyone. Until a build carries them the block doesn't
  draw (a `steps=mlb` run was dispatched after the merge; past seasons at the next rescore). **Found alongside**: since the EV-by-type change
  (7 Oct 2026) a `//` comment on `V()`'s hitter line had swallowed `brl` and `pull`, so a hitter's Barrel% and Pull Air% were missing under any
  date window or split — the fourth time a mid-line `//` has eaten code; it's `/* */` now.
  **The ground-ball row came off the same day** (Sean: "get rid of gb% barrel rate too"): the block is Fly balls · Line drives; `brgb` is
  still built and stays a Leaderboard column.
* **His page stays put on a year or a filter (Sean, 8 Oct 2026: "make the site basically stay in the spot i was at and not shoot me back up to
  the top of a player page when i adjust the filters or change the year")**: `render()` scrolled to the top whenever the page's key changed, and
  the key carried the season, so every year picked started over at the top; the key is type + id now (`pageKeyOf`) — another season of the same
  player is the same page. And a rebuild that has to load first (that season's file, or the day rows for a window / split) drew a short
  placeholder, which pulled the window up to it: those placeholders carry class `pgload` (in `renderExplore` and `playerView`), and while one is
  up `render()` holds `#xboard` at the height it had (`heldH`, cleared once the real page is drawn), so `keepScroll` puts the reader back where
  they were. A page opened from a list, the search, a Similar name or a board still starts at the top.
* **League leaders in the season table, gold records, air above it (Sean, 8 Oct 2026, after a preview of the condensed bar as the page's header —
  declined, "it is fine how it is" — "add in some blank space between where standard batting starts and the end of the header", "get rid of this
  bottom text below the standard hitting stats and do the thing baseballreference does with the bold indicates the player led the league and
  italics indicates they led the MLB", "make the bottom two blue rows have bolded font and make it gold like profootballreference does if it is an
  all time mlb record", "have the three rows of text below the table that indicates the bold italics and gold labeling, but only have that")**:
  the career-best bolding is gone; a season row's cell is **bold** when he led his league (AL / NL by `leagueOf`) and **bold italic** when he led
  MLB (`td.lead` / `td.mlblead`, the title says which) — `sbLeaders(H, y)` takes every player's season line from `hist/career.js` (`mlbLine`, the
  row parse factored out of `rawLines`; a traded player leads MLB on his TOT line and a league on his clubs in it, `clubLine` / `sbCombine` when he
  changed clubs inside one), counts (`SB_COUNT`: G, PA, HR, R, RBI, SB, fWAR, bWAR; W, L, G, GS, IP, H, HR, BB, K) lead by the most, rates by the
  better end (`SB_BEST_LO`) among lines with 3.1 PA / 1 IP per team game (162, 60 in 2020). Only seasons from 2015 (`SB_LEAD_FROM`): career.js
  holds every MLB player since 2015 with his whole career, so an earlier season misses whoever had retired. The N Yrs and 162 Game Avg rows are
  bold; a career-row cell is **gold** (`td.record`, #e8c547) at or past MLB's all-time career record (`SB_RECORD`, Baseball-Reference's: G, PA,
  HR, R, RBI, SB, AVG / OBP / SLG / OPS with 3,000+ PA; W, L, G, GS, IP, H, HR, BB, K, ERA / WHIP with 1,000+ IP) — no active player is near one,
  so it doesn't fire yet. Under the table only the three-line key (`.sbkey`); the Postseason note and the rest of the old note are gone. 34px of
  air above "Standard batting" (26 on a phone). Checked: Ohtani 2024 NL HR / RBI / OPS, MLB runs; Judge 2022 MLB across the board; Skenes 2025
  MLB ERA, 2024 unqualified.
* **The club and league rows always shown, a blue gap; total WAR for a two-way player (Sean, 8 Oct 2026: "dont make the by league or team splits a
  drop down anymore, and format them exactly like this row spacing wise", from B-Ref's foot; "have the row gap be blue instead of white"; "for bwar
  and fwar include all war so like include both pitching and hitting for ohtani")**: `seasonBlock` draws N Yrs · 162 Game Avg, a gap, every club
  (`TEAM (n Yrs)`), a gap, every league — no "By team and league" fold (`sbMore` is gone). Every totals row is bold at the season rows' 28px; the gap
  rows are 10px of the band blue a shade deeper (`color-mix` of `--ink` 18% into `--band2`). **WAR**: `build_career.py` appends his pitching WAR
  `[FanGraphs, Baseball-Reference]` (or null) to every hitting row after the `[bWAR, sprint, fly balls]` array (index 24) and to every `HT` club
  row (index 22) — FanGraphs' from MLB's sabermetrics stat, `group=pitching` (`sabr_pitch_season`, one league-wide request a season, cached in
  `.cache/sabr/pitch-<y>.json`; `sabr_pitch_clubs` for a traded season's clubs), B-Ref's from `war_daily_pitch.txt` (`bref_war(…, kind="pitch")`,
  per stint). In `app.js` `mlbLine` / `clubLine` / the club parse read it as `c.pw`, `sbVal`'s fWAR / bWAR are batting + pitching (a line that
  batted but lacks its batting WAR stays blank), `sbCombine` sums it, the 162-game average scales it — so the league leaders count it too.
  `hist/career.js` was patched in place the same day (scratch `patch_pw.py`; 7,368 hitting rows have a pitching WAR — most of them pitchers' own
  at-bats). The app counts it only on a line with **100+ PA** (`SB_TWO_PA`): Ohtani's seasons (2020: 175 PA) and position players' mop-up innings, not
  a pitcher's batting line, which would otherwise lead the league in WAR. Ohtani: B-Ref 2021 4.9 + 4.1 = 9.0, 2022 3.4 + 6.3 = 9.6, 2023 6.1 + 3.8;
  FanGraphs 2023 6.6 + 2.3 = 8.9.
* **The totals' rules and gaps, no heat on them, more air (Sean, 8 Oct 2026, from Ohtani's page on his phone: "make it so the line break after like
  9 yrs and whatnot carries all the way down and don't heat map any of the bottom totals rows and make the gap blue be the same shade of blue as the
  rest and also make it so the white space gap between the header and standard batting is like 3x as big")**: the gap rows are built cell for cell
  like a row (`gap()` in `seasonBlock`: the label cell spanning Season / Age / Team, a cell per column with `ge` where a group ends, Pos), so the
  2px ink rule after the label and every group rule run unbroken from the column names through the totals, the gaps and the club / league rows;
  `tr.tot td.sbl` carries the ink rule (it was white); the gaps are `--band2`, the totals' own blue, with no inner lines; N Yrs and 162 Game Avg
  have no heat map (wOBA / xwOBA / Sprint plain there); "Standard batting" starts 102px under the band (78 on a phone).
* **Season and Team frozen, Age fades (Sean, 8 Oct 2026, from B-Ref on his phone: "do what baseball reference did with age where like when you scroll
  it fades and you just see the year and team")**: in the season table only Season (`.f1`, left 0) and Team (`.f3`, left `--sbw1` — Season's width)
  are sticky; Age (`.f2`) is an ordinary cell between them, so as the table scrolls sideways it slides under the two and Team ends up against Season.
  `seasonBlock` sets `--sbage` on the table from the scroller's `scrollLeft` (1 → 0 over Age's own width, `--sbw2`) and Age's opacity follows it.
  The totals / gap label cells span all three and stay frozen as before. Both layouts.
* **A phone's Regular Season / Playoffs at B-Ref's size (Sean, 8 Oct 2026: "make regular season and playoffs the same size as baseball reference
  has")**: 30px tall (was 44), 13.5px regular weight (was 16px / 600), 12px of side padding, 5px of strip round them — "Regular Season" 121 × 30.
  The desktop tabs were already 30px.
* **The totals' gaps plain again, twice the air, the key's words styled (Sean, 8 Oct 2026: "as far as the bottom totals line breaks I guess actually
  you had it right the first time now that I look at baseball reference", "the standard batting and header gap can you double that size", "bold
  and italicize the words bold italics")**: the gap rows are one cell across the table again (`gap()` in `seasonBlock`), so no rules run through
  them, and the totals' label cell has its white rule back; the gaps stay the band blue and the totals stay unheated (PR #473's other two
  changes). "Standard batting" starts 204px under the band (156 on a phone). The key's "Bold italic" is `b i` at 700 italic (the site-wide
  weight rule had reset the `<i>`).
* **The totals' labels in B-Ref's place (Sean, 8 Oct 2026, beside Devers's B-Ref table: "make the bottom subtotals do what baseball reference
  does")**: a totals row is three cells like a season row — an empty Season (`.f1`) and Age (`.f2`, `.sbl0`), and the label in the frozen Team
  cell (`td.sbl.f3`, the text a `.sblab` span absolutely placed at its right, spilling left over the empty cells). The one cell spanning Season /
  Age / Team had stayed Age wider than the frozen pair once Age faded, so on a scrolled phone it covered G and its rule sat a column right of the
  rows' rule; now every total sits under its column and the frozen rule runs straight down. A long label ("162 Game Avg") can run off the left
  edge when scrolled, as B-Ref's does.
* **The totals' gaps as B-Ref draws them (Sean, 8 Oct 2026: "make the break between sections in the total area be exactly like baseball
  references")**: B-Ref's gap is a 9px strip a shade darker than its totals rows (#ddd under #eee), no column rules, its frozen-column edge
  running straight through. `gap()` in `seasonBlock` is the frozen cells (`.f1` / `.f2` / `.f3`) plus one cell across the rest; the CSS at the end
  of `styles.css` makes it 9px of the band blue with 9% ink mixed in, every border off but the 2px ink rule on the Team cell.
* **The season table's four views (Sean, 8 Oct 2026: "add in a bar that allows the ability to switch between the stats we currently have, a batted
  ball quality table, a batted ball distribution table, and a plate discipline table", "put that bar ... somewhere towards the bottom of that white
  space")**: a hitter's page has a `.sbviews` bar over the table's title — **Standard** (the FanGraphs line as before) · **Batted Ball Quality** (BBE |
  Avg EV, EV90, Max EV | Hard-Hit%, Barrel%, Sweet-Spot% | FB / LD / GB EV | Bat Speed) · **Batted Ball Distribution** (BBE | GB%, LD%, FB%, PU% | Air%,
  Pull Air% | Pull%, Cent%, Oppo% | Mix wOBA) · **Plate Discipline** (PA | K%, BB% | Swing%, Z-Swing%, O-Swing% | Contact%, Z-Contact%, O-Contact%,
  Whiff%) — `sbTable` (per device, `draft2027.sbtable`), `SB_VIEWS`, `SBX` (column → key, direction, PA- or BBE-weighted), `SBX_COLS` / `SBX_BRK`
  in `app.js`; the title follows the pick. Every season cell with a direction is heat-mapped among that season's qualified hitters (`sbxPool`: 300+
  PA, 110 in 2020); Cent% / Oppo% / Swing% have none; the totals aren't heat-mapped. Totals: rates weighted by BBE (discipline by PA), Max EV the
  max, BBE summed (scaled in the 162 Game Avg); a club / league total that includes a traded season reads "–" (`sbxCombine`: a traded season's
  clubs have no Statcast line of their own). Regular season only — Playoffs switches back to Standard. The In Split row reads the view's own
  numbers (`V(p).m`). **Data**: `hist/career-bb.js` (`window.DRAFT_CAREER_BB = {keys, p: {id: {year: [BBE, …keys]}}}`, ~1.1 MB, every MLB hitter-
  season 2015 on from `data.js` and `hist/mlb-*.js`) written by `season_bb()` at the top of `build_career.py` (or alone: `build_career.py bb`),
  loaded only when a Statcast table is picked (value-free in `ensureScript`'s list). Append keys at the end of `SBX_KEYS` only. Bat speed starts 2023,
  EV by batted-ball type 2023. Pitchers' pages have no bar yet. The space over the table is 140px + the bar (64px + the 2 × 2 bar on a phone),
  so the title sits about where it did.
* **No white line under the totals' gaps (Sean, 8 Oct 2026: "you added a white line underneath the spacing on the totals while baseball reference
  doesn't have that")**: each totals row draws its white rule on its top edge (`border-collapse: separate`), so the row right after a gap showed one
  under the strip; `.sbt tr.gap + tr td` has no top border now.
* **ISO behind OPS (Sean, 8 Oct 2026: "move iso to behind ops on the standard table")**: `SB_H` = wOBA xwOBA | G PA HR R RBI | BB% K% HR/FB BABIP |
  AVG OBP SLG OPS ISO wRC+ | Sprint SB | fWAR bWAR | Pos.
* **2.5× the space above the table switch (Sean, 8 Oct 2026: "2.5x the white space gap between the header and that box with the different table
  selections")**: a hitter's `.sblock:has(.sbviews)` starts 350px under the band (was 140), 160px on a phone (was 64). Pitchers' pages (no bar) keep
  204 / 156.
* **HR/FB is FanGraphs' (Sean, 8 Oct 2026: "James Woods hr to fb ratio was 30% last year and 26% this year ... those are what fangraphs states")**:
  the season table's fly-ball count was MLB's (`flyOuts + flyHits + popOuts + popHits` from `yearByYearAdvanced`) — Statcast's stringer calls,
  which call more balls line drives and fewer fly balls than FanGraphs' (Sports Info Solutions) data: Wood 2025 86 fly balls against FanGraphs'
  101 (Statcast LD% 27.6 vs FanGraphs' 23.7), so his HR/FB read 36.0% against 30.7%; the league ran ~13% against FanGraphs' ~11-12%.
  `build_career.py` now reads FanGraphs' `FB` per player-season from `fangraphs.com/api/leaders/major-league/data` (`fg_fly`, keyed by
  `xMLBAMID`, cached in `.cache/sabr/fg-fb-<y>.json`, this season refetched after 18 hours; reachable from the cloud on 8 Oct 2026) into the
  hitting rows' `[bWAR, sprint, fly balls]` array (`fb_season`), and a traded season's club rows get MLB's club count scaled to FanGraphs'
  total (`fb_for`); MLB's count is the fallback when FanGraphs has none. `hist/career.js` patched in place the same day (scratch
  `patch_fgfb.py`: 16,991 season rows, 2,012 club rows). Wood: 2024 20.5%, 2025 30.7%, 2026 26.8%. Rerun of the FB EV analysis on the new counts:
  FB EV vs HR/FB r .814, Barrel% .847, FB EV + Barrel% R² .737 — unchanged; Cruz 2024-25 now reads 3-5 points under what his contact predicts.
* **HR/FB is Savant's, with line-drive homers as fly balls (Sean, 8 Oct 2026, an hour after the FanGraphs switch: "Let's do savants version")**:
  the FanGraphs counts above are gone (`fg_fly` removed). The fly-ball count is MLB's again (`flyOuts + flyHits + popOuts + popHits`, Statcast's
  calls) **plus his home runs Statcast calls line drives or ground balls** (`ld_hr`: one Savant `statcast_search/csv` request a season —
  `hfAB=home\.\.run|`, `hfBBT=line\.\.drive|ground\.\.ball|`, `type=details`, a row per homer, counted by `batter` — cached in
  `.cache/sabr/ldhr-<y>.json`, this season refetched after 18 hours; seasons before 2015 add nothing). Without them a liner over the fence counted
  on top of the ratio and not under it. `fb_season` adds them to a season's count; `fb_for` gives a traded season's clubs their share by fly balls.
  `hist/career.js` rebuilt from the pre-FanGraphs file plus the homers (scratch `patch_ldhr.py`: 3,533 season rows, 673 club rows). Wood: 2024
  23.7%, 2025 34.8% (31 / 89), 2026 32.3% (30 / 93); Judge 2025 30.6%, Ohtani 2025 32.4%, Cruz 2025 21.3%. League 12.9-13.3% 2024-26 (FanGraphs'
  run ~1.5-2 points lower: they call more balls fly balls). Statcast's first two seasons call far more homers liners (2015: 2,174; 2016:
  1,869; 2021 on: 424-602), which is why they're counted — it keeps those seasons' ratios consistent with their own fly-ball calls.
* **HR / FB by season on the Mix tab (Sean, 8 Oct 2026: "include a table that shows a players hr to fb ratio by year as well as their avg fb ev and
  barrel rate and then their expected hr to fb ratio ... regardless of what year is currently filtered on show all years")**: under the mix and the
  EV / Barrel% blocks, `hrfbTable(p)` — every MLB season of his (Season · Team · HR · FB · HR/FB · FB EV · Barrel% · xHR/FB · Diff, then Career),
  whatever season or filter the card is on, from `hist/career.js` (HR, the Savant fly-ball count with his line-drive homers) and `hist/career-bb.js`
  (FB EV, Barrel%, EV90, BBE), both loaded by the table. **xHR/FB** (`xHrfb` / `XHRFB`) = that season's league HR/FB moved by his contact against
  the league's (`hrfbLeague(y)`: FB-weighted over the season's 300+ PA hitters, 110 in 2020): **+0.779 per mph of FB EV and +0.738 per Barrel% point**
  from 2023 (where EV by type exists), **+1.037 per Barrel% point and +0.499 per mph of EV90** before. Fitted over every 300+ PA hitter-season,
  each centred on its season so the ball's year doesn't read as his (scratch `xhrfb.js`): r .862 / rmse 3.0 points (2023 on), .860 / 3.4 (all);
  next season's HR/FB r .68 from xHR/FB against .65 from his own HR/FB. HR/FB, FB EV, Barrel% and xHR/FB are heat-mapped (whole cell) among
  that season's qualified hitters on seasons of 100+ PA; Diff = HR/FB − xHR/FB, red when he out-homered his contact, blue under. Career: HR / FB
  summed, FB EV weighted by fly balls, Barrel% by BBE, xHR/FB weighted by fly balls over the seasons that have one, Diff over those same seasons.
  CSS `.hrfbbox / .hrfbt` at the end of `styles.css`. Wood: 2025 34.8% vs 24.0% (+10.9), 2026 32.3% vs 27.8%; Cruz 2024-25 21.0 / 21.3% vs 22.1 /
  23.9%, 2026 33.3% vs 23.0%.
  **The Barrel% column is FB Brl%** (Sean, the same night: "make the barrel % be barrel % on fly balls only"): barrels per fly ball, `brfb`
  appended to `SBX_KEYS` in `build_career.py` (so `hist/career-bb.js` carries it), heat-mapped against `hrfbLeague`'s `arr.brfb`, the Career cell
  weighted by fly balls; every season 2015-2026 carries it since the 8 Oct rescore (run 37855360025).
  **xHR/FB refit on fly-ball barrels (Sean, 8-9 Oct 2026: "it really should only factor in fly ball barrel rate")**: `XHRFB.c` = +0.373 a mph of
  FB EV, +0.391 a point of Barrel% on fly balls, +0.217 a point of Barrel% on line drives (a homer Statcast calls a liner sits in the fly-ball
  count), each against that season's FB-weighted league (`hrfbLeague` carries `brfb` / `brld`); `brld` appended to `SBX_KEYS` after `brfb`.
  Scratch `xhrfb2.js`, every 300+ PA hitter-season 2015-26 (3,321), held out by season: r .877 / rmse 3.29 against .856 / 3.54 for the old FB
  EV + overall Barrel% fit (`XHRFB.a`), next season's HR/FB r .652 against .655 (own HR/FB .614), the leftover repeating year to year at .17
  against .24. FB Brl% alone .855 / 3.54; FB EV + FB Brl% .864 / 3.45 but next season .623 — LD Brl% is what brings the forecast back; Pull
  Air% / Pull% added ≤ .003 same-season and cost forecast; bat speed nothing. `a` / `b` stay as fallbacks for a file without the rates. Wood
  2025 34.8% vs 27.8%, 2026 32.3 vs 31.4; Cruz 2024-25 21.0 / 21.3 vs 24.3 / 26.2, 2026 33.3 vs 26.7; Judge 2024 34.1 vs 31.8; Ohtani 2024 30.2 vs 28.8.
* **Fly-ball power on the Leaderboard (Sean, 8 Oct 2026: "on the overall leaderboards page could you add FB EV, FB barrel rate, and then a
  composite average score of the percentile of both and also add expected hr to fb ratio there too")**: four hitter columns, in the **Batted
  ball** set right after Avg EV (`LB_SETS`; `state.lb.fbAdd` moves a saved list that still equals the old Batted ball set) and in
  `LB_EXTRA_H` — **FB EV** (`evfb`) and **FB Brl%** (`brfb`, built since 8 Oct 2026, so 2026 only until a rescore), whose defs come from
  `meta.hitterMetrics` (`lbOrder` now looks there too, since neither is a card metric); **FB Power** (`fbq`) = the two percentiles averaged
  among the 300+ PA pool, a 0-100 number coloured as itself (`pct.fbq` in `pool()`'s hitter block and `placeIn`, `metricValue` reads
  `st.pct.fbq`); **xHR/FB** (`xhrfb`) = the Mix tab's `xHrfb` on his view's FB EV / Barrel% / EV90 against that season's `hrfbLeague` —
  `hrfbFill` in `V()` (beside `fantFill`), regular MLB seasons 2015 on, needing `hist/career.js` + `career-bb.js`, which `colsFor` asks for
  only while the column is showing; `hxKey` puts their arrival in the pool / rank keys under the same condition, so a player page loading
  career.js doesn't throw its pool away. SIDE_H defs, glossary entries; SHORT `evfb` / `brfb` read "FB EV" / "FB Brl". Filters ▸ Stats (`renderColPick`) lists the four right after Avg EV —
  `evfb` / `brfb` are meta defs, not card metrics, so the picker had no box for them (fixed the same evening).
* **B-Ref's table everywhere (Sean, 9 Oct 2026, from the "B-Ref Style Tables" canvas: "I want that for everything that all looks absolutely
  amazing")**: the season table's dress on the Leaderboard / Recent, the Pitching+ board and the card's Pitching+ and Mix tabs. **Card tabs and
  board**: `brTable(groups, heads, cls)` in `app.js` (before `renderStuffTab`) builds a `table.sbt.brt` in a `.sbscroll.brscroll` — an over-header
  row naming each group of columns (the band 9% darker), centred column names, a 2px ink rule where a group ends (`ends`, put on each row's cells by
  `fin()`), `gap()` for the darker strip, totals as `tr.tot` band rows; `PAIRH` / `pair` make every expected / actual pair two columns, **Exp** and
  **Act** (Act in grey, class `xact` — `.act` is the Draft board's sticky column, don't reuse it); `heatTd` fills a whole cell with `pctStyle`.
  The Pitching+ tab's arsenal (Pitch: Type, #, Use% | Shape | Grades vs type | Whiff% · GB% · PU% · Foul% · Called% Exp / Act, All pitches a band
  row), the K% build-up (`renderKArchetype`: Step · His · Lg · ± K% · K%, His filled by his percentile, ± by `signStyle`, the four together /
  everything else / K% as band rows — still no K% on the first two and no His / Lg on the last), the Mix tab (`renderMixTab`: Batted ball · Balls ·
  Share (filled) · Pctile · wOBA on it (filled cheapest blue → dearest red), Mix wOBA the band row; **Contact by type**: Avg EV and Barrel% His / Lg
  for FB · LD · GB) and HR / FB by season (Actual | Fly-ball contact | Expected, the career an "N Yrs" band row). Their headings are `.brbox >
  .rollhd .rollname` at the season table title's size. The **Pitching+ board** (`pitchBoardBody`): `table.sbt.brt.pbt` (no longer `.ftable` /
  `.pbtable`) — Rk and Pitcher frozen (`f1` / `f3`, `--sbw1` measured), Tm · Role · T columns (the name line under the name is gone), both header
  rows pinned (`--overh`), every column but the pitcher's facts sorts (Act columns sort by the actual rate), the sorted header lit with the red rule,
  the sorted + column filled whole (Colour: all fills all four grades), a **League** band row (every pitch the filters let through, whatever the
  minimum: grades by pitches, whiffs by swings, GB / PU by balls in play, fouls by contact). **The Leaderboard / Recent** (`body.brlb` while
  `onePage()`): one 28px line a row (30 on a phone), gridlines, no banding (the bands asked for on 6 Oct give way to B-Ref's plain rows), **Tm**
  after the name (`.brtm`), **PA / IP** before the headline (`.brpt`), **Pos** at the end (`.brpos`, `posShown`), the meta line under the name
  hidden; the Result / Process band (`#colband`) is the over-header on both layouts, a run split at a user break; `brEnds` puts the 2px rule at
  the end of each run (and after Tm and PA); the sorted column fills its cells (`paint()` sets `--heatfg` beside `--heat`) at the ordinary 13px,
  bold — the big coloured headline digits are gone there; a value equal to the best in the qualified pool is **bold italic** (`brLeaders`, cached
  per view); a **Qualified avg (N)** band row under a gap closes the last page (`brTotRows`: the reference pool, rates weighted by PA / batters
  faced, PA / IP the plain mean). The grid template under `body.brlb` adds the three columns, so every `.grid` there (`#colhead`, `#colband`, the
  rows, the gap and totals rows) carries the same cell count. The CSS is the two blocks at the end of `styles.css`; card / board rules are prefixed
  `:is(#xboard, #modal, #pitchboard)` because a warm-pass `:is(#colhead .h, …, .rollname)` rule carries id specificity. Rankings / Draft board
  keep their old rows (`brOn()` is `onePage()` only). The canvas also mocks the season table at 21px rows ("Season table — thinner rows",
  a row-height tweak) — not built; Sean asked what it would look like.
