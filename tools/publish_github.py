"""Publish the site to GitHub Pages — free, no deploy quota, a permanent https link that works on a phone.

One-time setup (about five minutes):
  1. Make a GitHub account at https://github.com/signup (a free one is fine).
  2. Make a token: https://github.com/settings/tokens -> "Generate new token (classic)"
       - note: "Sean's Site publisher";  expiration: "No expiration";  tick the "repo" scope
  3. Save it where the scripts look for it:   echo 'ghp_xxx' > ~/.github_token

Then, whenever the data has been updated:
  python3 publish_github.py                  # first run creates the repo <you>.github.io and turns Pages on
  python3 publish_github.py --repo seans-site # first run only: a project repo instead (https://<you>.github.io/seans-site/)
  python3 publish_github.py --squash          # collapse the repo's history to one commit (keeps the repo small)

How it works: the site files (not the build scripts or caches) are mirrored into ../draft-site-deploy, which is a git
repo; each publish is one commit pushed to the "main" branch and GitHub Pages serves it.  Git only sends what changed
(deltas), so a daily refresh is a few MB.  History is squashed automatically on the first publish of each month, and
whenever the local repo passes 1 GB, so the repo never grows without bound.  The repo is remembered in
github_site.json next to this script; the token never leaves ~/.
"""
import base64, datetime as dt, json, os, subprocess, sys, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(os.path.dirname(HERE), "draft-site-deploy")
SITE_FILE = os.path.join(HERE, "github_site.json")
API = "https://api.github.com"
sys.path.insert(0, HERE)
from publish import sync, say    # the same mirror the Netlify publisher uses  # noqa: E402


def token():
    t = os.environ.get("GITHUB_TOKEN")
    if not t:
        try:
            with open(os.path.expanduser("~/.github_token")) as f:
                t = f.read().strip()
        except OSError:
            t = ""
    if not t:
        sys.exit("No GitHub token. Make one at https://github.com/settings/tokens (classic, 'repo' scope, no expiration) "
                 "and save it:  echo 'ghp_xxx' > ~/.github_token")
    return t


def git(*args, check=True, capture=False, **kw):
    cmd = ["git", "-C", DEPLOY, "-c", "user.name=Sean's Site publisher", "-c", "user.email=publisher@users.noreply.github.com",
           "-c", "http.postBuffer=1000000000", "-c", "core.autocrlf=false", *args]
    if capture:
        return subprocess.run(cmd, check=check, stdout=subprocess.PIPE, stderr=kw.get("stderr"), text=True).stdout.strip()
    return subprocess.run(cmd, check=check, **kw).returncode


def auth_args(tok):
    # the token rides in a header for this one command; it is never written into the repo's config
    basic = base64.b64encode(f"x-access-token:{tok}".encode()).decode()
    return ["-c", f"http.extraheader=AUTHORIZATION: basic {basic}"]


def repo_info(sess, name=None):
    """The repo this site publishes to (created on the first run)."""
    if os.path.exists(SITE_FILE):
        with open(SITE_FILE) as f:
            return json.load(f)
    me = sess.get(f"{API}/user")
    me.raise_for_status()
    login = me.json()["login"]
    name = name or f"{login}.github.io"                 # the account's own site: https://<login>.github.io/
    r = sess.get(f"{API}/repos/{login}/{name}")
    if r.status_code == 404:
        r = sess.post(f"{API}/user/repos", json={"name": name, "description": "Sean's Site — fantasy baseball rankings, cards and leaderboards",
                                                  "private": False, "has_issues": False, "has_wiki": False, "has_projects": False, "auto_init": False})
        r.raise_for_status()
        say(f"created repo {login}/{name}")
    else:
        r.raise_for_status()
    user_site = name.lower() == f"{login}.github.io".lower()
    url = f"https://{login}.github.io/" + ("" if user_site else name + "/")
    info = {"owner": login, "repo": name, "url": url, "git": f"https://github.com/{login}/{name}.git"}
    with open(SITE_FILE, "w") as f:
        json.dump(info, f, indent=1)
    return info


