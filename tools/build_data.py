"""Build data.js for the 2027 Draft Board.

Usage:  python3 build_data.py [--end YYYY-MM-DD]

Sources
  - Statcast pitch-level data via pybaseball (cached in ~/.pybaseball, only new days download)
  - Baseball Savant batted-ball leaderboard  -> Air% and Pull Air% (Savant's own direction labels)
  - MLB Stats API                            -> names, teams, primary position, games by position, G/GS

Output: data.js  (window.DRAFT_DATA = {...}) next to index.html
"""
import argparse, json, socket, sys, time, io, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import joblib
import pybaseball as pb

HERE = Path(__file__).resolve().parent
SEASON = 2026
SEASON_START = f"{SEASON}-03-01"

# ---- pools & eligibility -------------------------------------------------------------------
GAME_TYPES = {"R"}           # Statcast game types to keep: R regular season; S spring; F/D/L/W postseason (build_history sets these)
API_GAME_TYPE = "R"          # the MLB Stats API game type for official AB / IP / ERA (R, S or P)
MIN_PA_HITTER = 1            # floor for shipping a hitter in data.js: everyone who played, so a call-up's page is there
MIN_BF_PITCHER = 1           # (was 20 — a 12-BF debut start left River Ryan off the site); the page applies Min AB / IP
CONST_MIN_BF = 20            # the league constants are still derived from pitchers with a real sample
STARTER_SHARE = 0.5          # GS / G at or above this = SP, else RP
WOBA_SCALE = 1.25            # runs per PA per point of wOBA (FanGraphs' yearly value sits at 1.2-1.3)
BB_TYPES = ["gb", "ld", "fb", "pu"]   # batted-ball types for the luck-neutral ERA (untyped balls in play use the BIP average)
DEFAULT_MIN = {"H": 300, "SP": 50, "RP": 20, "P": 20}   # page defaults: PA for hitters, IP for pitchers
REF_MIN_PA = 300                                        # hitter percentiles are always measured against this population
# Directional xwOBA: the gradient-boosted model from model-workspace/model2.py (EV, launch angle, sprint speed,
# pull & spray angle, batter side), trained on 2015-2025 batted balls, era-neutral -> rescaled to this season
# v3 (model-workspace/model3.py): same inputs as v2, seasons weighted by recency (3-year half-life) so the
# post-shift-ban years carry the ground-ball direction. Scoring 2026 off a fit through 2025, v2 ran 2.5%
# hot (RMSE .3640); v3 comes out at 0.999 of the league (RMSE .3588).
DIR_MODEL = HERE.parent / "model-workspace" / "v3_dir.joblib"
BA_MODEL = HERE.parent / "model-workspace" / "v3_ba.joblib"      # the same recipe, predicting hits
SLG_MODEL = HERE.parent / "model-workspace" / "v3_slg.joblib"    # ... and total bases
DIR_FEATS = ["launch_speed", "launch_angle", "sprint_speed", "pull_angle", "spray_angle", "stand_R"]

# ---- metrics ------------------------------------------------------------------------------
# key, label, column, higher-is-better, decimals, unit
HITTER_METRICS = [
    ("ev",   "Avg EV",      "avg_EV",       True,  1, "mph"),
    ("brl",  "Barrel%",     "Barrel_pct",   True,  1, "%"),
    ("pull", "Pull Air%",   "PullAir_pct",  True,  1, "%"),
    ("air",  "Air%",        "Air_pct",      True,  1, "%"),
    ("osw",  "O-Swing%",    "OSwing_pct",   False, 1, "%"),
    ("zsw",  "Z-Swing%",    "ZSwing_pct",   True,  1, "%"),
    ("zcon", "Z-Contact%",  "ZContact_pct", True,  1, "%"),
    ("ocon", "O-Contact%",  "OContact_pct", True,  1, "%"),
    ("whf",  "Whiff%",      "Whiff_pct",    False, 1, "%"),
]
PITCHER_METRICS = [       # the row columns on the list pages (SwStr% lives on the card, under Whiff%)
    ("whf",  "Whiff%",      "Whiff_pct",    True,  1, "%"),
    ("strk", "Strike%",     "Strike_pct",   True,  1, "%"),
    ("gb",   "GB%",         "GB_pct",       True,  1, "%"),
]

# Default hitter rank: the wOBA percentile blend (Formula 1, no bat speed) fit in
# "wOBA Percentile Blend 2026.xlsx" - weights sum to 100. Inputs are percentiles (0-100,
# already flipped so 100 = best); "zmo" is the percentile of Z-Swing% minus O-Swing%.
HITTER_SCORE_WEIGHTS = {"brl": 40.5, "ev": 11.6, "zcon": 16.9, "ocon": 17.2,
                        "pull": 0.2, "osw": 4.5, "zmo": 9.0}
# Default pitcher rank: average of Whiff% and Strike% percentiles.
PITCHER_SCORE_WEIGHTS = {"whf": 50.0, "strk": 50.0}

WHIFF = {"swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt", "bunt_foul_tip"}
SWING = WHIFF | {"foul", "hit_into_play", "foul_bunt"}
ZERO_NUM = {"field_error", "fielders_choice", "fielders_choice_out"}
EXCLUDE = {"sac_bunt", "truncated_pa", "catcher_interf", "intent_walk"}
HITS = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
COLS = ["game_date", "game_type", "game_pk", "batter", "pitcher", "stand", "p_throws", "description", "zone",
        "type", "events", "launch_speed", "launch_angle", "launch_speed_angle", "bb_type", "hc_x", "hc_y",
        "inning", "inning_topbot", "at_bat_number", "outs_when_up", "woba_value", "woba_denom",
        "estimated_woba_using_speedangle", "estimated_ba_using_speedangle", "estimated_slg_using_speedangle",
        "bat_speed", "pitch_type", "release_speed", "release_extension", "des",
        "release_spin_rate", "spin_axis", "pfx_x", "pfx_z", "release_pos_x", "release_pos_z", "arm_angle"]   # the last seven: Stuff
MIX_COLS = {"mxgb": "gb", "mxpu": "pu", "mxldp": "ld_p", "mxldc": "ld_c", "mxldo": "ld_o", "mxfbp": "fb_p", "mxfbc": "fb_c",
            "mxfbo": "fb_o", "mxx": "x"}                                  # x = an air ball with no direction
MIX = None          # the batted-ball mix's league values for the dataset being built (set by pitch_flags)
PULL_LINE = 16      # spray angle (deg toward the pull side) beyond which a ball is "pulled"; 16 matches Savant's Pull Air% best
AIR_TYPES = {"fly_ball", "line_drive", "popup"}
OUTS = {"strikeout": 1, "strikeout_double_play": 2, "field_out": 1, "force_out": 1, "grounded_into_double_play": 2,
        "double_play": 2, "triple_play": 3, "sac_fly": 1, "sac_bunt": 1, "sac_fly_double_play": 2,
        "sac_bunt_double_play": 2, "fielders_choice_out": 1, "fielders_choice": 1, "other_out": 1, "batter_interference": 1}
NON_AB = {"walk", "intent_walk", "hit_by_pitch", "sac_fly", "sac_fly_double_play", "sac_bunt", "sac_bunt_double_play",
          "catcher_interf", "truncated_pa"}
# per-day row layouts shipped to the page (data.js -> meta.dayFields); day = index into meta.days
# rows are per player-day-handedness (hand: 0 = vs LHP/LHB, 1 = vs RHP/RHB; home: 1 = home game); evs = that
# row's exit velocities (bbe and avg EV derive from it)
HITTER_DAY = ["day", "hand", "home", "pit", "sw", "whf", "zpit", "opit", "zsw", "osw", "zcon", "ocon", "brl",
              "air", "pullair", "pa", "ab", "bb", "k", "wnum", "wden", "xnum", "xden", "hh", "ss", "strk", "bsn", "bssum",
              "bbe", "evsum", "dnum", "pulln", "ld", "gbh", "puh", "evs", "bbt", "bip", "evn", "oppn", "h", "tb", "xbsum", "xssum", "dbsum", "dssum", "mixsum", "mixn",
              "mxgb", "mxpu", "mxldp", "mxldc", "mxldo", "mxfbp", "mxfbc", "mxfbo", "mxx", "hr"]   # hr: home runs (the fantasy page splits his official line by hand with these); mixsum / mixn = batted-ball mix value (Mix wOBA), mx* = its balls by bucket (mxx: air, no direction); dnum = directional-xwOBA numerator; evs = that row's exit velocities (no bunts); trailing fields (older files lack them): bbt = typed balls in play, bip = all balls in play, evn = EV-eligible (tracked, no bunt)
# The hitter card, grouped. key, label, higher-is-better, decimals, unit. Keys not in HITTER_METRICS are card-only.
HITTER_CARD = [
    ("Outcomes",             [("woba", "wOBA", True, 3, ""), ("xws", "xwOBA", True, 3, ""), ("xwd", "dxwOBA", True, 3, "")]),
    ("Batted-ball quality",  [("ev", "Avg EV", True, 1, "mph"), ("brl", "Barrel%", True, 1, "%")]),   # the rest fold out under Barrel%
    ("Swing decisions",      [("osw", "O-Swing%", False, 1, "%"), ("bb", "BB%", True, 1, "%")]),
    ("Contact",              [("whf", "Whiff%", False, 1, "%"), ("k", "K%", False, 1, "%")]),
    ("Batted-ball distribution", [("air", "Air%", True, 1, "%"), ("pull", "Pull Air%", True, 1, "%")]),   # GB% is Air%'s mirror — it folds out under it
]
HITTER_CARD_LEFT = 2   # groups in the card's left column
HITTER_CARD_RULES = []   # rows that start a ruled-off block on the hitter card (none: the bars carry their own separators)
# breakdown rows that fold out under a card metric: key -> [(key, label, higher-is-better, decimals, unit)]
HITTER_SUB = {"woba": [("ba", "BA", True, 3, ""), ("slg", "SLG", True, 3, "")],
              "xws": [("xba", "xBA", True, 3, ""), ("xslg", "xSLG", True, 3, "")],
              "xwd": [("dxba", "dxBA", True, 3, ""), ("dxslg", "dxSLG", True, 3, "")],
              "brl": [("hh", "Hard-Hit%", True, 1, "%"), ("ss", "LA Sweet-Spot%", True, 1, "%"), ("ev90", "90th% EV", True, 1, "mph"),
                      ("maxev", "Max EV", True, 1, "mph"), ("bs", "Bat speed", True, 1, "mph")],
              "air": [("fb", "FB%", True, 1, "%"), ("ld", "LD%", True, 1, "%"), ("pu", "Popup%", False, 1, "%"), ("gb", "GB%", False, 1, "%")],
              "osw": [("zsw", "Z-Swing%", True, 1, "%"), ("osw", "O-Swing%", False, 1, "%"), ("zmo", "(Z−O) Swing%", True, 1, "%")],
              "whf": [("zcon", "Z-Contact%", True, 1, "%"), ("ocon", "O-Contact%", True, 1, "%")]}
PITCHER_DAY = ["day", "hand", "home", "pit", "sw", "whf", "strk", "bip", "gb", "bf", "k", "bb", "outs", "wnum", "wden", "gs",
               "cs", "zpit", "opit", "zsw", "osw", "zcon", "hr", "hbp", "fbt", "pu", "bbe", "brl", "hh", "evsum",
               "fbn", "fbv", "extn", "exts",
               "ld", "wbip", "wgb", "wld", "wfb", "wpu", "evn", "h", "stn", "stw", "stg", "stp", "sts"]   # h: hits allowed (fantasy splits by hand); stn / stw / stg / stp / sts: graded pitches and their summed whiff, ground-ball, popup and strike chances (Stuff); luck-neutral ERA inputs: line drives, wOBA numerator on balls in play and by type; evn = EV-eligible balls (no bunts)
