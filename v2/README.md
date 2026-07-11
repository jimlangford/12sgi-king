# 12 Stones v2 — Local Owner Node

Private AI operations node. Runs locally on the owner machine. Accessible only via localhost or [Tailscale](https://tailscale.com/) private network. Nothing is exposed to the public internet.

## Architecture

```
Owner Machine
│
├─ Docker Desktop / Docker Engine
│  ├─ 12sgi-v2-app       FastAPI owner dashboard + API   :8088
│  ├─ 12sgi-v2-neo4j     Local graph + vector bus        :7474 / :7687
│  ├─ 12sgi-v2-ollama    Local LLM (Ollama)              :11434
│  └─ 12sgi-v2-tailscale Private network tunnel
│
├─ Secrets (local only — never committed)
│  ├─ secrets/hf_token.txt
│  ├─ secrets/github_token.txt
│  └─ secrets/ts_authkey.txt
│
└─ Tailscale
   ├─ hostname: 12sgi-v2
   └─ only owner devices can connect
```

## What goes where

| System | Purpose |
|---|---|
| **GitHub** | Code, configs, templates, deployment scripts, reports |
| **Hugging Face** | AI models, embeddings, LoRAs, datasets |
| **Docker** | Runs each service locally in containers |
| **Tailscale** | Private network — only your devices can reach v2 |

**Key rule:** tokens, model weights, private data, Maui records, grant docs, and personal records never go in GitHub.

## First-time setup

```bash
git clone https://github.com/jimlangford/12sgi-king.git
cd 12sgi-king/v2

# Create local secret files (never committed)
mkdir -p secrets data models
echo 'hf_your_read_token' > secrets/hf_token.txt
echo 'ghp_your_token'     > secrets/github_token.txt
echo 'tskey-auth-...'     > secrets/ts_authkey.txt
chmod 600 secrets/*.txt
```

## Start / stop

```bash
# Start everything
bash scripts/start.sh

# Check Tailscale
bash scripts/tailscale-check.sh

# Pull a Hugging Face model
bash scripts/pull-models.sh

# Stop
bash scripts/stop.sh
```

## Manual commands

```bash
docker compose up -d --build
docker compose ps

# Health check from the host machine (via port mapping on the tailscale service)
curl http://127.0.0.1:8088/health
curl http://127.0.0.1:8088/graph/status

# From your laptop on the same Tailscale network (MagicDNS or Tailscale IP):
#   curl http://12sgi-v2:8088/health
#   curl http://100.x.x.x:8088/health

# Tailscale status
bash scripts/tailscale-check.sh
docker exec -it 12sgi-v2-tailscale tailscale status
docker exec -it 12sgi-v2-tailscale tailscale ip

# Pull model manually
docker compose exec app python /workspace/app/hf_pull.py
```

## Four processing lanes

1. **INPUT** — agendas, PDFs, public records, farm data, grant data, site content
2. **AI** — summarize, classify, extract, compare, generate, flag risks (local LLM or HF model)
3. **VERIFY** — source links, timestamps, audit logs, human approval, version control
4. **OUTPUT** — approved updates to 12sgi.com, govOS dashboards, testimony, grant packs

V2 does not "think in public." It works privately, verifies evidence, then publishes only clean approved outputs.

## Planned modules

| Module | Status | Purpose |
|---|---|---|
| `v2-core` | scaffold ready | Local dashboard + FastAPI owner node |
| `v2-ingest` | planned | PDFs, agendas, web pages, CSVs → structured data |
| `v2-ai` | planned | Local LLM (Ollama) + Hugging Face model tools |
| `v2-ledger` | planned | Audit log + source traceability per output |
| `v2-reports` | planned | Testimony packs, grant reports, council reports |
| `v2-publish` | planned | Human-approved updates → 12sgi.com / govOS |
| `v2-tailscale` | scaffold ready | Private Tailscale access layer |
| **`v2-explainer`** | **noted** | **Free animated agenda explainer — turns any govOS agenda item into shareable animated fact-cards using premade design assets only. No AI required, no subscription. Wire after v2-core + v2-ingest are stable.** |

## What NOT to do

- Do not expose port 8088 or 11434 publicly (they bind to `127.0.0.1` only)
- Do not commit `.env`, tokens, model weights, private data, or records to GitHub
- Do not let the AI pipeline write to production without human approval
- Do not put admin dashboards on open ports

## Accounts

- GitHub: `jimlangford`
- Hugging Face: `jimmylangford`
- Tailscale: owner account — node hostname `12sgi-v2`

## Token guidance

| Token | Where to get it | Where to put it |
|---|---|---|
| HF read token | hf.co/settings/tokens | `secrets/hf_token.txt` |
| GitHub PAT (read) | github.com/settings/tokens | `secrets/github_token.txt` |
| Tailscale auth key | tailscale.com/admin/settings/keys | `secrets/ts_authkey.txt` |

Use **read-only** tokens wherever possible. Tailscale auth keys should be ephemeral (single-use or short TTL).
