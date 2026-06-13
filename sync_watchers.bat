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
REM kilo-aupuni watchers + their data files; EXCLUDE rpa (Cloudflare/Playwright, not CI),
REM probes, secret key, and per-run state files.
robocopy "%KA%" "%DEST%" *.py departments.json energov_permit_template.json commission_inputs.json ^
  /XF rpa_watch.py _probe*.py legiscan_key.txt *_state.json /NFL /NDL /NJH /NJS /NP >nul
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
