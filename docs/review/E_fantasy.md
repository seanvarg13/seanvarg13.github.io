# E — Fantasy layer review (read-only)

## 1. Map
- **Scoring → points**: `FCATS` (app.js:6811) lists categories; `fDerive` (6949) fills derived stats (TB, QS…); `fPts(w, line)` = Σ weight × category. Preset from `fpreset()`; any change bumps `fantGen`.
- **Actual points (Leaderboard)**: `fantFill` (1414) scores the official line (`fantasy.js`) plus game logs for G / PA / AB / weeks / GS. Full regular season of the last three MLB seasons only; it nulls under a window, split, span or minors.
- **xPts**:
  - Hitters (`fXLine` 7033): H / TB from dxBA / dxSLG, R / RBI / GWRBI × clamp(xwOBA / wOBA, .5, 2).
  - Pitchers (`fPLines` 7056): ER at nERA; H / HR / TB × league-value-of-mix / actual-value-of-mix.
  - `fSpread` (7043) spreads the line back over his games.
- **2027 projection**: `tools/build_proj27.py` Marcel feeds `hist/proj-2027.js`. `build_offseason.py proj` overlays Steamer (and ZiPS when asked); Marcel fills the rest.
- **Rankings order**:
  - `projPts` (1500): the proj line under the current preset, when `J.systems` is set.
  - Otherwise `boardProj` (1492): a hitter's xwOBA; a pitcher's nERA regressed with NREG.k = 80 IP of the league (`neraLeague`, 20+ IP).
- **Mock draft** (`mkPool` 13668):
  - Proj = the proj line under the room's preset.
  - Ohtani's pitcher entry is folded into his hitter entry.
  - VOR comes from `mkVOR` (13753). The ADP is the weighted median of the lists in `hist/adp-2027.js`; the projection only places unlisted players, at max(prank, min(deep, prank + 60)).
- **Replacement / positional adjustment** (`mkVOR`):
  - Greedy fill by points into slots in priority C, SS, 2B, 3B, 1B, OF, MI, CI, UTIL, SP, RP, P, then the bench.
  - Replacement per slot = the best unused player who fits.
  - A player's base = the min replacement over his eligible slots, so he is valued at his most generous position.
