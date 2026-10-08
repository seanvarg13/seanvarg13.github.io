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
STUFF_MODELS = HERE.parent / "model-workspace" / "stuff_models.joblib"   # the fixed Stuff+ models (tools/models/train_stuff.py), 3 Oct 2026
DIR_FEATS = ["launch_speed", "launch_angle", "sprint_speed", "pull_angle", "spray_angle", "stand_R"]

# ---- metrics ------------------------------------------------------------------------------
# key, label, column, higher-is-better, decimals, unit
HITTER_METRICS = [
    ("ev",   "Avg EV",      "avg_EV",       True,  1, "mph"),
    ("evfb", "EV on FB",    "EV_FB",        True,  1, "mph"),   # exit velocity by batted-ball type (Sean, 7 Oct 2026): fly balls, line drives, grounders
    ("evld", "EV on LD",    "EV_LD",        True,  1, "mph"),
    ("evgb", "EV on GB",    "EV_GB",        True,  1, "mph"),
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
# the pitchers' Rating (Sean, 4 Oct 2026: "the four skills in order of importance, ability to get Ks, avoid walks, get gbs, and get
# popups" — process, not outcomes). Weights from a 2020-26 backtest against NEXT season's ESPN points per inning (starters 100+ IP both
# years, r .56 vs .51 for the old 50 / 50 Whiff% / Strike%); Chase% and SwStr% tested and left out (nothing on top of these four)
PITCHER_SCORE_WEIGHTS = {"whf": 50.0, "xbbf": 50.0}   # Sean, 6 Oct 2026: "a ranking stat for pitchers that is the average percentile of their skills thing so whiff and xbb"; was nERA 100 ("make the rating just be their nERA" — the nERA percentile; was Strikeout 60 / Control 20 / Mix wOBA 20   # Sean, 5 Oct 2026: Strikeout (Whiff% / 2-strike Whiff% / Foul% percentiles averaged), Control (Strike% / 3-ball Strike%), Mix wOBA — app.js builds kskl / ctrl in pool(); was x(K-BB)% 80 / Mix wOBA 20   # Sean, 4 Oct 2026 (night): x(K-BB)% and Mix wOBA, the split that scored best against ESPN points per start / inning (kbbrate.py); put back 5 Oct 2026 with the card of that morning

WHIFF = {"swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt", "bunt_foul_tip"}
SWING = WHIFF | {"foul", "hit_into_play", "foul_bunt"}
ZERO_NUM = {"field_error", "fielders_choice", "fielders_choice_out"}
EXCLUDE = {"sac_bunt", "truncated_pa", "catcher_interf", "intent_walk"}
HITS = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
COLS = ["game_date", "game_type", "game_pk", "batter", "pitcher", "stand", "p_throws", "description", "zone",
        "type", "events", "launch_speed", "launch_angle", "launch_speed_angle", "bb_type", "hc_x", "hc_y",
        "inning", "inning_topbot", "at_bat_number", "pitch_number", "outs_when_up", "woba_value", "woba_denom",   # pitch_number: the pitch before (7 Oct 2026)
        "estimated_woba_using_speedangle", "estimated_ba_using_speedangle", "estimated_slg_using_speedangle",
        "bat_speed", "pitch_type", "release_speed", "release_extension", "des",
        "release_spin_rate", "spin_axis", "pfx_x", "pfx_z", "release_pos_x", "release_pos_z", "arm_angle",   # these seven: Stuff
        "home_team", "plate_x", "plate_z", "vx0", "vy0", "vz0", "ax", "ay", "az",  # Stuff's park adjustment and approach angles
        "sz_top", "sz_bot",                                                         # the batter's zone: the location-aware whiff model
        "balls", "strikes",                                                         # the count: the command models (swing, called strike) — 3 Oct 2026
        "swing_length", "attack_angle", "attack_direction", "swing_path_tilt",      # the batter's swing (with bat_speed above): the foul model with swing — 4 Oct 2026
        "intercept_ball_minus_batter_pos_x_inches", "intercept_ball_minus_batter_pos_y_inches"]
        # (home_team was missing until 2 Oct 2026, so the season being built was graded without its park adjustment)
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
              "mxgb", "mxpu", "mxldp", "mxldc", "mxldo", "mxfbp", "mxfbc", "mxfbo", "mxx", "hr", "wbh",
              "evfbs", "evfbn", "evlds", "evldn", "evgbs", "evgbn",   # EV sums and counts by batted-ball type (fly ball / line drive / grounder; 7 Oct 2026) so a window re-derives EV on FB / LD / GB   # wbh: wOBA value of his hits on balls in play (not HR) — BABIP reliance; hr: home runs (the fantasy page splits his official line by hand with these); mixsum / mixn = batted-ball mix value (Mix wOBA), mx* = its balls by bucket (mxx: air, no direction); dnum = directional-xwOBA numerator; evs = that row's exit velocities (no bunts); trailing fields (older files lack them): bbt = typed balls in play, bip = all balls in play, evn = EV-eligible (tracked, no bunt)
              "evbk"]   # each evs entry's Mix bucket (MIX_COLS index, -1 outside the mix), so a window re-derives EV by bucket for the Mix tab (8 Oct 2026)
# The hitter card, grouped. key, label, higher-is-better, decimals, unit. Keys not in HITTER_METRICS are card-only.
HITTER_CARD = [
    ("Outcomes",             [("woba", "wOBA", True, 3, ""), ("xws", "xwOBA", True, 3, ""), ("xwd", "dxwOBA", True, 3, "")]),
    ("Batted-ball quality",  [("ev", "Avg EV", True, 1, "mph"), ("brl", "Barrel%", True, 1, "%")]),   # the rest fold out under Barrel%; EV by type is the Mix tab's (8 Oct 2026)
    ("Swing decisions",      [("osw", "O-Swing%", False, 1, "%"), ("bb", "BB%", True, 1, "%")]),
    ("Contact",              [("whf", "Whiff%", False, 1, "%"), ("k", "K%", False, 1, "%")]),
    ("Batted-ball distribution", [("air", "Air%", True, 1, "%"), ("pull", "Pull Air%", True, 1, "%")]),   # GB% is Air%'s mirror — it folds out under it (Air% back, Sean 8 Oct 2026)
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
               "ld", "wbip", "wgb", "wld", "wfb", "wpu", "evn", "h", "stn", "stw", "stg", "stp", "stbw", "stbg", "stbp",
               "stf", "std", "stbf", "stbd", "stnl", "stwl", "stws", "stbwl", "stbws",   # over the pitches swung at: whiff chance with location, stuff-only on the same swings, the types' means of each (Location+)
               "stnb", "stgl", "stpl", "stgs", "stps", "stbgl", "stbpl", "stbgs", "stbps",   # the same over the balls in play for the GB / PU chances (Pitching+)
               "stcn", "stcs", "stck", "stco", "stcso", "stci", "stcsi", "stcwi", "stcw",   # command (3 Oct 2026)
               "fp", "fps", "b3", "b3s", "s2", "s2sw", "s2wh", "s2z",   # count states (3 Oct 2026): first pitches and the strikes among them, three-ball pitches and strikes, two-strike pitches and their swings, whiffs and in-zone pitches
               "stnf", "stfl", "stfs", "stfw",   # fouls with location (stfw: and the batter's swing) (4 Oct 2026): pitches contacted, the foul chance where each crossed and the stuff-only one on the same contact: pitches graded for it; their summed swing and strike chances; out-of-zone pitches and their swing chances; in-zone pitches, their swing chances and swing-and-miss chances; swing-and-miss chances on every pitch   # stb*: the league means of each graded pitch's own type (Stuff+ is graded against pitch type); h: hits allowed (fantasy splits by hand); stn / stw / stg / stp: graded pitches and their summed whiff, ground-ball and popup chances (Stuff); luck-neutral ERA inputs: line drives, wOBA numerator on balls in play and by type; evn = EV-eligible balls (no bunts)
               "evfbs", "evfbn", "evlds", "evldn", "evgbs", "evgbn"]   # EV allowed by batted-ball type (7 Oct 2026): sums and counts of the EV-eligible fly balls / line drives / grounders, so a window re-derives EV on FB / LD / GB
# per-game earned runs (from MLB game logs) ride along as "P<id>:er" rows: [day, home, er]
FASTBALLS = {"FF", "SI", "FT"}
PITCHER_CARD = [
    # Skills first (Sean, 4 Oct 2026): the four rates the Rating weighs, plus Mix wOBA (worked out in the app from ctx.bbl like Mix ERA)
    ("Skills",               [("whf", "Whiff%", True, 1, "%"), ("strk", "Strike%", True, 1, "%"), ("mixw", "Mix wOBA", False, 3, "")]),
    ("Swing & miss",         [("k", "K%", True, 1, "%"), ("whf", "Whiff%", True, 1, "%"), ("csw", "CSW%", True, 1, "%"),
                              # the strikes a pitcher gets without a ball in play, per pitch — the three the K% fit (xK%) is built on (Sean, 4 Oct 2026)
                              ("cstr", "Called Strike%", True, 1, "%"), ("swstr", "SwStr%", True, 1, "%"), ("foul", "Foul%", True, 1, "%")]),
    # the walk formula (Sean, 4 Oct 2026): BB% on Strike% + first-pitch strike% + three-ball strike% has R² .82 against .58 for Strike%
    # alone — Zone% / Chase% add nothing once Strike% is known; they stay fold-outs under Strike% and columns
    ("Zone & chase",         [("bb", "BB%", False, 1, "%"), ("strk", "Strike%", True, 1, "%"), ("fstrk", "1st-pitch Strike%", True, 1, "%"), ("b3strk", "3-ball Strike%", True, 1, "%")]),
    ("Results",              [("kbb", "K-BB%", True, 1, "%"), ("era", "ERA", False, 2, "")]),
    ("Batted ball",          [("gb", "GB%", True, 1, "%"), ("pu", "Popup%", True, 1, "%"), ("mixw", "Mix wOBA", False, 3, ""), ("mera", "Mix ERA", False, 2, ""),   # Mix wOBA on the card, Mix ERA a column (4 Oct 2026)
                              # EV allowed by batted-ball type (Sean, 7 Oct 2026: "add the gb fb and LD exit velo to the batted ball section"): the hitters' evfb / evld / evgb from his side
                              ("evgb", "EV on GB", False, 1, "mph"), ("evfb", "EV on FB", False, 1, "mph"), ("evld", "EV on LD", False, 1, "mph")]),
    # the four rates a pitcher owns outright, averaged (derived in the app from the four below it)
    ("Process score",        [("wsgp", "WSGP", True, 1, "")]),
    # one grade (Sean, 4 Oct 2026: "get rid of stuff+ and pitching+ being separate"): Pitching+ with its halves and Location+; Stuff+ still
    # built (the models, the sums, m.stuff) but no longer a card metric or a column
    ("Stuff",                [("pitch", "Pitching+", True, 0, ""), ("sloc", "Location+", True, 0, ""), ("fbv", "Fastball velo", True, 1, "mph"), ("ext", "Extension", True, 1, "ft")]),
    # what the ERA should be and what he's giving up: the expected / underlying marks beside contact quality
    ("Expected & contact",   [("uk", "uK%", True, 1, "%"), ("ubb", "uBB%", False, 1, "%"),   # the fitted process rates
                              ("ukb", "u(K-BB%)", True, 1, "%"),   # u(K-BB%) is derived in the app (expected K% − expected BB%)
                              ("nera", "Luck-neutral ERA", False, 2, ""),
                              ("siera", "SIERA", False, 2, ""), ("fip", "FIP", False, 2, ""),
                              ("ev", "Avg EV", False, 1, "mph"), ("hh", "Hard-Hit%", False, 1, "%"), ("brl", "Barrel%", False, 1, "%")]),
]
PITCHER_CARD_LEFT = 3   # groups in the card's left column (the folded group below doesn't sit in either)
PITCHER_CARD_FOLD = ["Expected & contact"]   # groups that ride below the card as a fold-out instead of a column
# fold-out rows under a pitcher card metric
PITCHER_SUB = {"kbb": [("k", "K%", True, 1, "%"), ("bb", "BB%", False, 1, "%")],
               "whf": [("swstr", "SwStr%", True, 1, "%"), ("zcon", "Z-Contact%", False, 1, "%")],
               "strk": [("zone", "Zone%", True, 1, "%"), ("osw", "O-Swing%", True, 1, "%")],
               "pitch": [("pwhf", "Whiff+", True, 0, ""), ("pbb", "Batted-ball+", True, 0, "")]}


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
# Two models, trained at every build on this season and the two before (no model file to ship or pickle):
#   * whiff — the chance a swing at this pitch misses (every non-bunt swing);
#   * batted-ball type — ground ball, popup or air ball (line drives and flies together, as uERA treats them) on contact.
# The two combine the way uERA does, so a whiff is worth what it is to uERA: a Whiff% point is 0.933 of a K% point
# (UK in app.js), each strikeout takes a ball in play off the board; a ball in play is worth the league's wOBA for
# its type, the air balls at the league's line-drive share. Both put on the ERA scale, and
# Stuff+ = 100 + the % of runs it saves against the league (higher is better; Whiff+ and Batted-ball+ are its halves).
# (Strike+ and a location-aware Pitching+ / Location+ were tried and dropped, 26 Sep 2026: they added little over the
# Strike% already on the card.)
# 2 Oct 2026 (Sean, after Kyle Bland's pitch-model thread: "add all of it in"): two more models and three more inputs, each
# backtested on 2025 / 2026 (models trained on the seasons before, a pitcher's grade against his next half / next season):
#   * foul — the chance contact goes foul instead of into play (a foul saves ~0.085 runs over a ball in play);
#   * damage — the wOBA a ball in play is worth, straight from the traits; Batted-ball+ prices contact at half this, half the
#     GB / PU / air mix, which beat either alone;
#   * the pitcher's hand (the same mirrored pitch from a lefty gets ~2 more whiffs per 100 swings and ~3 more grounders per 100
#     balls in play — hitters see fewer lefties) and location-neutral vertical / horizontal approach angle (what's left of
#     VAA / HAA after the height / side it crossed at, within pitch type).
#   Together, against the next season: runs saved per 100 pitches r .40 -> .49, xwOBA allowed .44 -> .53, K-BB% .45 -> .56.
#   Tested and left out: ball / called-strike chances (helped within a season, hurt the next — command is his, not the
#   pitch's), seam-shifted-wake proxies (spin axis vs movement axis, break per rpm), release point against his fastball.
# 3 Oct 2026 (Sean: "add in the location aspect ... base it off all prior years ... the fixed model"):
#   * the models are FIXED: trained once by tools/models/train_stuff.py on every season from 2020 (spin axis) through the last
#     finished one, saved as model-workspace/stuff_models.joblib on the "models" release, loaded by every build; retrained each
#     off-season (the Train Stuff+ models workflow). Without the file the build trains as before (this season + two). Tested:
#     all six seasons grade as well as the last two and move pitchers less year to year (r .861 vs .847).
#   * a second family with LOCATION (where the pitch crossed the plate: height in the batter's zone, side) — whiff and
#     batted-ball type again, each also seeing the spot (Sean, 3 Oct 2026: "whiff+, bb+ and location+ ... feeds into pitching
#     plus ... a separate model from the stuff plus, but still have both predict whiff% and gb% and pu%"). Each location-aware
#     chance is carried with the stuff-only chance ON THE SAME PITCHES (swings for whiffs, balls in play for the mix — a whiff
#     chance is P(whiff | swing) at that spot, so over every pitch a ball in the dirt reads 80%), so Pitching+ = Stuff+ + what
#     location adds and Location+ = Pitching+ − Stuff+ + 100. Same-season r with Whiff% .73-.78 -> .86-.89; next-season
#     +.04-.07 for whiffs, a touch worse for the mix. The count was tested and left out (nothing on top of location). A
#     run-value regressor (FanGraphs' recipe) was tested against the component build and lost on every next-period target.
# ============================================================================================
STUFF = None        # {"lg": league means, "pt": by pitch type, "p": per-pitcher sums, "t": per pitcher-and-pitch-type sums} for the dataset being built
STUFF_PT = {"FF": 0, "SI": 1, "FC": 2, "SL": 3, "ST": 4, "SV": 5, "CU": 6, "KC": 7, "CS": 6, "CH": 8, "FS": 9, "FO": 9, "SC": 8,
            "KN": 10, "EP": 11, "FA": 0}
