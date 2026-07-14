# WordPress Public Layer Architecture

## Overview

This document defines the separation of concerns between WordPress (public presentation layer) and QUAD OS (private operating layer).

### System Roles

| Component | Role | Visibility |
|-----------|------|-----------|
| **WordPress** | Public website and content | Public-facing |
| **QUAD OS** | Private operating system | Behind the scenes |
| **govOS** | Civic application module | Inside QUAD OS |
| **Element LOTUS** | Creative application module | Inside QUAD OS |

## WordPress: The Public Experience

WordPress serves as the public-facing website and content management system. Visitors interact with WordPress and should never know QUAD OS exists.

### WordPress Responsibilities

- **Pages**: Static public pages (about, contact, services, etc.)
- **Posts**: Published content and announcements
- **Media**: Images, videos, documents for public consumption
- **SEO**: Search engine optimization and discoverability
- **Public Forms**: Visitor-facing contact and submission forms
- **Public Releases**: Announcements, blog posts, updates

### WordPress Characteristics

- Fast, polished, professional appearance
- Clean, intuitive navigation
- SEO-optimized content
- Public visibility across search engines
- Public API endpoints (WordPress REST API)
- Application Password authentication
- Jetpack integration for WordPress.com sites

## QUAD OS: The Private Operating Layer

QUAD OS is the private orchestration system that powers civic and creative workflows. It remains completely invisible to public visitors.

### QUAD OS Responsibilities

- **AI Orchestration**: Language models, decision trees, automation
- **Case Management**: Internal tracking, workflow states, history
- **Work Board**: Team collaboration and task tracking
- **Health Monitoring**: System status, performance metrics, alerts
- **Deployments**: Release management, version control, rollback
- **Internal APIs**: Backend services, webhooks, integrations
- **Background Jobs**: Scheduled tasks, async processing, queues

### QUAD OS Characteristics

- Private, internal-only access
- Complex operational workflows
- AI and automation-driven
- No public-facing endpoints (except publishing to WordPress)
- Internal authentication and authorization
- Sophisticated monitoring and logging

## Publishing Bridge

The only connection from QUAD OS to WordPress is the **automated publishing workflow** (`wp-publish.yml`). This workflow:

- Runs manually via `workflow_dispatch` with deliberate status choice
- Defaults to **draft** (never auto-publish to production)
- Publishes only when explicitly triggered by authorized personnel
- Never exposes QUAD OS internals to public
- Uses WordPress REST API (primary) or Jetpack (fallback)
- Records post ID and URL for reviewer validation

### Publishing Workflow Safety Guarantees

- ✅ Default post status: **draft**
- ✅ Manual publication: Never automatic
- ✅ Status choice: Explicit `draft` or `publish` selection required
- ✅ Credentials masked: No secrets printed in logs
- ✅ Proper validation: HTTP 2xx required, fails on errors
- ✅ Retry logic: Exponential backoff on transient failures
- ✅ No production bypass: Workflow cannot modify `main` branch or deploy QUAD OS

## Architecture Principles

### 1. Separation of Concerns

WordPress and QUAD OS are independent systems with clearly defined boundaries. Neither should depend on the other's internals.

### 2. Public vs. Private

Everything public goes through WordPress. Everything private stays in QUAD OS. There is no middle ground.

### 3. Intentional Publishing

Publishing to WordPress is always a deliberate human decision. Automation may prepare drafts, but publishing requires explicit approval.

### 4. No Operational Exposure

Visitors should experience a fast, polished WordPress website. They should never see:
- QUAD OS configuration
- Deployment details
- AI orchestration logic
- Internal API documentation
- System monitoring data
- Operational complexity

### 5. Visitor Experience

From a visitor's perspective:
- Fast, responsive WordPress website
- Professional content and media
- Clear information architecture
- Accessible forms and interactions
- No technical debt visible

### 6. Backend Sophistication

Behind WordPress:
- QUAD OS handles all workflow automation
- AI makes intelligent decisions
- Civic and creative modules operate independently
- Health monitoring ensures reliability
- Internal APIs power integrations

## Integration Points

### WordPress → QUAD OS

Limited to specific use cases:
- **Public form submissions**: WordPress captures visitor input, sends to QUAD OS for processing
- **Public releases**: WordPress publishes announcements; QUAD OS provides content (as drafts)

### QUAD OS → WordPress

Restricted to publishing only:
- **Draft posts**: QUAD OS prepares draft content via `wp-publish.yml`
- **Manual approval**: WordPress administrators review and approve publishing
- **No direct content modification**: QUAD OS cannot edit existing WordPress content

