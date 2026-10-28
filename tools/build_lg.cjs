#!/usr/bin/env node
// hist/lg/<season>.js: the season table's league-wide numbers — the heat pools (every qualified hitter's or pitcher's value, sorted), the
// league leaders (AL / NL / MLB, Baseball-Reference's way), the HR/FB league and the ISO pool — computed by the site's own code (window.__lgData
// in app.js) from the whole hist/career.js + hist/career-bb.js, so a player's page reads one small file a season instead of the two whole files
// (~2.4 MB gzipped; Sean, 28 Oct 2026, from the review: item 5). Run by cloud_daily.py after build_career.py; non-fatal there — without a
// season's file the page falls back to the whole files, as it always did.
//
//   node tools/build_lg.cjs            (needs playwright-core and a Chrome; see tools/headless.cjs)
const fs = require("fs"), path = require("path");
const { serve, launch, DESK } = require("./headless.cjs");
const ROOT = path.resolve(__dirname, ".."), OUT = path.join(ROOT, "hist", "lg");

(async () => {
  const t0 = Date.now(), { srv, base } = await serve(ROOT), browser = await launch();
  try {
    const page = await (await browser.newContext(DESK)).newPage(), errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    await page.route(/^https?:\/\//, (r) => (r.request().url().startsWith(base) ? r.continue() : r.abort()));   // nothing outside the repo
    await page.goto(base + "#home", { waitUntil: "load", timeout: 120000 });
    await page.waitForFunction(() => typeof window.__lgData === "function", null, { timeout: 60000 });
    const data = await page.evaluate(() => window.__lgData());
    if (errs.length) throw new Error("the page threw: " + errs.slice(0, 3).join(" | "));
    const years = Object.keys(data || {}).sort();
    if (!years.length) throw new Error("no seasons came back");
    fs.mkdirSync(OUT, { recursive: true });
    let total = 0, wrote = 0;
    for (const y of years) {
      // full precision: a leader's value is matched to the cell's within 1e-9, and a pool is binary-searched for the cell's exact value
      const json = JSON.stringify(data[y]);
      const body = `window.DRAFT_LG=window.DRAFT_LG||{};window.DRAFT_LG[${JSON.stringify(y)}]=${json};\n`, f = path.join(OUT, y + ".js");
      total += body.length;
      if (!fs.existsSync(f) || fs.readFileSync(f, "utf8") !== body) { fs.writeFileSync(f, body); wrote++; }   // an unchanged season keeps its mtime
    }
    console.log(`hist/lg/ (${years.length} seasons ${years[0]}-${years[years.length - 1]}, ${(total / 1024).toFixed(0)} KB, ${wrote} changed, ${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  } finally { await browser.close(); srv.close(); }
})().catch((e) => { console.error("build_lg: " + e.message); process.exit(1); });
