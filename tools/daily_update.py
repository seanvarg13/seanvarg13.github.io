"""Daily refresh: MLB + the four minor-league levels through yesterday, plus the fantasy, search-index and
career/season-by-season files (GitHub Pages, or Netlify without a GitHub token).

Publishes twice: once as soon as the MLB build is done (about 25 minutes in, so the site is current early),
then again after the minors, fantasy and history index finish.

Run by launchd every morning at 4:45 (install_schedule.sh), so the day's numbers are live by 5:30 — or by hand:
    python3 daily_update.py
Log: logs/daily.log (one file per day, 30 days kept). Off days are cheap: nothing new to download.
"""
import datetime as dt, glob, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
os.makedirs("logs", exist_ok=True)
today = dt.date.today()
log_path = os.path.join("logs", f"daily-{today}.log")
for old in glob.glob("logs/daily-*.log"):
    if time.time() - os.path.getmtime(old) > 30 * 86400:
        os.remove(old)
try:
    link = os.path.join("logs", "daily.log")
    if os.path.islink(link) or os.path.exists(link):
        os.remove(link)
    os.symlink(os.path.basename(log_path), link)
except OSError:
    pass
log = open(log_path, "a", buffering=1)


def say(msg):
    log.write(msg + "\n")
    print(msg, flush=True)


def run(*args):
    say("$ " + " ".join(args))
    p = subprocess.Popen([sys.executable, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in p.stdout:
        if "it/s]" not in line and "s/it]" not in line:     # skip pybaseball progress bars
            log.write(line)
    code = p.wait()
    if code:
        say(f"!! {args[0]} exited with code {code}")
    return code == 0


say(f"=== {dt.datetime.now():%F %T} start")
stay_awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])   # no idle sleep while this runs
end = str(today - dt.timedelta(days=1))
year = end[:4]


def publish():
    github = os.environ.get("GITHUB_TOKEN") or os.path.exists(os.path.expanduser("~/.github_token"))
    say(f"--- publishing to {'GitHub Pages' if github else 'Netlify'}")
    return run("publish_github.py" if github else "publish.py")


run("sync_tools.py")      # adopt any script edited on GitHub before anything is built with it
ok = run("build_data.py", "--end", end)
if ok:
    # the minor-league scrape takes another hour or more; put the MLB numbers on the site now rather than
    # leaving it a day stale all morning. Whatever the minors add is published again at the end.
    say(f"--- MLB data through {end} built; publishing it before the minors run")
    publish()
ok = (ok
      and run("build_milb.py", "aaa", year)
      and run("build_milb.py", "aa", "ap", "a", year)
      and run("build_fantasy.py")
      and run("build_history.py", "index")
      # season-by-season / career tables on every card (hist/career.js + hist/minors.js); needs the search
      # index above, since that is the player list it builds from
      and run("build_career.py"))
if ok:
    say(f"--- everything through {end} built")
    ok = publish()


def unscored_seasons():
    """Past MLB seasons whose file has no directional xBA yet (built before the dxBA / dxSLG models existed)."""
    out = []
    for y in range(2015, int(year)):
        path = os.path.join("hist", f"mlb-{y}.js")
        try:
            with open(path) as f:
                text = f.read()
        except OSError:
            continue
        if not re.search(r'"dxba":\s*0?\.\d', text):
            out.append(str(y))
    return out


# Once, then never again: rebuild any past season still missing directional xBA / xSLG, so the player page's
# expected stats are the site's own model in every year rather than Statcast's before 2026. About two hours for
# all of 2015-2025, so it runs after today's site is already published; a season that fails is simply tried again
# tomorrow. Once every season has them this finds nothing and costs nothing.
if ok:
    todo = unscored_seasons()
    if todo:
        say(f"--- rescoring {len(todo)} past season(s) with the directional xBA / xSLG models: {' '.join(todo)}")
        if run("build_history.py", *todo) and run("build_career.py"):
            say("--- rescore built; publishing it")
            ok = publish()
say(f"=== {dt.datetime.now():%F %T} {'done' if ok else 'FAILED'}")
sys.exit(0 if ok else 1)
