"""Current worker, isolated from app startup, models, camera and databases."""
import ast
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlparse, quote

import cv2
import numpy as np
from backend.tests import test_live_collision_diagnostics as fixture
from backend.services.inference_execution import bounded_inference
from backend.camera_privacy import redact_camera_text

ROOT = Path(__file__).resolve().parents[3]


def worker(source=None, camera_id='TEST'):
    source = Path(source or ROOT / 'backend/main.py')
    with patch.object(fixture, 'SOURCE', source):
        ns = fixture.load_worker()
    ns.update(cv2=cv2, urlparse=urlparse, quote=quote, bounded_inference=bounded_inference,
              LIVE_CAMERA_JPEG_QUALITY=75, LIVE_CAMERA_DETECTION_INTERVAL_MS=0,
              LIVE_CAMERA_DUPLICATE_CASE_BLOCK_SECONDS=60, log_stream=lambda *_: None,
              QUALITY_REJECTION_MESSAGES={}, redact_camera_text=redact_camera_text)
    tree = ast.parse(source.read_text(encoding='utf-8'))
    preview = next(n for n in tree.body if isinstance(n, ast.Assign) and
                   any(isinstance(t, ast.Name) and t.id == 'LIVE_CAMERA_PREVIEW_FPS' for t in n.targets))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveCameraMonitor')
    exec(compile(ast.Module(body=[preview, cls], type_ignores=[]), str(source), 'exec'), ns)
    m = ns['LiveCameraMonitor'](monitor_key='rtsp://user:secret@host', camera_id=camera_id,
        camera_ip=None, stream_url='rtsp://user:secret@host', label='Test', area_id='test',
        barangay=None, road_name=None, latitude=None, longitude=None, location='test',
        redacted_stream_url='rtsp://host', output_base='http://test')
    ns.update(model=SimpleNamespace(predict=Mock(return_value=[]), names={}), vehicle_model=None,
        analyze_frame_quality=lambda _: dict(frameQualityStatus='good', qualityRejectionReason=None,
                                              blurScore=100, brightnessScore=100, contrastScore=100),
        extract_detections=lambda _: ([], False, 0),
        classify_crash_frame=lambda _: dict(crashClass='non_accident', accidentProbability=.01),
        find_unresolved_camera_case=lambda *a, **k: None, log_crash_decision=lambda **k: None,
        persist_sqlite_crash_case=Mock(side_effect=AssertionError('Persistence forbidden')))
    return m, ns


def frame(value=0):
    return np.full((48, 64, 3), value, np.uint8)


