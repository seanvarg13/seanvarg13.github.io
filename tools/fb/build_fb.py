#!/usr/bin/env python3
"""Sean's football site: nflverse play-by-play -> football/data/*.js.

    python3 tools/fb/build_fb.py [--cache DIR] [--out football/data] [--seasons 2016-2026] [--current 2026]

Everything comes from nflverse's public releases (no keys): play-by-play, on-field participation (routes),
snap counts, player bios, Next Gen rushing, and nfldata's games list (head coaches). Downloads are cached in
--cache; a past season is fetched once, the current season every run.

Writes, per season, football/data/fb-<season>.js (every WR / TE / RB / QB who touched the ball or ran a
route: season line, shares, PPR points, expected points, weekly rows), football/data/teams.js (every
team-season's head coach, coordinator and RB usage) and football/data/index.js (the search index).

xFP: every target and every carry is priced by what a play like it scores in PPR on average - a gradient-
boosted model on the play's depth, field position, down and distance, side of the field and the player's
position - fitted on the other seasons (leave one season out, so a season's own results never price it) and
anchored so each season's league total of expected points equals its actual total.
"""
import argparse, json, os, sys, time, urllib.request
from collections import defaultdict
import numpy as np
import pandas as pd

R = "https://github.com/nflverse/nflverse-data/releases/download"
GAMES = "https://raw.githubusercontent.com/nfldata/nfldata/master/data/games.csv".replace("nfldata/nfldata", "nflverse/nfldata")
SKILL = {"WR", "TE", "RB", "FB", "QB"}


def fetch(url, path, fresh=False):
    if os.path.exists(path) and not fresh and os.path.getsize(path) > 0:
        return path
    tmp = path + ".part"
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "seans-site-football/1.0"})
            with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
                f.write(r.read())
            os.replace(tmp, path)
            return path
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** i)
        except Exception:
            time.sleep(2 ** i)
    return path if os.path.exists(path) else None


def load(cache, seasons, current):
    os.makedirs(cache, exist_ok=True)
    out = {"pbp": {}, "part": {}, "snaps": {}}
    for y in seasons:
        fresh = y == current
        p = fetch(f"{R}/pbp/play_by_play_{y}.parquet", f"{cache}/pbp_{y}.parquet", fresh)
        if p:
            out["pbp"][y] = pd.read_parquet(p)
        q = fetch(f"{R}/pbp_participation/pbp_participation_{y}.parquet", f"{cache}/part_{y}.parquet", fresh)
        if q:
            out["part"][y] = pd.read_parquet(q, columns=["nflverse_game_id", "play_id", "offense_players"])
        s = fetch(f"{R}/snap_counts/snap_counts_{y}.csv", f"{cache}/snaps_{y}.csv", fresh)
        if s:
            out["snaps"][y] = pd.read_csv(s)
    out["players"] = pd.read_parquet(fetch(f"{R}/players/players.parquet", f"{cache}/players.parquet", True))
    out["ngs_rush"] = pd.read_parquet(fetch(f"{R}/nextgen_stats/ngs_rushing.parquet", f"{cache}/ngs_rushing.parquet", True))
    out["games"] = pd.read_csv(fetch(GAMES, f"{cache}/games.csv", True), low_memory=False)
    return out


# ---------- play tables ----------
def reg(pbp):
    p = pbp[(pbp.season_type == "REG")].copy()
    p = p[p.play_type.isin(["pass", "run"]) | (p.two_point_attempt == 1)]
    return p


def targets(p, pos):
    t = p[(p.pass_attempt == 1) & p.receiver_player_id.notna() & (p.two_point_attempt != 1) & (p.play_type == "pass")].copy()
    t["pid"] = t.receiver_player_id
    t["pos"] = t.pid.map(pos).fillna("WR")
    td = (t.pass_touchdown == 1) & (t.td_player_id == t.pid)
    t["y"] = t.complete_pass.fillna(0) * (1 + t.receiving_yards.fillna(0) / 10) + 6 * td
    t["td"] = td.astype(float)
    return t


