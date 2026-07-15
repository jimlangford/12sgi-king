#!/usr/bin/env python3
import os
from pathlib import Path

bridge_file = Path("services/king_bridge/app/main.py")
content = bridge_file.read_text()

if "StaticFiles" not in content:
    addition = '''

# Serve static HTML pages from element_lotus_public
from fastapi.staticfiles import StaticFiles

static_dir = Path(__file__).parents[3] / "element_lotus_public"
if static_dir.exists():
    try:
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="public")
    except Exception:
        pass
'''
    content += addition
    bridge_file.write_text(content)
    print("✓ Updated king_bridge to serve static files")
else:
    print("✓ StaticFiles already configured")
