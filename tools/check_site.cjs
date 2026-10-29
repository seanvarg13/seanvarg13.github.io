#!/usr/bin/env node
// The page check (Sean, 20 Oct 2026, item 4 of the recommendations: "an automatic page check, phone and desktop, that blocks anything that
// errors"): every page and card tab of the site as it stands in this folder, opened in headless Chrome at a phone's size and a desktop's. A step
// fails on a script error, on a file of ours that comes back missing (a 4xx / 5xx on the site's own address), or on a page that draws nothing.
// Run on every pull request (.github/workflows/check.yml) and by cloud_daily.py before each publish, which stops when a page breaks.
//
//   node tools/check_site.cjs [--quick]
//
// exit 0: every step passed · 1: a page broke · 2: the check itself couldn't run (no browser) — cloud_daily publishes on 2 and says so
const fs = require("fs"), path = require("path");
const { serve, launch, PHONE, DESK } = require("./headless.cjs");
const ROOT = path.resolve(__dirname, ".."), QUICK = process.argv.includes("--quick");
const OK_404 = /\/api\/status$/;   // serve.py's endpoint (the Mac's local server); a static host answers 404 and the page carries on

// a minor-league hitter with no MLB line this season, for a minors card
function minorsId() {
  try {
    const d = fs.readFileSync(path.join(ROOT, "data.js"), "utf8"), meta = JSON.parse(d.slice(d.indexOf("= {") + 2).trim().replace(/;$/, "")), y = meta.meta.season;
    const mlb = new Set(meta.players.filter((p) => p.type === "H").map((p) => p.id));
    const f = path.join(ROOT, "hist", `aaa-${y}.js`); if (!fs.existsSync(f)) return null;
    const t = fs.readFileSync(f, "utf8"), ds = JSON.parse(t.slice(t.indexOf("] = {") + 4).trim().replace(/;$/, ""));
    const p = ds.players.find((q) => q.type === "H" && !mlb.has(q.id) && (q.pa || 0) >= 300);
    return p ? p.id : null;
  } catch (e) { return null; }
}

