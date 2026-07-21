# Shared image for the govOS v2 backend (auth/tenant/documents/storage/ai/health/gpu-router).
#
# Built from the repo root (see docker-compose.v2.yml `build.context: .`), because several
# services import `services.v2_workboard` as a top-level package relative to the repo root
# (see services/tenant/app/main.py, services/documents/app/main.py, services/storage/app/main.py,
# services/ai/app/main.py). One image, one dependency set; docker-compose.v2.yml picks which
# service module to run per-container via CMD/entrypoint args.
FROM python:3.12-slim

WORKDIR /repo

# espeak-ng: required for the voice CPU lane (text-to-speech synthesis via espeak-ng).
# libespeak-ng1 is the runtime library; espeak-ng-data provides the voice data files
# (including Hawaiian 'haw' and English variants). ffmpeg is used by audio post-processing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    espeak-ng-data \
    && rm -rf /var/lib/apt/lists/*

# Union of services/*/requirements.txt (fastapi, uvicorn[standard], requests, python-dotenv).
# Current services: auth, tenant, documents, storage, ai, health, gpu-router, king-bridge, board-api, connector-runner, github-workflow-monitor.
COPY services/auth/requirements.txt /tmp/req-auth.txt
COPY services/tenant/requirements.txt /tmp/req-tenant.txt
COPY services/documents/requirements.txt /tmp/req-documents.txt
COPY services/storage/requirements.txt /tmp/req-storage.txt
COPY services/ai/requirements.txt /tmp/req-ai.txt
COPY services/health/requirements.txt /tmp/req-health.txt
COPY services/gpu_router/requirements.txt /tmp/req-gpu-router.txt
COPY services/king_bridge/requirements.txt /tmp/req-king-bridge.txt
COPY services/board_api/requirements.txt /tmp/req-board-api.txt
RUN cat /tmp/req-*.txt | sort -u > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Bring in only what the v2 backend needs at runtime (not the whole civic site/watchers tree).
COPY services/ /repo/services/
COPY element_lotus_public/ /repo/element_lotus_public/

# Non-root runtime (2026-07-09 fleet review V2-DOCK-3). uvicorn binds ports >1024 (8000/8101-8107)
# and needs ZERO Linux capabilities, so nothing here requires root. Running as an unprivileged uid
# shrinks the blast radius of any future dependency-CVE / endpoint compromise on the owner's machine.
# /data (the named volumes v2-db + v2-dispatch, mounted by compose) must be writable by this uid --
# Docker creates named-volume mount points owned by the container's runtime user on first mount, and
# these services only ever write under /data, so uid 10001 owning nothing at build time is fine.
RUN useradd -u 10001 -m -s /usr/sbin/nologin app \
    && mkdir -p /data/db /data/dispatch \
    && chown -R app:app /data /repo
USER app

EXPOSE 8000 8101 8102 8103 8104 8105 8107 8109 8799

# Overridden per-service by docker-compose.v2.yml `command:`.
CMD ["python", "-m", "uvicorn", "services.health.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