def ensure_pages(sess, info):
    """Serve the main branch's root as the site (user sites usually come up on their own; project repos need this)."""
    o, r = info["owner"], info["repo"]
    p = sess.get(f"{API}/repos/{o}/{r}/pages")
    if p.status_code == 404:
        c = sess.post(f"{API}/repos/{o}/{r}/pages", json={"build_type": "legacy", "source": {"branch": "main", "path": "/"}})
        if c.status_code not in (201, 409):
            say(f"  (could not turn Pages on automatically: {c.status_code} {c.text[:160]} — "
                f"do it once at https://github.com/{o}/{r}/settings/pages: Source = Deploy from a branch, main, / (root))")
        else:
            say("turned GitHub Pages on")
    elif p.ok:
        src = (p.json().get("source") or {})
        if src.get("branch") != "main" or src.get("path") not in ("/", None):
            sess.put(f"{API}/repos/{o}/{r}/pages", json={"source": {"branch": "main", "path": "/"}})


def repo_bytes():
    out = git("count-objects", "-v", capture=True)
    size = 0
    for line in out.splitlines():
        k, _, v = line.partition(":")
        if k.strip() in ("size", "size-pack"):
            size += int(v.strip()) * 1024
    return size


MODELS = os.path.join(os.path.dirname(HERE), "model-workspace")


def upload_models(sess, info):
    """Put the directional models on the repo's "models" release, where the GitHub Actions daily run fetches them
    (.github/workflows/daily.yml), with the Python and package versions they were pickled under so the cloud
    installs the same ones. Only files that changed since the last upload are sent."""
    import importlib.metadata as md, platform
    o, r = info["owner"], info["repo"]
    rel = sess.get(f"{API}/repos/{o}/{r}/releases/tags/models")
    if rel.status_code == 404:
        rel = sess.post(f"{API}/repos/{o}/{r}/releases", json={"tag_name": "models", "name": "Models for the daily build",
            "body": "The directional xwOBA / xBA / xSLG models (model-workspace/*.joblib) and versions.json, uploaded by the "
                    "Mac's publisher. The GitHub Actions daily update downloads them; nothing here is part of the site.",
            "target_commitish": "main"})
    rel.raise_for_status()
    rel = rel.json()
    have = {a["name"]: a for a in rel.get("assets", [])}
    versions = {"python": ".".join(platform.python_version_tuple()[:2]),
                "packages": {p: md.version(p) for p in ("scikit-learn", "numpy", "pandas", "scipy", "joblib")}}
    vpath = os.path.join(MODELS, "versions.json")
    with open(vpath, "w") as f:
        json.dump(versions, f, indent=1, sort_keys=True)
    for name in ("v3_dir.joblib", "v3_ba.joblib", "v3_slg.joblib", "versions.json"):
        path = os.path.join(MODELS, name)
        if not os.path.exists(path):
            continue
        size, old = os.path.getsize(path), have.get(name)
        if old and old.get("size") == size and name != "versions.json":
            continue
        if old and name == "versions.json":
            cur = sess.get(old["browser_download_url"])
            if cur.ok and cur.content == open(path, "rb").read():
                continue
        if old:
            sess.delete(f"{API}/repos/{o}/{r}/releases/assets/{old['id']}")
        with open(path, "rb") as f:
            up = sess.post(f"https://uploads.github.com/repos/{o}/{r}/releases/{rel['id']}/assets?name={name}",
                           data=f, headers={"Content-Type": "application/octet-stream"})
        say(f"  models release: uploaded {name} ({size / 1e6:.1f} MB)" if up.ok else f"  (models upload {name}: {up.status_code})")


def cloud_publishes(info):
    """True once GitHub Actions runs the daily update (tools/cloud.json on main): then this Mac stands down."""
    try:
        r = requests.get(f"https://raw.githubusercontent.com/{info['owner']}/{info['repo']}/main/tools/cloud.json", timeout=20)
        return bool(r.ok and r.json().get("daily"))
    except Exception:                                   # noqa: BLE001 — unreachable: keep publishing as before
        return False


