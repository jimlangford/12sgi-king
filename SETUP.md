# Kilo Aupuni — free hosting setup ($0/month)

This repo runs the civic-transparency watchers on **GitHub Actions** (free compute, off your
laptop) and serves the result on **Cloudflare Pages** (free, unlimited bandwidth, no commercial
restriction, free SSL + custom domain). Only cost is the domain you already own.

## One-time setup (~15 min)

### 1. Put this folder in a GitHub repo
```
cd 12sgi-king
git init && git add . && git commit -m "Kilo Aupuni civic transparency"
# create an EMPTY repo on github.com (private is fine), then:
git remote add origin https://github.com/<you>/kilo-aupuni.git
git push -u origin main
```
The `.gitignore` already blocks the LegiScan key, `config/`, and state files from ever being committed. Confirm `git status` shows no `legiscan_key.txt`.

### 2. Add the repo Secrets  (Settings → Secrets and variables → Actions → New secret)
| Secret | Where to get it |
|---|---|
| `LEGISCAN_KEY` | your LegiScan key. **Rotate it first** at legiscan.com → Account → API (it was shared in chat, so regenerate to be safe), then paste the new one. *(Optional — without it the lege step is skipped.)* |
| `CLOUDFLARE_API_TOKEN` | Cloudflare → My Profile → API Tokens → Create Token → "Edit Cloudflare Pages" template |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare dashboard → right sidebar → Account ID |

### 3. Create the Cloudflare Pages project (free)
- Cloudflare dashboard → **Workers & Pages → Create → Pages → Direct upload** → name it **`kilo-aupuni`** (must match `--project-name` in the workflow). No build settings needed — the Action uploads the prebuilt `site/`.

### 4. Run it
- GitHub → **Actions → "kilo-aupuni publish" → Run workflow**. It runs the watchers, builds `site/`, and deploys to Pages. After that it runs **daily at ~5:20 AM HST** automatically.

### 5. Custom domain (free)
- Cloudflare Pages project → **Custom domains → Set up** → e.g. `civic.12sgi.com` (or point `gov.12sgi.com` here instead of Vercel). SSL is automatic.

## What runs (and what doesn't) on the free runner
**Runs (HTTP/API + pypdf, no browser):** council agendas, council votes/recusals, procurement bids,
permits (EnerGov), Maui donors, statewide money (2008+), state legislator votes (LegiScan 2010+),
charter↔law, commission antitrust, the money×votes patterns, the county dashboard.
**Does NOT run in CI (by design):** `rpa_watch` (qPublic real property) — Cloudflare-gated, needs the
UIPA bulk file; run it attended on your machine if/when you have the data.

## Cost
GitHub Actions (free: public repo unlimited, private 2,000 min/mo — a daily run uses a few),
Cloudflare Pages (free, unlimited bandwidth). **$0/month.** Domain ~$15/yr (already owned).

## Security
- The LegiScan key lives ONLY in GitHub Secrets, written to `config/legiscan_key.txt` on the runner at
  run time, and `config/` is git-ignored. It is never committed and never printed in logs.
- All published data is public record; pages keep the "questions, not accusations" framing.
