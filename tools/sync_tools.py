"""Keep the build scripts on this Mac and their copies in the GitHub repo in step.

Why: the site's repo (seanvarg13/seanvarg13.github.io) is the only thing an assistant working outside this
Mac can see. Mirroring the scripts into it under tools/ lets that assistant read and edit them; pulling the
repo's copies back down before each build is what makes those edits actually run here.

    python3 sync_tools.py          # pull tools/ from the repo's main branch into this folder
    python3 sync_tools.py --dry    # say what would change, write nothing

Which way a file moves is decided per file, against .tools-mirror.json (the git blob sha of every file as it
was at the last publish):

    repo == local                 nothing to do
    local == last published       the repo moved on -> adopt it here
    repo  == last published       this Mac moved on -> keep it; the next publish pushes it
    both moved                    conflict -> keep the local file, drop the repo's copy in
                                  logs/tools-conflicts/ and say so loudly

A pulled .py has to compile before it is installed, and whatever it replaces is kept in logs/tools-backup/,
so a bad edit pushed from anywhere cannot take the 5:30 job down. Reading the repo needs no token (it is
public); ~/.github_token is used when it is there, only to get a bigger API rate limit.
"""
import base64, datetime as dt, hashlib, json, os, shutil, sys
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODELS = os.path.join(ROOT, "model-workspace")
STATE = os.path.join(HERE, ".tools-mirror.json")
SITE_FILE = os.path.join(HERE, "github_site.json")
BRANCH = "main"

# repo path -> file on this Mac. Nothing outside this map is ever read from the repo or written here.
FILES = {
    "CLAUDE.md": os.path.join(HERE, "CLAUDE.md"),
    "docs/site-README.md": os.path.join(HERE, "README.md"),   # the long-form manual; not served by the site
    "tools/build_data.py": os.path.join(HERE, "build_data.py"),
    "tools/build_history.py": os.path.join(HERE, "build_history.py"),
    "tools/build_milb.py": os.path.join(HERE, "build_milb.py"),
    "tools/build_fantasy.py": os.path.join(HERE, "build_fantasy.py"),
    "tools/build_career.py": os.path.join(HERE, "build_career.py"),
    "tools/daily_update.py": os.path.join(HERE, "daily_update.py"),
    "tools/publish.py": os.path.join(HERE, "publish.py"),
    "tools/publish_github.py": os.path.join(HERE, "publish_github.py"),
    "tools/serve.py": os.path.join(HERE, "serve.py"),
    "tools/sync_tools.py": os.path.join(HERE, "sync_tools.py"),
    "tools/install_schedule.sh": os.path.join(HERE, "install_schedule.sh"),
    # the GitHub Actions daily update: it lives only in the repo, but the Mac's publish rebuilds main from this folder,
    # so these ride along (unchanged) or its next push would delete them
    "tools/cloud_daily.py": os.path.join(HERE, "cloud_daily.py"),
    "tools/cloud.json": os.path.join(HERE, "cloud.json"),
    ".github/workflows/daily.yml": os.path.join(HERE, "github-workflow-daily.yml"),
    "tools/models/model3.py": os.path.join(MODELS, "model3.py"),
    "tools/models/model_bs.py": os.path.join(MODELS, "model_bs.py"),
    # repo-only files the Mac never edits: they ride along so a publish from here can't delete them (25 Sep 2026,
    # when one did — .gitignore is what keeps the cloud run's staged scripts out of its commit)
    "tools/models/milb_translate.py": os.path.join(MODELS, "milb_translate.py"),
    ".gitignore": os.path.join(HERE, "repo.gitignore"),
    # the front end: the repo's root copies are the site itself, published byte for byte from this folder, so an
    # edit made on GitHub comes down here like a script does and the next publish sends it back up unchanged.
    # index.html is left out on purpose: the published one is stamped, so it never equals the template here.
    "app.js": os.path.join(HERE, "app.js"),
    "styles.css": os.path.join(HERE, "styles.css"),
    "themes.js": os.path.join(HERE, "themes.js"),
}
# What this Mac last published of files that joined FILES after .tools-mirror.json was written (the publish of
# 24 Sep 2026, commit 4d0681a). Without it the first sync can't tell "the repo moved on" from "both moved" and
# would keep the local copy; with it, a file the Mac hasn't touched since is taken from the repo. Once a publish
# has recorded real shas in .tools-mirror.json these are never consulted again.
SEED_BASE = {
    "app.js": "bfb5beacbb0bb9be9e8eccbc236b89c920135699",
    "styles.css": "157aaa3efac0eec0047762ad0522fb0058b1cc37",
    "themes.js": "01697c2195f5658459415267faf0db9a2e9e3170",
}


def say(msg):
    print(msg, flush=True)


def blob_sha(data: bytes) -> str:
    """git's own hash for a file, so a listing's sha can be compared without downloading anything."""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def repo():
    with open(SITE_FILE) as f:
        return json.load(f)


