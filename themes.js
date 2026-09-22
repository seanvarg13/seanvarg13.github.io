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
      name: "Titans", blurb: "Tennessee — Titans blue forward, navy type, the red stripe under the banner.",
      light: { accent: "#0c2340", "accent-2": "#4b92db", ...onDark("#0c2340"), "accent-2-dim": W + "0.9)", "accent-2-text": "#4b92db", pop: "#0c2340", rule: "#0c2340", "stripe-line": "#c8102e", "accent-wash": "rgba(75, 146, 219, 0.16)", ink: "#0c2340", "ink-2": "#35465f", hover: "#e9f1f9", band: "#0c2340" },
      dark: { accent: "#8dc0ee", "accent-2-ink": "#071427", "accent-2-dim": "rgba(7, 20, 39, 0.85)", "on-fill-line": "rgba(7, 20, 39, 0.35)", "tab-ink": "#071427", "accent-2-text": "#8dc0ee", pop: "#071427", rule: "#071427", ink: "#edf3fa", "ink-2": "#b7c5d8", hover: "#1b2b45", "accent-wash": "rgba(75, 146, 219, 0.2)" },
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

  const F = {
    system: { name: "Helvetica / system", blurb: "The Savant look — Helvetica Neue on a Mac and iPhone.", google: null,
              display: '"Helvetica Neue", Helvetica, Arial, sans-serif', body: '"Helvetica Neue", Helvetica, Arial, sans-serif' },
    nunito: { name: "Nunito", blurb: "Rounded and soft; Nunito Sans for the rows.", google: "family=Nunito:wght@600;700;800&family=Nunito+Sans:wght@300;400;600;700",
              display: '"Nunito", "Nunito Sans", "Segoe UI", system-ui, sans-serif', body: '"Nunito Sans", "Nunito", "Segoe UI", system-ui, sans-serif' },
    figtree: { name: "Figtree", blurb: "Friendly geometric, a touch crisper than Nunito.", google: "family=Figtree:wght@400;500;600;700;800",
               display: '"Figtree", system-ui, sans-serif', body: '"Figtree", system-ui, sans-serif' },
    inter: { name: "Inter", blurb: "The screen workhorse; very even, very legible.", google: "family=Inter:wght@400;500;600;700",
             display: '"Inter", system-ui, sans-serif', body: '"Inter", system-ui, sans-serif' },
    source: { name: "Source Sans 3", blurb: "Adobe's humanist sans; light and open at small sizes.", google: "family=Source+Sans+3:wght@400;600;700",
              display: '"Source Sans 3", system-ui, sans-serif', body: '"Source Sans 3", system-ui, sans-serif' },
    plex: { name: "IBM Plex Sans", blurb: "A little more character in the letterforms; great numerals.", google: "family=IBM+Plex+Sans:wght@400;500;600;700",
            display: '"IBM Plex Sans", system-ui, sans-serif', body: '"IBM Plex Sans", system-ui, sans-serif' },
    roboto: { name: "Roboto", blurb: "Android's default; compact and neutral.", google: "family=Roboto:wght@400;500;700",
              display: '"Roboto", system-ui, sans-serif', body: '"Roboto", system-ui, sans-serif' },
    lato: { name: "Lato", blurb: "Warm and slightly rounded; a classic for dashboards.", google: "family=Lato:wght@400;700;900",
            display: '"Lato", system-ui, sans-serif', body: '"Lato", system-ui, sans-serif' },
    barlow: { name: "Barlow", blurb: "Slightly condensed and sporty — jersey-number energy.", google: "family=Barlow:wght@400;500;600;700",
              display: '"Barlow", system-ui, sans-serif', body: '"Barlow", system-ui, sans-serif' },
    oswald: { name: "Oswald + Source Sans", blurb: "Condensed headline face for the banner and tiers, Source Sans for the rows.", google: "family=Oswald:wght@500;600;700&family=Source+Sans+3:wght@400;600;700",
              display: '"Oswald", "Arial Narrow", system-ui, sans-serif', body: '"Source Sans 3", system-ui, sans-serif' },
  };

  const LS = { scheme: "draft2027.scheme", font: "draft2027.font", theme: "draft2027.theme", view: "draft2027.view" };
  const DEFAULTS = Object.assign({ scheme: "unc", font: "system", theme: "system", view: "auto" }, window.DRAFT_DEFAULTS || {});
  if (!S[DEFAULTS.scheme]) DEFAULTS.scheme = "unc";
  if (!F[DEFAULTS.font]) DEFAULTS.font = "system";
  const get = (k) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : null; } catch { return null; } };
  const put = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } };
  const root = document.documentElement;
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
