# services/connectors — per-platform OAuth token lifecycle for the MCP connector layer.
#
# Architecture:
#   token_store.py  — SQLite-backed store for platform access/refresh tokens
#   registry.py     — platform registry: status, silent refresh, OAuth redirect URLs
#
# Usage from v2/app/main.py:
#   from services.connectors.registry import connector_registry
#   status = connector_registry.status_all()          # dict of platform → status card
#   ok     = connector_registry.refresh("youtube")    # attempt silent refresh
#   url    = connector_registry.authorize_url("youtube", return_to="...")  # OAuth start
