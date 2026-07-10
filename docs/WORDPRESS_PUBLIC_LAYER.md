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

The bundle generates:

- one WordPress-ready page fragment per public Element Lotus page
- scoped CSS for WordPress (`additional-css.css`)
- a manifest describing slugs, templates, titles, and source files

Boundary rules enforced by this bundle:

- WordPress-owned public pages stay on WordPress routes (`/`, `/about/`, `/contact/`, `/films/`, `/music/`, `/civic/`)
- static playables and civic artifacts stay on the 12sgi bridge (`https://12sgi.com/games/`, `https://12sgi.com/sage/`, `https://12sgi.com/reports.html`, etc.)
- private/owner-only surfaces are not added to the WordPress bundle

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
