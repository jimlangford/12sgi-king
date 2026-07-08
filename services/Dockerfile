# Shared image for the govOS v2 backend (auth/tenant/documents/storage/ai/health/gpu-router).
#
# Built from the repo root (see docker-compose.v2.yml `build.context: .`), because several
# services import `services.v2_workboard` as a top-level package relative to the repo root
# (see services/tenant/app/main.py, services/documents/app/main.py, services/storage/app/main.py,
# services/ai/app/main.py). One image, one dependency set; docker-compose.v2.yml picks which
# service module to run per-container via CMD/entrypoint args.
FROM python:3.12-slim

WORKDIR /repo

# Union of services/*/requirements.txt (fastapi, uvicorn[standard], requests, python-dotenv).
COPY services/auth/requirements.txt /tmp/req-auth.txt
COPY services/tenant/requirements.txt /tmp/req-tenant.txt
COPY services/documents/requirements.txt /tmp/req-documents.txt
COPY services/storage/requirements.txt /tmp/req-storage.txt
COPY services/ai/requirements.txt /tmp/req-ai.txt
COPY services/health/requirements.txt /tmp/req-health.txt
COPY services/gpu_router/requirements.txt /tmp/req-gpu-router.txt
RUN cat /tmp/req-*.txt | sort -u > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Bring in only what the v2 backend needs at runtime (not the whole civic site/watchers tree).
COPY services/ /repo/services/

EXPOSE 8000 8101 8102 8103 8104 8105 8107

# Overridden per-service by docker-compose.v2.yml `command:`.
CMD ["python", "-m", "uvicorn", "services.health.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
