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
    "tools/models/model3.py": os.path.join(MODELS, "model3.py"),
    "tools/models/model_bs.py": os.path.join(MODELS, "model_bs.py"),
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


def pull(dry=False):
    """Bring down whatever was edited in the repo since the last publish. Returns the list of files adopted."""
    try:
        info = repo()
    except OSError:
        say("sync_tools: no github_site.json yet — nothing to pull")
        return []
    base, took, kept = state(), [], []
    try:
        remote = remote_shas(info)
    except Exception as e:                                        # noqa: BLE001 — never block a build on this
        say(f"sync_tools: could not reach GitHub ({type(e).__name__}: {e}) — using the local scripts")
        return []
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
        b = base.get(rel)
        if local is not None and lsha != b and rsha != b:          # edited in both places since the last publish
            data = fetch(info, rel)
            out = os.path.join(HERE, "logs", "tools-conflicts", stamp)
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, os.path.basename(rel)), "wb") as f:
                f.write(data)
            say(f"sync_tools: !! {rel} was edited here AND in the repo — keeping the local one; "
                f"the repo's copy is in logs/tools-conflicts/{stamp}/")
            kept.append(rel)
            continue
        if local is not None and rsha == b:                        # only this Mac moved: the next publish pushes it
            kept.append(rel)
            continue
        data = fetch(info, rel)                                    # the repo moved on (or we have no copy): adopt it
        if rel.endswith(".py"):
            try:
                compile(data.decode("utf-8"), rel, "exec")
            except (SyntaxError, UnicodeDecodeError) as e:
                say(f"sync_tools: !! {rel} in the repo does not compile ({e}) — keeping the local one")
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
