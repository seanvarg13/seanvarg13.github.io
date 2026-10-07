/* Colour schemes and fonts. Loaded in <head> before the page paints; sets the scheme's tokens inline on <html>
   (see the token roles at the top of styles.css) and swaps the Google Fonts link for the chosen type.
   The Appearance page (app.js) reads DRAFT_THEMES.schemes / .fonts and calls DRAFT_THEMES.set(). */
window.DRAFT_THEMES = (function () {
  const W = "rgba(255, 255, 255, ";
  // type on a dark fill / on a light fill
  const onDark = (ink) => ({ "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.82)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": ink || "#ffffff" });
  const onLight = (ink, dim) => ({ "accent-2-ink": ink, "accent-2-dim": dim, "on-fill-wash": W + "0.28)", "on-fill-wash-2": W + "0.45)", "on-fill-line": dim.replace(/[\d.]+\)$/, "0.35)"), "tab-ink": ink });
  // the neutral dark page for the non-blue schemes (the blue ones keep the navy-black page from styles.css)
  const greyNight = { page: "#121316", surface: "#1a1b1f", "surface-2": "#22242a", hair: "#2f3239", rail: "#3d414a", stripe: "#17181c", hover: "#24262d", band: "#1a1b1f", plate: "#5f6570", muted: "#8b919c", ink: "#eceef2", "ink-2": "#bfc5cf", mid: "#3d4048" };

  const S = {
    warm: {
      name: "Warm", blurb: "The warm pass (6 Oct 2026): an off-white ground, ink-black type and buttons, hairlines instead of frames — the percentile colours do the colouring.",
      light: { accent: "#141414", "accent-2": "#141414", "accent-2-ink": "#141414", "accent-2-dim": "#7d7b74", "on-fill-wash": "rgba(20, 20, 20, 0.06)", "on-fill-wash-2": "rgba(20, 20, 20, 0.1)", "on-fill-line": "rgba(20, 20, 20, 0.18)", "tab-ink": "#141414",
               "accent-2-text": "#141414", pop: "#fbfaf7", rule: "#e4e2db", "stripe-line": "transparent", "accent-wash": "#efede8", ink: "#141414", "ink-2": "#44423d", hover: "#efede8",
               page: "#f3f2ee", surface: "#fbfaf7", "surface-2": "#edece7", hair: "#e4e2db", rail: "#d9d7d0", stripe: "#f3f2ee", band: "#fbfaf7", plate: "#e4e2db", muted: "#7d7b74",
               btn: "#141414", "btn-ink": "#ffffff", "btn-line": "#e4e2db", "tab-fill": "#141414" },
      dark: { accent: "#f2f1ec", "accent-2": "#f2f1ec", "accent-2-ink": "#f2f1ec", "accent-2-dim": "#8e8c85", "on-fill-wash": "rgba(242, 241, 236, 0.08)", "on-fill-wash-2": "rgba(242, 241, 236, 0.14)", "on-fill-line": "rgba(242, 241, 236, 0.22)", "tab-ink": "#f2f1ec",
              "accent-2-text": "#f2f1ec", pop: "#1d1e23", rule: "#2f3036", "accent-wash": "#26272d", ink: "#f2f1ec", "ink-2": "#c9c7c0", hover: "#26272d",
              page: "#15161a", surface: "#1d1e23", "surface-2": "#26272d", hair: "#2f3036", rail: "#3a3b42", stripe: "#15161a", band: "#1d1e23", plate: "#2f3036", muted: "#8e8c85",
              btn: "#f2f1ec", "btn-ink": "#141414", "btn-line": "#2f3036", "tab-fill": "#f2f1ec" },
    },
    unc: {
      name: "Carolina blue", blurb: "UNC — Carolina blue carries the site, navy type on it.",
      light: { accent: "#13294b", "accent-2": "#7bafd4", ...onLight("#13294b", "rgba(19, 41, 75, 0.85)"), "accent-2-text": "#4b9cd3", pop: "#ffffff", rule: "#13294b", "stripe-line": "transparent", "accent-wash": "rgba(123, 175, 212, 0.24)", ink: "#13294b", "ink-2": "#3a4a66", hover: "#eaf2f9", band: "#13294b" },
      dark: { accent: "#9cc6e8", "accent-2-ink": "#0f213d", "accent-2-dim": "rgba(15, 33, 61, 0.85)", "on-fill-line": "rgba(15, 33, 61, 0.35)", "tab-ink": "#0f213d", "accent-2-text": "#9cc6e8", ink: "#edf3fa", "ink-2": "#b7c5d8", hover: "#1b2b45", "accent-wash": "rgba(123, 175, 212, 0.22)" },
    },
    "unc-navy": {
      name: "Carolina navy", blurb: "UNC — navy carries the site, Carolina blue is the highlight.",
      light: { accent: "#13294b", "accent-2": "#13294b", ...onDark(), "accent-2-text": "#4b9cd3", pop: "#7bafd4", rule: "#7bafd4", "stripe-line": "transparent", "accent-wash": "rgba(75, 156, 211, 0.16)", ink: "#13294b", "ink-2": "#3a4a66", hover: "#e9f1f9", band: "#13294b",
               btn: "#7bafd4", "btn-ink": "#13294b", "btn-line": "#7bafd4", "tab-fill": "#7bafd4", "tab-ink": "#13294b" },
      dark: { accent: "#9cc6e8", "accent-2": "#122747", "accent-2-text": "#8dc0ee", pop: "#8dc0ee", rule: "#8dc0ee", ink: "#edf3fa", "ink-2": "#b7c5d8", hover: "#1b2b45", "accent-wash": "rgba(123, 175, 212, 0.2)",
              btn: "#7bafd4", "btn-ink": "#0f213d", "btn-line": "#7bafd4", "tab-fill": "#7bafd4", "tab-ink": "#0f213d" },
    },
    titans: {
      name: "Titans", blurb: "Tennessee Titans, the white jersey (the site's palette since 6 Oct 2026): white first, Titans light blue second (buttons, anything active), the red third (the stripe under the band); navy type.",
      light: { accent: "#4b92db", "accent-2": "#4b92db", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.9)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#2f6fb3", pop: "#ffffff", rule: "#dde4ed", "stripe-line": "#c8102e", "accent-wash": "rgba(75, 146, 219, 0.12)", ink: "#0c2340", "ink-2": "#3d4e68", hover: "#eef4fb",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#f3f6fa", hair: "#dde4ed", rail: "#c9d3e0", stripe: "#ffffff", band: "#ffffff", plate: "#dde4ed", muted: "#6f7c90",
               btn: "#4b92db", "btn-ink": "#ffffff", "btn-line": "#dde4ed", "tab-fill": "#4b92db",
               // the warm pass's own tokens (styles.css sets them to its off-white values; a scheme has to say otherwise)
               ground: "#ffffff", "line-soft": "#dde4ed", frame: "#dde4ed", secrule: "#dde4ed", "accent-ink": "#ffffff", "band-ink": "#0c2340", svtext: "#0c2340", svrule: "#dde4ed", pctrack: "#e6ecf3" },
      dark: { accent: "#8dc0ee", "accent-2": "#4b92db", "accent-2-ink": "#071427", "accent-2-dim": "rgba(7, 20, 39, 0.85)", "on-fill-wash": "rgba(7, 20, 39, 0.1)", "on-fill-wash-2": "rgba(7, 20, 39, 0.18)", "on-fill-line": "rgba(7, 20, 39, 0.35)", "tab-ink": "#071427",
              "accent-2-text": "#8dc0ee", pop: "#112138", rule: "#233b5c", "stripe-line": "#c8102e", "accent-wash": "rgba(75, 146, 219, 0.22)", ink: "#edf3fa", "ink-2": "#b7c5d8", hover: "#172a46",
              page: "#0b1628", surface: "#112138", "surface-2": "#172a46", hair: "#233b5c", rail: "#2d4a70", stripe: "#0b1628", band: "#112138", plate: "#233b5c", muted: "#8ea0b8",
              btn: "#4b92db", "btn-ink": "#071427", "btn-line": "#233b5c", "tab-fill": "#4b92db",
              ground: "#0b1628", "line-soft": "#233b5c", frame: "#233b5c", secrule: "#233b5c", "accent-ink": "#071427", "band-ink": "#edf3fa", svtext: "#edf3fa", svrule: "#233b5c", pctrack: "#1b2f4c" },
    },
    "titans-unc": {
      name: "Titans · Carolina", blurb: "Tennessee in Carolina blue — Titans navy type, the red stripe, UNC blue across the banner.",
      light: { accent: "#0c2340", "accent-2": "#7bafd4", ...onLight("#0c2340", "rgba(12, 35, 64, 0.85)"), "accent-2-text": "#4b9cd3", pop: "#ffffff", rule: "#0c2340", "stripe-line": "#c8102e", "accent-wash": "rgba(123, 175, 212, 0.24)", ink: "#0c2340", "ink-2": "#35465f", hover: "#eaf2f9", band: "#0c2340" },
      dark: { accent: "#9cc6e8", "accent-2-ink": "#071427", "accent-2-dim": "rgba(7, 20, 39, 0.85)", "on-fill-line": "rgba(7, 20, 39, 0.35)", "tab-ink": "#071427", "accent-2-text": "#9cc6e8", pop: "#071427", rule: "#071427", ink: "#edf3fa", "ink-2": "#b7c5d8", hover: "#1b2b45", "accent-wash": "rgba(123, 175, 212, 0.22)" },
    },
    purple: {
      name: "Purple", blurb: "Deep purple carries the site, lavender is the highlight.",
      light: { accent: "#3b1d6e", "accent-2": "#5b2d8e", ...onDark(), "accent-2-text": "#6b3fa0", pop: "#c9b3e8", rule: "#c9b3e8", "stripe-line": "transparent", "accent-wash": "rgba(140, 100, 190, 0.16)", ink: "#241a33", "ink-2": "#4a3f5c", hover: "#f1ecf8", band: "#3b1d6e" },
      dark: { ...greyNight, accent: "#c9b3e8", "accent-2": "#5b2d8e", "accent-2-text": "#c9b3e8", "accent-wash": "rgba(140, 100, 190, 0.22)", hover: "#26212f" },
    },
    alabama: {
      name: "Crimson Tide", blurb: "Alabama — crimson carries the site, cool grey rules and white type.",
      light: { accent: "#7a1428", "accent-2": "#9e1b32", ...onDark(), "accent-2-text": "#9e1b32", pop: "#e9ebed", rule: "#828a8f", "stripe-line": "transparent", "accent-wash": "rgba(158, 27, 50, 0.12)", ink: "#1f1a1b", "ink-2": "#4d4346", hover: "#f7eef0", band: "#7a1428" },
      dark: { ...greyNight, accent: "#e79aa8", "accent-2": "#9e1b32", "accent-2-text": "#e79aa8", rule: "#9aa1a6", "accent-wash": "rgba(158, 27, 50, 0.22)", hover: "#2a2022" },
    },
    clemson: {
      name: "Clemson", blurb: "Clemson — orange carries the site, regalia purple is the highlight.",
      light: { accent: "#522d80", "accent-2": "#f56600", ...onDark("#522d80"), "accent-2-text": "#d95a00", pop: "#522d80", rule: "#522d80", "stripe-line": "transparent", "accent-wash": "rgba(245, 102, 0, 0.14)", ink: "#2a1f3d", "ink-2": "#4d4360", hover: "#fbf1ea", band: "#522d80" },
      dark: { ...greyNight, accent: "#c9b3e8", "accent-2": "#f56600", "accent-2-text": "#ff9a4d", pop: "#3a1f5e", rule: "#3a1f5e", "tab-ink": "#3a1f5e", "accent-wash": "rgba(245, 102, 0, 0.2)", hover: "#2a2320" },
    },
  };

  // the site's type (Sean, 30 Sep 2026, from the Percentile Bar Studio page: "adjust the entire font of the site to be this
  // font"): Barlow Condensed for headings, names and big numbers, Source Sans 3 for everything else. This file loads them
  // (in <head>, before the page paints) rather than index.html, whose template lives on the Mac and isn't synced.
  const F = {
    studio: { name: "Barlow Condensed + Source Sans 3", blurb: "Condensed headings, an easy-reading text face — the same on every page and device.",
              google: "family=Barlow+Condensed:wght@400;500;600;700;800&family=Source+Sans+3:ital,wght@0,400..700;1,400..700&family=Roboto+Condensed:wght@700",   // Roboto: the percentile bubbles' digits only
              display: '"Barlow Condensed", "Arial Narrow", "Helvetica Neue", Arial, sans-serif',
              body: '"Source Sans 3", "Source Sans Pro", -apple-system, "Segoe UI", Helvetica, Arial, sans-serif' },
  };

  const LS = { scheme: "draft2027.scheme", font: "draft2027.font", theme: "draft2027.theme", view: "draft2027.view" };
  const DEFAULTS = Object.assign({ scheme: "titans", font: "studio", theme: "system", view: "auto" }, window.DRAFT_DEFAULTS || {});
  if (!S[DEFAULTS.scheme]) DEFAULTS.scheme = "titans";
  if (!F[DEFAULTS.font]) DEFAULTS.font = "studio";
  const get = (k) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : null; } catch { return null; } };
  const put = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } };
  const root = document.documentElement;
  // the warm pass (6 Oct 2026): every device moves to the warm scheme once, whatever it had saved; a scheme picked after that stays
  try { if (!localStorage.getItem("draft2027.warm1")) { localStorage.setItem("draft2027.warm1", "1"); localStorage.removeItem(LS.scheme); } } catch { /* private mode */ }
  // the Titans palette (Sean, 6 Oct 2026: "make the websites main color palette or theme the Tennessee titans color scheme"): every device moves to it once
  try { if (!localStorage.getItem("draft2027.titans1")) { localStorage.setItem("draft2027.titans1", "1"); localStorage.removeItem(LS.scheme); } } catch { /* private mode */ }
  const current = () => ({
    scheme: S[get(LS.scheme)] ? get(LS.scheme) : DEFAULTS.scheme,
    font: F[get(LS.font)] ? get(LS.font) : DEFAULTS.font,
    theme: ["light", "dark"].includes(get(LS.theme)) ? get(LS.theme) : "system",
  });
  const isDark = () => root.dataset.theme === "dark" || (root.dataset.theme !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
  let setKeys = [];

  function apply() {
    const cur = current();
    if (cur.theme !== "system" && root.dataset.theme !== cur.theme) root.dataset.theme = cur.theme;   // explicit choice; "system" leaves the host's / OS value alone
    const sc = S[cur.scheme];
    const tokens = Object.assign({}, sc.light, isDark() ? sc.dark : {});
    for (const k of setKeys) if (!(k in tokens)) root.style.removeProperty("--" + k);
    for (const [k, v] of Object.entries(tokens)) root.style.setProperty("--" + k, v);
    setKeys = Object.keys(tokens);
    root.dataset.scheme = cur.scheme;
    const f = F[cur.font];
    root.style.setProperty("--display", f.display);
    root.style.setProperty("--body", f.body);
    root.dataset.font = cur.font;
    let link = document.getElementById("fontlink");
    if (f.google) {
      const href = "https://fonts.googleapis.com/css2?" + f.google + "&display=swap";
      if (!link) { link = document.createElement("link"); link.id = "fontlink"; link.rel = "stylesheet"; document.head.appendChild(link); }
      if (link.getAttribute("href") !== href) link.setAttribute("href", href);
    } else if (link) link.remove();
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = tokens["accent-2"];
  }

  // preview every font at once (the Appearance page only)
  function preloadFonts() {
    if (document.getElementById("fontpreview")) return;
    const fams = Object.values(F).filter((f) => f.google).map((f) => f.google).join("&");
    if (!fams) return;
    const l = document.createElement("link"); l.id = "fontpreview"; l.rel = "stylesheet";
    l.href = "https://fonts.googleapis.com/css2?" + fams + "&display=swap";
    document.head.appendChild(l);
  }

  // Mobile / desktop layout. "auto" follows the screen (phones get the compact layout); "desktop" on a phone
  // widens the viewport so the full layout shows zoomed out, like Safari's "Request Desktop Website".
  const viewPref = () => (["mobile", "desktop"].includes(get(LS.view)) ? get(LS.view) : (["mobile", "desktop"].includes(DEFAULTS.view) ? DEFAULTS.view : "auto"));
  const hasOwn = () => [LS.scheme, LS.font, LS.theme, LS.view].some((k) => get(k) != null);
  const useDefaults = () => { for (const k of [LS.scheme, LS.font, LS.theme, LS.view]) { try { localStorage.removeItem(k); } catch { /* */ } } delete root.dataset.theme; apply(); applyView(); };
  const smallScreen = () => matchMedia("(max-width: 700px)").matches || (navigator.maxTouchPoints > 1 && Math.min(screen.width, screen.height) <= 700);
  function applyView() {
    const pref = viewPref(), small = smallScreen();
    const view = pref === "auto" ? (small ? "mobile" : "desktop") : pref;
    root.dataset.view = view;
    const vp = document.querySelector('meta[name="viewport"]');
    if (vp) vp.content = view === "desktop" && small ? "width=1100, viewport-fit=cover" : "width=device-width, initial-scale=1, viewport-fit=cover";
    return view;
  }
  function setView(v) { put(LS.view, v); applyView(); }

  function set(changes) {
    if (changes.scheme && S[changes.scheme]) put(LS.scheme, changes.scheme);
    if (changes.font && F[changes.font]) put(LS.font, changes.font);
    if (changes.theme) { put(LS.theme, changes.theme); if (changes.theme === "system") delete root.dataset.theme; }
    apply();
  }

  apply(); applyView();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", apply);
  new MutationObserver(apply).observe(root, { attributes: true, attributeFilter: ["data-theme"] });
  window.addEventListener("resize", () => { if (viewPref() === "auto") applyView(); });
  return { schemes: S, fonts: F, defaults: DEFAULTS, current, isDark, apply, set, preloadFonts, viewPref, applyView, setView, view: () => root.dataset.view, hasOwn, useDefaults };
})();