STUFF_COLS = ["release_spin_rate", "spin_axis", "pfx_x", "pfx_z", "release_pos_x", "release_pos_z", "arm_angle"]
STUFF_BB = {"ground_ball": 0, "popup": 1, "line_drive": 2, "fly_ball": 2}
STUFF_BUNT = {"foul_bunt", "missed_bunt", "bunt_foul_tip"}
# a pitcher's ctx.arsenal rows, one per pitch type (x = the model's chance; the plain ones are what happened)
STUFF_ARSENAL = ["pt", "n", "velo", "ivb", "hb", "spin", "xwhf", "xgb", "xpu", "whfp", "bbp", "stuffp", "whf", "gb", "pu", "sw", "bip",
                 "xfoul", "xdmg",      # xfoul: foul chance on contact (%); xdmg: the damage model's wOBA on contact
                 "xwhfl", "locp",      # xwhfl: whiff chance with location (%); locp: Location+ for the pitch (3 Oct 2026)
                 "xgbl", "xpul", "pitp", "whfpl", "bbpl",   # the location-aware GB / PU chances, Pitching+ and its Whiff+ / Batted-ball+
                 "xstk", "stk", "xchs", "chs",              # command (3 Oct 2026): the strike chance the swing and called-strike models give the pitch where it was thrown, and the chase chance out of the zone — each beside what happened (%)
                 "xfoull",              # the foul chance on contact with location (%; 4 Oct 2026), null under 5 contacted pitches
                 "xfoulw",              # ... and with the batter's swing too (the location chance where no swing was tracked)
                 "foul",                # what happened: fouls per contact (%; 6 Oct 2026, the Stuff+ tab's xFoul pair) — null under 5 contacted
                 "cstr", "xcstr"]       # called strikes per pitch (%) and the command models' called-strike chance per pitch (ck − cs over cn; 6 Oct 2026 — the Pitching+ tab's whiffs-to-strikeouts table)
STUFF_FOUL_RV = 0.085   # runs a foul saves over a ball in play (Statcast run expectancy, 2023-2026: .082-.090)
STUFF_DMG = 0.5         # Batted-ball+'s share of the damage model in a ball in play's value (the rest: the GB / PU / air mix)


STUFF_PARK = ["velo", "ivb", "hb", "spin"]     # the traits a ballpark moves (Coors' thin air takes ~3" off a four-seamer's ride)
STUFF_PARK_K = 400                             # shrinkage: a park × pitch type with n pitches keeps n / (n + 400) of its offset


