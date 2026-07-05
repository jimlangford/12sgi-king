# Health service

The FastAPI-based health service lives under /services/health (already present on the integration branch). This README links to that service and explains ownership.

Purpose

- Provide /api/v1/live, /api/v1/ready, /api/v1/health and /admin/status

Ownership

- Platform / SRE

Next steps

- Ensure deployment provides RELEASE_FILE and ADMIN_ALLOWED_IPS or ADMIN_BASIC_* for admin protection