def carries(p, pos):
    c = p[(p.rush_attempt == 1) & p.rusher_player_id.notna() & (p.two_point_attempt != 1) & (p.qb_kneel != 1)].copy()
    c["pid"] = c.rusher_player_id
    c["pos"] = c.pid.map(pos).fillna("RB")
    td = (c.rush_touchdown == 1) & (c.td_player_id == c.pid)
    c["y"] = c.rushing_yards.fillna(0) / 10 + 6 * td
    c["td"] = td.astype(float)
    return c


POS_CODE = {"WR": 0, "TE": 1, "RB": 2, "FB": 2, "QB": 3}
LOC = {"left": 0, "middle": 1, "right": 2}
GAP = {"end": 0, "tackle": 1, "guard": 2}


def tfeat(t):
    return np.column_stack([
        t.air_yards.clip(-10, 60).fillna(0), t.yardline_100.fillna(50), t.down.fillna(1), t.ydstogo.clip(0, 30).fillna(10),
        t.pass_location.map(LOC).fillna(1), t.shotgun.fillna(0), t.pos.map(POS_CODE).fillna(0), t.air_yards.isna().astype(int),
    ])


def cfeat(c):
    return np.column_stack([
        c.yardline_100.fillna(50), c.down.fillna(1), c.ydstogo.clip(0, 30).fillna(10), c.run_location.map(LOC).fillna(1),
        c.run_gap.map(GAP).fillna(3), c.shotgun.fillna(0), c.pos.map(POS_CODE).fillna(2), c.qb_scramble.fillna(0),
    ])


