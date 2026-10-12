import unittest
from unittest.mock import MagicMock
from fastapi import HTTPException
from starlette.requests import Request

from backend.main import (
    require_admin,
    require_camera_editor,
    require_dashboard_access,
)


def mock_request_with_user(role: str, uid: str = "test-user-id", permissions: list | None = None) -> Request:
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.headers = {"authorization": "Bearer dummy-token"}
    return req


class CameraRolePermissionsTest(unittest.TestCase):
    def test_require_camera_editor_allows_admin_and_dispatcher_with_explicit_grant(self):
        for role in ("admin", "dispatcher"):
            user = {"uid": f"user-{role}", "role": role, "email": f"{role}@test.com", "permissions": ["cameras.update"]}
            # Mock verify_session_user
            with unittest.mock.patch("backend.main.verify_session_user", return_value=user):
                req = mock_request_with_user(role)
                result = require_camera_editor(req)
                self.assertEqual(result["role"], role)

    def test_require_camera_editor_blocks_responder_and_other(self):
        for role in ("responder", "user", "guest"):
            user = {"uid": f"user-{role}", "role": role, "email": f"{role}@test.com", "permissions": ["cameras.update"]}
            with unittest.mock.patch("backend.main.verify_session_user", return_value=user):
                req = mock_request_with_user(role)
                with self.assertRaises(HTTPException) as ctx:
                    require_camera_editor(req)
                self.assertEqual(ctx.exception.status_code, 403)
                self.assertIn("Permission required: cameras.update", ctx.exception.detail)

    def test_require_admin_allows_only_admin(self):
        user_admin = {"uid": "user-admin", "role": "admin"}
        with unittest.mock.patch("backend.main.verify_session_user", return_value=user_admin):
            req = mock_request_with_user("admin")
            self.assertEqual(require_admin(req)["role"], "admin")

        user_disp = {"uid": "user-disp", "role": "dispatcher"}
        with unittest.mock.patch("backend.main.verify_session_user", return_value=user_disp):
            req = mock_request_with_user("dispatcher")
            with self.assertRaises(HTTPException) as ctx:
                require_admin(req)
            self.assertEqual(ctx.exception.status_code, 403)

    def test_require_dashboard_access_allows_admin_dispatcher_responder(self):
        for role in ("admin", "dispatcher", "responder"):
            user = {"uid": f"user-{role}", "role": role}
            with unittest.mock.patch("backend.main.verify_session_user", return_value=user):
                req = mock_request_with_user(role)
                self.assertEqual(require_dashboard_access(req)["role"], role)


if __name__ == "__main__":
    unittest.main()
