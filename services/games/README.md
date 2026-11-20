# PUBLIC/BRIDGE — Multiplayer game API

The public static games use this service only for the two-player Konane and Weiqi circles.
It is a separate, narrow API; it does not proxy to the owner console, Studio APIs, or other
Tailscale services.

## Access and boundaries

- `web-server` serves the built static site and forwards only `/games/api/` to this service.
- The game service has no published host port; Compose exposes it to the web-server on the
  private Compose network.
- Every game operation except the anonymous sign-in status check requires an auth-service
  token with the matching game scope. Registered-user tokens have only `game:read` and
  `game:write`, are limited to the shared `tribegamestudios` tenant, and expire within one
  hour.
- Owner allowlisting and Owner sessions are unchanged. A game's six-character join code
  grants entry to that circle only; the API still requires an authenticated, authorized
  player.
- Do not add a direct host-port publish or route broader backend APIs through this location.

## API used by `game_studio/circle_core.js`

`{game}` is one of `konane` or `weiqi`.

- `GET /games/api/{game}/me` — return login status and a pseudonymous player label.
- `GET /games/api/{game}/lobby` — list up to 25 waiting circles in the shared lobby.
- `POST /games/api/{game}/match/new` — create a waiting circle.
- `POST /games/api/{game}/match/join` — join a waiting circle with its code.
- `GET /games/api/{game}/match?id={match_id}` — read a circle as a member.
- `POST /games/api/{game}/match/turn` — advance one turn using the current revision.

Turn updates require membership, the caller's turn, a matching revision, a JSON object, and
a bounded state payload. Revision checks prevent concurrent stale turns. The client submits
the game state; this API does not independently validate game-specific legal moves or provide
competitive anti-cheat guarantees.

## Local checks

```bash
docker compose -f docker-compose.v2.yml config --quiet
python -m pytest -q tests/v2/test_games_multiplayer.py tests/v2/test_v2_client_migration.py
```

The API is available at `/games/api/` only when the Compose web-server is reachable. Deployment
verification must confirm the intended static-site host forwards this route to the Compose
web-server; a static GitHub Pages backup alone cannot run the API.