def fit_price(frames, featf, label, current, col="y"):
    """Leave-one-season-out gradient boosting; returns {season: predicted y per row}, anchored per season."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    seasons = sorted(frames)
    X = {y: featf(frames[y]) for y in seasons}
    Y = {y: frames[y][col].to_numpy() for y in seasons}
    hist = [y for y in seasons if y != current]          # finished seasons only as training data
    out = {}
    for y in seasons:
        tr = [s for s in hist if s != y]
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=200, random_state=7)
        m.fit(np.vstack([X[s] for s in tr]), np.concatenate([Y[s] for s in tr]))
        pred = np.clip(m.predict(X[y]), 0, None)
        k = Y[y].sum() / pred.sum() if pred.sum() else 1.0   # the season's own scoring level
        out[y] = pred * k
        print(f"  {label} {y}: {len(pred)} plays, anchor {k:.3f}", flush=True)
    return out


# ---------- per-season player build ----------
def r1(v):
    return None if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), 1)


def build_season(y, d, P, pos, xt, xc, ngs, tt=None, tc=None):
    pbp = d["pbp"][y]
    p = reg(pbp)
    p = p[p.week <= 18]
    t = targets(p, pos); t["x"] = xt; t["xtd"] = tt if tt is not None else 0.0
    c = carries(p, pos); c["x"] = xc; c["xtd"] = tc if tc is not None else 0.0
    # dropbacks and plays by team-week (for shares and the route estimate)
    plays = p[(p.play_type.isin(["pass", "run"])) & (p.two_point_attempt != 1)]
    db = plays[plays.qb_dropback == 1]
    tw_db = db.groupby(["posteam", "week"]).size()
    tw_tgt = t.groupby(["posteam", "week"]).size()
    tw_ay = t.groupby(["posteam", "week"]).air_yards.sum()
    tw_car = c.groupby(["posteam", "week"]).size()
    rz = t.yardline_100 <= 20
    ez = (t.air_yards.fillna(-99) >= t.yardline_100)
    # snaps: pfr id -> gsis
    pfr2g = dict(zip(P.pfr_id, P.gsis_id))
    sn = d["snaps"].get(y)
    snaps = {}
    if sn is not None:
        sn = sn[(sn.game_type == "REG") & (sn.week <= 18)].copy()
        sn["pid"] = sn.pfr_player_id.map(pfr2g)
        sn = sn[sn.pid.notna() & (sn.offense_snaps > 0)]
        for r in sn.itertuples():
            snaps[(r.pid, r.week)] = (r.offense_snaps, r.offense_pct, r.team, r.opponent)
    sweeks = defaultdict(set)
    for (j, w) in snaps:
        sweeks[j].add(w)
    # routes: on the field for a dropback (participation), else snap share x team dropbacks
    routes = defaultdict(float)
    est = sn is not None and y not in d["part"]
    if y in d["part"]:
        part = d["part"][y]
        keys = set(zip(db.game_id, db.play_id))
        pp = part[[k in keys for k in zip(part.nflverse_game_id, part.play_id)]]
        wk = dict(zip(zip(db.game_id, db.play_id), db.week))
        for g, pl, ids in zip(pp.nflverse_game_id, pp.play_id, pp.offense_players):
            if not isinstance(ids, str):
                continue
            w = wk[(g, pl)]
            for i in ids.split(";"):
                if pos.get(i) in ("WR", "TE", "RB", "FB"):
                    routes[(i, w)] += 1
    elif sn is not None:
        for (pid, w), (s, pct, tm, opp) in snaps.items():
            if pos.get(pid) in ("WR", "TE", "RB", "FB"):
                routes[(pid, w)] = pct * tw_db.get((tm, w), 0)
    # QB passing
    pas = plays[(plays.qb_dropback == 1) & plays.passer_player_id.notna()]
    # fantasy points by player-week
    fp = defaultdict(float)
    for r in t.itertuples():
        fp[(r.pid, r.week)] += r.y
    for r in c.itertuples():
        fp[(r.pid, r.week)] += r.y
    pa = p[(p.pass_attempt == 1) & p.passer_player_id.notna() & (p.two_point_attempt != 1)]
    for r in pa.itertuples():
        fp[(r.passer_player_id, r.week)] += (r.passing_yards if r.passing_yards == r.passing_yards else 0) / 25 + 4 * (r.pass_touchdown == 1) - 2 * (r.interception == 1)
    fl = plays[(plays.fumble_lost == 1) & plays.fumbled_1_player_id.notna()]   # offensive snaps only: nflverse charges no fumble on a return
    for r in fl.itertuples():
        fp[(r.fumbled_1_player_id, r.week)] -= 2
    # kneel-downs count their lost yards (as nflverse's fantasy points do), and so do kick and punt return touchdowns
    kn = p[(p.qb_kneel == 1) & p.rusher_player_id.notna()]
    for r in kn.itertuples():
        fp[(r.rusher_player_id, r.week)] += (r.rushing_yards if r.rushing_yards == r.rushing_yards else 0) / 10
    st = pbp[(pbp.season_type == "REG") & (pbp.week <= 18) & pbp.play_type.isin(["kickoff", "punt"]) & (pbp.touchdown == 1) & pbp.td_player_id.notna()]   # whoever scored: returns, and a recovered kick, as nflverse counts them
    for r in st.itertuples():
        fp[(r.td_player_id, r.week)] += 6
    tp = p[(p.two_point_attempt == 1) & (p.two_point_conv_result == "success")]
    for r in tp.itertuples():
        for i in (r.rusher_player_id, r.receiver_player_id, r.passer_player_id):
            if isinstance(i, str):
                fp[(i, r.week)] += 2
    # who's in: skill players with a target, carry, dropback or route
    ids = set(t.pid) | set(c.pid) | set(pas.passer_player_id) | {k[0] for k in routes}
    ids = {i for i in ids if pos.get(i) in SKILL}
    T = t.groupby("pid"); C = c.groupby("pid")
    tg = {k: v for k, v in T}; cg = {k: v for k, v in C}
    pg = {k: v for k, v in pas.groupby("passer_player_id")}
    ngs_s = ngs[(ngs.season == y) & (ngs.week == 0) & (ngs.season_type == "REG")].set_index("player_gsis_id") if ngs is not None else None
    bio = P.set_index("gsis_id")
    # week-by-week sums for the game logs, once for everyone
    tq = t.assign(tdf=((t.pass_touchdown == 1) & (t.td_player_id == t.pid)).astype(int), ryd_=t.receiving_yards.fillna(0))
    cq = c.assign(tdf=((c.rush_touchdown == 1) & (c.td_player_id == c.pid)).astype(int), ryd_=c.rushing_yards.fillna(0))
    TW = {k: v for k, v in zip(tq.groupby(["pid", "week"]).groups.keys(), tq.groupby(["pid", "week"]).agg(n=("y", "size"), rec=("complete_pass", "sum"), yd=("ryd_", "sum"), td=("tdf", "sum"), x=("x", "sum"), opp=("defteam", "first")).itertuples(index=False))}
    CW = {k: v for k, v in zip(cq.groupby(["pid", "week"]).groups.keys(), cq.groupby(["pid", "week"]).agg(n=("y", "size"), yd=("ryd_", "sum"), td=("tdf", "sum"), x=("x", "sum"), opp=("defteam", "first")).itertuples(index=False))}
    fweeks = defaultdict(set)   # a week with points but no offensive snap (a kick-return touchdown) still gets its row
    for (j, w), v in fp.items():
        if v:
            fweeks[j].add(w)
    out = []
    for i in ids:
        ti = tg.get(i, t.iloc[0:0]); ci = cg.get(i, c.iloc[0:0]); qi = pg.get(i, pas.iloc[0:0])
        weeks = sorted(sweeks.get(i, set()) | set(ti.week) | set(ci.week) | set(qi.week) | fweeks.get(i, set()))
        if not weeks:
            continue
        # his team each week: snaps' team, else the play's posteam
        tmw = {}
        for w in weeks:
            s = snaps.get((i, w))
            if s:
                tmw[w] = s[2]
        for df in (ti, ci, qi):
            for w, tm in zip(df.week, df.posteam):
                tmw.setdefault(w, tm)
        tms = [tmw[w] for w in weeks if w in tmw]
        team = max(set(tms), key=tms.count) if tms else None
        tl = list(dict.fromkeys(tms))
        sh = lambda ser: float(sum(ser.get((tmw[w], w), 0) for w in weeks if w in tmw))
        rts = sum(routes.get((i, w), 0) for w in weeks)
        comp = ti[ti.complete_pass == 1]
        xy = comp[comp.xyac_mean_yardage.notna()]
        bp = bio.loc[i] if i in bio.index else None
        age = None
        if bp is not None and isinstance(bp.birth_date, str):
            try:
                b = pd.Timestamp(bp.birth_date); age = round((pd.Timestamp(f"{y}-09-01") - b).days / 365.25, 1)
            except Exception:
                pass
        ps = pos.get(i)
        wrows = []
        for w in weeks:
            a_ = TW.get((i, w)); b_ = CW.get((i, w)); s = snaps.get((i, w))
            opp = s[3] if s else (a_.opp if a_ else b_.opp if b_ else None)
            wrows.append([int(w), opp, round(s[1] * 100) if s else None, round(routes.get((i, w), 0), 1),
                          int(a_.n) if a_ else 0, int(a_.rec) if a_ else 0, int(a_.yd) if a_ else 0, int(a_.td) if a_ else 0,
                          int(b_.n) if b_ else 0, int(b_.yd) if b_ else 0, int(b_.td) if b_ else 0,
                          round(fp.get((i, w), 0), 1), round(float((a_.x if a_ else 0) + (b_.x if b_ else 0)), 1), tmw.get(w)])
        ng = ngs_s.loc[i] if ngs_s is not None and i in ngs_s.index else None
        if isinstance(ng, pd.DataFrame):
            ng = ng.iloc[0]
        rec = dict(
            id=i, n=(bp.display_name if bp is not None else i), pos=ps, tm=team, tms=tl, age=age, g=len(weeks),
            snp=int(sum(snaps[(i, w)][0] for w in weeks if (i, w) in snaps)),
            snpct=r1(100 * np.mean([snaps[(i, w)][1] for w in weeks if (i, w) in snaps])) if any((i, w) in snaps for w in weeks) else None,
            rts=round(rts), est=1 if est else 0,
            tgt=len(ti), rec=int(ti.complete_pass.sum()), ryd=int(ti.receiving_yards.fillna(0).sum()),
            rtd=int(((ti.pass_touchdown == 1) & (ti.td_player_id == i)).sum()), ay=int(ti.air_yards.fillna(0).sum()),
            rzt=int(rz[ti.index].sum()) if len(ti) else 0, ezt=int(ez[ti.index].sum()) if len(ti) else 0,
            xc=r1(ti.cp.sum()), xcn=int(ti.cp.notna().sum()), cc=int(ti[ti.cp.notna()].complete_pass.sum()),
            yac=int(comp.yards_after_catch.fillna(0).sum()), xyac=r1(xy.xyac_mean_yardage.sum()), yacn=len(xy), yacs=int(xy.yards_after_catch.fillna(0).sum()),
            car=len(ci), ruyd=int(ci.rushing_yards.fillna(0).sum()), rutd=int(((ci.rush_touchdown == 1) & (ci.td_player_id == i)).sum()),
            glc=int((ci.yardline_100 <= 5).sum()), rzc=int((ci.yardline_100 <= 20).sum()),
            tmt=round(sh(tw_tgt)), tmay=round(sh(tw_ay)), tmc=round(sh(tw_car)), tmdb=round(sh(tw_db)),
            fp=round(sum(fp.get((i, w), 0) for w in weeks), 1),
            xr=round(float(ti.x.sum()), 1), xu=round(float(ci.x.sum()), 1),
            frt=round(float(ti.y.sum()), 1), fru=round(float(ci.y.sum()), 1),
            xtr=round(float(ti.xtd.sum()), 2), xtu=round(float(ci.xtd.sum()), 2),
            ryoe=r1(ng.rush_yards_over_expected) if ng is not None else None, ngsatt=int(ng.rush_attempts) if ng is not None else None,
            w=wrows,
        )
        if len(qi) or ps == "QB":
            rec.update(db=len(qi), att=int(qi.pass_attempt.sum()), cmp=int(qi.complete_pass.sum()), pyd=int(qi.passing_yards.fillna(0).sum()),
                       ptd=int(qi.pass_touchdown.sum()), int_=int(qi.interception.sum()), sk=int(qi.sack.sum()),
                       epa=r1(qi.qb_epa.sum()), cpoe=r1(qi.cpoe.mean()) if qi.cpoe.notna().any() else None, scr=int(ci.qb_scramble.sum()) if len(ci) else 0)
        out.append(rec)
    return out, t, c, plays, snaps


# ---------- team-seasons: coaches and RB usage ----------
def team_seasons(y, games, players, t, c, snaps, pos, staff):
    g = games[(games.season == y) & (games.game_type == "REG")]
    hc = defaultdict(list)
    ab = {"OAK": "LV", "SD": "LAC", "STL": "LA"}   # the games list keeps the old codes; play-by-play uses today's
    for r in g.itertuples():
        hc[ab.get(r.home_team, r.home_team)].append(r.home_coach); hc[ab.get(r.away_team, r.away_team)].append(r.away_coach)
    byid = {p["id"]: p for p in players}
    out = []
    for tm in sorted(hc):
        coaches = [x for x in hc[tm] if isinstance(x, str)]
        head = max(set(coaches), key=coaches.count) if coaches else None
        rbs = [p for p in players if p["pos"] in ("RB", "FB") and tm in (p["tms"] or [])]
        # RB touches on this team (a traded back counts only his weeks here)
        tc = c[(c.posteam == tm) & c.pid.map(lambda i: pos.get(i) in ("RB", "FB"))]
        tt = t[(t.posteam == tm) & t.pid.map(lambda i: pos.get(i) in ("RB", "FB"))]
        car = tc.groupby("pid").size(); tgt = tt.groupby("pid").size()
        opp = car.add(tgt, fill_value=0).sort_values(ascending=False)
        if not len(opp):
            continue
        rows = []
        for pid in opp.index[:4]:
            wk = sorted(set(tc[tc.pid == pid].week) | set(tt[tt.pid == pid].week) | {w for (j, w) in snaps if j == pid and snaps[(j, w)][2] == tm})
            pct = [snaps[(pid, w)][1] for w in wk if (pid, w) in snaps and snaps[(pid, w)][2] == tm]
            fpt = float(tc[tc.pid == pid].y.sum() + tt[tt.pid == pid].y.sum())
            xpt = float(tc[tc.pid == pid].x.sum() + tt[tt.pid == pid].x.sum())
            rows.append(dict(id=pid, n=byid[pid]["n"] if pid in byid else pid, car=int(car.get(pid, 0)), tgt=int(tgt.get(pid, 0)),
                             g=len(wk), snp=r1(100 * np.mean(pct)) if pct else None, fp=round(fpt, 1), xfp=round(xpt, 1), wk=wk))
        rb1 = rows[0]
        w1 = set(rb1["wk"])
        hc1 = tc[tc.week.isin(w1)]; ht1 = tt[tt.week.isin(w1)]
        sh = hc1.groupby("pid").size() / max(len(hc1), 1)
        gl = tc[tc.yardline_100 <= 5]; gl1 = gl[gl.week.isin(w1)]
        team_tg = t[t.posteam == tm]
        rec = dict(
            tm=tm, hc=head, oc=(staff.get(f"{y}:{tm}") or {}).get("oc"), pc=(staff.get(f"{y}:{tm}") or {}).get("pc"),
            rbcar=len(tc), rbtgt=len(tt), tmtgt=len(team_tg), tmcar=int(len(c[c.posteam == tm])),
            rb1g=len(w1), rb1car=round(100 * float(sh.get(rb1["id"], 0)), 1),
            rb1opp=round(100 * (len(hc1[hc1.pid == rb1["id"]]) + len(ht1[ht1.pid == rb1["id"]])) / max(len(hc1) + len(ht1), 1), 1),
            rb1gl=round(100 * len(gl1[gl1.pid == rb1["id"]]) / len(gl1), 1) if len(gl1) else None, glc=len(gl1),
            eff=round(1 / float((sh ** 2).sum()), 2) if len(sh) else None,
            rb2car=round(100 * float(sh.get(rows[1]["id"], 0)), 1) if len(rows) > 1 else None,
            rbs=[{k: v for k, v in r.items() if k != "wk"} for r in rows],
        )
        out.append(rec)
    return out


def jsdump(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=lambda o: None)


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=".cache/fb")
    ap.add_argument("--out", default="football/data")
    ap.add_argument("--seasons", default="2016-2026")
    ap.add_argument("--current", type=int, default=2026)
    ap.add_argument("--write", default=None, help="only write these seasons (comma list); the model still trains on all")
    a = ap.parse_args()
    lo, hi = map(int, a.seasons.split("-"))
    seasons = list(range(lo, hi + 1))
    d = load(a.cache, seasons, a.current)
    P = d["players"]
    pos = dict(zip(P.gsis_id, P.position))
    staff_path = os.path.join(a.out, "staff.json")
    staff = json.load(open(staff_path)) if os.path.exists(staff_path) else {}
    print("pricing targets and carries", flush=True)
    T, C = {}, {}
    for y in seasons:
        if y not in d["pbp"]:
            continue
        p = reg(d["pbp"][y]); p = p[p.week <= 18]
        T[y] = targets(p, pos); C[y] = carries(p, pos)
    xt = fit_price(T, tfeat, "targets", a.current); xc = fit_price(C, cfeat, "carries", a.current)
    # expected touchdowns, so the FPOE splits into touchdown luck and the rest
    tt = fit_price(T, tfeat, "target TDs", a.current, "td"); tc = fit_price(C, cfeat, "carry TDs", a.current, "td")
    write = set(map(int, a.write.split(","))) if a.write else set(T)
    os.makedirs(a.out, exist_ok=True)
    index = {}
    idx_path = os.path.join(a.out, "index.js")
    teams_all = {}
    career = defaultdict(dict)
    for y in sorted(T):
        players, t, c, plays, snaps = build_season(y, d, P, pos, xt[y], xc[y], d["ngs_rush"], tt[y], tc[y])
        tsea = team_seasons(y, d["games"], players, t, c, snaps, pos, staff)
        teams_all[y] = tsea
        # position ranks by PPR points and by expected points, for the season table
        for key in ("fp", "xfp"):
            byp = defaultdict(list)
            for pl in players:
                v = pl["fp"] if key == "fp" else pl["xr"] + pl["xu"] + (pl.get("pyd", 0) / 25 + 4 * pl.get("ptd", 0) - 2 * pl.get("int_", 0) if pl["pos"] == "QB" else 0)
                byp[pl["pos"]].append((v, pl["id"]))
            for ps, lst in byp.items():
                for k, (v, i) in enumerate(sorted(lst, reverse=True)):
                    career[i].setdefault(y, {})["rk" if key == "fp" else "xrk"] = k + 1
        for pl in players:
            e = index.setdefault(pl["id"], {"n": pl["n"], "pos": pl["pos"], "s": []})
            e["s"].append(y); e["tm"] = pl["tm"]
            c_ = career[pl["id"]].setdefault(y, {})
            c_.update({k: pl.get(k) for k in ("tm", "tms", "age", "g", "snpct", "rts", "tgt", "rec", "ryd", "rtd", "ay", "car", "ruyd", "rutd", "tmt", "tmc", "tmdb",
                                               "fp", "xr", "xu", "xtr", "xtu", "att", "cmp", "pyd", "ptd", "int_", "epa", "cpoe", "db", "xc", "xcn", "cc")})
        if y in write:
            meta = dict(season=y, through=int(t.week.max()) if len(t) else None, built=time.strftime("%Y-%m-%d %H:%M"),
                        wfields=["wk", "opp", "snp", "rts", "tgt", "rec", "ryd", "rtd", "car", "ruyd", "rutd", "fp", "xfp", "tm"],
                        estRoutes=y not in d["part"])
            body = jsdump(clean({"meta": meta, "players": players}))
            with open(os.path.join(a.out, f"fb-{y}.js"), "w") as f:
                f.write(f"window.FB=window.FB||{{}};window.FB[{y}]={body};\n")
            print(f"  wrote fb-{y}.js: {len(players)} players, {len(body) // 1024} KB", flush=True)
    # bios for the index
    bio = P.set_index("gsis_id")
    for i, e in index.items():
        if i in bio.index:
            b = bio.loc[i]
            e.update(ht=b.height if b.height == b.height else None, wt=b.weight if b.weight == b.weight else None,
                     col=b.college_name if isinstance(b.college_name, str) else None,
                     dr=[int(b.draft_year), int(b.draft_round), int(b.draft_pick)] if b.draft_year == b.draft_year and b.draft_round == b.draft_round else None,
                     img=b.headshot if isinstance(b.headshot, str) else None, bd=b.birth_date if isinstance(b.birth_date, str) else None)
    with open(idx_path, "w") as f:
        f.write("window.FB_INDEX=" + jsdump(clean(index)) + ";\n")
    with open(os.path.join(a.out, "career.js"), "w") as f:
        f.write("window.FB_CAREER=" + jsdump(clean({i: {str(y): v for y, v in d_.items()} for i, d_ in career.items()})) + ";\n")
    with open(os.path.join(a.out, "teams.js"), "w") as f:
        f.write("window.FB_TEAMS=" + jsdump(clean({str(k): v for k, v in teams_all.items()})) + ";\n")
    print(f"index {len(index)} players; teams {sum(len(v) for v in teams_all.values())} team-seasons")


if __name__ == "__main__":
    main()
