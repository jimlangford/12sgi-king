# Gordon Integration for Local AI Systems

This guide enables LOTUS, King-Server, Naga, King-Lotus, Naga-Lotus, and other local AI systems to access Gordon's admin backend.

## Architecture

```
Local AI Systems (LOTUS, King-Server, Naga)
    ↓
Gordon Client Library (services/gordon_client.py)
    ↓
Gordon MCP Server (services/gordon_mcp_server.py)
    ↓
Gordon Admin Backend (api.py:/admin/gordon endpoints)
    ↓
File modifications, page redesigns, Docker assistance
```

## Setup

### 1. Install Dependencies

```bash
cd 12sgi-king
pip install httpx mcp
```

### 2. Configure Gordon Connection

Add to your `.env` or system environment:

```env
# Gordon API connection
GORDON_HOST=localhost
GORDON_PORT=8504
GORDON_API_KEY=dev_key_12345  # For local dev; uses Tailscale in production
GORDON_SYSTEM_NAME=lotus      # Or: king-server, naga, naga-lotus, etc.
```

### 3. Python Client Usage (Direct)

For LOTUS, King-Server, or custom scripts:

```python
from services.gordon_client import GordonClient

# Create client
with GordonClient(system_name="lotus") as client:
    # Check status
    status = client.check_status()
    print(status)
    
    # Ask Gordon
    response = client.query("How do I optimize multi-stage Dockerfile builds?")
    print(response["guidance"])
    
    # Request redesign
    redesign = client.redesign("Add dark mode to the admin dashboard")
    print(redesign["guidance"])
    
    # Request code changes
    modify = client.modify("Add rate limiting to all API endpoints")
    print(modify["guidance"])
```

### 4. MCP Server Setup (For Claude Desktop, LOTUS MCP)

#### Option A: Start MCP Server Manually

```bash
export GORDON_HOST=localhost
export GORDON_PORT=8504
export GORDON_SYSTEM_NAME=lotus

python services/gordon_mcp_server.py
```

#### Option B: Configure in Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "gordon": {
      "command": "python",
      "args": ["/path/to/12sgi-king/services/gordon_mcp_server.py"],
      "env": {
        "GORDON_HOST": "localhost",
        "GORDON_PORT": "8504",
        "GORDON_SYSTEM_NAME": "mcp-client"
      }
    }
  }
}
```

Then restart Claude Desktop.

#### Option C: Configure in LOTUS

Add to LOTUS system configuration:

```yaml
mcp_servers:
  gordon:
    command: python
    args:
      - /path/to/12sgi-king/services/gordon_mcp_server.py
    env:
      GORDON_HOST: localhost
      GORDON_PORT: 8504
      GORDON_SYSTEM_NAME: lotus
```

### 5. Docker Compose Integration

Add to `docker-compose.v2.yml` or your compose file:

```yaml
  gordon-mcp:
    build: { context: ., dockerfile: services/Dockerfile }
    command: ["python", "services/gordon_mcp_server.py"]
    environment:
      GORDON_HOST: localhost
      GORDON_PORT: 8504
      GORDON_SYSTEM_NAME: docker-mcp
    depends_on: [api]  # Ensure genai-stack API is running
    restart: unless-stopped
```

Then the ai/lotus service can reach it:

```yaml
  ai:
    # ... existing config ...
    environment:
      GORDON_MCP_URL: http://gordon-mcp:8000
```

## Usage Examples

### From Python (LOTUS backend)

```python
from services.gordon_client import ask_gordon, gordon_redesign, gordon_modify

# Ask for advice
response = ask_gordon(
    "How do I implement request signing for secure API calls?",
    system_name="lotus"
)
print(response["guidance"])

# Request redesign
redesign = gordon_redesign(
    "Redesign the tenant API to include pagination",
    system_name="lotus"
)

# Request modifications
modify = gordon_modify(
    "Add OpenTelemetry tracing to all FastAPI services",
    system_name="lotus"
)
```

### Via MCP (Claude Desktop, LOTUS MCP)

Once configured, use naturally in Claude:

- "Can you use Gordon to ask how to optimize Neo4j queries?"
- "Request Gordon to redesign the documents API"
- "Have Gordon modify the AI service to add better error handling"

### From King-Server

```python
# services/king_bridge/app/main.py or similar
from services.gordon_client import GordonClient

async def get_model_recommendation():
    with GordonClient(system_name="king-bridge") as client:
        return client.query("What's the best open-source model for document classification?")
```

### From Naga Systems

```python
# naga/main.py or similar
from services.gordon_client import check_gordon_status, ask_gordon

# Check Gordon is ready
status = check_gordon_status(system_name="naga")
if status.get("status") == "authenticated":
    # Ask for guidance
    advice = ask_gordon(
        "How do I implement caching for high-throughput systems?",
        system_name="naga"
    )
```

## API Endpoints (Low-Level)

If using raw HTTP instead of the client library:

### Check Status
```bash
curl -X GET http://localhost:8504/admin/gordon/status \
  -H "X-API-Key: dev_key_12345"
```

### Query
```bash
curl -X POST http://localhost:8504/admin/gordon \
  -H "X-API-Key: dev_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "How do I scale a Neo4j cluster?",
    "action": "query"
  }'
```

### Redesign
```bash
curl -X POST http://localhost:8504/admin/gordon \
  -H "X-API-Key: dev_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Redesign the storage API with versioning",
    "action": "redesign"
  }'
```

### Modify
```bash
curl -X POST http://localhost:8504/admin/gordon \
  -H "X-API-Key: dev_key_12345" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Add comprehensive logging to all services",
    "action": "modify"
  }'
```

## Authorization

- **Production (Tailscale)**: Gordon checks your Tailscale user identity automatically—no credentials needed
- **Local Dev**: Set `GORDON_API_KEY` environment variable; passed in `X-API-Key` header
- **Owner Emails**: jimlangford@me.com, elementlotus@gmail.com, jimmylangford@elementlotus.com, JRCSL@12sgi.com

## Troubleshooting

**"Connection refused"**
- Verify genai-stack API is running: `docker ps | grep api`
- Check GORDON_HOST and GORDON_PORT are correct
- Try: `curl http://localhost:8504/admin/gordon/status`

**"Unauthorized" (403)**
- Verify `GORDON_API_KEY` is set and correct (local dev)
- If using Tailscale, ensure you're accessing via Tailscale
- Check owner emails match your account

**"MCP server not responding"**
- Ensure `pip install mcp` is installed
- Check Python path in MCP config points to correct interpreter
- Try running `python services/gordon_mcp_server.py` directly to see errors

## Files

- `services/gordon_client.py` - Python client library
- `services/gordon_mcp_server.py` - MCP protocol server
- `GORDON_INTEGRATION_LOCAL_AI.md` - This file

## Next Steps

1. Start genai-stack API: `docker compose up` (in Projects/genai-stack)
2. Test Gordon: `python -c "from services.gordon_client import check_gordon_status; print(check_gordon_status())"`
3. Configure LOTUS to use Gordon client
4. Configure King-Server/Naga to access Gordon
5. Set up MCP in Claude Desktop for direct integration
