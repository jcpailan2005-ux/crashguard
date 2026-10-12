import threading
import time
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from fastapi import HTTPException
from fastapi.testclient import TestClient
import backend.main as app
from backend.phase3.permissions import ROLE_PERMISSIONS


def monitor():
    return app.LiveCameraMonitor(monitor_key='test', camera_id='test', camera_ip=None,
        stream_url='rtsp://test', label='Test', area_id='test', barangay=None,
        road_name=None, latitude=None, longitude=None, location='test',
        redacted_stream_url='rtsp://test', output_base='http://testserver')


class PreviewTests(unittest.TestCase):
    def test_detector_consumes_new_frames_once_and_stops_without_backlog(self):
        m = monitor()
        m.running = True
        entered = threading.Event()
        observed = []
        def analyze(**_):
            observed.append(m.frame_seq)
            entered.set()
        with patch.object(m, 'analyze_current_frame', side_effect=analyze), patch.object(app, 'LIVE_CAMERA_DETECTION_INTERVAL_MS', 0):
            worker = threading.Thread(target=m._detection_loop)
            worker.start()
            for i in range(5):
                m.seed_first_frame(np.full((2, 2, 3), i, np.uint8))
            self.assertTrue(entered.wait(2))
            time.sleep(.15)
            count = len(observed)
            time.sleep(.15)
            self.assertEqual(len(observed), count)
            self.assertEqual(observed[-1], 5)
            m.stop()
            worker.join(2)
            self.assertFalse(worker.is_alive())

    def test_capture_overwrites_native_frame_without_encoding_or_queue(self):
        m = monitor()
        m.running = True
        cap = MagicMock()
        frames = [np.full((48, 64, 3), i, np.uint8) for i in range(10)]
        def read():
            frame = frames.pop(0)
            if not frames:
                m.stop()
            return True, frame
        cap.read.side_effect = read
        with patch.object(app.cv2, 'VideoCapture', return_value=cap), patch.object(app.cv2, 'imencode') as encode, patch.object(app.time, 'sleep'):
            m._capture_loop()
        encode.assert_not_called()
        self.assertEqual(m.frame_seq, 10)
        self.assertEqual(int(m.latest_frame[0, 0, 0]), 9)
        self.assertFalse(hasattr(m, 'frame_queue'))
        cap.grab.assert_not_called()

    def test_preview_valid_cached_jpeg_and_capture_not_blocked_by_encoding(self):
        m = monitor()
        m.seed_first_frame(np.zeros((48, 64, 3), np.uint8))
        entered, release = threading.Event(), threading.Event()
        original = cv2.imencode
        def encode(*args):
            entered.set()
            release.wait(2)
            return original(*args)
        with patch.object(app.cv2, 'imencode', side_effect=encode):
            worker = threading.Thread(target=m.latest_jpeg)
            worker.start()
            self.assertTrue(entered.wait(2))
            m.seed_first_frame(np.full((48, 64, 3), 180, np.uint8))
            self.assertEqual(m.frame_seq, 2)
            release.set()
            worker.join(2)
        jpeg = m.latest_jpeg()
        self.assertIs(jpeg, m.latest_jpeg())
        decoded = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape, (48, 64, 3))
        self.assertGreater(decoded.mean(), 170)
        self.assertEqual(m.jpeg_encode_count, 2)


class CurrentEvidenceTests(unittest.TestCase):
    def analyze(self, *, hit_count=0, motion=False, positive=True, existing=True,
                notification_id='NOTICE', save_succeeds=True):
        m = monitor()
        m.seed_first_frame(np.zeros((48, 64, 3), np.uint8))
        for _ in range(hit_count):
            m.hit_window.append((time.time(), True))
        box = dict(label='car', confidence=.95, x=0, y=0, width=20, height=20)
        quality = dict(frameQualityStatus='good', qualityRejectionReason=None,
            blurScore=100, brightnessScore=100, contrastScore=100)
        with ExitStack() as stack:
            values = dict(analyze_frame_quality=quality, extract_detections=([], False, 0),
                classify_crash_frame=dict(crashClass='accident', accidentProbability=.99 if positive else .01),
                detect_vehicle_boxes=[box], filter_boxes_in_roi=([box], True),
                count_labels_from_results=0, crash_like_vehicle_interaction=motion,
                find_unresolved_camera_case=dict(caseId='OLD', status='pending_review') if existing else None,
                replace_case_evidence=None)
            for name, value in values.items():
                stack.enter_context(patch.object(app, name, return_value=value))
            predict = stack.enter_context(patch.object(app.model, 'predict', return_value=[]))
            stack.enter_context(patch.object(app.cv2, 'imwrite', return_value=False))
            stack.enter_context(patch.object(app, 'draw_detection_boxes_overlay', side_effect=lambda frame, boxes: frame))
            persist = stack.enter_context(patch.object(app, 'persist_sqlite_crash_case', return_value=dict(
                caseId='NEW', status='pending_review', casePersistenceStatus='created',
                createdNotificationId=notification_id) if save_succeeds else None))
            result = m.analyze_current_frame()
            self.assertEqual(predict.call_args.args[0].shape, (48, 64, 3))
            self.assertEqual(predict.call_args.kwargs['imgsz'], 640)
            if existing:
                persist.assert_not_called()
            else:
                persist.assert_called_once()
            with self.assertRaises(ValueError):
                m.analyze_current_frame(manual=True)
        return result

    def test_old_case_with_candidate_does_not_confirm_or_bypass_stabilization(self):
        result = self.analyze(motion=True)
        self.assertFalse(result['accident_detected'])
        self.assertTrue(result['existingCase'])
        self.assertEqual(result['finalDecision'], 'candidate')

    def test_duplicate_aftermath_suppresses_case_without_fresh_crash_boolean(self):
        result = self.analyze(hit_count=app.LIVE_CAMERA_REQUIRED_HITS, motion=False)
        self.assertEqual(result['finalDecision'], 'duplicate_active_case')
        self.assertFalse(result['accident_detected'])
        self.assertEqual(result['caseId'], 'OLD')
        self.assertFalse(result['caseCreated'])

    def test_independently_confirmed_duplicate_keeps_evidence_but_no_new_alarm_identity(self):
        result = self.analyze(hit_count=app.LIVE_CAMERA_REQUIRED_HITS, motion=True)
        self.assertTrue(result['temporalCrashVerified'])
        self.assertTrue(result['accident_detected'])
        self.assertEqual(result['finalDecision'], 'duplicate_active_case')
        self.assertFalse(result['caseCreated'])

    def test_clean_frame_does_not_inherit_active_case_evidence(self):
        self.assertFalse(self.analyze(positive=False)['accident_detected'])

    def test_confirmed_new_observation_creates_alarm_ready_identity(self):
        result = self.analyze(hit_count=app.LIVE_CAMERA_REQUIRED_HITS, motion=True, existing=False)
        self.assertTrue(result['accident_detected'])
        self.assertEqual(result['finalDecision'], 'confirmed_crash')
        self.assertTrue(result['caseCreated'])
        self.assertEqual(result['caseId'], 'NEW')

    def test_committed_incident_without_optional_notification_id_is_success(self):
        result = self.analyze(hit_count=app.LIVE_CAMERA_REQUIRED_HITS, motion=True,
                              existing=False, notification_id=None)
        self.assertEqual(result['persistenceStatus'], 'created')
        self.assertTrue(result['caseCreated'])
        self.assertIsNone(result['notificationId'])

    def test_failed_incident_save_reports_failure_without_created_case(self):
        result = self.analyze(hit_count=app.LIVE_CAMERA_REQUIRED_HITS, motion=True,
                              existing=False, save_succeeds=False)
        self.assertEqual(result['persistenceStatus'], 'failed')
        self.assertEqual(result['persistenceReason'], 'backend_save_failed')
        self.assertFalse(result['caseCreated'])


