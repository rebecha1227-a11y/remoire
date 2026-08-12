import tempfile
import unittest
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config, database
from app.auth import make_password_hash, verify_password, verify_token
from app.database import init_db
from app.routers import auth as auth_router


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
        asyncio.run(init_db())

        app = FastAPI()
        app.include_router(auth_router.router)

        @app.get("/probe")
        async def read_probe(_=Depends(verify_token)):
            return {"ok": True}

        @app.post("/probe")
        async def write_probe(_=Depends(verify_token)):
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


if __name__ == "__main__":
    unittest.main()