# per-game earned runs (from MLB game logs) ride along as "P<id>:er" rows: [day, home, er]
FASTBALLS = {"FF", "SI", "FT"}
PITCHER_CARD = [
    ("Whiffs and strikes",   [("whf", "Whiff%", True, 1, "%"), ("strk", "Strike%", True, 1, "%")]),
    ("Swing & miss",         [("k", "K%", True, 1, "%"), ("whf", "Whiff%", True, 1, "%"), ("csw", "CSW%", True, 1, "%")]),
    ("Zone & chase",         [("bb", "BB%", False, 1, "%"), ("strk", "Strike%", True, 1, "%")]),
    ("Results",              [("kbb", "K-BB%", True, 1, "%"), ("era", "ERA", False, 2, "")]),
    ("Batted ball",          [("gb", "GB%", True, 1, "%"), ("pu", "Popup%", True, 1, "%"), ("mera", "Mix ERA", False, 2, "")]),
    # the four rates a pitcher owns outright, averaged (derived in the app from the four below it)
    ("Process score",        [("wsgp", "WSGP", True, 1, "")]),
    ("Stuff",                [("stuff", "Stuff+", True, 0, ""), ("fbv", "Fastball velo", True, 1, "mph"), ("ext", "Extension", True, 1, "ft")]),
    # what the ERA should be and what he's giving up: the expected / underlying marks beside contact quality
    ("Expected & contact",   [("uk", "uK%", True, 1, "%"), ("ubb", "uBB%", False, 1, "%"),   # the fitted process rates
                              ("ukb", "u(K-BB%)", True, 1, "%"),   # u(K-BB%) is derived in the app (expected K% − expected BB%)
                              ("uera", "uERA", False, 2, ""), ("nera", "Luck-neutral ERA", False, 2, ""),
                              ("siera", "SIERA", False, 2, ""), ("fip", "FIP", False, 2, ""),
                              ("ev", "Avg EV", False, 1, "mph"), ("hh", "Hard-Hit%", False, 1, "%"), ("brl", "Barrel%", False, 1, "%")]),
]
PITCHER_CARD_LEFT = 3   # groups in the card's left column (the folded group below doesn't sit in either)
PITCHER_CARD_FOLD = ["Expected & contact"]   # groups that ride below the card as a fold-out instead of a column
# fold-out rows under a pitcher card metric
PITCHER_SUB = {"kbb": [("k", "K%", True, 1, "%"), ("bb", "BB%", False, 1, "%")],
               "whf": [("swstr", "SwStr%", True, 1, "%"), ("zcon", "Z-Contact%", False, 1, "%")],
               "strk": [("zone", "Zone%", True, 1, "%"), ("osw", "O-Swing%", True, 1, "%")],
               "stuff": [("swhf", "Whiff+", True, 0, ""), ("sstr", "Strike+", True, 0, ""), ("sbb", "Batted-ball+", True, 0, "")]}


def siera_raw(k, bb, gb, fb, pu, pa):
    """Swartz's SIERA (2011 form) before the seasonal constant."""
    if not pa:
        return None
    so, w, x = k / pa, bb / pa, (gb - fb - pu) / pa
    # the quadratic net-GB term is subtracted when net GB is positive and added when negative (Swartz 2011)
    return (6.145 - 16.986 * so + 11.434 * w - 1.858 * x + 7.653 * so * so
            - 6.664 * x * abs(x) + 10.130 * so * x - 5.195 * w * x)

UA = {"User-Agent": "Mozilla/5.0 (draft-board data build)"}


def log(*a):
    print(*a, flush=True)


# ============================================================================================
# 1. Statcast
# ============================================================================================
FRESH_DAYS = 3        # the last days before --end are always re-read from Savant (see load_statcast)


def savant_search_days(start: str, end: str, game_types, fresh: bool = False) -> pd.DataFrame:
    """Pitch-level rows straight from Savant's search, one day at a time (spring training and the postseason:
    pybaseball's statcast() clips its dates to the regular season). Cached per day under .cache/savant — but never an
    empty day, which may only be a day Savant hasn't posted yet. fresh=True skips the cache (the last few days)."""
    cache = Path(__file__).resolve().parent / ".cache" / "savant"
    cache.mkdir(parents=True, exist_ok=True)
    gt = "".join(f"{t}%7C" for t in sorted(game_types))
    out = []
    for day in pd.date_range(start, end):
        ds = str(day.date())
        f = cache / f"{ds}-{''.join(sorted(game_types))}.csv.gz"
        if f.exists() and not fresh:
            d = pd.read_csv(f, low_memory=False)
        else:
            url = ("https://baseballsavant.mlb.com/statcast_search/csv?all=true&hfPT=&hfAB=&hfGT=" + gt +
                   f"&hfPR=&hfZ=&stadium=&hfBBL=&hfNewZones=&hfPull=&hfC=&hfSea={day.year}%7C&hfSit=&player_type=batter&hfOuts=&opponent="
                   f"&pitcher_throws=&batter_stands=&hfSA=&game_date_gt={ds}&game_date_lt={ds}&hfInfield=&team=&position=&hfOutfield=&hfRO="
                   "&home_road=&hfFlag=&hfBBT=&metric_1=&hfInn=&min_pitches=0&min_results=0&group_by=name&sort_col=pitches"
                   "&player_event_sort=api_p_release_speed&sort_order=desc&min_pas=0&type=details&")
            for attempt in range(3):
                try:
                    r = requests.get(url, headers=UA, timeout=180); r.raise_for_status(); break
                except Exception as e:                    # noqa: BLE001
                    log(f"    retry {ds}: {type(e).__name__}"); time.sleep(5)
            else:
                continue
            d = pd.read_csv(io.StringIO(r.text), low_memory=False) if r.text.strip() else pd.DataFrame()
            if len(d):
                d.to_csv(f, index=False, compression="gzip")
        if len(d):
            out.append(d)
    log(f"  savant search: {sum(len(x) for x in out):,} pitches over {len(out)} days")
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS)


def load_statcast(end: str) -> pd.DataFrame:
    socket.setdefaulttimeout(120)
    if GAME_TYPES != {"R"}:                              # spring / postseason: straight from Savant, day by day
        d = savant_search_days(SEASON_START, end, GAME_TYPES)
        d = d[[c for c in COLS if c in d.columns]]
        d = d[(d["game_date"].astype(str) <= end) & (d["game_type"].isin(GAME_TYPES))]
        log(f"  {len(d):,} pitches, {d.game_date.min() if len(d) else '-'} .. {d.game_date.max() if len(d) else '-'}")
        return d
    pb.cache.enable()
    edges = [pd.Timestamp(SEASON_START)] + pd.date_range(SEASON_START, end, freq="MS").tolist() + [pd.Timestamp(end)]
    edges = sorted(set(edges))
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        b2 = b - pd.Timedelta(days=1) if b != edges[-1] else b
        if b2 < a:
            continue
        log(f"  statcast {a.date()} .. {b2.date()}")
        try:
            d = pb.statcast(start_dt=str(a.date()), end_dt=str(b2.date()), verbose=False)
            chunks = [d] if d is not None and len(d) else []
        except Exception as e:                          # one bad day-file from Savant: fetch the month day by day
            log(f"    month failed ({type(e).__name__}); retrying day by day")
            chunks = []
            for day in pd.date_range(a, b2):
                try:
                    x = pb.statcast(start_dt=str(day.date()), end_dt=str(day.date()), verbose=False)
                    if x is not None and len(x):
                        chunks.append(x)
                except Exception as e2:
                    log(f"    skipping {day.date()}: {type(e2).__name__}")
        for d in chunks:
            out.append(d[[c for c in COLS if c in d.columns]])
    d = pd.concat(out, ignore_index=True)
    # The last few days come straight from Savant, uncached. pybaseball caches every day it fetches for a year, empty
    # or not, so a day asked for before Savant posted it stayed empty for good: the cloud's first run (25 Sep 2026, 6:32
    # am) cached 24 Sep before its games were up, and the site sat at the 23rd. Re-reading the last FRESH_DAYS every run
    # also picks up Savant's overnight corrections to them.
    lo = str((pd.Timestamp(end) - pd.Timedelta(days=FRESH_DAYS - 1)).date())
    new = savant_search_days(max(lo, SEASON_START), end, GAME_TYPES, fresh=True)
    if len(new):
        new = new[[c for c in COLS if c in new.columns]]
        if pd.api.types.is_datetime64_any_dtype(d["game_date"]):
            new["game_date"] = pd.to_datetime(new["game_date"])
        got = set(new["game_date"].astype(str).str[:10])           # only days Savant sent replace the cached ones:
        d = pd.concat([d[~d["game_date"].astype(str).str[:10].isin(got)], new], ignore_index=True)   # a failed fetch keeps its copy
    d = d[(d["game_date"].astype(str) <= end) & (d["game_type"].isin(GAME_TYPES))]   # regular season by default
    log(f"  {len(d):,} pitches, {d.game_date.min()} .. {d.game_date.max()}")
    return d


# ============================================================================================
# Stuff: a pitch graded on its physical traits alone (Sean, 26 Sep 2026) — velocity, spin rate and axis, induced vertical
# and horizontal break, release height and side, extension, arm angle, the batter's side, and each pitch against his
# primary fastball (velocity and break differences). No location, no count: what the ball does, not where it went.
# Two models, trained at every build on this season and the one before (no model file to ship or pickle):
#   * whiff — the chance a swing at this pitch misses (every non-bunt swing);
#   * batted-ball type — ground ball, popup or air ball (line drives and flies together, as uERA treats them) on contact.
# The two combine the way uERA does, so a whiff is worth what it is to uERA: a Whiff% point is 0.933 of a K% point
# (UK in app.js), each strikeout takes a ball in play off the board; a ball in play is worth the league's wOBA for
# its type, the air balls at the league's line-drive share. Both put on the ERA scale -> Stuff ERA, and
# Stuff+ = 100 + the % of runs it saves against the league (higher is better; Whiff+ and Batted-ball+ are its two parts).
# ============================================================================================
STUFF = None        # {"lg": league means, "p": per-pitcher sums, "t": per pitcher-and-pitch-type sums} for the dataset being built
STUFF_PT = {"FF": 0, "SI": 1, "FC": 2, "SL": 3, "ST": 4, "SV": 5, "CU": 6, "KC": 7, "CS": 6, "CH": 8, "FS": 9, "FO": 9, "SC": 8,
            "KN": 10, "EP": 11, "FA": 0}
STUFF_COLS = ["release_spin_rate", "spin_axis", "pfx_x", "pfx_z", "release_pos_x", "release_pos_z", "arm_angle"]
STUFF_BB = {"ground_ball": 0, "popup": 1, "line_drive": 2, "fly_ball": 2}
STUFF_BUNT = {"foul_bunt", "missed_bunt", "bunt_foul_tip"}
# a pitcher's ctx.arsenal rows, one per pitch type (x = the model's chance; the plain ones are what happened)
STUFF_ARSENAL = ["pt", "n", "velo", "ivb", "hb", "spin", "xwhf", "xgb", "xpu", "whfp", "bbp", "stuffp", "whf", "gb", "pu", "sw", "bip",
                 "xstr", "strp", "strk"]


