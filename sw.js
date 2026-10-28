// The site's service worker (Sean, 28 Oct 2026, item 20 of the review's picks: "a service worker caching the app, data.js and the hist files —
// the home-screen app would open offline and instantly, and the build.json reload already handles staleness"). app.js registers it on the live
// site (registerSW; ?sw=1 tries it anywhere). Same-origin GETs only:
//   * a versioned file (?v=… — every script, stylesheet, data and hist file the build map stamps) never changes under its URL, so it is served
//     from the cache first and fetched only on a miss, the copy kept (a day file's stream and a gzipped past season included);
//   * the page itself (index.html, with or without the ?b= a build reload adds) is network first — a reload after a publish must see the new
//     stamps — and the cached copy is the fallback, so the home-screen app opens offline on the last page it saw;
//   * everything else (build.json, MLB's API, the fonts) goes straight through.
// One cache: one copy a file (a new build's stamp retires the old one), trimmed to the newest KEEP entries, and a copy that won't fit (iOS's
// quota) is just not kept.
const CACHE = "seans-site-v1", KEEP = 160;
self.addEventListener("install", (e) => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then((c) => c.add("index.html").catch(() => {}))); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
const same = (u) => u.origin === self.location.origin;
const versioned = (u) => same(u) && /[?&]v=[0-9a-f]+/.test(u.search);
const shell = (u) => same(u) && (u.pathname.endsWith("/") || u.pathname.endsWith("/index.html"));
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const u = new URL(e.request.url);
  if (versioned(u)) e.respondWith(cacheFirst(e.request));
  else if (shell(u)) e.respondWith(shellFirst(e.request));
});
async function cacheFirst(r) {
  const c = await caches.open(CACHE), hit = await c.match(r, { ignoreVary: true });
  if (hit) return hit;
  const res = await fetch(r);
  if (res && res.ok) put(c, r, res.clone());
  return res;
}
async function shellFirst(r) {
  const c = await caches.open(CACHE);
  try { const res = await fetch(r, { cache: "no-store" }); if (res && res.ok) put(c, "index.html", res.clone()); return res; }
  catch (e) { const hit = await c.match("index.html"); if (hit) return hit; throw e; }
}
let trimming = false;
async function put(c, r, res) {
  try { await c.put(r, res); } catch (e) { return; }   // no room: not kept
  if (trimming) return; trimming = true;
  try {
    const ks = await c.keys(), path = typeof r === "string" ? null : new URL(r.url).pathname;
    for (const k of ks) if (path && k.url !== r.url && new URL(k.url).pathname === path) await c.delete(k);   // one copy a file: a new build's stamp retires the old one (a day file is 12-17 MB)
    const left = await c.keys(); for (const k of left.slice(0, Math.max(0, left.length - KEEP))) await c.delete(k);   // and the newest KEEP of the rest
  } catch (e) {} finally { trimming = false; }
}
