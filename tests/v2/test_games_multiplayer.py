import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.v2._test_helpers import load_module

GAMES_MAIN = ROOT / "services" / "games" / "app" / "main.py"


class TestGameCircles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="game-circles-")
        self.db_path = str(Path(self.tmp.name) / "games.db")
        self.module = load_module(
            GAMES_MAIN,
            f"games_api_{time.time_ns()}",
            env_overrides={
                "GAMES_DB_PATH": self.db_path,
                "INTERNAL_SERVICE_TOKEN": "game-api-service-token",
                "GAME_LOBBY_TENANT_ID": "tribegamestudios",
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        self.app_client = TestClient(self.module.app)
        self.claims_by_token = {
            "player-a": {
                "sub": "magic:a@example.com",
                "role": "RegisteredUser",
                "tenant_id": "tribegamestudios",
                "scopes": ["game:read", "game:write"],
            },
            "player-b": {
                "sub": "magic:b@example.com",
                "role": "RegisteredUser",
                "tenant_id": "tribegamestudios",
                "scopes": ["game:read", "game:write"],
            },
            "wrong-tenant": {
                "sub": "magic:c@example.com",
                "role": "RegisteredUser",
                "tenant_id": "other-tenant",
                "scopes": ["game:read", "game:write"],
            },
            "resident": {
                "sub": "resident:c@example.com",
                "role": "Resident",
                "tenant_id": "tribegamestudios",
                "scopes": ["game:read"],
            },
        }

        def verify(authorization, required_scopes, **_kwargs):
            token = authorization.removeprefix("Bearer ")
            claims = self.claims_by_token.get(token)
            if not claims:
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail={"error": "unauthorized"})
            if not required_scopes.issubset(set(claims["scopes"])):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail={"error": "insufficient_scope"})
            return dict(claims)

        self.authz_patch = mock.patch.object(self.module, "require_claims", side_effect=verify)
        self.authz_patch.start()
        self.addCleanup(self.authz_patch.stop)
        self.addCleanup(self.app_client.close)
        self.addCleanup(self.tmp.cleanup)

    def _headers(self, token):
        return {"Authorization": "Bearer " + token}

    def test_registered_users_create_join_and_play_in_shared_lobby(self):
        created = self.app_client.post(
            "/games/api/konane/match/new",
            headers=self._headers("player-a"),
        )
        self.assertEqual(created.status_code, 201)
        first = created.json()
        self.assertEqual(first["status"], "waiting")
        self.assertEqual(len(first["players"]), 1)
        self.assertTrue(first["players"][0].startswith("Player-"))

        lobby = self.app_client.get(
            "/games/api/konane/lobby",
            headers=self._headers("player-b"),
        )
        self.assertEqual(lobby.status_code, 200)
        self.assertEqual(lobby.json()["matches"][0]["code"], first["code"])

        joined = self.app_client.post(
            "/games/api/konane/match/join",
            json={"code": first["code"].lower()},
            headers=self._headers("player-b"),
        )
        self.assertEqual(joined.status_code, 200)
        second = joined.json()
        self.assertEqual(second["status"], "active")
        self.assertEqual(second["seat"], 1)
        self.assertEqual(len(second["players"]), 2)

        turn = self.app_client.post(
            "/games/api/konane/match/turn",
            json={"id": first["id"], "rev": 0, "state": '{"board":[1,2],"turn":1}'},
            headers=self._headers("player-a"),
        )
        self.assertEqual(turn.status_code, 200)
        self.assertEqual(turn.json()["rev"], 1)
        self.assertFalse(turn.json()["your_turn"])

        refreshed = self.app_client.get(
            "/games/api/konane/match",
            params={"id": first["id"]},
            headers=self._headers("player-b"),
        )
        self.assertEqual(refreshed.status_code, 200)
        self.assertTrue(refreshed.json()["your_turn"])
        self.assertEqual(refreshed.json()["state"], '{"board":[1,2],"turn":1}')

        stale = self.app_client.post(
            "/games/api/konane/match/turn",
            json={"id": first["id"], "rev": 0, "state": '{"turn":0}'},
            headers=self._headers("player-a"),
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["detail"]["error"], "stale_turn")

    def test_game_api_restricts_roles_tenants_and_game_ids(self):
        response = self.app_client.get(
            "/games/api/konane/me",
            headers=self._headers("resident"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["logged_in"])

        response = self.app_client.post(
            "/games/api/konane/match/new",
            headers=self._headers("wrong-tenant"),
        )
        self.assertEqual(response.status_code, 403)

        response = self.app_client.get(
            "/games/api/monopoly/me",
            headers=self._headers("player-a"),
        )
        self.assertEqual(response.status_code, 404)

    def test_non_members_cannot_read_or_change_a_match(self):
        created = self.app_client.post(
            "/games/api/weiqi/match/new",
            headers=self._headers("player-a"),
        )
        match = created.json()

        read = self.app_client.get(
            "/games/api/weiqi/match",
            params={"id": match["id"]},
            headers=self._headers("player-b"),
        )
        self.assertEqual(read.status_code, 404)

        joined = self.app_client.post(
            "/games/api/weiqi/match/join",
            json={"code": match["code"]},
            headers=self._headers("player-b"),
        )
        self.assertEqual(joined.status_code, 200)
        invalid_state = self.app_client.post(
            "/games/api/weiqi/match/turn",
            json={"id": match["id"], "rev": 0, "state": "not-json"},
            headers=self._headers("player-a"),
        )
        self.assertEqual(invalid_state.status_code, 400)

        oversized = self.app_client.post(
            "/games/api/weiqi/match/turn",
            json={"id": match["id"], "rev": 0, "state": '{"data":"' + ("x" * 70000) + '"}'},
            headers=self._headers("player-a"),
        )
        self.assertEqual(oversized.status_code, 413)


if __name__ == "__main__":
    unittest.main()
