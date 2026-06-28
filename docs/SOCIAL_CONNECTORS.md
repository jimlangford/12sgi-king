# Social Connector Operating Policy

This policy applies to TikTok, YouTube, Instagram, Facebook, X, email, Stripe/customer messaging, and any future social or business connector used by 12SGI / govOS / Elemental Lotus.

## Core Rule

Social connectors are `BRIDGE` systems. They may distribute approved public material, but they must not publish private commentary, subscriber-only work, owner-only evidence, credentials, local mirror state, or unreviewed generated output.

## Connector Priority

Use existing MCP connectors, installed apps, and approved first-party integrations as the high-priority path before adding new browser automation, scripts, credentials, or custom API clients.

Preferred order:

1. Existing MCP connector or installed app with clear permissions.
2. Existing repo script that already follows this policy.
3. First-party platform API with scoped credentials and audit logs.
4. Browser automation only for gaps that cannot be handled safely above.
5. Manual operator action when policy, terms, authentication, or rights are uncertain.

Do not create duplicate connector paths for the same platform unless there is a documented reason and a clear owner-approved rollback path.

## Channel Boundaries

- `PUBLIC`: civic explainers, public-record dashboards, public launch pages, public testimony calls, public educational clips.
- `SUBSCRIBER`: per-seat commentary, paid analysis, private email delivery, customer-specific dashboards.
- `PRIVATE`: owner keys, evidence files, Tailscale/private mirror paths, browser sessions, cookies, connector credentials, unpublished strategy.
- `BRIDGE`: render queues, approval manifests, connector scripts, browser automation, webhook handlers, post logs.

## Build vs Publish

The site build may generate assets and metadata. It must not auto-post to social platforms simply because a server rebooted or `build_site.py` ran.

Use this lifecycle:

1. `BUILD`: generate static site, reports, captions, reels, thumbnails, metadata.
2. `STAGE`: place public-ready assets into a queue with a manifest.
3. `REVIEW`: owner approves source, caption, channel, and rights.
4. `PUBLISH`: connector posts only approved queue items.
5. `LOG`: record platform, URL, timestamp, account, caption, source commit, and status.
6. `FAIL CLOSED`: missing auth, missing approval, reboot, lock conflict, or connector error leaves content staged.

## Reboot Safety

Connector services may restart on reboot, but restart must not equal publish.

Required controls:

- queue status must be `approved` before posting
- connector must acquire a lock before posting
- connector must write `publishing` before upload and `posted` only after URL capture
- connector must not post anything already marked `posted`
- connector must leave ambiguous failures as `needs_review`

## Per-Seat Content

The govOS Commentary Seat is subscriber-private and licensed per recipient seat. It is not approved for rebroadcast, reposting, resale, or redistribution.

Do not send per-seat commentary to TikTok, YouTube, public feeds, or public email lists. Public platforms may receive only public civic explainer assets.

## Business Plan Readiness

Before upgrading any connector or platform plan, confirm:

- account ownership and recovery access
- business name, billing owner, and admin roles
- two-factor authentication
- brand handles and channel map
- allowed content categories
- private/subscriber/public boundaries
- data export and audit-log access
- API or automation terms of service
- rate limits and daily posting caps
- revocation path if a connector misbehaves

## Manifest Shape

Use a structured queue item for every social post:

```json
{
  "id": "agenda-YYYYMMDD-item",
  "status": "staged",
  "channel": "tiktok",
  "source_commit": "",
  "source_url": "",
  "asset_path": "",
  "caption": "",
  "rights": "public-civic-explainer-only",
  "approved_by": "",
  "approved_at": "",
  "posted_url": "",
  "posted_at": "",
  "error": ""
}
```

## Agent Reporting

When touching connector work, report:

1. `INSPECTED`: connector scripts, queue files, channel references.
2. `CHANGED`: exact files and behavior.
3. `PRESERVED`: private/subscriber/public boundaries.
4. `VERIFY`: build, queue validation, dry run, or live post check.
5. `NEXT`: safest next action.
