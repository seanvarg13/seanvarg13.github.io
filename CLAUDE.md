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
yesterday yet. `tools/cloud.json` is the switch: `{"daily": true}` =
the cloud publishes and the Mac's job and publisher stand down (they read the file from `main`); `false` = the Mac
publishes and the schedule does nothing (a manual run still works: Actions → Daily update → Run workflow, with
optional `steps`, `rescore` years and `dry`). The directional models are not in the repo: the Mac's publisher
uploads `model-workspace/*.joblib` and `versions.json` (the Python + package versions they were pickled with) to the
repo's **`models` release**, which the workflow downloads and pins against. Retraining a model is still a Mac job;
publishing it is automatic (the next Mac publish uploads changed files, even with the cloud on).

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
| `build_career.py` | `hist/career.js`, `hist/minors.js` | season-by-season + career tables on every card. Reads the search index, so run it **after** `build_history.py index` |
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
* **uK%** = `−26.975 + 0.933·Whiff% + 0.409·Strike%` (`UK`, fitted over every 100+ BF pitcher-season 2015-2026 bar
  2020; Whiff% as is ran 2.5 points high). **uBB%** = the walk rate at his own Strike% percentile (`impliedKBB`).
* **uERA** (`underlyingERA`) puts those two rates on the balls he actually allowed: his ground-ball and popup
  shares stand, the air balls left over are split into line drives and fly balls at the *population's* ratio, and
  every ball in play is then worth the league's average wOBA for its type (`consts.bbw`). The resulting wOBA is
  put on the ERA scale as `lgERA + (xw − lgwOBA) / wobaScale · pa9`. So a high line-drive rate never punishes
  him, but putting the ball in the air does.

**MLB-equivalent uERA** (the minors' rows in Season Stats, `milbU` / `MILB_X` in `app.js`): the level's Whiff%,
Strike%, GB% and Popup% shifted up to the majors by a fixed table per level, then uERA against that season's MLB pool.
The table comes from `tools/models/milb_translate.py` (same-season pairs at two levels, 2021 on, reliability-corrected
shifts, chained to MLB); re-run it by hand and paste the printed `MILB_X` when it goes stale.

**Mix wOBA** (`mixw`, hitters; built in `pitch_flags()` / `build_hitters`, re-derived from `mixsum` / `mixn` day
fields in a window): the average over his balls in play (bunts out) of the dataset's wOBA for each ball's bucket (GB,
PU, and LD / FB each pulled, straightaway or oppo — ground balls are one bucket on purpose: by direction they tracked
handedness and speed, not the mix). Per ball in play — walks and strikeouts don't enter it (Sean,
26 Sep 2026). Past seasons get it when rebuilt.

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
| `tools/build_data.py`, `build_history.py`, `build_milb.py`, `build_fantasy.py`, `build_career.py` | `draft-site/` |
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
  card in the site's one `#modal` via `showPageCard()`, with classes `pagecard` (no ×) and `pagebg` (navy with interlocking light-blue square double spirals, each chained into the next —
  pattern — Sean, 26 Sep 2026: "I don't really like the slant design" — masked in the theme's colours, instead of the dimmed list). Same element, classes and
  `playerView()` as a card off a list, so a change to one is a change to the other.
* **The list pages share the pattern** (Sean, 26 Sep 2026): Leaderboard, Trending, Rankings, Draft board, Fantasy,
  Eligibility and Compare put the same navy + spiral pattern behind the page (`body[data-mode=…]::before`, fixed) and
  gather `main.wrap` — filters, table, notes — into one white card with the player card's outline and shadow.
  The card **stands still** (Sean: "I don't want the white box itself to scroll at all"): it fills the screen from under
  the header to an 18px gap (10px on the phone), the page never scrolls, and only the rows' box (`.board-scroll`, Fantasy
  `.fscroll`) moves — filters, pager and column header frozen above it. On the phone, Fantasy keeps the page scroll (its
  filters would leave the table no room).
* **Starts / relief split** (Sean, 26 Sep 2026): a pitcher who both started and relieved (`ctx.GS > 0` and `G > GS`)
  gets a third split on his card, `state.split.role` = all / sp / rp. `V()` keeps the day rows whose `gs` flag matches,
  earned runs follow the same days, and a past season reads its day-by-day file for it (`byDay` in `histDataset`).
* `hist/` files built before a field was appended to `HITTER_DAY`/`PITCHER_DAY` lack it; `app.js` checks
  `indexOf(...) < 0` before using one. Keep doing that.
* **Fantasy Leaderboard / Trending** (Sean, 26 Sep 2026): the header menu is now just "Fantasy". Points total, per game,
  per AB / PA, per start / relief app / IP, per week (weeks he played in); dates, vs LHP / RHP, home / away; expected
  points — hitters xPts (H / TB from dxBA / dxSLG, R and RBI × xwOBA/wOBA), pitchers nPts (luck-neutral) and uPts
  (uK / uBB / uERA). Hand splits share each game's official line out by that day's Statcast rows (`fDayShares`), so
  vs L + vs R = the whole. See `docs/site-README.md` § Fantasy points.
* **Saved settings sync through a secret gist** (Sean, 26 Sep 2026): fantasy presets, stars, drafted, rankings, tiers
  and ranking sets (`SYNC_KEYS` in `app.js`) — Appearance ▸ Sync across devices, a gist-only GitHub key per device.
  Anything new that should follow him between devices goes in `SYNC_KEYS`; per-device UI state and Appearance don't.
* Spring training has little tracking (many parks are not instrumented), so EV-based stats are thin there.

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
