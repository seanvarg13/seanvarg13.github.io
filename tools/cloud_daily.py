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
SCRIPTS = ["build_data.py", "build_history.py", "build_milb.py", "build_fantasy.py", "build_career.py"]
# what the site serves: the same list publish.py stamps, plus every hist/ file
TOP = ["index.html", "app.js", "styles.css", "themes.js", "defaults.js", "data.js", "days.js", "fantasy.js", "manifest.json",
       "icons/icon-32.png", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png"]
OUTPUTS = ["data.js", "days.js", "fantasy.js"]            # plus hist/*.js — what a build writes


def say(msg):
    print(msg, flush=True)


def run(*args):
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


def outputs():
    return [p for p in OUTPUTS if os.path.exists(p)] + sorted(glob.glob("hist/*.js"))


def publish(label, end, dry):
    """Commit the build's outputs on top of main as it is now, and push. Returns True when main has them."""
    if dry:
        say(f"--- (dry run) would publish: {label}; build id {restamp()}")
        return True
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
        years = a.rescore or [str(y) for y in range(2015, int(year))]
        ok = run("build_history.py", *years) and run("build_career.py") and publish(f"rescored {' '.join(years)}", end, a.dry)
        sys.exit(0 if ok else 1)
    steps = set(a.steps.split(","))
    ok = True
    if "mlb" in steps:
        ok = run("build_data.py", "--end", end) and publish("MLB", end, a.dry)
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
