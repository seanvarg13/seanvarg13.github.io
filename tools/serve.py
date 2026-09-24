"""Serve the draft site locally with an "Update data" button.

    python3 serve.py            # opens http://localhost:8787
    python3 serve.py --phone    # also reachable from a phone on the same Wi-Fi (prints the address)

GET  /api/status            -> {"running": bool, "log": [...last lines], "through": "...", "built": "..."}
POST /api/update?end=DATE   -> runs build_data.py --end DATE (default: yesterday), rebuilds the four minor-league
                               levels for that year (AAA, AA, High-A, Single-A), then refreshes the player index
POST /api/publish           -> runs publish_github.py (GitHub Pages; falls back to publish.py / Netlify) — see their headers for the one-time setup
POST /api/appearance        -> body {"scheme","font","theme","view"}: writes defaults.js (the site-wide Appearance default)
"""
import json, os, re, subprocess, sys, threading, webbrowser, datetime as dt
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8787))
state = {"running": False, "job": None, "log": [], "exit": None, "started": None}


def data_meta():
    try:
        with open(os.path.join(HERE, "data.js"), encoding="utf-8") as f:
            head = f.read(4000)
        m = {k: re.search(rf'"{k}":"([^"]+)"', head) for k in ("through", "built")}
        return {k: (v.group(1) if v else None) for k, v in m.items()}
    except OSError:
        return {"through": None, "built": None}


def run_job(job, cmds):
    state.update(running=True, job=job, log=[], exit=None, started=dt.datetime.now().isoformat(timespec="seconds"))
    code = 0
    for cmd in cmds:
        state["log"].append("$ " + " ".join(cmd[1:]))
        p = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            line = line.rstrip()
            if not line or "it/s]" in line:          # drop pybaseball progress bars
                continue
            state["log"].append(line)
            state["log"] = state["log"][-60:]
        code = p.wait()
        if code:
            state["log"].append(f"!! exited with code {code}")
            break
    state.update(running=False, exit=code)


def run_update(end):
    year = end[:4]
    run_job("update", [
        [sys.executable, "build_data.py", "--end", end],            # MLB current season
        [sys.executable, "build_milb.py", "aaa", year],              # AAA (Savant feed)
        [sys.executable, "build_milb.py", "aa", "ap", "a", year],    # AA / High-A / Single-A (Gameday feeds)
        [sys.executable, "build_fantasy.py"],                       # official season stats + game logs for fantasy points
        [sys.executable, "build_history.py", "index"],              # player search index
    ])


def publisher():
    """GitHub Pages when its token is set up (no deploy quota), else Netlify."""
    if os.environ.get("GITHUB_TOKEN") or os.path.exists(os.path.expanduser("~/.github_token")):
        return "publish_github.py", "github_site.json", "GitHub Pages"
    if os.environ.get("NETLIFY_AUTH_TOKEN") or os.path.exists(os.path.expanduser("~/.netlify_token")):
        return "publish.py", "netlify_site.json", "Netlify"
    return None, None, None


def run_publish():
    run_job("publish", [[sys.executable, publisher()[0]]])


def publish_meta():
    """Where the site lives on the web (if it has been published) and whether a publishing token is set up."""
    script, site_file, host = publisher()
    out = {"site": None, "token": bool(script), "host": host}
    if site_file:
        try:
            with open(os.path.join(HERE, site_file)) as f:
                out["site"] = json.load(f).get("url")
        except (OSError, ValueError):
            pass
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, fmt, *args):   # quieter console
        if "/api/" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # always pick up a fresh data.js
        super().end_headers()

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/api/status":
            return self.send_json({**state, **data_meta(), **publish_meta()})
        if self.path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/appearance":
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            except ValueError:
                return self.send_json({"ok": False, "error": "bad JSON"}, 400)
            keep = {k: str(body[k])[:40] for k in ("scheme", "font", "theme", "view") if k in body}
            with open(os.path.join(HERE, "defaults.js"), "w", encoding="utf-8") as f:
                f.write("window.DRAFT_DEFAULTS = " + json.dumps(keep) + ";\n")
            return self.send_json({"ok": True, "defaults": keep})
        if u.path not in ("/api/update", "/api/publish"):
            return self.send_json({"error": "unknown endpoint"}, 404)
        if state["running"]:
            return self.send_json({"ok": False, "error": f"{state['job']} is already running"}, 409)
        if u.path == "/api/publish":
            if not publish_meta()["token"]:
                return self.send_json({"ok": False, "error": "No publishing token yet — see the top of publish_github.py for the 5-minute setup"}, 400)
            threading.Thread(target=run_publish, daemon=True).start()
            return self.send_json({"ok": True})
        end = parse_qs(u.query).get("end", [None])[0] or str(dt.date.today() - dt.timedelta(days=1))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
            return self.send_json({"ok": False, "error": "end must be YYYY-MM-DD"}, 400)
        threading.Thread(target=run_update, args=(end,), daemon=True).start()
        return self.send_json({"ok": True, "end": end})


def lan_ip():
    """This Mac's address on the local network (for opening the site on a phone)."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))          # no traffic is sent; just picks the outbound interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


if __name__ == "__main__":
    phone = "--phone" in sys.argv or os.environ.get("HOST") == "0.0.0.0"
    host = "0.0.0.0" if phone else "127.0.0.1"
    srv = ThreadingHTTPServer((host, PORT), Handler)
    url = f"http://localhost:{PORT}/"
    print(f"2027 Draft Board at {url}   (Ctrl-C to stop)")
    if phone:
        ip = lan_ip()
        print(f"  on your phone (same Wi-Fi): http://{ip or '<this Mac\'s IP>'}:{PORT}/")
    if not os.environ.get("NO_OPEN"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
