#!/usr/bin/env python3
"""Stamp football/index.html and, with --push, commit football/ on top of main as it is now and push it.

    python3 tools/fb/publish_fb.py            # stamp only (when merging by hand)
    python3 tools/fb/publish_fb.py --push     # what the weekly workflow runs

The stamp is the first 10 hex of the sha1 of every file the page loads, put on each ?v= so a phone picks up a new
build at once (the same idea as the baseball site's index.html stamps). The push works like tools/cloud_daily.py's
publish: keep the built files aside, reset to origin/main, put them back, commit, push, retry if main moved.
"""
import argparse, hashlib, os, re, shutil, subprocess, sys, tempfile, time, urllib.request

ROOT = "football"
LOADED = ["fb.css", "fb.js", "data/index.js", "data/teams.js"]


def stamp():
    h = hashlib.sha1()
    for rel in LOADED + sorted(f"data/{n}" for n in os.listdir(os.path.join(ROOT, "data")) if n.endswith(".js")):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            h.update(open(p, "rb").read())
    build = h.hexdigest()[:10]
    p = os.path.join(ROOT, "index.html")
    s = open(p).read()
    s = re.sub(r'\?v=[^"]*"', f'?v={build}"', s)
    s = re.sub(r'window\.FB_BUILD = "[^"]*"', f'window.FB_BUILD = "{build}"', s)
    open(p, "w").write(s)
    return build


def git(*a, check=True, capture=False):
    r = subprocess.run(["git", *a], capture_output=capture, text=True)
    if check and r.returncode:
        sys.exit(f"git {' '.join(a)} failed")
    return r.stdout if capture else r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--label", default="football weekly update")
    a = ap.parse_args()
    if not a.push:
        print("build", stamp()); return
    keep = tempfile.mkdtemp()
    shutil.copytree(os.path.join(ROOT, "data"), os.path.join(keep, "data"))
    for attempt in range(5):
        git("fetch", "-q", "origin", "main")
        git("reset", "-q", "--hard", "origin/main")
        shutil.rmtree(os.path.join(ROOT, "data"), ignore_errors=True)
        shutil.copytree(os.path.join(keep, "data"), os.path.join(ROOT, "data"))
        build = stamp()
        git("add", ROOT)
        if not git("status", "--porcelain", "--untracked-files=no", capture=True).strip():
            print("nothing changed since the last publish"); return
        git("commit", "-q", "-m", f"{a.label} (build {build}), GitHub Actions")
        if git("push", "-q", "origin", "HEAD:main", check=False) == 0:
            print("published, build", build)
            tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
            if tok and repo:   # a push with the workflow's own token may not start a Pages build by itself
                try:
                    urllib.request.urlopen(urllib.request.Request(f"https://api.github.com/repos/{repo}/pages/builds", method="POST",
                                           headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json"}), timeout=30).read()
                except Exception as e:
                    print("Pages build request:", e)
            return
        print(f"push rejected (main moved on), retrying {attempt + 1}/5"); time.sleep(5 + 10 * attempt)
    sys.exit("could not push after 5 tries")


if __name__ == "__main__":
    main()
