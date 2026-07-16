import subprocess, re

NAV_CANON = """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REPO NAVIGATION CANON — 12sgi-king (2026-07-16 update)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The repo is served as a subdirectory. In ALL HTML/JS you write or review:

From root-level HTML: href="site/reports.html"  (NOT href="reports.html")
From king_public_src/: href="../site/reports.html"  (NOT href="../reports.html")
  intra-king_public_src: href="commentary_seat.html"  (NOT ../king/commentary_seat.html)
From element_lotus_public/: href="../site/reports.html", href="../site/games/", href="../site/sage/"
  (NOT href="games/" or href="reports.html")
In govos-shell.js: href:'site/reports.html'  (NOT href:'reports.html')

site/ is OVERWRITTEN on every build_site.py run — never edit it directly.

Civic pages in site/: reports.html, jurisdictions.html, datasets.html, agendas.html,
testify.html, news_record.html, civic_daily.html, meetings_calendar.html, studio.html,
money_behind_officials.html, accountability_record.html, wildfire_recovery_watch.html,
tenants_hub.html, agenda_explainer.html, n53_engine.html, testimony_record.html.
Pages at repo root: take_action.html, grants.html, education.html, king_landing.html, go.html.
"""

for model in ["kahualii:latest", "king-reason:latest", "king-tax:latest"]:
    short = model.replace(":latest", "")
    r = subprocess.run(["ollama", "show", "--modelfile", model],
                       capture_output=True, text=True, timeout=15)
    mf = r.stdout

    sys_match = re.search(r'(SYSTEM\s+""")(.*?)(""")', mf, re.DOTALL)
    if sys_match:
        new_mf = mf[:sys_match.start(3)] + NAV_CANON + '\n"""' + mf[sys_match.end(3):]
    else:
        new_mf = mf.rstrip() + f'\nSYSTEM """{NAV_CANON}\n"""\n'

    mf_path = f"_mf_{short}.tmp"
    with open(mf_path, "w", encoding="utf-8") as f:
        f.write(new_mf)

    r2 = subprocess.run(["ollama", "create", short, "-f", mf_path],
                        capture_output=True, text=True, timeout=60)
    import os; os.remove(mf_path)
    print(f"  {'OK' if r2.returncode == 0 else 'FAIL'}: {model}")