def api(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "draft-board-sync-tools"})
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        try:
            with open(os.path.expanduser("~/.github_token")) as f:
                tok = f.read().strip()
        except OSError:
            tok = ""
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def remote_shas(info):
    """{repo path: blob sha} for everything in FILES that the repo's main branch has."""
    out = {}
    for folder in sorted({os.path.dirname(p) for p in FILES}):
        url = f"https://api.github.com/repos/{info['owner']}/{info['repo']}/contents/{folder}?ref={BRANCH}"
        if not folder:
            url = f"https://api.github.com/repos/{info['owner']}/{info['repo']}/contents?ref={BRANCH}"
        try:
            listing = api(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:                      # the repo has not got that folder yet
                continue
            raise
        for e in listing if isinstance(listing, list) else []:
            if e.get("type") == "file" and e.get("path") in FILES:
                out[e["path"]] = e["sha"]
    return out


def fetch(info, path):
    j = api(f"https://api.github.com/repos/{info['owner']}/{info['repo']}/contents/{path}?ref={BRANCH}")
    return base64.b64decode(j["content"])


def mirror_out(deploy):
    """Copy this Mac's scripts into the deploy folder under their repo paths, and record what was sent."""
    seen = {}
    for rel, src in FILES.items():
        data = read(src)
        if data is None:
            continue
        dst = os.path.join(deploy, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if read(dst) != data:
            shutil.copy2(src, dst)
        seen[rel] = blob_sha(data)
    with open(STATE, "w") as f:
        json.dump(seen, f, indent=1, sort_keys=True)
    return seen


# The site's own files, and its two manuals. They are edited on GitHub now (Sean's chat works there), so when this
# Mac's copy and the repo's have both moved since the last publish, the repo's wins for these (the Mac's goes to
# logs/tools-conflicts/). The README joined on 25 Sep 2026, after a publish put a days-old copy back over it.
SITE_FILES = ("app.js", "styles.css", "themes.js", "docs/site-README.md", "CLAUDE.md")


def pull(dry=False, source=None):
    """Bring down whatever was edited in the repo since the last publish. Returns the list of files adopted.
    source: (remote shas by repo path, fetch(repo path) -> bytes) read some other way than the API — the publisher
    passes git's own view of main, so a failing API call can never let it push old copies over new ones."""
    info = None
    if source is None:
        try:
            info = repo()
        except OSError:
            say("sync_tools: no github_site.json yet — nothing to pull")
            return []
    base, took, kept = state(), [], []
    if source is not None:
        remote, getter = source
    else:
        try:
            remote = remote_shas(info)
        except Exception as e:                                    # noqa: BLE001 — never block a build on this
            say(f"sync_tools: could not reach GitHub ({type(e).__name__}: {e}) — using the local scripts")
            return []
        getter = lambda rel: fetch(info, rel)                    # noqa: E731
    if not remote:
        say(f"sync_tools: the repo has no tools/ on {BRANCH} yet — nothing to pull")
        return []
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for rel, dst in FILES.items():
        rsha = remote.get(rel)
        if not rsha:
            continue
        local = read(dst)
        lsha = blob_sha(local) if local is not None else None
        if rsha == lsha:
            continue
        b = base.get(rel) or SEED_BASE.get(rel)
        if local is not None and lsha != b and rsha != b:          # edited in both places since the last publish
            out = os.path.join(HERE, "logs", "tools-conflicts", stamp)
            os.makedirs(out, exist_ok=True)
            if rel in SITE_FILES:                                  # the site: the repo's copy wins, this Mac's is kept aside
                if not dry:
                    shutil.copy2(dst, os.path.join(out, os.path.basename(rel)))
                say(f"sync_tools: !! {rel} was edited here AND in the repo — taking the repo's (the site is edited on "
                    f"GitHub); this Mac's copy is in logs/tools-conflicts/{stamp}/")
            else:
                data = getter(rel)
                with open(os.path.join(out, os.path.basename(rel)), "wb") as f:
                    f.write(data)
                say(f"sync_tools: !! {rel} was edited here AND in the repo — keeping the local one; "
                    f"the repo's copy is in logs/tools-conflicts/{stamp}/")
                kept.append(rel)
                continue
        if local is not None and rsha == b:                        # only this Mac moved: the next publish pushes it
            kept.append(rel)
            continue
        data = getter(rel)                                         # the repo moved on (or we have no copy): adopt it
        if rel.endswith(".py"):
            try:
                compile(data.decode("utf-8"), rel, "exec")
            except (SyntaxError, UnicodeDecodeError) as e:
                say(f"sync_tools: !! {rel} in the repo does not compile ({e}) — keeping the local one")
                continue
        elif rel.endswith((".js", ".css")):                # a site file: text, and not a stub that would blank the site
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as e:
                say(f"sync_tools: !! {rel} in the repo is not text ({e}) — keeping the local one")
                continue
            if local is not None and len(data) < 0.5 * len(local):
                say(f"sync_tools: !! {rel} in the repo is under half the size of the local one — keeping the local one")
                continue
        if dry:
            say(f"sync_tools: would update {rel}")
            took.append(rel)
            continue
        if local is not None:
            bak = os.path.join(HERE, "logs", "tools-backup", stamp)
            os.makedirs(bak, exist_ok=True)
            shutil.copy2(dst, os.path.join(bak, os.path.basename(rel)))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
        if rel.endswith(".sh"):
            os.chmod(dst, 0o755)
        base[rel] = rsha
        say(f"sync_tools: updated {os.path.relpath(dst, ROOT)} from the repo")
        took.append(rel)
    if took and not dry:
        with open(STATE, "w") as f:
            json.dump(base, f, indent=1, sort_keys=True)
    if not took:
        say(f"sync_tools: scripts already match the repo{' (' + str(len(kept)) + ' newer here)' if kept else ''}")
    return took


if __name__ == "__main__":
    got = pull(dry="--dry" in sys.argv)
    if got:
        say(f"sync_tools: {len(got)} file(s) taken from the repo — this run uses them")
