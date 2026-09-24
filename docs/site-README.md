# 2027 Draft Board

Fantasy baseball draft rankings built on 2026 Statcast skill percentiles.

**Home** — `index.html#home` (the default route and the wordmark's link): every page on the site as a card,
in three groups — Draft day, Look things up, Set up. The header carries **Home**, a **Draft & Fantasy**
menu (Draft Mode, Rankings, Draft board, Eligibility, Fantasy points), a **Leaderboards** menu
(Leaderboard, Trending Players), **Compare** and **Appearance**; `NAV_GROUPS` in `app.js` holds the two
menus and `HOME_SECS` the home page's cards.

The two menus work like Baseball Savant's: the opener is a `<button>` that only opens the menu — it is never
a page and never changes its label — and the pages are plain `<a>` links in a `.modemenu` list, with the open
one marked `aria-current` inside the menu while the opener's tab stays highlighted in the bar. `navMenus()`
opens on hover where there is a mouse (`(hover: hover) and (pointer: fine)`) and on a tap where there isn't,
closes on outside click / Escape / navigation / resize, and places the list with `position: fixed` (measured
from the opener) so the mobile nav's own sideways scroll can't clip it.

Views on one data set:

- **Rankings** — `index.html#rankings`: same board in *your* order — type a rank, use the
  arrows, or drag rows; add tier breaks; one list per tab, saved in the browser. Save named
  sets, load them back, export/import as text.
- **Draft** — `draft.html` (or `index.html#draft`): same board plus a *Draft* button per
  player that removes them; drafted players are remembered in the browser (localStorage)
  with Undo / Show drafted / Reset. Order: big board, your working rankings, or any saved set (tiers shown).
- **Explore** — `index.html#explore`: any player, any season (see below); date windows for the current season.
- **Compare** — `index.html#compare`: up to four players side by side, each with its own season.
- **Eligibility** — `index.html#eligibility`: positions you've added from player cards, with removal.

Eligibility: hitters 20+ games at a position; pitchers SP with 25+ IP as a starter, RP with 25+ IP
in relief (both possible), full-season stats either way. `ESPN` constants in `app.js`.

Open `index.html` directly in a browser — no server or build step needed.

Pitcher tabs: **Rank vs** measures everyone on the tab against the starter pool, reliever
pool, or all pitchers.

**Percentile bars** are drawn the way Baseball Savant draws them: a 24px bar filled from the left to the
percentile over a pale remainder (`--pctrack`), a white-ringed circle carrying the number at the end of the
fill, a faint halfway tick and a dashed rule (`--pctrule`) between rows, with the stat labels right-aligned
into the bars. The ramp is Savant's: `--lo` #325aa1 through a solid `--mid` #b3b3b3 to `--hi` #d22d49.
`--bub` on `.track` is the circle's diameter (30px, 26px on the phone and for fold-out rows) and the fill
and the circle share `bubLeft()` in `app.js`, so the circle always sits exactly at the fill's end and a 0 or
a 100 still lands on the bar instead of hanging off it.

**Hitter cards** show grouped percentile meters — Outcomes (wOBA, xwOBA and dxwOBA side by side, with xBA / xSLG
folded out under xwOBA), Batted-ball quality
(Avg EV and Barrel%, with Hard-Hit%, Sweet-Spot%, 90th% / max EV and bat speed folded out under
Barrel%), Swing decisions, Contact, Batted-ball distribution (Air% and Pull Air%, with FB% / LD% /
Popup% / GB% under Air%) — all recomputed for the active date window (`evs` per-day lists feed
90th% / max EV). The groups and the fold-outs are `HITTER_CARD` / `HITTER_SUB` in `build_data.py`
(`PITCHER_CARD` / `PITCHER_SUB` for pitchers); everything in either list stays available as a
table column.

**Pitcher cards** are grouped the same way — Whiffs and strikes, Swing & miss (K%, Whiff%, CSW%), Zone & chase
(BB%, Strike% with Zone% / O-Swing% under it), Results (K-BB%, ERA), **Batted ball** (GB%, Popup%), **Process score**
(WSGP) and Stuff (fastball velo, extension), with **Expected & contact** folded away below the card: u(K-BB%), uERA, luck-neutral
ERA, SIERA, FIP, Avg EV, Hard-Hit% and Barrel%. Groups named in `meta.pitcherCardFold` ride below as a fold-out instead of in a column.

**uK% and uBB%** are what his process rates say the strikeout and walk rates should be, and they are what uERA is
built on: uK% is his Whiff% taken as the K% directly, and uBB% is the walk rate of the pitcher at his Strike%
percentile in the same pool. Both are ordinary card metrics (`uk`, `ubb`) alongside u(K-BB%) and uERA, so they can
sit on any table. Fitted alternatives are measurably tighter — against actual K%, `-1.75 + 0.975·Whiff%` is RMSE 2.36
and `-25.81 + 0.955·Whiff% + 0.383·Strike%` is 2.24, against 3.41 for the flat rule, and for walks
`53.67 + 0.136·Whiff% - 0.890·Strike% + 0.160·Zone%` is 1.36 against 1.42 — and the working is in the session notes
if they are ever wanted back.

**WSGP** is the average of a pitcher's Whiff%, Strike%, GB% and Popup% **percentiles** — the four rates that belong
to him before a fielder touches the ball or a run scores. Like u(K-BB%) and uERA it is pool-derived, not a rate on
`V(p).m`: `pool()` averages the four percentile arrays into `stats.wsgp`, percentiles *that* for the bar, and keeps
`sorted.wsgp` so `placeIn()` can put a pitcher under the minimum on the same scale; `metricValue()` reads it off the
stats object. So every split, date range and past season ranks him inside that window's own pool. 50 is an average
pitcher in all four; the bar can sit well above the number itself, because being good at all four at once is rarer
than any one of them (Skubal: 92 / 96 / 70 / 41 → 74.8, which is the 98th percentile).

**The two fold-out tables under a pitcher card** — *Underlying K% and BB%* (which carries uERA) and *Batted-ball
luck* — are drawn as proper tables: a `.tblcard` wrapper with a tinted `.tblhead` strip carrying the one number the
table is about (uERA with its percentile, or luck-neutral ERA) beside the real ERA and a verdict chip, then the
Leaderboard's own table below it: the wrapper carries the `board` class, so it inherits the board's shell and its
theming, the head is the same `--band` / `--band-ink` bar over a `--accent-2` rule, rows stripe on `--stripe` with
`--hair` dividers, and a `<colgroup>` fixes every column's width the way the board's grid rows are fixed. The table
is only as wide as those columns (`table { width: auto }` under a `width: max-content` wrapper — with `width: 100%`
the wrapper's max-content resolves to the whole card), rows are tight, and the per-row captions live in the note
under the table rather than inside a cell. Every cell is outlined (`--hair` in the body, `--accent-2` in the head),
every value and heading is centred, and the label column has its own heading (Stat / Type) — `.tblcard td.l` has to
restate the centring because the older `.luck td.l` left-align outranks the element selector. A head strip is
`width: 0; min-width: 100%` so it stretches to its table without ever widening the card past it.

Under the uERA table, after a gap, sits a second small table (`renderBBMix`): the batted-ball mix uERA actually
prices — his GB / LD / FB / Popup shares with percentiles, beside a **uERA uses** column showing the same mix after
the league line-drive/fly-ball re-split. It isn't a table: each row is a
label, a small percentile bar (`minibar()` — the card's `pctStyle` / `bubLeft` maths in a 20px track) and the rate
uERA uses, and `.uerarow` floats the whole column to the right of the uERA table. GB% and Popup% take their
percentiles off the card's own stats object; the line-drive and fly-ball bars rank the rates uERA *uses*, i.e. his
air-ball rate cut at the league's split, computed across the same pool once and cached on `pool().sorted.eld` /
`.efb` — so those two bars are deliberately the same number. The
expected column is `--accent-2-text` and every diff is a squared `.chip2` pill (blue = results beat the process,
red = they trail it, grey = level). All of it comes from
the theme tokens, so it recolours with the scheme like the rest of the tables. uERA's own recipe is spelled out in
the note under the table: his ground-ball and popup shares as they are, the air balls that are left split into line
drives and fly balls at the league's rate, every ball in play worth the league's average for its type.

**Both expected models at once.** `xws` is always Statcast's xwOBA and `xwd` is always the directional model, so
either or both can sit on the Leaderboard, on any table's columns, in a comparison, or on the card — they are ordinary
card metrics with their own percentiles. The toggle-driven `xwoba` key stays what it always was: the headline the
hitter Score, the sort menu and the row bubbles use. In `V()` the window branch computes `xwSav` and `xwDir` once and
hands out all three keys; `seasonHitterM()` does the same for a full season (`m._sav` is stashed so the directional
value can never overwrite it).

**Comparing a card.** **Compare** on a card's filter row turns the card into a comparison and nothing else: two
columns of percentile bars for the same player. While it is open the **Splits & dates** button becomes **Set up
comparison**, whose popup holds everything — one box per side with **season** (any season he played, MLB or minors),
**split** (All, vs LHP / vs RHP, Home, Away, or a handedness and a venue together) and a **date range** (from / to,
blank meaning the season's first or last game), plus a tick list of which stats belong on the grid (shared with the
Compare page's `state.cmpCols`). Each column on the card is headed by what that side is and the plate appearances or
innings it covers, and those heading boxes freeze under the card's own pinned plate while the bars scroll
(`--cardtop-h`, measured after every render and re-measured by a ResizeObserver on the card top). The rows are
condensed, the bars stop at 236px on a desktop, and each value sits right beside its own bar in full-strength ink. So vs LHP against vs RHP, August against September, or 2026
against 2025 are all the same three clicks, on either side. `cmpSideData()` reads the player inside
`withDataset` / `withWindow` / `withSplit`, so each column is ranked against its own season's qualifiers on their
numbers in the same split and range; `renderCmpGrid()` draws Savant's side-by-side layout with the stat labels down
the left, using the same `.cgrid` as the Compare page. Changing a column's season clears its date range, since a
range belongs to the season it was set in. Every group is in the grid, including the ones that normally fold away
below the card. **Close comparison** goes back to the card.

**Hitters** rank by xwOBA, and **Expected stats** switches which model that is, for the whole site at once:

- **Statcast** (default) — exit velocity + launch angle: Savant's published number for a full season, rebuilt
  from pitch-level data inside a window or split.
- **Directional** — the spray-angle model in `../model-workspace/v2_dir.joblib` (exit velocity, launch angle,
  spray and pull angle, the batter's sprint speed), so where he hit the ball counts. It shows as **dxwOBA**
  everywhere the label appears.

The model scales its predictions by the league's mean wOBA on contact, and its own average prediction isn't
exactly 1, so a raw season of dxwOBA lands a few points off the real scale (+.009 in 2026, −.007 in 2015).
`dirInfo()` re-anchors each dataset with one factor — league wOBA over league dxwOBA, PA-weighted across every
hitter in the file (2026: ×0.981) — applied to the season number and to every window and split alike. It is a
single positive multiplier, so orderings and percentiles are identical either way; only the level moves.
The same function also notices a file whose `xwoba_dir` is simply its `wOBA` for everybody — the minor-league
builds never run the model — and reports no directional numbers at all rather than passing wOBA off as dxwOBA.

On the 2026 board, dxwOBA tracks wOBA far more closely than Statcast's does (r .862 against .798 among
qualifiers, and .860 against .777 for the top third by Pull Air%), while Statcast's is a shade better at
predicting *next* season's wOBA (pooled r .522 against .503 over 2023→24, 24→25 and 25→26).

The switch lives in **Stats & filters ▸ Splits & dates** on any hitter list and in the **Splits** block on any
hitter's card (`state.xmodel`, saved in prefs). Both come from the same day rows — `dnum` / `wden` for the
directional model, `xnum` / `xden` for Statcast's — so windows, splits, the trending spans, the percentile
pools, the board order and card comparisons all follow the choice; `applyXModel()` swaps the label on the
shared metric objects and clears the value, pool and rank caches, and `viewKey()` carries the model so nothing
stale survives. Directional is blank where batted balls aren't tracked (A and AA, `tracked < 5%`). Season files
also carry the plain `xwoba_dir` per player.

**dxBA and dxSLG** (`model-workspace/model_bs.py` -> `v3_ba.joblib`, `v3_slg.joblib`) are the same recipe with
the other two targets a batted ball can have: whether it goes for a hit, and how many bases. Same six features,
same 3-year recency half-life, same era-neutral target (divide by the season's league rate on contact, multiply
back when scoring), so a pulled fly ball is priced by the shift rules in force now. Both land within a quarter of
a percent of the real 2026 league rate in sample (level .998 and 1.002). `directional_bs()` in `build_data.py`
scores every tracked ball in play that counts as an at-bat, keeps the real result on an untracked one, and sums
per day into `dbsum` / `dssum` — two more fields on the end of `HITTER_DAY`, so older files still read — which
divide by AB to give `dxba` and `dxslg`. They fold out under dxwOBA on the card and lead the player page's middle
panel. Seasons built before these models fall back to Statcast's xBA / xSLG. The wOBA skills blend is still available as a sort and on each card.
**Position for 2027** on a pitcher's card moves him between SP and RP.

**Splits**: on an open player card — vs LHP / RHP (vs LHB / RHB for pitchers) and home / away.
The card is ranked against everyone's numbers in the same split (pool minimum pro-rated); the
list stays unsplit. Combines with the global Dates window.

**Dates**: from / to boxes on the list and on every card; a blank side means the season's start
or end. Past seasons use `hist/days-YYYY.js` (per-game rows, ~10 MB each, loaded on demand). `days.js`
carries per-game rows (split by handedness) for every player, loaded the first time a window or
split is chosen, and the page re-aggregates them —
every metric, AB / IP, pool and percentile. Full season uses Savant's exact Air% / Pull Air%
and official AB / IP; windows rebuild them from Statcast (Pull Air% within ~0.5 pts of Savant).

A day row is one player x handedness x venue x day, so anything that is a **sum of per-event
probabilities** has to keep its decimals in `daily()`'s packer — `xbsum` / `xssum` (the xBA and
xSLG numerators) are typically 0.2-1.0 in a bucket that size, and rounding them to whole numbers
cost about half of each (windowed xBA read .115 where the season said .265). They ride in the same
`round(v, 2)` list as `wnum` / `xnum` / `evsum`. Season files (`hist/mlb-YYYY.js`) were never
affected: their rows are one per handedness x venue, where the lost fraction is under 1%.

## Refresh the data

Easiest: `python3 serve.py` — opens the site at http://localhost:8787 with an **Update data**
button in the header (defaults to yesterday). It runs the whole pipeline — MLB (`build_data.py`),
then the four 2026 minor-league levels (`build_milb.py aaa` and `build_milb.py aa ap a`), then the
player index — shows progress, and reloads. MLB alone is ~1–2 minutes; the minors add ~5–15 minutes
(only new days download; everything is cached under `.cache/milb`).

`python3 serve.py --phone` binds to the whole local network and prints an address like
`http://192.168.1.23:8787/` that a phone on the same Wi-Fi can open. For a permanent link that
works anywhere, drag the `../draft-site-deploy` folder onto https://app.netlify.com/drop (see
"Hosting" below).

Or by hand:
```
python3 build_data.py                 # everything through yesterday
python3 build_data.py --end 2026-09-27
```

Takes ~1–2 minutes. It reads pitch-level Statcast through pybaseball (cached in
`~/.pybaseball`, only new days download), Savant's batted-ball leaderboard (Air%, Pull
Air%), and the MLB Stats API (teams, positions, games by position), then writes `data.js`.

Knobs at the top of `build_data.py`: the SP-vs-RP rule, the metric list and direction
(higher/lower is better), the score weights, and the page's default minimums (`DEFAULT_MIN`).
Hitter percentiles are always measured against hitters with **300+ PA** (`REF_MIN_PA`, pro-rated
inside windows/splits); the **Min PA** box only controls who is listed — hitters under 300 PA are
placed against that population. Pitcher percentiles use the **Min IP** pool.

## Explore (any player, any season)

`index.html#player/<id>` — search any player and open his card for any MLB season from 2015 on, with the
card's vs-LHP/RHP and home/away splits. Percentiles are against that season's own league.

A player's page **is** the popup card: the same pinned block (headshot plate, the filter row, and the
filter panel when it is open) over the same card, on the phone and on the desktop — the only difference
is that the popup carries an × and the page does not. Both are built by `renderPlate` + `renderSeasonChips`
inside `cardTop`. A two-way player gets a Hitting / Pitching switch on the plate either way. The site
header stays above an open popup, so the player search at the top right works from inside a card as
well; picking someone there closes the card and opens his page.

