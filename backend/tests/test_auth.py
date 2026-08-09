import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.auth import (
    AuthUser,
    decode_token,
    hash_password,
    issue_token,
    verify_password,
)
from backend.app.main import app


class AuthTests(unittest.TestCase):
    def test_password_hash_is_not_plaintext_and_verifies(self) -> None:
        encoded = hash_password("correct-password")
        self.assertNotIn("correct-password", encoded)
        self.assertTrue(verify_password("correct-password", encoded))
        self.assertFalse(verify_password("wrong-password", encoded))

    def test_signed_token_round_trip(self) -> None:
        user = AuthUser("alice", "local-demo", hash_password("correct-password"))
        with patch.dict(
            os.environ,
            {"DEVSAGE_AUTH_SECRET": "test-secret-with-at-least-32-characters"},
            clear=False,
        ):
            token, ttl = issue_token(user)
            decoded = decode_token(token)
        self.assertGreater(ttl, 0)
        self.assertEqual("alice", decoded.username)
        self.assertEqual("local-demo", decoded.actor_id)

    def test_api_requires_bearer_when_formal_auth_is_enabled(self) -> None:
        with TemporaryDirectory() as temporary:
            users_path = Path(temporary) / "auth-users.json"
            users_path.write_text(
                json.dumps(
                    {
                        "users": [
                            {
                                "username": "alice",
                                "actor_id": "local-demo",
                                "password_hash": hash_password("correct-password"),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "DEVSAGE_AUTH_ENABLED": "true",
                    "DEVSAGE_AUTH_SECRET": "test-secret-with-at-least-32-characters",
                    "DEVSAGE_AUTH_USERS_FILE": str(users_path),
                },
                clear=False,
            ):
                client = TestClient(app)
                self.assertEqual(401, client.get("/api/projects").status_code)
                login = client.post(
                    "/api/auth/login",
                    json={"username": "alice", "password": "correct-password"},
                )
                self.assertEqual(200, login.status_code)
                token = login.json()["access_token"]
                me = client.get(
                    "/api/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(200, me.status_code)
                self.assertEqual("alice", me.json()["username"])
                authorized = client.get(
                    "/api/projects",
                    headers={"Authorization": f"Bearer {token}"},
                )
                self.assertEqual(200, authorized.status_code)


if __name__ == "__main__":
    unittest.main()
