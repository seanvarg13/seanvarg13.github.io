/* Colour schemes and fonts. Loaded in <head> before the page paints; sets the scheme's tokens inline on <html>
   (see the token roles at the top of styles.css) and swaps the Google Fonts link for the chosen type.
   The Appearance page (app.js) reads DRAFT_THEMES.schemes / .fonts and calls DRAFT_THEMES.set(). */
/* Table style — the site default: false = the Baseball-Reference tables (12px, 23px rows); true = the Source Sans tables of 13-14 Oct (column
   names the size of their cells, ~28-30px rows). Each device can pick its own in Appearance ▸ Tables (draft2027.tables; Sean, 14 Oct 2026). */
const TABLE_SANS = false;
/* Windows Classic (17-18 Oct 2026) is gone (Sean, 18 Oct 2026: "We can eliminate the windows look I don't need it"): a device that had
   picked it drops the saved pick, so nothing is left of it. */
try { localStorage.removeItem("draft2027.skin"); } catch (e) { /* nothing saved */ }
window.DRAFT_TABLES = (function () {
  const KEY = "draft2027.tables";
  const own = () => { try { return localStorage.getItem(KEY); } catch (e) { return null; } };
  const get = () => own() || (TABLE_SANS ? "classic" : "bref");
  const apply = () => document.documentElement.classList.toggle("tsans", get() === "classic");
  const set = (v) => { try { localStorage.setItem(KEY, v); } catch (e) { /* the switch still applies for this visit */ } document.documentElement.classList.toggle("tsans", v === "classic"); };
  const clear = () => { try { localStorage.removeItem(KEY); } catch (e) { /* */ } apply(); };
  apply();
  return { get, set, own, clear };
})();
/* Table borders (Sean, 1 Nov 2026: "in appearance add an option to swap between the thick border table you just added vs the one with no thick
   borders at all"): per device, draft2027.borders = "thick" (the default: the 3px frame, group breaks, header foot and totals rule) or "thin"
   (every table line 1px) — class thinlines on <html>, which sets --xlw to 1px in styles.css. */
