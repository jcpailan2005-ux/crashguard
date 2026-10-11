import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.phase3.routes import SESSION_COOKIE, router


def user(role: str = "admin") -> dict:
    return {
        "uid": "user-1",
        "id": "user-1",
        "email": f"{role}@crashguard.local",
        "displayName": role.title(),
        "role": role,
        "roles": [role.upper()],
        "permissions": [],
        "areaId": None,
        "active": True,
        "status": "ACTIVE",
        "mustChangePassword": False,
        "createdAt": "2026-08-21T00:00:00Z",
        "updatedAt": "2026-08-21T00:00:00Z",
    }


class AuthCookieContractTests(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    @patch("backend.phase3.routes.service.login")
    def test_login_uses_httponly_cookie_and_hides_raw_token(self, login) -> None:
        login.return_value = {"token": "raw-session-secret", "user": user()}

        response = self.client.post(
            "/api/v3/auth/login",
            json={"email": "admin@crashguard.local", "password": "ValidPassword9!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("token", response.json())
        self.assertEqual(response.cookies.get(SESSION_COOKIE), "raw-session-secret")
        cookie_header = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie_header)
        self.assertIn("samesite=lax", cookie_header)
        self.assertIn("path=/", cookie_header)
        self.assertIn("max-age=", cookie_header)
        self.assertNotIn("secure;", cookie_header)
        self.assertEqual(response.headers["cache-control"], "no-store")
        # TestClient reports a hostname, not an IP. It must never reach INET.
        self.assertIsNone(login.call_args.kwargs["ip_address"])

    @patch("backend.phase3.routes.service.authenticate_session")
    def test_current_user_accepts_cookie_session(self, authenticate) -> None:
        principal = {**user("dispatcher"), "sessionId": "session-1"}
        authenticate.return_value = principal
        self.client.cookies.set(SESSION_COOKIE, "cookie-secret")

        response = self.client.get("/api/v3/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "dispatcher")
        authenticate.assert_called_once_with("cookie-secret")
        self.assertEqual(response.headers["cache-control"], "no-store")

    @patch("backend.phase3.routes.service.logout")
    @patch("backend.phase3.routes.service.authenticate_session")
    def test_logout_revokes_and_clears_cookie(self, authenticate, logout) -> None:
        authenticate.return_value = {**user(), "sessionId": "session-1"}
        self.client.cookies.set(SESSION_COOKIE, "cookie-secret")

        response = self.client.post("/api/v3/auth/logout")

        self.assertEqual(response.status_code, 200)
        logout.assert_called_once_with("session-1", "user-1")
        self.assertEqual(response.cookies.get(SESSION_COOKIE), None)
        self.assertIn("max-age=0", response.headers["set-cookie"].lower())


if __name__ == "__main__":
    unittest.main()