def stuff_features(d: pd.DataFrame) -> pd.DataFrame:
    """One row of model inputs per pitch (NaN where Statcast has no tracking); lefties mirrored so both hands read alike."""
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype(float) if c in d else pd.Series(np.nan, index=d.index)
    L = d["p_throws"].eq("L").to_numpy()
    velo, spin, axis = num("release_speed"), num("release_spin_rate"), num("spin_axis")
    ivb, hb = 12 * num("pfx_z"), 12 * num("pfx_x") * np.where(L, 1, -1)            # inches; arm-side run positive
    f = pd.DataFrame({"pt": d["pitch_type"].map(STUFF_PT).astype(float), "velo": velo, "spin": spin}, index=d.index)
    ax = np.radians(np.where(L, 360 - axis, axis))
    f["ax_s"], f["ax_c"], f["ivb"], f["hb"] = np.sin(ax), np.cos(ax), ivb, hb
    f["relx"], f["relz"] = num("release_pos_x") * np.where(L, 1, -1), num("release_pos_z")
    f["ext"], f["arm"] = num("release_extension"), num("arm_angle")
    f["same"] = (d["stand"] == d["p_throws"]).astype(float)
    # against his primary fastball that season: his most-thrown four-seamer, sinker or cutter (per season, so a
    # training set spanning years compares each pitch with the fastball he had then)
    yr = pd.to_datetime(d["game_date"]).dt.year.to_numpy()
    fb = d["pitch_type"].isin(["FF", "SI", "FC"]) & f.velo.notna() & f.ivb.notna()
    x = pd.DataFrame({"pitcher": d["pitcher"], "yr": yr, "pt": d["pitch_type"], "velo": f.velo, "ivb": f.ivb, "hb": f.hb})[fb]
    top = x.groupby(["pitcher", "yr", "pt"]).size().reset_index(name="n").sort_values("n").groupby(["pitcher", "yr"]).tail(1)
    ref = (x.merge(top[["pitcher", "yr", "pt"]], on=["pitcher", "yr", "pt"]).groupby(["pitcher", "yr"])[["velo", "ivb", "hb"]].mean()
           .reindex(pd.MultiIndex.from_arrays([d["pitcher"].to_numpy(), yr])))
    f["dvelo"], f["divb"], f["dhb"] = f.velo.to_numpy() - ref.velo.to_numpy(), f.ivb.to_numpy() - ref.ivb.to_numpy(), f.hb.to_numpy() - ref.hb.to_numpy()
    f.loc[f.pt.isna() | f.velo.isna() | f.ivb.isna()] = np.nan                        # untracked or unclassed: no grade
    return f


def load_prior_season(year: int) -> pd.DataFrame:
    """The season before, regular season only, for the Stuff models' training (pybaseball's cache makes it cheap after
    the first time). Empty if it can't be had — the models then train on this season alone."""
    try:
        pb.cache.enable()
        out = []
        for a in pd.date_range(f"{year}-03-01", f"{year}-10-31", freq="MS"):
            b = a + pd.offsets.MonthEnd(0)
            try:
                x = pb.statcast(start_dt=str(a.date()), end_dt=str(b.date()), verbose=False)
            except Exception as e:                          # noqa: BLE001 — a bad month costs that month
                log(f"    stuff: {year} {a:%b} skipped ({type(e).__name__})"); continue
            if x is not None and len(x):
                out.append(x[[c for c in COLS if c in x.columns]])
        d = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS)
        return d[d["game_type"].eq("R")] if len(d) else d
    except Exception as e:                                  # noqa: BLE001
        log(f"    stuff: no {year} data ({type(e).__name__})")
        return pd.DataFrame(columns=COLS)


def add_stuff(d: pd.DataFrame, prior: pd.DataFrame | None = None) -> pd.DataFrame:
    """Score every pitch: st_w (chance a swing misses), st_g / st_p (chance contact is a grounder / popup), st_n (1 if
    graded). Sets STUFF for the pitcher rows and league constants. A failure here costs the Stuff grades, never the build."""
    global STUFF
    STUFF = None
    for c in ["st_n", "st_w", "st_g", "st_p", "st_s"]:
        d[c] = 0.0
    try:
        return _add_stuff(d, prior)
    except Exception as e:                                  # noqa: BLE001
        STUFF = None
        for c in ["st_n", "st_w", "st_g", "st_p", "st_s"]:
            d[c] = 0.0
        log(f"  !! stuff skipped: {type(e).__name__}: {e}")
        return d


def _add_stuff(d: pd.DataFrame, prior: pd.DataFrame | None) -> pd.DataFrame:
    from sklearn.ensemble import HistGradientBoostingClassifier
    global STUFF
    if not all(c in d.columns for c in ["pfx_x", "pfx_z", "release_spin_rate"]):
        log("  stuff: no pitch-tracking columns in this data"); return d
    t0 = time.time()
    train = pd.concat([prior, d[[c for c in COLS if c in d.columns]]], ignore_index=True) if prior is not None and len(prior) else d
    ftr = stuff_features(train)
    ok = ftr.velo.notna().to_numpy()
    desc = train["description"].to_numpy()
    sw = ok & np.isin(desc, list(SWING)) & ~np.isin(desc, list(STUFF_BUNT))
    bb = train["bb_type"].map(STUFF_BB)
    bip = ok & train["type"].eq("X").to_numpy() & bb.notna().to_numpy() & ~train["events"].fillna("").str.contains("bunt").to_numpy()
    if sw.sum() < 5000 or bip.sum() < 2000:
        log(f"  stuff: too few tracked pitches ({sw.sum()} swings)"); return d
    kw = dict(max_iter=400, learning_rate=0.06, max_leaf_nodes=63, min_samples_leaf=200, l2_regularization=1.0,
              categorical_features=[0], early_stopping=True, validation_fraction=0.1, random_state=0)
    wm = HistGradientBoostingClassifier(**kw).fit(ftr.to_numpy()[sw], np.isin(desc[sw], list(WHIFF)))
    # strike: any strike — called, swinging, foul, in play — on every non-bunt pitch (pitchouts and intentional balls out)
    pitched = ok & ~np.isin(desc, list(STUFF_BUNT)) & ~np.isin(desc, ["pitchout", "intent_ball"])
    sm = HistGradientBoostingClassifier(**kw).fit(ftr.to_numpy()[pitched], train["type"].isin(["S", "X"]).to_numpy()[pitched])
    bm = HistGradientBoostingClassifier(**kw).fit(ftr.to_numpy()[bip], bb.to_numpy()[bip].astype(int))
    f = stuff_features(d)
    has = f.velo.notna().to_numpy()
    X = f.to_numpy()[has]
    pw = wm.predict_proba(X)[:, 1]; pbt = bm.predict_proba(X); ps = sm.predict_proba(X)[:, 1]
    d.loc[has, "st_n"] = 1.0; d.loc[has, "st_w"] = pw; d.loc[has, "st_g"] = pbt[:, 0]; d.loc[has, "st_p"] = pbt[:, 1]; d.loc[has, "st_s"] = ps
    # the air balls' line-drive share and his pitch traits, for the per-pitch table
    air = d["bb_type"].isin(["line_drive", "fly_ball"])
    g = d[has].assign(velo=f.velo[has], ivb=f.ivb[has], hb=f.hb[has], spin=f.spin[has], wh=d["description"][has].isin(WHIFF),
                      swg=d["description"][has].isin(SWING), gbx=d["bb_type"][has].eq("ground_ball"), pux=d["bb_type"][has].eq("popup"),
                      stx=d["type"][has].isin(["S", "X"]),
                      bipx=d["bb_type"][has].isin(STUFF_BB.keys()))
    agg = dict(n=("st_n", "sum"), w=("st_w", "sum"), g=("st_g", "sum"), p=("st_p", "sum"), s=("st_s", "sum"))
    STUFF = {"lg": {"w": float(pw.mean()), "g": float(pbt[:, 0].mean()), "p": float(pbt[:, 1].mean()), "s": float(ps.mean()),
                    "la": float(d["bb_type"].eq("line_drive").sum() / max(1, air.sum()))},
             "pt": g.groupby("pitch_type").agg(**agg),               # the league by pitch type: each pitch is also graded against its own kind
             "p": g.groupby("pitcher").agg(**agg),
             "t": g.groupby(["pitcher", "pitch_type"]).agg(**agg, velo=("velo", "mean"), ivb=("ivb", "mean"), hb=("hb", "mean"),
                                                             spin=("spin", "mean"), sw=("swg", "sum"), wh=("wh", "sum"),
                                                             bip=("bipx", "sum"), gb=("gbx", "sum"), pu=("pux", "sum"), stk=("stx", "sum"))}
    log(f"  stuff: trained on {sw.sum():,} swings / {bip.sum():,} balls in play ({len(train):,} pitches), "
        f"graded {has.sum():,} ({time.time() - t0:.0f}s)")
    return d


def stuff_consts(pit: pd.DataFrame, bbw: dict, pa9: float) -> dict | None:
    """The league means and the two ERA weights (per Whiff% point, per 1.000 of ball-in-play value)."""
    if not STUFF:
        return None
    lg = STUFF["lg"]
    vair = lg["la"] * bbw["ld"] + (1 - lg["la"]) * bbw["fb"]
    lgb = lg["g"] * bbw["gb"] + lg["p"] * bbw["pu"] + (1 - lg["g"] - lg["p"]) * vair
    bip_share = float(pit.nBIP.sum() / max(1, pit.BF.sum()))
    # a Strike% point, the uERA way: +0.409 K% (UK in app.js) and the walks the league gives up less of per point of
    # strike rate (uBB% is the walk rate at his Strike% percentile) — slope fitted on this season's 300+ BF pitchers
    q = pit[(pit.BF >= 300) & pit.Strike_pct.notna() & pit.BB_pct.notna()]
    if len(q) < 30:
        q = pit[(pit.BF >= 100) & pit.Strike_pct.notna() & pit.BB_pct.notna()]
    slope = float(np.polyfit(q.Strike_pct, q.BB_pct, 1)[0]) if len(q) >= 10 else -0.75
    wbb = float(pit.wUBB.sum() / max(1, pit.nUBB.sum()))
    k_s = (0.00409 * lgb - slope * 0.01 * (wbb - lgb)) / WOBA_SCALE * pa9
    out = {"lgW": round(100 * lg["w"], 3), "lgB": round(lgb, 4), "vair": round(vair, 4), "gb": bbw["gb"], "pu": bbw["pu"],
           "kW": round(0.00933 * lgb / WOBA_SCALE * pa9, 4), "kB": round(bip_share / WOBA_SCALE * pa9, 3),
           "lgS": round(100 * lg["s"], 3), "kS": round(k_s, 4), "bbSlope": round(slope, 3)}
    # each pitch type's league-average grades, so a pitch can be graded against its own kind (a four-seamer vs four-seamers)
    out["types"] = {pt: [int(x.n), round(100 * x.w / x.n, 3), round(x.g / x.n, 4), round(x.p / x.n, 4), round(100 * x.s / x.n, 3)]
                    for pt, x in STUFF["pt"].iterrows() if x.n >= 500}
    return out


def stuff_grade(n, w, g, p, s, sc: dict, lg_era: float):
    """Whiff+, Batted-ball+, Strike+ and Stuff+ (= the three together) from summed per-pitch predictions."""
    if not sc or not n:
        return None, None, None, None
    xw, xs = 100 * w / n, 100 * s / n
    xb = (g * sc["gb"] + p * sc["pu"] + (n - g - p) * sc["vair"]) / n
    wp = 100 + 100 * sc["kW"] * (xw - sc["lgW"]) / lg_era
    bp = 100 - 100 * sc["kB"] * (xb - sc["lgB"]) / lg_era
    sp = 100 + 100 * sc.get("kS", 0) * (xs - sc.get("lgS", xs)) / lg_era
    return round(wp, 1), round(bp, 1), round(sp, 1), round(wp + bp + sp - 200, 1)


