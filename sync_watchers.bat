@echo off
REM sync_watchers.bat - copy the latest watchers from the live elementLOTUS project
REM into this repo's watchers\ and commit. Run after improving any watcher.
REM Pure ASCII on purpose (a stray non-ASCII byte makes cmd mis-parse the file).
setlocal
set REPO=C:\Users\12sgi\Documents\Claude\12sgi-king
set KA=C:\Users\12sgi\Documents\Claude\Projects\Video System elementLOTUS\tools\kilo-aupuni
set CW=C:\Users\12sgi\Documents\Claude\tools\council-watch
set DEST=%REPO%\watchers

echo Syncing watchers from the live project...
REM kilo-aupuni watchers + the data files the generators need on CI.
REM EXCLUDE: rpa (Cloudflare/Playwright, not CI), probes, per-run state, secret keys,
REM and every watcher marked PRIVATE/OWNER-ONLY in its own header - these must NEVER reach the
REM public repo. (Found 2026-07-09: this list only had prosecutor.py + lead_dossier was never
REM added when written 2026-06-16 -- 22 self-declared-private watchers had leaked in via this
REM exact gap. tools/kilo-aupuni/selfheal.py's chk_no_leak() now also scans every .py file's own
REM header for a PRIVATE/OWNER-ONLY/never-published declaration as a second, self-updating layer
REM that does not depend on this list being remembered -- but keep this list current too, since
REM sync_watchers.bat is what actually keeps the file out in the first place.)
robocopy "%KA%" "%DEST%" *.py departments.json energov_permit_template.json commission_inputs.json ^
  crosswalk_local.json agenda_sources.json n53_archive.json tenants.json ^
  /XF rpa_watch.py prosecutor.py _probe*.py legiscan_key.txt nysenate_key.txt *_state.json ^
  candidate_watch.py cases_crosscheck.py case_money_bridge.py civic_analytics.py committee_sweep.py ^
  daily_learnings.py enforcement_ingest.py facebook_dyi_ingest.py langford_case_builder.py ^
  langford_legal_ingest.py lead_dossier.py matter_attachments.py maui_re_report.py minutes_review.py ^
  onboard_readiness.py private_completeness.py prosecutor_leads.py prosecutor_reddit_pull.py ^
  prosecutor_transcribe.py prosecutor_youtube_pull.py ram_loop.py recusal_evidence.py ^
  /NFL /NDL /NJH /NJS /NP >nul
REM council_watch.py lives in a separate folder
copy /Y "%CW%\council_watch.py" "%DEST%\council_watch.py" >nul

cd /D "%REPO%"
git add watchers
git diff --cached --quiet
if %errorlevel% neq 0 (
  git commit -m "sync: update watchers from live project"
  echo Committed. Now: git push   (to publish via GitHub Actions + Cloudflare Pages)
) else (
  echo No watcher changes to commit.
)
endlocal
