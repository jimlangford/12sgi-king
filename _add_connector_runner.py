#!/usr/bin/env python3
# Inject connector-runner service into docker-compose.v2.yml

import yaml

with open('docker-compose.v2.yml', 'r') as f:
    compose = yaml.safe_load(f)

connector_runner = {
    'build': {'context': '.', 'dockerfile': 'services/Dockerfile'},
    'command': ['python', 'services/connectors/runner.py'],
    'environment': {
        'CONNECTOR_REFRESH_INTERVAL': '${CONNECTOR_REFRESH_INTERVAL:-3600}',
        'CONNECTOR_TOKEN_DB': '/data/db/connector_tokens.db',
        'WORKBOARD_ENABLED': '1',
    },
    'volumes': [
        'v2-db:/data/db',
        'v2-dispatch:/data/dispatch',
    ],
    'depends_on': ['auth', 'king-bridge'],
    'restart': 'unless-stopped',
    'logging': {
        'driver': 'json-file',
        'options': {
            'max-size': '5m',
            'max-file': '2',
        }
    }
}

# Insert before github-workflow-monitor
services = compose['services']
keys = list(services.keys())
idx = keys.index('github-workflow-monitor')
new_keys = keys[:idx] + ['connector-runner'] + keys[idx:]

new_services = {}
for k in new_keys:
    if k == 'connector-runner':
        new_services[k] = connector_runner
    else:
        new_services[k] = services[k]

compose['services'] = new_services

with open('docker-compose.v2.yml', 'w') as f:
    yaml.safe_dump(compose, f, default_flow_style=False, sort_keys=False)

print("✓ Connector runner service added to docker-compose.v2.yml")
