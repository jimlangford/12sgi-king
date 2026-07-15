#!/usr/bin/env python3
from pathlib import Path

# Read the current file
bridge_file = Path("services/king_bridge/app/main.py")
lines = bridge_file.read_text().split('\n')

# Remove the old static mount lines at the end
while lines and ('StaticFiles' in lines[-1] or 'app.mount' in lines[-1] or 'except' in lines[-1] or 'pass' in lines[-1]):
    lines.pop()

# Trim trailing blank lines
while lines and lines[-1].strip() == '':
    lines.pop()

# Add the new route
new_lines = [
    "",
    "# Serve owner_jobs.html from element_lotus_public",
    "@app.get(\"/owner_jobs.html\")",
    "async def serve_owner_jobs():",
    "    from fastapi.responses import FileResponse",
    "    html_path = Path(__file__).parents[3] / \"element_lotus_public\" / \"owner_jobs.html\"",
    "    if html_path.exists():",
    "        return FileResponse(html_path, media_type=\"text/html\")",
    "    raise HTTPException(status_code=404, detail=\"owner_jobs.html not found\")",
]

content = '\n'.join(lines) + '\n' + '\n'.join(new_lines)
bridge_file.write_text(content)
print("✓ Updated king_bridge to serve /owner_jobs.html")