def park_offsets(d: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame | None:
    """How much each park moves each pitch type's velocity, ride, run and spin (Sean, 29 Sep 2026: "park adjusted stuff+").
    A two-way fixed-effects fit — every pitch = his own pitch-type average (that season) + the park's offset — solved by
    alternating the two a few times, so a park isn't blamed for its home staff and a pitcher isn't credited for his park.
    Offsets are shrunk toward zero by sample and centred so the league's parks average out to nothing."""
    if "home_team" not in d.columns:
        return None
    yr = pd.to_datetime(d["game_date"]).dt.year.to_numpy()
    who = d["pitcher"].astype(str) + "_" + pd.Series(yr, index=d.index).astype(str) + "_" + d["pitch_type"].astype(str)
    park = d["home_team"].astype(str) + "_" + d["pitch_type"].astype(str)
    out = {}
    for c in STUFF_PARK:
        x = f[c]; ok = x.notna() & f.pt.notna()
        if ok.sum() < 20000:
            return None
        xs, ws, ps = x[ok], who[ok], park[ok]
        pe = pd.Series(0.0, index=xs.index)
        for _ in range(4):
            own = (xs - pe).groupby(ws).transform("mean")
            r = xs - own
            g = r.groupby(ps).agg(["sum", "size"])
            eff = g["sum"] / (g["size"] + STUFF_PARK_K)
            pe = ps.map(eff).fillna(0.0)
        # centre within each pitch type, pitch-weighted, so the league's own mean is untouched
        n = g["size"]; pt_of = eff.index.str.rsplit("_", n=1).str[-1]
        centre = (eff * n).groupby(pt_of).sum() / n.groupby(pt_of).sum()
        out[c] = eff - pt_of.map(centre).to_numpy()
    return pd.DataFrame(out)


def approach_angles(d: pd.DataFrame, num, L) -> tuple:
    """Vertical and horizontal approach angle at the front of the plate, location-neutral: what's left after the height (VAA)
    or side (HAA, arm side +) it crossed at, fitted within each pitch type — a flat fastball is flat wherever it's thrown."""
    if not all(c in d.columns for c in ("vy0", "vz0", "ay", "az", "plate_z")):
        nan = pd.Series(np.nan, index=d.index); return nan, nan
    vx0, vy0, vz0, ax, ay, az = (num(c) for c in ("vx0", "vy0", "vz0", "ax", "ay", "az"))
    vyf = -np.sqrt(np.maximum(vy0 ** 2 - 2 * ay * (50 - 17 / 12), 0)); t = (vyf - vy0) / ay
    vaa = -np.degrees(np.arctan((vz0 + az * t) / vyf))
    haa = -np.degrees(np.arctan((vx0 + ax * t) / vyf)) * np.where(L, -1, 1)
    out = []
    for a, loc in ((vaa, num("plate_z")), (haa, num("plate_x") * np.where(L, -1, 1))):
        r = pd.Series(np.nan, index=d.index)
        for _, idx in d.groupby("pitch_type").groups.items():
            x, y = loc[idx], a[idx]; m = (x.notna() & y.notna()).to_numpy()
            if m.sum() < 200:
                continue
            b = np.polyfit(x[m], y[m], 1); r[idx] = y - (b[0] * x + b[1])
        out.append(r)
    return out[0], out[1]


STUFF_LOC = ["lx", "lz"]


def location_features(d: pd.DataFrame) -> pd.DataFrame:
    """Where the pitch crossed the plate, for the location-aware whiff model: lz = height as a share of the batter's zone
    (0 = the knees, 1 = the letters), lx = side in feet, positive away from the batter whatever the hands. Not stuff — kept
    apart from stuff_features() so Stuff+ never sees them."""
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype(float) if c in d else pd.Series(np.nan, index=d.index)
    L = d["p_throws"].eq("L").to_numpy(); same = d["stand"].eq(d["p_throws"]).to_numpy()
    lx = num("plate_x") * np.where(L, -1, 1) * np.where(same, 1, -1)
    top, bot = num("sz_top"), num("sz_bot")
    lz = (num("plate_z") - bot) / (top - bot).where((top - bot) > 0.5)
    return pd.DataFrame({"lx": lx, "lz": lz}, index=d.index)


# The pitch before, in the same plate appearance (7 Oct 2026, with the season and release-consistency inputs in stuff_features): was it the
# same pitch type, how much faster or slower is this one, how far did the spot move (feet at the plate). The part of what the models miss
# that repeats year to year (actual − expected whiff r .29-.44, scratch pmodel.js) is where tunnelling and sequencing would live; the
# location family alone takes them — Stuff+ stays the pitch on its own. NaN on the first pitch of a PA and on a frame without the numbering
STUFF_SEQ = ["pv_same", "pv_dvelo", "pv_dloc"]


def seq_features(d: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({c: np.full(len(d), np.nan) for c in STUFF_SEQ}, index=d.index)
    if not {"game_pk", "at_bat_number", "pitch_number", "plate_x", "plate_z", "release_speed"} <= set(d.columns): return out
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype(float)
    g = pd.DataFrame({"k": d["game_pk"].astype(str) + "_" + d["at_bat_number"].astype(str), "pn": num("pitch_number"), "pt": d["pitch_type"].astype(str),
                      "v": num("release_speed"), "x": num("plate_x"), "z": num("plate_z")}, index=d.index)
    g = g[g.pn.notna()].sort_values(["k", "pn"], kind="stable")
    prev = g.groupby("k", sort=False)[["pt", "v", "x", "z"]].shift(1)
    has = prev["v"].notna()
    out.loc[g.index[has], "pv_same"] = (g.pt == prev.pt).astype(float)[has].to_numpy()
    out.loc[g.index[has], "pv_dvelo"] = (g.v - prev.v)[has].to_numpy()
    out.loc[g.index[has], "pv_dloc"] = np.sqrt((g.x - prev.x) ** 2 + (g.z - prev.z) ** 2)[has].to_numpy()
    return out


STUFF_CMD = ["lx", "lz", "edge", "balls", "strikes"]   # the command models' inputs beyond the pitch's traits (3 Oct 2026)
# the batter's swing on the pitch (bat tracking, 2024 on): the foul model with swing (Sean, 4 Oct 2026: "i just really want his and other
# players foul ball data to be accurate") — a late, defensive swing is what a foul is, and whether a pitcher's pitches draw them is his
STUFF_SWING = ["bat_speed", "swing_length", "attack_angle", "attack_direction", "swing_path_tilt",
               "intercept_ball_minus_batter_pos_x_inches", "intercept_ball_minus_batter_pos_y_inches"]


def swing_features(d: pd.DataFrame) -> pd.DataFrame:
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype(float) if c in d else pd.Series(np.nan, index=d.index)
    return pd.DataFrame({c: num(c) for c in STUFF_SWING}, index=d.index)


def command_features(d: pd.DataFrame) -> pd.DataFrame:
    """Where the pitch crossed and the count it came in, for the command models (3 Oct 2026): location_features' lx / lz,
    edge = how far outside the strike zone it crossed, in feet (negative inside; the plate's half-width plus a ball's radius
    to the sides, the batter's own top and bottom), and the count. Not stuff — Stuff+ never sees them."""
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype(float) if c in d else pd.Series(np.nan, index=d.index)
    f = location_features(d)
    top, bot, px, pz = num("sz_top"), num("sz_bot"), num("plate_x"), num("plate_z")
    f["edge"] = np.maximum(px.abs() - (17 / 24 + 0.12), np.maximum(bot - pz, pz - top)).clip(lower=-1.5)
    f["balls"], f["strikes"] = num("balls"), num("strikes")
    return f


def stuff_features(d: pd.DataFrame, park: bool = True) -> pd.DataFrame:
    """One row of model inputs per pitch (NaN where Statcast has no tracking); lefties mirrored so both hands read alike.
    park: velocity, ride, run and spin are taken back to a neutral park first (park_offsets), so a Coors start doesn't
    read as worse stuff and a Tampa one as better; the displayed velo / IVB / HB / spin stay as measured."""
    num = lambda c: pd.to_numeric(d[c], errors="coerce").astype(float) if c in d else pd.Series(np.nan, index=d.index)
    L = d["p_throws"].eq("L").to_numpy()
    velo, spin, axis = num("release_speed"), num("release_spin_rate"), num("spin_axis")
    ivb, hb = 12 * num("pfx_z"), 12 * num("pfx_x") * np.where(L, 1, -1)            # inches; arm-side run positive
    if park:
        pf = park_offsets(d, pd.DataFrame({"pt": d["pitch_type"].map(STUFF_PT).astype(float), "velo": velo, "ivb": ivb, "hb": hb, "spin": spin}, index=d.index))
        if pf is not None:
            key = d["home_team"].astype(str) + "_" + d["pitch_type"].astype(str)
            velo = velo - key.map(pf["velo"]).fillna(0.0); ivb = ivb - key.map(pf["ivb"]).fillna(0.0)
            hb = hb - key.map(pf["hb"]).fillna(0.0); spin = spin - key.map(pf["spin"]).fillna(0.0)
    f = pd.DataFrame({"pt": d["pitch_type"].map(STUFF_PT).astype(float), "velo": velo, "spin": spin}, index=d.index)
    ax = np.radians(np.where(L, 360 - axis, axis))
    f["ax_s"], f["ax_c"], f["ivb"], f["hb"] = np.sin(ax), np.cos(ax), ivb, hb
    f["relx"], f["relz"] = num("release_pos_x") * np.where(L, 1, -1), num("release_pos_z")
    f["ext"], f["arm"] = num("release_extension"), num("arm_angle")
    f["same"] = (d["stand"] == d["p_throws"]).astype(float)
    f["lefty"] = L.astype(float)             # the same (mirrored) pitch plays up from the left side (2 Oct 2026)
    f["vaa"], f["haa"] = approach_angles(d, num, L)
    # against his primary fastball that season: his most-thrown four-seamer, sinker or cutter (per season, so a
    # training set spanning years compares each pitch with the fastball he had then)
    yr = pd.to_datetime(d["game_date"]).dt.year.to_numpy()
    fb = d["pitch_type"].isin(["FF", "SI", "FC"]) & f.velo.notna() & f.ivb.notna()
    x = pd.DataFrame({"pitcher": d["pitcher"], "yr": yr, "pt": d["pitch_type"], "velo": f.velo, "ivb": f.ivb, "hb": f.hb})[fb]
    top = x.groupby(["pitcher", "yr", "pt"]).size().reset_index(name="n").sort_values("n").groupby(["pitcher", "yr"]).tail(1)
    ref = (x.merge(top[["pitcher", "yr", "pt"]], on=["pitcher", "yr", "pt"]).groupby(["pitcher", "yr"])[["velo", "ivb", "hb"]].mean()
           .reindex(pd.MultiIndex.from_arrays([d["pitcher"].to_numpy(), yr])))
    f["dvelo"], f["divb"], f["dhb"] = f.velo.to_numpy() - ref.velo.to_numpy(), f.ivb.to_numpy() - ref.ivb.to_numpy(), f.hb.to_numpy() - ref.hb.to_numpy()
    # arsenal depth (whiff model only, Sean 27 Sep 2026): how much he throws this pitch, and how many pitches he throws a
    # real amount (5%+ that season; a 3% show-me pitch doesn't count). Tested on 2026: first-half xWhiff predicted the
    # second half's Whiff% at .679 against .655 without them (10%+ .665, "effective number of pitches" .674); command
    # habits (zone / edge rate, location spread) described the season better but predicted worse, so they're out
    k = pd.Series(d["pitcher"].astype(str).to_numpy() + "_" + yr.astype(str), index=d.index)
    sh = d.groupby([k, d["pitch_type"]]).size() / d.groupby(k).size()
    f["use"] = sh.reindex(pd.MultiIndex.from_arrays([k, d["pitch_type"]])).to_numpy()
    f["depth"] = sh[sh >= 0.05].groupby(level=0).size().reindex(k).to_numpy().astype(float)
    # the season (7 Oct 2026): with no season input the fixed models priced a 2026 pitch at what the same pitch earned in 2021-25 and read the
    # whole year 2 whiff points hot (2020-21 cold); a season number lets the level follow the year, and a season the models never saw scores at
    # the last one's level (a tree puts an out-of-range value in its last bin). Release consistency: how tightly he repeats his release point
    # on this pitch type that season (feet, the x / z spread combined) — a deception / tunnelling trait no per-pitch input carries
    f["season"] = (yr - 2020).astype(float)
    rel = pd.DataFrame({"x": f.relx, "z": f.relz}).groupby([d["pitcher"].to_numpy(), yr, d["pitch_type"].astype(str).to_numpy()]).std()
    f["relsd"] = np.sqrt(rel.x ** 2 + rel.z ** 2).reindex(pd.MultiIndex.from_arrays([d["pitcher"].to_numpy(), yr, d["pitch_type"].astype(str).to_numpy()])).to_numpy()
    f.loc[f.pt.isna() | f.velo.isna() | f.ivb.isna()] = np.nan                        # untracked or unclassed: no grade
    return f


STUFF_WHIFF_ONLY = ["use", "depth"]                # inputs the batted-ball model leaves out (they didn't help it)


# what a prior season keeps for training (the rest of its columns are dropped as it loads, to keep memory down)
STUFF_TRAIN = ["game_date", "game_type", "pitcher", "stand", "p_throws", "description", "type", "events", "bb_type", "pitch_type",
               "game_pk", "at_bat_number", "pitch_number",      # the pitch before in the plate appearance: seq_features (7 Oct 2026)
               "release_speed", "release_extension", "home_team", "woba_value", "woba_denom",      # home_team: the park adjustment;
               "plate_x", "plate_z", "vx0", "vy0", "vz0", "ax", "ay", "az", "sz_top", "sz_bot",
               "balls", "strikes", "zone",                # woba: damage; the rest: approach angles, location; the count and zone: the command models
               "bat_speed", "swing_length", "attack_angle", "attack_direction", "swing_path_tilt",   # the batter's swing: the foul model with swing (4 Oct 2026)
               "intercept_ball_minus_batter_pos_x_inches", "intercept_ball_minus_batter_pos_y_inches"] + STUFF_COLS
STUFF_YEARS = 2          # prior seasons the models train on besides this one: three seasons in all — tested on 2026 (26 Sep
                         # 2026), a third season still helped a little, a fourth to sixth added nothing, recency weights neither


def load_prior_season(year: int) -> pd.DataFrame:
    """A past regular season for the Stuff models' training (pybaseball's cache makes it cheap after the first
    time). Empty if it can't be had — the models then train on what they have."""
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
                x = x[x["game_type"].eq("R")] if "game_type" in x.columns else x
                out.append(x[[c for c in STUFF_TRAIN if c in x.columns]])
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=STUFF_TRAIN)
    except Exception as e:                                  # noqa: BLE001
        log(f"    stuff: no {year} data ({type(e).__name__})")
        return pd.DataFrame(columns=STUFF_TRAIN)


def load_prior_seasons(season: int) -> pd.DataFrame:
    parts = [load_prior_season(season - k) for k in range(1, STUFF_YEARS + 1)]
    parts = [x for x in parts if len(x)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=STUFF_TRAIN)


STUFF_OUT = ["st_n", "st_w", "st_g", "st_p", "st_bw", "st_bg", "st_bp",   # st_b*: the league means for the pitch's own type
             "st_f", "st_d", "st_bf", "st_bd",                         # foul chance on contact, damage (wOBA on contact)
             "st_nl", "st_wl", "st_ws", "st_bwl", "st_bws",            # on the pitches swung at: whiff chance with location, the
                                                                      # stuff-only chance on the same swings, and the type's means of each (3 Oct 2026)
             "st_nb", "st_gl", "st_pl", "st_gs", "st_ps", "st_bgl", "st_bpl", "st_bgs", "st_bps",   # the same on balls in play for GB / PU
             "st_cn", "st_cs", "st_ck", "st_co", "st_cso", "st_ci", "st_csi", "st_cwi", "st_cw",    # command (3 Oct 2026): graded for it, its swing and strike chances, out of the zone (and its swing chance), in the zone (swing and swing-and-miss chances), swing-and-miss chance on every pitch
             "st_nf", "st_fl", "st_fs", "st_fw"]   # fouls with location (and st_fw: with the batter's swing too, 4 Oct 2026) (4 Oct 2026): on the pitches contacted, the foul chance where the pitch crossed, and the stuff-only one on the same contact


def add_stuff(d: pd.DataFrame, prior=None, ref: pd.DataFrame | None = None) -> pd.DataFrame:
    """Score every pitch on its traits alone: the chance a swing misses (st_w), the chance contact is a grounder / popup
    (st_g / st_p), st_n = 1 if graded. Sets STUFF for the pitcher rows and league constants. A failure costs the grades,
    never the build.
    The models are the fixed ones in STUFF_MODELS when the file is there (3 Oct 2026); without it they're trained here on
    prior (a frame, or a function that loads it — only called when training) plus this dataset, as before.
    With ref (the minors, Sean 27 Sep 2026): the league means and each pitch type's baseline come from ref (that MLB
    season), so a Triple-A pitch is graded against MLB pitches of its type."""
    global STUFF
    STUFF = None
    for c in STUFF_OUT:
        d[c] = 0.0
    if not all(c in d.columns for c in ["pfx_x", "pfx_z", "release_spin_rate"]):
        log("  stuff: no pitch-tracking columns in this data"); return d
    try:
        M = load_stuff_models()
        if M is None:
            prior = prior() if callable(prior) else prior
            if ref is not None:
                train = prior
            else:
                train = pd.concat([prior, d[[c for c in STUFF_TRAIN if c in d.columns]]], ignore_index=True) if prior is not None and len(prior) else d
            M = train_stuff_models(train)
        STUFF = _grade_stuff(M, d, ref) if M else None
    except Exception as e:                                  # noqa: BLE001
        for c in STUFF_OUT:
            d[c] = 0.0
        log(f"  !! stuff skipped: {type(e).__name__}: {e}")
    return d


def load_stuff_models():
    """The fixed models, if the file is there (the daily workflow downloads it from the models release)."""
    if not STUFF_MODELS.exists():
        return None
    try:
        M = joblib.load(STUFF_MODELS)
        t = M.get("trained", {})
        log(f"  stuff: fixed models trained {t.get('at', '?')} on {t.get('seasons', '?')}")
        return M
    except Exception as e:                                  # noqa: BLE001
        log(f"  stuff: {STUFF_MODELS.name} couldn't be loaded ({type(e).__name__}: {e}) — training instead")
        return None


def train_stuff_models(train: pd.DataFrame) -> dict | None:
    """The six models, from a frame of pitches (STUFF_TRAIN columns): whiff per swing, whiff per swing with location,
    batted-ball type on contact, foul on contact, damage (wOBA) on a ball in play. Returns them with their input columns —
    what train_stuff.py saves to model-workspace/stuff_models.joblib."""
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
    t0 = time.time()
    ftr = stuff_features(train)
    ok = ftr.velo.notna().to_numpy()
    desc = train["description"].to_numpy()
    sw = ok & np.isin(desc, list(SWING)) & ~np.isin(desc, list(STUFF_BUNT))
    bb = train["bb_type"].map(STUFF_BB)
    bip = ok & train["type"].eq("X").to_numpy() & bb.notna().to_numpy() & ~train["events"].fillna("").str.contains("bunt").to_numpy()
    if sw.sum() < 5000 or bip.sum() < 2000:
        log(f"  stuff: too few tracked pitches ({sw.sum()} swings)"); return None
    kw = dict(max_iter=400, learning_rate=0.06, max_leaf_nodes=63, min_samples_leaf=200, l2_regularization=1.0,
              categorical_features=[0], early_stopping=True, validation_fraction=0.1, random_state=0)
    # a trait no pitch in the training seasons has (spin axis and arm angle before 2020) is left out: an all-empty
    # column makes the fit fail outright (numpy's "window shape" error), which cost 2015-2019 every grade
    seen = lambda c, m: bool(np.isfinite(ftr[c].to_numpy(dtype=float)[m]).any())
    wcols = [c for i, c in enumerate(ftr.columns) if i == 0 or seen(c, sw)]     # column 0 is the categorical one
    bcols = [c for c in wcols if c not in STUFF_WHIFF_ONLY and seen(c, bip)]
    if len(wcols) < len(ftr.columns): log(f"  stuff: no data for {', '.join(c for c in ftr.columns if c not in wcols)} — graded without")
    ftr = ftr[wcols]; Xtr = ftr.to_numpy()
    wm = HistGradientBoostingClassifier(**kw).fit(Xtr[sw], np.isin(desc[sw], list(WHIFF)))
    bm = HistGradientBoostingClassifier(**kw).fit(ftr[bcols].to_numpy()[bip], bb.to_numpy()[bip].astype(int))
    # foul: of the swings that made contact, the ones that stayed alive; damage: a ball in play's wOBA value
    con = sw & ~np.isin(desc, list(WHIFF))
    fm = HistGradientBoostingClassifier(**kw).fit(Xtr[con], desc[con] == "foul")
    wv = pd.to_numeric(train["woba_value"], errors="coerce").to_numpy() if "woba_value" in train else np.full(len(train), np.nan)
    wd = pd.to_numeric(train["woba_denom"], errors="coerce").fillna(0).to_numpy() if "woba_denom" in train else np.zeros(len(train))
    dmk = bip & (wd > 0) & np.isfinite(wv)
    dm = HistGradientBoostingRegressor(**kw).fit(ftr[bcols].to_numpy()[dmk], wv[dmk]) if dmk.sum() >= 2000 else None
    # whiff with location (3 Oct 2026): the same inputs plus where the pitch crossed the plate
    loc = pd.concat([location_features(train), seq_features(train)], axis=1); lcols = wcols + STUFF_LOC + STUFF_SEQ   # + the pitch before (7 Oct 2026)
    fl = pd.concat([ftr, loc], axis=1); lbcols = bcols + STUFF_LOC + STUFF_SEQ
    lm = HistGradientBoostingClassifier(**kw).fit(fl[lcols].to_numpy()[sw], np.isin(desc[sw], list(WHIFF))) if seen_loc(loc, sw) else None
    lbm = HistGradientBoostingClassifier(**kw).fit(fl[lbcols].to_numpy()[bip], bb.to_numpy()[bip].astype(int)) if seen_loc(loc, bip) else None
    # foul with location (Sean, 4 Oct 2026: "factor in the sequencing location and count for expected foul balls"): where the
    # pitch crossed lifts the pitcher-level fit with foul-on-contact from r .69-.75 to .74-.79 (2025-26, models through 2024)
    # and next season's from .67 to .69; the count and the pitch before (type, velo change, spot moved, what it did, pitch
    # number) added nothing on top and were left out (scratch foulseq.py). The stuff-only foul model stays for Stuff+
    flm = HistGradientBoostingClassifier(**kw).fit(fl[lcols].to_numpy()[con], desc[con] == "foul") if seen_loc(loc, con) else None
    # foul with location and the batter's swing (Sean, 4 Oct 2026): bat speed, swing length, attack angle / direction, path tilt and the
    # intercept point on the contacted pitch — trained on the contact that has bat tracking (2024 on). Backtest (scratch foulsw.py, each
    # season scored by models trained on the other two): pitcher-level r with foul-on-contact .741 / .773 / .734 (location) → .766 /
    # .787 / .762, and the spread of expected rates widens toward the real one (sd 2.6-2.8 → 2.9-3.1 against 3.5). Skenes 2026: 54.1 →
    # 55.1 (actual 56.9); Sasaki 2025 52.0 → 47.2 (44.8); Mason Miller 2025 57.2 → 60.5 (61.2). A pitch without a tracked swing is
    # graded by the location model instead (_grade_stuff), so seasons before 2024 read the location number
    swf = swing_features(train); fwcols = lcols + STUFF_SWING; fwm = None
    cb = con & swf["bat_speed"].notna().to_numpy() if flm is not None else np.zeros(len(train), bool)
    if cb.sum() >= 20000:
        fwm = HistGradientBoostingClassifier(**kw).fit(pd.concat([fl, swf], axis=1)[fwcols].to_numpy()[cb], desc[cb] == "foul")
    else:
        log(f"  stuff: too little contact with bat tracking for the foul-with-swing model ({cb.sum():,})")
    # command (3 Oct 2026; Sean: "a pitchers command and ability to generate chases, stay in the zone and throw strikes and avoid
    # balls"): P(swing) from the pitch's traits, its spot, how far off the plate it was and the count, and P(called strike | taken)
    # from its type, spot and count. Together they give every pitch a strike chance, a chase chance out of the zone and — with
    # the location whiff model — a swing-and-miss chance: the rates uBB%'s fit runs on, from where he threw instead of what came
    # of it. Pitchouts, intentional balls and bunts stay out of the training. Backtested 2024-26 (cmd.py): an expected-rate
    # uBB% tracks the season's BB% less closely than the actual-rate one (r .71 vs .80) but predicts next season's as well or
    # better, and 0.6 actual / 0.4 expected beats either (next-season error 1.23 / 1.29 BB% points vs 1.27 / 1.42); for K% the
    # expected rates added nothing, so uK% is unchanged
    sm = cm = scols = ccols = None; ncmd = 0
    if "balls" in train.columns and "strikes" in train.columns and seen_loc(loc, ok):
        cf = command_features(train); fc = pd.concat([fl, cf[["edge", "balls", "strikes"]]], axis=1)
        fin = lambda c: np.isfinite(cf[c].to_numpy(dtype=float))
        cok = (ok & fin("lz") & fin("balls") & fin("strikes") & ~np.isin(desc, list(STUFF_BUNT)) & ~np.isin(desc, ["pitchout", "intent_ball"])
               & ~train["events"].fillna("").str.contains("bunt").to_numpy())
        tk = cok & np.isin(desc, ["called_strike", "ball", "blocked_ball"])
        if cok.sum() >= 20000 and tk.sum() >= 10000:
            scols, ccols = wcols + STUFF_CMD, ["pt"] + STUFF_CMD + ["same", "lefty"]
            sm = HistGradientBoostingClassifier(**kw).fit(fc[scols].to_numpy()[cok], np.isin(desc[cok], list(SWING)))
            cm = HistGradientBoostingClassifier(**kw).fit(fc[ccols].to_numpy()[tk], desc[tk] == "called_strike")
            ncmd = int(cok.sum())
        else:
            log(f"  stuff: too few pitches with a count and location for the command models ({cok.sum():,})")
    log(f"  stuff: trained on {sw.sum():,} swings / {bip.sum():,} balls in play / {ncmd:,} pitches for command ({len(train):,} pitches, {time.time() - t0:.0f}s)")
    return {"whiff": wm, "whiff_loc": lm, "bb": bm, "bb_loc": lbm, "foul": fm, "foul_loc": flm, "foul_sw": fwm, "dmg": dm, "swing": sm, "call": cm,
            "wcols": wcols, "bcols": bcols, "lcols": lcols, "lbcols": lbcols, "scols": scols, "ccols": ccols, "fwcols": fwcols,
            "trained": {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), "pitches": int(len(train)), "swings": int(sw.sum())}}


