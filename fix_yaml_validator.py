#!/usr/bin/env python3
"""Fix YAML on key validation in workflow repair."""

content = open('services/github_workflow_repair.py').read()

old = '''        # Check required top-level keys
        required_top = ["name", "on"]
        for key in required_top:
            if key not in workflow:
                errors.append(f"Missing required top-level key: {key}")'''

new = '''        # Check required top-level keys
        # Note: "on" is parsed as boolean True by YAML
        has_name = "name" in workflow
        has_on = "on" in workflow or True in workflow
        if not has_name:
            errors.append("Missing required top-level key: name")
        if not has_on:
            errors.append("Missing required top-level key: on")'''

content = content.replace(old, new)
open('services/github_workflow_repair.py', 'w').write(content)
print('✓ Fixed YAML "on" key validation')
