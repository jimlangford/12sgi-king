# AI change broadcast contract

## Purpose

Keep Claude Code, Codex, GitHub Copilot, and the local AI aligned on material
repository changes. Agents share files and Git history, not live chat memory.
The append-only, repository-visible feed is `docs/AI_CHANGE_FEED.jsonl`.

## Required workflow

1. At session start, read this contract, the latest entries in the feed, and
   `docs/ACTIVE_AGENT_HANDOFF.md`.
2. After a material change is ready for another agent to act on, append one
   notice with:

   ```powershell
   python tools/announce_ai_change.py `
     --actor "Codex" `
     --summary "Describe the completed change and its user impact" `
     --boundary BRIDGE `
     --audience local-ai --audience claude-code --audience codex --audience github-copilot `
     --path services/example.py `
     --evidence "Focused validation passed; no deployment performed"
   ```

3. Include outcome, validation, blockers, and next action in the active handoff.
   Keep uncommitted work clearly labeled; never imply GitHub or runtime delivery.
4. Commit/push the notice with its associated reviewed work when appropriate.
   GitHub-connected agents can only see it after that push. A local agent can
   read an uncommitted notice from the shared checkout.

## Scope and safety

- Publish only `PUBLIC` or `BRIDGE` metadata to the shared feed. PRIVATE,
  owner-only, `DO NOT TOUCH`, and unverified sensitive details stay in the
  appropriate local/private handoff. The publisher rejects those boundaries,
  credential-like strings, absolute local paths, and known private path names.
- Summaries describe changes; do not paste source, user data, tokens, private
  reports, or machine-specific paths. List only safe repository-relative paths.
- The feed is discoverable shared context, not a direct message. It does not
  invoke an external model, notify a live Claude/Copilot/Codex chat, push code,
  create a PR comment, or deploy. Those require a separate configured delivery
  connector and their own authorization.
- Record each meaningful change set once. Do not emit an event for every save;
  include failed/blocked outcomes when they affect another agent's next action.

This contract establishes shared change visibility. Provider-specific push
notifications require verified, authorized connectors; no such broadcast
connector is configured by this tool.

## Local AI to Claude Code bridge

The Owner AI profile has a scoped `claude_code.review` tool in the canonical
registry. It sends the requested task through AI Gateway to the host-side
`tools/claude_code_bridge.py` service. The host service runs `claude -p` in the
12SGI-KING checkout with read-only `Read`, `Grep`, and `Glob` tools. It accepts
only requests marked with an explicit Owner instruction and authenticated by
the existing internal service token. No shell, file writes, commits, pushes,
deploys, or publishing are exposed. Poll job output with `claude_code.status`.

Start the Windows service with `tools/start_claude_code_bridge.ps1`. It reads
the existing token from the ignored `.env.v2` file, binds port 8127 for the
local Docker host bridge, and runs hidden. Stop it with
`tools/start_claude_code_bridge.ps1 -Stop`. The AI Gateway must be rebuilt or
restarted with `docker compose --env-file .env.v2 -f docker-compose.v2.yml
up -d --build ai-gateway` after Compose configuration changes. If the host daemon is stopped,
the tool returns an unavailable error; the local AI must report that state and
must not claim Claude ran.