def seen_loc(loc: pd.DataFrame, m) -> bool:
    return bool(np.isfinite(loc["lz"].to_numpy(dtype=float)[m]).mean() > 0.5)


def _grade_stuff(M: dict, d: pd.DataFrame, ref: pd.DataFrame | None = None):
    """Grade a dataset with the models: per-pitch chances into d's st_* columns, the yardstick (this dataset's pitches, or
    ref's) into STUFF's league / per-type means, and the per-pitcher and per-pitch-type sums for the cards."""
    t0 = time.time()
    wm, lm, bm, lbm, fm, dm, flm, fwm = M["whiff"], M.get("whiff_loc"), M["bb"], M.get("bb_loc"), M["foul"], M.get("dmg"), M.get("foul_loc"), M.get("foul_sw")
    wcols, bcols, lcols, lbcols = M["wcols"], M["bcols"], M.get("lcols", M["wcols"] + STUFF_LOC), M.get("lbcols", M["bcols"] + STUFF_LOC)
    def score(x):
        f = stuff_features(x); has = f.velo.notna().to_numpy()
        for c in wcols:                                                  # a column the models know that this frame lacks (older data)
            if c not in f.columns: f[c] = np.nan
        X = f[wcols].to_numpy()[has]; Xb = f[bcols].to_numpy()[has]
        out = {"w": wm.predict_proba(X)[:, 1], "b": bm.predict_proba(Xb), "f": fm.predict_proba(X)[:, 1],
               "d": dm.predict(Xb) if dm is not None else np.full(has.sum(), np.nan)}
        fl = pd.concat([f, location_features(x), seq_features(x)], axis=1) if lm is not None or lbm is not None or flm is not None else None
        out["wl"] = lm.predict_proba(fl[lcols].to_numpy()[has])[:, 1] if lm is not None else out["w"].copy()
        out["bl"] = lbm.predict_proba(fl[lbcols].to_numpy()[has]) if lbm is not None else out["b"].copy()
        out["fl"] = flm.predict_proba(fl[lcols].to_numpy()[has])[:, 1] if flm is not None else None   # None: a file trained before it, and the sums stay 0
        out["fw"] = None
        if fwm is not None and out["fl"] is not None:                 # with the batter's swing where it was tracked, the location chance where not
            swf = swing_features(x); fw = pd.concat([fl, swf], axis=1)
            for c in M["fwcols"]:
                if c not in fw.columns: fw[c] = np.nan
            hb = swf["bat_speed"].notna().to_numpy()[has]
            out["fw"] = np.where(hb, fwm.predict_proba(fw[M["fwcols"]].to_numpy()[has])[:, 1] if hb.any() else 0.0, out["fl"])
        # command (3 Oct 2026): the swing and called-strike chances on every graded pitch that has a spot and a count
        sm, cm = M.get("swing"), M.get("call")
        out["cn"] = None
        if sm is not None and cm is not None and "balls" in x.columns and "strikes" in x.columns:
            cf = command_features(x); fc = pd.concat([f, cf], axis=1)
            for c in M["scols"]:
                if c not in fc.columns: fc[c] = np.nan
            cmask = (np.isfinite(cf.lz.to_numpy(dtype=float)) & np.isfinite(cf.balls.to_numpy(dtype=float)) & np.isfinite(cf.strikes.to_numpy(dtype=float)))[has]
            if cmask.any():
                out["cn"] = cmask.astype(float)
                out["ps"] = np.where(cmask, sm.predict_proba(fc[M["scols"]].to_numpy()[has])[:, 1], 0.0)
                out["pc"] = np.where(cmask, cm.predict_proba(fc[M["ccols"]].to_numpy()[has])[:, 1], 0.0)
        return has, out
    has, o = score(d)
    if o["cn"] is not None:
        # the sums the site's expected rates come from: xStrike% = ck / cn, xSwing% = cs / cn, xChase% = cso / co,
        # xZ-Contact% = 1 − cwi / csi, xWhiff% = cw / cs — the swing chance times the location whiff chance is a pitch's
        # swing-and-miss chance. Zone 1-9 is in, 11-14 out (Statcast's); a pitch with no zone counts for strikes and swings only
        cn, ps, pc = o["cn"], o["ps"], o["pc"]
        zone = pd.to_numeric(d["zone"], errors="coerce").to_numpy()[has] if "zone" in d.columns else np.full(has.sum(), np.nan)
        inz, outz = cn * ((zone >= 1) & (zone <= 9)), cn * (zone >= 11)
        d.loc[has, "st_cn"] = cn; d.loc[has, "st_cs"] = ps; d.loc[has, "st_ck"] = (ps + (1 - ps) * pc) * cn
        d.loc[has, "st_co"] = outz; d.loc[has, "st_cso"] = ps * outz
        d.loc[has, "st_ci"] = inz; d.loc[has, "st_csi"] = ps * inz
        d.loc[has, "st_cwi"] = ps * o["wl"] * inz; d.loc[has, "st_cw"] = ps * o["wl"] * cn
    pw, pbt, pf, pdm, pwl, pbl = o["w"], o["b"], o["f"], o["d"], o["wl"], o["bl"]
    d.loc[has, "st_n"] = 1.0; d.loc[has, "st_w"] = pw; d.loc[has, "st_g"] = pbt[:, 0]; d.loc[has, "st_p"] = pbt[:, 1]
    d.loc[has, "st_f"] = pf; d.loc[has, "st_d"] = pdm if dm is not None else 0.0
    # the location-aware chance is P(whiff | swing) at that spot — a ball in the dirt reads 80% whether or not anyone swung —
    # so it's kept, with the stuff-only chance, over the pitches actually swung at (bunts out); summed like the rest
    swm = (d["description"][has].isin(SWING) & ~d["description"][has].isin(STUFF_BUNT)).to_numpy().astype(float)
    d.loc[has, "st_nl"] = swm; d.loc[has, "st_wl"] = pwl * swm; d.loc[has, "st_ws"] = pw * swm
    # the foul chance with location is P(foul | contact) at that spot, so, like the whiff one, it's kept over the pitches
    # actually contacted (with the stuff-only chance on the same pitches); Stuff xK% reads it in the app
    conm = swm * (~d["description"][has].isin(WHIFF)).to_numpy().astype(float)
    pfl = o["fl"] if o["fl"] is not None else None; pfw = o["fw"] if o["fw"] is not None else pfl
    if pfl is not None:
        d.loc[has, "st_nf"] = conm; d.loc[has, "st_fl"] = pfl * conm; d.loc[has, "st_fs"] = pf * conm; d.loc[has, "st_fw"] = pfw * conm
    bim = d["bb_type"][has].isin(STUFF_BB.keys()).to_numpy().astype(float)      # and the mix on the balls in play
    d.loc[has, "st_nb"] = bim; d.loc[has, "st_gl"] = pbl[:, 0] * bim; d.loc[has, "st_pl"] = pbl[:, 1] * bim
    d.loc[has, "st_gs"] = pbt[:, 0] * bim; d.loc[has, "st_ps"] = pbt[:, 1] * bim
    # every pitch also carries the league's average chances for its own type, so a pitcher's grades are against pitch type
    # (Sean, 27 Sep 2026: "vs all pitches" gone) — summed like the chances, so any window or split re-derives them
    pts = d["pitch_type"][has]
    # the yardstick: this dataset's own pitches, or (the minors) the reference MLB season's, graded by the same models
    if ref is not None:
        hr, r = score(ref)
        rsw = (ref["description"][hr].isin(SWING) & ~ref["description"][hr].isin(STUFF_BUNT)).to_numpy().astype(float)
        rbi = ref["bb_type"][hr].isin(STUFF_BB.keys()).to_numpy().astype(float)
        rcon = rsw * (~ref["description"][hr].isin(WHIFF)).to_numpy().astype(float)
        rdf = pd.DataFrame({"pitch_type": ref["pitch_type"].to_numpy()[hr], "n": 1.0, "w": r["w"], "g": r["b"][:, 0], "p": r["b"][:, 1], "f": r["f"], "d": r["d"],
                            "nl": rsw, "wl": r["wl"] * rsw, "ws": r["w"] * rsw, "nf": rcon, "fl": (r["fl"] if r["fl"] is not None else r["f"]) * rcon, "fs": r["f"] * rcon,
                            "fw": (r["fw"] if r["fw"] is not None else r["fl"] if r["fl"] is not None else r["f"]) * rcon,
                            "nb": rbi, "gl": r["bl"][:, 0] * rbi, "pl": r["bl"][:, 1] * rbi, "gs": r["b"][:, 0] * rbi, "ps": r["b"][:, 1] * rbi})
        src = ref
    else:
        rdf = pd.DataFrame({"pitch_type": pts.to_numpy(), "n": 1.0, "w": pw, "g": pbt[:, 0], "p": pbt[:, 1], "f": pf, "d": pdm, "nl": swm, "wl": pwl * swm, "ws": pw * swm,
                            "nf": conm, "fl": (pfl if pfl is not None else pf) * conm, "fs": pf * conm, "fw": (pfw if pfw is not None else pf) * conm,
                            "nb": bim, "gl": pbl[:, 0] * bim, "pl": pbl[:, 1] * bim, "gs": pbt[:, 0] * bim, "ps": pbt[:, 1] * bim})
        src = d
    air0 = src["bb_type"].isin(["line_drive", "fly_ball"])
    nsw, nbi = max(1.0, float(rdf.nl.sum())), max(1.0, float(rdf.nb.sum()))
    base = {"w": float(rdf.w.mean()), "g": float(rdf.g.mean()), "p": float(rdf.p.mean()), "f": float(rdf.f.mean()),
            "d": float(np.nanmean(rdf.d)) if dm is not None else None, "wl": float(rdf.wl.sum() / nsw), "ws": float(rdf.ws.sum() / nsw),
            "gl": float(rdf.gl.sum() / nbi), "pl": float(rdf.pl.sum() / nbi), "gs": float(rdf.gs.sum() / nbi), "ps": float(rdf.ps.sum() / nbi),
            "fl": float(rdf.fl.sum() / max(1.0, float(rdf.nf.sum()))) if pfl is not None else None, "fs": float(rdf.fs.sum() / max(1.0, float(rdf.nf.sum()))) if pfl is not None else None,
            "fw": float(rdf.fw.sum() / max(1.0, float(rdf.nf.sum()))) if o["fw"] is not None else None,
            "la": float(src["bb_type"].eq("line_drive").sum() / max(1, air0.sum())), **swing_rates(src)}
    tm = rdf.groupby("pitch_type").agg(n=("w", "size"), w=("w", "mean"), g=("g", "mean"), p=("p", "mean"), f=("f", "mean"), d=("d", "mean"),
                                       nl=("nl", "sum"), wl=("wl", "sum"), ws=("ws", "sum"), nb=("nb", "sum"), gl=("gl", "sum"), pl=("pl", "sum"), gs=("gs", "sum"), ps=("ps", "sum"))
    tm = tm[tm.n >= 500]
    for c in ("wl", "ws"): tm[c] = tm[c] / tm.nl.clip(lower=1)           # the type's means over its swings ...
    for c in ("gl", "pl", "gs", "ps"): tm[c] = tm[c] / tm.nb.clip(lower=1)   # ... and over its balls in play
    for c in ("w", "g", "p", "f", "d"):
        d.loc[has, "st_b" + c] = pts.map(tm[c]).fillna(base[c] if base[c] is not None else 0.0).to_numpy()
    for c in ("wl", "ws"):                                                # on his swung-at pitches only, so the sums line up with st_nl
        d.loc[has, "st_b" + c] = pts.map(tm[c]).fillna(base[c]).to_numpy() * swm
    for c in ("gl", "pl", "gs", "ps"):                                    # and on his balls in play, with st_nb
        d.loc[has, "st_b" + c] = pts.map(tm[c]).fillna(base[c]).to_numpy() * bim
    fr0 = stuff_features(d, park=False)                                   # the arsenal table shows what was measured, park and all
    g = d[has].assign(velo=fr0.velo[has], ivb=fr0.ivb[has], hb=fr0.hb[has], spin=fr0.spin[has], wh=d["description"][has].isin(WHIFF),
                      swg=d["description"][has].isin(SWING), gbx=d["bb_type"][has].eq("ground_ball"), pux=d["bb_type"][has].eq("popup"),
                      bipx=d["bb_type"][has].isin(STUFF_BB.keys()),
                      stkx=d["type"][has].isin(["S", "X"]) & (d["st_cn"][has] > 0),        # what happened on the command-graded pitches:
                      oszx=d["description"][has].isin(SWING) & (d["st_co"][has] > 0),       # strikes, and swings at the ones out of the zone
                      fox=d["description"][has].eq("foul") & (d["st_nf"][has] > 0),           # fouls on the contacted pitches the foul models graded
                      csx=d["description"][has].eq("called_strike"))                            # called strikes (6 Oct 2026)
    agg = dict(n=("st_n", "sum"), w=("st_w", "sum"), g=("st_g", "sum"), p=("st_p", "sum"), bw=("st_bw", "sum"), bg=("st_bg", "sum"), bp=("st_bp", "sum"),
               f=("st_f", "sum"), dd=("st_d", "sum"), bf=("st_bf", "sum"), bd=("st_bd", "sum"),
               nl=("st_nl", "sum"), wl=("st_wl", "sum"), ws=("st_ws", "sum"), bwl=("st_bwl", "sum"), bws=("st_bws", "sum"),
               nb=("st_nb", "sum"), gl=("st_gl", "sum"), pl=("st_pl", "sum"), gs=("st_gs", "sum"), ps=("st_ps", "sum"),
               bgl=("st_bgl", "sum"), bpl=("st_bpl", "sum"), bgs=("st_bgs", "sum"), bps=("st_bps", "sum"),
               cn=("st_cn", "sum"), cs=("st_cs", "sum"), ck=("st_ck", "sum"), co=("st_co", "sum"), cso=("st_cso", "sum"),
               ci=("st_ci", "sum"), csi=("st_csi", "sum"), cwi=("st_cwi", "sum"), cw=("st_cw", "sum"), stk=("stkx", "sum"), osz=("oszx", "sum"),
               nf=("st_nf", "sum"), fl=("st_fl", "sum"), fs=("st_fs", "sum"), fw=("st_fw", "sum"), fo=("fox", "sum"), cst=("csx", "sum"))
    res = {"lg": base,
           "pt": rdf.groupby("pitch_type")[["n", "w", "g", "p", "f", "d", "nl", "wl", "ws", "nb", "gl", "pl", "gs", "ps"]].sum(),   # the league by pitch type: each pitch is also graded against its own kind
           "p": g.groupby("pitcher").agg(**agg),
           "t": g.groupby(["pitcher", "pitch_type"]).agg(**agg, velo=("velo", "mean"), ivb=("ivb", "mean"), hb=("hb", "mean"),
                                                           spin=("spin", "mean"), sw=("swg", "sum"), wh=("wh", "sum"),
                                                           bip=("bipx", "sum"), gb=("gbx", "sum"), pu=("pux", "sum"))}
    log(f"  stuff: graded {has.sum():,} pitches ({time.time() - t0:.0f}s)")
    return res