## Configuration

See `.env.example` for required environment variables:

```
WP_URL=
WP_USER=
WP_APP_PASSWORD=
JETPACK_TOKEN=
JETPACK_SITE_ID=
WP_DEFAULT_STATUS=draft
```

Entitlement bridge config (source-controlled, no secrets):

- Canonical tier map: `/home/runner/work/12sgi-king/12sgi-king/config/entitlement_map.json`
- Bridge implementation: `/home/runner/work/12sgi-king/12sgi-king/services/entitlements.py`

This keeps authority split explicit:
- PUBLIC authority: WordPress/Jetpack/WooCommerce access state
- PRIVATE authority: QUAD OS workflow + internal surfaces
- BRIDGE payload: identity + entitlement assertions only

**Never commit secrets.** Store actual values in GitHub repository secrets.

## Element Lotus Rebuild Source Bundle

The actual Element Lotus page/template rebuild happens in WordPress itself, but the repo remains the
source blueprint.

- Source shell: `/home/runner/work/12sgi-king/12sgi-king/element_lotus_public/`
- Builder: `/home/runner/work/12sgi-king/12sgi-king/watchers/deploy_elementlotus_wp.py`
- Output bundle: `/home/runner/work/12sgi-king/12sgi-king/content/wordpress/element_lotus/`

Run:

```bash
python /home/runner/work/12sgi-king/12sgi-king/watchers/deploy_elementlotus_wp.py
```

Operational rule:

- whenever `/home/runner/work/12sgi-king/12sgi-king/element_lotus_public/` changes, rerun the builder above
- then paste/apply the refreshed bundle from `/home/runner/work/12sgi-king/12sgi-king/content/wordpress/element_lotus/` into WordPress
- `python -m unittest tests.test_deploy_elementlotus_wp` now fails if the committed WordPress bundle drifts from the public shell source

The bundle generates:

- one WordPress-ready page fragment per public Element Lotus page
- scoped CSS for WordPress (`additional-css.css`)
- a manifest describing slugs, templates, titles, and source files

Boundary rules enforced by this bundle:

- WordPress-owned public pages stay on WordPress routes (`/`, `/about/`, `/contact/`, `/films/`, `/music/`, `/civic/`)
- static playables and civic artifacts stay on the 12sgi bridge (`https://12sgi.com/games/`, `https://12sgi.com/sage/`, `https://12sgi.com/reports.html`, etc.)
- private/owner-only surfaces are not added to the WordPress bundle

## Launch Center (Owner Publishing Dashboard)

The **Launch Center** (`king_public_src/LaunchCenter.dc.html`) is the owner's
single-pane view of the publishing pipeline.  It is an owner-only panel in the
Naga console (sign-in required; never public) that reads the
**media catalog** (`watchers/media_catalog.py` / `data/media_catalog.jsonl`).

### What it shows

Each content item becomes one card with four sections:

- **Asset checklist** — video rendered · transcript · thumbnail · social package · metadata
- **WordPress row** — draft ID, draft URL, current WP status
- **Platform grid** — per-platform status badges (queued / draft / published / failed)
- **Approval badges** — which approval gates (editorial / legal / corporate / rights) are cleared

### Tabs

| Tab | Contents |
|-----|----------|
| **Drafts** | WP draft exists, approvals incomplete |
| **Ready** | All required approvals cleared, not yet published |
| **Published** | Live on ≥1 platform |
| **Needs Attention** | Any platform in `failed` state |

### Approval types

`services/v2_workboard.py` now supports multi-gate approval via `--approval-type`:

```
python -m services.v2_workboard --approve <job_id> --approver owner --approval-type editorial
python -m services.v2_workboard --approve <job_id> --approver legal  --approval-type legal
```

Available types: `editorial` (default) · `legal` · `corporate` · `rights`

All required types must be cleared before a job passes
`all_required_approvals_met()` and is eligible for publish.

### Pipeline boundary

WordPress remains the *preview and public presentation* surface.  The Launch
Center is the *editorial decision* surface.  Nothing reaches any platform without:

1. A WordPress draft registered in the media catalog
2. All required approval types cleared in the workboard log
3. An explicit `tools/publish_approved_social.py` call per
   `docs/SOCIAL_CONNECTORS.md` — fail-closed, no tombstone = no post.

## Branch Working-Space Pages (private, per tenant per department)

Mirrors the existing Hawaii County pattern: 4 private WordPress pages per tenant (Council /
Counsel / Executive / Judicial), each restricted via WordPress's `Groups` taxonomy to the matching
department. Content is generated from real, already-sourced civic reports -- no fabrication, and
every link is checked against disk before being included so a renamed/missing report can never
produce a dead link.