```
python3 build_history.py            # builds hist/mlb-YYYY.js for 2015-2025 (skips ones already built)
python3 build_history.py 2025       # one season
```
Each season is ~1.9 MB and loads on demand; `hist/index.js` is the search index (rebuilt each run).

```
python3 build_milb.py               # Triple-A seasons from Savant's minor-league Statcast search -> hist/aaa-YYYY.js
python3 build_milb.py 2026          # one season (~40 min of downloads the first time; days are cached in .cache/milb)
```

Triple-A seasons show up as extra `2026 AAA` chips on player cards, Explore and Compare; percentiles are against that
level's own qualifiers. No bat speed (no bat tracking in the minors) and no directional xwOBA.
`python3 build_career.py` refreshes the season-by-season / career stats table shown on every card —
`hist/career.js` (MLB lines + career totals) and `hist/minors.js` (the minor-league lines). It reads the
search index, so run it after `build_history.py index`; it takes about 3 minutes and **is part of the daily
job** (it wasn't until 2026-09-23, so those tables sat two days stale while every other number refreshed).

## The toolbar, in one button

Every filter lives in one popup: the **Filters** button opens it and the tabs are **Filters** (position, name
search, team, the Leaderboard's season and level, sort, and a pitcher's ranking pool), **Included stats**,
**Splits & dates** and **Table**. Nothing hides or unhides any more — the page shows the button and one line of
what is in effect (`renderToolSummary`). The controls themselves are single nodes that live in `#park` and are
moved into the popup while it is open (`PARKED` / `parkControls()`), so their listeners are wired once.

## Stat glossary

The wall of explanation under every list is two fold-outs: **Stat glossary**, one box per stat for whichever side
of the ball the tab is on (`GLOSS` in `app.js` keyed by metric, drawn from the card groups so a new stat only needs
a line in `GLOSS`), and **How this page works** for the eligibility / pools / splits / dates prose.

## Files

| file            | what                                   |
|-----------------|----------------------------------------|
| `index.html`    | page shell                             |
| `draft.html`    | redirect to `index.html#draft`         |
| `app.js`        | rendering, sorting, draft state        |
| `styles.css`    | light + dark themes                    |
| `data.js`       | generated — season values (`window.DRAFT_DATA`) |
| `days.js`       | generated — per-game split rows, loaded on demand |
| `build_data.py` | data pipeline (current season)         |
| `build_history.py` | past seasons for Explore -> `hist/` |
| `build_milb.py` | Triple-A seasons (Savant minors Statcast) -> `hist/aaa-YYYY.js` |
| `build_fantasy.py` | official season stats + pitching game logs + Savant expected stats -> `fantasy.js` (past years `hist/fantasy-YYYY.js`) |
| `publish.py` | pushes the site to Netlify (only changed files); remembers the site in `netlify_site.json` |
| `themes.js` | colour schemes + fonts (Appearance page); sets the scheme tokens on `<html>` before first paint |
| `manifest.json`, `icons/` | home-screen app on a phone (name, icon, standalone window) |
| `build_career.py` | season-by-season + career stats table -> `hist/career.js` |
| `serve.py`      | local server with the Update button |

## Spring training and postseason

`python3 build_history.py spring 2026 2025` and `python3 build_history.py post 2025 2024` build those game types as
their own datasets (`hist/mlb-YYYY-spring.js`, `hist/mlb-YYYY-post.js`, each with a days file). They show up as a
**Regular season / Spring training / Postseason** switch next to the Year and Level pickers on player cards, Compare and
the Leaderboard. Percentile pools are that set's own players (refPA scales with the number of games), and the Min PA / IP
box is scaled down the same way. Spring training has little Statcast tracking (many parks aren't instrumented), so
EV-based stats are thin there.

## Spans of seasons on the Leaderboard

Pick a season, then a later year in the **to** pill and the list covers the whole span at that level and game type
(`mlb-2023_2025` in the code). **Combined** gives one line per player with every season in the span summed (the same
row-summing a date window uses; ERA from the seasons' earned runs; Min PA / IP multiplies by the seasons in the span;
percentiles are measured against players with 300 PA × seasons). **Each season** lists every player-season as its own
line. **Year** and **Age** columns live under "Player" in Included stats and always sit right after the name (Year is
on by itself in Each-season mode). Clicking a line opens that season's card, or the combined card for the span.

## Team filter and the toolbar

The four Draft Mode pages (Draft Mode / Rankings / Draft board / Eligibility) are a dropdown on the header's own
**Draft Mode** item rather than a second nav row; it shows whichever of them you're on. Opening a player's card and
closing it leaves the page exactly where it was (`lockPage` reads the scroll position *before* `body.modal-open`
makes the page `position: fixed`, which would otherwise collapse it to zero).

**A popup stays put on a desktop.** The overlay itself no longer scrolls: `.modal` is a centring flexbox with
`overflow: hidden`, the panel is a column flexbox and `#modal-body` is the only scroller (`min-height: 0`,
`overscroll-behavior: contain`). The panel's height is capped three ways, because any one of them can be the honest
one: `--modal-max`, which `sizeModal()` measures off `visualViewport.height` on every render and on every resize
(`vh` goes out of step under page zoom, a forced viewport width, or a browser's own chrome); `100%` of the fixed
overlay; and `calc(100dvh - 40px)` if the variable never lands. The panel's own `margin-top: 28px` is zeroed there
too — flex centring splits a margin, so it was leaving twice as much room above the card as below. So a player card or a settings popup sits still while you
scroll inside it, the close button (absolute to the panel) never scrolls away, and the card's pinned plate and the
comparison's frozen heads stick to the panel instead of the page — `#modal-body .cardtop { top: 0 }` and the existing
`--cardtop-h` offset do the rest. Mobile keeps the old full-page scroll, where a long card wants the whole screen.

**Five toolbar buttons, five dropdowns.** Position / Filters / Stats / Splits & dates / Table each open their own
panel under their own button (`POP_BTNS`, `renderToolButtons`), in the `#pop` host that sits at body level with
`z-index: 120` — `placePop()` hangs it 6px under the button, clamps it to the window and caps its height to the room
below; on a phone it spans the width with an 8px margin. The panels are the same renderers as before, only they call
`panelOpen()` instead of opening the modal, so nothing locks the page. Clicking away (or the ×) closes and **applies**;
Cancel still reverts, because `openPanel` keeps taking its snapshot. `POPPED` is the set of panels that live in the
dropdown; everything else (Team, Rankings lists, the card's comparison) still uses the modal.

**Position is a multi-select.** `state.pos` stays the primary — it picks the pool the percentiles come from — and
`state.posAlso` holds the extras; `posSel()` is the list and `inPosSel()` the filter the board uses. `togglePos()`
keeps it honest: crossing between hitters and pitchers replaces the selection, ticking a real position drops the
"all" tab, unticking the last one falls back to "all", and SP + RP together collapses to ALLP.

**The header's own dropdowns** (Draft & Fantasy, Leaderboards) stay where they are in the DOM — their styling is
keyed to that nesting — and `body.navopen header.top { z-index: 300 }` lifts the whole header over the page while one
is open, which is what keeps them from painting behind it on a phone.

**The player page is three panels**, laid out the way Baseball Savant lays out its own (`.ppage`, built in
`renderExplore`). The pinned row with the season, the splits and Compare runs full width; under it:

- **Left — the player card** (`renderSavantPlate`, `.splate`), then his season table, then Player apps. The card is
  Savant's: his MLB action shot as a full-bleed banner, his circular headshot overlapping its bottom edge, then
  centred under it the name, `POS | Club` with the team logo (`mlbstatic.com/team-logos/<id>.svg`, ids in `TEAM_ID`),
  `Bats/Throws | height weight | Age`, and the draft line (`Draft: 2024 | Rd. 1, No. 19, New York Mets | Oklahoma
  State`). Height, weight and the draft come from one small cached request to
  `statsapi.mlb.com/api/v1/people/<id>?hydrate=draft` per player (`bio()`), which re-renders when it lands.

  Under it, `renderSeasonHeat()` draws the plain counting line Savant puts there, laid out the same way: one rule
  above the header, a hairline under it, no cell borders, seasons oldest-first and right-aligned, and a shaded
  career row. It shows his three most recent MLB seasons and then a career row totalling all of them: PA, AB, R, H, HR, SB, AVG, OBP, SLG, OPS for a hitter (`SAV_H`), W / L / ERA / G / GS / SV / IP / K /
  BB / WHIP for a pitcher (`SAV_P`), off `rawLines()` and `combineLines()`. Clicking a row opens that season.

  Then **Player apps** (`renderPlayerApps`): the year and the level as two pills (`renderSeasonPicker` with
  `{noKind: true, levelOnly: true}` — the first picks the season, the second MLB / Triple-A / Double-A / A+ / A for
  that season), the run of games below them as its own split (regular season / postseason / spring training, from
  `seasonKinds()`), the hitting / pitching switch, the split-and-date panel (`renderSplitPanel`), the sample line and
  Star / Draft. This replaces the pinned row
  the page used to carry, so the three panels start at the top the way Savant's do.
- **Middle — one flat percentile list** (`renderPctPanel`, `.pctbox`), with a single banner header ("2026 Percentile
  Rankings") and no group headings inside it. The stats are Savant's own, in Savant's order: `SAVANT_H` is dxwOBA,
  dxBA, dxSLG, Avg EV, Barrel%, Hard-Hit%, LA Sweet-Spot%, Bat speed, Chase (O-Swing)%, Whiff%, K%, BB%, and
  `SAVANT_P` is xERA (uERA here), fastball velo, Avg EV, Chase%, Whiff%, K%, BB%, Barrel%, Hard-Hit%, GB%,
  Extension. Its title is the page's navigation: `pctTitle()` builds "**2026** MLB Percentile Rankings" with the year
  and the level as `headSelect()` pickers — a native `<select>` laid invisibly over text that reads as part of the
  heading — so changing either moves the whole page to that season. The word itself is the button and the list drops
  under it in a bordered, rounded panel (`HSEL`, `.hmenu`), the way Savant's does; a document click or Escape closes
  it.
  The bars are drawn the way Savant draws them — a full-width light track, the fill from the left edge, a
  round marker at its end, a dashed rule under each row, and a poor / average / great scale over the first bar
  (`pctScale()`); the three expected stats follow whichever model is switched on (`expKeys()`) and are always named
  plainly. Savant's run values, fielding, sprint speed and spin have no counterpart in this data. `PCT_FALL` gives
  each expected stat a chain to fall back down — dxwOBA to xwOBA to wOBA, dxBA to xBA to BA — so a season built
  before the directional BA / SLG models, or a level with no batted-ball tracking (A, AA, in `NEEDS_EV`), shows the
  real result instead of a blank row.
- **Right — the rest, under four tabs on one row** (`extraSections`): `EXTRA_H` (Discipline, Contact, Batted ball,
  Quality) and `EXTRA_P` (Run prev., K and BB, Discipline, Batted ball). Each tab is a list of
  blocks and a block break draws a rule across the bars, so the batted-ball tab reads air / ground, then the four
  types, then the spray. Under the tabs sits `renderRolling()` — Savant's rolling line, expected wOBA over a
  trailing 100 plate appearances across the whole season, walked day by day off the same day rows with a
  two-pointer, with the pool's own average as the dashed LG AVG line. It follows whichever expected model is on.

**Under the boxes**, `renderBelow()` hangs the same centred strip of tabs Savant hangs there (`BTABS`,
`state.pbtab`): **Compare** (turn the two-side comparison on, and Set up comparison once it is — turning it on drops
the third panel and gives the comparison the whole right-hand side, `.cmp2page`), **Season Stats** (the full
`renderRawStats` table with its MLB / MiLB / All levels switch) and **Advanced Stats** (`belowAdvanced()` — every
card group at once, then the card's own fold-outs: Underlying K% and BB%, Batted-ball luck, and the card notes).
The splits and dates stay up in Player apps rather than down here.

The three panels are exactly the same width (`repeat(3, minmax(0, 1fr))`) and the same height. `sizePPage()` puts
`body.playerwide` on while a player page is open, which lifts the site's 1240px cap off `.wrap` and `.top` and
leaves `min(6vw, 96px)` on each side — Savant's own proportion — then sizes the boxes to run from under the header
to the bottom of the window, less the height of the tab strip so that strip stays on screen. It measures where the
boxes start in the **document** (`rect.top + scrollY`), not the viewport: reading the viewport while the page is
scrolled gives a smaller number every time and the boxes grow with each render. The site's own notes
sit below the fold rather than eating into the boxes. A panel whose content is longer (a card with eleven seasons on
it) scrolls inside its own `.pscroll`, which hands the wheel back to the page (`overscroll-behavior: auto`) once it
has run out, so the page still scrolls with the pointer over a box. The bars keep their own spacing at the top of
the middle panel; in the right one the rolling chart is pushed to the foot so it anchors the box.

**The chrome is Savant's too.** A panel has no coloured band: `panelHead(lead, rest, sub)` centres a title with the
year in bold and the rest regular, over the little dotted rule (`.pcdots`, a repeating radial gradient). The season
table is borderless — a plain bold header row over a rule, no cell borders, no striping, one shaded career row. The
name is set large and light, the club by its full name (`TEAM_FULL`, built from `TEAM_CITY` + `TEAM_NAMES`), and
"Player Apps" is a centred mixed-case heading rather than the site's usual uppercase label.

The page reuses the card's renderer and moves its pieces into the columns, so the card in a popup is unchanged.
Stats these groups need that aren't card metrics (Pull%, Cent%, Oppo%, Non-pull%, Swing%, Strike%) are added to the
percentile set as `SIDE_H` / `SIDE_P`, so they get bars like everything else. On a phone the three panels stack and
the height cap is lifted.

The first toolbar row is the positions, the name search and **Team** (one league, one division or one team; × or Clear
removes it — the tab counts follow). Everything else sits on the second row, which scrolls sideways when it runs out
of room. **▴ Hide filters** tucks the rows into a slim pinned bar that shows what's in effect; **▾ Filters** brings them
back from anywhere in a long table. Both are the same control in the same corner: the button lives at the right-hand end
of the toolbar's first row either way, which on the Rankings page is the rankings-list bar rather than the tabs
(`renderSetBar` moves it), so it never jumps when you fold or unfold. Popup% is a card stat for both hitters (under Air%) and pitchers (Contact allowed), so
it can be a leaderboard column.

## Stars and notes

**Saving rankings.** The Rankings page has a **Save** button on its list bar: it writes back to the open list, or
asks for a name when there isn't one, and it greys out when there's nothing new to save. Saved lists live in this
browser under `draft2027.rankSets`, and the storage around them is deliberately defensive — a value that won't parse
is left untouched (its text is kept under `<key>.corrupt`) instead of being replaced by an empty one, every change
keeps the previous copy under `draft2027.rankSets.bak`, and the lists panel offers to restore anything the backup
still holds that the live copy has lost. A write that would blank the lists is refused unless it is a deliberate
delete. Export still writes every list as text for another browser.

**Tiers and pages.** The board's order is **tier first, rank second**: a player's tier decides where he sits, his rank
only orders him inside it, and the rank numbers read 1, 2, 3… straight down the page — put a player in a tier and his
number travels with him (`byTier` / `tierSort`, run from `saveTiers` and after a hand-typed rank; older lists and every
saved list are converted once by `migrateTierOrder`, storage flag `tiersFmt` 4). A rank typed or nudged across a tier
boundary lands at the edge of the player's own tier rather than leaving it. With tiers on, `pageWindow` takes the tier
spans: a tier that would fit on a page of its own is never cut in two — it starts a fresh page instead — while a tier
longer than a page has to break wherever it falls, so it carries on filling the page it started. That second half
matters: without it one short tier ends the page early and leaves the rest of it blank.

**Hide filters** leaves the rankings-list bar in place, so Save is always one click away; on that page the one button
flips between ▴ Hide filters and ▾ Filters instead of the slim bar appearing.

**Lists stay on the device that made them.** Saved rankings live in this browser only; **Export / Import** in the
lists panel move them between devices as text. (A publish-and-pick-up sync was tried on 2026-09-22 and removed at
Sean's request — he preferred the lists staying put.)

On any player card, **☆ Star** stars him on a rankings list (the open one, or any saved list) with a note. Stars travel
with the list (Save / open / export). On Rankings and the Draft board, starred players show ★ (hover for the note) and
**Starred** filters the list down to them.

## Fantasy points

`#fantasy` — ESPN-style points scoring. **Scoring settings** holds presets (ESPN standard built in; make your own from
any of ESPN's categories, plus league size). **Points** ranks every hitter / pitcher by the preset with the official
season line (G, PA, AB, H, R, HR, RBI, SB, BB, K, AVG/OBP/SLG/OPS; pitchers G, GS, IP, W, L, SV, HD, K, ERA, WHIP, K/9,
QS), by position / role, for 2026 and the two seasons before. **Per opportunity**: points per game, per PA, per AB,
per 600 PA; pitchers per IP, per start, per relief appearance, QS%. **What if**: pitchers with K and BB at their
underlying rates (uK% = Whiff%, uBB% from Strike% percentile), ER at luck-neutral ERA, hits at Savant xBA — and the
rank at the role that would give; hitters with H / TB at Savant xBA / xSLG, points per game at a starter's PA/G and a
full starter's PA at their position (top teams × lineup slots by PA), and the rank at the position that would give.
Data: `build_fantasy.py` (part of Update / the daily job) -> `fantasy.js`; `python3 build_fantasy.py 2025 2024` for
past years -> `hist/fantasy-YYYY.js`.

## Hosting (a real link, on your phone)

It is a static site, so any host works. The built-in way is **GitHub Pages** (free, no publishing quota — Netlify's
free plan meters deploys and ran out):

1. Make a free account at https://github.com/signup.
2. https://github.com/settings/tokens -> **Generate new token (classic)** -> note "Sean's Site publisher",
   expiration **No expiration**, tick the **repo** scope -> Generate, copy it.
3. Save it on this Mac (outside the site folder, so it is never uploaded):
   `echo 'ghp_xxx' > ~/.github_token`
4. `python3 publish_github.py` — the first run creates the repo `<you>.github.io`, turns Pages on and pushes
   everything (~450 MB, compressed to ~100 MB on the wire; a few minutes). It prints the link:
   `https://<you>.github.io/`. After that just run it again, or press **Publish** in the header of the local
   site — git sends only what changed, and the page goes live a minute or two later.

The site files are mirrored into `../draft-site-deploy`, which is the git repo. Its history is squashed to one
commit on the first publish of each month (and whenever it passes 1 GB), so it never grows without bound
(`--squash` does it on demand). Netlify still works through `publish.py` / `~/.netlify_token` and is used
only when there is no GitHub token.

The daily loop is then: `python3 serve.py` -> **Update data** -> **Publish** -> reload on the phone.
Rankings lists live in each browser's storage, so use Export / Import on the Rankings page to move
them between the Mac and the phone.

**On an iPhone as an app**: open the link in Safari -> Share -> **Add to Home Screen**. It gets its own
icon and opens full-screen without the Safari bars (the page ships a web-app manifest and apple-touch-icon).
The home-screen copy has its own storage, so its rankings lists, drafted players and Appearance choices are
separate from Safari's — use Export / Import to move lists.

**Appearance** (header link): colour scheme — Carolina blue (default), Carolina navy, Titans, Titans · Carolina
(Titans navy and the red stripe, with Carolina blue on the banner instead of Titans blue), Purple,
Crimson Tide, Clemson — plus font and light / dark. Schemes are defined in `themes.js` as the token roles
described at the top of `styles.css`; add one by adding an entry there. Saved per browser.

**Hands-off**: `bash install_schedule.sh` installs a launchd job that runs `daily_update.py` (MLB + minors
through yesterday, then `publish_github.py`) every day at 5:30 am and logs to `logs/daily.log`. It publishes
**twice**: once the moment the MLB build finishes (~25 minutes in), then again after the minor-league scrape,
fantasy and history index — the minors take another hour or more, and the site shouldn't sit a day stale
all morning waiting for them. The Mac has to be
awake at 5:30 (plugged in + `sudo pmset repeat wakeorpoweron MTWRFSU 05:25:00` wakes it; if it's asleep the job
runs when it next wakes). macOS blocks background jobs from the Desktop folder until Python has Full Disk
Access — the installer probes for that and prints the one-time fix. `bash install_schedule.sh remove` turns it off.

Same Wi-Fi only, no account needed: `python3 serve.py --phone` prints an address like
`http://192.168.1.23:8787/` the phone can open while the Mac is running it.