def swing_rates(d: pd.DataFrame) -> dict:
    """The league's swing rate per pitch and whiff rate per swing (bunts out): what turns a foul chance into runs."""
    desc = d["description"]; sw = desc.isin(SWING) & ~desc.isin(STUFF_BUNT)
    return {"swr": float(sw.mean()), "whr": float(desc[sw].isin(WHIFF).mean()) if sw.any() else 0.25}


def stuff_consts(pit: pd.DataFrame, bbw: dict, pa9: float) -> dict | None:
    """Stuff+'s league means and ERA weights: per Whiff% point, and per 1.000 of ball-in-play value."""
    if not STUFF:
        return None
    lg = STUFF["lg"]
    vair = lg["la"] * bbw["ld"] + (1 - lg["la"]) * bbw["fb"]
    lgb = lg["g"] * bbw["gb"] + lg["p"] * bbw["pu"] + (1 - lg["g"] - lg["p"]) * vair
    bip_share = float(pit.nBIP.sum() / max(1, pit.BF.sum()))
    out = {"lgW": round(100 * lg["w"], 3), "lgB": round(lgb, 4), "vair": round(vair, 4), "gb": bbw["gb"], "pu": bbw["pu"],
           "kW": round(0.00933 * lgb / WOBA_SCALE * pa9, 4), "kB": round(bip_share / WOBA_SCALE * pa9, 3)}
    # foul (2 Oct 2026): ERA per point of foul chance on contact = contact per pitch x the runs a foul saves x pitches per nine
    p9 = float(pit["Pitches"].sum() / max(1, pit["outs"].sum()) * 27) if "Pitches" in pit.columns and "outs" in pit.columns else 0.0
    if lg.get("f") is not None and p9:
        out.update({"lgF": round(100 * lg["f"], 3), "kF": round(0.01 * lg["swr"] * (1 - lg["whr"]) * STUFF_FOUL_RV * p9, 4)})
    if lg.get("d") is not None:
        out.update({"lgD": round(lg["d"], 4), "dmg": STUFF_DMG})     # damage: blended into a ball in play's value at STUFF_DMG
    if lg.get("fl") is not None:                                      # over contact: the league's foul chance with location, and stuff-only on the same contact
        out.update({"lgFL": round(100 * lg["fl"], 3), "lgFS": round(100 * lg["fs"], 3)})
    if lg.get("fw") is not None:                                      # over contact: the foul chance with location and the batter's swing
        out.update({"lgFW": round(100 * lg["fw"], 3)})
    if lg.get("wl") is not None:                                      # over swings: the league's whiff chance with location, and stuff-only on the same swings
        out.update({"lgWL": round(100 * lg["wl"], 3), "lgWS": round(100 * lg["ws"], 3)})
    if lg.get("gl") is not None:                                      # over balls in play: the GB / PU chances with location, and stuff-only on the same balls
        out.update({"lgGL": round(lg["gl"], 4), "lgPL": round(lg["pl"], 4), "lgGS": round(lg["gs"], 4), "lgPS": round(lg["ps"], 4)})
    # each pitch type's league-average grades, so a pitch can be graded against its own kind (a four-seamer vs four-seamers):
    # [pitches, xWhiff%, xGB, xPU, xFoul%, xDamage, xWhiff% with location over its swings, stuff-only xWhiff% over the same swings,
    #  then over its balls in play: xGB and xPU with location, and stuff-only on the same balls]
    out["types"] = {pt: [int(x.n), round(100 * x.w / x.n, 3), round(x.g / x.n, 4), round(x.p / x.n, 4),
                         round(100 * x.f / x.n, 3), round(x.d / x.n, 4)]
                        + ([round(100 * x.wl / x.nl, 3), round(100 * x.ws / x.nl, 3)] if "nl" in x and x.nl > 0 else [None, None])
                        + ([round(x.gl / x.nb, 4), round(x.pl / x.nb, 4), round(x.gs / x.nb, 4), round(x.ps / x.nb, 4)] if "nb" in x and x.nb > 0 else [None] * 4)
                    for pt, x in STUFF["pt"].iterrows() if x.n >= 500}
    return out


