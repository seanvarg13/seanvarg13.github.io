// Headless Chrome for the build (Sean, 20 Oct 2026): a static server on the repo root and a browser, for tools/build_home.cjs (home's lists, computed
// by the site's own code) and tools/check_site.cjs (every page on a phone and a desktop, before a publish). playwright-core comes from npm in the
// workflow (NODE_PATH) and drives the runner's Chrome (PW_CHANNEL=chrome); in a Claude cloud session the preinstalled playwright and its Chromium.
const http = require("http"), fs = require("fs"), path = require("path");

function playwright() {
  for (const m of ["playwright-core", "playwright", "/opt/node-tools/node_modules/playwright"]) { try { return require(m); } catch (e) { /* the next one */ } }
  throw new Error("playwright isn't installed (npm install playwright-core)");
}

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json",
                ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".gz": "application/gzip", ".webmanifest": "application/manifest+json" };
function serve(root) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let u; try { u = decodeURIComponent(req.url.split("?")[0]); } catch (e) { res.writeHead(400); return res.end(); }
      if (u.endsWith("/")) u += "index.html";
      const f = path.join(root, u);
      if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end("not found"); }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" });
      fs.createReadStream(f).pipe(res);
    });
    srv.listen(0, "127.0.0.1", () => resolve({ srv, base: `http://127.0.0.1:${srv.address().port}/` }));
  });
}

async function launch() {
  const { chromium } = playwright(), ch = process.env.PW_CHANNEL;
  try { return await chromium.launch(ch ? { channel: ch } : {}); } catch (e) { if (!ch) throw e; return chromium.launch(); }   // the channel missing: the bundled one
}

const PHONE = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2, serviceWorkers: "block" };   // no service worker in a test's browser (28 Oct 2026): the tests route requests, and a worker would answer from its cache
const DESK = { viewport: { width: 1300, height: 900 }, deviceScaleFactor: 1, serviceWorkers: "block" };

module.exports = { serve, launch, PHONE, DESK };
