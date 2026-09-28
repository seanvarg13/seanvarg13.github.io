"""Publish the site to Netlify — a permanent https link that works on a phone.

One-time setup (free):
  1. Make an account at https://app.netlify.com
  2. User settings -> Applications -> Personal access tokens -> "New access token"
  3. Save the token where the scripts look for it:   echo 'nfp_xxx' > ~/.netlify_token

Then, whenever the data has been updated:
  python3 publish.py                       # first run creates the site and prints its address
  python3 publish.py --name my-draft-board # first run only: pick the subdomain (my-draft-board.netlify.app)

It mirrors the site files into ../draft-site-deploy, tells Netlify the SHA-1 of every file, and uploads
only the ones Netlify does not already have — a daily refresh is ~7 files, not the whole 400 MB.
The site id is remembered in netlify_site.json next to this script; the token never leaves ~/.
"""
import hashlib, json, os, shutil, sys, time
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.join(os.path.dirname(HERE), "draft-site-deploy")
SITE_FILE = os.path.join(HERE, "netlify_site.json")
API = "https://api.netlify.com/api/v1"
TOP = ["index.html", "app.js", "styles.css", "themes.js", "defaults.js", "data.js", "days.js", "fantasy.js", "manifest.json",
       "icons/icon-32.png", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png"]


def token():
    t = os.environ.get("NETLIFY_AUTH_TOKEN")
    if not t:
        try:
            with open(os.path.expanduser("~/.netlify_token")) as f:
                t = f.read().strip()
        except OSError:
            t = ""
    if not t:
        sys.exit("No Netlify token. Create one at app.netlify.com (User settings -> Applications -> "
                 "Personal access tokens) and save it:  echo 'nfp_xxx' > ~/.netlify_token")
    return t


def say(msg):
    print(msg, flush=True)


def sync():
    """Mirror the site files (not the build scripts or caches) into the deploy folder."""
    for sub in ("hist", "icons"):
        os.makedirs(os.path.join(DEPLOY, sub), exist_ok=True)
    wanted = {}
    for name in TOP:
        wanted[name] = os.path.join(HERE, name)
    for name in sorted(os.listdir(os.path.join(HERE, "hist"))):
        if name.endswith(".js"):
            wanted["hist/" + name] = os.path.join(HERE, "hist", name)
    copied = 0
    for rel, src in wanted.items():
        dst = os.path.join(DEPLOY, rel)
        s = os.stat(src)
        try:
            d = os.stat(dst)
            same = d.st_size == s.st_size and int(d.st_mtime) == int(s.st_mtime)
        except OSError:
            same = False
        if not same:
            shutil.copy2(src, dst)
            copied += 1
    for name in os.listdir(os.path.join(DEPLOY, "hist")):      # drop files that no longer exist upstream
        if "hist/" + name not in wanted:
            os.remove(os.path.join(DEPLOY, "hist", name))
    stamp(wanted)
    try:                                                   # the build scripts ride along under tools/ so they can be
        import sync_tools                                  # read and edited from GitHub; they are not part of the site
        sync_tools.mirror_out(DEPLOY)
    except Exception as e:                                 # noqa: BLE001 — a publish must never fail over this
        say(f"  (tools mirror skipped: {type(e).__name__}: {e})")
    say(f"synced {len(wanted)} files to draft-site-deploy ({copied} changed)")
    return wanted


def stamp(wanted):
    """Version every file reference so a phone never serves yesterday's app out of its cache.

    Hosts tell browsers to keep these files for a while, and a home-screen web app holds them longer still, so a
    publish could leave an iPhone on the old code. Here each file gets a ?v=<hash of its contents> in the page:
    unchanged files keep their address (and stay cached), changed ones get a new one and are fetched at once. The
    files app.js loads by itself (days.js, hist/…) are versioned through the DRAFT_BUILD map it reads.
    """
    ver = {rel: sha1(os.path.join(DEPLOY, rel))[:10] for rel in wanted}
    build = hashlib.sha1("".join(f"{k}:{v}" for k, v in sorted(ver.items())).encode()).hexdigest()[:10]
    html = open(os.path.join(DEPLOY, "index.html")).read()
    for rel, v in ver.items():                                  # src="app.js" -> src="app.js?v=1a2b3c4d5e"
        for attr in ('src="', 'href="'):
            html = html.replace(f'{attr}{rel}"', f'{attr}{rel}?v={v}"')
    tag = ("<script>window.DRAFT_BUILD=" + json.dumps(ver, separators=(",", ":"))
           + ';window.DRAFT_BUILD_ID="' + build + '";</script>\n')
    html = html.replace('<script src="defaults.js', tag + '<script src="defaults.js', 1)
    with open(os.path.join(DEPLOY, "index.html"), "w") as f:
        f.write(html)
    # a tiny file the running page polls (never cached): when its id moves on, the page reloads itself, which is
    # how a phone's home-screen app picks up a publish instead of sitting on the copy it saved days ago
    with open(os.path.join(DEPLOY, "build.json"), "w") as f:
        json.dump({"build": build, "at": time.strftime("%Y-%m-%d %H:%M")}, f)
    wanted["build.json"] = os.path.join(DEPLOY, "build.json")


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def site(sess, name=None):
    if os.path.exists(SITE_FILE):
        with open(SITE_FILE) as f:
            return json.load(f)
    body = {"name": name} if name else {}
    r = sess.post(f"{API}/sites", json=body)
    if r.status_code == 422 and name:
        sys.exit(f"The name '{name}' is taken on netlify.app — try another with --name")
    r.raise_for_status()
    j = r.json()
    # new sites can come up with "team members only" protection on; this board is meant to open without a login
    sess.patch(f"{API}/sites/{j['id']}", json={"sso_login": False})
    info = {"id": j["id"], "name": j["name"], "url": j.get("ssl_url") or j["url"]}
    with open(SITE_FILE, "w") as f:
        json.dump(info, f, indent=1)
    say(f"created site {info['url']}")
    return info


def main():
    name = None
    if "--name" in sys.argv:
        name = sys.argv[sys.argv.index("--name") + 1]
    sess = requests.Session()
    sess.headers["Authorization"] = "Bearer " + token()
    sess.headers["User-Agent"] = "draft-board-publish"
    info = site(sess, name)

    files = sync()
    digests = {"/" + rel: sha1(os.path.join(DEPLOY, rel)) for rel in files}
    say(f"asking Netlify which of {len(digests)} files it needs…")
    r = sess.post(f"{API}/sites/{info['id']}/deploys", json={"files": digests, "draft": False})
    r.raise_for_status()
    dep = r.json()
    while "required" not in dep or dep.get("state") in ("preparing",):
        time.sleep(2)
        dep = sess.get(f"{API}/deploys/{dep['id']}").json()
    need = set(dep.get("required") or [])
    todo = [rel for rel in files if digests["/" + rel] in need]
    total = sum(os.path.getsize(os.path.join(DEPLOY, rel)) for rel in todo)
    say(f"uploading {len(todo)} changed files ({total / 1e6:.0f} MB)")
    for i, rel in enumerate(todo, 1):
        path = os.path.join(DEPLOY, rel)
        for attempt in range(3):
            with open(path, "rb") as f:
                u = sess.put(f"{API}/deploys/{dep['id']}/files/{rel}", data=f,
                             headers={"Content-Type": "application/octet-stream"}, timeout=300)
            if u.ok:
                break
            time.sleep(3)
        else:
            sys.exit(f"upload failed for {rel}: {u.status_code} {u.text[:200]}")
        say(f"  {i}/{len(todo)} {rel} ({os.path.getsize(path) / 1e6:.1f} MB)")

    say("waiting for Netlify to go live…")
    for _ in range(150):
        d = sess.get(f"{API}/deploys/{dep['id']}").json()
        if d.get("state") == "ready":
            break
        if d.get("state") == "error":
            sys.exit("Netlify reported an error: " + str(d.get("error_message")))
        time.sleep(2)
    say(f"LIVE {info['url']}")


if __name__ == "__main__":
    main()
