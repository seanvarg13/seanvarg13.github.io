# C — Hitting talent xwOBA build-up review (read-only)

## 1. Map (app.js / tools/build_career.py)
| Piece | app.js | Python | Inputs / constants | Provenance (CLAUDE.md §8) |
|---|---|---|---|---|
| xK% fit | XKH 1603 | TW_XK 357 | whf .989, zsw −.212, osw −.272, strk .523, c −.08, vs 20+ PA league | 28 Sep, 100+ PA 2015-26 pooled |
| xBB% fit | TW_XBB / TW_XBB0 8304-05 | 359-60 | osw, zsw, ocon, zcon, zsn, ev90, **ibbr**, **fcon** | 12 Oct, held out by season |
| Blend | TW.act 0.5, talentCore 8428 | TW_ACT 368 | K/BB = .5·actual(park-adj) + .5·fit | 11 Oct |
| xHR/FB | TW_HF 8334 (+XHRFB 8280 fallback, hrfbFit) | TW_HF 370 / TW_XHRFB 365 | c .096, evfb 1.364, ev90 .822, pfb .097 | 14 Nov, park-neutral HR target |
| xBABIP drivers | XBAB 8733, XBAB_GBP 8734, xbabDrivers 8471 | TW_XBAB 363-64, xbab_drivers 466 | 9 drivers; spd/gbp scaled by GB share | 10-11 Oct, 2015-26 |
| Extra power | talentCore tphU/tph | talent_of | model xSLG/xBA less xHR, recentred on L.tphA, clamp 1–1.8 | 12 Nov |
| Combine | twRaw (≈8495) | tw_raw 524 | TW weights bb .69 hbp .72 1B .88 2B 1.25 HR 2.03 | fixed |
| Scale | talentLeague L.scale | talent_league L.scale | Σ actual wOBA / Σ raw over 300+ PA, same season | — |
| GB lean | TW_GB 8352, gbAdj | TW_GB 375 | +0.45/pt GB% after scale | 12 Nov |
| Window regression | TW_WIN 8342 | — | **disabled** TW_WIN_ON=false 8343 | 16 Nov (CLAUDE.md 12 Nov entry is stale) |
| Park | rawPk in talentCore; m.pk* from build_data/build_parks | park=True | residuals added to every piece | 15/18 Oct |

## 2. Findings
1. **HIGH – target leakage: actual K%/BB% in "expected"** (VERIFIED). app.js 8428 `const xk = m.k == null ? xkFit : act * (m.k - pkk) + (1 - act) * xkFit`; Python mirrors. Half of two pieces is the outcome itself, so "xwOBA" partly restates wOBA; also xBB% includes `ibbr` (an outcome) and `fcon`. Fix: label as blended/"skill-weighted", or expose a pure-expected variant; don't evaluate same-season r vs wOBA as validation.
2. **MED – scale anchored to same-season wOBA** (VERIFIED). talentLeague: `L.scale = a ? b / a : null` with b = Σ actual wOBA. Same for L.sslg/L.sba (actual SLG/BA), L.xbabip := actual league BABIP, L.tphA from actual SLG, L.hr.hrfb from actual HR. League-level only (no per-player leak), but a partial/early season, a window or the minors inherit current-season outcome levels; "expected" can't disagree with the league's luck. Fix: acceptable for centring; document; for live seasons consider prior-season anchors.
3. **MED – temporal leakage / in-sample constants** (VERIFIED from CLAUDE.md provenance). All weights (XKH, TW_XBB, XBAB, TW_HF, TW_GB, XSLG) fit on 2015-2026 then reported on the same seasons; several reported as "held out by season" but the fixed constants shipped are full-sample, and feature/term selection (e.g. EV90/LD% added then removed, 14→17 Nov) was done on the full set (selection leakage). The directional model (dxslg/dxba feeding Extra power, xBABIP model mean) is trained on 2015-26 including the scored season. Fix: freeze a pre-season fit per season or document as in-sample.
4. **MED – park factors use future seasons** (SUSPECTED, documented). tools/build_parks.py:14 "pools the venue's seasons Y-2..Y (the nearest three when fewer exist)" → early venue seasons (2015-16, new parks 2020/2025) borrow later years; park-aware outcome model trained on 2015-26. Fix: only Y-2..Y, shrink harder when short.
5. **LOW – centring inconsistency in HR piece** (VERIFIED). talentCore: `xhf = L.hr.hrfb + (ev ? TW_HF.c : 0)` then terms centred on `L.twh` (PA-weighted) while base HR/FB is FB-weighted; constant .096 patches the gap. Drift if PA/FB weighting diverges by season. Fix: centre both on one weighting.
6. **LOW – CLAUDE.md stale** (VERIFIED): 12 Nov entry says window final numbers regressed by TW_WIN; code 8343 `TW_WIN_ON = false`. 14 Nov EV90/LD% terms in TW_GB were removed 17 Nov (gbParts still lists ev90/ld but filters by TW_GB — harmless).
7. **LOW – app vs Python mismatches** (VERIFIED, minor):
   - Python talent_of reads `m["dxslg"]`; app reads `m.dxslgm ?? m.dxslg`. Equivalent on raw season files only; fine for build, breaks if Python is ever fed V()-style rows.
   - Python xK uses its own k20 league (L["k"]); app uses `xKFrom(m)`/lgRatesH (same 20+ PA population — verify null handling: Python returns None if any XK input missing, app xKFrom behaviour determines null). 
   - Python never computes L["slg"]/L["iso"]/L["slgA"] (app-only display fields) — OK.
   - Both default unknown `bats` GB-pull weight to −0.95 (match).
8. **LOW – null/division** (VERIFIED safe mostly): `(I.pa - I.ab) / I.pa` guarded by `!I.pa` early return; `twRaw` divides by `(1 - i)` (i<1 always); `tphU` denom `Math.max(1, …)` hides tiny-hit samples (window with <1 expected non-HR hit silently gives an extreme tphU, then clamped 1–1.8). `bip = max(0, 1 − xk − xbb − hbp)` clamps silently. In driversOf hbp passed 0 (only affects inputs not used by drivers) — fine.
9. **LOW – methodology**: GB lean (TW_GB) is fitted on the residual wOBA − xwOBA (i.e. fitted to actual outcomes), another outcome-tuned term; next-season check reported, acceptable but in-sample.
