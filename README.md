# Kilo Aupuni — public civic-transparency site

"Kilo Aupuni" = *observer of the government*. A keyless, public-record watch layer over
**Maui County and the State of Hawaii**: council & legislative votes, campaign money,
procurement, permits, and the patterns between them — published as a free static site.

**This is the publishable subset** of the MauiOS / Kilo Aupuni system. It contains only the
watchers that run on free CI from public data sources. The full local system (renders, gated
property data, iOS router, etc.) stays on the operator's machine.

## How it works
```
GitHub Actions (free cron)  ->  run watchers (public APIs + pypdf)
        |                              writes reports/mauios/*.html + *.json
        v
   build_site.py  ->  site/  (index + dashboards + raw data)
        |
        v
   Cloudflare Pages (free)  ->  served at your custom domain
```
See **SETUP.md** for the 15-minute one-time setup. $0/month.

## Sources (all public record)
- **CivicClerk** — Maui County agendas + minutes (votes, recusals)
- **Hawaii Campaign Spending Commission** (Socrata `jexd-xbcg`) — money, all jurisdictions, 2008+
- **LegiScan** — State Legislature per-member roll-call votes, 2010+ (needs free key)
- **capitol.hawaii.gov** — keyless legislative fallback
- **mauicounty.gov / EnerGov** — bids, permits

## Integrity
Everything is **documented facts + open questions**, never accusations. Correlations (money next
to votes) are leads to verify, with sources linked on every page. See the disclaimers in each report.

## Watchers
`council_watch` · `votes_watch` · `bids_watch` · `mapps_watch` · `donor_watch` ·
`statewide_money` · `lege_legiscan` (+ keyless `lege_watch`) · `commission_watch` ·
`charter_law_map` · `patterns` · `kilo_aupuni` (dashboard). Registry: `watchers/departments.json`.
