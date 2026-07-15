#!/usr/bin/env python3
txt = open('king-watchdog.py').read()
old = """def check_processes():
    for svc in PROCESS_SERVICES:
        ensure_process(svc['label'], svc['cmd'], svc.get('ready_url'))"""
new = """def check_processes():
    for svc in PROCESS_SERVICES:
        ensure_process(svc['label'], svc['cmd'], svc.get('ready_url'))
    # Health-check Docker-managed services (not started here; just monitored)
    for chk in HTTP_HEALTH_CHECKS:
        if not http_ready(chk['url']):
            log(f"WARNING: {chk['label']} not responding at {chk['url']} -- check docker compose logs")"""
txt = txt.replace(old, new)
open('king-watchdog.py', 'w').write(txt)
print('Updated check_processes')
