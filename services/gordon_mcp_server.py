"""
Gordon MCP (Model Context Protocol) Server
Exposes Gordon admin capabilities to Claude, LOTUS, and other MCP clients.
Allows local AI systems to query, redesign, and modify backend systems via Gordon.

Usage:
    python services/gordon_mcp_server.py

Then configure in Claude Desktop or LOTUS MCP config:
```json
{
  "mcpServers": {
    "gordon": {
      "command": "python",
      "args": ["-m", "services.gordon_mcp_server"],
      "env": {
        "GORDON_HOST": "localhost",
        "GORDON_PORT": "8504",
        "GORDON_API_KEY": "your_dev_key_if_needed"
      }
    }
  }
}
```
"""

import json
import os
from typing import Any
from services.gordon_client import GordonClient, GordonAction

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        ToolResult,
        Attachment,
    )
except ImportError:
    raise ImportError(
        "MCP SDK not installed. Install with: pip install mcp"
    )


# Initialize MCP server
server = Server("gordon")
gordon_host = os.getenv("GORDON_HOST", "localhost")
gordon_port = int(os.getenv("GORDON_PORT", "8504"))
system_name = os.getenv("GORDON_SYSTEM_NAME", "mcp-client")


@server.list_tools()
async def list_tools():
    """List available Gordon tools."""
    return [
        Tool(
            name="gordon_status",
            description="Check if Gordon is accessible and verify authentication",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="gordon_query",
            description="Ask Gordon for Docker/development advice and best practices",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Your question for Gordon (Docker, containers, CI/CD, etc.)"
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="gordon_redesign",
            description="Request Gordon to redesign backend pages, APIs, or components",
            inputSchema={
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": "Description of what to redesign (e.g., 'Add dark mode to admin dashboard')"
                    }
                },
                "required": ["request"]
            }
        ),
        Tool(
            name="gordon_modify",
            description="Request Gordon to modify backend files or add functionality",
            inputSchema={
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": "Description of code changes needed (e.g., 'Add request logging to api.py')"
                    }
                },
                "required": ["request"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> ToolResult:
    """Execute Gordon tools."""
    with GordonClient(
        host=gordon_host,
        port=gordon_port,
        system_name=system_name
    ) as client:
        try:
            if name == "gordon_status":
                result = client.check_status()

            elif name == "gordon_query":
                result = client.query(arguments["question"])

            elif name == "gordon_redesign":
                result = client.redesign(arguments["request"])

            elif name == "gordon_modify":
                result = client.modify(arguments["request"])

            else:
                result = {"error": f"Unknown tool: {name}"}

            # Format response for MCP
            response_text = json.dumps(result, indent=2)
            return ToolResult(
                content=[TextContent(type="text", text=response_text)],
                is_error="error" in result or "status_code" in result
            )

        except Exception as e:
            error_text = f"Tool execution failed: {str(e)}"
            return ToolResult(
                content=[TextContent(type="text", text=error_text)],
                is_error=True
            )


async def main():
    """Run the MCP server."""
    async with stdio_server(server) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
