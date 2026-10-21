#!/usr/bin/env node
// hist/home.js: home's day-file lists — the last game day, Trending, Movers — computed by the site's own code (window.__homeData in app.js) on the
// freshly built data.js and day files (days-h.js, days-p.js), so a fresh home reads ~10 KB instead of downloading and parsing them (Sean, 20 Oct 2026, item 1
// of the recommendations). Run by cloud_daily.py after build_data.py; non-fatal there — without the file, or with one older than data.js, home loads
// the day rows and computes the lists itself, as it always did.
//
//   node tools/build_home.cjs            (needs playwright-core and a Chrome; see tools/headless.cjs)
const fs = require("fs"), path = require("path");
const { serve, launch, DESK } = require("./headless.cjs");
const ROOT = path.resolve(__dirname, ".."), OUT = path.join(ROOT, "hist", "home.js");

(async () => {
  const t0 = Date.now(), { srv, base } = await serve(ROOT), browser = await launch();
  try {
    const page = await (await browser.newContext(DESK)).newPage(), errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    // nothing outside the repo is needed (fonts, MLB's API for a bio): leave it out, so the run is quick and the same every time
    await page.route(/^https?:\/\//, (r) => (r.request().url().startsWith(base) ? r.continue() : r.abort()));
    await page.goto(base + "#home", { waitUntil: "load", timeout: 120000 });
    await page.waitForFunction(() => typeof window.__homeData === "function", null, { timeout: 60000 });
    const data = await page.evaluate(() => window.__homeData());
    if (errs.length) throw new Error("the page threw: " + errs.slice(0, 3).join(" | "));
    if (!data || !data.last || !data.trend || !data.movers) throw new Error("no lists came back");
    // four decimals are more than any of them shows (xwOBA to three, nERA to two)
    const json = JSON.stringify(data, (k, v) => (typeof v === "number" ? Math.round(v * 1e4) / 1e4 : v));
    fs.writeFileSync(OUT, "window.DRAFT_HOME = " + json + ";\n");
    console.log(`hist/home.js (${(json.length / 1024).toFixed(1)} KB, ${((Date.now() - t0) / 1000).toFixed(0)} s): last game day ${data.day} — ${data.last.hit.length} hitters, ${data.last.pit.length} starts; ` +
                `trending ${data.trend.hit.length} + ${data.trend.pit.length}; movers ${data.movers.length} hitters, ${(data.pmovers || []).length} pitchers`);
  } finally { await browser.close(); srv.close(); }
})().catch((e) => { console.error("build_home: " + e.message); process.exit(1); });
