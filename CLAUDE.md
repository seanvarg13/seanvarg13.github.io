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
question as a scheduled one. A Claude routine ("Site daily update kick", 4:50) checks and kicks it too; GitHub's schedule stays as the last backup. `tools/cloud.json` is the switch: `{"daily": true}` =
the cloud publishes and the Mac's job and publisher stand down (they read the file from `main`); `false` = the Mac
publishes and the schedule does nothing (a manual run still works: Actions → Daily update → Run workflow, with
optional `steps`, `rescore` years and `dry`). The directional models are not in the repo: the Mac's publisher
uploads `model-workspace/*.joblib` and `versions.json` (the Python + package versions they were pickled with) to the
repo's **`models` release**, which the workflow downloads and pins against. **Retraining can run in the cloud too**
(30 Sep 2026): Actions → Retrain models (`.github/workflows/retrain.yml`) fetches every regular-season PA 2015-now
(`tools/models/fetch_pa.py`, past seasons cached), trains `model3.py` / `model_bs.py` under the release's pinned versions
(`MODEL_DIR`, `ANCHOR`, and `MONO=1` for the "harder is never worse" constraint on exit velocity), keeps the replaced
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
| **Savant minors search** | Triple-A Statcast; AA/A+/A come from Gameday play-by-play (calls, batted-ball type and location, no tracking outside FSL parks) | `build_milb.py`, cached under `.cache/milb` |

Everything is fetched anonymously — no API keys anywhere in this pipeline.

### The build scripts

| script | writes | notes |
|---|---|---|
| `build_data.py [--end DATE]` | `data.js`, `days.js` | the current season. Every MLB player who played ships (`MIN_PA_HITTER` / `MIN_BF_PITCHER` = 1, since 24 Sep 2026 — a 12-BF start had left River Ryan off the site); league constants still come from 20+ BF (`CONST_MIN_BF`), and the minors keep a 20 floor. ~1-2 min on a warm cache. All the knobs (`SEASON`, `GAME_TYPES`, `DEFAULT_MIN`, `REF_MIN_PA`, `PULL_LINE`, metric lists, card layout, score weights) are constants at the top |
| `build_history.py [years…]` | `hist/mlb-YYYY.js` (+ days) | re-runs `build_data.py` season by season for 2015-2025. `build_history.py index` rebuilds `hist/index.js` (the search index). `spring 2026 2025` / `post 2025 2024` build those game types as their own datasets — but the site is regular
season only now: `indexReady()` in `app.js` drops them from the index, so nothing offers them. Rows are player × handedness × venue — no date dimension, so past seasons have splits but not date windows |
| `build_milb.py [aaa|aa|ap|a] [year]` | `hist/<level>-YYYY.js` | Triple-A has real Statcast; lower levels have batted-ball type and location only. **No bat speed, no directional xwOBA** in the minors (the model needs MLB sprint speeds) |
| `build_fantasy.py [years…]` | `fantasy.js`, `hist/fantasy-YYYY.js` | official counting stats + per-game logs for hitters (`hg`/`hgk`, with fielding and GWRBI per game) and pitchers (`gk`), home / away on both — the Fantasy Leaderboard / Trending sum these for any date range and split + Savant expected stats, plus ESPN's bonus categories: grand slams (the API's bases-loaded `r123` split), cycles (hitter game logs), game-winning RBI (the schedule's scoring plays: the RBI that put the winners ahead for good), fielding A / PO / OFA / DPT, pitcher TB / GIDP / pitches. Points are computed in the browser from the chosen scoring preset (`FCATS` in `app.js` lists every category), so an ESPN setting change needs no rebuild |
| `build_fantasy.py lines [years…]` | `hist/fantasy-lines.js` | every past season's official lines (2015 on, no game logs) for the card's Fantasy ▸ By season table; static, rebuilt by hand when a season ends |
| `build_career.py` | `hist/career.js`, `hist/minors.js` | season-by-season + career tables on every card. Reads the search index, so run it **after** `build_history.py index` |
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
  Z-Contact% use a four-rate fit, then Strike% alone.
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
**no location, no count**. **Park-adjusted** (Sean, 29 Sep 2026; `park_offsets` / `STUFF_PARK`): before grading, each pitch's
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
pull 0.2` over percentiles (already flipped so 100 = best). Pitcher rank is the mean of the Whiff% and Strike%
percentiles.

**Percentile pools.** Hitters are always ranked against hitters with **300+ PA** (`REF_MIN_PA`), pro-rated inside
a date window or split; the Min PA box only controls who is *listed*. Pitchers use the Min IP pool. Percentiles
count ties at half (`insertPct`), and lower-is-better metrics are stored negated in the sorted arrays.

**Fallbacks.** The minors have no directional xwOBA (`build_milb.py` stubs that model out — it needs MLB sprint
speeds), so there the hitters' headline and rank are wOBA and the player page has no xwOBA row. The directional
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
  `.fsorted`) is a light tint of its percentile colour with navy digits.
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
  (uK / uBB / uERA). Hand splits share each game's official line out by that day's Statcast rows (`fDayShares`), so
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
* **Positions shown are where he played that season** (`playedLabel`: positions with a tenth of his games, most first, up to three;
  SP / RP by that season's starts and relief), on the Leaderboard, Trending and cards; next year's fantasy eligibility (`posLabel`)
  only on Rankings, the Draft board, Eligibility and Fantasy (`posShown`; Sean, 30 Sep 2026).

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
