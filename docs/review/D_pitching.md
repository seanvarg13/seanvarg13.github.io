# D — Pitching metrics review (app.js, read-only)

## 1. Map (constants, file:line, provenance)
- xLevel (league actual−expected shift per dataset, per pitch type ≥2000 swings/BIP) app.js:466; xAdj 494; LOC_K=70 ~491; cmdOff 493.
- stuffFrom 586, locDelta 598, pitchingFrom 609, stuffPlusLoc 634 (build-side grades, CLAUDE §4 3 Oct).
- UKF 1571 / UBB 1587 (ridge by role, 2020-26, "scratch" fits; not in repo). rateFit 1638 (swaps pitch/sloc → pitch0/sloc0 when cmdp).
- impliedKBB 1687; CMD_K=150 1713; XBBF {61.762,-.545,-.026,-.229} 1714 (scratch bbstrk.js); XKM 1747 (ridge, actual rates incl. Foul%).
- underlyingERA 1828; expectedNERA 1846; xneraShift 1992 (pool BF-weighted mean nERA − xnERA); xnera per-pitcher 2122.
- Command+/Pitching+ rewrite in V(): 1310-1318. KCONV 9872. arsDayFields "gs" handling 9667.
Provenance: every fitted constant cites scratch scripts outside the repo — not reproducible (UNVERIFIED by me).

## 2. Location+ / Pitching+ today
- When count-state rates exist (cmdp true, 1318): m.sloc = Command+ (XBBF-based walk value, shrunk BF/(BF+150)), m.pitch = Stuff+ + Command+ − 100, m.pbb = sbb+cm−100; old location-model values kept as m.pitch0 / m.sloc0. So **Location+ is no longer shown** for modern files; the "Command+" label (10172) occupies its slot. Older/minor files (cmdp false) still show the location-model Pitching+/Location+ — same column, two different definitions across seasons. VERIFIED.
- Per pitch (xAdj off≠null): pitp = stuffp + pitcher-level Command+ offset — every pitch gets the same command, so per-pitch Pitching+ is just Stuff+ shifted. Works, but "Cmd+" per pitch is not per-pitch information. VERIFIED.

## 3. Findings
1. HIGH target leakage — Command+ (1314-1315) is built from actual Strike%/1st-pitch/3-ball strike rates; these are near-outcome (3-ball strike rate ≈ walk avoidance). Pitching+ (1318) therefore mixes a stuff model with an actual-rate walk proxy and is presented as a model grade. Fix: label as process/actual, or use the command model's expected strike rates. VERIFIED.
2. HIGH leakage in "expected" K: XKM (1747) uses actual Whiff%, CSW, SwStr, 2-strike Whiff%, Foul% (Foul weight 1.56) — same-season fit, so K%−xK% is near-pure residual; CLAUDE admits it. xnERA uses xKStuff with actual Strike%/swing rates and XBBF (actual strike rates) for BB (2122) — "expected" nERA is half actual. Fix: document as descriptive, or drop actual inputs. VERIFIED.
3. MED centering on same-season actuals: xLevel shifts expected rates by the current season's actual−expected gap (466-489) and xneraShift forces pool mean xnERA = mean nERA (1992). Fine for level, but on a partial season (April) the shift is noisy and leaks the season's outcomes into every pitcher's expected rate. Fix: use prior-season shift or cap early. VERIFIED (logic), impact SUSPECTED.
4. MED rateFit (1641) feeds pitch0/sloc0 to UKF/UBB because fits were trained on them, while V() otherwise reports the new numbers — consistent only if pitch0 exists; for cmdp false pitch is already the location value. OK, but fragile. VERIFIED.
5. MED Command+ pulled to 100 by BF/(BF+150) but xb(L) uses lgRatesP() of the current view; in a window lgRatesP changes → Command+ shifts for everyone. SUSPECTED.
6. LOW underlyingERA (1838): bip = max(0, pa−K−BB−HBP) uses PAw incl. intentional/truncated adjustments; HBP counted from season ctx in a window if HBP not windowed. SUSPECTED.
7. LOW duplicate key "gs" in arsDayFields: handled at 9667 via ARS_F.indexOf("gs") (first = started flag) and Object.fromEntries keeps last (= chance sum). Works, VERIFIED, but any new code using I.gs gets the chance sum — rename on next rebuild.
8. LOW xLevel fallbacks: types under 2000 n get league shift (`out[k]`) silently; xfoul uses only league f (no per-type). VERIFIED.
9. Survivorship: pools/fits use 100+ BF (fits) and 20+ BF (xLevel, xneraShift uses pool list) — xneraShift weights only listed pool pitchers, so changes with Min IP filter. VERIFIED (1992 uses `list`).
Not reviewed in depth: FIP/SIERA constants, placeIn, Rating weights.
