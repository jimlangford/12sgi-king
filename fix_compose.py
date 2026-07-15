#!/usr/bin/env python3
import sys
content = open('docker-compose.v2.yml').read()
insert_point = content.rfind('\nvolumes:')
service_def = '''
  github-workflow-monitor:
    build: { context: ., dockerfile: services/Dockerfile }
    command: ["python", "-m", "services.github_workflow_monitor_service"]
    environment:
      <<: *common-env
      GITHUB_TOKEN: ${GITHUB_TOKEN:-}
      GITHUB_OWNER: ${GITHUB_OWNER:-jimlangford}
      GITHUB_REPO: ${GITHUB_REPO:-12sgi-king}
      GITHUB_WORKFLOW_MONITOR_ENABLED: ${GITHUB_WORKFLOW_MONITOR_ENABLED:-true}
      GITHUB_REPAIR_LOOKBACK_MINUTES: ${GITHUB_REPAIR_LOOKBACK_MINUTES:-60}
      GITHUB_REPAIR_INTERVAL_SECONDS: ${GITHUB_REPAIR_INTERVAL_SECONDS:-300}
      GITHUB_REPAIR_AUTONOMY_THRESHOLD: ${GITHUB_REPAIR_AUTONOMY_THRESHOLD:-75}
      GITHUB_REPAIR_MAX_CONCURRENT: ${GITHUB_REPAIR_MAX_CONCURRENT:-3}
      GITHUB_AUTO_REPAIR_DRY_RUN: ${GITHUB_AUTO_REPAIR_DRY_RUN:-false}
      REPO_PATH: /repo
    volumes:
      - v2-db:/data/db
      - v2-dispatch:/data/dispatch
      - .:/repo
    depends_on: [king-bridge]
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
'''
new_content = content[:insert_point] + '\n' + service_def + content[insert_point:]
open('docker-compose.v2.yml', 'w').write(new_content)
print('✓ Added github-workflow-monitor service')
