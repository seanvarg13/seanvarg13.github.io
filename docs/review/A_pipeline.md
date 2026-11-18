# A. Data pipeline review (read-only, quick pass)

## 1. Map
- Sources: pybaseball Statcast (pitch level), Savant leaderboards (air/pull-air, bat speed, sprint, expected stats), MLB Stats API (people, ER, logs), Savant minors + Gameday (build_milb). Season `SEASON=2026` (build_data.py:21), `GAME_TYPES={"R"}` (:25); build_history re-runs per season 2015-25.
- wOBA bookkeeping: `ZERO_NUM` (ROE/FC/FC-out → num 0, den 1, :84), `EXCLUDE` (sac_bunt, truncated_pa, catcher_interf, intent_walk → 0/0, :85); applied identically in pitch_flags (:1174-1183), pa_outcomes (:1265-1270), pa_rows (:1500-1505).
- Pull angle: `degrees(atan2(hc_x-125.42, 198.27-hc_y))`, negated for stand=R (:1145-1146, dup :1449); `PULL_LINE=16` (:102). Switch hitters handled per pitch via `stand`.
- Mix buckets (gb, pu, ld/fb × p/c/o/x) priced at dataset's own per-bucket mean wOBA (:1160-1190) → `consts.mix`.
- league_constants (:1992): lgERA (official ER / Statcast IP, ER-matched pitchers), FIP C, SIERA shift, bbw per type + `air`, lgwOBA, pa9, wbb/whbp; all from the same season being scored.
- neutral_era (:2024): wnum − wK − wBIP + typed BIP × league type wOBA, untyped at `ut`, onto ERA scale.
- Parks (build_parks.py): residuals vs a park-blind model trained on all 2015-now; venue-season factors pooled Y−2..Y (:161) or the nearest 3 seasons (:163), shrunk n/(n+k).
- Ships in data.js: meta (card layout, weights, consts, dayFields), players {m, ctx}; day rows to days-h/p.js.

## 2. Hardcoded constants (provenance)
| const | where | note |
|---|---|---|
| SEASON 2026 | build_data.py:21 | must be bumped yearly by hand |
| CONST_MIN_BF 20 | :29 | league constants pool |
| ZERO_NUM / EXCLUDE | :84-85 | site's own bookkeeping choice |
| PULL_LINE 16 | :102 | "matches Savant best" (unverified here) |
| 125.42 / 198.27 | :1145, :1449 | standard Statcast home-plate coords (community convention); duplicated |
| venue map | build_parks.py:48-51 | hand-entered park configurations |
| VENUE window y−2..y | build_parks.py:161 | includes target year |

## 3. Findings
1. **HIGH – park factors leak the target season and later seasons (VERIFIED).** build_parks.py:161 `win = [z for z in avail if y - 2 <= z <= y]` includes season y itself; :163 fills short windows with the *nearest* seasons, including future ones (e.g. a 2025 venue pools 2025-26; 2015 pools 2015-17). The outcome model and the cells are trained on every ball 2015-now (header :5, `cells(D)`), so every historical park residual/cell is in-sample. Matters: park-neutral BABIP/HR/FB and the "park-neutral" xwOBA are then used in forecast tests (CLAUDE.md claims next-season r gains) — those gains are partly leakage, and a single season's own luck partially gets absorbed into "park". Fix: for display keep it, but for any backtest build factors from seasons < y only (prior-window), and fill new venues only backward.
2. **MED – league constants / bucket values are same-season (VERIFIED, by design).** league_constants (:1992) and MIX (:1160-1190) price a season with its own outcomes (incl. the player's own BIP). Fine for description; it makes nERA/Mix wOBA "in-sample" and early-season values noisy (MIX from a few weeks). Fix: blend early-season constants with prior season(s) weighted by sample; never use these in "predictive" claims without a lag.
3. **MED – nERA denominators inconsistent (SUSPECTED).** neutral_era removes `wK` from the numerator but leaves the strikeout-reached PA in `wden` (fine) — however `pa9` (:2009) is BF-based (includes IBB, CI, truncated) while `wden` excludes IBB/sac bunts; the wOBA→runs scale therefore mixes PA definitions. Small (~1-2%) but systematic for high-IBB relievers. Fix: compute pa9 from Σwden or scale per wden.
4. **MED – IBB in xwOBA set to league average (VERIFIED)** pa_rows :1532-1537: `xnum = lg` for IBB with den 1, while wOBA (EXCLUDE) drops IBB entirely. Hitter xwOBA and wOBA are on different PA bases; feared hitters' xwOBA−wOBA gap is shifted by ~(IBB/PA)·(lg−0). Fix: drop IBB from both or include in both.
5. **LOW – untracked BIP dropped from xwOBA denominator (VERIFIED, :1534-1536).** Untracked balls (common 2015 and in 2020/Hawk-Eye transition parks, and minors) are removed from xwOBA but kept in wOBA; biased if untracked BIP aren't random (weak contact more often untracked in 2015). Fix: impute with type/spray-based value (bb_type exists) instead of dropping.
6. **LOW – inconsistent `pa` definitions (VERIFIED).** pa_outcomes :1278 `~ev.isin([trunc, CI]) | ev.eq(CI)` (= ~truncated) vs pa_rows :1513 `~ev.isin(["truncated_pa"])` — equal, but the first is confusing; and AB in pa_outcomes (:~1286) `PA−BB−HBP−SF` omits sac bunts and CI, overstating AB vs NON_AB (:233) used in pa_rows. Inflates AB, depresses AVG/SLG slightly for bunters. Fix: use NON_AB everywhere.
7. **LOW – bunt detection by description text (VERIFIED :1172)** `des.str.contains("bunt")` — fine, but `fin` uses `bbt` and EXCLUDE only; sac_bunt already excluded, bunt singles removed by text. Gameday minors `des` formats may differ → minors Mix values include bunts. Suspected.
8. **LOW – 2020 short season / 2023 shift ban.** No per-season handling beyond centring in constants; pull/GB values computed per dataset so shift-ban changes are absorbed (OK). 2020 60-game handled only in downstream minimums (CLAUDE.md), not in build_data's MIN_* (SUSPECTED, not checked).
9. **LOW – pitch-type misclassification** (e.g. old sweepers relabelled by Savant) is taken as-is; pitch-type-relative Stuff+ baselines inherit relabel drift across seasons (SUSPECTED).
10. **LOW – whats_new/gate timezone.** whats_new.py:106 uses NY "yesterday"; daily.yml:97 gate 3:00/4:40 NY. Late West-coast games final after midnight ET are dated the prior day, so fine; a doubleheader/suspended game resumed later dates by original game_date and may be missed by the "final after last built day" test (SUSPECTED).
11. **INFO – duplicated spray formula** (:1145 and :1449) — risk of drift; factor into one helper.

Not reviewed in depth: build_milb.py, cloud_daily.py adopt/re-run logic, build_history.py.