def pitch_flags(d: pd.DataFrame) -> pd.DataFrame:
    global STUFF
    STUFF = None                                    # add_stuff() sets it again for a dataset that gets Stuff grades
    d = d.copy()
    z = pd.to_numeric(d["zone"], errors="coerce")
    d["in_zone"], d["out_zone"] = z.le(9), z.ge(11)
    d["swing"] = d["description"].isin(SWING)
    d["whiff"] = d["description"].isin(WHIFF)
    d["contact"] = d["swing"] & ~d["whiff"]
    d["z_swing"], d["o_swing"] = d["in_zone"] & d["swing"], d["out_zone"] & d["swing"]
    d["z_contact"], d["o_contact"] = d["in_zone"] & d["contact"], d["out_zone"] & d["contact"]
    d["strike"] = d["type"].isin(["S", "X"])
    bbe = (d["type"] == "X") & d["launch_speed"].notna() & d["launch_angle"].notna()
    d["bbe"] = bbe
    d["bip"] = d["type"] == "X"
    d["barrel"] = bbe & d["launch_speed_angle"].eq(6)
    d["gb"] = d["bip"] & d["bb_type"].eq("ground_ball")
    spray = np.degrees(np.arctan2(d["hc_x"] - 125.42, 198.27 - d["hc_y"]))
    pull_angle = np.where(d["stand"].eq("R"), -spray, spray)
    # batted-ball type and direction come from the stringer (every ball in play with a type), so they exist even
    # where nothing is tracked; exit-velocity flags stay on tracked BBE
    bbt = d["bip"] & d["bb_type"].notna() & d["bb_type"].ne("")
    d["bbt"] = bbt
    d["airall"] = bbt & d["bb_type"].isin(AIR_TYPES)          # fly ball, line drive or popup (Savant's "air")
    d["pullair"] = d["airall"] & (pull_angle > PULL_LINE)
    d["air"] = bbt & d["bb_type"].isin(["fly_ball", "line_drive"])   # Air% on the card excludes popups
    d["pull"] = bbt & (pull_angle > PULL_LINE)
    d["oppo"] = bbt & (pull_angle < -PULL_LINE)                # the other way: spray angle beyond the line to the opposite field
    d["ld"] = bbt & d["bb_type"].eq("line_drive")
    d["gbh"] = bbt & d["bb_type"].eq("ground_ball")
    d["puh"] = bbt & d["bb_type"].eq("popup")
    d["fbh"] = bbt & d["bb_type"].eq("fly_ball")
    # Mix wOBA (Sean, 26 Sep 2026): each typed ball in play (bunts out) worth the dataset's average wOBA for its bucket — ground
    # ball, popup, and line drives and fly balls each split pulled / straightaway / the other way — so a hitter's mix is
    # priced by what the league does on it, not by how hard he hit it. Direction matters most in the air, which is the
    # whole point: a pulled fly ball is worth far more than one the other way. No direction on a ball → its type's value.
    dirn = np.where(pull_angle > PULL_LINE, "p", np.where(pull_angle < -PULL_LINE, "o", np.where(np.isnan(pull_angle), "x", "c")))
    bt = d["bb_type"].fillna("")
    kind = np.select([bt.eq("ground_ball"), bt.eq("popup"), bt.eq("line_drive"), bt.eq("fly_ball")], ["gb", "pu", "ld", "fb"], "")
    # Ground balls stay one bucket (Sean, 26 Sep 2026): split by direction they moved Mix wOBA very little (r 0.976 with
    # the lumped version, no better against wOBAcon) and mostly measured the side he bats from — an oppo grounder is .427
    # for a lefty, .283 for a righty — and his speed, not his batted-ball mix
    d["mixb"] = np.where(np.isin(kind, ["ld", "fb"]), np.char.add(np.char.add(kind.astype(str), "_"), dirn.astype(str)), kind)
    ev_ = d["events"].fillna("")
    bunt_ = d["des"].astype(str).str.contains("bunt", case=False) | ev_.str.contains("bunt")
    fin = d["bbt"] & ev_.ne("") & ~ev_.isin(EXCLUDE) & d["mixb"].ne("") & ~bunt_   # the PA-ending ball in play, no bunts
    wv = pd.to_numeric(d["woba_value"], errors="coerce").fillna(0.0).where(~ev_.isin(ZERO_NUM), 0.0)
    val = wv[fin].groupby(d["mixb"][fin]).mean()
    for t in ("ld", "fb"):                                        # an air ball with no direction: its type's average
        typ = fin & pd.Series(kind == t, index=d.index)
        if typ.any():
            val[f"{t}_x"] = float(wv[typ].mean())
    per = float(wv[fin].mean()) if fin.any() else 0.0
    pa_ = ev_.ne("") & ~ev_.isin(EXCLUDE)
    wden_ = pd.to_numeric(d["woba_denom"], errors="coerce").fillna(0.0).where(~ev_.isin(ZERO_NUM), 1.0).where(pa_, 0.0)
    wnum_ = pd.to_numeric(d["woba_value"], errors="coerce").fillna(0.0).where(~ev_.isin(ZERO_NUM), 0.0).where(pa_, 0.0)
    den = float(wden_.sum())
    global MIX
    MIX = {"lg": round(per, 4), "f": round(float(fin.sum()) / den, 4) if den else 0.0,
           "w": round(float(wnum_.sum()) / den, 4) if den else 0.0,
           "v": {k: round(float(v), 4) for k, v in val.items()}}
    d["mixn"] = fin.astype(int)
    xs = d["mixb"].str.endswith("_x")
    for col, b in MIX_COLS.items():                               # each bucket's balls, for the Mix tab's shares
        hit = xs if b == "x" else d["mixb"].eq(b)
        d[col] = (fin & hit).astype(int)
    d["mixv"] = d["mixb"].map(MIX["v"]).where(fin, 0.0).fillna(0.0)
    if (fin & xs).any():                                          # the no-direction row: what those balls are priced at
        MIX["v"]["x"] = round(float(d["mixv"][fin & xs].mean()), 4)
    bunt = d["des"].astype(str).str.contains("bunt", case=False) | d["events"].astype(str).str.contains("bunt")
    d["bunt"] = bunt
    d["evb"] = bbe & ~bunt                                  # EV-eligible: tracked and not a bunt (Savant's Avg EV skips bunts)
    d["ev"] = d["launch_speed"].where(d["evb"], 0.0)
    d["hand"] = d["p_throws"].eq("R").astype(int)          # hitter split: pitcher hand
    d["bhand"] = d["stand"].eq("R").astype(int)            # pitcher split: batter side
    d["bhome"] = d["inning_topbot"].eq("Bot").astype(int)  # batter is the home team
    d["phome"] = 1 - d["bhome"]
    d["cs"] = d["description"].eq("called_strike")
    d["fbt"] = d["bip"] & d["bb_type"].eq("fly_ball")
    d["pu"] = d["bip"] & d["bb_type"].eq("popup")
    rs = pd.to_numeric(d["release_speed"], errors="coerce").astype("float64")
    d["fbn"] = d["pitch_type"].isin(FASTBALLS) & rs.notna()
    d["fbv"] = rs.where(d["fbn"], 0.0).fillna(0.0)
    ext = pd.to_numeric(d["release_extension"], errors="coerce").astype("float64")
    d["extn"] = ext.notna()
    d["exts"] = ext.fillna(0.0)
    d["hardhit"] = bbe & d["launch_speed"].ge(95)
    la = d["launch_angle"]
    d["sweetspot"] = np.where(bbe & la.between(9, 31), 1.0, np.where(bbe & (la.eq(8) | la.eq(32)), 0.5, 0.0))   # 8–32° on the unrounded angle: the rounded edges count half
    # competitive swings: Savant averages bat speed over roughly the hardest 90% of a hitter's swings
    bs = pd.to_numeric(d["bat_speed"], errors="coerce").astype("float64").where(d["swing"])
    thr = bs.groupby(d["batter"]).transform(lambda x: x.quantile(0.10)).astype("float64")
    d["comp"] = bs.notna() & thr.notna() & (bs.fillna(-1) >= thr.fillna(1e9))
    d["bs"] = bs.where(d["comp"], 0.0).fillna(0.0)
    return d


def pa_outcomes(d: pd.DataFrame, key: str) -> pd.DataFrame:
    """True PA count + wOBA/OPS/K%/BB% from PA-ending rows, with corrected wOBA bookkeeping."""
    p = d[d["events"].notna() & (d["events"] != "")].copy()
    num = pd.to_numeric(p["woba_value"], errors="coerce").fillna(0.0)
    den = pd.to_numeric(p["woba_denom"], errors="coerce").fillna(0.0)
    ev = p["events"]
    num = num.where(~ev.isin(ZERO_NUM), 0.0); den = den.where(~ev.isin(ZERO_NUM), 1.0)
    num = num.where(~ev.isin(EXCLUDE), 0.0);  den = den.where(~ev.isin(EXCLUDE), 0.0)
    p["wnum"], p["wden"] = num, den
    p["is_bb"] = ev.isin(["walk", "intent_walk"])
    p["is_k"] = ev.isin(["strikeout", "strikeout_double_play"])
    p["is_hbp"] = ev.eq("hit_by_pitch")
    p["is_sf"] = ev.isin(["sac_fly", "sac_fly_double_play"])
    p["tb"] = ev.map(HITS).fillna(0.0)
    p["is_hit"] = ev.isin(HITS)
    p["pa"] = ~ev.isin(["truncated_pa", "catcher_interf"]) | ev.eq("catcher_interf")
    g = p.groupby(key)
    o = g.agg(PA=("pa", "sum"), wnum=("wnum", "sum"), wden=("wden", "sum"),
              BB=("is_bb", "sum"), K=("is_k", "sum"), HBP=("is_hbp", "sum"),
              SF=("is_sf", "sum"), TB=("tb", "sum"), H=("is_hit", "sum"))
    o["wOBA"] = o.wnum / o.wden.replace(0, np.nan)
    AB = o.PA - o.BB - o.HBP - o.SF
    o["OBP"] = (o.H + o.BB + o.HBP) / o.PA.replace(0, np.nan)
    o["SLG"] = o.TB / AB.replace(0, np.nan)
    o["OPS"] = o.OBP + o.SLG
    o["K_pct"] = 100 * o.K / o.PA.replace(0, np.nan)
    o["BB_pct"] = 100 * o.BB / o.PA.replace(0, np.nan)
    return o