window.DRAFT_BORDERS = (function () {
  const KEY = "draft2027.borders";
  const get = () => { try { return localStorage.getItem(KEY) || "thick"; } catch (e) { return "thick"; } };
  const set = (v) => { try { localStorage.setItem(KEY, v); } catch (e) { /* this visit only */ } document.documentElement.classList.toggle("thinlines", v === "thin"); };
  const clear = () => { try { localStorage.removeItem(KEY); } catch (e) { /* */ } document.documentElement.classList.remove("thinlines"); };
  document.documentElement.classList.toggle("thinlines", get() === "thin");
  return { get, set, clear };
})();
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
      name: "Titans", blurb: "Tennessee Titans, the white jersey: white first, the uniform's light blue second (buttons, bands, anything active), the red third (the stripe under the bands), navy type.",
      light: { accent: "#5aa9db", "accent-2": "#5aa9db", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.9)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#2f6fb3", pop: "#ffffff", rule: "#dde4ed", "stripe-line": "#c8102e", "accent-wash": "rgba(90, 169, 219, 0.12)", ink: "#0c2340", "ink-2": "#3d4e68", hover: "#eef4fb",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#f3f6fa", hair: "#dde4ed", rail: "#c9d3e0", stripe: "#ffffff", band: "#ffffff", plate: "#dde4ed", muted: "#6f7c90",
               btn: "#5aa9db", "btn-ink": "#ffffff", "btn-line": "#dde4ed", "tab-fill": "#5aa9db",
               // the warm pass's own tokens (styles.css sets them to its off-white values; a scheme has to say otherwise)
               ground: "#ffffff", "line-soft": "#dde4ed", frame: "#dde4ed", secrule: "#dde4ed", "accent-ink": "#ffffff", "band-ink": "#0c2340", svtext: "#0c2340", svrule: "#dde4ed", pctrack: "#e6ecf3" },
      dark: { accent: "#8dc0ee", "accent-2": "#5aa9db", "accent-2-ink": "#071427", "accent-2-dim": "rgba(7, 20, 39, 0.85)", "on-fill-wash": "rgba(7, 20, 39, 0.1)", "on-fill-wash-2": "rgba(7, 20, 39, 0.18)", "on-fill-line": "rgba(7, 20, 39, 0.35)", "tab-ink": "#071427",
              "accent-2-text": "#8dc0ee", pop: "#112138", rule: "#233b5c", "stripe-line": "#c8102e", "accent-wash": "rgba(90, 169, 219, 0.22)", ink: "#edf3fa", "ink-2": "#b7c5d8", hover: "#172a46",
              page: "#0b1628", surface: "#112138", "surface-2": "#172a46", hair: "#233b5c", rail: "#2d4a70", stripe: "#0b1628", band: "#112138", plate: "#233b5c", muted: "#8ea0b8",
              btn: "#5aa9db", "btn-ink": "#071427", "btn-line": "#233b5c", "tab-fill": "#5aa9db",
              ground: "#0b1628", "line-soft": "#233b5c", frame: "#233b5c", secrule: "#233b5c", "accent-ink": "#071427", "band-ink": "#edf3fa", svtext: "#edf3fa", svrule: "#233b5c", pctrack: "#1b2f4c" },
    },
    // the New York Jets (Sean, 18 Oct 2026: "basically just the white and green and no tertiary color. I like how they don't have outlines and it is
    // just the green and white"): Legacy Green (#115740, the team's own, 2024 on) and white. Type, buttons, bands and every rule are the green — the
    // stripe the other schemes draw under a band is the band's own colour here, so it vanishes; `flat` sets data-flat on <html>, and styles.css's
    // ":root[data-flat]" block takes the outlines off the buttons and boxes. The percentile colours stay Savant's (they're data)
    jets: {
      name: "Jets", flat: true, blurb: "New York Jets — Legacy Green and white, nothing else: green type, green bands with white type, no stripes and no outlines.",
      light: { "flat-ink": "#115740", accent: "#115740", "accent-2": "#115740", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#115740", pop: "#ffffff", rule: "#dfeae5", "stripe-line": "#115740", "accent-wash": "rgba(17, 87, 64, 0.08)", ink: "#115740", "ink-2": "#3f6b5d", hover: "#eef5f2",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#f1f7f4", hair: "#dfeae5", rail: "#c8dad2", stripe: "#ffffff", band: "#ffffff", plate: "#dfeae5", muted: "#6c8a7f",
               btn: "#115740", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#115740",
               ground: "#ffffff", "line-soft": "#dfeae5", frame: "#dfeae5", secrule: "#dfeae5", "accent-ink": "#ffffff", "band-ink": "#115740", svtext: "#115740", svrule: "#dfeae5", pctrack: "#e7f0ec" },
      dark: { accent: "#6fd1a6", "accent-2": "#115740", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
              "accent-2-text": "#6fd1a6", pop: "#0e2119", rule: "#1f4436", "stripe-line": "#115740", "accent-wash": "rgba(29, 122, 87, 0.22)", ink: "#eef6f2", "ink-2": "#bcd3c9", hover: "#143026",
              page: "#08140f", surface: "#0e2119", "surface-2": "#132b21", hair: "#1f4436", rail: "#2a5646", stripe: "#08140f", band: "#0e2119", plate: "#1f4436", muted: "#88a398",
              btn: "#1d7a57", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#1d7a57",
              ground: "#08140f", "line-soft": "#1f4436", frame: "#1f4436", secrule: "#1f4436", "accent-ink": "#ffffff", "band-ink": "#eef6f2", svtext: "#eef6f2", svrule: "#1f4436", pctrack: "#173328" },
    },
    // the Jets look in the two blues (Sean, 18 Oct 2026: "another two jets ones but one with the titans blue and another with the unc blue"): the
    // blue and white, no stripes, no outlines (flat). Both blues are too pale to read as type on white (Titans blue 3.2:1, Carolina 2.3:1), so the
    // type — and --flat-ink, the white buttons' type — is a deeper shade of the same blue, as dark as the Jets green (8.4:1 / 8.8:1)
    "jets-titans": {
      name: "Jets · Titans blue", flat: true, blurb: "The Jets look in Titans blue: the blue and white, nothing else — blue bands with white type, the type a deeper shade of the blue, no stripes and no outlines.",
      light: { "flat-ink": "#1d4f81", accent: "#1d4f81", "accent-2": "#4b92db", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#2966a3", pop: "#ffffff", rule: "#dce6f1", "stripe-line": "#4b92db", "accent-wash": "rgba(75, 146, 219, 0.1)", ink: "#1d4f81", "ink-2": "#425e7b", hover: "#edf3fa",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#f0f5fb", hair: "#dce6f1", rail: "#c4d5e8", stripe: "#ffffff", band: "#ffffff", plate: "#dce6f1", muted: "#6e8091",
               btn: "#4b92db", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#4b92db",
               ground: "#ffffff", "line-soft": "#dce6f1", frame: "#dce6f1", secrule: "#dce6f1", "accent-ink": "#ffffff", "band-ink": "#1d4f81", svtext: "#1d4f81", svrule: "#dce6f1", pctrack: "#e5eef8" },
      dark: { accent: "#8cc0f0", "accent-2": "#4b92db", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
              "accent-2-text": "#8cc0f0", pop: "#0c1d33", rule: "#1d3858", "stripe-line": "#4b92db", "accent-wash": "rgba(75, 146, 219, 0.22)", ink: "#eef4fb", "ink-2": "#bccbdd", hover: "#12284a",
              page: "#071322", surface: "#0c1d33", "surface-2": "#11263f", hair: "#1d3858", rail: "#284a72", stripe: "#071322", band: "#0c1d33", plate: "#1d3858", muted: "#8aa0ba",
              btn: "#4b92db", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#4b92db",
              ground: "#071322", "line-soft": "#1d3858", frame: "#1d3858", secrule: "#1d3858", "accent-ink": "#ffffff", "band-ink": "#eef4fb", svtext: "#eef4fb", svrule: "#1d3858", pctrack: "#15304f" },
    },
    "jets-unc": {
      name: "Jets · UNC blue", flat: true, blurb: "The Jets look in Carolina blue: the blue and white, nothing else — Carolina bands with white type, the type a deeper shade of the blue, no stripes and no outlines.",
      light: { "flat-ink": "#204e6f", accent: "#204e6f", "accent-2": "#7bafd4", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#336e99", pop: "#ffffff", rule: "#dde8ef", "stripe-line": "#7bafd4", "accent-wash": "rgba(123, 175, 212, 0.14)", ink: "#204e6f", "ink-2": "#46657c", hover: "#edf4f9",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#f0f6fa", hair: "#dde8ef", rail: "#c6d8e3", stripe: "#ffffff", band: "#ffffff", plate: "#dde8ef", muted: "#6c8393",
               btn: "#7bafd4", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#7bafd4",
               ground: "#ffffff", "line-soft": "#dde8ef", frame: "#dde8ef", secrule: "#dde8ef", "accent-ink": "#ffffff", "band-ink": "#204e6f", svtext: "#204e6f", svrule: "#dde8ef", pctrack: "#e6eff5" },
      dark: { accent: "#9cc6e8", "accent-2": "#7bafd4", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
              "accent-2-text": "#9cc6e8", pop: "#0c1e2b", rule: "#1d3a4f", "stripe-line": "#7bafd4", "accent-wash": "rgba(123, 175, 212, 0.22)", ink: "#eef5fa", "ink-2": "#bccfdc", hover: "#12293a",
              page: "#07131c", surface: "#0c1e2b", "surface-2": "#112736", hair: "#1d3a4f", rail: "#284c66", stripe: "#07131c", band: "#0c1e2b", plate: "#1d3a4f", muted: "#88a2b4",
              btn: "#7bafd4", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#7bafd4",
              ground: "#07131c", "line-soft": "#1d3a4f", frame: "#1d3a4f", secrule: "#1d3a4f", "accent-ink": "#ffffff", "band-ink": "#eef5fa", svtext: "#eef5fa", svrule: "#1d3a4f", pctrack: "#15303f" },
    },
    // the Jets look in mint (Sean, 23 Oct 2026: "a jets style color scheme but make it like a mint green"): Mint (#3eb489) and white, no stripes,
    // no outlines (flat). White type on the mint bands reads at 2.6:1, a little better than Carolina's 2.3; mint is too pale to read as type on
    // white, so the type and --flat-ink are a deep shade of the same green (8.2:1), the links a mid one (5.3:1)
    "jets-mint": {
      name: "Jets · Mint", flat: true, blurb: "The Jets look in mint: mint and white, nothing else — mint bands with white type, the type a deep shade of the green, no stripes and no outlines.",
      light: { "flat-ink": "#165a42", accent: "#165a42", "accent-2": "#3eb489", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#1f7a5a", pop: "#ffffff", rule: "#dbeee6", "stripe-line": "#3eb489", "accent-wash": "rgba(62, 180, 137, 0.12)", ink: "#165a42", "ink-2": "#3c6c5c", hover: "#edf7f3",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#eff8f4", hair: "#dbeee6", rail: "#c3e1d5", stripe: "#ffffff", band: "#ffffff", plate: "#dbeee6", muted: "#6a8c80",
               btn: "#3eb489", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#3eb489",
               ground: "#ffffff", "line-soft": "#dbeee6", frame: "#dbeee6", secrule: "#dbeee6", "accent-ink": "#ffffff", "band-ink": "#165a42", svtext: "#165a42", svrule: "#dbeee6", pctrack: "#e4f3ed" },
      dark: { accent: "#86e0bd", "accent-2": "#3eb489", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
              "accent-2-text": "#86e0bd", pop: "#0d221d", rule: "#1e463b", "stripe-line": "#3eb489", "accent-wash": "rgba(62, 180, 137, 0.22)", ink: "#eef7f4", "ink-2": "#bad6cd", hover: "#13302a",
              page: "#071512", surface: "#0d221d", "surface-2": "#122b25", hair: "#1e463b", rail: "#295a4c", stripe: "#071512", band: "#0d221d", plate: "#1e463b", muted: "#86a59b",
              btn: "#3eb489", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#3eb489",
              ground: "#071512", "line-soft": "#1e463b", frame: "#1e463b", secrule: "#1e463b", "accent-ink": "#ffffff", "band-ink": "#eef7f4", svtext: "#eef7f4", svrule: "#1e463b", pctrack: "#16352d" },
    },
    // the old Cleveland Indians (Sean, 29 Oct 2026: "a color theme that is the old cleveland indians maroon navy and cream white colors"): a cream
    // ground and cream cards, maroon bands and buttons with cream type on them, navy type and the navy stripe under the band — the cream jersey
    // with maroon lettering and navy piping. Dark mode is a navy night with the same maroon bands and cream type. Outlines stay (not a flat
    // scheme); the percentile colours are Savant's
    cleveland: {
      name: "Cleveland", blurb: "The old Cleveland Indians — cream white ground, maroon bands and buttons with cream type, navy type and a navy stripe under the band.",
      light: { accent: "#7a1f33", "accent-2": "#7a1f33", "accent-2-ink": "#f8f1e1", "accent-2-dim": "rgba(248, 241, 225, 0.85)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": "#f8f1e1",
               "accent-2-text": "#8f2a40", pop: "#fbf6ea", rule: "#dccfb3", "stripe-line": "#0c2340", "accent-wash": "rgba(122, 31, 51, 0.12)", ink: "#0c2340", "ink-2": "#35445f", hover: "#f1e7d2",
               page: "#f4ecdc", surface: "#fbf6ea", "surface-2": "#efe6d2", hair: "#dccfb3", rail: "#c9b995", stripe: "#f4ecdc", band: "#fbf6ea", plate: "#dccfb3", muted: "#6f6a5c",
               btn: "#7a1f33", "btn-ink": "#f8f1e1", "btn-line": "#dccfb3", "tab-fill": "#7a1f33",
               ground: "#f4ecdc", "line-soft": "#dccfb3", frame: "#cdbf9e", secrule: "#dccfb3", "accent-ink": "#f8f1e1", "band-ink": "#f8f1e1", svtext: "#0c2340", svrule: "#dccfb3", pctrack: "#e8dfc9" },
      dark: { accent: "#e0a0ae", "accent-2": "#7a1f33", "accent-2-ink": "#f8f1e1", "accent-2-dim": "rgba(248, 241, 225, 0.85)", "on-fill-wash": W + "0.1)", "on-fill-wash-2": W + "0.18)", "on-fill-line": W + "0.35)", "tab-ink": "#f8f1e1",
              "accent-2-text": "#e0a0ae", pop: "#112138", rule: "#233b5c", "stripe-line": "#efe6d4", "accent-wash": "rgba(122, 31, 51, 0.3)", ink: "#efe6d4", "ink-2": "#c8bda6", hover: "#172a46",
              page: "#0b1628", surface: "#112138", "surface-2": "#172a46", hair: "#233b5c", rail: "#2d4a70", stripe: "#0b1628", band: "#112138", plate: "#233b5c", muted: "#98a3b3",
              btn: "#7a1f33", "btn-ink": "#f8f1e1", "btn-line": "#233b5c", "tab-fill": "#7a1f33",
              ground: "#0b1628", "line-soft": "#233b5c", frame: "#233b5c", secrule: "#233b5c", "accent-ink": "#f8f1e1", "band-ink": "#efe6d4", svtext: "#efe6d4", svrule: "#233b5c", pctrack: "#1b2f4c" },
    },
    // the Cincinnati Bengals (Sean, 31 Oct 2026: "Make a Cincinnati bengals theme"): a white ground, Bengal orange bands and buttons with white
    // type on them (3.2:1, as Carolina's bands read), black type and the black stripe under the band. Dark mode is a black night with the same
    // orange bands. Outlines stay (not a flat scheme); the percentile colours are Savant's
    // the outlines black, not grey (Sean, 1 Nov 2026: "for the bengals orange theme can you make it so all the outlines are black"): the frame,
    // rail, button-line and rule tokens here, and the frames drawn in a mix of the ink in styles.css' "Bengals outlines" block
    bengals: {
      name: "Bengals", blurb: "The Cincinnati Bengals — a white ground, Bengal orange bands and buttons with white type, black type, a black stripe under the band and black outlines.",
      light: { accent: "#fb4f14", "accent-2": "#fb4f14", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#c2380a", pop: "#ffffff", rule: "#111111", "stripe-line": "#111111", "accent-wash": "rgba(251, 79, 20, 0.1)", ink: "#111111", "ink-2": "#3d3a38", hover: "#fdf1ec",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#f7f3f1", hair: "#ebe2dc", rail: "#111111", stripe: "#ffffff", band: "#ffffff", plate: "#ebe2dc", muted: "#6e6762",
               btn: "#fb4f14", "btn-ink": "#ffffff", "btn-line": "#111111", "tab-fill": "#fb4f14",
               ground: "#ffffff", "line-soft": "#111111", frame: "#111111", secrule: "#111111", "accent-ink": "#ffffff", "band-ink": "#ffffff", svtext: "#111111", svrule: "#ebe2dc", pctrack: "#f1ebe7" },
      dark: { accent: "#ff8a5c", "accent-2": "#fb4f14", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
              "accent-2-text": "#ff8a5c", pop: "#1a1a1a", rule: "#333130", "stripe-line": "#fb4f14", "accent-wash": "rgba(251, 79, 20, 0.22)", ink: "#f4f1ef", "ink-2": "#cfc8c3", hover: "#242220",
              page: "#0d0d0d", surface: "#1a1a1a", "surface-2": "#222120", hair: "#333130", rail: "#45413e", stripe: "#0d0d0d", band: "#1a1a1a", plate: "#333130", muted: "#9e9894",
              btn: "#fb4f14", "btn-ink": "#ffffff", "btn-line": "#333130", "tab-fill": "#fb4f14",
              ground: "#0d0d0d", "line-soft": "#333130", frame: "#333130", secrule: "#333130", "accent-ink": "#ffffff", "band-ink": "#f4f1ef", svtext: "#f4f1ef", svrule: "#333130", pctrack: "#2a2827" },
    },
    // the Bengals in the Jets' flat look (Sean, the same ask: "a bengals theme in the jets style"): Bengal orange and white, no stripes and no
    // outlines; the type and --flat-ink are the Bengals' black (orange is too pale to read as type on white, 3.2:1), the links a deep orange
    "jets-bengals": {
      name: "Jets · Bengals", flat: true, blurb: "The Jets look in Bengal orange: orange and white with black type — orange bands with white type, no stripes and no outlines.",
      light: { "flat-ink": "#111111", accent: "#111111", "accent-2": "#fb4f14", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.14)", "on-fill-wash-2": W + "0.24)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
               "accent-2-text": "#c2380a", pop: "#ffffff", rule: "#f2e2da", "stripe-line": "#fb4f14", "accent-wash": "rgba(251, 79, 20, 0.1)", ink: "#111111", "ink-2": "#3d3a38", hover: "#fdf1ec",
               page: "#ffffff", surface: "#ffffff", "surface-2": "#fbf3ef", hair: "#f2e2da", rail: "#e8cfc3", stripe: "#ffffff", band: "#ffffff", plate: "#f2e2da", muted: "#6e6762",
               btn: "#fb4f14", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#fb4f14",
               ground: "#ffffff", "line-soft": "#f2e2da", frame: "#f2e2da", secrule: "#f2e2da", "accent-ink": "#ffffff", "band-ink": "#111111", svtext: "#111111", svrule: "#f2e2da", pctrack: "#f8ece6" },
      dark: { accent: "#ff8a5c", "accent-2": "#fb4f14", "accent-2-ink": "#ffffff", "accent-2-dim": W + "0.85)", "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.4)", "tab-ink": "#ffffff",
              "accent-2-text": "#ff8a5c", pop: "#1a1a1a", rule: "#333130", "stripe-line": "#fb4f14", "accent-wash": "rgba(251, 79, 20, 0.22)", ink: "#f4f1ef", "ink-2": "#cfc8c3", hover: "#242220",
              page: "#0d0d0d", surface: "#1a1a1a", "surface-2": "#222120", hair: "#333130", rail: "#45413e", stripe: "#0d0d0d", band: "#1a1a1a", plate: "#333130", muted: "#9e9894",
              btn: "#fb4f14", "btn-ink": "#ffffff", "btn-line": "transparent", "tab-fill": "#fb4f14",
              ground: "#0d0d0d", "line-soft": "#333130", frame: "#333130", secrule: "#333130", "accent-ink": "#ffffff", "band-ink": "#f4f1ef", svtext: "#f4f1ef", svrule: "#333130", pctrack: "#2a2827" },
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

  // The customizer (Sean, 1 Nov 2026: "instead of like pre set color schemes we have here can we instead have like a customizer ... a two color
  // scheme or like a three color one ... choose your own colors or choose professional sports teams colors"): a scheme built from up to four
  // colours, each with a job — main (the bands, buttons and tab fills), text (the type and lines), stripe (the rule under the bands) and
  // highlight (links and accent type). Two colours: the stripe is the text colour and the highlight a deep shade of the main; three: a stripe of
  // its own. Saved per device as draft2027.custom = {colors: {main, text, stripe, accent}, n, flat, name}; S.custom is built from it here, before the
  // page paints, and rebuilt by setCustom. Colours that wouldn't read are moved until they do (text darkened to 4.5:1 on white, and so on).
  const hx = (h) => { const m = /^#?([0-9a-f]{6})$/i.exec(h || ""); return m ? [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)) : null; };
  const toHex = (c) => "#" + c.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
  const mix = (a, b, t) => { const x = hx(a), y = hx(b); return x && y ? toHex(x.map((v, i) => v + (y[i] - v) * t)) : a; };   // t of the way from a to b
  const lum = (h) => { const c = hx(h); if (!c) return 0; const v = c.map((x) => x / 255).map((x) => (x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4))); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const ratioOf = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const rgba = (h, a) => { const c = hx(h) || [0, 0, 0]; return `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${a})`; };
  const toward = (c, to, bg, r) => { let t = 0, o = c; while (ratioOf(o, bg) < r && t < 1) { t += 0.05; o = mix(c, to, t); } return o; };   // move c toward `to` until it reads r:1 on bg
  function buildCustom(cfg) {
    const C = (cfg && cfg.colors) || {}, n = (cfg && cfg.n) || 2, flat = !!(cfg && cfg.flat);
    const M = hx(C.main) ? C.main : "#7bafd4", T0 = hx(C.text) ? C.text : "#0c2340";
    // every colour is the user's own since 1 Nov 2026 ("don't even give the option for selecting 2 3 or 4 color things just give the user the ability to
    // select the color for every necessary piece"): a saved n only fills a role an older save never had
    const S0 = hx(C.stripe) && !(n < 3 && !C.lines) ? C.stripe : T0, A0 = hx(C.accent) && !(n < 4 && !C.lines) ? C.accent : M;
    const LN = hx(C.lines) ? C.lines : "#111111", PG = hx(C.page) ? C.page : "#ffffff";
    const T = toward(T0, "#000000", "#ffffff", 7);                              // the type: dark enough to read as body text
    const onM = ratioOf(M, "#ffffff") >= 2 ? "#ffffff" : (ratioOf(M, T) >= 4.5 ? T : "#141414");   // type on the main colour
    const onDim = onM === "#ffffff" ? W + "0.85)" : rgba(onM, 0.72);
    const link = toward(A0, "#000000", "#ffffff", 4.5);                         // links / accent type on white
    const hair = mix(T, "#ffffff", 0.86), rail = mix(T, "#ffffff", 0.76), soft = mix(M, "#ffffff", 0.93);
    const stripe = flat ? M : S0;
    const light = { accent: link, "accent-2": M, "accent-2-ink": onM, "accent-2-dim": onDim, "on-fill-wash": onM === "#ffffff" ? W + "0.14)" : rgba(onM, 0.08),
      "on-fill-wash-2": onM === "#ffffff" ? W + "0.24)" : rgba(onM, 0.14), "on-fill-line": onM === "#ffffff" ? W + "0.4)" : rgba(onM, 0.3), "tab-ink": onM,
      "accent-2-text": link, pop: "#ffffff", rule: flat ? hair : hair, "stripe-line": stripe, "accent-wash": rgba(M, 0.12), ink: T, "ink-2": mix(T, "#ffffff", 0.22), hover: soft,
      page: "#ffffff", surface: "#ffffff", "surface-2": mix(M, "#ffffff", 0.94), hair, rail, stripe: "#ffffff", band: "#ffffff", plate: hair, muted: toward(mix(T, "#ffffff", 0.5), T, "#ffffff", 4),
      btn: M, "btn-ink": onM, "btn-line": flat ? "transparent" : rail, "tab-fill": M,
      ground: PG, "line-soft": hair, frame: flat ? hair : rail, secrule: hair, "accent-ink": onM, "band-ink": onM, svtext: T, svrule: hair, pctrack: mix(M, "#ffffff", 0.88),
      outline: LN, xl: hx(C.grid) ? C.grid : LN, xlt: hx(C.frame) ? C.frame : (hx(C.grid) ? C.grid : LN) };   // table lines and the thick frame (2 Nov 2026)
    if (hx(C.sub)) light.muted = toward(C.sub, "#000000", "#ffffff", 3);   // the subtitles / grey text (2 Nov 2026)
    if (hx(C.ref)) light.ref = toward(C.ref, "#000000", "#ffffff", 3);       // the references: "All hitters →", About, Glossary …
    light.refbold = !!(cfg && cfg.refBold);
    if (hx(C.table)) { light.tbl = C.table; light["tbl-ink"] = ratioOf(C.table, T) >= 4.5 ? T : "#ffffff"; }   // the tables' cells (2 Nov 2026)
    if (hx(C.picked)) { light.fbsel = C.picked; light["fbsel-ink"] = ratioOf(C.picked, "#ffffff") >= 3 ? "#ffffff" : T; }   // the picked button in a filter bar (2 Nov 2026)
    if (hx(C.fbar)) { light.fbar = C.fbar; light["fbar-ink"] = ratioOf(C.fbar, T) >= 4.5 ? T : "#ffffff"; }   // the filter bars (2 Nov 2026)
    if (hx(C.sorted)) { light.sorthd = C.sorted; light["sorthd-ink"] = ratioOf(C.sorted, "#ffffff") >= 3 ? "#ffffff" : T; }   // the sorted column's name (2 Nov 2026)
    if (hx(C.heading)) light.heading = toward(C.heading, "#000000", "#ffffff", 3);   // the bold headings (2 Nov 2026), readable on white
    if (flat) light["flat-ink"] = T;
    const page = mix(T, "#0b0c0f", 0.82), surf = mix(page, "#ffffff", 0.05), surf2 = mix(page, "#ffffff", 0.09), dh = mix(page, "#ffffff", 0.16);
    const lite = toward(A0, "#ffffff", page, 4.5);
    const dark = { accent: lite, "accent-2": M, "accent-2-ink": onM, "accent-2-dim": onDim, "on-fill-wash": W + "0.12)", "on-fill-wash-2": W + "0.22)", "on-fill-line": W + "0.35)", "tab-ink": onM,
      "accent-2-text": lite, pop: surf, rule: dh, "stripe-line": flat ? M : toward(S0, "#ffffff", page, 1.6), "accent-wash": rgba(M, 0.24), ink: "#eef0f3", "ink-2": "#c5c9d0", hover: surf2,
      page, surface: surf, "surface-2": surf2, hair: dh, rail: mix(page, "#ffffff", 0.24), stripe: page, band: surf, plate: dh, muted: "#8e939c",
      btn: M, "btn-ink": onM, "btn-line": flat ? "transparent" : dh, "tab-fill": M,
      ground: page, "line-soft": dh, frame: dh, secrule: dh, "accent-ink": onM, "band-ink": "#eef0f3", svtext: "#eef0f3", svrule: dh, pctrack: mix(page, "#ffffff", 0.12) };
    return { name: (cfg && cfg.name) || "Custom", flat, custom: true, blurb: "Your own colours, from the customizer below.", light, dark };
  }
  const readCustom = () => { try { const v = localStorage.getItem("draft2027.custom"); return v ? JSON.parse(v) : null; } catch { return null; } };
  if (readCustom()) S.custom = buildCustom(readCustom());

  // the site's type (Sean, 30 Sep 2026, from the Percentile Bar Studio page: "adjust the entire font of the site to be this
  // font"): Barlow Condensed for headings, names and big numbers, Source Sans 3 for everything else. This file loads them
  // (in <head>, before the page paints) rather than index.html, whose template lives on the Mac and isn't synced.
  const F = {
    studio: { name: "Barlow Condensed + Source Sans 3", blurb: "Condensed headings, an easy-reading text face — the same on every page and device.",
              google: "family=Barlow+Condensed:ital,wght@0,400;0,500;0,600;0,700;0,800;1,800&family=Source+Sans+3:ital,wght@0,400..700;1,400..700&family=Roboto+Condensed:wght@700",   // Roboto: the percentile bubbles' digits only
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
  const lumOf = (hex) => { const m = /^#?([0-9a-f]{6})$/i.exec(hex || ""); if (!m) return null; const v = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255).map((x) => (x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4))); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const pickInk = (bg, cands) => { const lb = lumOf(bg); if (lb == null) return cands[0]; let best = cands[0], bc = 0;
    for (const c of cands) { const l = lumOf(c); if (l == null) continue; const r = (Math.max(l, lb) + 0.05) / (Math.min(l, lb) + 0.05); if (r >= 4.5) return c; if (r > bc) { bc = r; best = c; } } return best; };

  function apply() {
    const cur = current();
    if (cur.theme !== "system" && root.dataset.theme !== cur.theme) root.dataset.theme = cur.theme;   // explicit choice; "system" leaves the host's / OS value alone
    const sc = S[cur.scheme];
    const tokens = Object.assign({}, sc.light, isDark() ? sc.dark : {});
    for (const k of setKeys) if (!(k in tokens)) root.style.removeProperty("--" + k);
    for (const [k, v] of Object.entries(tokens)) root.style.setProperty("--" + k, v);
    setKeys = Object.keys(tokens);
    // the light palette's ink in dark mode too: a white button or the light band keeps it (20 Oct 2026 — the dark ink is near-white, and the
    // header's pages, Filters / Raw and the Settings tabs read white on white)
    root.style.setProperty("--ink-day", sc.light.ink);
    // the ink for type on the band colour (accent-2), picked by contrast: the band ink where it reads (4.5:1), else the light palette's ink, white
    // or near-black, whichever reads best (20 Oct 2026: Titans' dark mode had near-white on its light blue, Warm near-black on near-black)
    root.style.setProperty("--band2-ink", pickInk(tokens["accent-2"], [tokens["band-ink"], sc.light.ink, "#ffffff", "#141414"]));
    // the phone's bottom bar on the band colour (29 Oct 2026): white type unless the band is too light for it (Warm's near-white dark band, then the
    // light ink), and the current page's capsule the light ink with white type where that ink reads on the band (Titans' navy on Carolina blue, a deep
    // green on mint), else white with the ink's type (Jets and UNC, whose band is their ink; Warm's near-black band)
    const ratio = (a, b) => { const la = lumOf(a), lb = lumOf(b); return la == null || lb == null ? 1 : (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05); };
    const band = tokens["accent-2"], inkDay = sc.light.ink, selInk = ratio(inkDay, band) >= 2;
    root.style.setProperty("--band2-type", ratio("#ffffff", band) >= 1.9 ? "#ffffff" : inkDay);
    root.style.setProperty("--band2-sel", selInk ? inkDay : "#ffffff");
    root.style.setProperty("--band2-sel-ink", selInk ? "#ffffff" : inkDay);
    // the rule under the phone's top bar (30 Oct 2026: "a line break or bar or separator between the site header and yordans header"): the red
    // stripe where the scheme has one that shows on its band, else its hairline colour (UNC's Carolina blue under navy), else red or white
    root.style.setProperty("--phsep", [tokens["stripe-line"], tokens.rule, "#c8102e", "#ffffff"].find((c) => ratio(c, band) >= 1.5) || "#c8102e");
    // black outlines on every scheme with outlines (Sean, 1 Nov 2026: "I want the black outline to be a thing for all the non jets themed themes"):
    // in light mode the frame, rail, button-line and soft-line tokens are black whatever the scheme says; dark mode and the flat (Jets) look keep theirs
    // (the customizer's Lines colour in place of black, and as the tables' lines, --xl, since 1 Nov 2026)
    const black = !sc.flat && !isDark(), ol = sc.light.outline || "#111111";
    root.style.setProperty("--outline", ol);
    // the customizer's Headings colour (Sean, 2 Nov 2026: "make it so I can make all of like the bold header text a different color than the regular
    // text"): --heading, and data-heading on <html> so styles.css paints the page's titles with it (light mode; dark mode keeps its light type)
    // the customizer's Sorted header colour (Sean, 2 Nov 2026: "the column that is sorted allow me to choose in the appearance color selector what
    // color that column header gets to be"): --sorthd / --sorthd-ink and data-sorthd, in both modes (the bands are the same colour in both)
    // the customizer's Filter bar colour (Sean, 2 Nov 2026: "I also want a color setting for the like filters bars too"): --fbar / --fbar-ink, data-fbar
    // the customizer's Table colour (Sean, 2 Nov 2026: "allow a table color option as well"): --tbl / --tbl-ink, data-tbl
    // the customizer's References colour and bold switch (Sean, 2 Nov 2026: "the references would apply to the like text that is all hitters all
    // pitchers that takes you to the table (and for those ones add a bold option too)"): --ref, data-ref, data-refbold
    if (sc.light.ref && !isDark()) { root.style.setProperty("--ref", sc.light.ref); root.dataset.ref = "1"; } else { root.style.removeProperty("--ref"); delete root.dataset.ref; }
    if (sc.light.refbold) root.dataset.refbold = "1"; else delete root.dataset.refbold;
    if (sc.light.tbl && !isDark()) { root.style.setProperty("--tbl", sc.light.tbl); root.style.setProperty("--tbl-ink", sc.light["tbl-ink"]); root.dataset.tbl = "1"; }
    else { root.style.removeProperty("--tbl"); root.style.removeProperty("--tbl-ink"); delete root.dataset.tbl; }
    if (sc.light.fbar && !isDark()) { root.style.setProperty("--fbar", sc.light.fbar); root.style.setProperty("--fbar-ink", sc.light["fbar-ink"]); root.dataset.fbar = "1"; }
    else { root.style.removeProperty("--fbar"); root.style.removeProperty("--fbar-ink"); delete root.dataset.fbar; }
    // the customizer's Picked button colour (Sean, 2 Nov 2026: "a color option for what standard is highlighted as"): --fbsel / --fbsel-ink, data-fbsel
    if (sc.light.fbsel) { root.style.setProperty("--fbsel", sc.light.fbsel); root.style.setProperty("--fbsel-ink", sc.light["fbsel-ink"]); root.dataset.fbsel = "1"; }
    else { root.style.removeProperty("--fbsel"); root.style.removeProperty("--fbsel-ink"); delete root.dataset.fbsel; }
    if (sc.light.sorthd) { root.style.setProperty("--sorthd", sc.light.sorthd); root.style.setProperty("--sorthd-ink", sc.light["sorthd-ink"]); root.dataset.sorthd = "1"; }
    else { root.style.removeProperty("--sorthd"); root.style.removeProperty("--sorthd-ink"); delete root.dataset.sorthd; }
    const hd = !isDark() && sc.light.heading;
    if (hd) { root.style.setProperty("--heading", hd); root.dataset.heading = "1"; } else { root.style.removeProperty("--heading"); delete root.dataset.heading; }
    if (sc.light.xl && !isDark()) root.style.setProperty("--xl", sc.light.xl); else root.style.removeProperty("--xl");
    if (sc.light.xlt && !isDark()) root.style.setProperty("--xlt", sc.light.xlt); else root.style.removeProperty("--xlt");
    for (const k of ["frame", "rail", "btn-line", "line-soft"]) {
      if (black) root.style.setProperty("--" + k, ol);
      else if (k in tokens) root.style.setProperty("--" + k, tokens[k]); else root.style.removeProperty("--" + k);
    }
    root.dataset.scheme = cur.scheme;
    root.toggleAttribute("data-flat", !!sc.flat);   // the Jets look: styles.css takes every outline off under it
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
    // the status bar is iOS's own, filled from theme-color (9 Nov 2026): under a translucent one iOS 27.2 blurs the page it draws over, header
    // colour and all, so the home-screen app no longer draws under it (index.html says the same; was black-translucent from 2 Nov 2026)
    const sb = document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]'); if (sb) sb.content = "default";
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = root.style.getPropertyValue("--hdrc").trim() || tokens["accent-2"];   // a header theme's own colour when one is on (app.js HDR)
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
  const hasOwn = () => [LS.scheme, LS.font, LS.theme, LS.view].some((k) => get(k) != null) || !!window.DRAFT_TABLES.own();
  const useDefaults = () => { for (const k of [LS.scheme, LS.font, LS.theme, LS.view]) { try { localStorage.removeItem(k); } catch { /* */ } } delete root.dataset.theme; apply(); applyView(); window.DRAFT_TABLES.clear(); if (window.DRAFT_BORDERS) window.DRAFT_BORDERS.clear(); };
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
  // the customizer's own calls: the saved colours, and saving a new set (it becomes this device's scheme at once)
  const customCfg = () => readCustom();
  const setCustom = (cfg) => { S.custom = buildCustom(cfg); put("draft2027.custom", cfg); set({ scheme: "custom" }); };
  return { schemes: S, fonts: F, defaults: DEFAULTS, current, isDark, apply, set, customCfg, setCustom, buildCustom, contrast: ratioOf, preloadFonts, viewPref, applyView, setView, view: () => root.dataset.view, hasOwn, useDefaults };
})();
