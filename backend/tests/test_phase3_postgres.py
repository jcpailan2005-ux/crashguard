from __future__ import annotations

import os
import tempfile
from pathlib import Path
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.phase3.database import connection
from backend.phase3.routes import SESSION_COOKIE, router
from backend.phase3 import service


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.crashguard.local"


class Phase3SQLiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='crashguard-operations-tests-')
        cls.previous_path = os.environ.get('CRASHGUARD_SQLITE_PATH')
        os.environ['CRASHGUARD_SQLITE_PATH'] = str(Path(cls.temp.name) / 'operations.sqlite')
        cls.addClassCleanup(cls.temp.cleanup)
        def restore():
            if cls.previous_path is None:
                os.environ.pop('CRASHGUARD_SQLITE_PATH', None)
            else:
                os.environ['CRASHGUARD_SQLITE_PATH'] = cls.previous_path
        cls.addClassCleanup(restore)
        app = FastAPI()
        app.include_router(router)
        cls.app = app
        cls.client = TestClient(app)

    def setUp(self):
        with connection() as conn, conn.transaction():
            for table in ('incidents', 'cameras', 'users', 'areas'):
                conn.execute(f'DELETE FROM {table}')
        self.accounts = {}
        for name, role in (
            ("admin", "ADMIN"), ("dispatcher", "DISPATCHER"),
            ("dispatcher2", "DISPATCHER"), ("responder", "RESPONDER"),
            ("responder2", "RESPONDER"),
        ):
            created = service.create_user(
                None, email=_unique_email(name), full_name=name.title(), role=role
            )
            temporary = created.pop("temporaryPassword")
            login = self.client.post("/api/v3/auth/login", json={"email": created["email"], "password": temporary})
            self.assertEqual(login.status_code, 200, login.text)
            self.assertNotIn("token", login.json())
            token = login.cookies.get(SESSION_COOKIE)
            self.assertTrue(token)
            permanent = f"Permanent9!{name}"
            changed = self.client.post(
                "/api/v3/auth/change-password",
                headers={"Authorization": f"Bearer {token}"},
                json={"currentPassword": temporary, "newPassword": permanent},
            )
            self.assertEqual(changed.status_code, 200, changed.text)
            self.accounts[name] = {"user": changed.json()["user"], "token": token, "password": permanent}

    def headers(self, name: str) -> dict:
        return {"Authorization": f"Bearer {self.accounts[name]['token']}"}

    def create_incident(self) -> str:
        result = service.create_ai_incident({
            "detectorEventId": f"test:{uuid.uuid4()}",
            "detectionMode": "temporal_collision",
            "crashScore": 0.91,
            "detectedAt": "2026-08-19T03:00:00Z",
            "location": "Test intersection",
            "evidenceSummary": {"impact": True},
            "media": {"keyFrame": "/outputs/test.jpg"},
        })
        return result["incidentId"]

    def claim_and_confirm(self, incident_id: str, dispatcher: str = "dispatcher"):
        self.assertEqual(self.client.post(f"/api/v3/dispatcher/incidents/{incident_id}/claim", headers=self.headers(dispatcher)).status_code, 200)
        response = self.client.post(
            f"/api/v3/dispatcher/incidents/{incident_id}/review",
            headers=self.headers(dispatcher),
            json={"decision": "CONFIRMED", "priority": "HIGH", "incidentType": "Vehicle collision"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_first_login_gate_argon2_and_hashed_session(self):
        created = service.create_user(None, email=_unique_email("fresh"), full_name="Fresh User", role="ADMIN")
        temporary = created["temporaryPassword"]
        login = self.client.post("/api/v3/auth/login", json={"email": created["email"], "password": temporary})
        self.assertNotIn("token", login.json())
        token = login.cookies.get(SESSION_COOKIE)
        self.assertTrue(token)
        denied = self.client.get("/api/v3/admin/users", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["detail"], "PASSWORD_CHANGE_REQUIRED")
        with connection() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE email=%s", (created["email"],)).fetchone()
            session = conn.execute("SELECT token_hash FROM sessions WHERE user_id=%s", (created["id"],)).fetchone()
        self.assertTrue(row["password_hash"].startswith("$argon2id$"))
        self.assertNotEqual(session["token_hash"], token)

    def test_cookie_login_current_user_refresh_and_logout_for_all_roles(self):
        for name, expected_role in (
            ("admin", "admin"),
            ("dispatcher", "dispatcher"),
            ("responder", "responder"),
        ):
            with self.subTest(role=expected_role), TestClient(self.app) as client:
                account = self.accounts[name]
                login = client.post(
                    "/api/v3/auth/login",
                    json={
                        "email": account["user"]["email"],
                        "password": account["password"],
                    },
                )
                self.assertEqual(login.status_code, 200, login.text)
                self.assertNotIn("token", login.json())
                cookie = login.cookies.get(SESSION_COOKIE)
                self.assertTrue(cookie)
                set_cookie = login.headers.get("set-cookie", "").lower()
                self.assertIn("httponly", set_cookie)
                self.assertIn("samesite=lax", set_cookie)
                self.assertIn("path=/", set_cookie)

                current = client.get("/api/v3/auth/me")
                self.assertEqual(current.status_code, 200, current.text)
                self.assertEqual(current.json()["user"]["role"], expected_role)
                refreshed = client.get("/api/v3/auth/me")
                self.assertEqual(refreshed.status_code, 200, refreshed.text)

                logout = client.post("/api/v3/auth/logout")
                self.assertEqual(logout.status_code, 200, logout.text)
                self.assertEqual(client.get("/api/v3/auth/me").status_code, 401)

    def test_three_isolated_cookie_sessions_complete_dispatch_workflow(self):
        # Revoke the setup responder session so dispatch first observes a real offline state.
        self.client.post("/api/v3/auth/logout", headers=self.headers("responder"))

        with TestClient(self.app) as admin, TestClient(self.app) as dispatcher, TestClient(self.app) as responder:
            for client, name in (
                (admin, "admin"),
                (dispatcher, "dispatcher"),
            ):
                account = self.accounts[name]
                login = client.post(
                    "/api/v3/auth/login",
                    json={"email": account["user"]["email"], "password": account["password"]},
                )
                self.assertEqual(login.status_code, 200, login.text)

            responder_id = self.accounts["responder"]["user"]["id"]
            initial_presence = dispatcher.get("/api/v3/responders/presence")
            self.assertEqual(initial_presence.status_code, 200, initial_presence.text)
            self.assertEqual(
                next(row for row in initial_presence.json()["responders"] if row["uid"] == responder_id)["presenceStatus"],
                "OFFLINE",
            )

            responder_account = self.accounts["responder"]
            login = responder.post(
                "/api/v3/auth/login",
                json={
                    "email": responder_account["user"]["email"],
                    "password": responder_account["password"],
                },
            )
            self.assertEqual(login.status_code, 200, login.text)
            self.assertEqual(
                responder.post("/api/v3/responder/presence/heartbeat").status_code,
                200,
            )
            online_presence = dispatcher.get("/api/v3/responders/presence").json()["responders"]
            self.assertEqual(
                next(row for row in online_presence if row["uid"] == responder_id)["presenceStatus"],
                "ONLINE",
            )

            incident_id = self.create_incident()
            self.assertEqual(
                dispatcher.post(f"/api/v3/dispatcher/incidents/{incident_id}/claim").status_code,
                200,
            )
            reviewed = dispatcher.post(
                f"/api/v3/dispatcher/incidents/{incident_id}/review",
                json={"decision": "CONFIRMED", "priority": "HIGH", "incidentType": "Vehicle collision"},
            )
            self.assertEqual(reviewed.status_code, 200, reviewed.text)
            assigned = dispatcher.post(
                f"/api/v3/dispatcher/incidents/{incident_id}/assign",
                json={"responderId": responder_id},
            )
            self.assertEqual(assigned.status_code, 200, assigned.text)
            assignment_id = assigned.json()["assignment"]["id"]

            own = responder.get("/api/v3/responder/assignments")
            self.assertEqual(own.status_code, 200, own.text)
            self.assertEqual(own.json()["assignments"][0]["id"], assignment_id)
            for status in ("ACCEPTED", "EN_ROUTE", "ARRIVED", "RESPONDING"):
                transition = responder.post(
                    f"/api/v3/responder/assignments/{assignment_id}/transition",
                    json={"status": status},
                )
                self.assertEqual(transition.status_code, 200, transition.text)
                dispatcher_view = dispatcher.get(f"/api/v3/incidents/{incident_id}")
                self.assertEqual(dispatcher_view.json()["incident"]["assignment_status"], status)

            resolved = responder.post(
                f"/api/v3/responder/assignments/{assignment_id}/transition",
                json={"status": "RESOLVED", "notes": "Scene secured", "outcome": "Cleared"},
            )
            self.assertEqual(resolved.status_code, 200, resolved.text)
            final_incident = dispatcher.get(f"/api/v3/incidents/{incident_id}").json()["incident"]
            self.assertEqual(final_incident["state"], "RESOLVED")
            self.assertEqual(final_incident["assignment_status"], "RESOLVED")

            self.assertEqual(responder.post("/api/v3/auth/logout").status_code, 200)
            final_presence = dispatcher.get("/api/v3/responders/presence").json()["responders"]
            self.assertEqual(
                next(row for row in final_presence if row["uid"] == responder_id)["presenceStatus"],
                "OFFLINE",
            )
            audit = admin.get("/api/v3/admin/audit-logs")
            self.assertEqual(audit.status_code, 200, audit.text)
            actions = {entry["action"] for entry in audit.json()["auditLogs"]}
            self.assertTrue({"assignment.created", "assignment.accepted", "assignment.resolved", "auth.logout"}.issubset(actions))

    def test_failed_login_does_not_create_a_session(self):
        with TestClient(self.app) as client:
            invalid_password = client.post(
                "/api/v3/auth/login",
                json={
                    "email": self.accounts["admin"]["user"]["email"],
                    "password": "definitely-not-the-password",
                },
            )
            self.assertEqual(invalid_password.status_code, 401)
            self.assertEqual(
                invalid_password.json()["detail"], "Invalid email or password."
            )
            self.assertIsNone(client.cookies.get(SESSION_COOKIE))

            unknown = client.post(
                "/api/v3/auth/login",
                json={
                    "email": _unique_email("unknown"),
                    "password": "UnknownPassword9!",
                },
            )
            self.assertEqual(unknown.status_code, 401)
            self.assertEqual(unknown.json()["detail"], "Invalid email or password.")
            self.assertIsNone(client.cookies.get(SESSION_COOKIE))

    def test_server_rbac_ignores_actor_and_role_spoofing(self):
        with TestClient(self.app) as unauthenticated:
            self.assertEqual(unauthenticated.get("/api/v3/admin/users").status_code, 401)
        denied = self.client.post(
            "/api/v3/admin/users", headers=self.headers("dispatcher"),
            json={"email": _unique_email("spoof"), "fullName": "Spoof", "role": "ADMIN", "actorId": self.accounts["admin"]["user"]["id"]},
        )
        self.assertEqual(denied.status_code, 403)
        incident_id = self.create_incident()
        denied = self.client.post(
            f"/api/v3/dispatcher/incidents/{incident_id}/claim", headers=self.headers("responder"),
            json={"role": "ADMIN", "actorId": self.accounts["admin"]["user"]["id"]},
        )
        self.assertEqual(denied.status_code, 403)

    def test_personal_settings_are_current_user_scoped(self):
        dispatcher = self.accounts["dispatcher"]["user"]
        responder = self.accounts["responder"]["user"]

        profile = self.client.patch(
            "/api/v3/me/profile",
            headers=self.headers("dispatcher"),
            json={"fullName": "Dispatcher Updated"},
        )
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["user"]["displayName"], "Dispatcher Updated")
        self.assertEqual(profile.json()["user"]["id"], dispatcher["id"])

        preferences = self.client.patch(
            "/api/v3/me/preferences",
            headers=self.headers("responder"),
            json={
                "theme": "dark",
                "notificationPreferences": {"alertNotifications": False, "alarmAudio": False},
            },
        )
        self.assertEqual(preferences.status_code, 200, preferences.text)
        self.assertEqual(preferences.json()["preferences"]["theme"], "dark")
        self.assertFalse(
            preferences.json()["preferences"]["notification_preferences"]["alertNotifications"]
        )
        self.assertFalse(
            preferences.json()["preferences"]["notification_preferences"]["alarmAudio"]
        )

        other_user_update = self.client.patch(
            f"/api/v3/admin/users/{responder['id']}",
            headers=self.headers("dispatcher"),
            json={"fullName": "Unauthorized Rename"},
        )
        self.assertEqual(other_user_update.status_code, 403)
        spoofed_own_update = self.client.patch(
            "/api/v3/me/profile",
            headers=self.headers("dispatcher"),
            json={"fullName": "Spoofed", "userId": responder["id"], "role": "ADMIN"},
        )
        self.assertEqual(spoofed_own_update.status_code, 422)

        with connection() as conn:
            unchanged = conn.execute(
                "SELECT full_name FROM users WHERE id=%s", (responder["id"],)
            ).fetchone()
            preference_owner = conn.execute(
                "SELECT user_id FROM user_preferences WHERE user_id=%s", (responder["id"],)
            ).fetchone()
        self.assertEqual(unchanged["full_name"], "Responder")
        self.assertEqual(str(preference_owner["user_id"]), responder["id"])

    def test_authenticated_responder_heartbeat_and_presence_timeout(self):
        responder_id = self.accounts["responder"]["user"]["id"]
        with connection() as conn, conn.transaction():
            conn.execute(
                "UPDATE sessions SET last_used_at=seconds_ago(120) WHERE user_id=%s",
                (responder_id,),
            )
            conn.execute(
                "UPDATE users SET availability_status='OFFLINE' WHERE id=%s",
                (responder_id,),
            )

        before = self.client.get(
            "/api/v3/responders/presence", headers=self.headers("dispatcher")
        )
        self.assertEqual(before.status_code, 200, before.text)
        responder_before = next(
            item for item in before.json()["responders"] if item["uid"] == responder_id
        )
        self.assertEqual(responder_before["presenceStatus"], "OFFLINE")

        heartbeat = self.client.post(
            "/api/v3/responder/presence/heartbeat", headers=self.headers("responder")
        )
        self.assertEqual(heartbeat.status_code, 200, heartbeat.text)
        self.assertEqual(heartbeat.json()["presenceStatus"], "ONLINE")
        self.assertEqual(heartbeat.json()["availabilityStatus"], "AVAILABLE")

        after = self.client.get(
            "/api/v3/responders/presence", headers=self.headers("dispatcher")
        )
        responder_after = next(
            item for item in after.json()["responders"] if item["uid"] == responder_id
        )
        self.assertEqual(responder_after["presenceStatus"], "ONLINE")
        self.assertIsNotNone(responder_after["lastSeenAt"])

        self.assertEqual(
            self.client.post(
                "/api/v3/responder/presence/heartbeat",
                headers=self.headers("dispatcher"),
                json={"userId": responder_id},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                "/api/v3/responders/presence", headers=self.headers("responder")
            ).status_code,
            403,
        )

        logout = self.client.post(
            "/api/v3/auth/logout", headers=self.headers("responder")
        )
        self.assertEqual(logout.status_code, 200, logout.text)
        logged_out = self.client.get(
            "/api/v3/responders/presence", headers=self.headers("dispatcher")
        )
        responder_logged_out = next(
            item for item in logged_out.json()["responders"] if item["uid"] == responder_id
        )
        self.assertEqual(responder_logged_out["presenceStatus"], "OFFLINE")

    def test_presence_list_prioritizes_online_available_responders(self):
        first_id = self.accounts["responder"]["user"]["id"]
        second_id = self.accounts["responder2"]["user"]["id"]
        self.client.post(
            "/api/v3/responder/presence/heartbeat", headers=self.headers("responder")
        )
        with connection() as conn, conn.transaction():
            conn.execute(
                "UPDATE sessions SET last_used_at=seconds_ago(120) WHERE user_id=%s",
                (second_id,),
            )
        response = self.client.get(
            "/api/v3/responders/presence", headers=self.headers("dispatcher")
        )
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()["responders"]
        self.assertEqual(rows[0]["uid"], first_id)
        self.assertEqual(rows[0]["presenceStatus"], "ONLINE")
        self.assertEqual(
            next(row for row in rows if row["uid"] == second_id)["presenceStatus"],
            "OFFLINE",
        )

    def restore_camera_create_permission(self):
        with connection() as conn, conn.transaction():
            conn.execute("""INSERT OR IGNORE INTO role_permissions(role_id,permission_id)
                            SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
                            WHERE r.name='DISPATCHER' AND p.code='cameras.create'""")

    def test_dispatcher_explicit_camera_create_permission(self):
        response = self.client.post('/api/v3/cameras', headers=self.headers('dispatcher'),
                                    json={'name': 'Authorized Dispatcher Camera'})
        self.assertEqual(response.status_code, 200, response.text)

    def test_dispatcher_camera_read_does_not_grant_camera_mutation(self):
        # A view-only role must not gain write access; current dispatchers also
        # receive explicit cameras.create through the existing migration.
        with connection() as conn, conn.transaction():
            conn.execute("""DELETE FROM role_permissions WHERE role_id=(SELECT id FROM roles WHERE name='DISPATCHER')
                            AND permission_id=(SELECT id FROM permissions WHERE code='cameras.create')""")
        self.addCleanup(self.restore_camera_create_permission)
        area = self.client.post(
            "/api/v3/areas",
            headers=self.headers("admin"),
            json={"name": "Camera RBAC Area"},
        ).json()["area"]
        created = self.client.post(
            "/api/v3/cameras",
            headers=self.headers("admin"),
            json={"name": "Read Only Camera", "areaId": area["id"]},
        )
        self.assertEqual(created.status_code, 200, created.text)
        camera_id = created.json()["camera"]["id"]

        self.assertEqual(
            self.client.get("/api/v3/cameras", headers=self.headers("dispatcher")).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/v3/cameras",
                headers=self.headers("dispatcher"),
                json={"name": "Forbidden Camera"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.put(
                f"/api/v3/cameras/{camera_id}",
                headers=self.headers("dispatcher"),
                json={"name": "Forbidden Update"},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                "/api/v3/cameras",
                headers=self.headers("responder"),
                json={"name": "Forbidden Responder Camera"},
            ).status_code,
            403,
        )
    def test_admin_configuration_and_account_actions_are_audited(self):
        area = self.client.post(
            "/api/v3/areas", headers=self.headers("admin"),
            json={"name": "Audit Test Area", "description": "integration"},
        )
        self.assertEqual(area.status_code, 200, area.text)
        camera = self.client.post(
            "/api/v3/cameras", headers=self.headers("admin"),
            json={"name": "Audit Camera", "areaId": area.json()["area"]["id"], "status": "OFFLINE"},
        )
        self.assertEqual(camera.status_code, 200, camera.text)
        setting = self.client.put(
            "/api/v3/admin/ai-settings/temporal_threshold", headers=self.headers("admin"),
            json={"value": 0.82},
        )
        self.assertEqual(setting.status_code, 200, setting.text)
        target = self.accounts["responder2"]["user"]["id"]
        self.assertEqual(self.client.patch(
            f"/api/v3/admin/users/{target}/role", headers=self.headers("admin"), json={"role": "DISPATCHER"}
        ).status_code, 200)
        with connection() as conn:
            actions = {row["action"] for row in conn.execute("SELECT action FROM audit_logs").fetchall()}
        self.assertTrue({"area.created", "camera.created", "ai_setting.changed", "user.role_changed"}.issubset(actions))

    def test_disable_revokes_existing_sessions(self):
        responder_id = self.accounts["responder"]["user"]["id"]
        changed = self.client.patch(
            f"/api/v3/admin/users/{responder_id}/status",
            headers=self.headers("admin"), json={"status": "DISABLED"},
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(self.client.get("/api/v3/auth/me", headers=self.headers("responder")).status_code, 401)

    def test_end_to_end_dispatch_and_strict_response_transitions(self):
        incident_id = self.create_incident()
        self.claim_and_confirm(incident_id)
        assigned = self.client.post(
            f"/api/v3/dispatcher/incidents/{incident_id}/assign", headers=self.headers("dispatcher"),
            json={"responderId": self.accounts["responder"]["user"]["id"]},
        )
        self.assertEqual(assigned.status_code, 200, assigned.text)
        assignment_id = assigned.json()["assignment"]["id"]
        invalid = self.client.post(
            f"/api/v3/responder/assignments/{assignment_id}/transition",
            headers=self.headers("responder"), json={"status": "ARRIVED"},
        )
        self.assertEqual(invalid.status_code, 409)
        for status in ("ACCEPTED", "EN_ROUTE", "ARRIVED", "RESPONDING"):
            response = self.client.post(
                f"/api/v3/responder/assignments/{assignment_id}/transition",
                headers=self.headers("responder"), json={"status": status},
            )
            self.assertEqual(response.status_code, 200, response.text)
        resolved = self.client.post(
            f"/api/v3/responder/assignments/{assignment_id}/transition",
            headers=self.headers("responder"),
            json={"status": "RESOLVED", "notes": "Scene secured", "outcome": "Cleared"},
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        incident = self.client.get(f"/api/v3/incidents/{incident_id}", headers=self.headers("dispatcher")).json()["incident"]
        self.assertEqual(incident["state"], "RESOLVED")
        events = {item["event_type"] for item in incident["timeline"]}
        self.assertIn("ASSIGNMENT_RESOLVED", events)
        with connection() as conn:
            actions = {row["action"] for row in conn.execute("SELECT action FROM audit_logs WHERE entity_id IN (%s,%s)", (incident_id, assignment_id)).fetchall()}
        self.assertTrue({"incident.confirmed", "assignment.created", "assignment.accepted", "assignment.resolved"}.issubset(actions))
        self.assertEqual(self.client.get(f"/api/v3/incidents/{incident_id}", headers=self.headers("admin")).status_code, 200)
        self.assertEqual(self.client.get("/api/v3/admin/audit-logs", headers=self.headers("admin")).status_code, 200)

    def test_false_alarm_requires_reason_and_cannot_be_assigned(self):
        incident_id = self.create_incident()
        self.client.post(f"/api/v3/dispatcher/incidents/{incident_id}/claim", headers=self.headers("dispatcher"))
        missing = self.client.post(
            f"/api/v3/dispatcher/incidents/{incident_id}/review", headers=self.headers("dispatcher"),
            json={"decision": "FALSE_ALARM"},
        )
        self.assertEqual(missing.status_code, 400)
        done = self.client.post(
            f"/api/v3/dispatcher/incidents/{incident_id}/review", headers=self.headers("dispatcher"),
            json={"decision": "FALSE_ALARM", "falseAlarmReason": "Stationary parked vehicles"},
        )
        self.assertEqual(done.status_code, 200)
        assignment = self.client.post(
            f"/api/v3/dispatcher/incidents/{incident_id}/assign", headers=self.headers("dispatcher"),
            json={"responderId": self.accounts["responder"]["user"]["id"]},
        )
        self.assertEqual(assignment.status_code, 409)

    def test_responder_cannot_read_or_update_another_assignment(self):
        incident_id = self.create_incident()
        self.claim_and_confirm(incident_id)
        assigned = self.client.post(
            f"/api/v3/dispatcher/incidents/{incident_id}/assign", headers=self.headers("dispatcher"),
            json={"responderId": self.accounts["responder"]["user"]["id"]},
        ).json()["assignment"]
        self.assertEqual(self.client.get(f"/api/v3/incidents/{incident_id}", headers=self.headers("responder2")).status_code, 404)
        self.assertEqual(self.client.post(
            f"/api/v3/responder/assignments/{assigned['id']}/transition",
            headers=self.headers("responder2"), json={"status": "ACCEPTED"},
        ).status_code, 403)

    def test_concurrent_review_and_assignment_have_single_winner(self):
        incident_id = self.create_incident()
        dispatchers = [service.get_principal_by_id(self.accounts[name]["user"]["id"]) for name in ("dispatcher", "dispatcher2")]
        def claim(actor):
            try: service.claim_review(actor, incident_id); return "won"
            except service.Conflict: return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, dispatchers))
        self.assertEqual(sorted(results), ["conflict", "won"])
        winner = dispatchers[results.index("won")]
        service.complete_review(winner, incident_id, decision="CONFIRMED", priority="HIGH", incident_type="Collision", notes=None, false_alarm_reason=None)
        responders = [self.accounts[name]["user"]["id"] for name in ("responder", "responder2")]
        def assign(responder_id):
            try: service.assign_responder(winner, incident_id, responder_id); return "won"
            except service.Conflict: return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(assign, responders))
        self.assertEqual(sorted(results), ["conflict", "won"])


if __name__ == "__main__":
    unittest.main()