def hitter_metrics(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby("batter")
    f = g.agg(Pitches=("swing", "size"), Swings=("swing", "sum"), Whiffs=("whiff", "sum"),
              ZonePit=("in_zone", "sum"), OutPit=("out_zone", "sum"),
              ZSw=("z_swing", "sum"), OSw=("o_swing", "sum"),
              ZCon=("z_contact", "sum"), OCon=("o_contact", "sum"),
              BBE=("bbe", "sum"), BBT=("bbt", "sum"), BIP=("bip", "sum"), EVn=("evb", "sum"), Barrels=("barrel", "sum"))
    bb = d[d["evb"]].groupby("batter")["launch_speed"]
    f["avg_EV"] = bb.mean()
    f["EV90"] = bb.quantile(0.9)
    f["maxEV"] = bb.max()
    f["HH"] = g["hardhit"].sum(); f["SS"] = g["sweetspot"].sum(); f["Strikes"] = g["strike"].sum()
    f["BSn"] = g["comp"].sum(); f["BSsum"] = g["bs"].sum()
    for col in MIX_COLS:
        f[col] = g[col].sum() if col in d.columns else 0
    f["MixSum"] = g["mixv"].sum() if "mixv" in d.columns else 0.0; f["MixN"] = g["mixn"].sum() if "mixn" in d.columns else 0
    f["Pulln"] = g["pull"].sum(); f["LDn"] = g["ld"].sum(); f["GBh"] = g["gbh"].sum(); f["PUh"] = g["puh"].sum(); f["Oppn"] = g["oppo"].sum()
    r = pd.DataFrame(index=f.index)
    r["avg_EV"] = f.avg_EV
    r["EV90"] = f.EV90
    r["maxEV"] = f.maxEV
    r["HardHit_pct"] = 100 * f.HH / f.BIP.replace(0, np.nan)       # per ball in play, like Savant's leaderboard
    r["SweetSpot_pct"] = 100 * f.SS / f.BIP.replace(0, np.nan)
    r["Strike_pct"] = 100 * f.Strikes / f.Pitches.replace(0, np.nan)
    r["Swing_pct"] = 100 * f.Swings / f.Pitches.replace(0, np.nan)
    r["BatSpeed"] = f.BSsum / f.BSn.replace(0, np.nan)
    r["Air_pct"] = 100 * g["air"].sum() / f.BBT.replace(0, np.nan)
    r["PullAir_own"] = 100 * g["pullair"].sum() / g["airall"].sum().replace(0, np.nan)   # our own Pull Air%, used where Savant's leaderboard has no line
    r["FB_pct"] = 100 * g["fbh"].sum() / f.BBT.replace(0, np.nan)
    r["Pull_pct"] = 100 * f.Pulln / f.BBT.replace(0, np.nan)
    r["Oppo_pct"] = 100 * f.Oppn / f.BBT.replace(0, np.nan)
    r["Cent_pct"] = 100 - r["Pull_pct"] - r["Oppo_pct"]
    r["NonPull_pct"] = 100 - r["Pull_pct"]
    r["LD_pct"] = 100 * f.LDn / f.BBT.replace(0, np.nan)
    r["GB_pct"] = 100 * f.GBh / f.BBT.replace(0, np.nan)
    r["PU_pct"] = 100 * f.PUh / f.BBT.replace(0, np.nan)
    r["Barrel_pct"] = 100 * f.Barrels / f.BIP.replace(0, np.nan)
    r["ZSwing_pct"] = 100 * f.ZSw / f.ZonePit.replace(0, np.nan)
    r["OSwing_pct"] = 100 * f.OSw / f.OutPit.replace(0, np.nan)
    r["ZContact_pct"] = 100 * f.ZCon / f.ZSw.replace(0, np.nan)
    r["OContact_pct"] = 100 * f.OCon / f.OSw.replace(0, np.nan)
    r["Whiff_pct"] = 100 * f.Whiffs / f.Swings.replace(0, np.nan)
    r["MixSum"], r["MixN"] = f.MixSum, f.MixN
    for col in MIX_COLS:
        r[col] = f[col]
    r["BBE"] = f.BIP                                                 # batted-ball events as Savant counts them: every ball in play
    r["BBT"] = f.BBT
    r["bats"] = g["stand"].agg(lambda s: "S" if s.nunique() > 1 else s.iloc[0])
    o = pa_outcomes(d, "batter")
    o["AB"] = o.PA - o.BB - o.HBP - o.SF
    o["BA"] = o.H / o.AB.replace(0, np.nan)
    return r.join(o[["PA", "AB", "wOBA", "OPS", "BA", "SLG", "K_pct", "BB_pct"]], how="inner")


def pitcher_metrics(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby("pitcher")
    f = g.agg(Pitches=("swing", "size"), Swings=("swing", "sum"), Whiffs=("whiff", "sum"),
              Strikes=("strike", "sum"), BIP=("bip", "sum"), GB=("gb", "sum"),
              G=("game_pk", "nunique"), CS=("cs", "sum"), ZonePit=("in_zone", "sum"), OutPit=("out_zone", "sum"),
              ZSw=("z_swing", "sum"), OSw=("o_swing", "sum"), ZCon=("z_contact", "sum"), FBt=("fbt", "sum"),
              PU=("pu", "sum"), BBE=("bbe", "sum"), EVn=("evb", "sum"), Barrels=("barrel", "sum"), HH=("hardhit", "sum"),
              EVsum=("ev", "sum"), FBn=("fbn", "sum"), FBv=("fbv", "sum"), Extn=("extn", "sum"), Exts=("exts", "sum"))
    # starter = pitcher on the first plate appearance of a half-inning 1 for his team
    first = d.sort_values("at_bat_number").groupby(["game_pk", "inning_topbot"]).head(1)
    f["GS"] = first.groupby("pitcher")["game_pk"].nunique()
    f["GS"] = f["GS"].fillna(0).astype(int)
    r = pd.DataFrame(index=f.index)
    r["Whiff_pct"] = 100 * f.Whiffs / f.Swings.replace(0, np.nan)
    r["SwStr_pct"] = 100 * f.Whiffs / f.Pitches.replace(0, np.nan)
    r["Strike_pct"] = 100 * f.Strikes / f.Pitches.replace(0, np.nan)
    r["GB_pct"] = 100 * f.GB / f.BIP.replace(0, np.nan)
    r["PU_pct"] = 100 * f.PU / f.BIP.replace(0, np.nan)             # popups per ball in play
    r["CSW_pct"] = 100 * (f.CS + f.Whiffs) / f.Pitches.replace(0, np.nan)
    r["Zone_pct"] = 100 * f.ZonePit / f.Pitches.replace(0, np.nan)
    r["OSwing_pct"] = 100 * f.OSw / f.OutPit.replace(0, np.nan)
    r["Swing_pct"] = 100 * f.Swings / f.Pitches.replace(0, np.nan)
    r["ZContact_pct"] = 100 * f.ZCon / f.ZSw.replace(0, np.nan)
    r["FBvelo"] = f.FBv / f.FBn.replace(0, np.nan)
    r["Ext"] = f.Exts / f.Extn.replace(0, np.nan)
    r["avg_EV"] = f.EVsum / f.EVn.replace(0, np.nan)                 # bunts excluded, like Savant
    r["HardHit_pct"] = 100 * f.HH / f.BIP.replace(0, np.nan)         # per ball in play
    r["Barrel_pct"] = 100 * f.Barrels / f.BIP.replace(0, np.nan)
    r["GBn"], r["FBn_bb"], r["PUn"] = f.GB, f.FBt, f.PU
    r["Pitches"], r["G"], r["GS"] = f.Pitches, f.G, f.GS
    r["throws"] = g["p_throws"].agg(lambda s: s.mode().iloc[0])
    o = pa_outcomes(d, "pitcher")
    o = o.rename(columns={"PA": "BF"})
    pa = pa_rows(d)
    pr = pa.groupby("pitcher").agg(HR=("is_hr", "sum"), HBP=("is_hbp", "sum"), Kn=("is_k", "sum"),
                                   BBn=("is_bb", "sum"), outs=("outs", "sum"),
                                   wnum=("wnum", "sum"), wden=("wden", "sum"), nBIP=("t_bip", "sum"), wBIP=("w_bip", "sum"),
                                   nGB=("t_gb", "sum"), wGB=("w_gb", "sum"), nLD=("t_ld", "sum"), wLD=("w_ld", "sum"),
                                   nFB=("t_fb", "sum"), wFB=("w_fb", "sum"), nPU=("t_pu", "sum"), wPU=("w_pu", "sum"),
                                   nUBB=("t_ubb", "sum"), wUBB=("w_ubb", "sum"), wHBP=("w_hbp", "sum"))
    first = d.sort_values("at_bat_number").groupby(["game_pk", "inning_topbot"]).head(1)
    started = set(zip(first["pitcher"], first["game_pk"]))
    as_starter = pd.Series([(pt, gp) in started for pt, gp in zip(pa["pitcher"], pa["game_pk"])], index=pa.index)
    pr["outsS"] = pa[as_starter].groupby("pitcher")["outs"].sum()
    pr["outsR"] = pa[~as_starter].groupby("pitcher")["outs"].sum()
    pr = pr.fillna({"outsS": 0, "outsR": 0})
    return r.join(o[["BF", "wOBA", "K_pct", "BB_pct"]], how="inner").join(pr, how="left")


_SPRINT = None
def sprint_speeds() -> dict:
    global _SPRINT
    if _SPRINT is None:
        t = pb.statcast_sprint_speed(SEASON, min_opp=5)
        _SPRINT = dict(zip(t["player_id"].astype(int), pd.to_numeric(t["sprint_speed"], errors="coerce")))
        log(f"  sprint speed: {len(_SPRINT)} players")
    return _SPRINT


def dir_features(p: pd.DataFrame) -> pd.DataFrame:
    """What all three directional models read: Savant's inputs plus where the ball went."""
    spray = np.degrees(np.arctan2(p["hc_x"] - 125.42, 198.27 - p["hc_y"]))
    return pd.DataFrame({
        "launch_speed": p["launch_speed"].astype("float64"), "launch_angle": p["launch_angle"].astype("float64"),
        "sprint_speed": p["batter"].map(sprint_speeds()).astype("float64"),
        "pull_angle": np.where(p["stand"].eq("R"), -spray, spray), "spray_angle": spray,
        "stand_R": p["stand"].eq("R").astype(float),
    }, index=p.index)


def directional_bs(p: pd.DataFrame, tracked: pd.Series, bip: pd.Series) -> tuple:
    """Per-PA dxBA and dxSLG contributions, the directional answer to Savant's xBA and xSLG: the models'
    expected hit and total bases on a tracked ball in play, the real result on an untracked one, nothing
    for a strikeout (which is already an out in the AB denominator). Era-neutral predictions are rescaled
    to this season's own league rate on contact, the way dxwOBA is."""
    ab = p["ab"].astype(float)
    hit = np.where(bip, p["is_hit"].astype(float), 0.0)
    tbs = np.where(bip, p["tb"].astype(float), 0.0)
    sel = tracked & p["ab"]
    if not sel.any() or not BA_MODEL.exists():
        log("  directional xBA / xSLG: not scored")
        return pd.Series(hit, index=p.index), pd.Series(tbs, index=p.index)
    X = dir_features(p)[DIR_FEATS]
    out_b, out_s = hit.copy(), tbs.copy()
    for model_path, col, out in [(BA_MODEL, hit, out_b), (SLG_MODEL, tbs, out_s)]:
        mu = float(col[sel.values].mean())                 # league BA / SLG on contact this season
        out[sel.values] = joblib.load(model_path).predict(X[sel][DIR_FEATS]) * mu
    out_b = np.where(ab > 0, out_b, 0.0); out_s = np.where(ab > 0, out_s, 0.0)
    log(f"  directional xBA / xSLG: {int(sel.sum()):,} tracked balls scored")
    return pd.Series(out_b, index=p.index), pd.Series(out_s, index=p.index)


def directional_xwoba(p: pd.DataFrame, tracked: pd.Series, num: pd.Series, den: pd.Series) -> pd.Series:
    """Per-PA numerator: the directional model's expected value on tracked balls in play, the actual wOBA
    value otherwise (K, BB, HBP, untracked contact). Era-neutral predictions are rescaled to this season's
    league wOBA on contact."""
    model = joblib.load(DIR_MODEL)
    X = dir_features(p)
    sel = tracked & (den > 0)
    if not sel.any():                                     # nothing tracked (spring training parks): keep the real values
        log("  directional xwOBA: no tracked balls in play")
        return num.astype(float).copy()
    mu = float(num[sel].mean())                           # league wOBA on contact this season
    out = num.astype(float).copy()
    out[tracked] = model.predict(X[tracked][DIR_FEATS]) * mu
    log(f"  directional xwOBA: {int(tracked.sum()):,} tracked BBE scored, league wOBAcon {mu:.4f}")
    return out


def pa_rows(d: pd.DataFrame) -> pd.DataFrame:
    """PA-ending rows with corrected wOBA bookkeeping, AB flag, and outs recorded (from outs_when_up)."""
    p = d[d["events"].notna() & (d["events"] != "")].sort_values(["game_pk", "at_bat_number"]).copy()
    num = pd.to_numeric(p["woba_value"], errors="coerce").fillna(0.0)
    den = pd.to_numeric(p["woba_denom"], errors="coerce").fillna(0.0)
    ev = p["events"]
    num = num.where(~ev.isin(ZERO_NUM), 0.0); den = den.where(~ev.isin(ZERO_NUM), 1.0)
    num = num.where(~ev.isin(EXCLUDE), 0.0);  den = den.where(~ev.isin(EXCLUDE), 0.0)
    p["wnum"], p["wden"] = num, den
    p["is_bb"] = ev.isin(["walk", "intent_walk"])
    p["is_k"] = ev.isin(["strikeout", "strikeout_double_play"])
    p["is_hr"] = ev.eq("home_run")
    p["is_hbp"] = ev.eq("hit_by_pitch")
    p["is_hit"] = ev.isin(HITS)
    p["tb"] = ev.map(HITS).fillna(0.0)
    p["pa"] = ~ev.isin(["truncated_pa"])
    p["ab"] = ~ev.isin(NON_AB)
    # batted-ball type of the PA (the PA-ending pitch is the ball in play) and the wOBA numerator it produced
    bipx = p["type"].eq("X")
    bt = p["bb_type"].fillna("")
    for t, name in [("gb", "ground_ball"), ("ld", "line_drive"), ("fb", "fly_ball"), ("pu", "popup")]:
        p[f"t_{t}"] = bipx & bt.eq(name)
        p[f"w_{t}"] = p["wnum"].where(p[f"t_{t}"], 0.0)
    p["t_bip"] = bipx
    p["w_bip"] = p["wnum"].where(bipx, 0.0)
    p["t_ubb"] = ev.eq("walk")
    p["w_ubb"] = p["wnum"].where(p["t_ubb"], 0.0)
    p["w_hbp"] = p["wnum"].where(p["is_hbp"], 0.0)
    # xwOBA (matches Savant's leaderboard to ~.001): balls in play take their xwOBA, K/BB/HBP their actual
    # wOBA value, untracked balls in play are dropped from both sides, and an intentional walk counts as a
    # league-average PA in numerator and denominator
    x = pd.to_numeric(p["estimated_woba_using_speedangle"], errors="coerce")
    bip = p["type"].eq("X"); untracked = bip & x.isna(); ibb = ev.eq("intent_walk")
    xnum = np.where(bip, x.fillna(0.0), num)
    xden = np.where(untracked, 0.0, np.where(ibb, 1.0, den))
    xd_tot = float(np.sum(np.where(ibb, 0.0, xden)))
    lg = float(np.sum(np.where(ibb, 0.0, xnum)) / xd_tot) if xd_tot > 0 else 0.0
    p["xnum"] = np.where(ibb, lg, np.where(untracked, 0.0, xnum))
    p["xden"] = xden
    xb = pd.to_numeric(p.get("estimated_ba_using_speedangle"), errors="coerce") if "estimated_ba_using_speedangle" in p else pd.Series(np.nan, index=p.index)
    xs = pd.to_numeric(p.get("estimated_slg_using_speedangle"), errors="coerce") if "estimated_slg_using_speedangle" in p else pd.Series(np.nan, index=p.index)
    p["xbsum"] = np.where(bip, xb.fillna(p["is_hit"].astype(float)), 0.0)     # xBA = Σ per-ball xBA over AB (strikeouts add 0)
    p["xssum"] = np.where(bip, xs.fillna(p["tb"]), 0.0)                        # xSLG likewise
    p.attrs["league_xwoba"] = round(lg, 4)
    p["dnum"] = directional_xwoba(p, bip & ~untracked, num, den)
    p["dbsum"], p["dssum"] = directional_bs(p, bip & ~untracked, bip)
    # outs recorded in this PA = outs at the start of the next PA of the half-inning (3 if it was the last),
    # which also captures runner outs during the PA; a game-ending half-inning stops at the event's own outs
    half = ["game_pk", "inning", "inning_topbot"]
    nxt = p.groupby(half)["outs_when_up"].shift(-1)
    last_of_game = p.groupby("game_pk")["at_bat_number"].transform("max") == p.groupby(half)["at_bat_number"].transform("max")
    after = nxt.fillna(3.0)
    after = after.where(~(nxt.isna() & last_of_game), np.minimum(3.0, p["outs_when_up"] + ev.map(OUTS).fillna(0)))
    p["outs"] = (after - p["outs_when_up"]).clip(lower=0)
    return p


def daily(d: pd.DataFrame, days: dict) -> tuple:
    """Per player-day count rows for the page's date filter -> ({batter: [[...], ...]}, {pitcher: [[...], ...]})."""
    p = pa_rows(d)
    # hitters
    HK = ["batter", "game_date", "hand", "bhome"]
    g = d.groupby(HK)
    h = g.agg(pit=("swing", "size"), sw=("swing", "sum"), whf=("whiff", "sum"), zpit=("in_zone", "sum"),
              opit=("out_zone", "sum"), zsw=("z_swing", "sum"), osw=("o_swing", "sum"), zcon=("z_contact", "sum"),
              ocon=("o_contact", "sum"), brl=("barrel", "sum"),
              air=("air", "sum"), pullair=("pullair", "sum"), hh=("hardhit", "sum"), ss=("sweetspot", "sum"),
              strk=("strike", "sum"), bsn=("comp", "sum"), bssum=("bs", "sum"), bbe=("bbe", "sum"), evsum=("ev", "sum"),
              pulln=("pull", "sum"), ld=("ld", "sum"), gbh=("gbh", "sum"), puh=("puh", "sum"), bbt=("bbt", "sum"),
              bip=("bip", "sum"), evn=("evb", "sum"), oppn=("oppo", "sum"),
              mixsum=("mixv", "sum"), mixn=("mixn", "sum"), **{c: (c, "sum") for c in MIX_COLS})
    h["mixsum"] = h["mixsum"].round(4)
    h["evs"] = d[d["evb"]].groupby(HK)["launch_speed"].agg(lambda x: [round(float(v), 1) for v in x])
    hp = p.groupby(HK).agg(pa=("pa", "sum"), ab=("ab", "sum"), bb=("is_bb", "sum"),
                           k=("is_k", "sum"), wnum=("wnum", "sum"), wden=("wden", "sum"),
                           xnum=("xnum", "sum"), xden=("xden", "sum"), dnum=("dnum", "sum"),
                           h=("is_hit", "sum"), tb=("tb", "sum"), xbsum=("xbsum", "sum"), xssum=("xssum", "sum"),
                           dbsum=("dbsum", "sum"), dssum=("dssum", "sum"), hr=("is_hr", "sum"))
    h = h.join(hp, how="left")
    h["evs"] = h["evs"].apply(lambda v: v if isinstance(v, list) else [])
    h = h.fillna(0)
    # pitchers
    PK = ["pitcher", "game_date", "bhand", "phome"]
    g = d.groupby(PK)
    q = g.agg(pit=("swing", "size"), sw=("swing", "sum"), whf=("whiff", "sum"), strk=("strike", "sum"),
              bip=("bip", "sum"), gb=("gb", "sum"), cs=("cs", "sum"), zpit=("in_zone", "sum"), opit=("out_zone", "sum"),
              zsw=("z_swing", "sum"), osw=("o_swing", "sum"), zcon=("z_contact", "sum"), fbt=("fbt", "sum"), pu=("pu", "sum"),
              bbe=("bbe", "sum"), brl=("barrel", "sum"), hh=("hardhit", "sum"), evsum=("ev", "sum"),
              fbn=("fbn", "sum"), fbv=("fbv", "sum"), extn=("extn", "sum"), exts=("exts", "sum"), evn=("evb", "sum"),
              **{c: (s, "sum") for c, s in [("stn", "st_n"), ("stw", "st_w"), ("stg", "st_g"), ("stp", "st_p"), ("sts", "st_s")] if s in d.columns})
    first = d.sort_values("at_bat_number").groupby(["game_pk", "inning_topbot"]).head(1)
    starters = set(zip(first["pitcher"], first["game_date"]))
    qp = p.groupby(PK).agg(bf=("pa", "size"), k=("is_k", "sum"), bb=("is_bb", "sum"),
                           outs=("outs", "sum"), wnum=("wnum", "sum"), wden=("wden", "sum"),
                           hr=("is_hr", "sum"), hbp=("is_hbp", "sum"), h=("is_hit", "sum"),
                           ld=("t_ld", "sum"), wbip=("w_bip", "sum"), wgb=("w_gb", "sum"), wld=("w_ld", "sum"), wfb=("w_fb", "sum"), wpu=("w_pu", "sum"))
    q = q.join(qp, how="left").fillna(0)
    for c in ["stn", "stw", "stg", "stp", "sts"]:
        if c not in q.columns:
            q[c] = 0.0
    q["gs"] = [1 if (key[0], key[1]) in starters else 0 for key in q.index]

    def pack(frame, fields):
        out = {}
        for (pid, date, hand, home), r in frame.iterrows():
            row = [days[str(date)[:10]], int(hand), int(home)]
            for f in fields[3:]:
                v = r[f]
                if f == "evs":
                    row.append(v)
                else:
                    # xbsum / xssum are sums of per-ball probabilities: a day's bucket is well under 1, so int() would erase it
                    row.append(round(float(v), 2) if f in ("evsum", "wnum", "xnum", "dnum", "bssum", "fbv", "exts", "ss", "wbip", "wgb", "wld", "wfb", "wpu", "xbsum", "xssum", "dbsum", "dssum", "stw", "stg", "stp", "sts") else int(v))
            out.setdefault(int(pid), []).append(row)
        return out
    return pack(h, HITTER_DAY), pack(q, PITCHER_DAY)


# ============================================================================================
# 2. Savant batted-ball leaderboard (Air%, Pull Air%)
# ============================================================================================
def savant_batted_ball() -> pd.DataFrame:
    url = ("https://baseballsavant.mlb.com/leaderboard/batted-ball"
           f"?type=batter&year={SEASON}&min=1&csv=true")      # every hitter with a ball in play (the default 25 dropped call-ups)
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text.lstrip("﻿")))
    df = df.rename(columns={"id": "batter"}).set_index("batter")
    out = pd.DataFrame(index=df.index)
    out["Air_pct"] = 100 * df["air_rate"]
    out["PullAir_pct"] = 100 * df["pull_air_rate"]
    log(f"  savant batted-ball: {len(out)} hitters")
    return out


