"""Webcam integration with isolated worker dependencies; never opens hardware."""
import base64
import json
import threading
import time
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np
from backend.services import camera_sources as sources
from backend.validation.live_cctv_implementation_stage1_20261001.test_stage1 import worker, frame


def webcam_worker():
    m, ns = worker()
    m.stream_url = 'webcam://school-demo-webcam'
    ns.update(base64=base64, json=json)
    return m, ns


class PipelineTests(unittest.TestCase):
    def test_capture_preview_detector_and_exact_packet(self):
        m, ns = webcam_worker()
        cap = Mock()
        cap.get.return_value = 30
        def read():
            cap.received_at, cap.received_monotonic = time.time(), time.monotonic()
            if m.frame_seq == 4:
                m.running = False
            return True, frame(m.frame_seq + 1)
        cap.read.side_effect = read
        m.running = True
        with patch.object(sources, 'open_webcam', return_value=cap):
            m._capture_loop()
        self.assertEqual(m.frame_seq, 5)
        cap.release.assert_called_once()
        # Lifecycle intentionally clears pixels on disconnect. Analyze while connected below.
        m.seed_first_frame(frame(70))
        jpeg, headers = m.latest_preview_packet()
        self.assertEqual(headers['X-Frame-Sequence'], '6')
        self.assertEqual(cv2.imdecode(np.frombuffer(jpeg, np.uint8), 1).shape, (48, 64, 3))
        result = m.analyze_current_frame()
        np.testing.assert_array_equal(ns['model'].predict.call_args.args[0], frame(70))
        packet = m.latest_box_packet()
        self.assertEqual(packet['sourceFrame'], result['sourceFrame'])
        self.assertEqual(packet['sourceFrame']['sequence'], 6)
        self.assertIsNotNone(packet['sourceFrame']['capturedMonotonic'])
        ns['persist_sqlite_crash_case'].assert_not_called()

    def test_retry_budget_unavailable_and_interruptible_backoff(self):
        m, _ = webcam_worker()
        cap = Mock()
        cap.isOpened.return_value = False
        m.running = True
        with patch.object(sources, 'open_webcam', return_value=cap), patch.object(m.stop_event, 'wait') as wait:
            m._capture_loop()
        self.assertEqual(cap.release.call_count, sources.MAX_ATTEMPTS)
        self.assertEqual([c.args[0] for c in wait.call_args_list], [1, 2, 4, 8])
        self.assertEqual(m.status, 'connection-lost')
        self.assertIsNone(m.latest_frame)
        self.assertFalse(m.capture_worker_running)

    def test_reconnect_epoch_sequence_and_hit_window_preserved(self):
        m, _ = webcam_worker()
        m.hit_window.append(123)
        identities = []
        def make_capture():
            cap = Mock()
            cap.get.return_value = 30
            count = [0]
            def read():
                count[0] += 1
                if count[0] == 2:
                    identities.append((m.latest_frame_epoch, m.frame_seq))
                    if len(identities) == 2:
                        m.running = False
                    return False, None
                cap.received_at, cap.received_monotonic = time.time(), time.monotonic()
                return True, frame()
            cap.read.side_effect = read
            return cap
        m.running = True
        with patch.object(sources, 'open_webcam', side_effect=[make_capture(), make_capture()]), patch.object(m.stop_event, 'wait'):
            m._capture_loop()
        self.assertNotEqual(identities[0][0], identities[1][0])
        self.assertEqual([i[1] for i in identities], [1, 2])
        self.assertEqual(list(m.hit_window), [123])
        self.assertEqual(m.reconnect_count, 1)


class SavedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Run via run_isolated_tests.py to redirect application SQLite before import.
        import backend.main as app
        cls.app = app

    def test_authorization_denies_before_open_for_saved_and_raw_routes(self):
        from fastapi.testclient import TestClient
        app = self.app
        with patch.object(app, 'open_webcam') as opener, patch.object(sources, 'open_webcam') as child_opener:
            with TestClient(app.app) as client:
                requests = [('POST', '/api/cameras/TEST/monitor/start', {}),
                            ('POST', '/api/cameras/test-connection', {'cameraId':'TEST', 'url':'webcam://school-demo-webcam'}),
                            ('POST', '/api/detect/stream-frame', {'cameraId':'TEST', 'url':'webcam://school-demo-webcam'}),
                            ('GET', '/api/cameras/TEST/latest-frame.jpg', None),
                            ('GET', '/api/cameras/TEST/preview.mjpeg', None),
                            ('GET', '/api/cameras/TEST/analysis-packet', None)]
                for method, url, body in requests:
                    response = client.request(method, url, json=body)
                    self.assertIn(response.status_code, (401, 403, 404), (url, response.text))
            opener.assert_not_called()
            child_opener.assert_not_called()

    def test_strict_saved_validation_and_private_public_label(self):
        app = self.app
        for reference in ('1', '-1', '999999', 'C:\\secret.mp4', '/dev/video1', 'file:///secret',
                          'webcam://unknown', 'webcam://school-demo-webcam?index=0'):
            body = app.CameraRecordIn(cameraId='TEST', label='Test', areaId='test', streamUrl=reference)
            with patch.object(app, 'list_cameras', return_value=[]), self.assertRaises(app.HTTPException):
                app.validate_camera_record_payload(body)
        data = dict(cameraId='TEST', streamUrl='webcam://school-demo-webcam', cameraIp=None)
        payload = app.camera_client_payload(data)
        self.assertTrue(payload['streamConfigured'])
        self.assertEqual(payload['streamSourceLabel'], 'USB Webcam (REDRAGON Live Camera)')
        self.assertNotIn('webcam://', str(payload))
        self.assertNotIn('device_index', str(payload))

    def test_source_list_requires_editor_and_returns_only_safe_labels(self):
        from fastapi.testclient import TestClient
        app = self.app
        with TestClient(app.app) as client:
            self.assertEqual(client.get('/api/cameras/local-webcam-sources').status_code, 401)
            viewer = {'role': 'responder', 'permissions': ['cameras.view'], 'uid': 'viewer'}
            with patch.object(app, 'verify_session_user', return_value=viewer):
                self.assertEqual(client.get('/api/cameras/local-webcam-sources').status_code, 403)
            editor = {'role': 'dispatcher', 'permissions': ['cameras.create'], 'uid': 'editor'}
            with patch.object(app, 'verify_session_user', return_value=editor):
                response = client.get('/api/cameras/local-webcam-sources')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [{'reference': 'webcam://school-demo-webcam', 'name': 'USB Webcam (REDRAGON Live Camera)'}])
            self.assertNotIn('device_index', response.text)
            self.assertNotIn('msmf', response.text)

    def test_active_saved_acquisition_never_opens_second_device(self):
        app = self.app
        m, _ = webcam_worker()
        m.camera_id = 'TEST'
        m.seed_first_frame(frame(22))
        saved = dict(cameraId='TEST', streamUrl=m.stream_url, isActive=True)
        with patch.object(app, 'get_camera', return_value=saved), patch.object(app, 'monitor_for_camera', return_value=m), patch.object(app, 'open_webcam') as opener:
            result = app.grab_saved_camera_frame('TEST', m.stream_url)
            np.testing.assert_array_equal(result, frame(22))
            self.assertFalse(np.shares_memory(result, m.latest_frame))
            opener.assert_not_called()

    def test_preview_endpoint_serves_the_saved_webcam_frame(self):
        from fastapi.testclient import TestClient
        app = self.app
        monitor, _ = webcam_worker()
        monitor.camera_id = 'TEST'
        monitor.seed_first_frame(frame(44))
        saved = dict(cameraId='TEST', streamUrl=monitor.stream_url, isActive=True)
        with patch.object(app, 'resolve_camera_identifier', return_value=saved), \
             patch.object(app, 'require_camera_stream_access'), \
             patch.object(app, 'monitor_for_camera', return_value=monitor), \
             TestClient(app.app) as client:
            response = client.get('/api/cameras/TEST/latest-frame.jpg')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['x-frame-sequence'], '1')
        self.assertEqual(cv2.imdecode(np.frombuffer(response.content, np.uint8), 1).shape, (48, 64, 3))


if __name__ == '__main__':
    unittest.main()
