#!/usr/bin/env python3
"""Add billing detection to github_workflow_monitor.py"""
import re

content = open('services/github_workflow_monitor.py').read()

# Find the method and insert billing check after the first early-return
insert_after = '        if not logs:\n            return None, 0'
billing_check = '''
        # Billing/account suspension is not a code problem — skip silently
        billing_markers = [
            r"account is locked due to a billing",
            r"billing issue",
            r"account locked",
            r"exceeded.*spending limit",
            r"payment.*required",
        ]
        for marker in billing_markers:
            if re.search(marker, logs, re.IGNORECASE):
                logger.info("Skipping run: GitHub billing suspension (not a code error)")
                return None, 0
'''

if insert_after in content:
    content = content.replace(insert_after, insert_after + billing_check)
    open('services/github_workflow_monitor.py', 'w').write(content)
    print('Added billing detection to monitor')
else:
    print('Pattern not found')
