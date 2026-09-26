# 2027 Draft Board

Fantasy baseball draft rankings built on 2026 Statcast skill percentiles.

**Home** — `index.html#home` (the default route and the wordmark's link): every page on the site as a card,
in three groups — Draft day, Look things up, Set up. The header carries **Home**, a **Fantasy**
menu (Draft Mode, Rankings, Draft board, Eligibility, Fantasy leaderboard, Fantasy trending, Scoring settings), a **Leaderboards** menu
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

**Percentile bars** are the site's own, styled after Baseball Savant's: a 24px bar filled from the left to the
percentile over a pale remainder (`--pctrack`), a white-ringed circle carrying the number at the end of the
fill, a faint halfway tick and a dashed rule (`--pctrule`) between rows, with the stat labels right-aligned
into the bars. The ramp is Savant's: `--lo` #325aa1 through a solid `--mid` #b3b3b3 to `--hi` #d22d49.
`--bub` on `.track` is the circle's diameter (30px, 26px on the phone and for fold-out rows) and the fill
and the circle share `bubLeft()` in `app.js`, so the circle always sits exactly at the fill's end and a 0 or
a 100 still lands on the bar instead of hanging off it.

**Hitter cards** show grouped percentile meters — Outcomes (wOBA and xwOBA side by side, with xBA / xSLG
folded out under xwOBA — all three the directional model's), Batted-ball quality
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
built on. uK% is fitted on his Whiff% and Strike%: `-26.975 + 0.933·Whiff% + 0.409·Strike%` (`UK` in `app.js`; Sean,
25 Sep 2026), least squares over every 100+ BF pitcher-season 2015-2026 bar 2020, weighted by BF. It sits within half
a point of the league's real K% every season and misses a pitcher's by ~2.6; Whiff% taken as the K% directly — the
old rule — ran 2.5 points high and missed by 3.4, and 2 × SwStr% + 1 did no better. uBB% is the walk rate of the
pitcher at his Strike% percentile in the same pool. Both are ordinary card metrics (`uk`, `ubb`) alongside u(K-BB%)
and uERA, so they can sit on any table.

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

**One expected model.** Statcast's xwOBA left the site on 24 Sep 2026 ("get rid of statcast xwoba completely"):
`xwd` (labelled **xwOBA**), `dxba` (**xBA**) and `dxslg` (**xSLG**) are the directional model's, and the `xwoba` key the
hitter Score, the sort menu and the row bubbles use is the same number. The build still writes Savant's `xws` row and
its xBA / xSLG fold-out into `data.js`; `app.js` drops them at load and relabels the three. Statcast's xBA / xSLG are
used only to stand in, under those names, for an MLB season not yet rescored for the directional ones.

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

**Hitters** rank by xwOBA, and xwOBA is the directional model: the spray-angle model in
`../model-workspace/v3_dir.joblib` (exit velocity, launch angle, spray and pull angle, the batter's sprint speed), so
where he hit the ball counts. There is no Statcast option any more — the Expected stats switch and `state.xmodel`
are gone.

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

It comes from the day rows (`dnum` / `wden`), so windows, splits, the trending spans, the percentile pools, the
board order and card comparisons all use it. It is blank in the minors — `build_milb.py` stubs the xwOBA model out
there (it needs MLB sprint speeds) — so `wobaHead()` hands the hitters' headline and rank to wOBA, the Leaderboard
drops its own wOBA column so it isn't shown twice, and the player page has no xwOBA row. The directional xBA / xSLG
models do run in the minors (sprint speed missing), so Triple-A and the tracked A parks show them; BA and SLG stand
in where nothing is tracked (AA). The hitter lists don't offer xwOBA as a column or a sort of its own (`HEAD_DUP`):
the headline column already is it. Season files also carry the plain `xwoba_dir` per player.

**dxBA and dxSLG** (`model-workspace/model_bs.py` -> `v3_ba.joblib`, `v3_slg.joblib`) are the same recipe with
the other two targets a batted ball can have: whether it goes for a hit, and how many bases. Same six features,
same 3-year recency half-life, same era-neutral target (divide by the season's league rate on contact, multiply
back when scoring), so a pulled fly ball is priced by the shift rules in force now. Both land within a quarter of
a percent of the real 2026 league rate in sample (level .998 and 1.002). `directional_bs()` in `build_data.py`
scores every tracked ball in play that counts as an at-bat, keeps the real result on an untracked one, and sums
per day into `dbsum` / `dssum` — two more fields on the end of `HITTER_DAY`, so older files still read — which
divide by AB to give `dxba` and `dxslg`. They fold out under xwOBA on the card, as xBA and xSLG, and lead the
player page's Results. An MLB season built before these models shows Statcast's xBA / xSLG under those names until
it is rescored. The wOBA skills blend is still available as a sort and on each card.
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

**The header's own dropdowns** (Fantasy, Leaderboards) stay where they are in the DOM — their styling is
keyed to that nesting — and `body.navopen header.top { z-index: 300 }` lifts the whole header over the page while one
is open, which is what keeps them from painting behind it on a phone.

**The player page** is the popup card itself: `renderExplore()` opens it in the site's `#modal` through
`showPageCard()`, with no × (`.pagecard`) and a navy background with one unbroken light-blue square-spiral line in the theme's colours behind it (`.pagebg`) where a card
off a list has the list dimmed. Both are built by `playerView()`; top to bottom:

- **The pinned plate** (`playerHead()`, `.phead`). The headshot sits in a square framed tile (the card's navy outline, a
  light wash behind the cut-out, a hard offset shadow) with the **Star** button under it (`.phmug`), on a desktop and a phone
  alike; every header button, the site's nav included, has the same square navy outline and shadow.
  The plate never scrolls: `playerView()` puts everything under it in `.cardscroll`, the card's only scroller (`cardSc()`
  in `app.js`), so a flick or a phone's rubber-band moves the stats and never the plate. Its pieces ride at the top of it
  (the tile, his lines, the filters box), which keeps it short. the blue plate from edge to edge of the window. On a desktop it is
  three columns with equal outer ones, so the middle sits over the middle of the page: the cut-out headshot, name,
  team / position / age, the sample (PA · AB · BBE · G, or IP · BF · G/GS · pitches), "full season" and Star on the
  left, and the season's title (below) centred in the room to their right: one short row. The filters — **From**, **To**,
  **Last PA** (or IP), **Pitchers** (All / vs LHP / vs RHP; Batters for a pitcher) and **Home / away** — sit behind a
  **Filters** button beside "full season", as on a phone: on a desktop it drops a panel under the button (`.phpop`) that a
  click outside or Escape shuts. The toggles are solid buttons on the
  band, so no colour scheme can wash them out. On a phone the plate is laid out tighter: the Star is a ☆ beside the name (by the popup's ×),
  the filters fold behind one **Filters** button beside "full season", and the season's title (below) sits at the foot
  of the plate, pinned with it.
- **The title** (`pageTitle()`), in the plate and pinned with it: "**2026 MLB Percentiles**", bold, in the name's ink.
  The year and the level are the season pickers for the whole page (`titleSelect()`): each is a word over a dotted
  rule.
- **Mix wOBA** (`mixw`, the last bar under Batted-Ball Distribution; Sean, 26 Sep 2026) — what a hitter's batted-ball
  distribution alone is worth, **per ball in play**. Every typed ball in play (bunts out) takes the dataset's average
  wOBA for its bucket — ground ball, popup, and line drives and fly balls each pulled / straightaway / the other way
  (`PULL_LINE`); an air ball with no direction takes its type's average — and Mix wOBA is the average over his. Ground
  balls stay one bucket: split by direction they barely moved it and mostly measured handedness and speed. Walks and strikeouts
  don't enter it (Sean). `consts.mix = {lg: the league's average ball, v: the buckets}` from `pitch_flags()`; day rows
  carry `mixsum` / `mixn`, so windows and splits re-derive it. About .365 is average; this season a pulled fly ball is
  worth ~.85, one to center ~.28, one the other way ~.22.
- **Percentile bars, two looks** (Appearance ▸ Percentile bars, `state.bars`, per device): **Savant charts** (the
  default, below) or **Classic meters**, the older look — `meterRow()` rows with a pale rounded track, a big white-ringed
  bubble, the value bold with its unit, dashed rules between rows and the pool under the sections (`.pctclassic`).
- **The percentile sections** (`renderPctPanel`): two columns of headed sections, drawn by the site's own SVG
  code (`pctSvg`) in the style of Savant's charts. Hitters (`PCT_COLS_H`): Results (wOBA, xwOBA, xBA, xSLG — the expected three the directional model's),
  Batted-Ball Quality, then Swing Decisions (Z-Swing%, O-Swing%, BB%), Contact and Batted-Ball Distribution.
  Pitchers (`PCT_COLS_P`): Whiffs and Strikes, Swing & Miss, Zone & Chase (BB%, Strike%, Zone%, Chase%), then Results
  (K-BB%, ERA), Batted Ball (GB%, Popup%, Mix ERA) and Stuff. His uERA table and batted-ball mix live in the uERA tab
  on a desktop and a phone alike (for a day they sat in a right-hand third beside a desktop's bars; Sean wanted them
  back in the tabs). On a desktop the box is a fixed 860px (`--pbox-w`), centred, so it hugs its two chart columns instead of
  leaving a blank sixth of the window each side; the tabs under it take the same width, and a popup is only a little
  wider (940px, its title on its own row under the headshot and filters). Both columns are drawn at
  one scale, the largest at which the taller one still fits the box (`pctChart`'s `fit`), so type, bars and circles
  grow together; a phone draws them at their real size. A chart starts at the size its column had last time
  (`pctLast`): drawn at a guess and resized a moment later, everything under it shifted and, near the foot of the
  page, the browser pulled the window up — which is what threw a phone's page upward on every tap of a tab.
- **The tabs** (`renderBelow`, `state.pbtab`): **Compare**, **Season Stats**, **Rolling**, **Fantasy**, then **Mix**
  for hitters and **nERA** and **uERA** for pitchers. Clicking the open tab closes it and leaves just the strip (`pbtab: "none"`), with the page's notes
  under it. After any tab is picked, `anchorTabs()` puts the strip back exactly where it was on the screen, padding
  the page under it when what's below got shorter, so nothing jumps.
  - **Compare** turns on the two-side comparison and opens it here, under the stats (`cmpCard`). Its grid is the
    page's own sections for both sides (`cmpPageGrid`), and **Set up comparison** picks each side's season, split and
    dates and which stats sit on the grid — the page's, by section, plus anything from **More stats**, which lands as a
    plain row under "Added" (`state.cmp2.pick`). Nothing folds out.
  - **Season Stats** (`renderSeasonTable`), the look Sean picked: one table, so every column lines up — an **MLB**
    section (Season, Team, one row per season and a career row) over a **Minor leagues** section (Season, **Level** —
    no clubs, Sean isn't after them — one row a year, newest first), each under a heading row and its own header row.
    Every row is one line tall. A traded MLB season reads **TOT** and a minor-league year at several levels just "–" (so
    the column stays a club's width); the ▸ beside that label (not the year) opens it (`SEASON_OPEN`) to each club's line (`HT`/`PT` in
    career.js, kept by `build_career.py`) or each level's. Hitters: **PA HR AVG OBP SLG OPS**. Pitchers: **IP ERA K%
    BB% GB% Popup% uERA** (K% / BB% per batter faced; Popup% is headed PU% to
    leave room between the columns). **uERA** is worked out on the page — opening the table fetches
    each year's MLB season file — and shows on a chip coloured by its percentile in the percentile bars' own colours
    (`paintBar`: Savant's scale, or the heat scale under Classic meters), inset like a leaderboard's sorted-column pill;
    none before 2015 (no Statcast). The career uERA is innings-weighted.
    In the minors it is an **MLB-equivalent uERA** (`milbU`): the level's Whiff%, Strike%, GB% and Popup% are carried up
    to the majors by `MILB_X` (fitted by `tools/models/milb_translate.py`: the same pitchers at two levels in a season,
    2021 on, the shift at each step with the promoted pitcher's lower-level rate first pulled toward his league by its
    reliability, chained A → A+ → AA → AAA → MLB), then uERA is worked out on those rates against that season's MLB
    starters or relievers (by his GS share, with the league's HBP rate), so it reads and colours on the MLB scale. A
    year at several levels is the innings-weighted mix of the levels that have one, when they cover 80% of its innings
    (a stint under a level file's 20-batter floor has no rates; GB% / PU% follow the same rule by batters faced); Rookie ball and short-season A have no
    translation. GB% / Popup% come from career.js / minors.js (appended to each line by `build_career.py`), else from
    the season's own file when it's loaded.
  - **Mix** (hitters, `renderMixTab`): his Mix wOBA taken apart (the bottom line is `m.mixw` and its pool percentile, the
    very numbers on the Batted-Ball Distribution bar). One row per bucket, dearest first — line drives and
    fly balls each pulled / center / oppo, ground balls, popups (and air balls with no direction when he has any) — each with a percentile bar for his share of it among the season's qualifiers
    (a bucket worth more than the league's average ball counts higher-is-better, the rest lower-is-better), the share,
    and the league's wOBA on it on a heat chip from the cheapest (blue) to the dearest (red). Below a rule,
    **Mix wOBA**: those values weighted by his shares, his average ball in play by where and how he hits it, with its
    percentile bar and a chip coloured by that percentile. Counts come from `ctx.mix` (a season) or the
    `mx*` day fields (a window or split), in `build_data.MIX_COLS` order.
  - **Fantasy** (`renderFantasyTab`): his points under a saved scoring preset — the picker lists the fantasy page's
    presets and shares its choice (`fstore.current`), with a link to edit them. Tiles for the season total and points
    per game (ranked among every hitter / pitcher, and per game among those past the fantasy page's minimum), games,
    and for a pitcher who has both started and relieved, points per start and per relief outing. Then the categories
    the preset scores with his count, the weight, the points and the per-game share, and for a pitcher his game log
    (`fantasy.js`'s per-game rows, newest first, the last ten or all). Hitters have season lines only in fantasy.js, so
    no game log. The card's season when fantasy.js covers it (the last three MLB seasons), otherwise the current one.
  - **Rolling** is `renderRolling()`: xwOBA over a hitter's last N PA (K−BB% for a pitcher), 25 to 300. On a phone
    the plot runs from the left edge (no bar column to line up with).
  - **nERA** is the batted-ball luck table (`renderLuckBox`). **uERA** is the uERA table (`renderUeraBox`) and, beside
    it, the batted-ball mix (`renderMixBox`): his GB / LD / FB / Popup shares, each one's rank among the season's
    pitchers in the direction that helps him (more grounders and popups, fewer liners and fly balls), the mix uERA
    actually prices (**uERA uses**: his ground-ball and popup shares, the rest of his air balls split at the league's
    line-drive ratio) and the league's wOBA for each type, with Mix ERA in the heading.

`sizePPage()` puts `body.playerwide` on while a player page is open, which lifts the site's 1240px cap off `.wrap`
and `.top` and leaves `min(6vw, 96px)` on each side — Savant's own proportion — then sizes the percentile box to run
from under the pinned plate to the bottom of the window, less the tab strip so that strip stays on screen. It measures
where the box starts in the **document** (`rect.top + scrollY`), not the viewport: reading the viewport while the page
is scrolled gives a smaller number every time and the box grows with each render. On a phone the height cap is lifted.

**Every dropdown on the site is Savant's** (`ddOpenOn()`): a list hung straight under what was clicked — a white box
inside a heavy dark rule (`--ddline`), the choices in large type — instead of the browser's list or the phone's wheel.
The list is placed on the page itself (fixed, above everything), so no popup, pinned header or sideways-scrolling strip
can clip it or cover it; it follows its opener if the page scrolls, and a pick, a click anywhere else or Escape closes
it. The player page's pickers are built with `ddList()`; the filter pills (`pillSelect()`) open it directly; and any
native `<select>` (Sort by, Rank vs, Draft from, the rankings list, Per page, Add position, the Star list, Scoring) is
kept in the page, hidden, as the source of truth behind a box (`ddSelect()`), so its value and "change" listeners work
as before. The header's **Fantasy** and **Leaderboards** menus use the same look and are moved out of the header
onto the page, because on a phone Safari clipped them to the nav row's sideways scroll.

**The site is regular season only.** Spring-training and postseason datasets can still be built (`build_history.py
spring …` / `post …`), but `indexReady()` takes them out of the search index the moment it loads, so no season picker
anywhere offers one, and a season remembered from before falls back to the regular season.

**A popup card is the player's page** — `renderModal` calls the same `playerView()`, ranked in the list's own pool,
in a panel with an ×. On a desktop the panel is up to 1500px wide and as tall as the window allows, and `sizePPage()`
fits its percentile box to the panel the same way; on a phone it floats over the list, 8px in from the edges and under
the site header, and scrolls inside itself (`.modal.pcard`, `body.cardpop`) while the list stays where it was.

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

`#fantasy` — ESPN-style points scoring, the header's **Fantasy** menu (renamed from "Draft & Fantasy", 26 Sep 2026; it
still holds Draft Mode, Rankings, Draft board and Eligibility). **Scoring settings** holds presets (ESPN standard built
in; make your own from any of ESPN's categories, plus league size). Every view covers 2026 and the two seasons before,
by position / role, with the scoring picked at the top.

- **Leaderboard** (`#fantasy/leaders`): total points, per game (per appearance for pitchers), per AB and per PA
  (hitters), per start, per relief appearance and per IP (pitchers), and **per week** — points over the Monday-to-Sunday
  weeks he played in, so a pitcher who works more often gets credit that per start misses. Filters: **From / To**
  dates, **vs LHP / RHP** (vs LHB / RHB), **Home / Away**, and **Actual / Expected / Both** (hitters) or **Actual /
  Luck-neutral / Underlying / All three** (pitchers). The Min PA / IP box is a full-season number, like the site's own
  leaderboard: a range or split changes the numbers, not who is listed.
- **Trending** (`#fantasy/trending`): the same columns over each hitter's last N PA or last N days (pitchers: last N IP
  or last N days), plus his season points per game and **Trend** (the window's per game minus the season's). Min here
  is playing time inside the window.
- **What if**: unchanged — xPts / uPts, points at a starter's PA per game at the position, and the rank that would give.

How the numbers are made (`fLeadRows` in `app.js`):
- Everything is summed from the **official game logs** in `fantasy.js` (hitters' and pitchers', with home / away on
  every game), so a date range is the real box-score line. Grand slams have no game log and are pro-rated by homers.
- **Handedness** isn't in a box score (a game has both), so each game's line is shared out by that day's Statcast plate
  appearances against each side: hits by hits, total bases by total bases, homers by homers, runs and RBI by wOBA
  production, steals by times on base, everything else by PA (pitchers: batters faced; K / BB / HBP / HR / hits / outs
  by their own). vs L plus vs R adds back to the whole. Per game in a hand split counts the games he faced that side.
- **Expected hitter points (xPts)**: hits and total bases at his directional xBA / xSLG over the same at bats (extra-base
  mix scaled to hit both); runs and RBI moved by his xwOBA ÷ wOBA (production drives both, and the model can't place
  runners; clamped to 0.5–2×); walks, strikeouts and steals as they happened. Over a range or split the rates are his
  Statcast rates over the same games.
- **Pitchers, two ways.** Luck-neutral (**nPts**): K and BB as they happened, earned runs at his luck-neutral ERA, hits /
  homers / total bases moved by what his balls in play were worth at league value for their type against what they
  produced. Underlying (**uPts**): on top of that, K and BB at his uK% / uBB% over the same batters faced, earned runs at
  his uERA, hits scaled to the balls in play those rates leave. Wins, saves, holds and quality starts stay as they
  happened; per start spreads each category over his starts by the same ratios. In a range or split his uK% / uBB% /
  uERA come from his rates there, placed in the full season's pool.

Data: `build_fantasy.py` (part of the daily job) -> `fantasy.js`; `python3 build_fantasy.py 2025 2024` for past years
-> `hist/fantasy-YYYY.js`. Game-log rows drop trailing zeros. `build_data.py`'s day rows carry `hr` (hitters) and `h`
(pitchers) at the end for the hand split; older files fall back to extra-base hits / balls in play.

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
separate from Safari's — connect each one to **Sync** (below) and they share them.

**Sync across devices** (Appearance ▸ Sync across devices; `syncNow()` near the top of `app.js`): the fantasy scoring
presets, stars, drafted players, rankings, tiers and saved ranking sets (`SYNC_KEYS`) are kept in a secret gist on
Sean's GitHub, `sean-site-sync.json` in the gist described "Sean's Site: saved settings (synced by the site)". Each
device is connected once with a GitHub key that has **gist** access only (it can't touch the site), stored in that
browser (`draft2027.sync`). The site pulls when it opens and whenever it comes back to the front, and pushes a few
seconds after anything is saved. Per key, against what was last synced: changed on one side takes that side; changed on
both (or on a device's first connect), the fantasy presets are merged by id and keyed lists by key, this device
winning a clash. A pull that changes anything reloads the page once. Appearance stays per device.

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
