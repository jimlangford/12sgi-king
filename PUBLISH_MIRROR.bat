@echo off
REM Publish the updated go.html (full public mirror links for govOS civic surfaces)
REM to GitHub Pages. Commits + pushes; the "kilo-aupuni publish" Action then rebuilds
REM site/ and deploys to https://jimlangford.github.io/12sgi-king/ (~1-3 min).
REM Canonical-source workflow: only go.html (repo root) is edited; CI rebuilds site/.
setlocal
cd /D "C:\Users\12sgi\Documents\Claude\12sgi-king"

echo === git status (before) ===
git status --short

echo.
echo === staging go.html ===
git add go.html

echo === committing ===
git commit -m "go.html: surface all govOS civic mirror links (budget-transparency + siblings) for mobile, no-Tailscale access"

echo.
echo === pushing to origin/main (triggers Pages rebuild) ===
git push origin main

echo.
echo Done. GitHub Actions ("kilo-aupuni publish") will rebuild and deploy in ~1-3 min.
echo Then verify: https://jimlangford.github.io/12sgi-king/go.html
echo.
pause
endlocal
