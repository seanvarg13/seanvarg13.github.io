# F — Engineering review (read-only, brief pass)

## 1. Map
Build (GitHub Actions `daily.yml` → `tools/cloud_daily.py`: whats_new gate → build_* → restamp (pack_hist gz, `?v=sha1` stamps, build.json, DRAFT_SIZES) → `check_site.cjs --quick` → commit on main) → Pages.
Browser caches: (a) sw.js cache-first for `?v=` URLs, network-first for index.html; (b) HTTP cache; (c) app in-memory value/pool/rank caches (provisional vs full); (d) localStorage prefs/rankings (+ gist sync); (e) lazy `ensureScript` with 3 tries then `failed` per visit. Staleness control = build.json poll → reload.

## 2. Findings
1. MEDIUM, VERIFIED — sw.js:37 `if (trimming) return; trimming = true;` A put arriving while another trim runs skips the "one copy a file" retirement, so parallel loads after a publish (data.js, days-h/p, app.js all at once) can leave old-stamp copies (12–17 MB day files) until a later put on the same path. Fix: queue trims (a promise chain) instead of dropping them.
2. MEDIUM, VERIFIED — tools/cloud_daily.py:118-119 `return True if code == 0 else False if code == 1 else None` — any exit other than 0/1 (crash, browser missing, timeout kill) is treated as "couldn't run" and publishes unchecked. Fix: only skip on explicit exit 2 with no Node; treat other codes as failure, or require the check in CI.
3. LOW, VERIFIED — sw.js:42 trims by `c.keys()` insertion order; a cache-first hit never re-inserts, so frequently used files (app.js, data.js) are evicted first once >160 entries (hist/lg, c/ buckets add many). Fix: exempt TOP files from trimming or re-put on hit.
4. LOW, VERIFIED — sw.js:32 network-first shell uses `cache:"no-store"` with no timeout; on a flaky (not offline) iPhone link the "instant open" waits the full TCP timeout. Fix: race fetch vs ~3s cached fallback.
5. LOW, SUSPECTED — app.js `ensureScript` marks a file failed for the visit after 3 tries; several readers render a permanent "Couldn't load" only where a retry button exists (season table, spans). Other consumers (similar, lineups, alerts) silently show nothing. Fix: generic retry on `online`/visibility.
6. LOW, VERIFIED — app.js has ~6 bare `.catch(() => {})`/`catch (e) {}`; MLB API fetches (bio, awards, oppLog, postLines) fail to "–" with no telemetry. Acceptable, but log to console.
7. MEDIUM, SUSPECTED — silent bad data: page check only asserts pages draw; nothing asserts value sanity (e.g. the aaa-2022 wOBA>1 incident, stale-checkout career.js that blanked wRC+). Fix: a data sanity step (ranges for league wOBA, row counts per season vs previous build, required fields present) before publish.

## 3. Tests
Exists: tools/check_site.cjs (≈40 headless steps, phone+desktop, script errors/4xx/draw assertions), check.yml on PRs.
Missing (add): unit tests for pure math (`talentCore`, `xbabDrivers`, `neraCounts`, `dayNERA`, `wrc` conversion, Shapley sums equal totals); build↔app parity test (build_career talent_of vs app within 5e-4 — currently ad-hoc scratch); sw.js tests (stamp change retires old copy under concurrent puts; offline shell); whats_new.py with mocked schedule; pack_hist round-trip; data sanity diff vs previous build.
