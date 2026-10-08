"""The daily update, run by GitHub Actions (.github/workflows/daily.yml) so the site refreshes whether or not the Mac
is on. The same steps as daily_update.py, in the same order, with the same scripts from tools/:

    build_data.py --end <yesterday>  -> publish (the day's MLB numbers, early)
    build_milb.py aaa / aa ap a, build_fantasy.py, build_history.py index, build_career.py -> publish again

The scripts write next to themselves, so they are copied to the repo root first and run there; the models they
load live in ../model-workspace (downloaded from the "models" release by the workflow). Publishing here is a plain
commit on top of whatever main is by then — never a force-push — so an edit merged while the build ran survives:
the build's outputs are set aside, main is fetched fresh, the outputs are put back, the page is re-stamped, and
the commit is pushed (retried if main moved again).

    python3 tools/cloud_daily.py                      # the whole day, as the schedule runs it
    python3 tools/cloud_daily.py --steps mlb          # just the MLB build + publish
    python3 tools/cloud_daily.py --end 2026-04-01 --dry   # build a short season, don't publish (testing)
    python3 tools/cloud_daily.py --rescore 2025 2024  # rebuild past seasons (directional xBA / xSLG), then publish
"""
import argparse, datetime as dt, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
os.chdir(ROOT)
SCRIPTS = ["build_data.py", "build_history.py", "build_milb.py", "build_fantasy.py", "build_career.py", "build_trends.py", "build_similar.py"]
# what the site serves: the same list publish.py stamps, plus every hist/ file
TOP = ["index.html", "app.js", "styles.css", "themes.js", "defaults.js", "data.js", "days.js", "fantasy.js", "manifest.json",
       "icons/icon-32.png", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png"]
OUTPUTS = ["data.js", "days.js", "fantasy.js"]            # plus hist/*.js — what a build writes


def say(msg):
    print(msg, flush=True)


# The stale-checkout guard (Sean, 8 Oct 2026: "add the guard to the cloud build"). A run's checkout is main as it was when the run
# began, and a run can take hours (a rescore, the minors), so a script merged to main meanwhile used to be ignored: the run built with
# the old copy and published files the new code had changed (4 Oct: data.js with the old card layout; 7-8 Oct: career.js without the
# positions or FanGraphs' numbers). Now every step first adopts tools/ as main carries it, and a publish re-runs any step of this run
# whose script (or a script it imports) changed on main after the step ran, before it pushes.
DEPS = {"build_history.py": ["build_data.py"], "build_milb.py": ["build_data.py", "build_history.py"]}
RAN = []                                                 # [(script, args, {script: sha1 of the copy it ran with})] since the last publish


def text_sha(b):
    return hashlib.sha1(b).hexdigest()


def adopt_main_tools():
    """Bring the build scripts up to main's copies. Returns the ones that changed. A script that doesn't compile is left alone."""
    if subprocess.run(["git", "fetch", "-q", "origin", "main"], capture_output=True).returncode:
        say("    (guard: couldn't fetch main — running with the scripts this run has)")
        return []
    changed = []
    for s in SCRIPTS:
        r = subprocess.run(["git", "show", f"origin/main:tools/{s}"], capture_output=True)
        if r.returncode or not r.stdout:
            continue
        here = os.path.join(ROOT, s)
        if os.path.exists(here) and open(here, "rb").read() == r.stdout:
            continue
        try:
            compile(r.stdout, s, "exec")
        except SyntaxError as e:
            say(f"!! guard: main's {s} doesn't compile ({e}) — keeping this run's copy")
            continue
        for dst in (here, os.path.join(TOOLS, s)):
            with open(dst, "wb") as f:
                f.write(r.stdout)
        changed.append(s)
    if changed:
        say("    guard: main moved on — now using its " + ", ".join(changed))
    return changed


def script_shas(script):
    return {s: text_sha(open(os.path.join(ROOT, s), "rb").read()) for s in [script, *DEPS.get(script, [])] if os.path.exists(os.path.join(ROOT, s))}


def run(*args):
    if args and args[0] in SCRIPTS:
        adopt_main_tools()
        RAN.append((args[0], args, script_shas(args[0])))
    return _run(*args)


def _run(*args):
    say("$ " + " ".join(args))
    p = subprocess.Popen([sys.executable, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in p.stdout:
        if "it/s]" not in line and "s/it]" not in line:     # skip pybaseball progress bars
            print(line, end="", flush=True)
    code = p.wait()
    if code:
        say(f"!! {args[0]} exited with code {code}")
    return code == 0


def git(*args, check=True, capture=False):
    r = subprocess.run(["git", *args], check=check, text=True, capture_output=capture)
    return r.stdout.strip() if capture else r.returncode


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def restamp():
    """publish.stamp(), on the repo root: strip the last publish's stamps back to the template, then version every
    file reference with ?v=<sha1> and write the DRAFT_BUILD map and build.json exactly as the Mac's publisher does."""
    html = open("index.html").read()
    html = re.sub(r'<script>window\.DRAFT_BUILD=.*?</script>\n?', "", html)
    html = re.sub(r'\?v=[0-9a-f]{10}"', '"', html)
    with open("index.html", "w") as f:
        f.write(html)
    wanted = [r for r in TOP if os.path.exists(r)] + sorted(f"hist/{n}" for n in os.listdir("hist") if n.endswith(".js"))
    ver = {rel: sha1(rel)[:10] for rel in wanted}
    build = hashlib.sha1("".join(f"{k}:{v}" for k, v in sorted(ver.items())).encode()).hexdigest()[:10]
    for rel, v in ver.items():
        for attr in ('src="', 'href="'):
            html = html.replace(f'{attr}{rel}"', f'{attr}{rel}?v={v}"')
    tag = ("<script>window.DRAFT_BUILD=" + json.dumps(ver, separators=(",", ":"))
           + ';window.DRAFT_BUILD_ID="' + build + '";</script>\n')
    html = html.replace('<script src="defaults.js', tag + '<script src="defaults.js', 1)
    with open("index.html", "w") as f:
        f.write(html)
    with open("build.json", "w") as f:
        json.dump({"build": build, "at": dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M")}, f)
    return build


START = time.time()


def outputs():
    # only what this run wrote (30 Sep 2026): every other file is the checkout's copy from when the run began, and putting it
    # back on top of main would undo another run that rebuilt it meanwhile (a retrain's rescore beside a minors rebuild)
    return [p for p in OUTPUTS + sorted(glob.glob("hist/*.js")) if os.path.exists(p) and os.path.getmtime(p) >= START - 1]


def publish(label, end, dry):
    """Commit the build's outputs on top of main as it is now, and push. Returns True when main has them."""
    if dry:
        say(f"--- (dry run) would publish: {label}; build id {restamp()}")
        return True
    # the guard: re-run, with main's scripts, every step of this run built with a copy main has since replaced (twice at most —
    # a merge landing during the re-run gets one more pass; the third publishes what it has and says so)
    for rnd in range(3):
        adopt_main_tools()
        stale = [r for r in RAN if script_shas(r[0]) != r[2]]
        if not stale:
            break
        if rnd == 2:
            say("!! guard: the scripts keep changing on main — publishing this build; the next run catches up")
            break
        say(f"--- guard: {len(stale)} step(s) built with scripts main has replaced — re-running them before publishing")
        first = RAN.index(stale[0])                          # everything after the first stale step read its output, so redo from there
        redo = RAN[first:]
        del RAN[first:]
        for script, args, _ in redo:
            if not run(*args):
                say("!! guard: a re-run failed — not publishing")
                return False
    RAN.clear()
    keep = tempfile.mkdtemp()
    for rel in outputs():
        os.makedirs(os.path.join(keep, os.path.dirname(rel)), exist_ok=True)
        shutil.copy2(rel, os.path.join(keep, rel))
    for attempt in range(5):
        git("fetch", "-q", "origin", "main")
        git("reset", "-q", "--hard", "origin/main")            # untracked files (the staged scripts, .cache) stay
        for root, _, files in os.walk(keep):
            for n in files:
                src = os.path.join(root, n)
                dst = os.path.relpath(src, keep)
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                shutil.copy2(src, dst)
        build = restamp()
        git("add", "index.html", "build.json", *[r for r in OUTPUTS if os.path.exists(r)], "hist")
        if not git("status", "--porcelain", "--untracked-files=no", capture=True):
            say("--- nothing changed since the last publish")
            return True
        n = len(git("diff", "--cached", "--name-only", capture=True).splitlines())
        git("commit", "-q", "-m", f"site through {end} ({n} files changed) — {label}, GitHub Actions")
        if git("push", "-q", "origin", "HEAD:main", check=False) == 0:
            say(f"--- published {label} (build {build})")
            pages_build()
            return True
        say(f"    push rejected (main moved on) — retrying ({attempt + 1}/5)")
        time.sleep(5 + 10 * attempt)
    say("!! could not push after 5 tries")
    return False


def pages_build():
    """Ask Pages to build now: a push made with the workflow's own token may not start one by itself."""
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not tok or not repo:
        return
    try:
        import urllib.request
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/pages/builds", method="POST",
                                     headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"})
        urllib.request.urlopen(req, timeout=30).read()
        say("    Pages build requested")
    except Exception as e:                                 # noqa: BLE001 — Pages usually builds on the push anyway
        say(f"    (Pages build request: {type(e).__name__}: {e})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", help="last day to build (default: yesterday, New York time)")
    ap.add_argument("--steps", default="mlb,minors", help="mlb, minors, or both (comma-separated)")
    ap.add_argument("--rescore", nargs="*", help="rebuild these past seasons instead of the daily steps")
    ap.add_argument("--dry", action="store_true", help="build but don't publish")
    a = ap.parse_args()
    end = a.end or str(dt.datetime.now(ZoneInfo("America/New_York")).date() - dt.timedelta(days=1))
    year = end[:4]
    for s in SCRIPTS:                                        # the scripts write next to themselves: run them from the root
        shutil.copy2(os.path.join(TOOLS, s), os.path.join(ROOT, s))
    say(f"=== {dt.datetime.now(ZoneInfo('America/New_York')):%F %T} start (through {end})")
    if a.rescore is not None:
        # plain years rebuild MLB seasons; "aaa-2025" / "a-2024" tokens rebuild a minor-league season (27 Sep 2026: Stuff+ there)
        toks = a.rescore or [str(y) for y in range(2015, int(year))]
        years = [t for t in toks if t.isdigit()]
        milb, other = {}, {}
        for t in toks:
            if "-" in t and t.split("-", 1)[1].isdigit():
                k0, y0 = t.split("-", 1)
                (other if k0 in ("spring", "post") else milb).setdefault(k0, []).append(y0)   # "spring-2026": that spring training
        ok = (not years or run("build_history.py", *years))
        for kind, ys in other.items():
            ok = ok and run("build_history.py", kind, *ys)
        for lvl, ys in milb.items():
            ok = ok and run("build_milb.py", lvl, *ys)
        # the search index too, so a newly built spring / postseason shows in the cards' MLB dropdown
        ok = ok and run("build_history.py", "index") and run("build_career.py") and (run("build_trends.py") or True) and (run("build_similar.py") or True) and publish(f"rescored {' '.join(toks)}", end, a.dry)
        sys.exit(0 if ok else 1)
    steps = set(a.steps.split(","))
    ok = True
    if "mlb" in steps:
        # League Trends (hist/trends.js) re-sums the season just built; a failure there costs only that page
        ok = run("build_data.py", "--end", end) and (run("build_trends.py") or True) and (run("build_similar.py") or True) and publish("MLB", end, a.dry)
        # spring training (Sean, 29 Sep 2026: track a pitcher's stuff in spring): through March, rebuild this spring's dataset too —
        # Stuff+ graded against MLB pitch types — and publish it; a failure costs only the spring file
        if ok and end[5:7] in ("02", "03") and run("build_history.py", "spring", year):
            publish("spring training", end, a.dry)
        # the postseason (Sean, 30 Sep 2026: MLB PS on the cards): from late September into November, rebuild this October's
        # dataset every morning (no games yet = no file, harmlessly); the index step below then offers it on the cards
        if ok and end[5:7] in ("09", "10", "11"):
            run("build_history.py", "post", year)
    if ok and "minors" in steps:
        ok = (run("build_milb.py", "aaa", year)
              and run("build_milb.py", "aa", "ap", "a", year)
              and run("build_fantasy.py")
              and run("build_history.py", "index")
              and run("build_career.py")
              and publish("minors, fantasy, index, career", end, a.dry))
    say(f"=== {dt.datetime.now(ZoneInfo('America/New_York')):%F %T} {'done' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