def stuff_parts(sc: dict, xw, xg, xp, era, xf=None, xd=None):
    """Whiff+ and Batted-ball+ from rates (xWhiff% per swing, GB / PU shares of contact, foul% of contact, damage = wOBA on
    contact) against the league: a ball in play is valued at the GB / PU / air mix blended with the damage model, and a foul
    chance above the league's saves the runs a foul saves over a ball in play. app.js's stuffParts() is the same."""
    xb, lb = xg * sc["gb"] + xp * sc["pu"] + (1 - xg - xp) * sc["vair"], sc["lgB"]
    if xd is not None and sc.get("lgD") is not None:
        a = sc.get("dmg", STUFF_DMG); xb, lb = (1 - a) * xb + a * xd, (1 - a) * lb + a * sc["lgD"]
    bp = 100 - 100 * sc["kB"] * (xb - lb) / era
    if xf is not None and sc.get("kF"):
        bp += 100 * sc["kF"] * (xf - sc["lgF"]) / era
    return 100 + 100 * sc["kW"] * (xw - sc["lgW"]) / era, bp


def location_delta(x, sc: dict, lg_era: float):
    """What location adds (3 Oct 2026), in Stuff+ points, from a row of summed chances (x: a pitcher's or a pitch type's):
    whiffs — over the pitches swung at, his location-aware whiff edge over his types minus his stuff-only edge on the same
    swings, at kW ERA per whiff point; the mix — over his balls in play, the same for the GB / PU / air value at kB. Returns
    (whiff delta, mix delta) or None; Pitching+'s halves are Whiff+ / Batted-ball+ plus these, Location+ = 100 + both.
    app.js's locDelta() is the same."""
    if not sc or not sc.get("kW") or x is None:
        return None
    g = lambda k: (x[k] if k in x and x[k] is not None and not pd.isna(x[k]) else None)
    nl, nb = g("nl"), g("nb")
    if not nl or g("wl") is None or not g("bwl"):
        return None
    dw = 100 * sc["kW"] * (100 * ((g("wl") - g("bwl")) - (g("ws") - g("bws"))) / nl) / lg_era
    db = 0.0
    if nb and g("gl") is not None and g("bgl"):
        val = lambda gg, pp: (gg * sc["gb"] + pp * sc["pu"] + (nb - gg - pp) * sc["vair"]) / nb
        edge_loc, edge_stuff = val(g("gl"), g("pl")) - val(g("bgl"), g("bpl")), val(g("gs"), g("ps")) - val(g("bgs"), g("bps"))
        db = -100 * sc["kB"] * (edge_loc - edge_stuff) / lg_era
    return dw, db


def pitching_grade(wp, bp, x, sc: dict, lg_era: float):
    """Pitching+ and its halves, Location+ (3 Oct 2026): the Stuff+ halves (wp, bp, against type) plus what location adds."""
    d = location_delta(x, sc, lg_era)
    if d is None or wp is None:
        return None, None, None, None
    wl, bl = wp + d[0], bp + d[1]
    return round(wl, 1), round(bl, 1), round(wl + bl - 100, 1), round(100 + d[0] + d[1], 1)


def pitch_loc_row(x, wp, bp, sc: dict, lg_era: float):
    """The arsenal row's location fields: xWhiff with location (%), Location+, xGB / xPU with location (%), Pitching+ and its
    halves — None under 5 swings / 5 balls in play. (wp, bp: the pitch's stuff grades vs all pitches, like stuff_grade's; the
    site re-bases them against type.)"""
    r1 = lambda v: None if v is None or pd.isna(v) else round(float(v), 1)
    nl, nb = (x["nl"] if "nl" in x else 0), (x["nb"] if "nb" in x else 0)
    xwl = r1(100 * x.wl / nl) if nl >= 5 else None
    xgl, xpl = (r1(100 * x.gl / nb), r1(100 * x.pl / nb)) if nb >= 5 else (None, None)
    pw, pb, pp, loc = pitching_grade(wp, bp, x, sc, lg_era) if nl >= 5 else (None, None, None, None)
    return [xwl, loc, xgl, xpl, pp, pw, pb]


def command_row(x):
    """The arsenal row's command fields (3 Oct 2026): xStrike% and Strike% over the pitches graded for command, xChase% and
    Chase% over the ones out of the zone — None under 5 of either."""
    r1 = lambda v: None if v is None or pd.isna(v) else round(float(v), 1)
    cn, co = (x["cn"] if "cn" in x else 0), (x["co"] if "co" in x else 0)
    return [r1(100 * x.ck / cn) if cn >= 5 else None, r1(100 * x.stk / cn) if cn >= 5 else None,
            r1(100 * x.cso / co) if co >= 5 else None, r1(100 * x.osz / co) if co >= 5 else None]


def stuff_grade(n, w, g, p, sc: dict, lg_era: float, f=None, d=None):
    """Whiff+, Batted-ball+ and Stuff+ (= the two together) from summed per-pitch predictions."""
    if not sc or not n:
        return None, None, None
    wp, bp = stuff_parts(sc, 100 * w / n, g / n, p / n, lg_era, None if f is None else 100 * f / n, None if d is None else d / n)
    return round(wp, 1), round(bp, 1), round(wp + bp - 100, 1)


def stuff_grade_type(n, w, g, p, bw, bg, bp, sc: dict, lg_era: float, f=None, d=None, bf=None, bd=None):
    """Whiff+, Batted-ball+ and Stuff+ against pitch type: the same weights, but his baseline is the league's average for
    the pitches he throws, in his mix (= the usage-weighted mean of his pitches' grades against their own types)."""
    if not sc or not n:
        return None, None, None
    r = lambda v: None if v is None else v / n
    wp, bp_ = stuff_parts(sc, 100 * w / n, g / n, p / n, lg_era, None if f is None else 100 * f / n, r(d))
    wb, bb = stuff_parts(sc, 100 * bw / n, bg / n, bp / n, lg_era, None if bf is None else 100 * bf / n, r(bd))
    wp, bp_ = wp - wb + 100, bp_ - bb + 100
    return round(wp, 1), round(bp_, 1), round(wp + bp_ - 100, 1)


def pitch_flags(d: pd.DataFrame) -> pd.DataFrame:
    global STUFF
    STUFF = None                                           # add_stuff() sets it again for a dataset that gets Stuff grades
    d = d.copy()
    z = pd.to_numeric(d["zone"], errors="coerce")
    d["in_zone"], d["out_zone"] = z.le(9), z.ge(11)
    d["swing"] = d["description"].isin(SWING)
    d["whiff"] = d["description"].isin(WHIFF)
    d["contact"] = d["swing"] & ~d["whiff"]
    d["z_swing"], d["o_swing"] = d["in_zone"] & d["swing"], d["out_zone"] & d["swing"]
    d["z_contact"], d["o_contact"] = d["in_zone"] & d["contact"], d["out_zone"] & d["contact"]
    d["strike"] = d["type"].isin(["S", "X"])
    # count-state rates (Sean, 3 Oct 2026, for uK% / uBB%: "as accurate as humanly and AIly possible"): the first pitch of a plate
    # appearance and whether it was a strike, pitches at three balls and the strikes among them, pitches with two strikes and the swings,
    # whiffs and in-zone pitches among them — pitch-level process, like Strike%, never the plate appearance's result. Held out 2021-26
    # they take a starter's uK% error from 1.37 to 1.12 points and uBB% from 0.91 to 0.54 (relievers 2.13 → 1.75, 1.37 → 0.93)
    b_ = pd.to_numeric(d["balls"], errors="coerce") if "balls" in d.columns else pd.Series(np.nan, index=d.index)
    s_ = pd.to_numeric(d["strikes"], errors="coerce") if "strikes" in d.columns else pd.Series(np.nan, index=d.index)
    d["fp"] = b_.eq(0) & s_.eq(0); d["fps"] = d["fp"] & d["strike"]
    d["b3"] = b_.eq(3); d["b3s"] = d["b3"] & d["strike"]
    d["s2"] = s_.eq(2); d["s2sw"] = d["s2"] & d["swing"]; d["s2wh"] = d["s2"] & d["whiff"]; d["s2z"] = d["s2"] & d["in_zone"]
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
    # each ball's Mix bucket as an index into MIX_COLS (an air ball with no direction is "x"; -1 when it isn't in the mix), so the
    # day rows can carry a bucket for every entry of their evs list (evbk) and a window re-derives EV by bucket for the Mix tab (8 Oct 2026)
    mi = {b: i for i, b in enumerate(MIX_COLS.values())}
    mb = d["mixb"].astype(str); mb = mb.where(~mb.str.endswith("_x"), "x")
    d["mixc"] = np.where(d["mixn"].astype(bool), mb.map(mi).fillna(-1), -1).astype(int)
    for t, bbt in (("fb", "fly_ball"), ("ld", "line_drive"), ("gb", "ground_ball")):   # EV by batted-ball type (Sean, 7 Oct 2026): the same EV-eligible balls, split by the stringer's type
        k = d["evb"] & d["bb_type"].eq(bbt)
        d["ev" + t + "n"] = k.astype(int); d["ev" + t + "s"] = d["launch_speed"].where(k, 0.0)
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
    for t in ("fb", "ld", "gb"):   # EV on fly balls / line drives / grounders (7 Oct 2026); NaN on a frame without the flags
        r["EV_" + t.upper()] = (g["ev" + t + "s"].sum() / g["ev" + t + "n"].sum().replace(0, np.nan)) if ("ev" + t + "s") in d.columns else np.nan
    e = d[d["evb"] & d["mixc"].ge(0)] if "mixc" in d.columns else None   # EV by Mix bucket (8 Oct 2026): the tracked balls in each and their EV sum, for ctx.mixev
    for i in range(len(MIX_COLS)):
        k = e[e["mixc"].eq(i)].groupby("batter")["launch_speed"] if e is not None else None
        r[f"MXS{i}"] = k.sum().reindex(r.index).fillna(0.0) if k is not None else 0.0
        r[f"MXN{i}"] = k.count().reindex(r.index).fillna(0).astype(int) if k is not None else 0
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
    # Foul% (Sean, 4 Oct 2026, hunting what K% − xK% was: "there has to be something that can explain this"): the strikes that are neither
    # called, swung through nor put in play — fouls, per pitch. It is what the K% fit on every other rate was missing: held out season by
    # season the error on 300+ BF pitchers goes 1.42 → 0.63 points, and Skenes / Webb / Phillips / Wandy Peralta's "unexplained" K% is
    # gone (foul 21% vs 14-15%). Contact that goes foul keeps the strikeout alive; a ball in play ends the plate appearance. Year to year
    # r .56, like Strike%. app.js re-derives it in a window from the day rows (strk − cs − whf − bip over pit)
    d = d.assign(foul=d["strike"] & ~d["whiff"] & ~d["bip"] & ~d["cs"])
    g = d.groupby("pitcher")
    f = g.agg(Pitches=("swing", "size"), Swings=("swing", "sum"), Whiffs=("whiff", "sum"), Foul=("foul", "sum"),
              Strikes=("strike", "sum"), BIP=("bip", "sum"), GB=("gb", "sum"),
              G=("game_pk", "nunique"), CS=("cs", "sum"), ZonePit=("in_zone", "sum"), OutPit=("out_zone", "sum"),
              ZSw=("z_swing", "sum"), OSw=("o_swing", "sum"), ZCon=("z_contact", "sum"), FBt=("fbt", "sum"),
              PU=("pu", "sum"), BBE=("bbe", "sum"), EVn=("evb", "sum"), Barrels=("barrel", "sum"), HH=("hardhit", "sum"),
              EVsum=("ev", "sum"), FBn=("fbn", "sum"), FBv=("fbv", "sum"), Extn=("extn", "sum"), Exts=("exts", "sum"),
              FP=("fp", "sum"), FPS=("fps", "sum"), B3=("b3", "sum"), B3S=("b3s", "sum"), S2=("s2", "sum"), S2Sw=("s2sw", "sum"), S2Wh=("s2wh", "sum"), S2Z=("s2z", "sum"),
              **{k: (c, "sum") for k, c in [("EVFBs", "evfbs"), ("EVFBn", "evfbn"), ("EVLDs", "evlds"), ("EVLDn", "evldn"), ("EVGBs", "evgbs"), ("EVGBn", "evgbn")] if c in d.columns})
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
    r["Foul_pct"] = 100 * f.Foul / f.Pitches.replace(0, np.nan)
    r["CStr_pct"] = 100 * f.CS / f.Pitches.replace(0, np.nan)        # called strikes per pitch
    r["Zone_pct"] = 100 * f.ZonePit / f.Pitches.replace(0, np.nan)
    r["OSwing_pct"] = 100 * f.OSw / f.OutPit.replace(0, np.nan)
    r["Swing_pct"] = 100 * f.Swings / f.Pitches.replace(0, np.nan)
    r["ZContact_pct"] = 100 * f.ZCon / f.ZSw.replace(0, np.nan)
    r["FBvelo"] = f.FBv / f.FBn.replace(0, np.nan)
    r["Ext"] = f.Exts / f.Extn.replace(0, np.nan)
    r["avg_EV"] = f.EVsum / f.EVn.replace(0, np.nan)                 # bunts excluded, like Savant
    for t in ("fb", "ld", "gb"):                                      # EV allowed by batted-ball type (7 Oct 2026); nan on a frame without the flags
        k = "EV" + t.upper()
        r["EV_" + t.upper()] = (f[k + "s"] / f[k + "n"].replace(0, np.nan)) if (k + "s") in f.columns else np.nan
    r["HardHit_pct"] = 100 * f.HH / f.BIP.replace(0, np.nan)         # per ball in play
    r["Barrel_pct"] = 100 * f.Barrels / f.BIP.replace(0, np.nan)
    r["FStrk_pct"] = 100 * f.FPS / f.FP.replace(0, np.nan)          # the count-state rates (pitch_flags): first-pitch strike%,
    r["B3Strk_pct"] = 100 * f.B3S / f.B3.replace(0, np.nan)         # strike% at three balls, and with two strikes the whiff% per swing,
    r["S2Whf_pct"] = 100 * f.S2Wh / f.S2Sw.replace(0, np.nan)       # swing% and zone%
    r["S2Sw_pct"] = 100 * f.S2Sw / f.S2.replace(0, np.nan)
    r["S2Zone_pct"] = 100 * f.S2Z / f.S2.replace(0, np.nan)
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