- **Auction $**: `mkCurve` (13776) maps the ADP rank to the curve `MK_TOP` + `MK_MKT.prices` (Sean's 2026 room, 14 × $200 × 25 spots), rescaled to T × B over $1 a spot. `mkDollars` (13789) prices by ADP rank, not projection. Inflation is `mkInflation` (13809, clamped .6-1.6) in the mock room and `aucValues` (5064, clamped .5-2) in Draft mode.
- **Lineups / playing time**: `build_lineups.py` writes starts, roster G, PA/G (= PA / games played) and slot; `luOf` / `lineFill` read them for the display columns only. Nothing in projections uses them.
- **Bullpens** (`bullpenRows` 6044): roles and leash from the window's game logs. Not deeply audited.

## 2. Key constants
| constant | where | provenance |
|---|---|---|
| WH 5/4/3, WP 3/2/1 | build_proj27.py:22 | Marcel default (hitters 5/4/3; pitchers 3/2/1) |
| regression 1200 wPA / 600 wOuts | build_proj27.py:91, ~148 | Marcel-ish (true Marcel: 1200 PA, 134 IP×3 not weighted outs) |
| age +0.6%/yr <29, −0.3%/yr >29 | build_proj27.py:71-73 | hand-set |
| PT: .5·PA26+.1·PA25+200, ≥.85 avg of two 450+ seasons, ≥560 young regular, ×.92 at 35+, cap 700 | :117-123 | hand-set |
| SP PT: .5·IP26+.1·IP25+60, ≥140 if ≤29 and 12+ GS, cap 200; RP cap 72 | :163-171 | hand-set |
| H/TB, ER halfway to Statcast | :94-110, ~151 | hand-set 0.5 |
| NREG k 80, min 20 | app.js:1487 | backtest per CLAUDE.md (r .40→.46) |
| rr clamp [.5, 2] | app.js:7036 | hand-set |
| MK_MKT / MK_TOP | app.js:13770-13771 | Sean's 2026 auction + hand smoothing |
| inflation clamps .6-1.6 / .5-2 | 13814 / 5071 | hand-set |
| Ohtani fold threshold 50 pts | 13686 | hand-set |
| unlisted ADP cap +60 | ~13716 | hand-set |

## 3. Findings

1. **HIGH: Marcel drops anyone without a 2026 line. VERIFIED.**
   - Where: build_proj27.py:87 `for pid in L[YEARS[0]]:` (and the pitcher equivalent).
   - Why: a player who missed all of 2026 with injury gets no projection, so he disappears from the Mock draft pool (`mkPool` skips anyone without `a`) and from `projPts` / Rankings. Steamer overlays only players Marcel already knows unless build_offseason adds new ids (not verified).
   - Fix: iterate the union of ids across 2024-26, and apply a PT discount for missed time.

2. **MED: the playing-time formula is inconsistent with the rates.**
   - The rates are weighted 5/4/3 but PT is .5/.1 + 200 PA. A part-timer with 100 PA in 2026 gets 250 PA.
   - Hitter G = t / clamp(PA/G, 3, 4.4) is fine.
   - Pitchers: `role_of(last)` decides the SP/RP league rate and the PT model from the 2026 role alone, and PT ignores 2024. A starter moved to the pen late gets RP-capped at 72 IP. VERIFIED from code; impact by judgment.

3. **MED: the age adjustment is applied to every "good" category multiplicatively, including counting stats per out (W, QS, SV, HD).** Aging role and team stats is dubious; SV/HD are role, not skill. SUSPECTED methodology flaw, build_proj27.py:111-113 / ~158.

4. **MED: Marcel regresses to the league rate of all hitters pooled** (lg over every hitter, PA-weighted, ~:80). Bench and replacement players drag the prior, and SV/HD for pitchers regress toward the role's league mean per out. That's acceptable, but RP SV rates regress toward a pool where most RPs have 0 saves, so closers are under-projected. SUSPECTED.

5. **MED: Ohtani in the Mock draft — the folded value may be double counted relative to roster cost. VERIFIED behaviour.**
   - Where: app.js:13684-13688 adds the pitcher points to the hitter entry, which fills one hitter slot.
   - Why: in ESPN, Ohtani is one player too, so his value per roster spot is correct. But `mkVOR` uses the hitter replacement level only, so his pitching value is compared to zero, not to P replacement, which inflates his VOR by roughly the P replacement's points.
   - Fix: VOR = (hit − hit repl) + (pit − P repl), or `max(...)`, depending on the league's lineup rules.
   - Meanwhile `projPts` (Rankings) and `lgItem` handle Ohtani differently (separate rows vs summed). That is inconsistent across pages.

6. **MED: mkVOR uses greedy priority filling, not optimal assignment** (13756-13758). A C/1B-eligible star is consumed by C first, which can leave 1B replacement artificially low or high. The base, min over eligible slots of repl, then rewards multi-position players with the scarcest slot's replacement even when they would never play there. That's standard-ish, but the greedy fill makes replacement order-dependent. SUSPECTED inaccuracy; fix by matching with `mkAssign` or a per-slot top-N.

7. **LOW-MED: auction $ ignores the projection.**
   - `mkDollars` prices by ADP rank, not VOR (13789-13791), so a player the lists overrate gets top dollars and inflation (`mkInflation`, `aucValues`) inherits it.
   - This is by design (Sean asked for it), but `aucValues`' "worth" (`slice(0, open)` in ADP order) assumes the ADP order of remaining players.
   - Flag it as a methodology limit.

8. **MED: stale caches. SUSPECTED.**
   - `mkPool` cache sig = [scoring, teams, roster] (13671). It doesn't include whether `DRAFT_ADP27` / `DRAFT_PROJ27` are loaded or their versions. A pool built before ADP arrives (no votes → projection order) is reused until the scoring or room changes. `aucValues` guards with `mkReady`; other callers of `mkP` / `mkPool` (e.g. the Mock setup screen) may not.
   - `lgProjCache` keys on league id only (14481). If the league's scoring changes on refresh (or the preset is re-mapped), the projections stay stale until reload.
   - `projPtsCache` keys on `fpreset().id` + `fantGen`: fine provided every weight edit bumps `fantGen`.

9. **MED: xPts input leakage (hitters). VERIFIED by reading.**
   - `fXLine` scales R/RBI by xwOBA / wOBA (7036). The site's xwOBA (talent build) carries half his actual K% and BB%, and since 18 Oct his actual parks. So the "expected" partly contains outcomes, and the ratio is bounded [.5, 2] but unregressed.
   - Under a date window it reads `xwdW` (the unregressed window number, deliberately), so small windows give noisy xPts.
   - H/TB use `dxba` = the batted-ball model, whose past-season level is off by up to 18 BABIP points (CLAUDE.md 23 Oct note). Past-season xPts carry that league-wide offset.
   - Fix: re-anchor xBA/xSLG per season, as `dirInfo` does; or score xPts on park-neutral talent.

10. **LOW: pitcher xPts (nPts) leave K, BB, W, SV, QS actual.** Only ER/H/HR/TB are neutralized (7066), so "expected" points for a pitcher are mostly actual. QS isn't recomputed from neutral ER. Methodology limit; note it in the UI.

11. **LOW: division and zero guards.**
    - `fXLine` returns null without AB.
    - `fantFill`'s `per()` guards n = 0.
    - `fpgs` guards `st.length`.
    - `fSpread` uses `o.OUTS` (falsy → 0).
    - `mkCurve`'s `sum ? … : 0` is OK.
    - `fPLines`' `br` is 1 when act = 0.
    - No crash found.
    - `mkPool`'s role uses `o.G || 1`. OK.

12. **LOW: `boardProj` mixes scales.** A hitter's raw xwOBA is unregressed, while a pitcher's nERA is regressed by 80 IP. Hitter boards still float tiny-PA hitters with unregressed talent xwOBA. The CLAUDE.md 20 Oct note says the 10-PA problem was fixed by xwOBA proj., which was later removed (25 Oct).
    - Where: app.js:1492.
    - Fix: regress xwOBA by PA (e.g. 250 PA at league − .030, as the deleted `TW` did) when `projOn()` is false. VERIFIED regression in behaviour.

13. **LOW: `neraLeague` cache key `DS.key:viewKey()` never clears.** It's fine unless the data reloads in-session after a publish; a page reload handles that.

## Not audited in depth
- `build_offseason.py` averaging and id matching.
- `build_lineups.py`.
- `bullpenRows` leash logic.
- `fDerive` / `FCATS` mapping to ESPN stat ids.
