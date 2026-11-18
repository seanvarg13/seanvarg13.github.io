"""Pull the site's stored per-season values (m.*) for every player from data.js / hist/mlb-YYYY.js into a parquet."""
import json, glob, pandas as pd
R = "/home/user/seanvarg13.github.io"
rows = []
for f in [R + "/data.js"] + sorted(glob.glob(R + "/hist/mlb-20[12][0-9].js")):
    s = open(f).read(); d = json.loads(s[s.index("= {") + 2:].rstrip().rstrip(";"))
    if d.get("kind"): continue
    y = int(d["meta"]["season"] if "meta" in d else d["season"])
    for p in d["players"]:
        m = p.get("m") or {}
        rows.append({"id": p["id"], "season": y, "role": p["type"], **{k: m.get(k) for k in ("stuff", "pitch", "nera", "siera", "fip", "xwd", "dxw", "woba")}})
pd.DataFrame(rows).to_parquet("/home/user/statcast/sitevals.parquet"); print(len(rows))