def baserunning(pid: int, info: dict) -> dict:
    """The card's Base Running section (Sean, 30 Sep 2026): Savant's sprint speed (ft/s, its competitive runs) and the
    official steals — SB, attempts (SB + CS) and success rate (none without an attempt). Full season only."""
    try:
        spd = sprint_speeds().get(pid)
    except Exception as e:                                   # a Savant hiccup costs the sprint row, not the build
        log("  sprint speed unavailable:", e); spd = None
    sb, cs = info.get("sb"), info.get("cs")
    att = (sb or 0) + (cs or 0) if sb is not None or cs is not None else None
    return {"spd": round(float(spd), 1) if spd is not None and pd.notna(spd) else None,
            "sb": sb, "sba": att, "sbp": round(100 * sb / att, 1) if att else None}


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
    p["w_bh"] = p["wnum"].where(p["is_hit"] & ~p["is_hr"], 0.0)       # hits in play: what BABIP swings move
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
              mixsum=("mixv", "sum"), mixn=("mixn", "sum"), **{c: (c, "sum") for c in MIX_COLS},
              **{c: (c, "sum") for c in ("evfbs", "evfbn", "evlds", "evldn", "evgbs", "evgbn") if c in d.columns})
    for c in ("evfbs", "evfbn", "evlds", "evldn", "evgbs", "evgbn"):
        if c not in h.columns: h[c] = 0.0
    h["mixsum"] = h["mixsum"].round(4)
    h["evs"] = d[d["evb"]].groupby(HK)["launch_speed"].agg(lambda x: [round(float(v), 1) for v in x])
    if "mixc" in d.columns:                                       # the same balls in the same order: their Mix buckets (8 Oct 2026)
        h["evbk"] = d[d["evb"]].groupby(HK)["mixc"].agg(lambda x: [int(v) for v in x])
    hp = p.groupby(HK).agg(pa=("pa", "sum"), ab=("ab", "sum"), bb=("is_bb", "sum"),
                           k=("is_k", "sum"), wnum=("wnum", "sum"), wden=("wden", "sum"),
                           xnum=("xnum", "sum"), xden=("xden", "sum"), dnum=("dnum", "sum"),
                           h=("is_hit", "sum"), tb=("tb", "sum"), xbsum=("xbsum", "sum"), xssum=("xssum", "sum"),
                           dbsum=("dbsum", "sum"), dssum=("dssum", "sum"), hr=("is_hr", "sum"), wbh=("w_bh", "sum"))
    h = h.join(hp, how="left")
    h["evs"] = h["evs"].apply(lambda v: v if isinstance(v, list) else [])
    h["evbk"] = h["evbk"].apply(lambda v: v if isinstance(v, list) else []) if "evbk" in h.columns else [[] for _ in range(len(h))]
    h = h.fillna(0)
    # pitchers
    PK = ["pitcher", "game_date", "bhand", "phome"]
    g = d.groupby(PK)
    q = g.agg(pit=("swing", "size"), sw=("swing", "sum"), whf=("whiff", "sum"), strk=("strike", "sum"),
              bip=("bip", "sum"), gb=("gb", "sum"), cs=("cs", "sum"), zpit=("in_zone", "sum"), opit=("out_zone", "sum"),
              zsw=("z_swing", "sum"), osw=("o_swing", "sum"), zcon=("z_contact", "sum"), fbt=("fbt", "sum"), pu=("pu", "sum"),
              bbe=("bbe", "sum"), brl=("barrel", "sum"), hh=("hardhit", "sum"), evsum=("ev", "sum"),
              fbn=("fbn", "sum"), fbv=("fbv", "sum"), extn=("extn", "sum"), exts=("exts", "sum"), evn=("evb", "sum"),
              fp=("fp", "sum"), fps=("fps", "sum"), b3=("b3", "sum"), b3s=("b3s", "sum"), s2=("s2", "sum"), s2sw=("s2sw", "sum"), s2wh=("s2wh", "sum"), s2z=("s2z", "sum"),
              **{c: (c, "sum") for c in ("evfbs", "evfbn", "evlds", "evldn", "evgbs", "evgbn") if c in d.columns},   # EV allowed by type (7 Oct 2026)
              **{c: (s, "sum") for c, s in [("stn", "st_n"), ("stw", "st_w"), ("stg", "st_g"), ("stp", "st_p"), ("stbw", "st_bw"), ("stbg", "st_bg"), ("stbp", "st_bp"),
                                                 ("stf", "st_f"), ("std", "st_d"), ("stbf", "st_bf"), ("stbd", "st_bd"),
                                                 ("stnl", "st_nl"), ("stwl", "st_wl"), ("stws", "st_ws"), ("stbwl", "st_bwl"), ("stbws", "st_bws"),
                                                 ("stnb", "st_nb"), ("stgl", "st_gl"), ("stpl", "st_pl"), ("stgs", "st_gs"), ("stps", "st_ps"),
                                                 ("stbgl", "st_bgl"), ("stbpl", "st_bpl"), ("stbgs", "st_bgs"), ("stbps", "st_bps"),
                                                 ("stcn", "st_cn"), ("stcs", "st_cs"), ("stck", "st_ck"), ("stco", "st_co"), ("stcso", "st_cso"),
                                                 ("stci", "st_ci"), ("stcsi", "st_csi"), ("stcwi", "st_cwi"), ("stcw", "st_cw"),
                                                 ("stnf", "st_nf"), ("stfl", "st_fl"), ("stfs", "st_fs"), ("stfw", "st_fw")] if s in d.columns})
    first = d.sort_values("at_bat_number").groupby(["game_pk", "inning_topbot"]).head(1)
    starters = set(zip(first["pitcher"], first["game_date"]))
    qp = p.groupby(PK).agg(bf=("pa", "size"), k=("is_k", "sum"), bb=("is_bb", "sum"),
                           outs=("outs", "sum"), wnum=("wnum", "sum"), wden=("wden", "sum"),
                           hr=("is_hr", "sum"), hbp=("is_hbp", "sum"), h=("is_hit", "sum"),
                           ld=("t_ld", "sum"), wbip=("w_bip", "sum"), wgb=("w_gb", "sum"), wld=("w_ld", "sum"), wfb=("w_fb", "sum"), wpu=("w_pu", "sum"))
    q = q.join(qp, how="left").fillna(0)
    for c in ["stn", "stw", "stg", "stp", "stbw", "stbg", "stbp", "stf", "std", "stbf", "stbd", "stnl", "stwl", "stws", "stbwl", "stbws", "stnb", "stgl", "stpl", "stgs", "stps", "stbgl", "stbpl", "stbgs", "stbps",
              "stcn", "stcs", "stck", "stco", "stcso", "stci", "stcsi", "stcwi", "stcw", "stnf", "stfl", "stfs", "stfw",
              "evfbs", "evfbn", "evlds", "evldn", "evgbs", "evgbn"]:
        if c not in q.columns:
            q[c] = 0.0
    q["gs"] = [1 if (key[0], key[1]) in starters else 0 for key in q.index]

    def pack(frame, fields):
        out = {}
        for (pid, date, hand, home), r in frame.iterrows():
            row = [days[str(date)[:10]], int(hand), int(home)]
            for f in fields[3:]:
                v = r[f]
                if f in ("evs", "evbk"):
                    row.append(v)
                else:
                    # xbsum / xssum are sums of per-ball probabilities: a day's bucket is well under 1, so int() would erase it
                    row.append(round(float(v), 2) if f in ("evsum", "wnum", "xnum", "dnum", "bssum", "fbv", "exts", "ss", "wbip", "wgb", "wld", "wfb", "wpu", "xbsum", "xssum", "dbsum", "dssum", "stw", "stg", "stp", "stbw", "stbg", "stbp", "stf", "std", "stbf", "stbd", "stwl", "stws", "stbwl", "stbws", "stgl", "stpl", "stgs", "stps", "stbgl", "stbpl", "stbgs", "stbps", "stcs", "stck", "stcso", "stcsi", "stcwi", "stcw", "stfl", "stfs", "stfw", "mixsum", "wbh", "evfbs", "evlds", "evgbs") else int(v))
            out.setdefault(int(pid), []).append(row)
        return out
    return pack(h, HITTER_DAY), pack(q, PITCHER_DAY)


# a pitcher's arsenal day by day, so the Stuff tab's table follows the card's dates and splits: one row per
# game day x batter hand x venue x pitch type (fields = meta.arsDayFields), in hist/ars-<key>.js — its own file, loaded
# only when the Stuff tab is open with a window or split (it's ~8 MB a season; days.js is big enough). Sums, so
# any set of rows adds up: graded pitches, the model's whiff / grounder / popup chances, velocity, break and spin
# (spin over spn pitches that had it), swings, whiffs, balls in play, grounders and popups that actually happened.
ARS_DAY = ["day", "hand", "home", "gs", "pt", "n", "w", "g", "p", "velo", "ivb", "hb", "spin", "spn", "sw", "wh", "bip", "gb", "pu",
           "f", "d", "nl", "wl", "ws",    # f / d: summed foul chances on contact and damage (wOBA on contact) — 2 Oct 2026; nl / wl / ws: swings graded, whiff chances with location and stuff-only on them
           "nb", "gl", "pl", "gs", "ps",  # balls in play graded, GB / PU chances with location and stuff-only on them
           "cn", "cs", "ck", "co", "cso", "stk", "osz",   # command (3 Oct 2026): pitches graded for it, their swing and strike chances, the ones out of the zone and their swing chances; strikes and out-of-zone swings that happened on them
           "nf", "fl", "fs", "fw",        # fouls with location (fw: and the batter's swing) (4 Oct 2026): pitches contacted, the foul chance where each crossed, the stuff-only one on the same contact
           "fo",                          # fouls that happened on the contacted pitches (6 Oct 2026)
           "cst"]                         # called strikes that happened (6 Oct 2026)


def write_arsenal_days(key: str, rows: dict, out_dir: Path | None = None) -> None:
    if not rows:
        return
    out = (out_dir or HERE / "hist") / f"ars-{key[4:] if key.startswith('mlb-') else key}.js"   # ars-2026.js, ars-aaa-2026.js
    out.parent.mkdir(exist_ok=True)
    out.write_text(f'window.DRAFT_ARS = window.DRAFT_ARS || {{}};\nwindow.DRAFT_ARS["{key}"] = '
                   + json.dumps({f"P{k}": v for k, v in rows.items()}, separators=(",", ":")) + ";\n")


