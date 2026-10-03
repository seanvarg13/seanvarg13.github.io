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
predict whiff% and gb% and pu%")**: `tools/models/train_stuff.py` trains all six models (whiff, batted-ball type, foul, damage, and
whiff / batted-ball type again **with location**) on 2020 (the first season with spin axis) through the last finished season and
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

* **Home, 3 Oct 2026** (Sean: "not make it the starred players ... leaderboard for both xwoba and pitching uERA and then also add a
  trending for hitters of last 100 PAs and then last 50 IP for pitchers by pitching uERA", then "get rid of Sean's Site on it too",
  "make the leaderboard have the same column headers format as the stuff+ table"): `renderHome` draws two cards — **leaders**
  (xwOBA, 300+ PA; Pitching uERA, 100+ IP, `puOf` from the pool's stats) and **Trending** (xwOBA over each hitter's last 100 PA, 75+ in
  the window; Pitching uERA over each pitcher's last 50 IP, 37.5+) from the day rows through `withWindow`, "Loading game-by-game
  data…" until `ensureDays()` has days.js, then it redraws itself; each list's name opens the Leaderboard with that position, sort and
  window. No starred-players card. The header's **wordmark is hidden** (`header.top .wordmark { display: none }`) — Home is in the nav.
  The Leaderboard's column names wear the Stuff+ table's header format (11px, 8px above and below; the end of `styles.css`), and the
  rows' box has a 1px navy outline.

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