def savant_bat_speed() -> pd.Series:
    url = ("https://baseballsavant.mlb.com/leaderboard/bat-tracking?attackZone=&batSide=&contactType=&count=&dateStart="
           f"&dateEnd=&gameType=&isHardHit=&minSwings=1&minGroupSwings=1&pitchHand=&pitchType=&seasonStart={SEASON}"
           f"&seasonEnd={SEASON}&team=&type=batter&csv=true")
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text.lstrip("\ufeff"))).set_index("id")
    log(f"  savant bat speed: {len(df)} hitters")
    return pd.to_numeric(df["avg_bat_speed"], errors="coerce")


XSAV = None          # Savant expected BA / SLG for the season (filled by savant_xwoba)


def savant_xwoba() -> pd.Series:
    url = ("https://baseballsavant.mlb.com/leaderboard/expected_statistics"
           f"?type=batter&year={SEASON}&position=&team=&min=1&csv=true")
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text.lstrip("\ufeff"))).set_index("player_id")
    log(f"  savant xwOBA: {len(df)} hitters")
    global XSAV
    XSAV = df[["est_ba", "est_slg"]]
    return df["est_woba"]


# ============================================================================================
# 3. MLB Stats API (names, teams, positions)
# ============================================================================================
def innings_to_float(ip):
    """'146.2' (146 and 2/3 innings) -> 146.667"""
    if ip is None:
        return None
    whole, _, thirds = str(ip).partition(".")
    return int(whole) + int(thirds or 0) / 3


