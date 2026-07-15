#!/usr/bin/env python3
"""Fix neo4j strict validation env var and known_issues in docker-compose.v2.yml"""
content = open('docker-compose.v2.yml').read()

for line in content.splitlines():
    if 'strict' in line.lower() or 'NEO4J_server' in line:
        print('Current:', repr(line))

# neo4j 5.23+ renamed the key; also the real fix is ensuring bolt connector
# is properly configured. Simplest: remove the strict validation line entirely
# since NEO4J_AUTH=none is sufficient for our local-only setup.
import re
# Remove the strict validation line
new = re.sub(r'\s*NEO4J_server_config_strict__validation_enabled:.*\n', '\n', content)
if new != content:
    open('docker-compose.v2.yml', 'w').write(new)
    print('Removed problematic strict_validation line')
else:
    print('Line not found - checking for variant')
    new2 = re.sub(r'\s*NEO4J_server_config_strict.*\n', '\n', content)
    if new2 != content:
        open('docker-compose.v2.yml', 'w').write(new2)
        print('Removed strict validation variant')
    else:
        print('Not found at all - may already be fixed')