(async () => {
  let browser, srv;
  try { ({ srv } = await serve(ROOT)); } catch (e) { console.error("check_site: no server: " + e.message); process.exit(2); }
  const base = `http://127.0.0.1:${srv.address().port}/`;
  try { browser = await launch(); } catch (e) { console.error("check_site: no browser: " + e.message.split("\n")[0]); srv.close(); process.exit(2); }
  const mid = QUICK ? null : minorsId();
  let failed = 0, steps = 0;
  for (const [name, vp] of [["phone", PHONE], ["desktop", DESK]]) {
    const ctx = await browser.newContext(vp), pg = await ctx.newPage(), errs = [];
    // pictures and fonts from elsewhere aren't the site's to check, and they slow it down; MLB's API (a bio, a game log) stays
    await pg.route(/^https?:\/\//, (r) => { const q = r.request(); return !q.url().startsWith(base) && ["image", "font", "media"].includes(q.resourceType()) ? r.abort() : r.continue(); });
    pg.on("pageerror", (e) => errs.push("script error: " + e.message.split("\n")[0]));
    pg.on("response", (r) => { const u = r.url(); if (u.startsWith(base) && r.status() >= 400 && !OK_404.test(u.split("?")[0])) errs.push(`HTTP ${r.status()} ${u.slice(base.length).split("?")[0]}`); });
    const hash = async (h) => { await pg.evaluate((x) => { location.hash = x; }, h); await pg.waitForTimeout(300); };
    // poll for a page's content, giving up at once when the page has thrown (a broken page shouldn't cost a minute's wait)
    let stepAt = 0;   // errs' length when the step began
    const until = async (fn, arg, ms = 60000) => { const t0 = Date.now();
      for (;;) { if (await pg.evaluate(fn, arg).catch(() => false)) return;
        if (errs.slice(stepAt).some((e) => e.startsWith("script error"))) throw new Error("gave up waiting after the error");
        if (Date.now() - t0 > ms) throw new Error(`timed out after ${ms / 1000} s`); await pg.waitForTimeout(250); } };
    const count = (sel, n, ms) => until(([s, k]) => document.querySelectorAll(s).length >= k, [sel, n], ms);
    const clickAll = async (sel) => { const n = await pg.$$eval(sel, (a) => a.length); for (let i = 0; i < n; i++) { await pg.evaluate(([s, k]) => { const b = document.querySelectorAll(s)[k]; if (b) b.click(); }, [sel, i]); await pg.waitForTimeout(500); } return n; };
    // a Similar name in the Leaderboard's popup opens him in the popup, the × still there (Sean, 21 Oct 2026: under a last-N-PA window it drew his
    // old-style card under the popup, out of sight; with no window it went to his full page, which has no ×)
    const simTap = async () => { await count("#xboard.xpop .simname", 1, 60000);
      const who = await pg.evaluate(() => { const b = document.querySelector("#xboard.xpop .simname"), w = b.textContent.replace(/ '\d\d$/, ""); b.click(); return w; });
      await until((w) => { const n = document.querySelector("#xboard.xpop .pgbname"); return !!(n && n.textContent.startsWith(w) && document.querySelector("#xboard.xpop .xpopx") && document.getElementById("modal").hidden && document.querySelector("#xboard.xpop table.sbt tbody tr")); }, who, 90000); };
    const prefs = async (patch) => { await pg.evaluate((p) => { let o = {}; try { o = JSON.parse(localStorage.getItem("draft2027.prefs") || "{}"); } catch (e) {} Object.assign(o, { v: 2 }, p); localStorage.setItem("draft2027.prefs", JSON.stringify(o)); }, patch); };
    const step = async (label, fn) => {
      steps++; const n0 = stepAt = errs.length, t0 = Date.now(); let thrown = null;
      try { await fn(); } catch (e) { thrown = e.message.split("\n")[0]; }
      const bad = errs.slice(n0).concat(thrown ? [thrown] : []);
      if (bad.length) failed++;
      console.log(`${bad.length ? "FAIL" : "ok  "} ${name.padEnd(7)} ${label.padEnd(28)} ${((Date.now() - t0) / 1000).toFixed(1)} s${bad.length ? "  — " + [...new Set(bad)].slice(0, 4).join(" | ") : ""}`);
    };
    await step("home", async () => {
      await pg.goto(base + "#home", { waitUntil: "load", timeout: 120000 });
      await count("#hub .hsec table", 6, 90000);
      await until(() => !/Loading game-by-game/.test(document.querySelector("#hub").innerText), null, 120000);
    });
    await step("leaderboard, hitters", async () => { await hash("#leaderboard"); await count("#rows > li.row", 20);
      // the filters are a row of buttons, one per page, each opening its own dropdown (25 Oct 2026)
      await count("#tbtns .sbviews .sbview", 5);
      for (const k of ["positions", "stats", "dates"]) { await pg.evaluate((p) => document.querySelector('#tbtns [data-panel="' + p + '"]').click(), k); await until(() => !document.getElementById("pop").hidden); }
      await pg.evaluate(() => document.querySelector('#tbtns [data-panel="dates"]').click()); await until(() => document.getElementById("pop").hidden);
      if (await pg.$("#pagerbot .pbtn[title='Next page']:not([disabled])")) { await pg.evaluate(() => document.querySelector("#pagerbot .pbtn[title='Next page']").click()); await until(() => { const c = document.querySelector("#pagerbot [aria-current]"); return c && c.textContent === "2"; }); } });
    await step("leaderboard, pitchers", async () => { await prefs({ pos: "SP" }); await pg.reload({ waitUntil: "load" }); await count("#rows > li.row", 20); });
    if (!QUICK) {
      await step("leaderboard, last 100 PA", async () => { await prefs({ pos: "ALL" }); await pg.reload({ waitUntil: "load" }); await hash("#home"); await count("#hub .hsec .hmore", 2);
        await pg.evaluate(() => { const a = [...document.querySelectorAll("#hub .hsec")].find((s) => /Trending/.test(s.innerText)); a.querySelector(".hmore").click(); });
        await until(() => location.hash === "#leaderboard"); await count("#rows > li.row", 10, 120000);
        await pg.evaluate(() => document.querySelector("#rows > li.row .name, #rows > li.row .who").click()); await count("#xboard.xpop table.sbt tbody tr", 1, 60000);
        await simTap(); await pg.keyboard.press("Escape"); await until(() => !document.querySelector("#xboard.xpop")); });
      await step("leaderboard, 2025", async () => { await prefs({ pos: "ALL", lbDs: "mlb-2025" }); await pg.reload({ waitUntil: "load" }); await count("#rows > li.row", 20, 90000); await prefs({ lbDs: null }); });
      // a finished season's day rows are stored gzipped (tools/pack_hist.py): a 2025 starter's game log reads hist/days-2025.js.gz
      await step("a 2025 game log (gzipped)", async () => { await prefs({ pos: "SP", lbDs: "mlb-2025" }); await pg.reload({ waitUntil: "load" }); await count("#rows > li.row", 20, 90000);
        await pg.evaluate(() => document.querySelector("#rows > li.row .name, #rows > li.row .who").click()); await count("#xboard.xpop table.sbt tbody tr", 1, 60000);
        await pg.evaluate(() => { const b = [...document.querySelectorAll("#xboard .btabs .btab")].find((x) => /Game Logs/.test(x.textContent)); if (b) b.click(); });
        await count("#xboard table.glbt tbody tr", 3, 90000);
        await pg.keyboard.press("Escape"); await until(() => !document.querySelector("#xboard.xpop")); await prefs({ pos: "ALL", lbDs: null }); });
      await step("a player popup", async () => { await pg.reload({ waitUntil: "load" }); await hash("#leaderboard"); await count("#rows > li.row", 20);
        await pg.evaluate(() => document.querySelector("#rows > li.row .name, #rows > li.row .who").click()); await count("#xboard.xpop table.sbt tbody tr", 1, 60000);
        await simTap(); await pg.keyboard.press("Escape"); await until(() => !document.querySelector("#xboard.xpop")); });
      await step("rankings", async () => { await hash("#rankings"); await count("#rows li", 5); });
      await step("draft mode", async () => { await hash("#draft"); await count("#rows li", 5); });
    }
    await step("pitching+ board", async () => { await hash("#pitches"); await count("#pitchboard table tbody tr", 20); });
    if (!QUICK) await step("movers", async () => { await hash("#movers"); await count(".flawpage table tbody tr", 1, 120000);
      await pg.evaluate(() => document.querySelector(".flawpage table tbody tr .pbname").click()); await count(".fxwin", 1);
      // his name in the flaw popup opens his page as the Leaderboard's popup over Movers, the flaw popup gone (23 Oct 2026)
      await pg.evaluate(() => document.querySelector(".fxwin .fxname").click()); await count("#xboard.xpop table.sbt tbody tr", 1, 60000);
      await until(() => !document.querySelector(".fxwin") && !!document.querySelector("#xboard.xpop .xpopx")); await pg.keyboard.press("Escape"); await until(() => !document.querySelector("#xboard.xpop"));
      // the pitchers and a position through the Position pill (23 Oct 2026), then back, so the next run starts where this one did; a pitcher's row opens the popup too
      for (const sd of ["All pitchers", "SS", "All hitters"]) { await pg.evaluate((t) => { document.querySelector(".fxbar .pill").click(); [...document.querySelectorAll(".ddmenu .ddi")].find((x) => x.textContent === t).click(); }, sd);
        await until((t) => document.querySelector(".fxbar .pill")?.textContent.trim() === t && document.querySelectorAll(".flawpage table tbody tr").length > 0, sd, 120000);
        if (sd === "All pitchers") { await pg.evaluate(() => document.querySelector(".flawpage table tbody tr .pbname").click()); await count("#xboard.xpop table.sbt tbody tr", 1, 60000);
          await until(() => location.hash === "#movers" && !document.querySelector("#xboard .pbback")); await pg.keyboard.press("Escape"); await until(() => !document.querySelector("#xboard.xpop")); } } });
    // Bullpens (28 Oct 2026): the overview's 30 teams, one team's pen through the Team pill, a name's popup, back to every team
    if (!QUICK) await step("bullpens", async () => { await hash("#bullpens"); await count(".bppage table tbody tr", 20, 120000);
      for (const [tm, n] of [["NYY", 5], ["All teams", 20]]) { await pg.evaluate((t) => { document.querySelector(".bpbar .pill").click(); [...document.querySelectorAll(".ddmenu .ddi")].find((x) => x.textContent.startsWith(t)).click(); }, tm);
        await until(([t, k]) => document.querySelector(".bpbar .pill")?.textContent.trim() === t && document.querySelectorAll(".bppage table tbody tr").length >= k, [tm === "All teams" ? "All teams" : tm, n], 60000);
        if (tm === "NYY") { await pg.evaluate(() => document.querySelector(".bppage table tbody tr .pbname").click()); await count("#xboard.xpop table.sbt tbody tr", 1, 60000);
          await until(() => location.hash === "#bullpens" && !!document.querySelector("#xboard.xpop .xpopx")); await pg.keyboard.press("Escape"); await until(() => !document.querySelector("#xboard.xpop")); } } });
    await step("fantasy", async () => { await hash("#fantasy"); await count("#fboard table tbody tr", 10, 90000); });
    await step("phone bar", async () => {   // the bottom bar on a phone (29 Oct 2026): six tabs, Fantasy's sheet, a page from it; hidden on a desktop
      const shown = await pg.evaluate(() => { const b = document.querySelector(".pbar"); return b ? getComputedStyle(b).display !== "none" : null; });
      if (shown === null) throw new Error("no .pbar");
      if (name.startsWith("phone")) { if (!shown) throw new Error("the phone bar is hidden");
        await until(() => document.querySelectorAll(".pbar > a, .pbar > button").length === 7 && getComputedStyle(document.querySelector(".navtog")).display === "none" && getComputedStyle(document.querySelector("header.top")).display === "none");
        await pg.evaluate(() => document.querySelector(".pbar button[aria-controls='pbarsheet']").click()); await until(() => !document.querySelector("#pbarsheet").hidden && document.querySelectorAll("#pbarsheet a").length === 5);
        await pg.evaluate(() => [...document.querySelectorAll("#pbarsheet a")].find((a) => a.textContent === "Bullpens").click());
        await until(() => location.hash === "#bullpens" && document.querySelector("#pbarsheet").hidden); await count(".bppage table tbody tr", 20, 120000);
        await until(() => document.querySelector('.pbar [data-mode="draftmode"]').getAttribute("aria-current") === "page");
        // the search from the bar (29 Oct 2026): the tab opens the header over the page with the box focused, a pick closes it
        await pg.evaluate(() => document.querySelector(".pbar .psbtn").click());
        await until(() => document.body.classList.contains("psearchon") && getComputedStyle(document.querySelector("header.top")).display !== "none" && document.activeElement === document.getElementById("gq"));
        await pg.type("#gq", "Judge"); await count("#glist .addhit", 1);
        await pg.evaluate(() => [...document.querySelectorAll("#glist .addhit")].find((x) => /^Aaron Judge/.test(x.textContent)).click());
        await until(() => location.hash === "#player/592450" && !document.body.classList.contains("psearchon") && getComputedStyle(document.querySelector("header.top")).display === "none"); }
      else { if (shown) throw new Error("the phone bar shows on a desktop");
        await until(() => getComputedStyle(document.querySelector("header.top")).display !== "none" && getComputedStyle(document.querySelector(".pscancel")).display === "none"); } });
    if (!QUICK) {
      await step("mock draft", async () => { await hash("#mock"); await until(() => document.querySelector("#pitchboard") && document.querySelector("#pitchboard").innerText.length > 50); });
      await step("settings", async () => { for (const t of ["glossary", "appearance", "key", "how"]) { await hash("#settings/" + t); await count(".stabs .btab", 3); } });
    }
    await step("hitter page", async () => { await hash("#player/592450"); await count("table.sbt tbody tr", 5, 60000);
      await clickAll(".btabs .btab");
      if (!QUICK) { await count(".sbviews .sbview", 5); await clickAll(".sbviews .sbview"); } });   // the five tables, a row of buttons on both layouts again (25 Oct 2026)
    await step("pitcher page", async () => { await hash("#player/694973"); await count("table.sbt tbody tr", 2, 60000); await clickAll(".btabs .btab");
      await clickAll(".sbviews .sbview");   // Raw / Stuff, the hitter's table switch in a pitcher's dress (25 Oct 2026)
      await pg.evaluate(() => { const b = document.querySelector(".sbviews .sbview"); if (b) b.click(); }); });   // and back to Raw
    // a name picked from the header search opens his page at the top, through an iPhone putting the page's scroll back once the keyboard has gone
    // (Sean, 23 Oct 2026: Skenes's page, searched from a scrolled page, opened at that page's scroll) — the restore after the blur mimicked
    await step("search from a scrolled page", async () => {
      await pg.evaluate(() => window.scrollTo(0, 600)); await pg.waitForTimeout(1600);   // past the open's own "to the top" moment
      if (!(await pg.evaluate(() => window.scrollY > 100))) throw new Error("the page didn't scroll down");
      await pg.evaluate(() => { const gq = document.getElementById("gq"), y = window.scrollY; gq.addEventListener("blur", () => setTimeout(() => window.scrollTo(0, y), 120), { once: true }); });
      if (name.startsWith("phone")) await pg.evaluate(() => document.querySelector(".pbar .psbtn").click()); else await pg.focus("#gq");   // a phone opens the box from the bar (29 Oct 2026)
      await pg.type("#gq", "Judge"); await count("#glist .addhit", 1);
      await pg.evaluate(() => [...document.querySelectorAll("#glist .addhit")].find((x) => /^Aaron Judge/.test(x.textContent)).click());
      await until(() => { const n = document.querySelector("#xboard .pgbname"); return !!(n && /Aaron Judge/.test(n.textContent) && document.querySelector("table.sbt tbody tr")); });
      await pg.waitForTimeout(1500);
      const y = await pg.evaluate(() => window.scrollY); if (y > 1) throw new Error(`Judge's page opened at ${y}px, not the top`);
    });
    // the iPhone's viewport heal (23 Oct 2026) flips the body's display and back and puts every scroller back: run by hand here, it must leave the
    // page and a sideways-scrolled table exactly where they were
    await step("viewport heal", async () => {
      // a table that scrolls sideways (a phone's season table; a desktop's fit, so there may be none)
      await pg.evaluate(() => { window.scrollTo(0, 500); window.__sc = [...document.querySelectorAll("#xboard .sbscroll, #xboard .brscroll")].find((e) => e.scrollWidth > e.clientWidth + 10) || null; if (window.__sc) window.__sc.scrollLeft = 120; }); await pg.waitForTimeout(1600);
      const before = await pg.evaluate(() => [window.scrollY, window.__sc ? window.__sc.scrollLeft : -1]);
      await pg.evaluate(() => window.__healViewport()); await pg.waitForTimeout(300);
      const after = await pg.evaluate(() => [window.scrollY, window.__sc ? window.__sc.scrollLeft : -1, !!document.querySelector("#xboard .pgbname")]);
      if (before[0] < 100 || (before[1] >= 0 && before[1] < 50)) throw new Error(`the page didn't scroll first (${before})`);
      if (Math.abs(after[0] - before[0]) > 2 || Math.abs(after[1] - before[1]) > 2 || !after[2]) throw new Error(`the heal moved the page: ${before} → ${after}`);
    });
    if (mid) await step("a minors card", async () => { await hash("#player/" + mid); await count("table.sbt tbody tr", 1, 90000); await clickAll(".btabs .btab"); });
    await ctx.close();
  }
  await browser.close(); srv.close();
  console.log(failed ? `check_site: ${failed} of ${steps} steps failed` : `check_site: all ${steps} steps passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error("check_site: " + e.message); process.exit(2); });