def mlb_people(ids, game_logs: bool = True) -> dict:
    ids = [int(i) for i in ids]
    teams = requests.get(f"https://statsapi.mlb.com/api/v1/teams?sportId=1&season={SEASON}",
                         headers=UA, timeout=60).json()["teams"]
    abbr = {t["id"]: t["abbreviation"] for t in teams}
    people = {}
    for i in range(0, len(ids), 80):
        chunk = ids[i:i + 80]
        url = ("https://statsapi.mlb.com/api/v1/people?personIds=" + ",".join(map(str, chunk)) +
               f"&hydrate=currentTeam,stats(group=[fielding,hitting,pitching],type=[{'season,gameLog' if game_logs else 'season'}],season={SEASON}{',gameType=' + API_GAME_TYPE if API_GAME_TYPE != 'R' else ''})")
        for attempt in range(3):
            try:
                js = requests.get(url, headers=UA, timeout=60).json()
                break
            except Exception as e:
                log("   retry", e); time.sleep(2)
        for p in js.get("people", []):
            pos_games, ab, ip, era, er, games, season_team = {}, None, None, None, None, [], None
            for s in p.get("stats", []):
                grp, typ = s["group"]["displayName"], s["type"]["displayName"]
                if typ == "season" and grp in ("hitting", "pitching"):
                    for x in s["splits"]:
                        if "team" in x:
                            season_team = abbr.get(x["team"].get("id"), season_team)   # last club that season
                if typ == "gameLog":
                    if grp == "pitching":
                        games = [(x["date"], 1 if x.get("isHome") else 0, int(x["stat"].get("earnedRuns", 0)))
                                 for x in s["splits"] if x.get("gameType", "R") == "R"]
                    continue
                if grp in ("hitting", "pitching"):
                    splits = s["splits"]
                    tot = [x for x in splits if "team" not in x] or splits[:1]   # season total, not a per-team split
                    if tot:
                        st = tot[0]["stat"]
                        if grp == "hitting":
                            ab = st.get("atBats")
                        else:
                            ip = innings_to_float(st.get("inningsPitched"))
                            era = float(st["era"]) if st.get("era") not in (None, "-.--") else None
                            er = st.get("earnedRuns")
                    continue
                for sp in s["splits"]:
                    code = sp.get("position", {}).get("abbreviation")
                    if code in ("LF", "CF", "RF"):
                        code = "OF"
                    if not code or code in ("P", "TWP"):
                        continue
                    pos_games[code] = pos_games.get(code, 0) + int(sp["stat"].get("games", 0))
            prim = p.get("primaryPosition", {}).get("abbreviation", "")
            if prim in ("LF", "CF", "RF"):
                prim = "OF"
            if prim in ("TWP", "P", ""):          # two-way players and pitchers rank as DH when hitting
                prim = "DH"
            people[p["id"]] = {
                "name": p.get("fullName"),
                "team": abbr.get(p.get("currentTeam", {}).get("id"), "FA"),
                "primary": prim,
                "pos": pos_games,
                "age": p.get("currentAge"),
                "ab": ab, "ip": ip, "era": era, "er": er, "games": games,
                "seasonTeam": season_team, "birth": p.get("birthDate"),
            }
        log(f"  mlb api: {min(i + 80, len(ids))}/{len(ids)}")
    return people


MILB_SPORTS = (11, 12, 13, 14, 16)          # AAA, AA, High-A, Single-A, Rookie
MILB_MAX_MLB_GAMES = 120                     # only look up the minors for hitters with fewer MLB games than this


def milb_positions(ids) -> dict:
    """Minor-league games by position this season, {id: {"OF": 95, "DH": 29}} — ESPN grants eligibility for
    positions a call-up played in the minors, so these add to the MLB games in the page's 20-game rule."""
    from concurrent.futures import ThreadPoolExecutor
    ids = [int(i) for i in ids]

    def one(pid):
        out = {}
        for sport in MILB_SPORTS:
            url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group=fielding&season={SEASON}&sportId={sport}"
            for attempt in range(3):
                try:
                    js = requests.get(url, headers=UA, timeout=30).json(); break
                except Exception:
                    time.sleep(1); js = {}
            for st in js.get("stats", []):
                for sp in st.get("splits", []):
                    code = sp.get("position", {}).get("abbreviation")
                    if code in ("LF", "CF", "RF"):
                        code = "OF"
                    if not code or code in ("P", "TWP"):
                        continue
                    out[code] = out.get(code, 0) + int(sp["stat"].get("games", 0))
        return pid, out

    res = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for n, (pid, out) in enumerate(ex.map(one, ids), 1):
            if out:
                res[pid] = out
            if n % 100 == 0:
                log(f"  minors: {n}/{len(ids)}")
    return res


# ============================================================================================
# 4. Percentiles, scores, JSON
# ============================================================================================
def metric_values(r, metrics):
    return {key: (None if pd.isna(r[col]) else round(float(r[col]), dec)) for key, _, col, _, dec, _ in metrics}


def build_hitters(hit: pd.DataFrame, sav: pd.DataFrame, people: dict, days_h: dict, xw: pd.Series, bsp: pd.Series) -> list:
    df = hit.join(sav.drop(columns=["Air_pct"], errors="ignore"), how="left")   # Air% is our no-popup version
    if "PullAir_pct" in df.columns:
        df["PullAir_pct"] = df["PullAir_pct"].fillna(df["PullAir_own"])
    else:
        df["PullAir_pct"] = df["PullAir_own"]
    df = df[df.PA >= MIN_PA_HITTER]
    rows = []
    for pid, r in df.iterrows():
        info = people.get(int(pid))
        if not info:
            continue
        m = metric_values(r, HITTER_METRICS)
        rows_d = days_h.get(int(pid), [])
        dn = sum(x[HITTER_DAY.index("dnum")] for x in rows_d); wd = sum(x[HITTER_DAY.index("wden")] for x in rows_d)
        xn = sum(x[HITTER_DAY.index("xnum")] for x in rows_d); xd = sum(x[HITTER_DAY.index("xden")] for x in rows_d)
        m["xwoba_dir"] = round(dn / wd, 3) if wd else None                  # directional model, kept for reference
        m["xwoba_sav"] = round(float(xw[pid]), 3) if pid in xw.index and pd.notna(xw[pid]) else None
        m["xwoba"] = m["xwoba_sav"] if m["xwoba_sav"] is not None else (round(xn / xd, 3) if xd else None)   # EV + launch angle
        m["woba"] = None if pd.isna(r.wOBA) else round(float(r.wOBA), 3)
        # Mix wOBA: the league's value of his average ball in play by bucket — balls in play only, no bunts (Sean)
        mn = float(r.get("MixN", 0) or 0)
        m["mixw"] = round(float(r.MixSum) / mn, 3) if MIX and mn else None
        ab_ = float(r.AB) if pd.notna(r.AB) else 0.0
        m["ba"] = None if pd.isna(r.BA) else round(float(r.BA), 3)
        m["slg"] = None if pd.isna(r.SLG) else round(float(r.SLG), 3)
        xbs = sum(x[HITTER_DAY.index("xbsum")] for x in rows_d if len(x) > HITTER_DAY.index("xbsum"))
        xss = sum(x[HITTER_DAY.index("xssum")] for x in rows_d if len(x) > HITTER_DAY.index("xssum"))
        sav_x = XSAV.loc[pid] if XSAV is not None and pid in XSAV.index else None
        m["xba"] = round(float(sav_x["est_ba"]), 3) if sav_x is not None and pd.notna(sav_x["est_ba"]) else (round(xbs / ab_, 3) if ab_ else None)
        m["xslg"] = round(float(sav_x["est_slg"]), 3) if sav_x is not None and pd.notna(sav_x["est_slg"]) else (round(xss / ab_, 3) if ab_ else None)
        dbs = sum(x[HITTER_DAY.index("dbsum")] for x in rows_d if len(x) > HITTER_DAY.index("dbsum"))
        dss = sum(x[HITTER_DAY.index("dssum")] for x in rows_d if len(x) > HITTER_DAY.index("dssum"))
        m["dxba"] = round(dbs / ab_, 3) if ab_ else None      # the directional models' answer to xBA / xSLG
        m["dxslg"] = round(dss / ab_, 3) if ab_ else None
        m["zmo"] = None if pd.isna(r["ZSwing_pct"]) or pd.isna(r["OSwing_pct"]) else round(float(r["ZSwing_pct"] - r["OSwing_pct"]), 1)
        m["k"], m["bb"] = (None if pd.isna(r.K_pct) else round(float(r.K_pct), 1)), (None if pd.isna(r.BB_pct) else round(float(r.BB_pct), 1))
        m["con"] = None if pd.isna(r["Whiff_pct"]) else round(100 - float(r["Whiff_pct"]), 1)
        for key, col in [("ev90", "EV90"), ("maxev", "maxEV"), ("hh", "HardHit_pct"), ("ss", "SweetSpot_pct"),
                         ("strk", "Strike_pct"), ("swing", "Swing_pct"), ("pullp", "Pull_pct"), ("oppo", "Oppo_pct"), ("cent", "Cent_pct"), ("npull", "NonPull_pct"), ("ld", "LD_pct"),
                         ("gb", "GB_pct"), ("pu", "PU_pct"), ("fb", "FB_pct")]:
            m[key] = None if pd.isna(r[col]) else round(float(r[col]), 1)
        own_bs = None if pd.isna(r["BatSpeed"]) else round(float(r["BatSpeed"]), 1)
        m["bs"] = round(float(bsp[pid]), 1) if pid in bsp.index and pd.notna(bsp[pid]) else own_bs
        rows.append({
            "id": int(pid), "name": info["name"], "team": info["team"], "type": "H",
            "primary": info["primary"] or "DH", "pos": info["pos"], "milb": info.get("milb", {}), "bats": r["bats"],
            "age": info["age"], "pa": int(r.PA), "ab": int(info["ab"] or 0),
            "m": m,
            "ctx": {"wOBA": m["woba"], "OPS": None if pd.isna(r.OPS) else round(float(r.OPS), 3),
                    "K%": m["k"], "BB%": m["bb"],
                    "BBE": int(r.BBE), "BIP": int(r.BBT),
                    "mix": [int(r.get(c, 0) or 0) for c in MIX_COLS]},        # balls by Mix bucket, MIX_COLS order
        })
    return rows


def league_constants(pit: pd.DataFrame, people: dict) -> dict:
    """FIP constant and SIERA shift so both average out to the league ERA (official ER over Statcast IP), plus the
    luck-neutral ERA inputs: league wOBA on each batted-ball type, league wOBA, and PA per nine innings."""
    ids = [i for i in pit.index if int(i) in people and people[int(i)]["er"] is not None]
    sub = pit.loc[ids]
    ip = sub.outs.sum() / 3
    lg_era = 9 * sum(people[int(i)]["er"] for i in ids) / ip
    fip_c = lg_era - (13 * sub.HR.sum() + 3 * (sub.BBn.sum() + sub.HBP.sum()) - 2 * sub.Kn.sum()) / ip
    raw = siera_raw(sub.Kn.sum(), sub.BBn.sum(), sub.GBn.sum(), sub.FBn_bb.sum(), sub.PUn.sum(), sub.BF.sum())
    out = {"lgERA": round(lg_era, 3), "fipC": round(float(fip_c), 3), "sieraShift": round(float(lg_era - raw), 3)}
    if "wBIP" in pit.columns:                                     # whole population, not just the ER-matched pitchers
        typed = sum(int(pit[f"n{t.upper()}"].sum()) for t in BB_TYPES)
        bbw = {t: round(float(pit[f"w{t.upper()}"].sum() / max(1, pit[f"n{t.upper()}"].sum())), 4) for t in BB_TYPES}
        bbw["ut"] = round(float(pit.wBIP.sum() / max(1, pit.nBIP.sum())), 4)    # untyped balls in play: the BIP average
        out.update({"bbw": bbw, "lgwOBA": round(float(pit.wnum.sum() / pit.wden.sum()), 4), "wobaScale": WOBA_SCALE,
                    "pa9": round(float(9 * pit.BF.sum() / (pit.outs.sum() / 3)), 2),
                    "wbb": round(float(pit.wUBB.sum() / max(1, pit.nUBB.sum())), 3),      # wOBA value of a walk / a hit by pitch
                    "whbp": round(float(pit.wHBP.sum() / max(1, pit.HBP.sum())), 3)})
    if MIX:
        out["mix"] = MIX
    if "bbw" in out:
        sc = stuff_consts(pit, out["bbw"], out["pa9"])
        if sc:
            out["stuff"] = sc                                     # Stuff+'s league means and weights (the page re-derives it in a window)                                          # Mix wOBA's league values (the page re-derives it in a window)
    return out


