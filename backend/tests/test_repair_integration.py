"""CONTROLLED_INTEGRATION_TEST: real SQLite, simulated detector decision.

No physical camera and no model inference. All data belongs to an explicitly
isolated temporary SQLite database. No deletion or truncation is performed here.
"""
import os
import tempfile
from pathlib import Path
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as app
from backend.db import get_connection
from backend.phase3 import service
from backend.phase3.database import connection, DatabaseUnavailable
from backend.services.operational_detection import persist_operational_detection


class ControlledIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.getenv('CRASHGUARD_SQLITE_PATH', '')).resolve()
        if not path.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError('CONTROLLED_INTEGRATION_TEST requires temporary SQLite storage.')
        cls.clients = {}
        cls.users = {}
        for role in ('ADMIN', 'DISPATCHER', 'RESPONDER'):
            user = service.create_user(None, email=f'repair-{uuid.uuid4().hex}@test.local',
                                       full_name=f'Repair {role}', role=role)
            client = TestClient(app.app)
            response = client.post('/api/v3/auth/login', json={'email':user['email'], 'password':user['temporaryPassword']})
            if response.status_code != 200:
                raise AssertionError(response.text)
            response = client.post('/api/v3/auth/change-password', json={
                'currentPassword':user['temporaryPassword'], 'newPassword':'IsolatedRepair9!Password'})
            if response.status_code != 200:
                raise AssertionError(response.text)
            cls.clients[role] = client
            cls.users[role] = response.json()['user']

    def payload(self, decision='confirmed_crash'):
        return dict(media_type='image', source_file='CONTROLLED_INTEGRATION_TEST',
            confidence=.95, timestamp=datetime.now(timezone.utc).isoformat(), location='Isolated test',
            original_path=None, annotated_url=None, annotated_download_url=None, key_frame_url=None,
            trigger_status='camera_detection', final_decision=decision, vehicle_count=2,
            scene_valid=True, motion_valid=True, crash_score=.95, consecutive_crash_hits=3,
            route='CONTROLLED_INTEGRATION_TEST', camera_id='REPAIR-' + uuid.uuid4().hex,
            detector_event_id='CONTROLLED_INTEGRATION_TEST:' + uuid.uuid4().hex)

    def test_controlled_detection_dispatch_and_responder(self):
        payload = self.payload()
        result = app.persist_sqlite_crash_case(**payload)
        self.assertIsNotNone(result)
        self.assertTrue(result['incidentCreated'])
        self.assertEqual(result['casePersistenceStatus'], 'created')
        self.assertIsNone(result['createdNotificationId'])
        self.assertGreaterEqual(result['notificationCount'], 1)
        incident_id = result['incidentId']
        repeated = app.persist_sqlite_crash_case(**payload)
        self.assertEqual(repeated['incidentId'], incident_id)
        self.assertFalse(repeated['incidentCreated'])
        with ThreadPoolExecutor(max_workers=4) as pool:
            replayed = list(pool.map(lambda _: app.persist_sqlite_crash_case(**payload), range(8)))
        self.assertTrue(all(r['incidentId'] == incident_id and not r['incidentCreated'] for r in replayed))
        with connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM incidents WHERE detector_event_id=%s',
                                          (payload['detector_event_id'],)).fetchone()['n'], 1)
            row = conn.execute('SELECT state FROM incidents WHERE id=%s', (incident_id,)).fetchone()
            self.assertEqual(row['state'], 'AWAITING_REVIEW')
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM alerts WHERE incident_id=%s', (incident_id,)).fetchone()['n'], 1)
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM audit_logs WHERE action='incident.ai_created' AND entity_id=%s", (incident_id,)).fetchone()['n'], 1)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM notifications WHERE incident_id=%s AND user_id=%s',
                                          (incident_id, self.users['RESPONDER']['id'])).fetchone()['n'], 0)
        dispatcher = self.clients['DISPATCHER']
        response = dispatcher.get('/api/v3/incidents')
        self.assertEqual(response.status_code, 200)
        self.assertIn(incident_id, [i['id'] for i in response.json()['incidents']])
        self.assertEqual(TestClient(app.app).get('/api/v3/incidents').status_code, 401)
        self.assertEqual(dispatcher.post(f'/api/v3/dispatcher/incidents/{incident_id}/claim').status_code, 200)
        response = dispatcher.post(f'/api/v3/dispatcher/incidents/{incident_id}/review', json={
            'decision':'CONFIRMED', 'priority':'HIGH', 'incidentType':'Vehicle collision'})
        self.assertEqual(response.status_code, 200, response.text)
        responder = self.clients['RESPONDER']
        response = responder.post('/api/v3/responder/availability', json={'status':'AVAILABLE'})
        self.assertEqual(response.status_code, 200, response.text)
        response = dispatcher.post(f'/api/v3/dispatcher/incidents/{incident_id}/assign', json={'responderId':self.users['RESPONDER']['id']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(responder.get(f'/api/v3/incidents/{incident_id}').status_code, 200)
        with get_connection() as conn:
            self.assertIsNone(conn.execute('SELECT caseId FROM crash_cases WHERE caseId=?', (incident_id,)).fetchone())

    def test_candidates_do_not_create_operational_incidents(self):
        for decision in ('candidate', 'ignored', 'temporal_not_verified', 'possible_crash'):
            event_id = 'candidate:' + uuid.uuid4().hex
            self.assertIsNone(persist_operational_detection({'finalDecision':decision, 'detectorEventId':event_id}))
            with connection() as conn:
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM incidents WHERE detector_event_id=%s', (event_id,)).fetchone()['n'], 0)

    def test_aftermath_remains_human_review_not_confirmed(self):
        result = app.persist_sqlite_crash_case(**self.payload('possible_crash_aftermath'))
        with connection() as conn:
            row = conn.execute('SELECT state,detection_mode FROM incidents WHERE id=%s', (result['incidentId'],)).fetchone()
        self.assertEqual(row, {'state':'AWAITING_REVIEW', 'detection_mode':'aftermath_review'})

    def test_real_persistence_failure_can_retry_same_event(self):
        payload = self.payload()
        with patch('backend.phase3.service.create_ai_incident', side_effect=DatabaseUnavailable('unavailable')):
            self.assertIsNone(app.persist_sqlite_crash_case(**payload))
        result = app.persist_sqlite_crash_case(**payload)
        self.assertTrue(result['incidentCreated'])

    def test_simultaneous_first_observations_commit_once(self):
        payload = self.payload()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: app.persist_sqlite_crash_case(**payload), range(8)))
        self.assertEqual(sum(result['incidentCreated'] for result in results), 1)
        self.assertEqual(len({result['incidentId'] for result in results}), 1)

    def test_sqlite_camera_responses_and_audit_never_return_credentials(self):
        admin = self.clients['ADMIN']
        secret_url = 'rtsp://repair-secret-user:repair-secret-password@192.168.1.17/live'
        response = admin.post('/api/v3/cameras', json={'name':'Privacy test', 'streamReference':secret_url})
        self.assertEqual(response.status_code, 200, response.text)
        camera_id = response.json()['camera']['id']
        for response in (response, admin.get('/api/v3/cameras'), admin.get('/api/v3/admin/audit-logs'),
                         admin.put(f'/api/v3/cameras/{camera_id}', json={'name':'Updated privacy test'})):
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn('repair-secret-user', response.text)
            self.assertNotIn('repair-secret-password', response.text)
        with connection() as conn:
            self.assertEqual(conn.execute('SELECT stream_reference FROM cameras WHERE id=%s', (camera_id,)).fetchone()['stream_reference'], secret_url)

    def test_z_camera_ticket_uses_sqlite_session_and_revokes_on_logout(self):
        admin = self.clients['ADMIN']
        token = admin.cookies.get('crashguard_session')
        principal = service.authenticate_session(token)
        ticket = app.create_camera_stream_token({**principal, 'uid':principal['id']}, 'TEST-CAMERA')
        verified = app.verify_camera_stream_token(ticket, 'TEST-CAMERA')
        self.assertIn('cameras.monitor', verified['permissions'])
        self.assertEqual(admin.post('/api/v3/auth/logout').status_code, 200)
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as error:
            app.verify_camera_stream_token(ticket, 'TEST-CAMERA')
        self.assertEqual(error.exception.status_code, 401)


if __name__ == '__main__':
    unittest.main()