class PermissionTests(unittest.TestCase):
    def test_camera_create_and_delete_routes_enforce_postgres_cookie_permissions(self):
        for role in ('ADMIN', 'DISPATCHER', 'RESPONDER'):
            principal = dict(id='USER', role=role, permissions=list(ROLE_PERMISSIONS[role]))
            client = TestClient(app.app)
            client.cookies.set('crashguard_session', 'isolated-test-session')
            with patch('backend.phase3.service.authenticate_session', return_value=principal), \
                    patch.object(app, 'upsert_camera', return_value={'cameraId': 'TEST'}) as create, \
                    patch.object(app, 'delete_camera') as delete, \
                    patch.object(app, 'get_camera', return_value={'cameraType': 'RTSP'}):
                response = client.post('/api/cameras', json={
                    'label': 'Test', 'areaId': 'test', 'streamUrl': 'rtsp://127.0.0.1/live'})
                self.assertEqual(response.status_code, 200 if role in ('ADMIN', 'DISPATCHER') else 403)
                response = client.delete('/api/cameras/TEST')
                self.assertEqual(response.status_code, 200 if role == 'ADMIN' else 403)
                if role in ('ADMIN', 'DISPATCHER'):
                    create.assert_called_once()
                else:
                    create.assert_not_called()
                if role == 'ADMIN':
                    delete.assert_called_once()
                else:
                    delete.assert_not_called()

    def test_configured_role_policy_and_custom_dispatcher_grants(self):
        for role in ('ADMIN', 'DISPATCHER', 'RESPONDER'):
            for action in ('create', 'update', 'disable'):
                user = dict(role=role.lower(), permissions=list(ROLE_PERMISSIONS[role]))
                with patch.object(app, 'verify_session_user', return_value=user):
                    if role == 'ADMIN' or (role == 'DISPATCHER' and action == 'create'):
                        self.assertIs(app.require_camera_editor(MagicMock(), 'cameras.'+action), user)
                    else:
                        with self.assertRaises(HTTPException):
                            app.require_camera_editor(MagicMock(), 'cameras.'+action)
        with patch.object(app, 'verify_session_user', return_value=dict(role='dispatcher', permissions=['cameras.create'])):
            app.require_camera_editor(MagicMock(), 'cameras.create')

    def test_missing_session_does_not_gain_local_dispatcher_access(self):
        with patch.object(app, 'verify_session_user', side_effect=HTTPException(401, 'Authentication required')):
            with self.assertRaises(HTTPException) as ctx:
                app.require_camera_editor(MagicMock())
            self.assertEqual(ctx.exception.status_code, 401)

    def test_delete_permitted_normal_camera_and_protected_demo(self):
        user = dict(role='admin', permissions=['cameras.disable'])
        for camera, protected in [(dict(cameraType='RTSP'), False), (dict(cameraType='Demo'), True),
                                  (dict(streamUrl='demo://1'), True), (dict(cameraIp='demo-1'), True)]:
            with patch.object(app, 'verify_session_user', return_value=user), patch.object(app, 'get_camera', return_value=camera), patch.object(app, 'delete_camera') as delete:
                if protected:
                    with self.assertRaises(HTTPException):
                        app.api_delete_camera('CAM', MagicMock())
                    delete.assert_not_called()
                else:
                    app.api_delete_camera('CAM', MagicMock())
                    delete.assert_called_once_with('CAM')
