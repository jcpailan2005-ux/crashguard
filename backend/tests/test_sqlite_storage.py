"""SQLite transactions, type round trips, and local camera-status scope."""
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.phase3 import database, service
from backend.phase3.routes import current_user, router


class SQLiteStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='crashguard-sqlite-test-')
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {'CRASHGUARD_SQLITE_PATH': str(Path(self.temp.name) / 'operations.sqlite')})
        env.start()
        self.addCleanup(env.stop)
        self.user_id = str(uuid.uuid4())
        with database.connection() as conn, conn.transaction():
            conn.execute('''INSERT INTO users(id,email,full_name,password_hash,must_change_password)
                            VALUES (%s,%s,%s,%s,FALSE)''',
                         (self.user_id, 'fixture@example.invalid', 'Fixture Responder', 'unused-test-only-hash'))
        self.actor = {'id': self.user_id, 'role': 'responder', 'roles': ['RESPONDER'],
                      'areaId': 'AREA-TEST', 'mustChangePassword': False,
                      'permissions': ['profile.view_own', 'assignments.view_own']}
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[current_user] = lambda: self.actor
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_network_database_configuration_is_ignored(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://invalid.invalid/unreachable'}), \
             patch('socket.socket.connect') as connect:
            self.assertEqual(database.check_database()['engine'], 'sqlite')
            connect.assert_not_called()

    def test_failed_transaction_rolls_back_and_releases_writer(self):
        with self.assertRaises(RuntimeError):
            with database.connection() as conn, conn.transaction():
                conn.execute("INSERT INTO areas(name) VALUES ('Rolled back')")
                raise RuntimeError('abort fixture')
        with database.connection() as conn, conn.transaction():
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM areas').fetchone()['n'], 0)
            conn.execute("INSERT INTO areas(name) VALUES ('Next writer')")

    def test_email_uniqueness_is_case_insensitive(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with database.connection() as conn, conn.transaction():
                conn.execute('INSERT INTO users(email,full_name,password_hash) VALUES (%s,%s,%s)',
                             ('FIXTURE@EXAMPLE.INVALID', 'Duplicate', 'unused-test-only-hash'))

    def test_foreign_keys_remain_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with database.connection() as conn, conn.transaction():
                conn.execute('INSERT INTO user_preferences(user_id) VALUES (%s)', (str(uuid.uuid4()),))

    def test_preferences_keep_json_booleans_and_timestamps(self):
        updated = service.update_own_preferences(self.actor, theme='dark',
                                                notification_preferences={'alarmAudio': False})
        self.assertFalse(updated['notification_preferences']['alarmAudio'])
        self.assertIn('T', updated['updated_at'])
        self.assertFalse(service.get_own_preferences(self.actor)['notification_preferences']['alarmAudio'])

    def test_camera_status_is_persistent_and_area_scoped(self):
        saved = self.client.put('/api/v3/live-camera-sessions/AREA-TEST', json={'active': True})
        self.assertEqual(saved.status_code, 200, saved.text)
        saved = self.client.put('/api/v3/live-camera-sessions/AREA-TEST', json={'latestDetection': None})
        self.assertEqual(saved.status_code, 200, saved.text)
        state = self.client.get('/api/v3/live-camera-sessions/AREA-TEST').json()['session']
        self.assertTrue(state['active'])
        self.assertEqual(state['responderUid'], self.user_id)
        self.assertEqual(self.client.get('/api/v3/live-camera-sessions/OTHER-AREA').status_code, 403)
        self.assertEqual(self.client.put('/api/v3/live-camera-sessions/OTHER-AREA', json={'active': True}).status_code, 403)

    def test_password_change_and_status_size_guards_are_preserved(self):
        self.actor['mustChangePassword'] = True
        self.assertEqual(self.client.get('/api/v3/live-camera-sessions/AREA-TEST').status_code, 403)
        self.actor['mustChangePassword'] = False
        self.assertEqual(self.client.put('/api/v3/live-camera-sessions/AREA-TEST',
                                         json={'livePreviewDataUrl': 'https://example.invalid/image.jpg'}).status_code, 422)
        self.assertEqual(self.client.put('/api/v3/live-camera-sessions/AREA-TEST',
                                         json={'livePreviewDataUrl': 'x' * 400001}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