def neutral_era(r, consts) -> float | None:
    """Luck-neutral ERA: every ball in play gets the league's average wOBA for its batted-ball type (ground ball,
    line drive, fly ball, popup), strikeouts / walks / HBP stay as they were, and the result is put on the ERA
    scale around the league ERA using the wOBA scale and league PA per nine — so BABIP and HR/FB luck wash out
    while a ground-ball profile keeps its value."""
    if "bbw" not in consts or not r.wden:
        return None
    xnum = r.wnum - r.wBIP + sum(r[f"n{t.upper()}"] * consts["bbw"][t] for t in BB_TYPES)
    untyped = r.nBIP - sum(r[f"n{t.upper()}"] for t in BB_TYPES)
    xnum += untyped * consts["bbw"]["ut"]
    xw = xnum / r.wden
    return round(consts["lgERA"] + (xw - consts["lgwOBA"]) / consts["wobaScale"] * consts["pa9"], 2)


def build_pitchers(pit: pd.DataFrame, people: dict, days_p: dict, consts: dict) -> list:
    pit = pit[pit.BF >= MIN_BF_PITCHER].copy()
    pit["role"] = np.where(pit.GS / pit.G.replace(0, np.nan) >= STARTER_SHARE, "SP", "RP")
    rows = []
    for pid, r in pit.iterrows():
        info = people.get(int(pid))
        if not info:
            continue
        m = metric_values(r, PITCHER_METRICS)
        m["k"], m["bb"] = (None if pd.isna(r.K_pct) else round(float(r.K_pct), 1)), (None if pd.isna(r.BB_pct) else round(float(r.BB_pct), 1))
        m["kbb"] = None if pd.isna(r.K_pct) or pd.isna(r.BB_pct) else round(float(r.K_pct - r.BB_pct), 1)
        m["era"] = info["era"]
        ip = r.outs / 3
        m["fip"] = round((13 * r.HR + 3 * (r.BBn + r.HBP) - 2 * r.Kn) / ip + consts["fipC"], 2) if ip else None
        sr = siera_raw(r.Kn, r.BBn, r.GBn, r.FBn_bb, r.PUn, r.BF)
        m["siera"] = round(sr + consts["sieraShift"], 2) if sr is not None else None
        m["nera"] = neutral_era(r, consts) if "wBIP" in pit.columns else None
        bbl = {t: [int(r[f"n{t.upper()}"]), round(float(r[f"w{t.upper()}"] / r[f"n{t.upper()}"]), 3) if r[f"n{t.upper()}"] else None]
               for t in BB_TYPES} if "wBIP" in pit.columns else None
        for key, col in [("swstr", "SwStr_pct"), ("csw", "CSW_pct"), ("zone", "Zone_pct"), ("osw", "OSwing_pct"), ("swing", "Swing_pct"),
                         ("zcon", "ZContact_pct"), ("fbv", "FBvelo"), ("ext", "Ext"), ("ev", "avg_EV"),
                         ("hh", "HardHit_pct"), ("brl", "Barrel_pct"), ("pu", "PU_pct")]:
            m[key] = None if pd.isna(r[col]) else round(float(r[col]), 1)
        sc = consts.get("stuff")
        stuff_rows = None
        if sc and STUFF is not None and pid in STUFF["p"].index:
            s_ = STUFF["p"].loc[pid]
            m["swhf"], m["sbb"], m["sstr"], m["stuff"] = stuff_grade(s_.n, s_.w, s_.g, s_.p, s_.s, sc, consts["lgERA"])
            t_ = STUFF["t"].loc[pid] if pid in STUFF["t"].index.get_level_values(0) else None
            if t_ is not None:                             # his arsenal: one row per pitch type, most-thrown first
                stuff_rows = []
                for pt, x in t_.sort_values("n", ascending=False).iterrows():
                    wp, bp, spp, sp = stuff_grade(x.n, x.w, x.g, x.p, x.s, sc, consts["lgERA"])
                    r1 = lambda v, k=1: None if pd.isna(v) else round(float(v), k)
                    stuff_rows.append([pt, int(x.n), r1(x.velo), r1(x.ivb), r1(x.hb), None if pd.isna(x.spin) else int(round(x.spin)),
                                       r1(100 * x.w / x.n), r1(100 * x.g / x.n), r1(100 * x.p / x.n), wp, bp, sp,
                                       r1(100 * x.wh / x.sw) if x.sw else None, r1(100 * x.gb / x.bip) if x.bip else None,
                                       r1(100 * x.pu / x.bip) if x.bip else None, int(x.sw), int(x.bip),
                                       r1(100 * x.s / x.n), spp, r1(100 * x.stk / x.n)])
        else:
            m["swhf"] = m["sbb"] = m["sstr"] = m["stuff"] = None
        rows.append({
            "id": int(pid), "name": info["name"], "team": info["team"], "type": "P",
            "primary": r["role"], "pos": {r["role"]: int(r.G)}, "throws": r["throws"],
            "age": info["age"], "bf": int(r.BF), "ip": round(float(info["ip"] or 0), 3),
            "m": m,
            "ctx": {"G": int(r.G), "GS": int(r.GS), "K%": m["k"],
                    "BB%": m["bb"], "wOBA": None if pd.isna(r.wOBA) else round(float(r.wOBA), 3),
                    "Pitches": int(r.Pitches),
                    "IPs": round(float(r.outsS) / 3, 1), "IPr": round(float(r.outsR) / 3, 1),   # innings as starter / reliever
                    "bbl": bbl,                                                                  # balls in play and wOBA allowed by type
                    "PAw": int(r.wden) if "wden" in r else None, "HBP": int(r.HBP),           # wOBA plate appearances + HBP (underlying ERA)
                    "arsenal": stuff_rows},     # per pitch type: STUFF_ARSENAL fields
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", default=str(dt.date.today() - dt.timedelta(days=1)))
    ap.add_argument("--statcast-parquet", help="use a saved pitch-level parquet instead of pybaseball")
    args = ap.parse_args()

    t0 = time.time()
    log("1/4 Statcast")
    d = pd.read_parquet(args.statcast_parquet) if args.statcast_parquet else load_statcast(args.end)
    d = pitch_flags(d)
    if GAME_TYPES == {"R"}:
        log("  stuff: loading last season to train on")
        d = add_stuff(d, load_prior_season(SEASON - 1))
    hit = hitter_metrics(d)
    pit = pitcher_metrics(d)
    log(f"  {len(hit)} batters, {len(pit)} pitchers  ({time.time()-t0:.0f}s)")

    log("2/4 Savant leaderboards")
    sav = savant_batted_ball()
    xw = savant_xwoba()
    bsp = savant_bat_speed()

    log("3/4 MLB Stats API")
    hit_ids = hit[hit.PA >= MIN_PA_HITTER].index
    pit_ids = pit[pit.BF >= MIN_BF_PITCHER].index
    people = mlb_people(sorted(set(hit_ids) | set(pit_ids)))
    # minor-league games by position for hitters who spent part of the year down (ESPN counts them for eligibility)
    few = [i for i in hit_ids if i in people and sum(people[i]["pos"].values()) < MILB_MAX_MLB_GAMES]
    log(f"    minors positions for {len(few)} hitters")
    for pid, pos in milb_positions(few).items():
        people[pid]["milb"] = pos

    log("4/4 per-day rows + data.js")
    days_list = sorted(d["game_date"].astype(str).str[:10].unique())
    days = {day: i for i, day in enumerate(days_list)}
    days_h, days_p = daily(d, days)
    hitters = build_hitters(hit, sav, people, days_h, xw, bsp)
    consts = league_constants(pit[pit.BF >= CONST_MIN_BF], people)
    log(f"  league ERA {consts['lgERA']}, FIP constant {consts['fipC']}, SIERA shift {consts['sieraShift']}")
    pitchers = build_pitchers(pit, people, days_p, consts)
    meta = {
        "season": SEASON, "through": str(d.game_date.max())[:10],
        "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "hitterMetrics": [{"key": k, "label": l, "hib": h, "unit": u} for k, l, _, h, _, u in HITTER_METRICS],
        # pitcher list columns show the value itself, coloured by percentile (the Score column stays a percentile)
        "pitcherMetrics": [{"key": k, "label": l, "hib": h, "unit": u, "showValue": True} for k, l, _, h, _, u in PITCHER_METRICS]
                          + [{"key": "nera", "label": "Luck-neutral ERA", "hib": False, "dec": 2, "unit": "", "showValue": True},
                             {"key": "uera", "label": "uERA", "hib": False, "dec": 2, "unit": "", "showValue": True},          # uERA and u(K-BB%) are derived in the app
                             {"key": "ukb", "label": "u(K-BB%)", "hib": True, "dec": 1, "unit": "%", "showValue": True}],
        "defaultMin": DEFAULT_MIN,
        "refMinPA": REF_MIN_PA,
        "days": days_list,
        "dayFields": {"H": HITTER_DAY, "P": PITCHER_DAY},
        "pullLine": PULL_LINE,
        "hitterWeights": HITTER_SCORE_WEIGHTS,
        "pitcherWeights": PITCHER_SCORE_WEIGHTS,
        "hitterHeadline": {"key": "xwoba", "label": "xwOBA", "hib": True, "unit": ""},
        "hitterCard": [{"group": grp, "metrics": [{"key": k, "label": l, "hib": h, "dec": dc, "unit": u} for k, l, h, dc, u in ms]}
                       for grp, ms in HITTER_CARD],
        "hitterCardLeft": HITTER_CARD_LEFT,
        "hitterCardRules": HITTER_CARD_RULES,
        "hitterSub": {k: [{"key": kk, "label": l, "hib": h, "dec": dc, "unit": u} for kk, l, h, dc, u in v] for k, v in HITTER_SUB.items()},
        "airNoPU": True,          # Air% (season values and day rows) excludes popups
        "pitcherCard": [{"group": grp, "metrics": [{"key": k, "label": l, "hib": h, "dec": dc, "unit": u} for k, l, h, dc, u in ms]}
                        for grp, ms in PITCHER_CARD],
        "pitcherCardLeft": PITCHER_CARD_LEFT,
        "pitcherCardFold": PITCHER_CARD_FOLD,
        "pitcherSub": {k: [{"key": kk, "label": l, "hib": h, "dec": dc, "unit": u} for kk, l, h, dc, u in v] for k, v in PITCHER_SUB.items()},
        "consts": consts,
        "arsenalFields": STUFF_ARSENAL,
        "scoreNote": {
            "H": "xwOBA (Statcast expected wOBA from exit velocity and launch angle); the full season uses Savant's "
                 "published number, date windows and splits rebuild it from pitch-level data to within about .001",
            "blend": "wOBA percentile blend (Formula 1): 40.5% Barrel, 17.2% O-Contact, 16.9% Z-Contact, "
                     "11.6% Avg EV, 9.0% Z-minus-O Swing, 4.5% O-Swing (flipped), 0.2% Pull Air — re-ranked as a percentile",
            "P": "plain average of the Whiff% and Strike% percentiles",
        },
    }
    out = {"meta": meta, "players": hitters + pitchers}
    (HERE / "data.js").write_text("window.DRAFT_DATA = " + json.dumps(out, separators=(",", ":")) + ";\n")
    # game-by-game split rows, loaded by the page only when a date window or split is chosen
    pit_ids = {q["id"] for q in pitchers}
    days_out = {**{f"H{k}": v for k, v in days_h.items() if any(h["id"] == k for h in hitters)},
                **{f"P{k}": v for k, v in days_p.items() if k in pit_ids}}
    for k in pit_ids:
        games = people.get(k, {}).get("games") or []
        days_out[f"P{k}:er"] = [[days[dt], home, er] for dt, home, er in games if dt in days]
    (HERE / "days.js").write_text("window.DRAFT_DAYS = " + json.dumps(days_out, separators=(",", ":")) + ";\n")
    log(f"    data.js {(HERE / 'data.js').stat().st_size / 1e6:.1f} MB, days.js {(HERE / 'days.js').stat().st_size / 1e6:.1f} MB")
    log(f"OK  {len(hitters)} hitters, {len(pitchers)} pitchers -> data.js  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
