import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import backend.main as app
from backend.phase3.permissions import ROLE_PERMISSIONS


CAMERA = dict(cameraId='REPAIR-CAM', label='Test', cameraType='RTSP',
              streamUrl='rtsp://secret-user:secret-password@192.168.1.17:554/stream2')


class RepairSecurityTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.client = TestClient(app.app)
        for name, value in {'get_camera': CAMERA, 'resolve_camera_identifier': CAMERA,
                            'list_cameras': [CAMERA], 'monitor_for_camera': None}.items():
            self.stack.enter_context(patch.object(app, name, return_value=value))
        self.stack.enter_context(patch('backend.phase3.service.authenticate_session', return_value=None))

    def authenticate(self, role, **extra):
        principal = dict(id='USER', role=role.lower(), roles=[role], sessionId='SESSION',
                         permissions=list(ROLE_PERMISSIONS[role]), **extra)
        self.stack.enter_context(patch('backend.phase3.service.authenticate_session', return_value=principal))
        self.client.cookies.set('crashguard_session', 'test-session')
        return principal

    def test_unauthenticated_camera_routes_fail_closed(self):
        # All side effects are stubbed: no physical camera or user data touched.
        for name in ('grab_frame_from_stream_url', 'start_live_camera_monitor', 'stop_live_camera_monitor', 'upsert_camera',
                     'delete_camera', 'set_camera_active', '_test_camera_connection_sync',
                     '_detect_stream_frame_sync'):
            self.stack.enter_context(patch.object(app, name, return_value={}))
        routes = [
            ('get', '/api/cameras', None), ('get', '/api/cameras/REPAIR-CAM', None),
            ('get', '/api/cameras/REPAIR-CAM/status', None),
            ('get', '/api/cameras/REPAIR-CAM/preview.mjpeg', None),
            ('head', '/api/cameras/REPAIR-CAM/preview.mjpeg', None),
            ('get', '/api/cameras/REPAIR-CAM/latest-frame.jpg', None),
            ('get', '/api/cameras/REPAIR-CAM/events', None),
            ('post', '/api/cameras/REPAIR-CAM/monitor/start', None),
            ('post', '/api/cameras/REPAIR-CAM/monitor/stop', None),
            ('post', '/api/cameras/REPAIR-CAM/stream-token', None),
            ('post', '/api/cameras/REPAIR-CAM/test-detection', None),
            ('get', '/api/camera/status', None), ('post', '/api/camera/test-detection', None),
            ('post', '/api/cameras', {'label':'Test', 'areaId':'demo', 'streamUrl':CAMERA['streamUrl']}),
            ('delete', '/api/cameras/REPAIR-CAM', None),
            ('post', '/api/cameras/REPAIR-CAM/enable', None),
            ('post', '/api/cameras/REPAIR-CAM/disable', None),
            ('post', '/api/cameras/test-connection', {'url':CAMERA['streamUrl']}),
            ('post', '/api/detect/stream-frame', {'url':CAMERA['streamUrl']}),
        ]
        for method, path, body in routes:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path, json=body)
                self.assertEqual(response.status_code, 401, response.text)

    def test_responder_cannot_monitor_or_manage_cameras(self):
        self.authenticate('RESPONDER')
        for path in ('/api/cameras', '/api/cameras/REPAIR-CAM/status',
                     '/api/cameras/REPAIR-CAM/preview.mjpeg'):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post('/api/cameras/REPAIR-CAM/monitor/stop').status_code, 403)

    def test_authorized_camera_reads_never_expose_credentials(self):
        for role in ('ADMIN', 'DISPATCHER'):
            self.authenticate(role)
            for path in ('/api/cameras', '/api/cameras/REPAIR-CAM', '/api/cameras/REPAIR-CAM/status'):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotIn('secret-user', response.text)
                self.assertNotIn('secret-password', response.text)

    def test_missing_permission_and_password_change_gate(self):
        self.authenticate('DISPATCHER', mustChangePassword=True)
        self.assertEqual(self.client.get('/api/cameras').status_code, 403)

    def test_legacy_action_rejects_responder_and_uses_real_actor(self):
        action = self.stack.enter_context(patch.object(app, 'apply_action', return_value={'ok':True}))
        self.authenticate('RESPONDER')
        response = self.client.post('/api/crash-cases/CASE/actions', json={'action':'confirm_crash','actorId':'SPOOF'})
        self.assertEqual(response.status_code, 403)
        action.assert_not_called()
        self.authenticate('DISPATCHER')
        response = self.client.post('/api/crash-cases/CASE/actions', json={'action':'confirm_crash','actorId':'SPOOF'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(action.call_args.args[2], 'USER')

    def test_cookie_only_user_is_attributed(self):
        self.authenticate('DISPATCHER')
        request = MagicMock(headers={}, cookies={'crashguard_session':'test-session'})
        self.assertEqual(app.optional_request_user(request)['uid'], 'USER')

    def test_validation_errors_do_not_echo_connection_credentials(self):
        self.authenticate('ADMIN')
        response = self.client.post('/api/cameras/test-connection', json={
            'url': CAMERA['streamUrl'] + 'x' * 2100})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('secret-user', response.text)
        self.assertNotIn('secret-password', response.text)

    def test_mutation_response_redacts_and_edit_preserves_stored_stream(self):
        self.authenticate('ADMIN')
        with patch.object(app, 'upsert_camera', return_value=CAMERA) as save:
            response = self.client.put('/api/cameras/REPAIR-CAM', json={'label':'Updated', 'areaId':'demo'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(save.call_args.args[0]['streamUrl'], CAMERA['streamUrl'])
        self.assertNotIn('secret-user', response.text)
        self.assertNotIn('secret-password', response.text)

    def test_stream_ingestion_requires_saved_camera_and_uses_saved_source(self):
        self.authenticate('DISPATCHER')
        with patch.object(app, '_detect_stream_frame_sync', return_value={'ok': True}) as detect:
            response = self.client.post('/api/detect/stream-frame', json={'url':'http://127.0.0.1/private'})
            self.assertEqual(response.status_code, 400)
            detect.assert_not_called()
            response = self.client.post('/api/detect/stream-frame', json={
                'cameraId':'REPAIR-CAM', 'url':'http://127.0.0.1/private'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(detect.call_args.args[1].url, CAMERA['streamUrl'])

    def test_connection_test_does_not_create_or_start_camera(self):
        import numpy as np
        self.authenticate('ADMIN')
        with patch.object(app, 'grab_frame_from_stream_url', return_value=np.zeros((4,4,3))), \
             patch.object(app, 'upsert_camera') as save, patch.object(app, 'start_live_camera_monitor') as start:
            response = self.client.post('/api/cameras/test-connection', json={'url':CAMERA['streamUrl']})
        self.assertEqual(response.status_code, 200, response.text)
        save.assert_not_called()
        start.assert_not_called()

    def test_camera_host_policy_requires_local_address_or_explicit_host(self):
        with patch.dict('os.environ', {'AUTHORIZED_CAMERA_HOSTS': 'camera.example'}):
            self.assertTrue(app.is_authorized_camera_host('192.168.1.17'))
            self.assertTrue(app.is_authorized_camera_host('camera.example'))
            self.assertFalse(app.is_authorized_camera_host('unapproved.example'))

    def test_unsigned_bearer_is_not_an_operational_identity(self):
        import base64, json
        token = 'e30.' + base64.urlsafe_b64encode(json.dumps({'sub':'attacker','role':'admin'}).encode()).decode().rstrip('=') + '.unsigned'
        self.stack.enter_context(patch.object(app, 'upsert_user_profile'))
        response = self.client.get('/api/camera-settings', headers={'Authorization':f'Bearer {token}'})
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
