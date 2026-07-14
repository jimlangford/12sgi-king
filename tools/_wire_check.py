import urllib.request, json, sys

checks = [
    ("studio-assets live",   "http://localhost:8108/api/v2/live"),
    ("studio-assets ready",  "http://localhost:8108/api/v2/ready"),
    ("studio-assets stats",  "http://localhost:8108/api/v2/stats"),
    ("studio projects list", "http://localhost:8108/api/v2/projects"),
    ("health sees studio",   "http://localhost:8106/api/v1/ready"),
    ("workboard pulse",      "http://localhost:8109/api/v2/bridge/pulse"),
]

ok_count = 0
for label, url in checks:
    try:
        r = urllib.request.urlopen(url, timeout=6)
        d = json.loads(r.read())
        if label == "health sees studio":
            svc = d.get("services", {})
            sa  = svc.get("studio-assets", {})
            val = f"studio-assets ok={sa.get('ok')} status={sa.get('reported_status', sa.get('status'))}"
        elif label == "studio projects list":
            val = f"{d.get('count')} projects"
        elif label == "studio-assets stats":
            val = f"total={d.get('total')} ({d.get('total_gb')} GB)"
        elif label == "workboard pulse":
            p = d.get("pulse", {})
            val = f"running={p.get('jobs_running')} gpu={p.get('waiting_gpu')} owner={p.get('waiting_owner')} deploy_ready={p.get('deploy_ready')}"
        else:
            val = d.get("status", str(d)[:60])
        print(f"  ok  {label:<28} {val}")
        ok_count += 1
    except Exception as e:
        print(f"  !!  {label:<28} {str(e)[:60]}")

print(f"\n{ok_count}/{len(checks)} checks passed")
sys.exit(0 if ok_count == len(checks) else 1)
