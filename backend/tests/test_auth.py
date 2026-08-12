import tempfile
import unittest
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import config, database
from app.auth import _client_key, make_password_hash, verify_mcp_token, verify_password, verify_token
from app.database import init_db
from app.routers import auth as auth_router
from app.routers import autonomous as autonomous_router


class AuthTests(unittest.TestCase):
    PASSWORD = "correct horse nest staple"

    def setUp(self):
        import asyncio

        self.tempdir = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = str(Path(self.tempdir.name) / "auth.db")
        config.APP_USERNAME = "connie"
        config.APP_PASSWORD_HASH = make_password_hash(self.PASSWORD)
        config.SESSION_COOKIE_SECURE = False
        config.SESSION_TTL_DAYS = 30
        config.ALLOW_LEGACY_BEARER = False
        config.API_SECRET_KEY = "legacy-secret"
        config.MCP_API_TOKEN_SHA256 = ""
        asyncio.run(init_db())

        app = FastAPI()
        app.include_router(auth_router.router)
        app.include_router(autonomous_router.router)

        @app.get("/probe")
        async def read_probe(_=Depends(verify_token)):
            return {"ok": True}

        @app.post("/probe")
        async def write_probe(_=Depends(verify_token)):
            return {"ok": True}

        @app.get("/mcp-probe")
        async def mcp_probe(_=Depends(verify_mcp_token)):
            return {"ok": True}

        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.tempdir.cleanup()

    def login(self):
        return self.client.post(
            "/api/auth/login",
            json={"username": "connie", "password": self.PASSWORD},
        )

    def test_password_hash_round_trip_and_wrong_password(self):
        encoded = make_password_hash(self.PASSWORD)
        self.assertTrue(verify_password(self.PASSWORD, encoded))
        self.assertFalse(verify_password("wrong password", encoded))

    def test_login_creates_http_only_session_and_authenticates(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        cookies = response.headers.get_list("set-cookie")
        session_cookie = next(value for value in cookies if value.startswith("remoire_session="))
        csrf_cookie = next(value for value in cookies if value.startswith("remoire_csrf="))
        self.assertIn("HttpOnly", session_cookie)
        self.assertIn("SameSite=strict", session_cookie)
        self.assertNotIn("HttpOnly", csrf_cookie)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.client.get("/probe").status_code, 200)

    def test_wrong_credentials_do_not_create_session(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "connie", "password": "definitely wrong"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("remoire_session", response.cookies)

    def test_session_write_requires_matching_csrf(self):
        self.login()
        self.assertEqual(self.client.post("/probe").status_code, 403)
        csrf = self.client.cookies.get("remoire_csrf")
        self.assertEqual(
            self.client.post("/probe", headers={"X-CSRF-Token": csrf}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/probe", headers={"X-CSRF-Token": "wrong"}).status_code,
            403,
        )

    def test_query_token_and_legacy_bearer_are_rejected_by_default(self):
        self.assertEqual(self.client.get("/probe?token=legacy-secret").status_code, 401)
        self.assertEqual(
            self.client.get("/probe", headers={"Authorization": "Bearer legacy-secret"}).status_code,
            401,
        )

    def test_logout_revokes_server_side_session(self):
        self.login()
        csrf = self.client.cookies.get("remoire_csrf")
        response = self.client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/probe").status_code, 401)

    def test_mcp_auth_fails_closed_when_unconfigured(self):
        self.assertEqual(self.client.get("/mcp-probe").status_code, 503)
        self.assertEqual(self.client.get("/api/auth/mcp-check").status_code, 503)

    def test_mcp_auth_accepts_only_the_independent_bearer(self):
        import hashlib

        token = "mcp-test-token-with-high-entropy-placeholder"
        config.MCP_API_TOKEN_SHA256 = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.assertEqual(self.client.get("/mcp-probe").status_code, 401)
        self.assertEqual(
            self.client.get("/mcp-probe", headers={"Authorization": "Bearer wrong"}).status_code,
            401,
        )
        response = self.client.get(
            "/mcp-probe", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(
            self.client.get(
                "/api/auth/mcp-check", headers={"Authorization": f"Bearer {token}"}
            ).status_code,
            204,
        )

    def test_autonomous_activity_is_private(self):
        self.assertEqual(self.client.get("/api/autonomous/logs").status_code, 401)
        self.assertEqual(self.client.get("/api/autonomous/dates").status_code, 401)
        self.login()
        self.assertEqual(self.client.get("/api/autonomous/logs").status_code, 200)
        self.assertEqual(self.client.get("/api/autonomous/dates").status_code, 200)

    def test_forwarded_ip_is_trusted_only_from_loopback_proxy(self):
        def request_for(peer: str, forwarded: str) -> Request:
            return Request({
                "type": "http",
                "method": "POST",
                "path": "/api/auth/login",
                "headers": [(b"x-forwarded-for", forwarded.encode("ascii"))],
                "client": (peer, 1234),
                "scheme": "https",
                "server": ("remoire.cc", 443),
                "query_string": b"",
            })

        self.assertEqual(_client_key(request_for("127.0.0.1", "203.0.113.7")), "203.0.113.7")
        self.assertEqual(_client_key(request_for("198.51.100.4", "203.0.113.7")), "198.51.100.4")


if __name__ == "__main__":
    unittest.main()