- Generator: `watchers/wp_branch_pages.py --tenant <id> --all`
- Blueprint output (repo source of record): `content/wordpress/branch_pages/<tenant>/`
- Sync to live WordPress: `.github/workflows/wp-branch-pages-sync.yml` (`workflow_dispatch`)
  - `dry_run` defaults to **true** -- searches WordPress by exact page title and reports what
    would change; writes nothing.
  - Set `dry_run=false` to push updates to existing pages found by title match.
  - Set `dry_run=false` + `create_missing=true` to create a page that has no title match --
    always created as a **draft**, never auto-published, and never auto-tagged with a Group (the
    owner assigns the correct Group manually in WP admin, same as every other access-restricted
    page on the site).

**Boundary preserved:** this workflow only ever touches pages, never Group/taxonomy access
assignments -- who can see a working space stays a deliberate, manual WordPress-admin decision.

### Auth: Jetpack OAuth2 is the standard path for this site (owner-confirmed)

Because this site is WordPress.com-hosted, `JETPACK_TOKEN` + `JETPACK_SITE_ID` (WordPress.com REST
API v1.1, `wp-branch-pages-sync.yml`'s Jetpack fallback step) is the confirmed auth path -- not the
Application Password path. One-time setup, owner-only (do this locally, never in a shared chat):

1. **Find `JETPACK_SITE_ID`**: your site's numeric ID or domain works. Quickest way while logged
   into WordPress.com: visit `https://public-api.wordpress.com/rest/v1.1/sites/<yourdomain>` in a
   browser (no auth needed for this lookup) and read the `"ID"` field from the JSON response.
2. **Register a WordPress.com application** at <https://developer.wordpress.com/apps/> → "Create
   New Application". Redirect URI can be anything you control (e.g.
   `https://12sgi.com/oauth/callback`) since you'll copy the `code` manually. Note the
   `client_id` and `client_secret` it gives you.
3. **Authorize once in a browser** — visit:
   `https://public-api.wordpress.com/oauth2/authorize?client_id=<CLIENT_ID>&redirect_uri=<REDIRECT_URI>&response_type=code&scope=global`
   Log in, approve, and you'll be redirected to your redirect URI with `?code=...` in the URL —
   copy that `code`.
4. **Exchange the code for a token** (one local `curl`, run once):
   ```
   curl -s https://public-api.wordpress.com/oauth2/token \
     -d client_id=<CLIENT_ID> \
     -d client_secret=<CLIENT_SECRET> \
     -d redirect_uri=<REDIRECT_URI> \
     -d grant_type=authorization_code \
     -d code=<CODE_FROM_STEP_3>
   ```
   The response's `access_token` is your `JETPACK_TOKEN`. WordPress.com access tokens obtained this
   way do not expire on a fixed schedule (no refresh-token dance needed) — they're valid until you
   revoke the app's access in WordPress.com account settings.
5. **Store both as repo secrets** (run locally, never paste the value in chat):
   ```
   gh secret set JETPACK_TOKEN
   gh secret set JETPACK_SITE_ID
   ```
6. **Dispatch `wp-branch-pages-sync.yml`** with `dry_run=true` first to confirm the Jetpack path
   picks up and reports `[FOUND]`/`[NOT FOUND]` per page title, then `dry_run=false` to go live.

This same `JETPACK_TOKEN`/`JETPACK_SITE_ID` pair also unblocks `wp-publish.yml`'s existing Jetpack
fallback for release posts — one credential covers both workflows.

## Monitoring

Monitor the publishing workflow via:
- GitHub Actions logs (filtered for [Attempt X/3] messages)
- GitHub Actions summary (records post ID and URL)
- WordPress post history (review draft and published posts)
- QUAD OS logs (verify automation initiated correctly)

## Future Considerations

- Webhook support for WordPress → QUAD OS notifications
- Bulk publishing for multi-site WordPress networks
- Custom post types specific to govOS or Element LOTUS
- Media synchronization between systems
- Analytics bridge (public stats in WordPress, internal metrics in QUAD OS)

## References

- WordPress REST API: https://developer.wordpress.org/rest-api/
- WordPress Application Passwords: https://developer.wordpress.org/plugins/authentication/basic-auth/
- Jetpack API: https://jetpack.com/support/jetpack-api/
- QUAD OS Documentation: (internal)
- govOS Documentation: (internal)
- Element LOTUS Documentation: (internal)