class Stage1Tests(unittest.TestCase):
    def test_sequence_slot_and_seed_ownership(self):
        m, _ = worker()
        source = frame()
        for i in range(20):
            source.fill(i)
            m.seed_first_frame(source)
        source.fill(99)
        self.assertEqual(m.frame_seq, 20)
        self.assertEqual(int(m.latest_frame[0, 0, 0]), 19)
        self.assertFalse(hasattr(m, 'frame_queue'))
        self.assertEqual(m.capture_timestamps.maxlen, 300)

    def test_metadata_and_api_are_additive(self):
        m, _ = worker()
        m.seed_first_frame(frame())
        at = m.last_frame_at
        result = m.analyze_current_frame()
        self.assertEqual(result['sourceFrame']['sequence'], 1)
        self.assertEqual(result['sourceFrame']['cameraId'], 'TEST')
        self.assertEqual(result['sourceFrame']['capturedAt'], at)
        self.assertEqual(result['sourceFrame']['width'], 64)
        self.assertLessEqual(at, result['inferenceStartedAt'])
        self.assertLessEqual(result['inferenceStartedAt'], result['inferenceFinishedAt'])
        self.assertGreaterEqual(result['modelProcessingMs'], 0)
        self.assertTrue(result['success'])
        self.assertFalse(result['accident_detected'])
        self.assertEqual(result['boxes'], [])
        status = m.snapshot_status()
        self.assertEqual(status['latestFrameIdentity'], result['sourceFrame'])
        self.assertIs(status['latestResult'], result)

    def test_slow_inference_capture_preview_newest_and_no_backlog(self):
        m, ns = worker()
        m.seed_first_frame(frame(1))
        entered, release = threading.Event(), threading.Event()
        outputs, errors = [], []
        def predict(image, **_):
            self.assertTrue(m.lock.acquire(blocking=False))
            m.lock.release()
            entered.set()
            if not release.wait(3):
                raise AssertionError('test release timed out')
            self.assertEqual(int(image[0, 0, 0]), 1)
            return []
        ns['model'].predict = predict
        def analyze():
            try:
                outputs.append(m.analyze_current_frame())
            except Exception as e:
                errors.append(e)
        t = threading.Thread(target=analyze)
        t.start()
        try:
            self.assertTrue(entered.wait(2))
            for i in range(2, 12):
                m.seed_first_frame(frame(i))
            jpeg, headers = m.latest_preview_packet()
            self.assertEqual(headers['X-Frame-Sequence'], '11')
            self.assertIsNotNone(jpeg)
            self.assertEqual(m.frame_seq, 11)
            with self.assertRaises(ValueError):
                m.analyze_current_frame()
        finally:
            release.set()
            t.join(3)
        self.assertFalse(t.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(outputs[0]['sourceFrame']['sequence'], 1)
        self.assertEqual(m.latest_result['sourceFrame']['sequence'], 1)
        ns['model'].predict = Mock(return_value=[])
        latest = m.analyze_current_frame()
        self.assertEqual(latest['sourceFrame']['sequence'], 11)
        self.assertEqual(m.dropped_frame_count, 9)
        self.assertEqual(int(ns['model'].predict.call_args.args[0][0, 0, 0]), 11)
        with self.assertRaises(ValueError):
            m.analyze_current_frame()

    def test_copy_is_outside_capture_lock(self):
        m, _ = worker()
        class CheckedFrame(np.ndarray):
            def copy(self, *args, **kwargs):
                acquired = m.lock.acquire(blocking=False)
                if not acquired:
                    raise AssertionError('copy holds capture lock')
                m.lock.release()
                return super().copy(*args, **kwargs)
        m.seed_first_frame(frame().view(CheckedFrame))
        m.analyze_current_frame()

    def test_preview_metadata_pinned_during_capture_and_encoding(self):
        m, _ = worker()
        m.seed_first_frame(frame(1))
        encode = cv2.imencode
        def concurrent(*a, **k):
            self.assertTrue(m.lock.acquire(blocking=False))
            m.lock.release()
            m.seed_first_frame(frame(200))
            return encode(*a, **k)
        with patch.object(cv2, 'imencode', side_effect=concurrent):
            jpeg, headers = m.latest_preview_packet()
        self.assertEqual(headers['X-Frame-Sequence'], '1')
        self.assertEqual(headers['X-Frame-Session'], m.latest_frame_epoch)
        self.assertLess(cv2.imdecode(np.frombuffer(jpeg, np.uint8), 1).mean(), 10)
        self.assertEqual(m.frame_seq, 2)
        self.assertEqual(m.latest_preview_packet()[1]['X-Frame-Sequence'], '2')

    def test_monotonic_preview_age_survives_wall_clock_jump(self):
        m, _ = worker()
        m.seed_first_frame(frame())
        m.latest_preview_packet()
        with patch.object(time, 'time', return_value=m.last_frame_at - 3600):
            _, headers = m.latest_preview_packet()
        self.assertGreaterEqual(float(headers['X-Jpeg-Send-Age-Ms']), 0)
        self.assertLess(float(headers['X-Jpeg-Send-Age-Ms']), 1000)

    def test_reconnect_epoch_does_not_relabel_previous_frame(self):
        m, ns = worker()
        m.seed_first_frame(frame())
        old = m.latest_preview_packet()[1]
        m.running = True
        cap = Mock()
        cap.get.return_value = 15
        def read():
            self.assertEqual(m.latest_preview_packet()[1]['X-Frame-Session'], old['X-Frame-Session'])
            m.stop()
            return True, frame(100)
        cap.read.side_effect = read
        with patch.object(cv2, 'VideoCapture', return_value=cap), patch.object(time, 'sleep'):
            m._capture_loop()
        new = m.latest_preview_packet()[1]
        self.assertNotEqual(new['X-Frame-Session'], old['X-Frame-Session'])
        self.assertEqual(new['X-Frame-Sequence'], '2')

    def test_metadata_never_uses_credential_bearing_fallback(self):
        for identifier in (None, 'rtsp://user:secret@host'):
            m, _ = worker(camera_id=identifier)
            m.seed_first_frame(frame())
            metadata = m.analyze_current_frame()['sourceFrame']
            headers = m.latest_preview_packet()[1]
            self.assertTrue(metadata['cameraId'].startswith('live-'))
            self.assertEqual(headers['X-Frame-Camera-Id'], metadata['cameraId'])
            self.assertNotIn('secret', str(metadata) + str(headers))
            self.assertNotIn('rtsp:', str(metadata) + str(headers))

    def test_global_model_gate_remains_nonblocking(self):
        from backend.services import inference_execution
        m, _ = worker()
        m.seed_first_frame(frame())
        entered, release = threading.Event(), threading.Event()
        def hold():
            with inference_execution._inference_lock:
                entered.set()
                release.wait(3)
        t = threading.Thread(target=hold)
        t.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(Exception) as error:
                m.analyze_current_frame()
            self.assertEqual(error.exception.status_code, 503)
            self.assertEqual(m.last_analyzed_frame_seq, 0)
            m.seed_first_frame(frame(2))
        finally:
            release.set()
            t.join(3)
        self.assertEqual(m.analyze_current_frame()['sourceFrame']['sequence'], 2)

    def test_slow_consumer_resumes_latest_and_cache_is_bounded(self):
        m, _ = worker()
        m.running = True
        m.seed_first_frame(frame())
        stream = m.mjpeg_stream()
        self.assertIn(b'X-Frame-Sequence: 1', next(stream))
        for i in range(1, 21):
            m.seed_first_frame(frame(i))
        self.assertIn(b'X-Frame-Sequence: 21', next(stream))
        self.assertEqual(m.jpeg_encode_count, 2)
        m.stop()
        stream.close()

    def test_preview_deadline_includes_encoding_and_respects_source_rate(self):
        m, ns = worker()
        clock = [0.0]
        waits = []
        def wait(delay):
            waits.append(delay)
            clock[0] += delay
            return False
        m.stop_event = SimpleNamespace(wait=wait)
        m.running = True
        m.source_reported_fps = 5.0
        ns['LIVE_CAMERA_PREVIEW_FPS'] = 15
        ns['time'] = SimpleNamespace(perf_counter=lambda: clock[0])
        def packet():
            clock[0] += .02
            return b'jpeg', {}
        m.latest_preview_packet = packet
        stream = m.mjpeg_stream()
        next(stream)
        next(stream)
        self.assertAlmostEqual(waits[-1], .18)  # 5 Hz minus encode cost
        clock[0] += 2  # slow reader: no replay/catch-up queue
        next(stream)
        self.assertEqual(waits[-1], 0)
        m.running = False
        stream.close()

    def test_before_after_collision_outputs_identical(self):
        case = fixture.LiveDiagnosticsTests()
        scenarios = [([.95, .95, .95], {}), ([.95, .95, .89], {}),
                     ([.95, .95, .95], {'times': [1000, 1001, 1007]}),
                     ([.95, .95, .95], {'boxes': [fixture.raw('motorcycle')]}),
                     ([.01, .01, .01], {})]
        for scores, kwargs in scenarios:
            with self.subTest(scores=scores, options=str(kwargs)):
                with patch.object(fixture, 'SOURCE', Path(__file__).parent/'main_before.py.txt'):
                    before = case.run_sequence(scores, False, **kwargs)[0]
                after = case.run_sequence(scores, False, **kwargs)[0]
                self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