def arsenal_daily(d: pd.DataFrame, days: dict) -> dict:
    if "st_n" not in d.columns or not d["st_n"].any():
        return {}
    first = d.sort_values("at_bat_number").groupby(["game_pk", "inning_topbot"]).head(1)
    starters = set(zip(first["pitcher"], first["game_date"]))
    x = d[d["st_n"] > 0]
    L = x["p_throws"].eq("L").to_numpy()
    num = lambda c: pd.to_numeric(x[c], errors="coerce").astype(float)
    spin = num("release_spin_rate")
    y = pd.DataFrame({"pitcher": x["pitcher"], "game_date": x["game_date"], "bhand": x["bhand"], "phome": x["phome"], "pt": x["pitch_type"],
                      "n": x["st_n"], "w": x["st_w"], "g": x["st_g"], "p": x["st_p"], "velo": num("release_speed"),
                      "ivb": 12 * num("pfx_z"), "hb": 12 * num("pfx_x") * np.where(L, 1, -1), "spin": spin.fillna(0), "spn": spin.notna().astype(int),
                      "sw": x["description"].isin(SWING).astype(int), "wh": x["description"].isin(WHIFF).astype(int),
                      "bip": x["bb_type"].isin(STUFF_BB.keys()).astype(int), "gb": x["bb_type"].eq("ground_ball").astype(int),
                      "pu": x["bb_type"].eq("popup").astype(int), "f": x["st_f"], "d": x["st_d"], "nl": x["st_nl"], "wl": x["st_wl"], "ws": x["st_ws"],
                      "nb": x["st_nb"], "gl": x["st_gl"], "pl": x["st_pl"], "gs": x["st_gs"], "ps": x["st_ps"],
                      "cn": x["st_cn"], "cs": x["st_cs"], "ck": x["st_ck"], "co": x["st_co"], "cso": x["st_cso"],
                      "stk": (x["type"].isin(["S", "X"]) & (x["st_cn"] > 0)).astype(int), "osz": (x["description"].isin(SWING) & (x["st_co"] > 0)).astype(int),
                      "nf": x["st_nf"], "fl": x["st_fl"], "fs": x["st_fs"], "fw": x["st_fw"],
                      "fo": (x["description"].eq("foul") & (x["st_nf"] > 0)).astype(int),
                      "cst": x["description"].eq("called_strike").astype(int)})
    q = y.groupby(["pitcher", "game_date", "bhand", "phome", "pt"]).sum(numeric_only=True)
    out = {}
    for (pid, date, hand, home, pt), r in q.iterrows():
        day = str(date)[:10]
        if day not in days:
            continue
        out.setdefault(int(pid), []).append([days[day], int(hand), int(home), 1 if (pid, date) in starters else 0, pt, int(r.n),
                                             round(float(r.w), 2), round(float(r.g), 2), round(float(r.p), 2), round(float(r.velo), 1),
                                             round(float(r.ivb), 1), round(float(r.hb), 1), int(round(r.spin)), int(r.spn),
                                             int(r.sw), int(r.wh), int(r.bip), int(r.gb), int(r.pu), round(float(r.f), 2), round(float(r.d), 2), int(r.nl), round(float(r.wl), 2), round(float(r.ws), 2),
                                             int(r.nb), round(float(r.gl), 2), round(float(r.pl), 2), round(float(r.gs), 2), round(float(r.ps), 2),
                                             int(r.cn), round(float(r.cs), 2), round(float(r.ck), 2), int(r.co), round(float(r.cso), 2), int(r.stk), int(r.osz),
                                             int(r.nf), round(float(r.fl), 2), round(float(r.fs), 2), round(float(r.fw), 2), int(r.fo), int(r.cst)])
    return out


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
            pos_games, ab, ip, era, er, games, season_team, sb, cs = {}, None, None, None, None, [], None, None, None
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
                            sb, cs = st.get("stolenBases"), st.get("caughtStealing")   # the card's Base Running section
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
                "ab": ab, "ip": ip, "era": era, "er": er, "games": games, "sb": sb, "cs": cs,
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


def babip_stats(rows: list) -> dict:
    """BABIP, xBABIP (the directional xBA's hits, less his home runs, over his non-HR balls in play), BABIP luck (his hits
    in play above expected, in wOBA points) and BIP reliance (% of his wOBA from hits in play — how far a BABIP swing
    moves him). Sean, 27 Sep 2026. Same arithmetic as babipFrom() in app.js, which re-derives them in a window."""
    ix = {f: HITTER_DAY.index(f) for f in ("h", "hr", "bip", "dbsum", "wnum", "wden", "wbh")}
    t = {f: sum(r[i] for r in rows if len(r) > i) for f, i in ix.items()}
    has_wbh = any(len(r) > ix["wbh"] for r in rows)
    out = {"babip": None, "xbabip": None, "bluck": None, "brel": None}
    den = t["bip"] - t["hr"]
    if den > 0:
        out["babip"] = round((t["h"] - t["hr"]) / den, 3)
        if t["dbsum"]:
            out["xbabip"] = round((t["dbsum"] - t["hr"]) / den, 3)
    if has_wbh and t["wden"] and t["wnum"]:
        nh = t["h"] - t["hr"]
        out["brel"] = round(100 * t["wbh"] / t["wnum"], 1)
        if t["dbsum"] and nh:
            out["bluck"] = round(1000 * (nh - (t["dbsum"] - t["hr"])) * (t["wbh"] / nh) / t["wden"], 1)
    return out


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
        m.update(babip_stats(rows_d))
        m["zmo"] = None if pd.isna(r["ZSwing_pct"]) or pd.isna(r["OSwing_pct"]) else round(float(r["ZSwing_pct"] - r["OSwing_pct"]), 1)
        m["k"], m["bb"] = (None if pd.isna(r.K_pct) else round(float(r.K_pct), 1)), (None if pd.isna(r.BB_pct) else round(float(r.BB_pct), 1))
        m["con"] = None if pd.isna(r["Whiff_pct"]) else round(100 - float(r["Whiff_pct"]), 1)
        for key, col in [("ev90", "EV90"), ("maxev", "maxEV"), ("hh", "HardHit_pct"), ("ss", "SweetSpot_pct"),
                         ("strk", "Strike_pct"), ("swing", "Swing_pct"), ("pullp", "Pull_pct"), ("oppo", "Oppo_pct"), ("cent", "Cent_pct"), ("npull", "NonPull_pct"), ("ld", "LD_pct"),
                         ("gb", "GB_pct"), ("pu", "PU_pct"), ("fb", "FB_pct")]:
            m[key] = None if pd.isna(r[col]) else round(float(r[col]), 1)
        own_bs = None if pd.isna(r["BatSpeed"]) else round(float(r["BatSpeed"]), 1)
        m["bs"] = round(float(bsp[pid]), 1) if pid in bsp.index and pd.notna(bsp[pid]) else own_bs
        m.update(baserunning(int(pid), info))
        mixev = []                                                 # [tracked balls, avg EV] by Mix bucket, MIX_COLS order (8 Oct 2026)
        for i in range(len(MIX_COLS)):
            n = int(r.get(f"MXN{i}", 0) or 0); mixev.append([n, round(float(r[f"MXS{i}"]) / n, 1)] if n else None)
        rows.append({
            "id": int(pid), "name": info["name"], "team": info["team"], "type": "H",
            "primary": info["primary"] or "DH", "pos": info["pos"], "milb": info.get("milb", {}), "bats": r["bats"],
            "age": info["age"], "pa": int(r.PA), "ab": int(info["ab"] or 0),
            "m": m,
            "ctx": {"wOBA": m["woba"], "OPS": None if pd.isna(r.OPS) else round(float(r.OPS), 3),
                    "K%": m["k"], "BB%": m["bb"],
                    "BBE": int(r.BBE), "BIP": int(r.BBT),
                    "mix": [int(r.get(c, 0) or 0) for c in MIX_COLS],         # balls by Mix bucket, MIX_COLS order
                    "mixev": mixev},                                           # and [tracked balls, avg EV] by bucket — the Mix tab's EV column
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
            out["stuff"] = sc
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
        for key, col in [("swstr", "SwStr_pct"), ("csw", "CSW_pct"), ("foul", "Foul_pct"), ("cstr", "CStr_pct"), ("zone", "Zone_pct"), ("osw", "OSwing_pct"), ("swing", "Swing_pct"),
                         ("zcon", "ZContact_pct"), ("fbv", "FBvelo"), ("ext", "Ext"), ("ev", "avg_EV"),
                         ("hh", "HardHit_pct"), ("brl", "Barrel_pct"), ("pu", "PU_pct"),
                         ("fstrk", "FStrk_pct"), ("b3strk", "B3Strk_pct"), ("s2whf", "S2Whf_pct"), ("s2sw", "S2Sw_pct"), ("s2zone", "S2Zone_pct"),
                         ("evfb", "EV_FB"), ("evld", "EV_LD"), ("evgb", "EV_GB")]:   # EV allowed by type (7 Oct 2026)
            m[key] = None if col not in r or pd.isna(r[col]) else round(float(r[col]), 1)
        sc = consts.get("stuff")
        stuff_rows = None
        m["xstrk"] = m["xswing"] = m["xosw"] = m["xzcon"] = m["xwhfa"] = None
        if sc and STUFF is not None and pid in STUFF["p"].index:
            s_ = STUFF["p"].loc[pid]
            m["swhf"], m["sbb"], m["stuff"] = stuff_grade_type(s_.n, s_.w, s_.g, s_.p, s_.bw, s_.bg, s_.bp, sc, consts["lgERA"],
                                                               s_.f, s_.dd, s_.bf, s_.bd)
            m["pwhf"], m["pbb"], m["pitch"], m["sloc"] = pitching_grade(m["swhf"], m["sbb"], s_, sc, consts["lgERA"])
            if "cn" in s_ and s_.cn >= 1:                 # command (3 Oct 2026): the rates his pitches, where he threw them, deserve —
                r1 = lambda v: None if pd.isna(v) else round(float(v), 1)   # the app's xBB% / Command+ / Pitching uBB% run on these
                m["xstrk"], m["xswing"] = r1(100 * s_.ck / s_.cn), r1(100 * s_.cs / s_.cn)
                m["xosw"] = r1(100 * s_.cso / s_.co) if s_.co else None
                m["xzcon"] = r1(100 * (1 - s_.cwi / s_.csi)) if s_.csi else None
                m["xwhfa"] = r1(100 * s_.cw / s_.cs) if s_.cs else None
            t_ = STUFF["t"].loc[pid] if pid in STUFF["t"].index.get_level_values(0) else None
            if t_ is not None:                             # his arsenal: one row per pitch type, most-thrown first
                stuff_rows = []
                for pt, x in t_.sort_values("n", ascending=False).iterrows():
                    wp, bp, sp = stuff_grade(x.n, x.w, x.g, x.p, sc, consts["lgERA"], x.f, x.dd)
                    r1 = lambda v, k=1: None if pd.isna(v) else round(float(v), k)
                    stuff_rows.append([pt, int(x.n), r1(x.velo), r1(x.ivb), r1(x.hb), None if pd.isna(x.spin) else int(round(x.spin)),
                                       r1(100 * x.w / x.n), r1(100 * x.g / x.n), r1(100 * x.p / x.n), wp, bp, sp,
                                       r1(100 * x.wh / x.sw) if x.sw else None, r1(100 * x.gb / x.bip) if x.bip else None,
                                       r1(100 * x.pu / x.bip) if x.bip else None, int(x.sw), int(x.bip),
                                       r1(100 * x.f / x.n), r1(x.dd / x.n, 3) if sc.get("lgD") is not None else None,
                                       *pitch_loc_row(x, wp, bp, sc, consts["lgERA"]), *command_row(x),
                                       r1(100 * x.fl / x.nf) if "nf" in x and x.nf >= 5 and sc.get("lgFL") is not None else None,
                                       r1(100 * x.fw / x.nf) if "nf" in x and x.nf >= 5 and sc.get("lgFW") is not None else None,
                                       r1(100 * x.fo / x.nf) if "nf" in x and x.nf >= 5 else None,
                                       r1(100 * x.cst / x.n), r1(100 * (x.ck - x.cs) / x.cn) if "cn" in x and x.cn >= 5 else None])
        else:
            m["swhf"] = m["sbb"] = m["stuff"] = m["sloc"] = m["pwhf"] = m["pbb"] = m["pitch"] = None
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
        d = add_stuff(d, lambda: (log(f"  stuff: loading the {STUFF_YEARS} seasons before to train on"), load_prior_seasons(SEASON))[1])
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
        "arsenalFields": STUFF_ARSENAL, "arsDayFields": ARS_DAY,
        "scoreNote": {
            "H": "xwOBA (Statcast expected wOBA from exit velocity and launch angle); the full season uses Savant's "
                 "published number, date windows and splits rebuild it from pitch-level data to within about .001",
            "blend": "wOBA percentile blend (Formula 1): 40.5% Barrel, 17.2% O-Contact, 16.9% Z-Contact, "
                     "11.6% Avg EV, 9.0% Z-minus-O Swing, 4.5% O-Swing (flipped), 0.2% Pull Air — re-ranked as a percentile",
            "P": "Rating: Whiff% 50 / xBB% 50 — the two Skills percentiles averaged (Sean, 6 Oct 2026)",
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
    try:
        write_arsenal_days(f"mlb-{SEASON}", {k: v for k, v in arsenal_daily(d, days).items() if k in pit_ids})
    except Exception as e:                                  # noqa: BLE001 — the per-day arsenal is a nicety; the table then stays season-long
        log(f"  !! arsenal by day skipped: {type(e).__name__}: {e}")
    (HERE / "days.js").write_text("window.DRAFT_DAYS = " + json.dumps(days_out, separators=(",", ":")) + ";\n")
    log(f"    data.js {(HERE / 'data.js').stat().st_size / 1e6:.1f} MB, days.js {(HERE / 'days.js').stat().st_size / 1e6:.1f} MB")
    log(f"OK  {len(hitters)} hitters, {len(pitchers)} pitchers -> data.js  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
