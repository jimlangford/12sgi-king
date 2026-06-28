# Agent Operating Guide

This repository is not only a public website. It is a layered operating system with public civic pages, private owner controls, mirrors, deployment bridges, and local automation. Work here with care, humility, and aloha.

Before changing files, read `CANON.md` as the compact standing memory for JRCSL / 12SGI / Elemental Lotus work. Apply it quietly; do not spend response space restating it unless a boundary or handoff depends on it.

## Core Principle

Preserve intention before changing mechanism.

Do not treat unusual infrastructure as broken just because it does not match a generic web deployment pattern. Cloudflare, GitHub Pages, Tailscale, local `Documents/Claude/...` paths, `king-local`, private reports, public sanitizers, and mirror scripts may all be intentional parts of the system.

## Boundary Labels

Use these labels in reports and handoffs:

- `PUBLIC`: safe published website output.
- `PRIVATE`: owner-only control plane, local mirror, Tailscale, private data room, or non-public report.
- `BRIDGE`: connection layer between local tools, GitHub Actions, Cloudflare, GitHub Pages, Tailscale, or mirrors.
- `DO NOT TOUCH`: intentional infrastructure unless the owner explicitly asks for changes.
- `VERIFY`: commands run and results observed.

## Do No Harm Rules

- Do not remove or "simplify" private connection paths, Cloudflare notes, Tailscale hosts, local mirror logic, owner-only reports, or deployment bridges without explicit instruction.
- Do not publish private files or owner-only pages into the public `site/` output.
- Do not rewrite setup docs just because the visible workflow appears to use a different deployment path.
- Do not flatten the system into a standard static-site template.
- Keep changes narrow, reversible, and aligned with existing comments and scripts.

## Reporting Format

When reporting work, use language another agent can continue from:

1. `INSPECTED`: files, workflows, tools, or GitHub surfaces checked.
2. `CHANGED`: exact files and purpose.
3. `PRESERVED`: private/public boundaries intentionally left intact.
4. `VERIFY`: commands run and whether they passed.
5. `NEXT`: safest next action, if any.

## Local Validation

Known lightweight checks:

```powershell
python -m compileall -q .
python tools\reconcile.py --gate seed_reports html --route-only
$env:KA_SITE='C:\tmp\12sgi-king-site-check'; python build_site.py
```

The default `site/` tree can be touched by local tools or file watchers. If a direct `python build_site.py` hits a Windows file lock, prefer a redirected `KA_SITE` build before assuming the build is broken.

## Spirit Of The Work

Move with Christ aloha: truthful, careful, protective, and useful. Strengthen the system without harming the people, private pathways, or trust boundaries it serves.