def main():
    name = sys.argv[sys.argv.index("--repo") + 1] if "--repo" in sys.argv else None
    squash = "--squash" in sys.argv
    tok = token()
    sess = requests.Session()
    sess.headers.update({"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json", "User-Agent": "draft-board-publish"})
    info = repo_info(sess, name)
    try:
        upload_models(sess, info)
    except Exception as e:                                 # noqa: BLE001 — never block a publish on this
        say(f"  (models upload skipped: {type(e).__name__}: {e})")
    if cloud_publishes(info) and "--force" not in sys.argv:
        say("GitHub Actions publishes the site now (tools/cloud.json) — not pushing from this Mac. --force overrides.")
        return

    try:                                                   # a script edited on GitHub is taken first, so this push
        import sync_tools                                  # does not put the old copy back over it
        sync_tools.pull()
    except Exception as e:                                 # noqa: BLE001
        say(f"  (tools pull skipped: {type(e).__name__}: {e})")
    sync()
    with open(os.path.join(DEPLOY, ".nojekyll"), "w") as f:      # serve the files as they are (no Jekyll pass)
        f.write("")
    with open(os.path.join(DEPLOY, ".gitignore"), "w") as f:
        f.write(".DS_Store\n")
    if not os.path.isdir(os.path.join(DEPLOY, ".git")):
        git("init", "-q", "-b", "main")
        git("config", "gc.pruneExpire", "never")     # old commits stay until a publish has gone through (keeps squash pushes small)
        git("config", "gc.auto", "0")
        squash = True
    if git("remote", "get-url", "origin", check=False, capture=True, stderr=subprocess.DEVNULL) != info["git"]:
        git("remote", "remove", "origin", check=False, stderr=subprocess.DEVNULL)
        git("remote", "add", "origin", info["git"])

    # first of the month, or a local repo past 1 GB: start the history over (the push stays small — GitHub already
    # has every unchanged file's blob)
    stamp = os.path.join(DEPLOY, ".git", "last-squash")
    last = open(stamp).read().strip() if os.path.exists(stamp) else ""
    month = dt.date.today().strftime("%Y-%m")
    if last != month or repo_bytes() > 1e9:
        squash = True
    if squash:
        git("branch", "-D", "fresh", check=False, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        git("checkout", "-q", "--orphan", "fresh")
        with open(stamp, "w") as f:
            f.write(month)
    git("add", "-A")
    changed = git("status", "--porcelain", capture=True)
    if changed or squash:
        n = len(changed.splitlines())
        msg = f"site through {dt.date.today()}" + (f" ({n} files changed)" if n else "")
        git("commit", "-q", "-m", msg)
        if squash:
            git("branch", "-M", "main")
    else:
        say("nothing changed since the last publish")
    sha = git("rev-parse", "HEAD", capture=True)
    say(f"pushing to github.com/{info['owner']}/{info['repo']} …")
    if git(*auth_args(tok), "push", "-q", "--force", "origin", "main", check=False):
        sys.exit("push failed — is the token right (repo scope) and does the repo still exist?")
    ensure_pages(sess, info)
    if squash:                                       # the old history is on neither side now
        git("gc", "-q", "--prune=now", check=False)

    say("waiting for GitHub Pages to go live…")
    o, r = info["owner"], info["repo"]
    for _ in range(90):
        b = sess.get(f"{API}/repos/{o}/{r}/pages/builds/latest")
        if b.ok and b.json().get("status") == "built" and b.json().get("commit") == sha:
            break
        if b.ok and b.json().get("status") == "errored":
            sys.exit(f"Pages build failed: {b.json().get('error')}")
        time.sleep(4)
    else:
        say("  (still building — it usually appears within a couple of minutes)")
    say(f"LIVE {info['url']}")


if __name__ == "__main__":
    main()
