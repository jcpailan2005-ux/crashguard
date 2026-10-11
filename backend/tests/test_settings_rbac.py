import unittest

from backend.phase3.permissions import ROLE_PERMISSIONS, principal_has_permission


OWN_PERMISSIONS = {
    "profile.view_own",
    "profile.update_own",
    "preferences.view_own",
    "preferences.update_own",
    "password.change_own",
    "notifications.preferences_own",
}


class SettingsRbacTests(unittest.TestCase):
    def test_all_operational_roles_receive_own_resource_permissions(self):
        for role in ("ADMIN", "DISPATCHER", "RESPONDER"):
            self.assertTrue(OWN_PERMISSIONS.issubset(ROLE_PERMISSIONS[role]), role)

    def test_system_and_ai_settings_remain_admin_only(self):
        protected = {
            "system_settings.view",
            "system_settings.manage",
            "ai_settings.view",
            "ai_settings.manage",
        }
        self.assertTrue(protected.issubset(ROLE_PERMISSIONS["ADMIN"]))
        self.assertTrue(protected.isdisjoint(ROLE_PERMISSIONS["DISPATCHER"]))
        self.assertTrue(protected.isdisjoint(ROLE_PERMISSIONS["RESPONDER"]))

    def test_dispatcher_can_create_but_not_manage_existing_cameras(self):
        dispatcher = ROLE_PERMISSIONS["DISPATCHER"]
        self.assertIn("cameras.view", dispatcher)
        self.assertIn("cameras.monitor", dispatcher)
        self.assertIn("cameras.create", dispatcher)
        self.assertNotIn("cameras.update", dispatcher)
        self.assertNotIn("cameras.disable", dispatcher)
        self.assertNotIn("cameras.manage_credentials", dispatcher)
        self.assertTrue(principal_has_permission({"permissions": dispatcher}, "cameras.view"))
        self.assertFalse(principal_has_permission({"permissions": dispatcher}, "cameras.update"))

    def test_responder_has_no_general_camera_control_room_access(self):
        responder = ROLE_PERMISSIONS["RESPONDER"]
        self.assertNotIn("cameras.view", responder)
        self.assertNotIn("cameras.monitor", responder)

    def test_admin_can_monitor_and_manage_camera_credentials(self):
        admin = ROLE_PERMISSIONS["ADMIN"]
        self.assertIn("cameras.view", admin)
        self.assertIn("cameras.monitor", admin)
        self.assertIn("cameras.manage_credentials", admin)


if __name__ == "__main__":
    unittest.main()
